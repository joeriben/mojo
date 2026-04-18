"""Deterministic relevance signals and attention metadata — zero LLM cost.

Computes a signal profile for each article using already-stored metadata:
  a) cites_researcher — article cites the researcher's publications (via citation_tracker)
  b) zotero_overlap   — article refs cite items from the researcher's Zotero library (by title)
  c) keyword_hits     — article title contains key terms from the researcher's summaries

All signals operate on data already present in articles.db + summaries.json + projects.json
+ zotero_library.json.
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
PROJECTS_JSON = PROJECT_ROOT / "projects.json"
TRIGGER_AUTHORS = ("macgilchrist", "jarke", "wendy chun", "wendy hui kyong")
SELECTION_MODES = {
    "none", "screening", "similarity", "complementarity", "citation", "trigger", "mixed",
}
DISCOURSE_INDICATORS = {
    "kein_indikator", "schwacher_indikator", "starker_indikator",
}

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
    "digital", "cultural", "education", "educational", "research", "teacher",
    "teachers", "learning", "school", "schools", "project", "projects",
}

_PROJECT_SIGNAL_KEYWORDS = {
    "cultural_resilience": [
        "resilience", "anthropocene", "planetary", "mourning", "grief",
        "multispecies", "plant ethics", "care ethics", "rootedness",
        "resourcefulness", "futurability", "post-anthropocentric",
        "posthuman", "relational ontology", "agential realism",
    ],
    "metakubi": [
        "transformation", "morphogenesis", "metamorphosis", "transgression",
        "meta-analysis", "systematic review", "bibliometric",
        "discourse-analytical", "school development", "schulkultur",
        "cultural education",
    ],
    "ai4artsed": [
        "generative ai", "chatgpt", "llm", "diffusion", "clip", "bias",
        "decolonial", "indigenous", "co-creation", "ai literacy",
        "prompt engineering", "embedding space",
    ],
    "comearts": [
        "teacher professional development", "music education", "arts education",
        "community networks", "post-digital youth", "cross-aesthetic",
        "diversity-sensitive", "teacher training",
    ],
    "diaes_kubi": [
        "digital-aesthetic sovereignty", "aesthetic agency", "digital contexts",
        "teacher competencies", "post-digital aesthetics",
        "global citizenship", "cultural resilience",
    ],
}


def _title_words(title: str) -> set[str]:
    """Distinctive words from a title (lowercase, ≥4 chars, no stopwords)."""
    words = re.findall(r"\w{4,}", (title or "").lower())
    return {w for w in words if w not in _STOP}


def _text_words(text: str) -> set[str]:
    """Distinctive words from free text (lowercase, ≥4 chars, no stopwords)."""
    words = re.findall(r"[\w-]{4,}", (text or "").lower())
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


@dataclass
class AttentionProfile:
    """How and why an article should surface in the attention system."""
    selection_mode: str = ""
    discourse_indicator: str = ""
    signal_group: str = ""
    project_hits: list[str] = field(default_factory=list)
    deterministic_signals: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
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


def _load_active_projects(path: Path = PROJECTS_JSON) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [p for p in data.get("projects", []) if p.get("status") == "active"]


def _project_match_score(project: dict[str, Any], text_blob: str, text_words: set[str]) -> int:
    score = 0
    for phrase in _PROJECT_SIGNAL_KEYWORDS.get(project.get("key", ""), []):
        if phrase.lower() in text_blob:
            score += 2 if " " in phrase else 1

    project_text = " ".join(
        [
            project.get("name", ""),
            project.get("description", ""),
            " ".join(project.get("relevance_shifts", [])),
        ]
    )
    overlap = text_words & _text_words(project_text)
    score += min(len(overlap), 4)
    return score


def detect_project_hits(text_blob: str) -> list[str]:
    """Match an article blob against active project/problem fields."""
    blob = (text_blob or "").lower()
    words = _text_words(blob)
    hits: list[tuple[int, str]] = []
    for project in _load_active_projects():
        score = _project_match_score(project, blob, words)
        if score >= 2:
            hits.append((score, project["key"]))
    hits.sort(key=lambda item: (-item[0], item[1]))
    return [key for _, key in hits[:2]]


def _infer_selection_mode(
    *,
    explicit: str,
    signal_profile: SignalProfile,
    trigger_author_hit: bool,
    project_hits: list[str],
    bezuege: list[dict],
    verdict: str,
    discourse_indicator: str,
) -> str:
    if explicit in SELECTION_MODES:
        return explicit
    if signal_profile.cites_researcher:
        return "citation"
    if trigger_author_hit:
        return "trigger"
    if project_hits and bezuege and discourse_indicator != "kein_indikator":
        return "mixed"
    if project_hits and discourse_indicator != "kein_indikator":
        return "complementarity"
    if bezuege or signal_profile.zotero_overlap or signal_profile.keyword_hits:
        return "similarity"
    if verdict:
        return "screening"
    return "none"


def _infer_discourse_indicator(
    *,
    explicit: str,
    verdict: str,
    bemerkenswert: list[str],
    project_hits: list[str],
    signal_profile: SignalProfile,
) -> str:
    if explicit in DISCOURSE_INDICATORS:
        return explicit
    if verdict in {"pflichtlektuere", "lesenswert"}:
        return "starker_indikator"
    if verdict == "scannen" and project_hits and (bemerkenswert or signal_profile.signal_count > 0):
        return "starker_indikator"
    if verdict == "scannen" and project_hits:
        return "schwacher_indikator"
    if verdict == "ignorieren" and project_hits and (bemerkenswert or signal_profile.signal_count > 1):
        return "schwacher_indikator"
    if bemerkenswert or signal_profile.signal_count > 0 or verdict == "scannen":
        return "schwacher_indikator"
    return "kein_indikator"


def derive_attention_profile(
    *,
    article_id: str,
    title: str,
    authors: list[str],
    abstract: str = "",
    openalex_abstract: str = "",
    crossref_refs: list[dict] | None = None,
    entry: dict[str, Any] | None = None,
    signal_resources: dict[str, Any] | None = None,
) -> AttentionProfile:
    """Derive attention metadata from existing article + agent data."""
    entry = entry or {}
    signal_resources = signal_resources or load_signal_resources()
    signal_profile = compute_signals(
        article_id,
        title,
        crossref_refs or [],
        **signal_resources,
    )

    bemerkenswert = entry.get("bemerkenswert") or []
    bezuege = entry.get("bezuege") or []
    text_blob = "\n".join(
        [
            title or "",
            abstract or "",
            openalex_abstract or "",
            entry.get("kernthese", "") or "",
            entry.get("verdict_begruendung", "") or "",
            entry.get("theoretisch_methodisch", "") or "",
            "\n".join(bemerkenswert),
        ]
    ).lower()
    project_hits = detect_project_hits(text_blob)
    trigger_author_hit = any(
        trigger in " ".join(authors).lower() for trigger in TRIGGER_AUTHORS
    )

    discourse_indicator = _infer_discourse_indicator(
        explicit=entry.get("discourse_indicator", ""),
        verdict=entry.get("verdict", ""),
        bemerkenswert=bemerkenswert,
        project_hits=project_hits,
        signal_profile=signal_profile,
    )
    selection_mode = _infer_selection_mode(
        explicit=entry.get("selection_mode", ""),
        signal_profile=signal_profile,
        trigger_author_hit=trigger_author_hit,
        project_hits=project_hits,
        bezuege=bezuege,
        verdict=entry.get("verdict", ""),
        discourse_indicator=discourse_indicator,
    )
    signal_group = ""
    if discourse_indicator != "kein_indikator":
        signal_group = entry.get("signal_group", "") or (project_hits[0] if project_hits else "")

    return AttentionProfile(
        selection_mode=selection_mode,
        discourse_indicator=discourse_indicator,
        signal_group=signal_group,
        project_hits=project_hits,
        deterministic_signals=signal_profile.to_dict(),
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
