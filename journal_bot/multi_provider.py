"""Multi-Provider LLM-Client für Kostenexperimente.

Portiert aus dem SARAH-Projekt (`src/lib/server/ai/client.ts`). Erlaubt es,
denselben MOJO-Code mit unterschiedlichen Providern + Modellen zu fahren —
Anthropic via OpenRouter (Opus/Sonnet/Haiku), Mistral nativ (mistral-large)
und OpenRouter für sonstige offene Modelle (xiaomi/mimo-v2.5-pro etc.).

Cache-Strategie pro Provider (Stand 2026-05):
  - Anthropic via OpenRouter: explizite `cache_control: { type: 'ephemeral' }`
    auf System-Block. Mindest-Token-Schwellen (siehe `_anthropic_cache_min_tokens`).
  - Mistral nativ: KEIN cache_control senden — der Provider macht implizites
    Prefix-Caching server-side. Sendet man cache_control, gibt es 422.
  - Andere OpenRouter-Modelle (xiaomi/mimo, deepseek): cache_control wird
    durchgereicht oder still ignoriert; kein Schaden.

Keys (Reihenfolge der Suche):
  1. Env-Variable `MOJO_{PROVIDER}_KEY` (z. B. `MOJO_OPENROUTER_KEY`)
  2. Standard-Pfad `~/.config/mojo/{provider}_key`

Provider ohne hinterlegten Key werfen `RuntimeError` mit dem erwarteten Pfad
in der Message — relevant nur für Q-Check-Scripts, die das Modul direkt
nutzen. Produktiv-Calls gehen über `journal_bot.llm_client`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI


# ────────────────────────────────────────────────────────────────────
# Provider-Definitionen
# ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ProviderDef:
    label: str
    base_url: str
    key_files: tuple[Path, ...]   # Suchreihenfolge; erste vorhandene gewinnt
    dsgvo: bool
    region: str


_HOME = Path.home()

PROVIDERS: dict[str, ProviderDef] = {
    "openrouter": ProviderDef(
        label="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        key_files=(_HOME / ".config" / "mojo" / "openrouter_key",),
        dsgvo=False,
        region="US",
    ),
    "mistral": ProviderDef(
        label="Mistral AI",
        base_url="https://api.mistral.ai/v1",
        key_files=(_HOME / ".config" / "mojo" / "mistral_key",),
        dsgvo=True,
        region="EU",
    ),
    "mammouth": ProviderDef(
        label="Mammouth (EU-vermittelt)",
        base_url="https://api.mammouth.ai/v1",
        key_files=(_HOME / ".config" / "mojo" / "mammouth_key",),
        dsgvo=True,
        region="EU",
    ),
}


def _read_key(provider: str) -> str:
    env = os.environ.get(f"MOJO_{provider.upper()}_KEY")
    if env:
        return env.strip()
    if provider not in PROVIDERS:
        raise ValueError(f"Unbekannter Provider: {provider}")
    for p in PROVIDERS[provider].key_files:
        if p.exists():
            key = p.read_text(encoding="utf-8").strip()
            if key:
                return key
    raise RuntimeError(
        f"Kein API-Key für {provider!r} gefunden. Erwartet in: "
        + ", ".join(str(p) for p in PROVIDERS[provider].key_files)
    )


def build_client(provider: str) -> OpenAI:
    """Liefert einen OpenAI-kompatiblen Client für den gewählten Provider."""
    if provider not in PROVIDERS:
        raise ValueError(f"Unbekannter Provider: {provider}")
    pdef = PROVIDERS[provider]
    headers = {}
    if provider == "openrouter":
        headers = {"HTTP-Referer": "https://localhost/mojo", "X-Title": "mojo-cost-test"}
    return OpenAI(
        base_url=pdef.base_url,
        api_key=_read_key(provider),
        default_headers=headers,
    )


# ────────────────────────────────────────────────────────────────────
# Modell-Routen + Preise (USD pro Mio Tokens, Stand 2026-05)
# ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Route:
    provider: str
    model: str
    label: str
    input_usd_per_mtok: float
    output_usd_per_mtok: float
    region: str
    dsgvo: bool
    supports_anthropic_cache: bool  # darf cache_control: ephemeral senden
    has_implicit_cache: bool        # Provider cached automatisch ab Call 2-3


ROUTES: dict[str, Route] = {
    # Baselines
    "opus": Route(
        provider="openrouter",
        model="anthropic/claude-opus-4.7",
        label="Claude Opus 4.7 (OpenRouter)",
        # Korrigiert 2026-05-16: Opus 4.6 kostet $5/$25/Mtok (input/output),
        # Cache-Read $0.5/Mtok. Vorher hier irrtümlich Opus-3-Preise ($15/$75)
        # eingetragen — Rückrechnung aus realem OpenRouter-cost-Feld bestätigt $5/$25.
        input_usd_per_mtok=5.0,
        output_usd_per_mtok=25.0,
        region="US",
        dsgvo=False,
        supports_anthropic_cache=True,
        has_implicit_cache=False,
    ),
    "sonnet": Route(
        provider="openrouter",
        model="anthropic/claude-sonnet-4.6",
        label="Claude Sonnet 4.6 (OpenRouter)",
        input_usd_per_mtok=3.0,
        output_usd_per_mtok=15.0,
        region="US",
        dsgvo=False,
        supports_anthropic_cache=True,
        has_implicit_cache=False,
    ),
    "haiku": Route(
        provider="openrouter",
        model="anthropic/claude-haiku-4.5",
        label="Claude Haiku 4.5 (OpenRouter)",
        input_usd_per_mtok=1.0,
        output_usd_per_mtok=5.0,
        region="US",
        dsgvo=False,
        supports_anthropic_cache=True,
        has_implicit_cache=False,
    ),
    # SARAH-Stack
    "mistral": Route(
        provider="mistral",
        model="mistral-large-latest",
        label="Mistral Large (nativ EU)",
        input_usd_per_mtok=0.5,
        output_usd_per_mtok=1.5,
        region="EU",
        dsgvo=True,
        supports_anthropic_cache=False,
        has_implicit_cache=True,
    ),
    "mimo": Route(
        provider="openrouter",
        model="xiaomi/mimo-v2.5-pro",
        label="MiMo 2.5 Pro (OpenRouter, Xiaomi)",
        input_usd_per_mtok=1.0,
        output_usd_per_mtok=3.0,
        region="US",
        dsgvo=False,
        # OpenRouter listet für mimo-v2.5-pro: input_cache_read $0.20/Mtok (5×
        # günstiger als prompt), cache_write gratis. Cache wird per
        # `cache_control: ephemeral` aktiviert — ohne diesen Header sendet
        # OpenRouter den Block uncached durch, kein implicit-caching.
        supports_anthropic_cache=True,
        has_implicit_cache=False,
    ),
    # Existierender MOJO-Stack als Vergleich
    "deepseek": Route(
        provider="openrouter",
        model="deepseek/deepseek-v3.2",
        label="DeepSeek v3.2 (OpenRouter)",
        input_usd_per_mtok=0.26,
        output_usd_per_mtok=1.10,
        region="US",
        dsgvo=False,
        supports_anthropic_cache=False,
        has_implicit_cache=True,
    ),
}


# ────────────────────────────────────────────────────────────────────
# Cache-aware System-Prompt-Builder
# ────────────────────────────────────────────────────────────────────


def build_system_param(system_prompt: str, route: Route) -> list[dict] | str:
    """Konstruiert den `content`-Wert für die System-Message provider-gerecht.

    - Anthropic via OpenRouter: structured block + cache_control
    - Mistral nativ: PLAIN STRING (sonst 422; implicit caching via stable prefix)
    - Sonstige OpenRouter-Modelle (mimo, deepseek): plain string reicht;
      cache_control schaden würde nicht, bringt aber nichts.
    """
    if route.supports_anthropic_cache:
        return [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    # Plain-String-Pfad — sicher für Mistral und alle anderen OpenAI-kompat.
    return system_prompt


def make_messages(
    system_prompt: str,
    user_content: str,
    route: Route,
    *,
    second_user_for_sticky_routing: str | None = None,
) -> list[dict]:
    """Baut die messages-Liste für einen Single-Shot-Call.

    Wenn `second_user_for_sticky_routing` gesetzt ist (typisch
    SCREENING_BATCH_PREAMBLE), wird die batch-spezifische Payload in eine
    zweite User-Message gepackt — relevant für DeepSeek-Style implicit cache
    via stabilem OpenRouter-Routing.
    """
    sys_content = build_system_param(system_prompt, route)
    if isinstance(sys_content, list):
        system_msg = {"role": "system", "content": sys_content}
    else:
        system_msg = {"role": "system", "content": sys_content}

    msgs: list[dict] = [system_msg]
    if second_user_for_sticky_routing is not None:
        msgs.append({"role": "user", "content": second_user_for_sticky_routing})
        msgs.append({"role": "user", "content": user_content})
    else:
        msgs.append({"role": "user", "content": user_content})
    return msgs


# ────────────────────────────────────────────────────────────────────
# Cost extraction
# ────────────────────────────────────────────────────────────────────


@dataclass
class CallStats:
    cost_usd: float
    tokens_in: int
    tokens_out: int
    cached_read: int
    cache_write: int
    fallback_cost: bool  # True wenn cost aus Preisliste geschätzt (Provider lieferte 0)


def extract_stats(usage, route: Route) -> CallStats:
    """Holt aus dem usage-Objekt die Stats raus und schätzt cost wenn nötig."""
    if usage is None:
        return CallStats(0.0, 0, 0, 0, 0, False)
    dump = usage.model_dump() if hasattr(usage, "model_dump") else {}
    cost = float(dump.get("cost") or 0.0)
    tokens_in = int(usage.prompt_tokens or 0)
    tokens_out = int(usage.completion_tokens or 0)
    pd = dump.get("prompt_tokens_details") or {}
    cached = int(pd.get("cached_tokens") or 0)
    cache_write = int(pd.get("cache_write_tokens") or 0)

    fallback = False
    if cost == 0.0:
        # Mistral liefert keinen `cost`-Wert im usage; auch andere
        # OpenAI-kompat-Provider können fehlen. Aus Tabelle schätzen.
        fallback = True
        cost = (
            tokens_in / 1_000_000 * route.input_usd_per_mtok
            + tokens_out / 1_000_000 * route.output_usd_per_mtok
        )
    return CallStats(cost, tokens_in, tokens_out, cached, cache_write, fallback)
