"""Deterministic relevance signals — zero LLM cost.

Computes a signal profile for each article using already-stored metadata:
  a) cites_researcher — article cites the researcher's publications (via citation_tracker)
  b) zotero_overlap   — article refs cite items from the researcher's Zotero library (by title)
  c) keyword_hits     — article title contains key terms from the researcher's summaries

All signals operate on data already present in articles.db + summaries.json + zotero_library.json.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from journal_bot.citation_tracker import find_citations, CitationHit, load_authored_all
from journal_bot.settings import CORPUS_JSON, SUMMARIES_JSON, PROJECT_ROOT


ZOTERO_LIBRARY_JSON = PROJECT_ROOT / "zotero_library.json"

# Stopwords for title-word extraction (DE + EN), shared with citation_tracker
_STOP = {
    "und", "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer",
    "einen", "einem", "mit", "von", "zur", "zum", "als", "auf", "aus", "für",
    "gegen", "ohne", "über", "unter", "vor", "nach", "bei", "ist", "sind",
    "wird", "werden", "kann", "nicht", "auch", "noch",
    "the", "and", "for", "with", "from", "into", "onto", "over", "under",
    "between", "of", "on", "in", "to", "at", "by", "as", "is", "are", "was",
    "were", "be", "been", "has", "have", "had", "do", "does", "did", "a",
    "an", "its", "it", "this", "that", "these", "those", "their", "than",
    "about", "some", "what", "which", "when", "where", "how", "who", "new",
    "case", "study", "analysis", "approach", "toward", "towards", "through",
    "based", "using", "between", "review", "introduction", "special", "issue",
}


def _title_words(title: str) -> set[str]:
    """Distinctive words from a title (lowercase, ≥4 chars, no stopwords)."""
    words = re.findall(r"\w{4,}", (title or "").lower())
    return {w for w in words if w not in _STOP}


# ------------------------------------------------------------------ Cleanup --


def _extract_items_from_xml(raw: str) -> list[str]:
    """Split '<item>A</item>\n<item>B</item>' blocks into ['A', 'B']."""
    if "<item>" not in raw:
        return [raw]
    return re.findall(r"<item>(.*?)</item>", raw, re.DOTALL)


def load_key_terms(summaries_path: Path = SUMMARIES_JSON) -> set[str]:
    """Load and clean key_terms from summaries.json."""
    data = json.loads(summaries_path.read_text(encoding="utf-8"))
    terms: set[str] = set()
    stopwords = {
        "bildung", "erziehung", "pädagogik", "education", "forschung",
        "research", "methoden", "theorie", "praxis", "kultur", "culture",
        "gesellschaft", "digitalisierung", "schule", "lernen",
    }
    for pub in data["summaries"].values():
        for entry in (pub.get("key_terms") or []):
            for item in _extract_items_from_xml(entry):
                sub_items = re.split(r"\n\s*-\s+", item) if "\n" in item else [item]
                for sub in sub_items:
                    t = sub.strip().lstrip("- ").strip().lower()
                    if len(t) >= 5 and t not in stopwords and "<" not in t:
                        terms.add(t)
    return terms


# ----------------------------------------------------- Zotero Library Index --


@dataclass
class ZoteroItem:
    key: str
    title: str
    doi: str
    title_words: set[str]


def load_zotero_library(path: Path = ZOTERO_LIBRARY_JSON) -> list[ZoteroItem]:
    """Load Zotero library export and build title-word index."""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    items = []
    for entry in data.get("items", []):
        title = entry.get("title", "")
        tw = _title_words(title)
        if len(tw) >= 2:  # skip items with fewer than 2 distinctive words
            items.append(ZoteroItem(
                key=entry.get("key", ""),
                title=title,
                doi=(entry.get("doi") or "").strip().lower().rstrip("."),
                title_words=tw,
            ))
    return items


def _build_zotero_doi_index(library: list[ZoteroItem]) -> dict[str, ZoteroItem]:
    """DOI → ZoteroItem for fast exact matching."""
    return {it.doi: it for it in library if it.doi}


def _build_zotero_word_index(library: list[ZoteroItem]) -> dict[str, list[ZoteroItem]]:
    """Inverted index: word → list of ZoteroItems containing that word."""
    idx: dict[str, list[ZoteroItem]] = {}
    for it in library:
        for w in it.title_words:
            idx.setdefault(w, []).append(it)
    return idx


# ----------------------------------------------------------------- Signals --


@dataclass
class SignalProfile:
    """Deterministic relevance signals for one article."""
    article_id: str
    cites_researcher: list[dict] = field(default_factory=list)
    zotero_overlap: list[str] = field(default_factory=list)  # matched Zotero titles
    keyword_hits: list[str] = field(default_factory=list)

    @property
    def has_any_signal(self) -> bool:
        return bool(self.cites_researcher or self.zotero_overlap or self.keyword_hits)

    @property
    def signal_count(self) -> int:
        return sum([
            bool(self.cites_researcher),
            bool(self.zotero_overlap),
            bool(self.keyword_hits),
        ])

    @property
    def summary(self) -> str:
        parts = []
        if self.cites_researcher:
            parts.append(f"cites_researcher({len(self.cites_researcher)})")
        if self.zotero_overlap:
            n = len(self.zotero_overlap)
            sample = "; ".join(self.zotero_overlap[:3])
            parts.append(f"zotero({n}: {sample})")
        if self.keyword_hits:
            parts.append(f"keywords({','.join(self.keyword_hits[:5])})")
        return " | ".join(parts) if parts else "(no signals)"

    def to_dict(self) -> dict:
        return asdict(self)


def signal_cites_researcher(
    crossref_refs: list[dict],
    authored_all: list[dict] | None = None,
) -> list[dict]:
    """Signal a: Does this article cite the researcher's publications?"""
    if authored_all is None:
        authored_all = load_authored_all()
    hits = find_citations(crossref_refs, authored_all)
    return [asdict(h) for h in hits]


def signal_zotero_overlap(
    crossref_refs: list[dict],
    zotero_doi_index: dict[str, ZoteroItem] | None = None,
    zotero_word_index: dict[str, list[ZoteroItem]] | None = None,
    min_word_overlap: int = 3,
) -> list[str]:
    """Signal b: Which refs cite works from the researcher's Zotero library?

    Matching strategy:
      1. DOI exact match (if ref has DOI and it's in Zotero)
      2. Title-word overlap: ≥min_word_overlap distinctive words in common

    Returns list of matched Zotero item titles (deduplicated).
    """
    if not crossref_refs or zotero_word_index is None:
        return []

    matched_keys: set[str] = set()
    matched_titles: list[str] = []

    for ref in crossref_refs:
        # Strategy 1: DOI exact match
        ref_doi = (ref.get("doi") or "").strip().lower().rstrip(".")
        if ref_doi and zotero_doi_index and ref_doi in zotero_doi_index:
            zit = zotero_doi_index[ref_doi]
            if zit.key not in matched_keys:
                matched_keys.add(zit.key)
                matched_titles.append(zit.title)
            continue

        # Strategy 2: Title-word overlap against ref raw string
        ref_raw = (ref.get("raw") or "").strip()
        if not ref_raw:
            continue
        ref_words = _title_words(ref_raw)
        if len(ref_words) < min_word_overlap:
            continue

        # Find candidate Zotero items via inverted index
        candidate_scores: dict[str, int] = {}
        for w in ref_words:
            for zit in (zotero_word_index.get(w) or []):
                if zit.key not in matched_keys:
                    candidate_scores[zit.key] = candidate_scores.get(zit.key, 0) + 1

        # Accept candidates with sufficient overlap
        for zkey, score in candidate_scores.items():
            if score >= min_word_overlap:
                matched_keys.add(zkey)
                # Find title for this key
                for zit in (zotero_word_index.get(list(ref_words)[0]) or []):
                    if zit.key == zkey:
                        matched_titles.append(zit.title)
                        break

    return matched_titles


def signal_keyword_hits(
    title: str,
    key_terms: set[str] | None = None,
) -> list[str]:
    """Signal c: Which of the researcher's key terms appear in the article title?"""
    if key_terms is None:
        key_terms = load_key_terms()
    title_lower = (title or "").lower()
    if not title_lower:
        return []
    return [t for t in sorted(key_terms) if t in title_lower]


# --------------------------------------------------------- Composite Score --


def compute_signals(
    article_id: str,
    title: str,
    crossref_refs_json: str | list | None,
    *,
    authored_all: list[dict] | None = None,
    key_terms: set[str] | None = None,
    zotero_doi_index: dict[str, ZoteroItem] | None = None,
    zotero_word_index: dict[str, list[ZoteroItem]] | None = None,
) -> SignalProfile:
    """Compute all deterministic signals for one article."""
    refs: list[dict] = []
    if isinstance(crossref_refs_json, str) and crossref_refs_json:
        try:
            refs = json.loads(crossref_refs_json)
        except json.JSONDecodeError:
            pass
    elif isinstance(crossref_refs_json, list):
        refs = crossref_refs_json

    return SignalProfile(
        article_id=article_id,
        cites_researcher=signal_cites_researcher(refs, authored_all),
        zotero_overlap=signal_zotero_overlap(
            refs, zotero_doi_index, zotero_word_index,
        ),
        keyword_hits=signal_keyword_hits(title, key_terms),
    )


# ---------------------------------------------------------- Batch Helpers --


def load_signal_resources(
    summaries_path: Path = SUMMARIES_JSON,
    corpus_path: Path = CORPUS_JSON,
    zotero_path: Path = ZOTERO_LIBRARY_JSON,
) -> dict[str, Any]:
    """Pre-load all resources needed for batch signal computation."""
    zotero_lib = load_zotero_library(zotero_path)
    return {
        "authored_all": load_authored_all(corpus_path),
        "key_terms": load_key_terms(summaries_path),
        "zotero_doi_index": _build_zotero_doi_index(zotero_lib),
        "zotero_word_index": _build_zotero_word_index(zotero_lib),
    }
