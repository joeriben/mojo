"""Citation-Tracker.

Prüft, ob ein neuer Beitrag (via Crossref-Refs) Publikationen aus der
konfigurierten Zotero-Collection (ZOTERO_COLLECTION) zitiert.

Matching-Strategien (in Reihenfolge abnehmender Zuverlässigkeit):
  1. DOI-exact match: höchste Zuverlässigkeit
  2. Researcher last name (from RESEARCHER_NAME) + year in raw reference string
  3. Researcher last name without year (fallback, lower confidence)

Arbeitet gegen authored_all aus corpus.json (alle Publikationen, auch prä-2018).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

from journal_bot.settings import CORPUS_JSON, RESEARCHER_NAME


YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def _parse_researcher_name(name: str) -> tuple[str, str, str]:
    """Parse 'Firstname Lastname' → (first_name, last_name, initial)."""
    parts = name.strip().split()
    first = parts[0] if len(parts) >= 2 else ""
    last = parts[-1] if parts else "UNKNOWN"
    return first, last, first[0].upper() if first else ""


def _build_name_patterns(first: str, last: str) -> list[re.Pattern]:
    """Build the 4 canonical name patterns as regexes.

    Matches exactly:  Firstname Lastname | F. Lastname | Lastname, Firstname | Lastname, F.
    """
    ln = last.replace("ö", "[oö]").replace("ä", "[aä]").replace("ü", "[uü]")
    fn = re.escape(first)
    ini = re.escape(first[0]) if first else "[A-Z]"
    return [
        re.compile(fn + r"\s+" + ln, re.IGNORECASE),           # Firstname Lastname
        re.compile(ini + r"\.\s*" + ln, re.IGNORECASE),        # F. Lastname
        re.compile(ln + r",\s*" + fn, re.IGNORECASE),          # Lastname, Firstname
        re.compile(ln + r",\s*" + ini + r"\.", re.IGNORECASE), # Lastname, F.
    ]


def _build_wrong_name_re(last: str) -> re.Pattern:
    """Matches any name-like token adjacent to last name — used to detect namesakes.

    Catches: X. Lastname, Lastname, X., Firstname Lastname, Lastname, Firstname
    """
    ln = last.replace("ö", "[oö]").replace("ä", "[aä]").replace("ü", "[uü]")
    pat = (
        r"(?:[A-Z][a-zà-ÿ]*\.?\s+" + ln
        + r"|" + ln + r",?\s*[A-Z][a-zà-ÿ]*)"
    )
    return re.compile(pat, re.IGNORECASE)


def _text_is_researcher_citation(ref: dict, right_patterns: list[re.Pattern],
                                  wrong_re: re.Pattern, last_name_re: re.Pattern) -> str:
    """Check if reference cites the researcher, not a namesake.

    Returns one of: "strong" | "weak" | "reject".

    Logic:
    1. Last name must appear in the text                       → else "reject"
    2. If any of the 4 canonical name forms match              → "strong"
    3. If last name appears with a different initial / first   → "reject"
    4. Last name alone (no initial / no first name nearby)     → "weak"
       (caller must downgrade confidence — last name alone is unsafe for
       common names like "Smith" or "Müller", which becomes a real risk
       once MOJO ships beyond the original user.)
    """
    blob = " ".join([
        ref.get("raw", "") or "",
        " ".join(ref.get("authors", []) or []),
    ])
    if not last_name_re.search(blob):
        return "reject"

    # Check if any canonical form matches → definite yes
    for pat in right_patterns:
        if pat.search(blob):
            return "strong"

    # Check if a wrong-initial form exists → definite no
    if wrong_re.search(blob):
        return "reject"

    # Last name alone, no initial → ambiguous, downgrade to weak
    return "weak"


# Stopwörter für die Titel-Disambiguierung (DE + EN)
_STOP = {
    "und", "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer",
    "einen", "einem", "mit", "von", "zur", "zum", "als", "auf", "aus", "für",
    "gegen", "ohne", "über", "unter", "vor", "nach", "bei", "ist", "sind",
    "wird", "werden", "kann", "soll", "muss", "nicht", "auch", "noch",
    "eine", "einen",
    "the", "and", "for", "with", "from", "into", "onto", "over", "under",
    "between", "of", "on", "in", "to", "at", "by", "as", "is", "are", "was",
    "were", "be", "been", "has", "have", "had", "do", "does", "did", "a",
    "an", "its", "it", "this", "that", "these", "those",
}


def _title_words(title: str) -> set[str]:
    """Distinktive Wörter aus einem Titel (lowercase, ≥4 Zeichen, keine Stopwörter)."""
    words = re.findall(r"\w{4,}", (title or "").lower())
    return {w for w in words if w not in _STOP}


@dataclass
class CitationHit:
    match_type: str            # "doi" | "author_year" | "author_only"
    confidence: str            # "high" | "medium" | "low"
    pub_id: str | None         # matched researcher publication key, or None
    pub_title: str             # Titel der gematchten Publikation
    pub_year: int | None
    pub_authors: list[str]
    ref_raw: str               # die Rohzeile aus Crossref
    ref_doi: str               # der in der Ref angegebene DOI, falls vorhanden


def _normalize_doi(doi: str) -> str:
    return (doi or "").strip().lower().rstrip(".")


def _year_from_ref(ref: dict) -> int | None:
    y = ref.get("year") or ""
    if y and str(y).strip().isdigit():
        return int(str(y).strip()[:4])
    m = YEAR_RE.search(ref.get("raw", "") or "")
    return int(m.group(0)) if m else None


def find_citations(
    references: list[dict],
    authored_all: list[dict],
) -> list[CitationHit]:
    """references: Liste von dicts wie in enrichment.references_crossref.
    authored_all: Liste der Forscher-Publikationen (aus corpus.json['authored_all']).
    """
    if not references or not authored_all:
        return []

    # Build researcher name matcher
    first_name, last_name, initial = _parse_researcher_name(RESEARCHER_NAME)
    ln_pattern = last_name.replace("ö", "[oö]").replace("ä", "[aä]").replace("ü", "[uü]")
    last_name_re = re.compile(ln_pattern, re.IGNORECASE)
    right_patterns = _build_name_patterns(first_name, last_name)
    wrong_re = _build_wrong_name_re(last_name)

    # Index: DOI → Publikation
    by_doi: dict[str, dict] = {}
    for p in authored_all:
        d = _normalize_doi(p.get("doi", ""))
        if d:
            by_doi[d] = p

    # Index: Jahr → Liste Publikationen (für author_year-Match)
    by_year: dict[int, list[dict]] = {}
    for p in authored_all:
        y = p.get("year")
        if isinstance(y, int):
            by_year.setdefault(y, []).append(p)

    hits_by_key: dict[str, CitationHit] = {}

    def add(hit: CitationHit) -> None:
        """Dedup mit 'replace on upgrade': höhere Confidence ersetzt niedrigere."""
        key = hit.pub_id or f"raw:{hit.ref_raw[:80]}"
        existing = hits_by_key.get(key)
        if existing is None or CONFIDENCE_RANK[hit.confidence] > CONFIDENCE_RANK[existing.confidence]:
            hits_by_key[key] = hit

    def _mk_hit(pub: dict, *, match_type: str, confidence: str, ref: dict) -> CitationHit:
        return CitationHit(
            match_type=match_type,
            confidence=confidence,
            pub_id=pub.get("pub_id"),
            pub_title=pub.get("title", ""),
            pub_year=pub.get("year"),
            pub_authors=pub.get("authors", []),
            ref_raw=ref.get("raw", "") or "",
            ref_doi=_normalize_doi(ref.get("doi", "")),
        )

    for ref in references:
        ref_doi = _normalize_doi(ref.get("doi", ""))
        ref_raw_lower = (ref.get("raw", "") or "").lower()

        # --- 1. DOI-exact match (höchste Confidence) ---
        if ref_doi and ref_doi in by_doi:
            add(_mk_hit(by_doi[ref_doi], match_type="doi", confidence="high", ref=ref))
            continue

        # --- 2. Researcher name mention + year ---
        name_match = _text_is_researcher_citation(
            ref, right_patterns, wrong_re, last_name_re,
        )
        if name_match == "reject":
            continue

        year = _year_from_ref(ref)
        if year is None or year not in by_year:
            # Researcher name found but no year → low confidence, no pub_id
            add(CitationHit(
                match_type="author_only",
                confidence="low",
                pub_id=None,
                pub_title="",
                pub_year=year,
                pub_authors=[],
                ref_raw=ref.get("raw", "") or "",
                ref_doi=ref_doi,
            ))
            continue

        candidates = by_year[year]

        # If only the last name was found (no initial / first name nearby),
        # cap confidence at "low" regardless of year/title evidence — this
        # is the namesake-protection layer.
        weak_match = name_match == "weak"

        def _cap(level: str) -> str:
            if not weak_match:
                return level
            return "low" if level in ("high", "medium") else level

        # --- 2a. Title disambiguation: distinctive words from candidate titles
        #         matched against the raw text ---
        scored: list[tuple[int, dict]] = []
        for pub in candidates:
            pub_words = _title_words(pub.get("title", ""))
            if not pub_words:
                continue
            overlap = sum(1 for w in pub_words if w in ref_raw_lower)
            if overlap >= 2:
                scored.append((overlap, pub))

        if scored:
            # Take only the best-scoring candidate(s) (same top score)
            scored.sort(key=lambda x: x[0], reverse=True)
            top_score = scored[0][0]
            winners = [p for s, p in scored if s == top_score]
            if len(winners) == 1:
                add(_mk_hit(winners[0], match_type="author_year_title",
                            confidence=_cap("high"), ref=ref))
            else:
                for pub in winners:
                    add(_mk_hit(pub, match_type="author_year_title",
                                confidence=_cap("medium"), ref=ref))
            continue

        # --- 2b. No title overlap: researcher name + year only ---
        if len(candidates) == 1:
            add(_mk_hit(candidates[0], match_type="author_year",
                        confidence=_cap("high"), ref=ref))
        else:
            # ambiguous — all candidates with medium confidence (agent decides)
            for pub in candidates:
                add(_mk_hit(pub, match_type="author_year",
                            confidence=_cap("medium"), ref=ref))

    return list(hits_by_key.values())


def load_authored_all(corpus_path: Path = CORPUS_JSON) -> list[dict]:
    data = json.loads(corpus_path.read_text(encoding="utf-8"))
    return data.get("authored_all", [])


def format_for_agent(hits: list[CitationHit]) -> str:
    """Formatiert Treffer für den Agent-User-Prompt. Leerstring, wenn keine Treffer."""
    if not hits:
        return ""
    lines = ["", "=== ZITATIONSTREFFER ===",
             "Der neue Beitrag zitiert im Literaturverzeichnis Publikationen aus",
             "dem Werk des/der Forscher*in. Dies ist ein **sehr starkes Relevanzsignal** — jemand",
             "setzt sich mit diesen Arbeiten explizit auseinander.", ""]
    high = [h for h in hits if h.confidence == "high"]
    med = [h for h in hits if h.confidence == "medium"]
    low = [h for h in hits if h.confidence == "low"]

    if high:
        lines.append(f"Sichere Treffer ({len(high)}):")
        for h in high:
            authors = ", ".join(h.pub_authors[:2])
            lines.append(
                f"  · pub_id={h.pub_id}  [{h.pub_year}]  {authors} — {h.pub_title[:100]}"
            )
            if h.ref_raw:
                lines.append(f"    Ref-Zeile: {h.ref_raw[:180]}")
        lines.append("")
    if med:
        lines.append(f"Wahrscheinliche Treffer ({len(med)}, Jahr mehrdeutig):")
        for h in med:
            authors = ", ".join(h.pub_authors[:2])
            lines.append(
                f"  · pub_id={h.pub_id}  [{h.pub_year}]  {authors} — {h.pub_title[:100]}"
            )
        lines.append("")
    if low:
        lines.append(f"Unspezifische Namens-Erwähnungen ({len(low)}, Jahr fehlt/unklar):")
        for h in low:
            lines.append(f"  · {h.ref_raw[:180]}")
        lines.append("")
    lines.append("Wenn Du eine dieser Publikationen im Digest zitierst, kannst Du Dich")
    lines.append("darauf berufen — prüfe aber im Volltext der Publikation, WAS der neue")
    lines.append("Beitrag aus ihr aufnimmt.")
    return "\n".join(lines)
