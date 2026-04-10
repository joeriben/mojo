"""Journal-Scout: Multi-Linsen-Evaluation von Kandidaten-Journals.

Architektur (3 Linsen + Opus-Synthese):
  1. Watchlist parsen → Kandidaten ohne ✓ extrahieren
  2. ISSN via OpenAlex Sources API auflösen (wenn nicht in Watchlist)
  3. 3 Jahre Artikel pro Journal via OpenAlex holen (kein LLM)
  4. Drei Haiku-Linsen pro Journal (parallel):
     A) Thematische Passung — Überlappung mit Benjamins Forschungsthemen
     B) Disziplinäre Beheimatungen — Zugehörigkeit zu Benjamins 5 diskursiven Räumen
     C) Latente Relevanz — periphere Diskurse die im Blickfeld bleiben sollten
  5. Opus-Synthese: kartiert Spannungen zwischen den Linsen, empfiehlt
  6. Ausgabe: multiperspektivische Bewertung nach Obsidian

Kosten: ~$0.03 pro Journal (3× Haiku) + ~$0.50–1.00 Opus-Synthese (gebatcht).
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
from journal_bot.settings import JOURNALS, MODEL_AGENT, MODEL_SUMMARIZE, SUMMARIES_JSON


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
class LensResult:
    """Result from a single evaluation lens."""
    lens: str               # "thematisch" | "disziplinaer" | "latent"
    verdict: str = ""       # lens-specific verdict
    reason_de: str = ""
    details: dict = field(default_factory=dict)  # lens-specific structured data
    tokens_in: int = 0
    tokens_out: int = 0
    est_cost_usd: float = 0.0


@dataclass
class ScoutVerdict:
    """Multi-lens verdict for a journal."""
    candidate: Candidate
    probe: ProbeResult
    lens_results: list[LensResult] = field(default_factory=list)
    # Opus synthesis
    synthesis_de: str = ""
    empfehlung: str = ""     # "aufnehmen" | "beobachten" | "nicht_aufnehmen"
    suggested_clusters: list[str] = field(default_factory=list)
    total_cost_usd: float = 0.0


# ---------------------------------------------------------------- Watchlist-Parser


_ISSN_RE = re.compile(r"\b(\d{4}-?\d{3}[\dXx])\b")
_TRACKED_NAMES = {j.name.lower() for j in JOURNALS} | {j.short.lower() for j in JOURNALS}


def parse_watchlist(path: Path) -> tuple[list[Candidate], list[str]]:
    """Parse the markdown watchlist into candidate journals + tracked names.

    Returns (candidates, tracked_names) where tracked_names are ✓-marked entries.
    """
    candidates: list[Candidate] = []
    tracked_names: list[str] = []
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

        # Collect tracked entries
        if item.startswith("✓"):
            # Extract name from "✓ ZfE" or "✓ BJET - British Journal..."
            tracked_name = item[1:].strip()
            # Strip parenthetical notes
            paren = re.search(r"\(([^)]+)\)\s*$", tracked_name)
            if paren:
                tracked_name = tracked_name[:paren.start()].strip().rstrip("-–—").strip()
            dash = re.search(r"\s*[—–]\s*.+$", tracked_name)
            if dash:
                tracked_name = tracked_name[:dash.start()].strip()
            tracked_names.append(tracked_name.strip(" ,;"))
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

    # Deduplicate by normalized name, keeping the entry with the most info
    seen: dict[str, int] = {}
    deduped: list[Candidate] = []
    for c in candidates:
        key = c.name.lower().strip()
        if key in seen:
            # Keep the one with more metadata (ISSN, note)
            idx = seen[key]
            existing = deduped[idx]
            if not existing.issn and c.issn:
                deduped[idx] = c
            continue
        seen[key] = len(deduped)
        deduped.append(c)

    return deduped, tracked_names


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
POLITE_MAILTO = "mojo@localhost"
USER_AGENT = f"mojo/0.1 (mailto:{POLITE_MAILTO})"
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


def _build_sample_block(probe: ProbeResult) -> str:
    """Build the article sample block shared by all lenses."""
    c = probe.candidate
    lines = [f"Zeitschrift: {c.name}"]
    lines.append(f"Artikel in den letzten 3 Jahren: {probe.article_count}")
    lines.append(f"\nStichprobe ({len(probe.sample_titles)} Titel):\n")
    for i, title in enumerate(probe.sample_titles[:25]):
        abstract = probe.sample_abstracts[i] if i < len(probe.sample_abstracts) else ""
        lines.append(f"{i+1}. {title}")
        if abstract:
            lines.append(f"   {abstract[:300]}")
    return "\n".join(lines)


# --- Beheimatungen (from Benjamin, 2026-04-10) ---

BEHEIMATUNGEN = [
    ("Allgemeine Pädagogik / Bildungstheorie",
     "Institutionelle Heimat (Lehrstuhl FAU). Bildungsphilosophie, Subjektivierung, "
     "Transformationsprozesse, erziehungswissenschaftliche Grundfragen."),
    ("Posthumanismus / STS / Resilienz",
     "Paradigmenwechsel zu relationaler Bildungstheorie. New Materialisms, "
     "Science & Technology Studies, Cultural Resilience, mehr-als-menschliche Perspektiven."),
    ("Medienbildung / Medienpädagogik",
     "Kernfeld: mediale Bildungsprozesse, Postdigitalität, generative KI in Bildung, "
     "Medienkultur und Subjektivierung."),
    ("Pädagogische Medienforschung / Medienwissenschaft",
     "Medienwissenschaftlich orientiert: digitale Kultur, Plattformen, "
     "Algorithmen, methodische Zugänge zu Medienpraktiken."),
    ("Kulturwissenschaft / Ästhetik",
     "Kulturelle und ästhetische Bildung, Kunst-Bildungs-Verhältnis, "
     "visuelle Kultur, ästhetische Erfahrung, künstlerische Forschung."),
]


# ---------------------------------------------------------------- Linse A: Thematisch


LENS_A_SYSTEM = """Du bist ein wissenschaftlicher Evaluator. Du bewertest die THEMATISCHE
PASSUNG einer Zeitschrift zu Benjamin Jörissens konkreten Forschungsthemen.

Benjamins Arbeitsgebiete: ästhetische und kulturelle Bildung, Postdigitalität, generative KI
in Bildungskontexten, Cultural Resilience, digital-kulturelles Erbe, New Materialisms,
Bildungstheorie, qualitative Methoden (insb. postqualitative Ansätze).

Unten folgt Benjamins Publikationsstand als Kurzprofile.

{profile}

=== AUFGABE ===
Bewerte NUR die thematische Passung: Wie viele der Stichproben-Artikel behandeln Themen,
die an Benjamins konkrete Arbeitsgebiete anschließen? Zähle präzise.

Rufe das Tool `lens_a_verdict` auf."""


LENS_A_TOOL = {
    "type": "function",
    "function": {
        "name": "lens_a_verdict",
        "description": "Thematische Passung einer Zeitschrift.",
        "parameters": {
            "type": "object",
            "properties": {
                "passung": {
                    "type": "string",
                    "enum": ["hoch", "mittel", "niedrig"],
                    "description": "hoch: ≥4 Titel mit Bezug. mittel: 2-3. niedrig: 0-1.",
                },
                "matching_count": {
                    "type": "integer",
                    "description": "Anzahl der Stichproben-Titel mit erkennbarem thematischen Bezug.",
                },
                "matching_titles": {
                    "type": "string",
                    "description": "Nummern der passenden Titel (z.B. '3, 8, 12, 23').",
                },
                "reason_de": {
                    "type": "string",
                    "description": "2-3 Sätze: Welche Themenüberschneidungen? Was fehlt?",
                },
            },
            "required": ["passung", "matching_count", "matching_titles", "reason_de"],
        },
    },
}


# ---------------------------------------------------------------- Linse B: Disziplinäre Beheimatungen


def _build_lens_b_system() -> str:
    beh_block = "\n".join(
        f"  {i+1}. **{name}**: {desc}"
        for i, (name, desc) in enumerate(BEHEIMATUNGEN)
    )
    return f"""Du bist ein wissenschaftlicher Evaluator. Du bewertest die DISZIPLINÄRE
ZUGEHÖRIGKEIT einer Zeitschrift zu Benjamin Jörissens diskursiven Beheimatungen.

Benjamin verortet sich in folgenden disziplinären Räumen:

{beh_block}

=== AUFGABE ===
Bewerte: Ist diese Zeitschrift ein Publikationsort für eine oder mehrere dieser
disziplinären Communities? Nicht ob einzelne Artikel thematisch passen, sondern ob die
Zeitschrift ALS GANZES zur Infrastruktur eines dieser Diskursfelder gehört.

Beispiel: Die ZfPäd ist ein zentrales Organ der Allgemeinen Pädagogik, auch wenn einzelne
Hefte sich mit Themen befassen die Benjamin nicht bearbeitet.

Rufe das Tool `lens_b_verdict` auf."""


LENS_B_TOOL = {
    "type": "function",
    "function": {
        "name": "lens_b_verdict",
        "description": "Disziplinäre Verortung einer Zeitschrift.",
        "parameters": {
            "type": "object",
            "properties": {
                "beheimatungen": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string",
                                     "description": "Name der Beheimatung"},
                            "fit": {"type": "string",
                                    "enum": ["zentral", "peripher", "kein_bezug"],
                                    "description": "zentral: Kernorgan. peripher: gelegentlich relevant. kein_bezug."},
                        },
                        "required": ["name", "fit"],
                    },
                    "description": "Bewertung für jede der 5 Beheimatungen.",
                },
                "reason_de": {
                    "type": "string",
                    "description": "2-3 Sätze: Warum gehört (oder gehört nicht) diese Zeitschrift zu diesen diskursiven Räumen?",
                },
            },
            "required": ["beheimatungen", "reason_de"],
        },
    },
}


# ---------------------------------------------------------------- Linse C: Latente Relevanz


LENS_C_SYSTEM = """Du bist ein wissenschaftlicher Evaluator. Du bewertest die LATENTE RELEVANZ
einer Zeitschrift für Benjamin Jörissen — d.h. Diskurse die Benjamin nicht aktiv bearbeitet,
aber im Blickfeld haben sollte.

Benjamins Arbeitsgebiete: ästhetische und kulturelle Bildung, Postdigitalität, generative KI
in Bildungskontexten, Cultural Resilience, digital-kulturelles Erbe, New Materialisms,
Bildungstheorie, qualitative Methoden (insb. postqualitative Ansätze).

=== AUFGABE ===
Prüfe die Stichprobe auf Diskurse die Benjamin NICHT bearbeitet, die aber trotzdem sein
Denken herausfordern, erweitern oder kontextualisieren könnten.

FILTER: Nicht alles Periphere ist relevant. Eyetracking in der Unterrichtsforschung oder
PISA-Ranking-Analysen wären NICHT latent relevant. Aber z.B.:
- Neue methodische Zugänge die seine Methoden ergänzen könnten
- Debatten in angrenzenden Feldern die seine Grundannahmen berühren
- Gegenstände die er nicht bearbeitet aber die seine Theorie testen würden

Rufe das Tool `lens_c_verdict` auf."""


LENS_C_TOOL = {
    "type": "function",
    "function": {
        "name": "lens_c_verdict",
        "description": "Latente Relevanz einer Zeitschrift.",
        "parameters": {
            "type": "object",
            "properties": {
                "latente_relevanz": {
                    "type": "string",
                    "enum": ["hoch", "mittel", "niedrig"],
                    "description": "hoch: mehrere Diskurse die Benjamins Denken produktiv herausfordern. mittel: vereinzelt. niedrig: nichts Relevantes.",
                },
                "topics_de": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2-5 konkrete Diskurse/Themen die latent relevant wären (leer wenn niedrig).",
                },
                "reason_de": {
                    "type": "string",
                    "description": "2-3 Sätze: Welche angrenzenden Diskurse? Warum könnten sie Benjamins Arbeit bereichern?",
                },
            },
            "required": ["latente_relevanz", "topics_de", "reason_de"],
        },
    },
}


# ---------------------------------------------------------------- Lens Evaluation


def _run_lens(
    lens_name: str,
    system_prompt: str,
    tool_def: dict,
    tool_name: str,
    sample_block: str,
    client,
    use_cache: bool = False,
) -> LensResult:
    """Run a single Haiku evaluation lens."""
    result = LensResult(lens=lens_name)

    content = [{"type": "text", "text": system_prompt}]
    if use_cache:
        content[0]["cache_control"] = {"type": "ephemeral"}

    try:
        resp = client.chat.completions.create(
            model=MODEL_SUMMARIZE,
            messages=[
                {"role": "system", "content": content},
                {"role": "user", "content": sample_block},
            ],
            tools=[tool_def],
            tool_choice={"type": "function", "function": {"name": tool_name}},
            temperature=0.2,
        )
    except Exception as e:
        result.verdict = "?"
        result.reason_de = f"LLM-Fehler: {e}"
        return result

    usage = resp.usage
    if usage:
        result.tokens_in = usage.prompt_tokens
        result.tokens_out = usage.completion_tokens
        result.est_cost_usd = (
            (usage.prompt_tokens / 1_000_000) * 0.80
            + (usage.completion_tokens / 1_000_000) * 4.00
        )

    msg = resp.choices[0].message
    if msg.tool_calls:
        args = json.loads(msg.tool_calls[0].function.arguments)
        result.details = args
        result.reason_de = args.get("reason_de", "")
        # Extract lens-specific verdict
        if lens_name == "thematisch":
            result.verdict = args.get("passung", "?")
        elif lens_name == "disziplinaer":
            beh = args.get("beheimatungen", [])
            zentral = [b for b in beh if b.get("fit") == "zentral"]
            result.verdict = "zentral" if zentral else ("peripher" if beh else "?")
        elif lens_name == "latent":
            result.verdict = args.get("latente_relevanz", "?")

    return result


def evaluate_journal_multilens(
    probe: ProbeResult,
    profile_block: str,
    client,
    verbose: bool = True,
) -> ScoutVerdict:
    """Run all 3 evaluation lenses on a journal."""
    c = probe.candidate
    verdict = ScoutVerdict(candidate=c, probe=probe)

    if probe.error or not probe.sample_titles:
        verdict.empfehlung = "?"
        verdict.synthesis_de = probe.error or "Keine Artikel gefunden"
        return verdict

    sample_block = _build_sample_block(probe)

    # Lens A: Thematische Passung
    lens_a = _run_lens(
        "thematisch",
        LENS_A_SYSTEM.format(profile=profile_block),
        LENS_A_TOOL,
        "lens_a_verdict",
        sample_block,
        client,
        use_cache=True,
    )
    verdict.lens_results.append(lens_a)
    if verbose:
        print(f"A:{lens_a.verdict}", end=" ", flush=True)

    # Lens B: Disziplinäre Beheimatungen
    lens_b = _run_lens(
        "disziplinaer",
        _build_lens_b_system(),
        LENS_B_TOOL,
        "lens_b_verdict",
        sample_block,
        client,
    )
    verdict.lens_results.append(lens_b)
    if verbose:
        print(f"B:{lens_b.verdict}", end=" ", flush=True)

    # Lens C: Latente Relevanz
    lens_c = _run_lens(
        "latent",
        LENS_C_SYSTEM,
        LENS_C_TOOL,
        "lens_c_verdict",
        sample_block,
        client,
    )
    verdict.lens_results.append(lens_c)
    if verbose:
        print(f"C:{lens_c.verdict}", end=" ", flush=True)

    verdict.total_cost_usd = sum(lr.est_cost_usd for lr in verdict.lens_results)
    return verdict


# ---------------------------------------------------------------- Opus-Synthese


def _format_verdict_for_synthesis(v: ScoutVerdict) -> str:
    """Format a single journal's lens results for the Opus synthesis prompt."""
    lines = [f"### {v.candidate.name}"]
    if v.probe.article_count:
        lines.append(f"Artikel (3 Jahre): {v.probe.article_count}")

    for lr in v.lens_results:
        if lr.lens == "thematisch":
            mc = lr.details.get("matching_count", "?")
            mt = lr.details.get("matching_titles", "")
            lines.append(f"\n**Linse A (Thematisch):** {lr.verdict} "
                         f"({mc} passende Titel: {mt})")
            lines.append(f"  {lr.reason_de}")

        elif lr.lens == "disziplinaer":
            beh = lr.details.get("beheimatungen", [])
            beh_str = ", ".join(
                f"{b['name']}: {b['fit']}" for b in beh if b.get("fit") != "kein_bezug"
            )
            lines.append(f"\n**Linse B (Disziplinär):** {beh_str or 'kein Bezug'}")
            lines.append(f"  {lr.reason_de}")

        elif lr.lens == "latent":
            topics = lr.details.get("topics_de", [])
            topics_str = ", ".join(topics) if topics else "—"
            lines.append(f"\n**Linse C (Latent):** {lr.verdict} → {topics_str}")
            lines.append(f"  {lr.reason_de}")

    return "\n".join(lines)


def synthesize_with_opus(
    verdicts: list[ScoutVerdict],
    client,
    verbose: bool = True,
) -> list[ScoutVerdict]:
    """Send all lens results to Opus for synthesis. Updates verdicts in-place."""
    from journal_bot.settings import DISCOURSE_SPACES
    cluster_list = ", ".join(DISCOURSE_SPACES.keys())

    journal_blocks = "\n\n".join(
        _format_verdict_for_synthesis(v)
        for v in verdicts
        if v.lens_results  # skip errored journals
    )

    system = f"""Du bist Forschungsberater für Benjamin Jörissen (FAU, Allgemeine Pädagogik).

Du bekommst für jede Kandidaten-Zeitschrift drei Bewertungs-Perspektiven:
- **Linse A** (Thematisch): Direkte Überlappung mit Benjamins Forschungsthemen
- **Linse B** (Disziplinär): Zugehörigkeit zu Benjamins diskursiven Beheimatungen
- **Linse C** (Latent): Periphere Diskurse die im Blickfeld bleiben sollten

Deine Aufgabe: Synthetisiere die drei Perspektiven. Das Interessante sind die SPANNUNGEN:
- Eine Zeitschrift kann thematisch marginal sein aber disziplinär zentral (z.B. ZfPäd)
- Eine Zeitschrift kann thematisch relevant sein aber disziplinär fremd
- Latente Relevanz kann den Ausschlag geben bei unklaren Fällen

Für jede Zeitschrift:
1. Kartiere die Spannungen zwischen den Linsen (2-4 Sätze)
2. Gib eine Empfehlung: "aufnehmen" / "beobachten" / "nicht_aufnehmen"
3. Schlage passende Diskursräume vor aus: {cluster_list}

Rufe das Tool `synthesis` auf — einmal pro Zeitschrift, in der Reihenfolge der Eingabe."""

    synthesis_tool = {
        "type": "function",
        "function": {
            "name": "synthesis",
            "description": "Synthese-Urteil für eine Zeitschrift.",
            "parameters": {
                "type": "object",
                "properties": {
                    "journal_name": {
                        "type": "string",
                        "description": "Name der Zeitschrift.",
                    },
                    "synthesis_de": {
                        "type": "string",
                        "description": (
                            "2-4 Sätze: Spannungen zwischen den Linsen, "
                            "was macht diese Zeitschrift interessant oder uninteressant?"
                        ),
                    },
                    "empfehlung": {
                        "type": "string",
                        "enum": ["aufnehmen", "beobachten", "nicht_aufnehmen"],
                        "description": (
                            "aufnehmen: aktiv tracken. beobachten: Watchlist belassen, "
                            "gelegentlich prüfen. nicht_aufnehmen: streichen."
                        ),
                    },
                    "suggested_clusters": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": f"Passende Diskursräume aus: {cluster_list}",
                    },
                },
                "required": ["journal_name", "synthesis_de", "empfehlung", "suggested_clusters"],
            },
        },
    }

    if verbose:
        print("[scout] Opus-Synthese...")

    try:
        resp = client.chat.completions.create(
            model=MODEL_AGENT,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": journal_blocks},
            ],
            tools=[synthesis_tool],
            temperature=0.3,
            max_tokens=16000,
        )
    except Exception as e:
        if verbose:
            print(f"Opus-Fehler: {e}")
        return verdicts

    usage = resp.usage
    opus_cost = 0.0
    if usage:
        opus_cost = (
            (usage.prompt_tokens / 1_000_000) * 10.00
            + (usage.completion_tokens / 1_000_000) * 50.00
        )
        if verbose:
            print(f"[scout] Opus: {usage.prompt_tokens} in, "
                  f"{usage.completion_tokens} out — ${opus_cost:.3f}")

    # Distribute Opus cost evenly across verdicts
    evaluable = [v for v in verdicts if v.lens_results]
    per_journal_opus = opus_cost / max(len(evaluable), 1)

    # Parse tool calls — Opus may call synthesis once per journal
    msg = resp.choices[0].message
    synthesis_results: list[dict] = []
    for tc in (msg.tool_calls or []):
        if tc.function.name == "synthesis":
            args = json.loads(tc.function.arguments)
            synthesis_results.append(args)

    def _normalize(s: str) -> str:
        """Strip punctuation, articles, and common prefixes for matching."""
        s = s.lower().strip()
        # Remove common prefixes like "Int J of", "Journal of", etc.
        for prefix in ("int j of ", "international journal of ",
                       "journal of ", "zeitschrift f. ", "zeitschrift für "):
            if s.startswith(prefix):
                s = s[len(prefix):]
        return re.sub(r"[^a-z0-9äöüß]+", " ", s).strip()

    # Build lookup from synthesis results
    syn_by_norm: dict[str, dict] = {}
    syn_by_words: list[tuple[set[str], dict]] = []
    for args in synthesis_results:
        name = args.get("journal_name", "")
        norm = _normalize(name)
        syn_by_norm[norm] = args
        syn_by_words.append((set(norm.split()), args))

    # Match synthesis results to verdicts (used set tracks consumed results)
    used: set[int] = set()

    def _find_match(candidate_name: str) -> dict | None:
        norm = _normalize(candidate_name)
        # 1. Exact normalized match
        if norm in syn_by_norm:
            return syn_by_norm[norm]
        # 2. Substring containment
        for sn, args in syn_by_norm.items():
            if sn in norm or norm in sn:
                return args
        # 3. Word-overlap match (≥60% of words shared both ways)
        norm_words = set(norm.split())
        best_score, best_args = 0.0, None
        for i, (sw, args) in enumerate(syn_by_words):
            if i in used:
                continue
            if not norm_words or not sw:
                continue
            overlap = len(norm_words & sw)
            score = overlap / max(len(norm_words), len(sw))
            if score > best_score and score >= 0.6:
                best_score = score
                best_args = args
        return best_args

    for v in verdicts:
        if not v.lens_results:
            continue
        syn = _find_match(v.candidate.name)
        # Mark as used to avoid double-matching
        if syn:
            norm_syn = _normalize(syn.get("journal_name", ""))
            for i, (sw, args) in enumerate(syn_by_words):
                if _normalize(args.get("journal_name", "")) == norm_syn:
                    used.add(i)
                    break
        if syn:
            v.synthesis_de = syn.get("synthesis_de", "")
            v.empfehlung = syn.get("empfehlung", "?")
            v.suggested_clusters = syn.get("suggested_clusters", [])
        else:
            v.empfehlung = "?"
            v.synthesis_de = "(Opus-Synthese nicht zugeordnet)"
        v.total_cost_usd += per_journal_opus

    return verdicts


# ---------------------------------------------------------------- Rendering


def render_markdown(
    verdicts: list[ScoutVerdict],
    window_years: int = 3,
    tracked_names: list[str] | None = None,
) -> str:
    this_year = datetime.now().year
    start_year = this_year - window_years + 1

    aufnehmen = [v for v in verdicts if v.empfehlung == "aufnehmen"]
    beobachten = [v for v in verdicts if v.empfehlung == "beobachten"]
    nicht = [v for v in verdicts if v.empfehlung == "nicht_aufnehmen"]
    skipped = [v for v in verdicts if v.empfehlung == "?"]

    total_cost = sum(v.total_cost_usd for v in verdicts)

    lines: list[str] = []
    lines.append("# Journal-Scout: Multi-Linsen-Evaluation")
    lines.append(f"_Datum: {date.today().isoformat()} · "
                 f"Fenster: {start_year}-{this_year} · "
                 f"Kosten: ${total_cost:.2f}_")
    lines.append("")
    n_tracked = len(tracked_names) if tracked_names else 0
    lines.append(f"**{len(aufnehmen)}** aufnehmen · "
                 f"**{len(beobachten)}** beobachten · "
                 f"**{len(nicht)}** nicht aufnehmen · "
                 f"**{len(skipped)}** übersprungen · "
                 f"**{n_tracked}** bereits getrackt")
    lines.append("")
    lines.append("_Linsen: A=Thematische Passung, B=Disziplinäre Beheimatung, "
                 "C=Latente Relevanz_")
    lines.append("")

    def _render_journal(v: ScoutVerdict) -> None:
        c = v.candidate
        clusters = ", ".join(v.suggested_clusters) if v.suggested_clusters else "—"
        art_count = v.probe.article_count if v.probe else 0
        lines.append(f"### {c.name}")
        if c.issn or v.probe.issn_resolved:
            lines.append(f"ISSN: {v.probe.issn_resolved or c.issn}")
        lines.append(f"Artikel ({start_year}-{this_year}): {art_count}")
        lines.append(f"Diskursräume: {clusters}")
        lines.append("")

        # Lens verdicts compact
        for lr in v.lens_results:
            if lr.lens == "thematisch":
                mc = lr.details.get("matching_count", "?")
                lines.append(f"**A (Thematisch):** {lr.verdict} "
                             f"({mc} Treffer) — {lr.reason_de}")
            elif lr.lens == "disziplinaer":
                beh = lr.details.get("beheimatungen", [])
                relevant_beh = [b for b in beh if b.get("fit") != "kein_bezug"]
                beh_str = ", ".join(
                    f"{b['name']}: **{b['fit']}**" for b in relevant_beh
                ) or "kein Bezug"
                lines.append(f"**B (Disziplinär):** {beh_str}")
                lines.append(f"  {lr.reason_de}")
            elif lr.lens == "latent":
                topics = lr.details.get("topics_de", [])
                topics_str = ", ".join(topics) if topics else "—"
                lines.append(f"**C (Latent):** {lr.verdict} → {topics_str}")
                lines.append(f"  {lr.reason_de}")

        lines.append("")
        if v.synthesis_de:
            lines.append(f"> **Synthese:** {v.synthesis_de}")
        lines.append("")

    def _section(title: str, items: list[ScoutVerdict]) -> None:
        if not items:
            return
        lines.append(f"## {title}")
        lines.append("")
        for v in items:
            _render_journal(v)
        lines.append("")

    _section("Aufnehmen", aufnehmen)
    _section("Beobachten", beobachten)
    _section("Nicht aufnehmen", nicht)

    if skipped:
        lines.append("## Übersprungen")
        lines.append("")
        for v in skipped:
            lines.append(f"- **{v.candidate.name}**: {v.synthesis_de or '?'}")
        lines.append("")

    if tracked_names:
        lines.append("## Bereits getrackt")
        lines.append("")
        for name in sorted(tracked_names):
            lines.append(f"- {name}")
        lines.append("")

    lines.append("---")
    lines.append(f"_Kosten: ${total_cost:.2f} (3× Haiku + Opus-Synthese)_")
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
    candidates, tracked_names = parse_watchlist(watchlist)
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

    # 4. Multi-lens LLM evaluation (3× Haiku per journal)
    evaluable = [p for p in probes if not p.error and p.sample_titles]
    skipped_probes = [p for p in probes if p.error or not p.sample_titles]
    if verbose:
        n_skip = len(skipped_probes)
        print(f"\n[scout] Multi-Linsen-Evaluation für {len(evaluable)} Journals "
              f"({n_skip} übersprungen)...")
        if skipped_probes:
            # Group by reason
            issn_fail = [p for p in skipped_probes if p.error and "ISSN" in p.error]
            no_articles = [p for p in skipped_probes if not p.error and not p.sample_titles]
            not_indexed = [p for p in skipped_probes if p.error and "nicht in OpenAlex" in p.error]
            other = [p for p in skipped_probes
                     if p not in issn_fail and p not in no_articles and p not in not_indexed]
            if issn_fail:
                print(f"[scout]   ISSN nicht aufgelöst ({len(issn_fail)}): "
                      f"{', '.join(p.candidate.name for p in issn_fail)}")
            if no_articles:
                print(f"[scout]   Keine Artikel ({len(no_articles)}): "
                      f"{', '.join(p.candidate.name for p in no_articles)}")
            if not_indexed:
                print(f"[scout]   Nicht in OpenAlex ({len(not_indexed)}): "
                      f"{', '.join(p.candidate.name for p in not_indexed)}")
            if other:
                print(f"[scout]   Sonstige ({len(other)}): "
                      f"{', '.join(p.candidate.name for p in other)}")

    client = build_client()
    verdicts: list[ScoutVerdict] = []

    # Add skipped ones first
    for p in probes:
        if p.error or not p.sample_titles:
            verdicts.append(ScoutVerdict(
                candidate=p.candidate, probe=p,
                empfehlung="?",
                synthesis_de=p.error or "Keine Artikel gefunden",
            ))

    for i, p in enumerate(evaluable):
        if verbose:
            print(f"[scout]   {i+1}/{len(evaluable)} {p.candidate.name}: ", end="", flush=True)
        v = evaluate_journal_multilens(p, profile_block, client, verbose)
        verdicts.append(v)
        if verbose:
            print(f" ${v.total_cost_usd:.3f}")

    # 5. Opus synthesis (batched)
    evaluable_verdicts = [v for v in verdicts if v.lens_results]
    if evaluable_verdicts:
        verdicts_for_synthesis = synthesize_with_opus(
            evaluable_verdicts, client, verbose,
        )

    # Sort by empfehlung
    order = {"aufnehmen": 0, "beobachten": 1, "nicht_aufnehmen": 2, "?": 3}
    verdicts.sort(key=lambda v: order.get(v.empfehlung, 9))

    total_cost = sum(v.total_cost_usd for v in verdicts)

    # 6. Output
    md = render_markdown(verdicts, window_years, tracked_names=tracked_names)

    trends_dir = out_dir / "trends"
    trends_dir.mkdir(parents=True, exist_ok=True)
    filename = f"scout_{date.today().isoformat()}.md"
    out_path = trends_dir / filename
    out_path.write_text(md, encoding="utf-8")

    if verbose:
        print(f"\n[scout] Geschrieben: {out_path}")
        print(f"[scout] Kosten: ${total_cost:.2f}")
        a = sum(1 for v in verdicts if v.empfehlung == "aufnehmen")
        b = sum(1 for v in verdicts if v.empfehlung == "beobachten")
        n = sum(1 for v in verdicts if v.empfehlung == "nicht_aufnehmen")
        print(f"[scout] Ergebnis: {a} aufnehmen, {b} beobachten, {n} nicht aufnehmen")

    return {
        "status": "ok",
        "path": str(out_path),
        "total_cost_usd": total_cost,
        "aufnehmen": sum(1 for v in verdicts if v.empfehlung == "aufnehmen"),
        "beobachten": sum(1 for v in verdicts if v.empfehlung == "beobachten"),
        "nicht_aufnehmen": sum(1 for v in verdicts if v.empfehlung == "nicht_aufnehmen"),
        "skipped": sum(1 for v in verdicts if v.empfehlung == "?"),
    }
