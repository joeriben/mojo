"""Agent-Loop mit Tool-Use über OpenRouter.

Der Agent:
  - bekommt im System-Prompt alle Summaries als Werkstand des/der Forscher*in
  - bekommt im User-Turn den neuen Beitrag + Enrichment (OpenAlex abstract, refs)
  - darf via read_publication() konkrete Stellen aus den Volltexten lesen
  - schließt mit submit_digest_entry() ab, liefert strukturierten Digest-Eintrag
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


class CacheNotHitError(RuntimeError):
    """Raised when prompt caching fails and costs would be excessive."""
    pass


# Minimum expected cache-read ratio after the first call (which always writes).
# If the second+ call reads < 50% from cache, something is wrong.
_MIN_CACHE_READ_RATIO = 0.5
_CACHE_CRITICAL_BATCH_COST_USD = 0.05

# Hard cost caps for batch_screen — apply regardless of cache reporting.
# These are last-resort circuit breakers: they trigger BEFORE the cache-ratio
# heuristic can fail silently for providers that don't report cached_tokens
# reliably (notably DeepSeek via OpenRouter).
_MAX_SINGLE_BATCH_COST_USD = 0.30   # one batch of 25 articles
_MAX_TOTAL_BATCH_COST_CHEAP_USD = 0.50    # DeepSeek/Haiku — total per batch_screen call
_MAX_TOTAL_BATCH_COST_EXPENSIVE_USD = 5.00  # Opus/Sonnet — total per batch_screen call


def _rough_token_count(text: str) -> int:
    """Cheap local estimate used only for cache-threshold guards."""
    return max(1, len(text) // 4)


def _model_input_cost_per_million(model: str) -> float | None:
    """Known OpenRouter input prices for cache-risk estimates.

    OpenRouter reports actual costs in normal responses; this fallback is only
    for warning text and deciding whether a no-cache screening batch is costly
    enough to abort.
    """
    m = model.lower()
    if "deepseek/deepseek-v3.2" in m:
        return 0.26
    if "claude-opus" in m:
        return 15.0
    if "claude-sonnet" in m:
        return 3.0
    if "claude-haiku" in m:
        return 1.0
    return None


def _max_total_batch_screen_cost_usd(model: str) -> float:
    """Hard total budget per batch_screen() invocation, by model class.

    Returns the cheap-tier limit by default so unknown models inherit the
    stricter cap. Override only by changing the constants above.
    """
    price = _model_input_cost_per_million(model)
    if price is not None and price >= 2.0:
        return _MAX_TOTAL_BATCH_COST_EXPENSIVE_USD
    return _MAX_TOTAL_BATCH_COST_CHEAP_USD


def _anthropic_cache_min_tokens(model: str) -> int | None:
    """Return Anthropic/OpenRouter's minimum cacheable prompt length.

    Current OpenRouter/Anthropic rules distinguish newer Claude releases:
    Opus 4.6/4.5 and Haiku 4.5 need 4096 cacheable tokens; Sonnet 4.6
    and Haiku 3.5 need 2048; older Claude 4/3.7 models need 1024.
    """
    m = model.lower()
    if not m.startswith("anthropic/") or "claude" not in m:
        return None
    if any(name in m for name in (
        "claude-opus-4.7",
        "claude-opus-4.6",
        "claude-opus-4.5",
        "claude-haiku-4.5",
    )):
        return 4096
    if "claude-sonnet-4.6" in m or "claude-haiku-3.5" in m:
        return 2048
    return 1024


def _should_use_explicit_cache_control(model: str) -> bool:
    """OpenRouter needs explicit breakpoints for Anthropic Claude only here."""
    return _anthropic_cache_min_tokens(model) is not None


def _extra_body_for_model(model: str) -> dict[str, Any]:
    """Per-model OpenRouter extras (reasoning effort, usage flags).

    Gemini 3.5 Flash is a reasoning model; without an explicit effort it
    defaults to a higher level which (per qcheck N=50, 2026-05-23) produces
    less informative verdict_begruendung than low-effort. See memory
    `feedback-reasoning-low-vs-high`.
    """
    m = model.lower()
    extras: dict[str, Any] = {"usage": {"include": True}}
    if "gemini" in m and "flash" in m:
        extras["reasoning"] = {"effort": "low"}
    return extras


def _estimate_uncached_batch_cost(
    *,
    model: str,
    prompt_tokens: int,
    reported_cost: float,
) -> float:
    if reported_cost > 0:
        return reported_cost
    input_price = _model_input_cost_per_million(model)
    if input_price is None:
        return 0.0
    return prompt_tokens / 1_000_000 * input_price

from journal_bot.citation_tracker import find_citations, format_for_agent
from journal_bot.enrichment import enrich
from journal_bot.llm_client import build_client
from journal_bot.llm_log import record_llm_call
from journal_bot.settings import (
    CORPUS_JSON, MODEL_AGENT, MODEL_SUMMARIZE, PROJECT_ROOT, SINCE_YEAR,
    SUMMARIES_JSON, RESEARCHER_AREAS, RESEARCHER_INSTITUTION,
    RESEARCHER_NAME, RESEARCHER_TRIAGE_TOPICS,
)

PROJECTS_JSON = PROJECT_ROOT / "projects.json"


# ------------------------------------------------------------------ Prompt --


SYSTEM_INTRO = f"""You are a research assistant for {RESEARCHER_NAME}
({RESEARCHER_INSTITUTION}).
Research areas: {RESEARCHER_AREAS}.

Your task: You receive a newly published journal article and must write a digest entry
that helps {RESEARCHER_NAME} decide whether to read it, and why or why not — NOT
generically ("relevant because education"), but specifically in relation to their own
published arguments.

Below is the publication record from {SINCE_YEAR} onwards, formatted as factual summaries.
These summaries are a SEARCH INDEX, NOT interpretation — they tell you WHAT the texts
are about, not what is ARGUED. To cite a specific position, you MUST read the full text
via `read_publication(pub_id)`. NEVER cite from the summaries.
"""


SYSTEM_OUTRO = f"""

=== TWO TYPES OF RELEVANCE ===
There are two distinct reasons an article matters:

1. **bezuege** (substantive connections): The article directly extends, contradicts,
   imports from, or is imported into the researcher's published arguments. This requires
   reading the full text to verify. Shared reference frames alone (e.g. both citing
   Haraway or Barad) do NOT constitute a bezug.

2. **bemerkenswert** (second-order observations): Something worth knowing even if the
   article itself need not be read — e.g. someone applies computational methods to a
   theory-heavy question, imports a concept across disciplinary boundaries, or makes
   an unusual methodological move. These go in `bemerkenswert`, NOT in `bezuege`.

"ignorieren" = neither substantive connections nor noteworthy observations.

=== VERDICT CALIBRATION ===
The purpose of this digest is twofold: (1) maintain awareness of relevant discourses,
and (2) identify articles with Anregungspotenzial — stimulation potential for the
researcher's thinking, projects, and teaching. This is NOT about "resource transfer"
or direct applicability. An article is relevant when it offers perspectives,
counter-positions, conceptual moves, or phenomenal cases that could productively
irritate, extend, or contextualize the researcher's work.

**ignorieren** — genuinely outside the observation field:
  The article has no connection to the researcher's disciplines, projects, or discourse
  spaces. Typical: clinical pharmacology, sports biomechanics, accounting standards.
  Also ignorieren: articles that nominally share a keyword but operate in an entirely
  different disciplinary logic without Anregungspotenzial.

**scannen** — within the observation field, worth knowing about:
  The article touches the researcher's discourse spaces or project themes. It is
  useful for Diskursübersicht or as a phenomenal indicator, but does not clearly
  stimulate the researcher's own theoretical or project work.

**lesenswert** — offers Anregungspotenzial for thinking or projects:
  The article could productively stimulate the researcher's work. This includes:
  - A new conceptual move, counter-position, or reframing relevant to published work
  - A perspective, case, or method productive for an ACTIVE RESEARCH PROJECT
    (the connection may be structural/conceptual, not lexical — see project descriptions)
  - An article that operates within the same problematic from a different tradition
    (productive friction, not just overlap)
  - Work that the researcher should be aware of to position their own arguments
  Typical: an article on collective mourning in the Anthropocene — different
  theoretical tradition (Freud, not Barad), but the phenomenal case and the
  educational framing are directly productive for Cultural Resilience/Rootedness.

**pflichtlektuere** — central to current work, must read immediately.

=== PROCEDURE ===
1. Read the new article carefully (title, abstract, references).
2. **Immediate decision**: If clearly outside the observation field — call
   `submit_digest_entry` with verdict="ignorieren" immediately. Minimal output.
3. If potentially relevant, check THREE dimensions:
   (a) **Published work**: Are there substantive connections to the publication record?
       Pick 2–4 candidates, load with `read_publication(pub_id, search_term)`.
   (b) **Active projects**: Does the article offer Anregungspotenzial for a research
       project? A DIFFERENT theoretical tradition working on the SAME problematic is
       a positive signal, not a negative one — it means productive friction.
       An article on "planetary Bildung" from Freire/Vygotsky is relevant for Cultural
       Resilience precisely BECAUSE it approaches the problem differently.
   (c) **Discourse awareness**: Would {RESEARCHER_NAME} want to know about this to
       maintain Diskursübersicht? → fill `bemerkenswert`.
4. Decide verdict based on the strongest dimension. Project relevance alone
   can justify "lesenswert" even without direct connections to published work.

=== RULES ===
- Cite the researcher's work in `bezuege` ONLY after reading the full text. No
  hallucinated citations, no reasoning from summaries.
- If connections are thin, say so clearly ("weak topical echo, no real connection").
  Honest thin connections are preferred over inflated strong ones.
- `bemerkenswert` is for "interesting to know that someone does X with Y". No full
  text reading needed — the new article and context suffice.
- Take time for 2–5 read_publication calls when warranted. No speed runs.

=== PUBLICATION RECORD ({SINCE_YEAR}+) ==="""


def _build_projects_block() -> str:
    """Format active research projects as a prompt section."""
    if not PROJECTS_JSON.exists():
        return ""
    try:
        data = json.loads(PROJECTS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return ""

    active = [p for p in data.get("projects", []) if p.get("status") == "active"]
    if not active:
        return ""

    lines = [
        "\n=== ACTIVE RESEARCH PROJECTS ===",
        "These projects shift what counts as relevant. An article that would otherwise be",
        '"scannen" may become "lesenswert" if it connects to an active project.',
        "The connection is often conceptual, not lexical — the project's terminology may",
        "not appear in the article. Use the relevance shifts below as bridging heuristics.\n",
    ]
    for p in active:
        lines.append(f"[{p.get('key', '?')}] {p.get('name', '?')}")
        if p.get("period"):
            lines.append(f"  Period: {p['period']}")
        if p.get("description"):
            lines.append(f"  {p['description']}")
        for shift in p.get("relevance_shifts", []):
            lines.append(f"  → {shift}")
        if p.get("connected_publications"):
            lines.append(f"  Publications: {', '.join(p['connected_publications'])}")
        lines.append("")

    return "\n".join(lines)


def build_system_prompt(summaries: dict[str, dict], outro: str | None = None) -> str:
    projects_block = _build_projects_block()
    lines = [SYSTEM_INTRO, projects_block, outro or SYSTEM_OUTRO, ""]
    # Sortiert nach Jahr absteigend — aktuelles zuerst
    sorted_pubs = sorted(
        summaries.items(),
        key=lambda kv: (kv[1].get("year") or 0),
        reverse=True,
    )
    for pub_id, s in sorted_pubs:
        year = s.get("year") or "?"
        title = s.get("title", "").strip()
        authors = ", ".join((s.get("authors") or [])[:3])
        lines.append(f"\n--- pub_id: {pub_id} ({year}) ---")
        lines.append(f"{title}")
        if authors:
            lines.append(f"[{authors}]")
        if s.get("summary_de"):
            lines.append(s["summary_de"])
        if s.get("key_terms"):
            lines.append("Begriffe: " + "; ".join(s["key_terms"][:12]))
        if s.get("named_thinkers"):
            lines.append("Denker*innen: " + "; ".join(s["named_thinkers"][:12]))
        if s.get("methods"):
            lines.append("Methoden: " + "; ".join(s["methods"][:6]))
    return "\n".join(lines)


# ------------------------------------------------------------------- Tools --


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_publication",
            "description": (
                "Load an excerpt from one of the researcher's publications. "
                "Use this to read specific passages and arguments before citing "
                "them. A search_term returns text around the first match; "
                "without search_term you get the beginning (~4k words)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pub_id": {
                        "type": "string",
                        "description": "The pub_id from the publication list in the system prompt.",
                    },
                    "search_term": {
                        "type": "string",
                        "description": (
                            "Optional. Term, name, or short phrase. Returns the "
                            "text excerpt around the first match. If not found, "
                            "returns the beginning of the text."
                        ),
                    },
                },
                "required": ["pub_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_digest_entry",
            "description": (
                "Finalize the run. Call this when you have read enough to "
                "produce a structured digest entry."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kernthese": {
                        "type": "string",
                        "description": (
                            "2–3 sentences, descriptive: What does the article "
                            "address, what is its central claim. No judgment."
                        ),
                    },
                    "bezuege": {
                        "type": "array",
                        "description": (
                            "Concrete connections to publications you have READ. "
                            "Empty if no substantive connections found. "
                            "FORMAT: must be an actual JSON array of objects — "
                            "never a JSON-encoded string containing the array. "
                            "Inside string values, escape every double quote "
                            "as \\\" or use typographic quotes („…“ / “…”); a "
                            "bare \" inside a value breaks the payload."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "pub_id": {"type": "string"},
                                "pub_kurz": {
                                    "type": "string",
                                    "description": "Short form: Author + Year + Short Title",
                                },
                                "bezug": {
                                    "type": "string",
                                    "description": (
                                        "2–4 sentences: How does the new article relate "
                                        "to this publication? Based on the text you read "
                                        "via read_publication."
                                    ),
                                },
                                "relation": {
                                    "type": "string",
                                    "enum": [
                                        "erweitert",
                                        "widerspricht",
                                        "parallelisiert",
                                        "importiert",
                                        "tangential",
                                    ],
                                },
                            },
                            "required": ["pub_id", "pub_kurz", "bezug", "relation"],
                        },
                    },
                    "theoretisch_methodisch": {
                        "type": "string",
                        "description": (
                            "1–3 sentences: methodological and theoretical "
                            "assessment of the new article. Descriptive, no judgment."
                        ),
                    },
                    "bemerkenswert": {
                        "type": "array",
                        "description": (
                            "Second-order observations the researcher should know "
                            "about, even if the article itself is not worth reading. "
                            "Each 1–2 sentences, concise, concrete. Empty if nothing "
                            "noteworthy."
                        ),
                        "items": {"type": "string"},
                    },
                    "verdict": {
                        "type": "string",
                        "enum": [
                            "pflichtlektuere",
                            "lesenswert",
                            "scannen",
                            "ignorieren",
                        ],
                    },
                    "verdict_begruendung": {
                        "type": "string",
                        "description": "1–2 sentences: why this verdict.",
                    },
                    "candidate_reads": {
                        "type": "array",
                        "description": (
                            "Assessment phase only: publications whose full text "
                            "should be read to verify bezuege. Leave empty when "
                            "no verification needed or full text already read."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "pub_id": {
                                    "type": "string",
                                    "description": "pub_id from the publication list.",
                                },
                                "search_term": {
                                    "type": "string",
                                    "description": (
                                        "Concrete term/phrase to search for "
                                        "in the full text."
                                    ),
                                },
                                "hypothesis": {
                                    "type": "string",
                                    "description": (
                                        "1 sentence: What connection do you hypothesize?"
                                    ),
                                },
                            },
                            "required": ["pub_id", "search_term", "hypothesis"],
                        },
                    },
                },
                "required": [
                    "kernthese",
                    "bezuege",
                    "theoretisch_methodisch",
                    "bemerkenswert",
                    "verdict",
                    "verdict_begruendung",
                ],
            },
        },
    },
]


# ----------------------------------------------------------------- Triage --

_triage_topics = "\n".join(f"- {t}" for t in RESEARCHER_TRIAGE_TOPICS)
TRIAGE_PROMPT = f"""You are a pre-filter for a research digest.

{RESEARCHER_NAME} ({RESEARCHER_INSTITUTION}) works on:
{_triage_topics}

You receive title, abstract, and journal of a new article.
Decide: Could this article be relevant?

Respond ONLY with a JSON object:
{{"triage": "relevant", "grund": "..."}} — if there COULD be topical or methodological overlap (even distant)
{{"triage": "ignorieren", "grund": "..."}} — if the article is obviously unrelated

When in doubt: "relevant". Better to let through an irrelevant article than to miss a relevant one."""


def triage_article(
    article: dict,
    model: str = MODEL_SUMMARIZE,
    verbose: bool = True,
) -> dict:
    """Leichter Vorfilter: entscheidet ob ein Artikel den Haupt-Agenten braucht.

    Returns dict with keys: triage ("relevant"|"ignorieren"), grund, cost_usd.
    """
    client = build_client()
    user_msg = (
        f"Journal: {article.get('journal', '')}\n"
        f"Titel: {article.get('title', '')}\n"
        f"Abstract: {(article.get('abstract') or '(kein Abstract)')[:2000]}"
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": TRIAGE_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=200,
        temperature=0.0,
    )
    raw = resp.choices[0].message.content.strip()
    cost = 0.0
    usage_dump: dict[str, Any] = {}
    if resp.usage:
        usage_dump = (
            resp.usage.model_dump() if hasattr(resp.usage, "model_dump") else {}
        )
        # Prefer reported cost; fall back to Haiku-style estimate.
        cost = float(usage_dump.get("cost") or 0.0)
        if cost == 0.0:
            cost = (resp.usage.prompt_tokens / 1_000_000) * 0.80 + (
                resp.usage.completion_tokens / 1_000_000
            ) * 4.0
    record_llm_call(
        endpoint="triage", model=model, usage=usage_dump,
        cost_usd=cost, status="ok",
    )

    # Parse JSON from response
    result = None
    # Try 1: direct parse
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Try 2: extract between first { and last }
    if result is None:
        first = raw.find("{")
        last = raw.rfind("}")
        if first >= 0 and last > first:
            try:
                result = json.loads(raw[first:last + 1])
            except json.JSONDecodeError:
                pass
    if result is None or not isinstance(result, dict):
        result = {"triage": "relevant", "grund": f"(Triage-Parse-Fehler: {raw[:100]})"}

    result["cost_usd"] = cost
    if verbose:
        print(f"[triage] {result['triage']} — {result.get('grund', '')[:80]}  (${cost:.4f})")
    return result


# ----------------------------------------------------- Title-Only Screening --


def build_catchwords(summaries_path: Path = SUMMARIES_JSON) -> set[str]:
    """Extract catchwords from summaries.json key_terms + named_thinkers + manual additions."""
    import re as _re
    data = json.loads(summaries_path.read_text(encoding="utf-8"))
    raw = set()
    for s in data["summaries"].values():
        for t in s.get("key_terms") or []:
            t = _re.sub(r"<[^>]+>", "", t).strip()
            if t and len(t) > 2:
                raw.add(t.lower())
        for t in s.get("named_thinkers") or []:
            t = _re.sub(r"<[^>]+>", "", t).strip()
            if t and len(t) > 2:
                raw.add(t.lower())

    # English equivalents for core concepts
    raw.update({
        "aesthetic education", "cultural education", "media education",
        "postdigital", "post-digital", "postdigitality",
        "new materialism", "new materialisms", "agential realism",
        "cultural resilience", "digital culture",
        "algorithmic", "datafication", "computability",
        "subjectivation", "subjectification",
        "actor-network", "entanglement", "intra-action",
        "posthuman", "posthumanism", "more-than-human",
        "arts-based", "arts education", "art education",
        "digital heritage", "intangible cultural heritage",
        "generative ai", "generative ki",
        "partition of the sensible", "distribution of the sensible",
        "dissensus", "sympoiesis", "invisibilisation", "invisibility",
    })

    # Remove overly generic single words
    generic = {"bildung", "erziehung", "kultur", "gesellschaft", "theorie",
               "praxis", "forschung", "analyse", "methode", "perspektive",
               "diskurs", "education", "theory", "research", "culture",
               "practice", "analysis", "norm", "equity", "agency", "visibility"}
    return {t for t in raw if not (len(t.split()) == 1 and t in generic)}


def title_matches_catchwords(title: str, catchwords: set[str]) -> list[str]:
    """Return list of catchwords found in title (case-insensitive)."""
    t = (title or "").lower()
    return [cw for cw in catchwords if cw in t]


# ---------------------------------------------------------- Batch Screening --

MODEL_SCREEN = "deepseek/deepseek-v3.2"

SCREENING_SUFFIX = f"""

=== SCREENING MODE ===
You now receive a LIST of articles (title, journal, abstract excerpt).
For each article: decide whether it COULD be relevant and therefore deserves
full analysis.

Respond with EXACTLY one line per article in this format:
[ID] weitergeben|ignorieren — reason in ≤15 words

"weitergeben" when:
- Topical overlap with the researcher's themes/positions
- Methodologically/phenomenally noteworthy for the observation field
- Cites {RESEARCHER_NAME} or cites works from the bibliography

"ignorieren" when:
- Obviously unrelated to the research
- Purely empirical/applied without theoretical connection
- Topically in a field without overlap (e.g. pure psychometrics, nursing didactics)

When in doubt: weitergeben. Better to pass through than to miss.
No explanation, no introduction, just the lines."""

SCREENING_BATCH_PREAMBLE = (
    "You will receive one batch of article candidates in the next user message. "
    "Apply the screening rules from the system prompt and respond only with the "
    "required line format."
)


def _build_screening_messages(
    system_prompt: str,
    batch_payload: str,
    model: str,
) -> list[dict[str, Any]]:
    """Build screening messages with a stable first user turn for cache affinity.

    OpenRouter's sticky routing keys on the first system message and the first
    non-system message. If the first user message changes for every batch, later
    requests may be routed to a different provider endpoint and DeepSeek's
    implicit prompt cache is lost. The batch-specific payload therefore goes
    into a second user message, while the first one stays constant.
    """
    system_block: dict[str, Any] = {
        "type": "text",
        "text": system_prompt,
    }
    if _should_use_explicit_cache_control(model):
        system_block["cache_control"] = {"type": "ephemeral"}

    return [
        {
            "role": "system",
            "content": [system_block],
        },
        {"role": "user", "content": SCREENING_BATCH_PREAMBLE},
        {"role": "user", "content": batch_payload},
    ]


def batch_screen(
    articles: list[dict],
    summaries_path: Path = SUMMARIES_JSON,
    model: str = MODEL_SCREEN,
    batch_size: int = 25,
    verbose: bool = True,
) -> dict[str, dict]:
    """Batch screening: cheap model with cached system prompt, one verdict per article.

    articles: list of dicts with keys: id, title, journal, abstract (or openalex_abstract).
    Returns: dict of article_id -> {"verdict": "weitergeben"|"ignorieren", "grund": str}.
    """
    summaries_data = json.loads(summaries_path.read_text(encoding="utf-8"))
    system_prompt = build_system_prompt(summaries_data["summaries"]) + SCREENING_SUFFIX
    cacheable_tokens = _rough_token_count(system_prompt)
    min_cache_tokens = _anthropic_cache_min_tokens(model)
    if min_cache_tokens is not None and cacheable_tokens < min_cache_tokens:
        raise CacheNotHitError(
            f"[screen] Cache-Block zu klein für {model}: "
            f"~{cacheable_tokens} Tokens, Minimum {min_cache_tokens}. "
            "Anthropic ignoriert cache_control unterhalb dieser Schwelle."
        )

    client = build_client()
    all_results: dict[str, dict] = {}
    total_cost = 0.0
    total_budget = _max_total_batch_screen_cost_usd(model)

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        batch_num = i // batch_size + 1

        # Format batch
        lines = []
        for a in batch:
            abstract = (a.get("openalex_abstract") or a.get("abstract") or "")[:500]
            lines.append(
                f"[{a['id'][:8]}] {a.get('journal', '')} | {a.get('title', '')}\n"
                f"  Abstract: {abstract}\n"
            )
        user_msg = "\n".join(lines)

        if verbose:
            print(f"[screen] Batch {batch_num}: {len(batch)} Artikel, "
                  f"~{len(user_msg) // 4} User-Tokens")

        resp = client.chat.completions.create(
            model=model,
            messages=_build_screening_messages(system_prompt, user_msg, model),
            max_tokens=2000,
            temperature=0.0,
        )

        raw = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        cost = 0.0
        usage_dump: dict[str, Any] = {}
        if usage:
            usage_dump = usage.model_dump() if hasattr(usage, "model_dump") else {}
            cost = usage_dump.get("cost") or 0.0
        total_cost += cost

        # Hard cost caps — fire BEFORE the cache-ratio heuristic so we cannot
        # be tricked by providers that report cached_tokens unreliably (e.g.
        # DeepSeek via OpenRouter). These are circuit breakers, not warnings.
        if cost > _MAX_SINGLE_BATCH_COST_USD:
            msg = (
                f"[screen] HARD-CAP: Batch {batch_num} kostet ${cost:.3f} "
                f"(Einzelbatch-Limit ${_MAX_SINGLE_BATCH_COST_USD:.2f}). "
                f"Modell: {model}. Sehr wahrscheinlich Cache-Miss oder "
                f"teures Provider-Routing. ABBRUCH."
            )
            print(msg, file=sys.stderr)
            record_llm_call(
                endpoint="batch_screen", model=model, usage=usage_dump,
                cost_usd=cost, status="aborted_single_cap",
            )
            raise CacheNotHitError(msg)
        if total_cost > total_budget:
            msg = (
                f"[screen] HARD-CAP: Gesamtbudget ${total_budget:.2f} "
                f"überschritten (${total_cost:.3f} nach {batch_num} Batches). "
                f"Modell: {model}. ABBRUCH."
            )
            print(msg, file=sys.stderr)
            record_llm_call(
                endpoint="batch_screen", model=model, usage=usage_dump,
                cost_usd=cost, status="aborted_total_cap",
            )
            raise CacheNotHitError(msg)

        # Track this call (must come after cap-check so aborted calls are
        # logged with the correct status above).
        record_llm_call(
            endpoint="batch_screen", model=model, usage=usage_dump,
            cost_usd=cost, status="ok", batch_num=batch_num,
        )

        if usage and batch_num >= 2:
            # Cache-ratio diagnostic (informational + abort for Anthropic).
            # Kept in addition to the hard caps because it gives a clearer
            # error message when cached_tokens is reported reliably.
            pd = usage_dump.get("prompt_tokens_details") or {}
            cached = pd.get("cached_tokens") or 0
            total_prompt = usage.prompt_tokens or 1
            ratio = cached / total_prompt
            expected_uncached = _estimate_uncached_batch_cost(
                model=model,
                prompt_tokens=total_prompt,
                reported_cost=cost,
            )
            cache_required = min_cache_tokens is not None
            costly_without_cache = expected_uncached >= _CACHE_CRITICAL_BATCH_COST_USD
            if ratio < _MIN_CACHE_READ_RATIO and (cache_required or costly_without_cache):
                min_note = (
                    f" Cache-Block: ~{cacheable_tokens} Tokens "
                    f"(Minimum {min_cache_tokens})."
                    if min_cache_tokens is not None else ""
                )
                msg = (
                    f"[screen] CACHE-WARNUNG: Batch {batch_num} hat nur "
                    f"{ratio:.0%} Cache-Hits ({cached}/{total_prompt} Tokens). "
                    f"Modell: {model}.{min_note} "
                    f"Erwartete Kosten pro Batch ohne Cache: "
                    f"~${expected_uncached:.2f}. "
                    f"ABBRUCH — bitte Cache-Konfiguration prüfen."
                )
                print(msg, file=sys.stderr)
                raise CacheNotHitError(msg)

        # Parse response
        valid_ids = {a["id"]: a["id"][:8] for a in batch}
        short_to_full = {v: k for k, v in valid_ids.items()}

        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line or not line.startswith("["):
                continue
            bracket_end = line.find("]")
            if bracket_end < 0:
                continue
            short_id = line[1:bracket_end].strip()
            rest = line[bracket_end + 1:].strip()

            verdict = "weitergeben"  # default: pass through
            if rest.startswith("ignorieren") or rest.startswith("ignor"):
                verdict = "ignorieren"

            full_id = short_to_full.get(short_id)
            if full_id:
                grund = rest.split("—", 1)[1].strip() if "—" in rest else rest[:80]
                all_results[full_id] = {"verdict": verdict, "grund": grund}

        parsed = sum(1 for a in batch if a["id"] in all_results)
        if verbose:
            print(f"[screen] → {parsed}/{len(batch)} geparst, ${cost:.4f}")

    # Articles not in results default to "weitergeben"
    for a in articles:
        if a["id"] not in all_results:
            all_results[a["id"]] = {
                "verdict": "weitergeben",
                "grund": "(nicht im Screening-Output, default: weitergeben)",
            }

    if verbose:
        passed = sum(1 for r in all_results.values() if r["verdict"] == "weitergeben")
        filtered = sum(1 for r in all_results.values() if r["verdict"] == "ignorieren")
        print(f"[screen] Gesamt: {passed} weitergeben, {filtered} ignorieren, "
              f"${total_cost:.4f}")

    return all_results


# ------------------------------------------------------------------ Runner --


def _load_corpus_index(corpus_path: Path) -> dict[str, dict]:
    data = json.loads(corpus_path.read_text(encoding="utf-8"))
    return {p["pub_id"]: p for p in data["publications"]}


def _load_authored_all(corpus_path: Path) -> list[dict]:
    data = json.loads(corpus_path.read_text(encoding="utf-8"))
    return data.get("authored_all", [])


def handle_read_publication(
    corpus_index: dict[str, dict],
    pub_id: str,
    search_term: str = "",
) -> str:
    if pub_id not in corpus_index:
        return f"[FEHLER] pub_id {pub_id!r} nicht im Corpus gefunden."
    pub = corpus_index[pub_id]
    fulltext = pub.get("fulltext", "")
    if not fulltext:
        return f"[FEHLER] Kein Volltext für {pub_id} ({pub.get('title', '')[:80]})."

    title = pub.get("title", "")
    year = pub.get("year", "")
    header = f"[Publikation {pub_id} — {title} ({year})]\n\n"

    if search_term:
        lower_text = fulltext.lower()
        lower_term = search_term.lower()
        idx = lower_text.find(lower_term)
        if idx >= 0:
            start = max(0, idx - 1800)
            end = min(len(fulltext), idx + 4200)
            snippet = fulltext[start:end]
            prefix = "… " if start > 0 else ""
            suffix = " …" if end < len(fulltext) else ""
            return (
                f"{header}[Ausschnitt um '{search_term}' — "
                f"Zeichen {start}–{end} von {len(fulltext)}]\n\n"
                f"{prefix}{snippet}{suffix}"
            )
        # Term nicht gefunden: wir sagen das ehrlich
        header += f"[Hinweis: '{search_term}' nicht im Text gefunden, gebe Anfang zurück]\n\n"

    # Default: Anfang
    return header + fulltext[:16000] + (" …" if len(fulltext) > 16000 else "")


TOOLS_SUBMIT_ONLY = [t for t in TOOLS if t["function"]["name"] == "submit_digest_entry"]


# ------------------------------------------------------- Tool-Args-Repair --
# GLM-5.2-Defekt (A/B-Test 2026-07-10, docs/glm52_vs_gemini_agent_ab_2026-07-10.md):
# In 3/7 Läufen mit befüllten Bezügen kam `bezuege` als JSON-STRING statt als
# Array, und der String war wegen unescapeter deutscher Anführungszeichen
# („…" — öffnend U+201E, schließend als nacktes ASCII 0x22) nicht parsebar.
# Die Kaskade hier entpackt solche Payloads SICHTBAR (Marker + Log, nie still);
# was auch dann nicht parsebar ist, bleibt als Roh-String in `bezuege_unparsed`
# erhalten statt verworfen zu werden.


def _escape_stray_quotes_in_json_strings(raw: str) -> str:
    """Escape ASCII double quotes that are content INSIDE JSON string values.

    Two stacked heuristics, beide nur zum Entpacken (Inhalte werden nicht
    umgeschrieben, das ASCII-Zeichen bleibt erhalten, nur escaped):

    1. German-quote pairing: nach einem noch offenen „ (U+201E) innerhalb
       desselben JSON-Strings ist das nächste ASCII-`"` das schließende
       deutsche Anführungszeichen → Content, escapen. (Deckt den Fall
       `„Police",` ab, wo Regel 2 fälschlich ein String-Ende sähe.)
       Ein korrektes typografisches “ (U+201C) schließt das „ ebenfalls.
    2. Follower-Regel: ein `"` terminiert den String nur legitim, wenn das
       nächste Nicht-Whitespace-Zeichen ein JSON-Strukturzeichen
       (`,`, `}`, `]`, `:`) oder das Eingabe-Ende ist; sonst Content.
    """
    out: list[str] = []
    in_string = False
    open_german = 0  # unclosed „ within the current JSON string
    i = 0
    n = len(raw)
    while i < n:
        c = raw[i]
        if not in_string:
            if c == '"':
                in_string = True
                open_german = 0
            out.append(c)
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            out.append(c)
            out.append(raw[i + 1])
            i += 2
            continue
        if c == "„":  # „
            open_german += 1
            out.append(c)
            i += 1
            continue
        if c == "“" and open_german > 0:  # “ schließt „ typografisch
            open_german -= 1
            out.append(c)
            i += 1
            continue
        if c == '"':
            if open_german > 0:
                out.append('\\"')
                open_german -= 1
                i += 1
                continue
            j = i + 1
            while j < n and raw[j] in " \t\r\n":
                j += 1
            if j >= n or raw[j] in ",}]:":
                in_string = False
                out.append(c)
            else:
                out.append('\\"')
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _coerce_bezuege(entry: dict) -> dict | None:
    """Normalize a string-typed `bezuege` field in-place (visible repair).

    Returns a repair-info dict when something was done, else None.
    Repair paths:
      - valid list of dicts        → untouched, returns None
      - dict (single bezug object) → wrapped into a list
      - str                        → json.loads; on failure quote-escape +
                                     json.loads; on failure moved to
                                     `bezuege_unparsed` (raw, preserved)
      - other shapes               → moved to `bezuege_unparsed` (repr)
    Every repair sets `bezuege_repaired: true` + `bezuege_repair_method`;
    unparseable payloads set `bezuege` to [] and keep the raw string.
    """
    bez = entry.get("bezuege")
    if bez is None:
        return None
    if isinstance(bez, list) and all(isinstance(b, dict) for b in bez):
        return None

    def _mark(method: str) -> dict:
        entry["bezuege_repaired"] = True
        entry["bezuege_repair_method"] = method
        return {"field": "bezuege", "method": method}

    if isinstance(bez, dict):
        entry["bezuege"] = [bez]
        return _mark("wrapped_single_object")

    if isinstance(bez, str):
        for method, candidate in (
            ("json_loads", bez),
            ("quote_escape_json_loads", _escape_stray_quotes_in_json_strings(bez)),
        ):
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, list) and all(isinstance(b, dict) for b in parsed):
                entry["bezuege"] = parsed
                return _mark(method)
            if isinstance(parsed, dict):
                entry["bezuege"] = [parsed]
                return _mark(method + "+wrapped_single_object")
        entry["bezuege"] = []
        entry["bezuege_unparsed"] = bez
        return _mark("unparsed_kept_raw")

    # Liste mit Nicht-dict-Items oder sonstige Typen: nichts wegwerfen.
    entry["bezuege"] = [b for b in bez if isinstance(b, dict)] if isinstance(bez, list) else []
    entry["bezuege_unparsed"] = json.dumps(bez, ensure_ascii=False, default=str)
    return _mark("unparsed_kept_raw")


# ------------------------------------------------- Assessment-Phase Prompt --


ASSESSMENT_OUTRO = f"""

=== TWO TYPES OF RELEVANCE ===
1. **bezuege** (substantive connections): Direct extensions, contradictions, or imports
   between the article and the researcher's published arguments. Shared reference frames
   alone (both citing Haraway) do NOT constitute a bezug.
2. **bemerkenswert** (second-order observations): Worth knowing even without reading —
   unusual methods, cross-disciplinary imports, phenomenal indicators.

"ignorieren" = neither substantive connections nor noteworthy observations.

=== VERDICT CALIBRATION ===
The purpose of this digest is to maintain Diskursübersicht and identify articles with
Anregungspotenzial — stimulation potential for the researcher's thinking and projects.
This is NOT about "resource transfer" or direct applicability.

- **ignorieren**: Genuinely outside the observation field. No connection to the
  researcher's disciplines, projects, or discourse spaces. Typical: clinical
  pharmacology, sports biomechanics, accounting standards.
- **scannen**: Within the observation field, useful for Diskursübersicht. The article
  touches the researcher's themes but offers no specific stimulation for current
  thinking or project work.
- **lesenswert**: Offers Anregungspotenzial — the article could productively
  stimulate the researcher's work. This includes:
  (a) Substantive connections to the published work (extends, contradicts, imports)
  (b) Productive relevance for an ACTIVE RESEARCH PROJECT — even from a different
      theoretical tradition. An article on "planetary Bildung" from Freire/Vygotsky
      is relevant for Cultural Resilience precisely BECAUSE the different approach
      offers productive friction. Different tradition + same problematic = lesenswert.
  (c) A conceptual move, case, or method that the researcher should know about to
      position their own arguments.
- **pflichtlektuere**: Central to current work, must read immediately.

=== PROCEDURE (ASSESSMENT PHASE) ===
You have NO access to full texts. You work only with the publication index above.

1. Read the new article carefully (title, abstract, references).
2. **Immediate decision**: If clearly outside the observation field → call
   `submit_digest_entry` with verdict="ignorieren" immediately.
3. Check THREE dimensions:
   (a) **Published work**: Are there substantive connections to the publication record?
   (b) **Active projects**: Does the article offer Anregungspotenzial for a research
       project? Check the project descriptions and relevance_shifts above.
       A DIFFERENT theoretical tradition working on the SAME problematic is a
       POSITIVE signal — it means productive friction, not irrelevance.
   (c) **Discourse awareness**: Is this worth noting for Diskursübersicht?
4. Generate candidate_reads when you see a specific connection to a publication that
   would benefit from full-text verification. Maximum 2 candidate_reads.
5. Fill bemerkenswert independently — second-order observations do not require
   full-text verification.
6. Decide verdict based on the STRONGEST dimension. Project relevance alone can
   justify "lesenswert" even without direct connections to published work.

=== RULES ===
- Write NO bezuege. The field stays empty. Bezuege require full-text reading.
- bemerkenswert may and should be filled when applicable.

=== VERDICT-BEGRÜNDUNG CONSISTENCY RULE ===
Before finalizing the verdict, re-read your own verdict_begruendung. If it
contains any of the following phrasings (or semantically equivalent ones, in
German or English):
  - "keine Anknüpfungspunkte" / "no points of connection"
  - "kein spezifischer Anschluss" / "no specific connection"
  - "kein konkreter Bezug" / "no concrete relation"
  - "außerhalb [...] Forschungsfeld[es]" / "outside [...] field of research"
  - "nur tangential" / "only tangential"
  - "berührt nicht" / "does not touch"
  - "keine substanzielle Verbindung" / "no substantive connection"
... then verdict MUST be "ignorieren". The verdicts "scannen" and "lesenswert"
require a positively named, concrete connection. A justification must not read
both ways — either there is a connection (then name it), or there is none (then
ignorieren).

=== PUBLICATION RECORD ({SINCE_YEAR}+) ==="""


def run_agent(
    new_article: dict,
    corpus_path: Path = CORPUS_JSON,
    summaries_path: Path = SUMMARIES_JSON,
    model: str = MODEL_AGENT,
    max_iterations: int = 8,
    verbose: bool = True,
    allow_read: bool = True,
    system_outro: str | None = None,
    extra_user_content: str = "",
    log_endpoint: str = "run_agent",
    article_id: str | None = None,
) -> dict:
    """new_article: dict mit title, authors, abstract, doi, url, journal.

    allow_read=False disables read_publication tool (assessment from
    summaries only, no fulltext verification).
    system_outro: replaces the default SYSTEM_OUTRO in the system prompt.
    extra_user_content: appended to the user message (e.g. verification context).
    log_endpoint: endpoint label written to llm_calls (e.g. "assess", "verify").
    article_id: optional articles.id for cost-attribution per article.
    """
    corpus_index = _load_corpus_index(corpus_path)
    authored_all = _load_authored_all(corpus_path)
    summaries_data = json.loads(summaries_path.read_text(encoding="utf-8"))
    summaries = summaries_data["summaries"]

    system_prompt = build_system_prompt(summaries, outro=system_outro)
    if verbose:
        phase = "assessment" if system_outro is ASSESSMENT_OUTRO else "full"
        print(f"[agent] System-Prompt ({phase}): ~{len(system_prompt)//4} Tokens "
              f"({len(summaries)} Publikationen im Index)")

    doi = (new_article.get("doi") or "").strip()

    # Use pre-computed enrichment from store if available, else fetch
    enrichment_data = new_article.get("enrichment") or {}
    if not enrichment_data and doi:
        enrichment_data = enrich(doi)

    # Citation-Tracker: researcher citations in references
    citation_hits = find_citations(
        enrichment_data.get("references_crossref") or [],
        authored_all,
    )
    if verbose:
        if citation_hits:
            high = sum(1 for h in citation_hits if h.confidence == "high")
            print(f"[agent] Zitationstreffer: {len(citation_hits)} "
                  f"(davon {high} mit hoher Confidence)")
        else:
            print(f"[agent] Keine Forscher-Zitate in den Refs")

    citations_block = format_for_agent(citation_hits)
    user_content = _format_new_article(new_article, enrichment_data) + citations_block
    if extra_user_content:
        user_content += extra_user_content
    if verbose:
        print(f"[agent] User-Content: ~{len(user_content)//4} Tokens")

    client = build_client()

    # System-Prompt als cache-fähigen Content-Block über OpenRouter.
    # cache_control nur für Anthropic-Modelle setzen — andere Provider
    # (Gemini, DeepSeek, etc.) verwenden implicit caching und tolerieren
    # zusätzliche Felder nicht durchgängig.
    system_text_block: dict[str, Any] = {
        "type": "text",
        "text": system_prompt,
    }
    if _should_use_explicit_cache_control(model):
        system_text_block["cache_control"] = {"type": "ephemeral"}
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": [system_text_block],
        },
        {"role": "user", "content": user_content},
    ]
    extra_body = _extra_body_for_model(model)

    final_entry: dict | None = None
    tool_call_log: list[dict] = []
    format_repairs: list[dict] = []
    total_in = 0
    total_out = 0
    total_cached_read = 0
    total_cache_write = 0
    total_cost_usd = 0.0
    _cache_verified = False  # set True after first successful cache read

    for it in range(1, max_iterations + 1):
        if verbose:
            print(f"\n[agent] --- Iteration {it} ---")

        resp = client.chat.completions.create(
            model=model,
            # Obergrenze, nur die real erzeugten Tokens werden berechnet. 4000
            # schnitt glm-5.2 auf verbose Artikeln mitten im submit-Tool-Call ab
            # (finish_reason=length → gar kein Entry; Re-Test 2026-07-11 maß 4374
            # und 4883 Output-Tokens auf zwei der drei betroffenen Artikel).
            # Gemini bleibt deutlich darunter, für es folgenlos.
            max_tokens=8000,
            messages=messages,
            tools=TOOLS if allow_read else TOOLS_SUBMIT_ONLY,
            extra_body=extra_body,
        )
        usage = getattr(resp, "usage", None)
        iter_cost = 0.0
        usage_dump: dict[str, Any] = {}
        if usage:
            total_in += usage.prompt_tokens or 0
            total_out += usage.completion_tokens or 0
            # OpenRouter-spezifische Extras im usage-Dump
            usage_dump = usage.model_dump() if hasattr(usage, "model_dump") else {}
            pd = usage_dump.get("prompt_tokens_details") or {}
            cached = pd.get("cached_tokens") or 0
            total_cached_read += cached
            total_cache_write += pd.get("cache_write_tokens") or 0
            iter_cost = float(usage_dump.get("cost") or 0.0)
            total_cost_usd += iter_cost
            if verbose and (cached or pd.get("cache_write_tokens")):
                print(
                    f"[agent] cache: read={cached}, "
                    f"write={pd.get('cache_write_tokens', 0)}"
                )
            # Mark cache as verified once we see a successful read
            if cached > 0:
                _cache_verified = True

        # Per-iteration logging — needed to detect cost spikes inside long
        # agent loops (e.g. tool-call ping-pong or runaway iterations).
        record_llm_call(
            endpoint=log_endpoint,
            model=model,
            usage=usage_dump,
            cost_usd=iter_cost,
            status="ok",
            article_id=article_id,
            iteration=it,
            allow_read=allow_read,
        )

        msg = resp.choices[0].message
        finish = resp.choices[0].finish_reason
        if verbose:
            if msg.content:
                print(f"[agent] assistant: {msg.content[:500]}")
            print(f"[agent] finish={finish}")

        tool_calls = getattr(msg, "tool_calls", None) or []

        if not tool_calls:
            if verbose:
                print("[agent] Keine Tool-Calls — Lauf endet.")
            break

        # Assistant-Nachricht mit Tool-Calls ins Transcript
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        # Tool-Calls abarbeiten
        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except Exception as e:
                result = f"[FEHLER beim Args-Parse] {e}"
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                continue

            if verbose:
                args_preview = json.dumps(args, ensure_ascii=False)[:200]
                print(f"[agent] → {name}({args_preview})")

            if name == "read_publication":
                result = handle_read_publication(
                    corpus_index,
                    pub_id=args.get("pub_id", ""),
                    search_term=args.get("search_term", ""),
                )
                tool_call_log.append(
                    {"tool": name, "pub_id": args.get("pub_id"),
                     "search_term": args.get("search_term", ""), "chars": len(result)}
                )
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": result}
                )
            elif name == "submit_digest_entry":
                # Guard against double-encoded JSON (string instead of dict)
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        pass
                final_entry = args if isinstance(args, dict) else None
                if final_entry is not None:
                    # Per-Feld-Repair (GLM-5.2: bezuege als String) — sichtbar,
                    # nie still: Marker am Entry + Zähler im Result + Log-Zeile.
                    repair = _coerce_bezuege(final_entry)
                    if repair is not None:
                        format_repairs.append(repair)
                        if verbose:
                            print(f"[agent] ⚠ Format-Repair {repair['field']}: "
                                  f"{repair['method']}")
                tool_call_log.append({"tool": name})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": "Digest-Eintrag empfangen. Lauf beendet.",
                    }
                )
            else:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": f"[FEHLER] Unbekanntes Tool: {name}",
                    }
                )

        if final_entry is not None:
            break

    # OpenRouter liefert tatsächliche Kosten, wir nehmen die statt Schätzung.
    # Fallback auf manuelle Schätzung, wenn cost-Feld fehlt.
    actual_or_estimated = total_cost_usd if total_cost_usd > 0 else (
        (total_in / 1_000_000) * 15.0 + (total_out / 1_000_000) * 75.0
    )

    return {
        "entry": final_entry,
        "iterations": it,
        "tool_calls": tool_call_log,
        "format_repairs": format_repairs,
        "new_article": new_article,
        "enrichment": enrichment_data,
        "citation_hits": [h.__dict__ for h in citation_hits],
        "tokens_in": total_in,
        "tokens_out": total_out,
        "tokens_cached_read": total_cached_read,
        "tokens_cache_write": total_cache_write,
        "est_cost_usd": actual_or_estimated,
    }


def _format_new_article(article: dict, enrichment: dict) -> str:
    parts = ["=== NEUER BEITRAG ===\n"]
    parts.append(f"Journal:   {article.get('journal', '')}")
    parts.append(f"Titel:     {article.get('title', '')}")
    parts.append(f"Autor*innen: {', '.join(article.get('authors') or []) or '(unbekannt)'}")
    parts.append(f"DOI:       {article.get('doi', '') or '(kein DOI)'}")
    parts.append(f"URL:       {article.get('url', '')}")
    parts.append("")
    parts.append("Abstract (aus Feed):")
    parts.append(article.get("abstract", "") or "(leer)")

    oa = (enrichment or {}).get("openalex") or {}
    if oa.get("abstract"):
        parts.append("\nAbstract (aus OpenAlex, meist vollständiger):")
        parts.append(oa["abstract"][:4000])
    if oa.get("topics"):
        parts.append("\nOpenAlex-Topics: " + "; ".join(t["name"] for t in oa["topics"][:5]))
    if oa.get("concepts"):
        parts.append("OpenAlex-Concepts: " + "; ".join(c["name"] for c in oa["concepts"][:10]))

    refs = (enrichment or {}).get("references_crossref") or []
    if refs:
        parts.append(f"\nLiteraturverzeichnis ({len(refs)} Einträge, erste 40):")
        for r in refs[:40]:
            authors = ", ".join(r.get("authors") or [])
            year = r.get("year", "")
            title = r.get("title", "") or r.get("raw", "")
            parts.append(f"  · {year} {authors} — {title[:160]}")

    return "\n".join(parts)


# ------------------------------------------------ Two-Phase: Assess → Verify


def _format_verification_context(assessment_entry: dict, candidates: list[dict]) -> str:
    """Build the verification context appended to the user message in Phase 2."""
    lines = [
        "\n\n=== VERIFICATION PHASE ===",
        "You made a preliminary assessment of this article.",
        "Your candidate connections:\n",
    ]
    for c in candidates:
        lines.append(f"- pub_id: {c['pub_id']}")
        lines.append(f"  search_term: {c.get('search_term', '')}")
        lines.append(f"  hypothesis: {c.get('hypothesis', '')}")
    lines.append("")
    lines.append("Your task:")
    lines.append("1. Read each candidate publication ONCE with read_publication(pub_id, search_term).")
    lines.append("   Do NOT re-read the same publication with different search terms.")
    lines.append("   If the search_term is not found, the beginning of the text is returned — use that.")
    lines.append("2. After reading ALL candidates, call submit_digest_entry IMMEDIATELY.")
    lines.append("3. Write bezuege ONLY for confirmed connections. Be honest if a")
    lines.append("   hypothesis is not confirmed — that is a valid result.")
    lines.append("4. Carry over bemerkenswert and theoretisch_methodisch from the")
    lines.append("   preliminary assessment, supplement if the full text reveals more.")
    lines.append("5. Correct the verdict if the full text changes your assessment.")
    lines.append("6. CRITICAL: 'parallelisiert' alone is NOT enough for 'lesenswert'.")
    lines.append("   Only 'erweitert', 'widerspricht', or 'importiert' justify 'lesenswert'.")
    lines.append("")
    if assessment_entry.get("kernthese"):
        lines.append(f"Preliminary — kernthese: {assessment_entry['kernthese']}")
    if assessment_entry.get("bemerkenswert"):
        lines.append("Preliminary — bemerkenswert: "
                     + "; ".join(assessment_entry["bemerkenswert"]))
    if assessment_entry.get("verdict"):
        lines.append(f"Preliminary — verdict: {assessment_entry['verdict']}")
        lines.append(f"  reasoning: {assessment_entry.get('verdict_begruendung', '')}")
    return "\n".join(lines)


def assess_then_verify(
    new_article: dict,
    corpus_path: Path = CORPUS_JSON,
    summaries_path: Path = SUMMARIES_JSON,
    model: str = MODEL_AGENT,
    verbose: bool = True,
    article_id: str | None = None,
) -> dict:
    """Two-phase pipeline: assessment from summaries, then targeted verification.

    Phase 1 (Assessment): Agent works from the summary index only.
      - Irrelevant articles → submit immediately, no fulltext reads.
      - Relevant articles → identifies candidate_reads (pub_id + hypothesis).

    Phase 2 (Verification): Only when candidate_reads is non-empty.
      - Agent reads specifically identified publications.
      - Verifies or refutes candidate connections.
      - Produces final digest entry with honest, verified bezuege.
    """
    # --- Phase 1: Assessment ---
    if verbose:
        print("[assess] === Phase 1: Assessment (nur Index) ===")
    assessment = run_agent(
        new_article,
        corpus_path=corpus_path,
        summaries_path=summaries_path,
        model=model,
        max_iterations=1,
        verbose=verbose,
        allow_read=False,
        system_outro=ASSESSMENT_OUTRO,
        log_endpoint="assess",
        article_id=article_id,
    )

    entry = assessment.get("entry") or {}
    candidates = entry.get("candidate_reads") or []

    if not candidates:
        if verbose:
            print(f"[assess] Keine candidate_reads → Assessment ist Endergebnis "
                  f"(verdict={entry.get('verdict', '?')})")
        # Clean up: remove candidate_reads from final entry, ensure bezuege present
        entry.pop("candidate_reads", None)
        if "bezuege" not in entry:
            entry["bezuege"] = []
        return assessment

    # --- Phase 2: Verification ---
    if verbose:
        pubs = ", ".join(c["pub_id"] for c in candidates)
        print(f"[assess] {len(candidates)} candidate_reads → Verifikation ({pubs})")
        print("[assess] === Phase 2: Verification (gezielte Volltext-Reads) ===")

    max_iter_verify = min(len(candidates) * 2 + 2, 10)
    verification = run_agent(
        new_article,
        corpus_path=corpus_path,
        summaries_path=summaries_path,
        model=model,
        max_iterations=max_iter_verify,
        verbose=verbose,
        allow_read=True,
        extra_user_content=_format_verification_context(entry, candidates),
        log_endpoint="verify",
        article_id=article_id,
    )

    # Combine costs from both phases
    for key in ("tokens_in", "tokens_out", "tokens_cached_read",
                "tokens_cache_write", "est_cost_usd"):
        verification[key] = verification.get(key, 0) + assessment.get(key, 0)
    verification["iterations"] = (
        assessment.get("iterations", 0) + verification.get("iterations", 0)
    )
    verification["tool_calls"] = (
        assessment.get("tool_calls", []) + verification.get("tool_calls", [])
    )
    verification["format_repairs"] = (
        assessment.get("format_repairs", []) + verification.get("format_repairs", [])
    )
    # Stash assessment for transparency
    verification["assessment"] = entry

    # If verification exhausted iterations without submitting, fall back to
    # the assessment entry (better than returning None).
    if verification.get("entry") is None and entry:
        fallback = dict(entry)
        fallback.pop("candidate_reads", None)
        fallback["verdict_begruendung"] = (
            fallback.get("verdict_begruendung", "")
            + " (Verifikation ohne Ergebnis abgebrochen, Assessment-Verdict übernommen)"
        )
        verification["entry"] = fallback
    else:
        final = verification.get("entry") or {}
        final.pop("candidate_reads", None)

    return verification


# ------------------------------------------------------------- Rendering ---


VERDICT_LABEL = {
    "pflichtlektuere": "PFLICHTLEKTÜRE",
    "lesenswert":      "LESENSWERT",
    "scannen":         "SCANNEN",
    "ignorieren":      "IGNORIEREN",
}

RELATION_LABEL = {
    "erweitert":       "erweitert",
    "widerspricht":    "widerspricht",
    "parallelisiert":  "parallel",
    "importiert":      "import",
    "tangential":      "tangential",
}


def render_markdown(result: dict) -> str:
    article = result["new_article"]
    entry = result.get("entry")
    lines: list[str] = []

    title = article.get("title") or "(ohne Titel)"
    lines.append(f"## {title}")
    meta_bits: list[str] = []
    if article.get("authors"):
        meta_bits.append(", ".join(article["authors"]))
    if article.get("journal"):
        meta_bits.append(article["journal"])
    if article.get("doi"):
        meta_bits.append(f"doi:{article['doi']}")
    if meta_bits:
        lines.append("_" + " · ".join(meta_bits) + "_")
    if article.get("url"):
        lines.append(f"{article['url']}")
    lines.append("")

    if not entry:
        lines.append(
            f"(Agent hat nach {result['iterations']} Iterationen keinen "
            f"submit_digest_entry erreicht.)"
        )
        return "\n".join(lines)

    label = VERDICT_LABEL.get(entry.get("verdict", ""), entry.get("verdict", "?"))
    lines.append(f"**Verdict:** {label} — {entry.get('verdict_begruendung', '')}")
    lines.append("")

    meta_profile: list[str] = []
    if entry.get("selection_mode"):
        meta_profile.append(f"Selektion: `{entry['selection_mode']}`")
    if entry.get("discourse_indicator"):
        meta_profile.append(f"Diskursindikator: `{entry['discourse_indicator']}`")
    if entry.get("signal_group"):
        meta_profile.append(f"Signalgruppe: `{entry['signal_group']}`")
    if entry.get("suggested_subgroup"):
        meta_profile.append(f"Sub-Motiv: `{entry['suggested_subgroup']}`")
    if meta_profile:
        lines.append(" · ".join(meta_profile))
        lines.append("")

    # Zitationstreffer (wenn vorhanden) direkt nach dem Verdict sichtbar machen
    citation_hits = [
        h for h in (result.get("citation_hits") or []) if isinstance(h, dict)
    ]
    high = [h for h in citation_hits if h.get("confidence") == "high"]
    med = [h for h in citation_hits if h.get("confidence") == "medium"]
    low = [h for h in citation_hits if h.get("confidence") == "low"]
    if high or med or low:
        lines.append("### Zitiert Dich")
        if high:
            for h in high:
                authors = ", ".join(h.get("pub_authors", [])[:2]) or "?"
                lines.append(
                    f"- **{authors}** ({h.get('pub_year')}): "
                    f"{h.get('pub_title', '')[:100]} · `{h.get('pub_id')}`"
                )
        if med:
            for h in med:
                authors = ", ".join(h.get("pub_authors", [])[:2]) or "?"
                lines.append(
                    f"- _(wahrscheinlich)_ **{authors}** ({h.get('pub_year')}): "
                    f"{h.get('pub_title', '')[:100]} · `{h.get('pub_id')}`"
                )
        if low:
            lines.append(
                f"- _(unspezifische Namens-Erwähnung in {len(low)} Ref(s) "
                f"ohne Jahr/Titel-Match)_"
            )
        lines.append("")

    lines.append("### Kernthese")
    lines.append(entry.get("kernthese", ""))
    lines.append("")

    bezuege = entry.get("bezuege") or []
    if not isinstance(bezuege, list):
        bezuege = []
    bezuege = [b for b in bezuege if isinstance(b, dict)]
    lines.append("### Bezüge zu Deinem Werk")
    if not bezuege and not entry.get("bezuege_unparsed"):
        lines.append("_Keine substantiellen Bezüge gefunden._")
    else:
        for b in bezuege:
            rel = RELATION_LABEL.get(b.get("relation", ""), b.get("relation", ""))
            lines.append(f"\n**{b.get('pub_kurz', '?')}** (`{b.get('pub_id', '?')}`, {rel})")
            lines.append(b.get("bezug", ""))
    if entry.get("bezuege_unparsed"):
        lines.append("")
        lines.append("_⚠ Bezüge kamen in defektem Format (Modell lieferte keinen "
                     "parsebaren JSON-Array); Rohtext unverändert:_")
        lines.append(str(entry["bezuege_unparsed"]))
    lines.append("")

    bemerkenswert = entry.get("bemerkenswert") or []
    if bemerkenswert:
        lines.append("### Bemerkenswert")
        for note in bemerkenswert:
            lines.append(f"- {note}")
        lines.append("")

    lines.append("### Methodisch / theoretisch")
    lines.append(entry.get("theoretisch_methodisch", ""))
    lines.append("")

    # Footer: Meta
    lines.append("---")
    reads = sum(1 for t in result["tool_calls"] if t["tool"] == "read_publication")
    cache_read = result.get("tokens_cached_read", 0) or 0
    cache_write = result.get("tokens_cache_write", 0) or 0
    cache_bit = ""
    if cache_read or cache_write:
        cache_bit = f" · cache: {cache_read:,} read / {cache_write:,} write"
    foot = (
        f"_{result['iterations']} Agent-Iterationen · "
        f"{reads} Volltext-Reads · "
        f"{result['tokens_in']:,} in / {result['tokens_out']:,} out"
        f"{cache_bit} · "
        f"${result['est_cost_usd']:.3f}_"
    )
    lines.append(foot)
    return "\n".join(lines)
