"""OpenRouter-Client mit interaktivem Key-Flow.

Liest den Key aus ~/.config/mojo/openrouter_key. Existiert die Datei nicht,
wird einmalig im Terminal gefragt (getpass), Key wird dann mit chmod 600 gespeichert.
"""

from __future__ import annotations

import getpass
import os
import sys
from dataclasses import dataclass, field

import httpx
from openai import OpenAI

import journal_bot.settings as settings
from journal_bot.settings import KEY_FILE, OPENROUTER_BASE_URL


def _load_or_prompt_key() -> str:
    # 1. Environment-Override (für Tests / CI)
    env_key = os.environ.get("OPENROUTER_API_KEY")
    if env_key:
        return env_key.strip()

    # 2. Gespeicherte Datei
    if KEY_FILE.exists():
        key = KEY_FILE.read_text().strip()
        if key:
            return key

    # 3. Interaktive Abfrage (nur wenn wir im Terminal sind)
    if not sys.stdin.isatty():
        raise RuntimeError(
            f"Kein OpenRouter-Key gefunden ({KEY_FILE}), und ich laufe nicht im Terminal. "
            f"Leg ihn an oder setze OPENROUTER_API_KEY."
        )

    print("Kein OpenRouter-Key gefunden.")
    print("Hol ihn unter https://openrouter.ai/keys (Create new).")
    key = getpass.getpass("Key hier einfügen (Eingabe wird nicht angezeigt): ").strip()
    if not key:
        raise RuntimeError("Kein Key eingegeben.")

    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_text(key + "\n")
    KEY_FILE.chmod(0o600)
    print(f"Gespeichert in {KEY_FILE} (chmod 600).")
    return key


def build_client() -> OpenAI:
    # timeout/max_retries: Hard-Limits gegen hängende Verbindungen.
    #
    # Vorfall 2026-05-23: Trends-Call (MiMo) lief 33+ min mit 100% CPU,
    # während die TCP-Verbindung zu OpenRouter bereits in CLOSE_WAIT war.
    # Ohne explizites timeout fällt die OpenAI-SDK auf ihren Default zurück
    # (kann je nach Version >10 min oder gar None sein) und retried zudem
    # transparent — was bei einem hängenden Stream zu Endlos-Loops führt.
    #
    # 600s = 10 min Hard-Cap. Trends ist der teuerste Call und liegt
    # normalerweise bei 60–180s; assess/verify/screen/summarize deutlich
    # darunter. 10 min ist großzügiges Sicherheitsnetz, schneidet aber
    # 30-min-Hänger sofort ab.
    #
    # max_retries=1: ein einziger Retry bei transientem Netzwerk-Fehler,
    # kein stilles Mehrfach-Wiederholen langlaufender Calls.
    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=_load_or_prompt_key(),
        timeout=600.0,
        max_retries=1,
        default_headers={
            "HTTP-Referer": "https://localhost/mojo",
            "X-Title": "mojo",
        },
    )


# ────────────────────────────────────────────────────────────────────
# Research backend: cloud (OpenRouter) vs. local (Ollama, free)
# ────────────────────────────────────────────────────────────────────
#
# The research agent runs multi-round tool loops; each round is a paid call on
# the cloud path. A local Ollama model makes those rounds free. Ollama speaks
# the OpenAI-compatible API, so the only differences from the cloud path are:
#   - no `cache_control` block (that is an Anthropic-via-OpenRouter feature;
#     Ollama wants a plain-string system message)
#   - no `extra_body={"transforms": ...}` (an OpenRouter-only routing hint)
#   - cost is always 0
# `LLMBackend` carries exactly those switches so caller code stays uniform.


@dataclass
class LLMBackend:
    client: OpenAI
    model: str
    sends_cache_control: bool
    extra_body: dict = field(default_factory=dict)
    label: str = ""
    is_local: bool = False


def build_ollama_client() -> OpenAI:
    """OpenAI-compatible client pointed at the local Ollama server."""
    return OpenAI(
        base_url=settings.OLLAMA_BASE_URL,
        api_key="ollama",  # Ollama ignores the key, but the SDK requires one.
        timeout=600.0,
        max_retries=1,
    )


def build_research_backend(local: bool = False, model: str | None = None) -> LLMBackend:
    """Build the backend the research agent should use this turn.

    `local=True` targets Ollama with `settings.MODEL_AGENT_LOCAL`; otherwise the
    paid OpenRouter path with `settings.MODEL_AGENT`. Settings are read live so
    profile.json edits take effect without a reload.
    """
    if local:
        chosen = model or settings.MODEL_AGENT_LOCAL
        return LLMBackend(
            client=build_ollama_client(),
            model=chosen,
            sends_cache_control=False,
            extra_body={},
            label=f"Ollama:{chosen}",
            is_local=True,
        )
    chosen = model or settings.MODEL_AGENT
    return LLMBackend(
        client=build_client(),
        model=chosen,
        sends_cache_control=True,
        extra_body={"transforms": ["middle-out"]},
        label=f"OpenRouter:{chosen}",
        is_local=False,
    )


def _ollama_tags_url() -> str:
    base = settings.OLLAMA_BASE_URL.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base.rstrip("/") + "/api/tags"


def list_local_models() -> list[str]:
    """Names of models installed in the local Ollama server (sorted), or []."""
    try:
        resp = httpx.get(_ollama_tags_url(), timeout=4.0)
        resp.raise_for_status()
        return sorted(m.get("name", "") for m in resp.json().get("models", []) if m.get("name"))
    except Exception:
        return []


# A model that runs but can't emit STRUCTURED tool_calls is useless for the
# research loop (the loop reads choice.message.tool_calls; if empty it never
# searches). Whether that works depends on model × Ollama version, not model
# recency — e.g. mistral-nemo's tool calls parse on Ollama 0.30.x but leak into
# the text as `[TOOL_CALLS][…]` on 0.12.x. So the preflight probes it. The probe
# also warms the model; the result is cached per model to keep later turns cheap.
_TOOLCALL_CAPABLE: dict[str, bool] = {}

_PROBE_TOOL = [{
    "type": "function",
    "function": {
        "name": "search_db",
        "description": "Search the database for a term.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
}]


def check_local_backend(model: str) -> tuple[bool, str]:
    """Preflight the local Ollama backend; return (ok, user_facing_message_de).

    Catches, with actionable German guidance: server not running, model not
    pulled, a broken runner, and — crucially — a model that runs but does not
    emit structured tool_calls on this Ollama version (which would make the
    research loop silently produce empty searches). The tool-probe doubles as a
    warm-up and is cached per model so only the first turn pays for it.
    """
    # 1. Server reachable + which models are present?
    try:
        resp = httpx.get(_ollama_tags_url(), timeout=4.0)
        resp.raise_for_status()
        present = [m.get("name", "") for m in resp.json().get("models", [])]
    except Exception:
        return False, (
            f"Lokales Modell gewählt, aber der Ollama-Server ist unter "
            f"`{settings.OLLAMA_BASE_URL}` nicht erreichbar.\n\n"
            "Starte ihn mit `ollama serve` (oder die Ollama-App), oder schalte "
            "im Agent-Panel zurück auf die Cloud."
        )
    # 2. Model pulled? (accept exact name or matching base before the ':' tag)
    base_names = {n.split(":")[0] for n in present}
    if model not in present and model.split(":")[0] not in base_names:
        avail = ", ".join(sorted(present)) or "(keine)"
        return False, (
            f"Lokales Modell `{model}` ist in Ollama nicht vorhanden.\n\n"
            f"Hol es mit `ollama pull {model}`. Verfügbar: {avail}."
        )
    if _TOOLCALL_CAPABLE.get(model):
        return True, ""
    # 3. Runs AND emits structured tool_calls? (one probe covers both)
    try:
        probe = build_ollama_client().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You can call tools. When asked to search, you MUST call search_db."},
                {"role": "user", "content": "Search the database for the term 'test'."},
            ],
            tools=_PROBE_TOOL,
            max_tokens=384,
        )
    except Exception as exc:
        return False, (
            f"Ollama erreicht, aber `{model}` lässt sich nicht ausführen:\n\n"
            f"`{str(exc)[:400]}`\n\n"
            "Häufige Ursache: die Ollama-Installation hat kein lauffähiges "
            "Inferenz-Backend (z. B. fehlendes `llama-server`). Neu installieren "
            "(offizieller Installer von ollama.com) behebt das meist."
        )
    if not getattr(probe.choices[0].message, "tool_calls", None):
        return False, (
            f"`{model}` läuft, emittiert auf dieser Ollama-Version aber **keine "
            f"strukturierten tool_calls** — die braucht der Recherche-Loop "
            "(sonst werden nie Suchen ausgeführt). Wähle ein anderes Modell "
            "(geprüft ok: qwen3:8b, llama3.3) oder aktualisiere Ollama."
        )
    _TOOLCALL_CAPABLE[model] = True
    return True, ""
