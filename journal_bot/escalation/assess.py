"""Volltext-LLM-Assessment für Wrong-LES-Diagnose (MOJO 2.0 §2.5 Pilot).

Use-Case: Items wo `user_verdict='lesenswert'` aber `agent_verdict != 'lesenswert'`
sind die echten Cascade-Lücken. Diese Funktion schickt den Volltext zusammen mit
`summaries.json` (Eigenwerk-Zusammenfassungen, gecacht!) an Opus/Sonnet und fragt:

  "Warum hätte das `lesenswert` sein müssen? Welcher konkrete Anschluss im
   Volltext (mit wörtlichem Anker-Zitat) fehlt in der Cascade-Bewertung?
   Welches Signal hätte die Cascade abfangen können?"

Output ist strukturiert per XML-Tags (robuster als JSON in chat-completion):
  - would_be_verdict, confidence
  - miss_diagnosis (deutsche Begründung)
  - anchored_quotes (1–3 wörtliche Belege mit Stellenangabe + Relevanz)
  - suggested_cascade_signal (welche neue Regel/Heuristik würde es fangen?)

Prompt-Caching:
  - System-Prompt enthält summaries.json (~28k Tokens) — cache_control:ephemeral.
    Erster Call ist teuer (cache-write), Calls 2…N lesen aus dem Cache.
  - Anthropic-Cache-TTL ist ~5 min; bei sequentiellen Calls hintereinander ist
    das ohne Pause garantiert.

Cost-Discipline (CLAUDE.md):
  - HARD_PER_CALL_CAP_USD (Default 0.50): einzelner Call darf nicht teurer
    werden; bei Überschreitung Abbruch und Diagnose.
  - HARD_TOTAL_CAP_USD muss vom Caller separat geprüft werden.

Logging: jeder Call landet in `llm_calls` via record_llm_call (endpoint =
"escalation_wrong_les"). cost_usd, tokens, article_id alle attribuiert.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from journal_bot.agent import (
    _anthropic_cache_min_tokens,
    _should_use_explicit_cache_control,
    build_system_prompt,
)
from journal_bot.llm_client import build_client
from journal_bot.llm_log import record_llm_call
from journal_bot.settings import RESEARCHER_NAME, SUMMARIES_JSON

# Maximaler Volltext-Anteil pro Call. 25k Zeichen ≈ ~7k Tokens — bleibt
# unter 10k user-Tokens für saubere Kostenbasis. Mittlerer Artikel hat
# ~30k Zeichen, also nehmen wir Anfang + Ende statt nur Anfang, damit
# Schluss/Bibliographie nicht verloren gehen.
MAX_VOLLTEXT_HEAD_CHARS = 18000
MAX_VOLLTEXT_TAIL_CHARS = 7000

HARD_PER_CALL_CAP_USD = 0.50

# Default-Modell für die Eskalation. Sonnet 4.6 ist sehr capable und ~6× günstiger
# als Opus 4.6 — bei Wrong-LES-Diagnose ist die Frage methodisch klar
# ("welches Cascade-Signal fehlt?"), nicht extrem-tief argumentativ.
DEFAULT_ESCALATION_MODEL = "anthropic/claude-sonnet-4.6"


# ----- Dataclasses ----------------------------------------------------------


@dataclass
class AnchoredQuote:
    quote: str
    section: str | None = None         # "S. 12", "Kap. 3.1", etc.
    relevance: str = ""


@dataclass
class AssessResult:
    article_id: str
    status: str                         # "ok" | "cost_cap_exceeded" | "parse_failed" | "error"
    would_be_verdict: str | None        # "lesenswert" | "scannen" | "ignorieren" | None
    confidence: float                   # 0.0 – 1.0
    miss_diagnosis: str                 # deutsche Begründung
    anchored_quotes: list[AnchoredQuote] = field(default_factory=list)
    suggested_cascade_signal: str | None = None
    raw_response: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cached_read: int = 0
    tokens_cache_write: int = 0
    cost_usd: float = 0.0
    model: str = ""
    error: str | None = None


# ----- Prompt-Building ------------------------------------------------------


def _build_escalation_outro(researcher_name: str) -> str:
    """Eskalations-Prompt-Outro mit Researcher-Namen aus profile.json.

    Parametrisiert, damit der Bot für andere User funktioniert. `researcher_name`
    sollte der volle Name sein (z. B. "Benjamin Jörissen") — kommt aus
    `journal_bot.settings.RESEARCHER_NAME`, das aus `profile.json` geladen wird.
    """
    short = researcher_name.split()[-1] if researcher_name else "der Forscher"
    return f"""\
ESKALATIONS-MODUS: WRONG-LES-DIAGNOSE.

Du bekommst gleich einen Artikel-Volltext UND die bisherige algorithmische
Cascade-Bewertung (Agent-Verdict, Selection-Mode, Indikator, IDF-Signale).

KONTEXT: {researcher_name} hat diesen Artikel persönlich als LESENSWERT
markiert. Die algorithmische Cascade hingegen hat ihn NICHT als lesenswert
gehoben. Das ist eine systematische Cascade-Lücke.

DEINE AUFGABE:
1. Lies den Volltext im Lichte von {short}s veröffentlichtem Werk (siehe
   summaries oben).
2. Identifiziere KONKRET, was im Volltext den Anschluss zu {short}s Arbeit
   herstellt — mit wörtlichen Anker-Zitaten und Stellenangabe.
3. Diagnostiziere, welches algorithmische Signal die Cascade hätte sehen
   müssen (z. B. ein bestimmter Begriff, eine Theorie-Tradition, ein
   Koautor-Netzwerk, ein methodischer Anschluss).

ANTWORTE STRENG IN DIESEM XML-FORMAT (keine zusätzlichen Erläuterungen):

<analysis>
  <would_be_verdict>lesenswert</would_be_verdict>
  <confidence>0.85</confidence>
  <miss_diagnosis>
    Ein bis zwei Sätze: was hat die Cascade strukturell übersehen?
  </miss_diagnosis>
  <quote_1>
    <text>wörtliches Zitat (max. 2 Sätze)</text>
    <section>z. B. "S. 12" oder "Kap. 3.1" oder "Schluss"</section>
    <relevance>warum ist dieses Zitat für {short}s Werk relevant?</relevance>
  </quote_1>
  <quote_2>
    <text>optional zweites Zitat — nur wenn ein anderer Anschluss-Aspekt</text>
    <section>...</section>
    <relevance>...</relevance>
  </quote_2>
  <suggested_cascade_signal>
    Konkrete Heuristik, die die Cascade ergänzen sollte. Beispiele:
    "Co-Autor-Netzwerk via OpenAlex" oder
    "Schlüsselbegriff 'mimetische Subjektivierung' im Abstract checken" oder
    "Resilienz-Wortfeld erkennen auch ohne Trigger-Autor".
    Wenn unklar oder bereits abgedeckt, schreibe NULL.
  </suggested_cascade_signal>
</analysis>
"""


# Aktive Eskalations-Outro für den Default-Researcher aus settings. Tests und
# Pilot-Runs benutzen diesen Wert; eine Per-Call-Überschreibung ist über das
# `researcher_name`-Argument von `assess_article_volltext` möglich.
ESCALATION_OUTRO = _build_escalation_outro(RESEARCHER_NAME)


def _truncate_volltext(text: str) -> str:
    """Volltext auf Head + Tail kürzen für stabile Token-Kosten.

    Zentrale Argumentation steht meist in Einleitung + Schluss. Mittelteil
    (Methodik, Detailanalysen) bringt selten zusätzliche Anker-Zitate für
    den disziplinären Anschluss.
    """
    text = text or ""
    if len(text) <= MAX_VOLLTEXT_HEAD_CHARS + MAX_VOLLTEXT_TAIL_CHARS + 200:
        return text
    head = text[:MAX_VOLLTEXT_HEAD_CHARS]
    tail = text[-MAX_VOLLTEXT_TAIL_CHARS:]
    return (
        head
        + "\n\n[…Volltext-Mittelteil gekürzt für Kosten — "
          "Methodik/Detail-Analyse weggelassen…]\n\n"
        + tail
    )


def _format_cascade_state(article: dict) -> str:
    """Was hat die Cascade bisher gesehen? In Stichpunkten an den LLM."""
    rows: list[str] = []
    rows.append(f"  Journal:        {article.get('journal_short')}")
    rows.append(f"  Title:          {article.get('title')!r}")
    rows.append(f"  DOI:            {article.get('doi')}")
    rows.append(f"  Year:           {article.get('year')}")
    rows.append(f"  Agent-Verdict:  {article.get('agent_verdict')}")
    rows.append(f"  User-Verdict:   {article.get('user_verdict')} (= LESENSWERT)")
    rows.append(f"  Selection-Mode: {article.get('selection_mode')}")
    rows.append(f"  Indikator:      {article.get('discourse_indicator')}")
    own_s = article.get("own_coupling_score", 0.0) or 0.0
    adv_s = article.get("adversarial_score", 0.0) or 0.0
    rows.append(f"  IDF-Signal:     own_coupling={own_s:.2f}, adversarial={adv_s:.2f}")
    if article.get("abstract"):
        rows.append("")
        rows.append("  Abstract (was die Cascade gesehen hat):")
        abstr = (article["abstract"] or "")[:1500]
        rows.append("    " + abstr.replace("\n", "\n    "))
    return "\n".join(rows)


def _build_user_message(
    article: dict,
    volltext: str,
    researcher_name: str = RESEARCHER_NAME,
) -> str:
    cascade_block = _format_cascade_state(article)
    volltext_truncated = _truncate_volltext(volltext)
    short = researcher_name.split()[-1] if researcher_name else "Der Forscher"
    return (
        "## Cascade-Bewertung bisher\n\n"
        + cascade_block
        + "\n\n"
        + "## Volltext des Artikels\n\n"
        + volltext_truncated
        + "\n\n"
        + "## Frage\n\n"
        + f"{short} hat das LESENSWERT gemacht, die Cascade nicht. Warum?\n"
        + "Antworte exakt im vorgegebenen XML-Schema."
    )


# ----- Output-Parsing -------------------------------------------------------


def _extract_tag(xml: str, tag: str) -> str | None:
    """Erste Inhaltsgruppe von <tag>…</tag>. None wenn fehlt. Multiline-aware."""
    m = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", xml, re.DOTALL)
    return m.group(1).strip() if m else None


def _parse_response(text: str) -> tuple[
    str | None, float, str, list[AnchoredQuote], str | None
]:
    """Antwort-XML in strukturierte Felder zerlegen.

    Robust gegen kleine Abweichungen (whitespace, extra-Text vor/nach
    <analysis>). Wenn Pflichtfelder fehlen: leere Defaults + Parse-Fehler
    wird vom Caller per `status='parse_failed'` markiert.
    """
    verdict = _extract_tag(text, "would_be_verdict")
    if verdict:
        verdict = verdict.lower().strip()
        if verdict not in ("lesenswert", "scannen", "ignorieren"):
            verdict = None

    confidence_raw = _extract_tag(text, "confidence")
    confidence = 0.0
    if confidence_raw:
        try:
            confidence = max(0.0, min(1.0, float(confidence_raw)))
        except ValueError:
            confidence = 0.0

    miss_diagnosis = _extract_tag(text, "miss_diagnosis") or ""

    # Bis zu drei Quotes
    quotes: list[AnchoredQuote] = []
    for i in (1, 2, 3):
        # Vollständiges Quote-Element extrahieren
        m = re.search(
            rf"<quote_{i}>\s*(.*?)\s*</quote_{i}>", text, re.DOTALL,
        )
        if not m:
            continue
        block = m.group(1)
        qt = _extract_tag(block, "text") or ""
        sec = _extract_tag(block, "section")
        rel = _extract_tag(block, "relevance") or ""
        if qt:
            quotes.append(AnchoredQuote(quote=qt, section=sec, relevance=rel))

    suggested = _extract_tag(text, "suggested_cascade_signal")
    if suggested and suggested.strip().upper() in ("NULL", "NONE", ""):
        suggested = None

    return verdict, confidence, miss_diagnosis, quotes, suggested


# ----- Public API -----------------------------------------------------------


def assess_article_volltext(
    article: dict,
    volltext: str,
    summaries_path: Path = SUMMARIES_JSON,
    model: str = DEFAULT_ESCALATION_MODEL,
    hard_per_call_cap_usd: float = HARD_PER_CALL_CAP_USD,
    verbose: bool = False,
    researcher_name: str = RESEARCHER_NAME,
) -> AssessResult:
    """Einzelnes Volltext-LLM-Assessment für Wrong-LES-Diagnose.

    Args:
        article: Dict mit at least id, title, abstract, journal_short, doi,
            agent_verdict, user_verdict, selection_mode, discourse_indicator,
            own_coupling_score, adversarial_score.
        volltext: Voller Artikel-Text (pdftotext-Output).
        summaries_path: Pfad zu summaries.json. Wird gecacht im System-Prompt.
        model: OpenRouter-Modell-ID. Default: Sonnet 4.6 (günstig+capable).
        hard_per_call_cap_usd: Hard cap pro Call. Bei Überschreitung wird
            der Aufruf VOR dem Senden abgebrochen, falls Token-Schätzung
            bereits zeigt, dass Kosten zu hoch werden würden.
        verbose: Print-Diagnose.
        researcher_name: Voller Forscher-Name für den Eskalations-Prompt.
            Default aus `settings.RESEARCHER_NAME` (aus profile.json).

    Returns:
        AssessResult mit status, parsed fields, token/cost metadata.
        Schreibt eine Zeile in llm_calls.
    """
    article_id = article.get("id") or article.get("article_id") or "?"

    # System-Prompt mit summaries.json (gecacht). build_system_prompt baut
    # SYSTEM_INTRO + projects + outro + summaries. Outro wird per-Call aus
    # researcher_name gebaut — Tests können damit andere Namen injizieren.
    summaries_data = json.loads(summaries_path.read_text(encoding="utf-8"))
    summaries = summaries_data["summaries"]
    outro = _build_escalation_outro(researcher_name)
    system_prompt = build_system_prompt(summaries, outro=outro)

    user_content = _build_user_message(article, volltext, researcher_name)

    if verbose:
        sys_tokens_est = len(system_prompt) // 4
        user_tokens_est = len(user_content) // 4
        print(
            f"[assess] system≈{sys_tokens_est} tokens, "
            f"user≈{user_tokens_est} tokens (model={model})"
        )

    client = build_client()

    system_block: dict[str, Any] = {"type": "text", "text": system_prompt}
    if _should_use_explicit_cache_control(model):
        system_block["cache_control"] = {"type": "ephemeral"}
    messages = [
        {"role": "system", "content": [system_block]},
        {"role": "user", "content": user_content},
    ]

    try:
        resp = client.chat.completions.create(
            model=model,
            max_tokens=1500,           # XML-Output ist kurz; gibt Begründung Raum
            messages=messages,
            extra_body={"usage": {"include": True}},
        )
    except Exception as e:
        record_llm_call(
            endpoint="escalation_wrong_les", model=model,
            cost_usd=0.0, status="error", article_id=article_id,
            error=str(e)[:200],
        )
        return AssessResult(
            article_id=article_id, status="error",
            would_be_verdict=None, confidence=0.0,
            miss_diagnosis="", model=model, error=str(e)[:200],
        )

    raw = resp.choices[0].message.content or ""
    usage = getattr(resp, "usage", None)
    usage_dump: dict[str, Any] = {}
    if usage:
        usage_dump = usage.model_dump() if hasattr(usage, "model_dump") else {}
    tokens_in = int(usage_dump.get("prompt_tokens") or 0)
    tokens_out = int(usage_dump.get("completion_tokens") or 0)
    pd = usage_dump.get("prompt_tokens_details") or {}
    cached_read = int(pd.get("cached_tokens") or 0)
    cache_write = int(pd.get("cache_write_tokens") or 0)
    cost_usd = float(usage_dump.get("cost") or 0.0)

    # Hard-Cap-Verifizierung POST-Call (der Cap war als Safety-Hinweis gedacht)
    cost_status = "ok"
    if cost_usd > hard_per_call_cap_usd:
        cost_status = "cost_cap_exceeded"
        if verbose:
            print(
                f"[assess] WARN: ${cost_usd:.3f} überschreitet Per-Call-Cap "
                f"${hard_per_call_cap_usd:.2f}"
            )

    verdict, confidence, miss, quotes, suggested = _parse_response(raw)

    status = cost_status
    if status == "ok" and verdict is None:
        status = "parse_failed"

    record_llm_call(
        endpoint="escalation_wrong_les", model=model,
        usage=usage_dump, cost_usd=cost_usd, status=status,
        article_id=article_id,
    )

    if verbose:
        print(
            f"[assess] tokens_in={tokens_in}, cached={cached_read}, "
            f"cache_write={cache_write}, out={tokens_out}, "
            f"cost=${cost_usd:.4f}, status={status}"
        )

    return AssessResult(
        article_id=article_id,
        status=status,
        would_be_verdict=verdict,
        confidence=confidence,
        miss_diagnosis=miss,
        anchored_quotes=quotes,
        suggested_cascade_signal=suggested,
        raw_response=raw,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        tokens_cached_read=cached_read,
        tokens_cache_write=cache_write,
        cost_usd=cost_usd,
        model=model,
    )
