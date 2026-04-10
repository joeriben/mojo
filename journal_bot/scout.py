"""Journal-Scout: Prüft Kandidaten-Journals auf Relevanz für Benjamins Profil.

Workflow:
  1. Watchlist parsen → Kandidaten ohne ✓ extrahieren
  2. ISSN via OpenAlex Sources API auflösen (wenn nicht in Watchlist)
  3. 3 Jahre Artikel pro Journal via OpenAlex holen (kein LLM)
  4. Haiku bewertet Relevanz gegen Benjamins Forschungsprofil (summaries.json)
  5. Ausgabe: priorisierte Liste mit Empfehlungen

Kosten: ~$0.01–$0.02 pro Journal (Haiku), $0.50–$1.00 für die volle Watchlist.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

from journal_bot.llm_client import build_client
from journal_bot.settings import JOURNALS, MODEL_SUMMARIZE, SUMMARIES_JSON


# ---------------------------------------------------------------- Typen


@dataclass
class Candidate:
    """A journal candidate parsed from the watchlist."""
    name: str
    issn: str = ""
    note: str = ""           # e.g. "T&F, ceer20" or "nicht in OpenAlex"
    section: str = ""        # watchlist section header
    already_tracked: bool = False


@dataclass
class ProbeResult:
    """Result of probing a journal via OpenAlex."""
    candidate: Candidate
    openalex_source_id: str = ""
    issn_resolved: str = ""
    article_count: int = 0
    sample_titles: list[str] = field(default_factory=list)
    sample_abstracts: list[str] = field(default_factory=list)
    error: str = ""


@dataclass
class ScoutVerdict:
    """LLM relevance verdict for a journal."""
    candidate: Candidate
    probe: ProbeResult
    verdict: str = ""        # "relevant" | "marginal" | "irrelevant"
    reason_de: str = ""
    suggested_clusters: list[str] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    est_cost_usd: float = 0.0


# ---------------------------------------------------------------- Watchlist-Parser


_ISSN_RE = re.compile(r"\b(\d{4}-?\d{3}[\dXx])\b")
_TRACKED_NAMES = {j.name.lower() for j in JOURNALS} | {j.short.lower() for j in JOURNALS}


def parse_watchlist(path: Path) -> list[Candidate]:
    """Parse the markdown watchlist into candidate journals.

    Skips entries marked with ✓ (already tracked).
    Extracts ISSNs from parenthetical notes where available.
    """
    candidates: list[Candidate] = []
    current_section = ""

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()

        # Track section headers
        if stripped.startswith("#"):
            current_section = stripped.lstrip("#").strip()
            continue

        # Only process list items
        if not stripped.startswith("- "):
            continue

        item = stripped[2:].strip()

        # Skip tracked entries
        if item.startswith("✓"):
            continue

        # Extract name and parenthetical note
        name = item
        note = ""
        paren_match = re.search(r"\(([^)]+)\)\s*$", item)
        if paren_match:
            note = paren_match.group(1)
            name = item[:paren_match.start()].strip().rstrip("-–—").strip()

        # Also strip trailing notes after em-dash
        dash_match = re.search(r"\s*[—–]\s*.+$", name)
        if dash_match:
            extra_note = name[dash_match.start():].strip().lstrip("—–").strip()
            name = name[:dash_match.start()].strip()
            if extra_note and not note:
                note = extra_note

        # Clean up name: remove leading abbreviation patterns like "ZfPäd"
        # but keep them if they ARE the name
        name = name.strip(" ,;")
        if not name:
            continue

        # Try to extract ISSN from note or name
        issn = ""
        issn_match = _ISSN_RE.search(note) or _ISSN_RE.search(name)
        if issn_match:
            raw = issn_match.group(1)
            # Normalize: add dash if missing
            if "-" not in raw:
                issn = f"{raw[:4]}-{raw[4:]}"
            else:
                issn = raw

        # Skip if it's already tracked (by name match)
        already = name.lower() in _TRACKED_NAMES
        if already:
            continue

        candidates.append(Candidate(
            name=name,
            issn=issn,
            note=note,
            section=current_section,
        ))

    return candidates


# ---------------------------------------------------------------- Name Expansion


# German abbreviations commonly found in watchlists
_DE_EXPANSIONS: list[tuple[str, str]] = [
    # Compound abbreviations (must come before single-char expansions)
    (r"\bZfPäd\b", "Zeitschrift für Pädagogik"),
    (r"\bZfM\b", "Zeitschrift für Medienwissenschaft"),
    (r"\bVjwP\b", "Vierteljahrsschrift für wissenschaftliche Pädagogik"),
    # Generic abbreviation patterns
    (r"\bZf\b\.?", "Zeitschrift für"),
    (r"\bVj\b\.?", "Vierteljahrsschrift für"),
    (r"\bInt\b\.?", "International"),
    (r"\bf\.\s*", "für "),
    (r"\bu\.\s*", "und "),
    (r"\ballg\.\s*", "allgemeine "),
    (r"\bwiss\.\s*", "wissenschaftliche "),
    (r"\bJ\b(?!\w)", "Journal"),
]

# URL-like pattern in name (e.g. "FQS (qualitative-research.net)")
_URL_IN_NAME_RE = re.compile(r"\s*\([a-z0-9.-]+\.[a-z]{2,}\)")


def _expand_name(raw: str) -> list[str]:
    """Generate search variants for a journal name.

    Returns a list of names to try, most specific first.
    """
    variants: list[str] = []

    # 1. Strip URL from name if embedded (e.g. "FQS (qualitative-research.net)")
    clean = _URL_IN_NAME_RE.sub("", raw).strip()

    # 2. "SHORT - Long Name" format: try the long part
    if " - " in clean:
        parts = clean.split(" - ", 1)
        long_part = parts[1].strip()
        # Expand abbreviations in the long part too
        expanded_long = long_part
        for pat, repl in _DE_EXPANSIONS:
            expanded_long = re.sub(pat, repl, expanded_long)
        expanded_long = re.sub(r"\s+", " ", expanded_long).strip()
        if expanded_long != long_part:
            variants.append(expanded_long)
        variants.append(long_part)

    # 3. Full expansion of the clean name
    expanded = clean
    for pat, repl in _DE_EXPANSIONS:
        expanded = re.sub(pat, repl, expanded)
    expanded = re.sub(r"\s+", " ", expanded).strip()
    if expanded != clean:
        variants.append(expanded)

    # 4. Original clean name as fallback
    variants.append(clean)

    # 5. Keyword-only fallback: drop generic leading words (Zeitschrift,
    #    Journal, Vierteljahr*, International) and search with the thematic
    #    core only. Catches typos in the generic prefix.
    drop = {"zeitschrift", "journal", "international", "vierteljahrsschrift",
            "vierteljahresschrift"}
    core_words = [w for w in re.findall(r"\w{3,}", expanded)
                  if w.lower() not in drop and w.lower() not in {"für", "und", "the", "and", "of"}]
    if len(core_words) >= 2:
        variants.append(" ".join(core_words[:4]))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for v in variants:
        if v.lower() not in seen and len(v) > 2:
            seen.add(v.lower())
            unique.append(v)
    return unique


_PUBLISHER_DOMAINS = {
    "springer.com", "wiley.com", "tandfonline.com", "sagepub.com",
    "degruyter.com", "palgrave.com", "elsevier.com", "jstor.org",
    "cambridge.org", "oxford.org", "routledge.com", "brill.com",
    # German publisher/hosting platforms
    "vr-elibrary.de", "budrich-journals.de", "nomos-elibrary.de",
    "beltz.de", "waxmann.com", "pedocs.de",
}


def _extract_url_hint(name: str, note: str) -> str:
    """Extract a domain hint for disambiguation from name or note.

    Only returns a hint for journal-specific domains (e.g. 'oneducation.net'),
    not for generic publisher platforms (e.g. 'vr-elibrary.de').
    """
    for text in [note, name]:
        m = re.search(r"\b([a-z0-9-]+\.[a-z]{2,}(?:\.[a-z]{2})?)\b", text.lower())
        if m:
            domain = m.group(1)
            # Skip generic publisher/platform domains
            if domain in _PUBLISHER_DOMAINS:
                continue
            if domain not in {"t&f", "de"} and "." in domain:
                return domain
    return ""


# ---------------------------------------------------------------- ISSN Resolution


OPENALEX_SOURCES = "https://api.openalex.org/sources"
POLITE_MAILTO = "journal-bot@localhost"
USER_AGENT = f"journal-bot/0.1 (mailto:{POLITE_MAILTO})"
_HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}


def _search_openalex_sources(query: str, n: int = 5) -> list[dict]:
    """Raw OpenAlex sources search, returns up to n results with metadata."""
    try:
        resp = httpx.get(
            OPENALEX_SOURCES,
            params={
                "search": query,
                "mailto": POLITE_MAILTO,
                "per-page": n,
                "select": "id,display_name,issn,homepage_url,type",
            },
            headers=_HEADERS,
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        return resp.json().get("results") or []
    except Exception:
        return []


def _score_source(source: dict, query: str, url_hint: str) -> float:
    """Score an OpenAlex source candidate for match quality.

    Higher is better. Considers name similarity and URL hint match.
    """
    score = 0.0
    display = (source.get("display_name") or "").lower()
    query_low = query.lower()

    # Exact match
    if display == query_low:
        score += 10.0
    # Query contained in display name or vice versa
    elif query_low in display:
        score += 5.0
    elif display in query_low:
        score += 3.0

    # Word overlap
    query_words = set(re.findall(r"\w{3,}", query_low))
    display_words = set(re.findall(r"\w{3,}", display))
    if query_words and display_words:
        overlap = len(query_words & display_words) / max(len(query_words), 1)
        score += overlap * 4.0

    # URL hint match (strong signal)
    if url_hint:
        homepage = (source.get("homepage_url") or "").lower()
        if url_hint in homepage:
            score += 20.0

    # Prefer type "journal" over others
    if source.get("type") == "journal":
        score += 1.0

    return score


def resolve_issn_openalex(
    name: str, url_hint: str = ""
) -> tuple[str, str, str]:
    """Resolve a journal name to (issn, source_id, matched_name).

    Tries multiple name variants and uses URL hint for disambiguation.
    """
    variants = _expand_name(name)
    all_candidates: list[tuple[dict, float, str]] = []  # (source, score, query)

    for variant in variants:
        sources = _search_openalex_sources(variant, n=5)
        for src in sources:
            sc = _score_source(src, variant, url_hint)
            all_candidates.append((src, sc, variant))

    if not all_candidates:
        return "", "", ""

    # Deduplicate by source ID, keep highest score
    best_by_id: dict[str, tuple[dict, float]] = {}
    for src, sc, _ in all_candidates:
        sid = src.get("id", "")
        if sid not in best_by_id or sc > best_by_id[sid][1]:
            best_by_id[sid] = (src, sc)

    # Pick the best overall
    best_src, best_score = max(best_by_id.values(), key=lambda x: x[1])

    # If we had a URL hint but no candidate matched it, the best hit is
    # probably a false positive (e.g. "On Education" → "IEEE Trans. on Edu.")
    if url_hint:
        any_url_match = any(
            url_hint in (s.get("homepage_url") or "").lower()
            for s, _ in best_by_id.values()
        )
        if not any_url_match:
            return "", "", ""

    issns = best_src.get("issn") or []
    issn = issns[0] if issns else ""
    source_id = best_src.get("id", "")
    matched_name = best_src.get("display_name", "")
    return issn, source_id, matched_name


# ---------------------------------------------------------------- Probe


OPENALEX_WORKS = "https://api.openalex.org/works"


def probe_journal(candidate: Candidate, window_years: int = 3) -> ProbeResult:
    """Fetch recent articles from a journal via OpenAlex.

    Tries ISSN first, falls back to source name search with disambiguation.
    """
    result = ProbeResult(candidate=candidate)

    # Skip known non-OpenAlex journals
    if "nicht in openalex" in (candidate.note or "").lower():
        result.error = "nicht in OpenAlex (laut Watchlist)"
        return result

    # Resolve ISSN if needed
    issn = candidate.issn
    source_id = ""
    if not issn:
        url_hint = _extract_url_hint(candidate.name, candidate.note)
        issn, source_id, matched = resolve_issn_openalex(
            candidate.name, url_hint=url_hint,
        )
        if not issn and not source_id:
            result.error = "ISSN konnte nicht aufgelöst werden"
            return result

    result.issn_resolved = issn
    result.openalex_source_id = source_id

    # Build filter
    from_date = (datetime.utcnow() - timedelta(days=window_years * 365)).date().isoformat()
    if issn:
        source_filter = f"primary_location.source.issn:{issn}"
    else:
        sid = source_id.rsplit("/", 1)[-1] if source_id else ""
        source_filter = f"primary_location.source.id:{sid}"

    full_filter = f"{source_filter},from_publication_date:{from_date},type:article"

    params = {
        "filter": full_filter,
        "sort": "publication_date:desc",
        "per-page": 50,
        "mailto": POLITE_MAILTO,
        "select": "id,doi,title,abstract_inverted_index,publication_date",
    }

    try:
        resp = httpx.get(
            OPENALEX_WORKS,
            params=params,
            timeout=30,
            headers=_HEADERS,
        )
        if resp.status_code != 200:
            result.error = f"OpenAlex {resp.status_code}"
            return result

        data = resp.json()
        meta = data.get("meta", {})
        result.article_count = meta.get("count", 0)
        works = data.get("results") or []

        for w in works[:30]:
            title = (w.get("title") or "").strip()
            if title:
                result.sample_titles.append(title)
            inv = w.get("abstract_inverted_index")
            if inv:
                abstract = _reconstruct_abstract(inv)
                if abstract:
                    result.sample_abstracts.append(abstract[:500])

    except Exception as e:
        result.error = str(e)

    return result


def _reconstruct_abstract(inverted: dict | None) -> str:
    if not inverted:
        return ""
    positions: dict[int, str] = {}
    for word, idxs in inverted.items():
        for i in idxs:
            positions[i] = word
    if not positions:
        return ""
    return " ".join(positions[i] for i in sorted(positions.keys()))


# ---------------------------------------------------------------- LLM Evaluation


def _load_profile_block() -> str:
    """Build a compact research profile from summaries.json for the scout prompt."""
    data = json.loads(SUMMARIES_JSON.read_text(encoding="utf-8"))
    summaries = data.get("summaries", {})

    lines: list[str] = []
    sorted_pubs = sorted(
        summaries.items(),
        key=lambda kv: (kv[1].get("year") or 0),
        reverse=True,
    )
    for pub_id, s in sorted_pubs:
        year = s.get("year") or "?"
        title = s.get("title", "").strip()
        lines.append(f"\n--- {pub_id} ({year}): {title}")
        if s.get("summary_de"):
            lines.append(s["summary_de"])
        if s.get("key_terms"):
            lines.append("Begriffe: " + "; ".join(s["key_terms"][:8]))
    return "\n".join(lines)


SCOUT_SYSTEM = """Du bist ein wissenschaftlicher Evaluator. Du bewertest, ob eine Zeitschrift
für Benjamin Jörissen relevant ist.

Benjamins Arbeitsgebiete: ästhetische und kulturelle Bildung, Postdigitalität, generative KI
in Bildungskontexten, Cultural Resilience, digital-kulturelles Erbe, New Materialisms,
Bildungstheorie, qualitative Methoden (insb. postqualitative Ansätze).

Unten folgt Benjamins Publikationsstand als Kurzprofile.

{profile}

=== AUFGABE ===
Du bekommst den Namen einer Zeitschrift und eine Stichprobe kürzlich publizierter Titel
und Abstracts. Entscheide:

- **relevant**: Die Zeitschrift publiziert regelmäßig Beiträge, die an Benjamins
  Arbeitsgebiete anschließen. Mindestens 3-4 der Stichproben-Titel haben erkennbaren Bezug.
- **marginal**: Gelegentliche Berührungspunkte, aber die Zeitschrift deckt primär ein
  anderes Feld ab. 1-2 der Stichproben sind relevant, der Rest nicht.
- **irrelevant**: Kein erkennbarer systematischer Bezug zu Benjamins Forschung.

Rufe das Tool `scout_verdict` auf."""


SCOUT_TOOL = {
    "type": "function",
    "function": {
        "name": "scout_verdict",
        "description": "Gibt das Relevanz-Urteil für eine Zeitschrift ab.",
        "parameters": {
            "type": "object",
            "properties": {
                "verdict": {
                    "type": "string",
                    "enum": ["relevant", "marginal", "irrelevant"],
                    "description": "Relevanz-Einschätzung.",
                },
                "reason_de": {
                    "type": "string",
                    "description": (
                        "2-3 Sätze Begründung auf Deutsch. Konkret: welche "
                        "thematischen Überschneidungen (oder deren Fehlen)."
                    ),
                },
                "suggested_clusters": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Passende Diskursräume aus: deutsche, erziehungswiss, "
                        "digitale_kultur, medienpaed, bildungstheorie, "
                        "aesthetische_kulturelle_bildung, resilienz"
                    ),
                },
            },
            "required": ["verdict", "reason_de", "suggested_clusters"],
        },
    },
}


def evaluate_journal(
    probe: ProbeResult,
    profile_block: str,
    client,
    verbose: bool = True,
) -> ScoutVerdict:
    """Ask Haiku to evaluate journal relevance."""
    c = probe.candidate
    verdict = ScoutVerdict(candidate=c, probe=probe)

    if probe.error or not probe.sample_titles:
        verdict.verdict = "?"
        verdict.reason_de = probe.error or "Keine Artikel gefunden"
        return verdict

    # Build user message with sample
    user_lines = [f"Zeitschrift: {c.name}"]
    user_lines.append(f"Artikel in den letzten 3 Jahren: {probe.article_count}")
    user_lines.append(f"\nStichprobe ({len(probe.sample_titles)} Titel):\n")

    for i, title in enumerate(probe.sample_titles[:25]):
        abstract = probe.sample_abstracts[i] if i < len(probe.sample_abstracts) else ""
        user_lines.append(f"{i+1}. {title}")
        if abstract:
            user_lines.append(f"   {abstract[:300]}")

    system = SCOUT_SYSTEM.format(profile=profile_block)

    try:
        resp = client.chat.completions.create(
            model=MODEL_SUMMARIZE,
            messages=[
                {"role": "system", "content": [
                    {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}},
                ]},
                {"role": "user", "content": "\n".join(user_lines)},
            ],
            tools=[SCOUT_TOOL],
            tool_choice={"type": "function", "function": {"name": "scout_verdict"}},
            temperature=0.2,
        )
    except Exception as e:
        verdict.verdict = "?"
        verdict.reason_de = f"LLM-Fehler: {e}"
        return verdict

    usage = resp.usage
    if usage:
        verdict.tokens_in = usage.prompt_tokens
        verdict.tokens_out = usage.completion_tokens
        # Haiku 4.5 pricing
        verdict.est_cost_usd = (
            (usage.prompt_tokens / 1_000_000) * 0.80
            + (usage.completion_tokens / 1_000_000) * 4.00
        )

    # Parse tool call
    msg = resp.choices[0].message
    if msg.tool_calls:
        args = json.loads(msg.tool_calls[0].function.arguments)
        verdict.verdict = args.get("verdict", "?")
        verdict.reason_de = args.get("reason_de", "")
        verdict.suggested_clusters = args.get("suggested_clusters", [])

    return verdict


# ---------------------------------------------------------------- Rendering


def render_markdown(verdicts: list[ScoutVerdict], window_years: int = 3) -> str:
    this_year = datetime.now().year
    start_year = this_year - window_years + 1

    relevant = [v for v in verdicts if v.verdict == "relevant"]
    marginal = [v for v in verdicts if v.verdict == "marginal"]
    irrelevant = [v for v in verdicts if v.verdict == "irrelevant"]
    skipped = [v for v in verdicts if v.verdict == "?"]

    total_cost = sum(v.est_cost_usd for v in verdicts)

    lines: list[str] = []
    lines.append(f"# Journal-Scout: Relevanz-Prüfung")
    lines.append(f"_Datum: {date.today().isoformat()} · "
                 f"Fenster: {start_year}-{this_year} · "
                 f"Kosten: ${total_cost:.2f}_")
    lines.append("")
    lines.append(f"**{len(relevant)}** relevant · "
                 f"**{len(marginal)}** marginal · "
                 f"**{len(irrelevant)}** irrelevant · "
                 f"**{len(skipped)}** übersprungen")
    lines.append("")

    def _table(title: str, items: list[ScoutVerdict]) -> None:
        if not items:
            return
        lines.append(f"## {title}")
        lines.append("")
        for v in items:
            c = v.candidate
            clusters = ", ".join(v.suggested_clusters) if v.suggested_clusters else "—"
            art_count = v.probe.article_count if v.probe else 0
            lines.append(f"### {c.name}")
            if c.issn or v.probe.issn_resolved:
                lines.append(f"ISSN: {v.probe.issn_resolved or c.issn}")
            lines.append(f"Artikel ({start_year}-{this_year}): {art_count}")
            lines.append(f"Diskursräume: {clusters}")
            lines.append(f"\n> {v.reason_de}")
            lines.append("")
        lines.append("")

    _table("Relevant — aufnehmen", relevant)
    _table("Marginal — optional", marginal)
    _table("Irrelevant — nicht aufnehmen", irrelevant)

    if skipped:
        lines.append("## Übersprungen")
        lines.append("")
        for v in skipped:
            lines.append(f"- **{v.candidate.name}**: {v.reason_de}")
        lines.append("")

    lines.append("---")
    lines.append(f"_Kosten: ${total_cost:.2f} (Haiku 4.5) · Keine manuellen Entscheidungen nötig_")
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI-Entry


def run(
    watchlist: Path,
    window_years: int = 3,
    limit: int | None = None,
    verbose: bool = True,
    out_dir: Path | None = None,
) -> dict:
    from journal_bot.settings import DIGEST_DIR
    out_dir = out_dir or DIGEST_DIR

    # 1. Parse watchlist
    candidates = parse_watchlist(watchlist)
    if limit:
        candidates = candidates[:limit]

    if verbose:
        print(f"[scout] {len(candidates)} Kandidaten aus Watchlist")

    # 2. Load profile once
    if verbose:
        print("[scout] Lade Forschungsprofil (summaries.json)...")
    profile_block = _load_profile_block()

    # 3. Probe all journals (no LLM)
    if verbose:
        print(f"[scout] Probe {len(candidates)} Journals via OpenAlex...")

    probes: list[ProbeResult] = []
    for i, c in enumerate(candidates):
        if verbose:
            print(f"[scout]   {i+1}/{len(candidates)} {c.name}...", end=" ", flush=True)
        probe = probe_journal(c, window_years)
        probes.append(probe)
        if verbose:
            if probe.error:
                print(f"✗ {probe.error}")
            else:
                print(f"✓ {probe.article_count} Artikel, "
                      f"{len(probe.sample_titles)} Titel")
        # Polite pause
        time.sleep(0.2)

    # 4. LLM evaluation (Haiku)
    evaluable = [p for p in probes if not p.error and p.sample_titles]
    if verbose:
        print(f"\n[scout] LLM-Evaluation für {len(evaluable)} Journals "
              f"({len(probes) - len(evaluable)} übersprungen)...")

    client = build_client()
    verdicts: list[ScoutVerdict] = []
    total_cost = 0.0

    # Add skipped ones first
    for p in probes:
        if p.error or not p.sample_titles:
            verdicts.append(ScoutVerdict(
                candidate=p.candidate, probe=p,
                verdict="?",
                reason_de=p.error or "Keine Artikel gefunden",
            ))

    for i, p in enumerate(evaluable):
        if verbose:
            print(f"[scout]   {i+1}/{len(evaluable)} {p.candidate.name}...", end=" ", flush=True)
        v = evaluate_journal(p, profile_block, client, verbose)
        verdicts.append(v)
        total_cost += v.est_cost_usd
        if verbose:
            print(f"{v.verdict} (${v.est_cost_usd:.3f})")

    # Sort: relevant first, then marginal, then irrelevant, then skipped
    order = {"relevant": 0, "marginal": 1, "irrelevant": 2, "?": 3}
    verdicts.sort(key=lambda v: order.get(v.verdict, 9))

    # 5. Output
    md = render_markdown(verdicts, window_years)

    trends_dir = out_dir / "trends"
    trends_dir.mkdir(parents=True, exist_ok=True)
    filename = f"scout_{date.today().isoformat()}.md"
    out_path = trends_dir / filename
    out_path.write_text(md, encoding="utf-8")

    if verbose:
        print(f"\n[scout] Geschrieben: {out_path}")
        print(f"[scout] Kosten: ${total_cost:.2f}")
        rel = sum(1 for v in verdicts if v.verdict == "relevant")
        mar = sum(1 for v in verdicts if v.verdict == "marginal")
        irr = sum(1 for v in verdicts if v.verdict == "irrelevant")
        print(f"[scout] Ergebnis: {rel} relevant, {mar} marginal, {irr} irrelevant")

    return {
        "status": "ok",
        "path": str(out_path),
        "total_cost_usd": total_cost,
        "relevant": sum(1 for v in verdicts if v.verdict == "relevant"),
        "marginal": sum(1 for v in verdicts if v.verdict == "marginal"),
        "irrelevant": sum(1 for v in verdicts if v.verdict == "irrelevant"),
        "skipped": sum(1 for v in verdicts if v.verdict == "?"),
    }
