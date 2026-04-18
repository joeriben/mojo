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
from collections import Counter, defaultdict
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

_SUBGROUP_SEEDS = {
    "ai4artsed": {
        "critical_ai_literacy": [
            "ai literacy", "critical ai", "critical literacy", "media literacy",
            "literacy scale", "assessment", "competence", "instrumental",
        ],
        "bias_decoloniality": [
            "bias", "decolonial", "indigenous", "hegemony",
            "western", "training data", "cultural production",
        ],
        "generative_co_creation": [
            "generative ai", "chatgpt", "co-creation", "creative ai",
            "artistic expression", "human-ai", "diffusion", "clip",
        ],
        "prompting_as_pedagogy": [
            "prompting", "prompt engineering", "prompt design",
            "pedagogical practice", "classroom use",
        ],
        "arts_music_teacher_ed": [
            "arts education", "music education", "art education",
            "arts teacher", "music teacher", "arts-based",
            "aesthetic education",
        ],
        "xr_immersive_aesthetics": [
            "xr", "vr", "immersive", "vision pro", "deepfake",
            "synthetic", "virtual worlds",
        ],
        "policy_governance": [
            "policy", "regulation", "governance", "ethics", "responsibility",
            "surveillance", "platform", "law",
        ],
    },
    "cultural_resilience": {
        "planetary_rootedness": [
            "anthropocene", "planetary", "ecological", "mourning", "grief",
            "multispecies", "plant ethics", "world", "earth",
        ],
        "affect_relationality": [
            "affect", "care", "discomfort", "solitude", "presence",
            "relational", "assemblage", "fragility",
        ],
        "normativity_resistance": [
            "justice", "resistance", "freedom", "sovereignty", "hegemony",
            "normative", "political economy",
        ],
        "postdigital_materiality": [
            "algorithmic", "datafied", "digital noise", "materiality",
            "subject", "literacies", "postdigital",
        ],
    },
    "metakubi": {
        "transformation_discourses": [
            "transformation", "metamorphosis", "morphogenesis", "change",
            "transgression", "reframing",
        ],
        "mapping_reviews": [
            "mapping", "systematic review", "meta-analysis", "bibliometric",
            "research synthesis", "review",
        ],
        "institutional_change": [
            "school development", "schulkultur", "organization", "institutional",
            "field", "higher education",
        ],
    },
    "comearts": {
        "teacher_networks": [
            "community networks", "professional development", "teacher learning",
            "teacher training", "collaborative",
        ],
        "postdigital_arts_practice": [
            "post-digital", "arts education", "music education", "cross-aesthetic",
            "youth culture", "aesthetic practice",
        ],
        "diversity_inclusion": [
            "diversity", "inclusion", "intersectional", "postcolonial",
            "refugee", "inclusive",
        ],
    },
    "diaes_kubi": {
        "digital_aesthetic_agency": [
            "digital-aesthetic", "agency", "aesthetic agency", "sovereignty",
            "creative practice",
        ],
        "teacher_competencies": [
            "teacher competencies", "teacher education", "teacher training",
            "professional learning",
        ],
        "global_citizenship": [
            "global citizenship", "european identity", "civic", "citizenship",
            "democracy",
        ],
    },
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

_EMERGENT_MOTIF_STOP = _STOP | {
    "artificial", "intelligence", "generative", "algorithmic", "algorithms",
    "chatgpt", "llms", "large", "language", "model", "models", "platform",
    "platforms", "student", "students", "teacher", "teachers", "teaching",
    "pedagogy", "pedagogical", "education", "educational", "learning",
    "higher", "journal", "journals", "article", "articles", "paper",
    "papers", "study", "studies", "analysis", "research", "digital",
    "school", "schools", "classroom", "university", "universities", "online",
    "social", "public", "human", "humans", "technology", "technologies",
    "future", "critical", "ethics", "ethical", "policy", "governance",
    "creative", "creativity", "literacy", "literacies", "aesthetic",
    "aesthetics", "cultural", "culture", "based", "using", "towards",
    "through", "perspective", "perspectives", "approach", "approaches",
    "practice", "design", "development", "context", "science", "media",
    "machine", "futures",
    "artikel", "beitrag", "beiträge", "untersucht", "zeigt", "argumentiert",
    "analysiert", "analysiere", "methodisch", "theoretisch", "theorie",
    "praxis", "diskurs", "screening", "scannen", "ignorieren", "lesenswert",
    "pflichtlektüre", "agent", "verdict", "begründung", "bemerkenswert",
    "about", "should", "otherwise", "current", "beyond", "understanding",
    "journey",
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
    suggested_subgroup: str = ""
    suggested_subgroup_reason: str = ""
    suggested_subgroup_confidence: float = 0.0
    deterministic_signals: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EmergentMotifSuggestion:
    """Corpus-level motif hypothesis for currently unassigned articles."""
    label: str
    article_count: int
    journal_count: int
    strong_count: int
    score: float
    article_ids: list[str] = field(default_factory=list)

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


def _cue_hits_text(cue: str, text: str) -> bool:
    cue = cue.lower().strip()
    haystack = (text or "").lower()
    if not cue or not haystack:
        return False
    if len(cue) <= 3 or " " not in cue:
        pattern = r"\b" + re.escape(cue) + r"\b"
        return re.search(pattern, haystack) is not None
    return cue in haystack


def _normalize_motif_token(token: str) -> str:
    token = token.lower().strip("-_ ")
    if len(token) < 5 or token in _EMERGENT_MOTIF_STOP:
        return ""
    if token.endswith("ies") and len(token) > 6:
        token = token[:-3] + "y"
    elif token.endswith("s") and len(token) > 7 and not token.endswith(("ss", "ics")):
        token = token[:-1]
    if token in _EMERGENT_MOTIF_STOP or len(token) < 5:
        return ""
    return token


def _motif_source_title(title: str) -> str:
    raw = (title or "").strip()
    if not raw:
        return ""
    if raw.lower().startswith("review of "):
        last_year_match = None
        for match in re.finditer(r"\(\d{4}\)\.\s*", raw):
            last_year_match = match
        if last_year_match:
            raw = raw[last_year_match.end():]
        elif ":" in raw:
            raw = raw.split(":", 1)[1]
    return raw


def _article_motif_tokens(article: Any) -> set[str]:
    text_blob = _motif_source_title(getattr(article, "title", "")).lower()
    tokens = {
        _normalize_motif_token(token)
        for token in re.findall(r"[\w-]{5,}", text_blob)
    }
    return {token for token in tokens if token}


def suggest_emergent_motifs(
    articles: list[Any],
    *,
    background_articles: list[Any] | None = None,
    min_articles: int = 3,
    min_journals: int = 2,
    limit: int = 4,
) -> list[EmergentMotifSuggestion]:
    """Suggest recurring motifs from unassigned articles within one signal group."""
    if not articles:
        return []

    token_articles: dict[str, set[str]] = defaultdict(set)
    token_journals: dict[str, set[str]] = defaultdict(set)
    token_strong: Counter[str] = Counter()
    article_tokens: dict[str, set[str]] = {}
    article_lookup: dict[str, Any] = {}
    background_token_articles: dict[str, set[str]] = defaultdict(set)

    for article in articles:
        article_id = getattr(article, "id", "")
        if not article_id:
            continue
        tokens = _article_motif_tokens(article)
        if not tokens:
            continue
        article_tokens[article_id] = tokens
        article_lookup[article_id] = article
        journal = getattr(article, "journal_short", "") or getattr(article, "journal_full", "")
        for token in tokens:
            token_articles[token].add(article_id)
            if journal:
                token_journals[token].add(journal)
            if getattr(article, "discourse_indicator", "") == "starker_indikator":
                token_strong[token] += 1

    if background_articles is None:
        background_articles = []
    candidate_ids = set(article_lookup)
    for article in background_articles:
        article_id = getattr(article, "id", "")
        if not article_id or article_id in candidate_ids:
            continue
        for token in _article_motif_tokens(article):
            background_token_articles[token].add(article_id)

    background_total = max(
        1,
        len({getattr(article, "id", "") for article in background_articles if getattr(article, "id", "")}) - len(candidate_ids),
    )
    candidate_total = max(1, len(article_lookup))
    distinctiveness: dict[str, float] = {}
    for token, article_ids in token_articles.items():
        article_count = len(article_ids)
        background_count = len(background_token_articles[token])
        distinctiveness[token] = (article_count / candidate_total) / (
            (background_count + 1) / background_total
        )

    candidates: list[EmergentMotifSuggestion] = []
    for token, article_ids in token_articles.items():
        article_count = len(article_ids)
        journal_count = len(token_journals[token])
        if article_count < min_articles or journal_count < min_journals:
            continue
        if distinctiveness.get(token, 0.0) < 2.0:
            continue

        co_tokens: Counter[str] = Counter()
        for article_id in article_ids:
            for co_token in article_tokens.get(article_id, set()):
                if co_token != token:
                    co_tokens[co_token] += 1

        companion = ""
        companion_count = 0
        for co_token, count in co_tokens.most_common():
            if (
                count >= max(2, min_articles - 1)
                and count / max(article_count, 1) >= 0.4
                and distinctiveness.get(co_token, 0.0) >= 1.8
            ):
                companion = co_token
                companion_count = count
                break

        label = token
        if companion:
            label = f"{token} / {companion}"

        score = (
            article_count * 2.0
            + journal_count * 1.5
            + token_strong[token] * 1.2
            + companion_count * 0.3
            + distinctiveness[token] * 2.5
        )
        candidates.append(
            EmergentMotifSuggestion(
                label=label,
                article_count=article_count,
                journal_count=journal_count,
                strong_count=token_strong[token],
                score=score,
                article_ids=sorted(article_ids),
            )
        )

    candidates.sort(
        key=lambda item: (-item.score, -item.strong_count, -item.article_count, item.label)
    )

    selected: list[EmergentMotifSuggestion] = []
    used_article_sets: list[set[str]] = []
    used_token_sets: set[frozenset[str]] = set()
    for candidate in candidates:
        candidate_ids = set(candidate.article_ids)
        token_parts = frozenset(part.strip() for part in candidate.label.split("/"))
        if token_parts in used_token_sets:
            continue
        if any(candidate_ids <= used_ids for used_ids in used_article_sets):
            continue
        selected.append(candidate)
        used_article_sets.append(candidate_ids)
        used_token_sets.add(token_parts)
        if len(selected) >= limit:
            break

    return selected


def _suggest_subgroup(
    *,
    signal_group: str,
    title: str,
    text_blob: str,
    signal_profile: SignalProfile,
    discourse_indicator: str,
) -> tuple[str, str, float]:
    if not signal_group or discourse_indicator == "kein_indikator":
        return "", "", 0.0

    seeds = _SUBGROUP_SEEDS.get(signal_group, {})
    if seeds:
        scores: list[tuple[int, str, list[str]]] = []
        for subgroup, cues in seeds.items():
            score = 0
            hits: list[str] = []
            for cue in cues:
                cue_lower = cue.lower()
                if _cue_hits_text(cue_lower, text_blob):
                    score += 3 if " " in cue_lower else 2
                    hits.append(cue)
                elif _cue_hits_text(cue_lower, title or ""):
                    score += 2
                    hits.append(cue)
            if score:
                scores.append((score, subgroup, hits))

        if scores:
            scores.sort(key=lambda item: (-item[0], item[1]))
            best_score, best_subgroup, hits = scores[0]
            confidence = min(0.95, 0.35 + best_score / 10)
            reason = "Signale: " + ", ".join(hits[:3])
            if signal_profile.keyword_hits:
                reason += f" | Keywords: {', '.join(signal_profile.keyword_hits[:3])}"
            return best_subgroup, reason[:220], confidence

    # Emerging motifs need corpus-level aggregation. A per-article fallback creates
    # mostly one-off labels that look structured but do not compress the discourse.
    return "", "", 0.0


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
    suggested_subgroup, subgroup_reason, subgroup_confidence = _suggest_subgroup(
        signal_group=signal_group,
        title=title,
        text_blob=text_blob,
        signal_profile=signal_profile,
        discourse_indicator=discourse_indicator,
    )

    return AttentionProfile(
        selection_mode=selection_mode,
        discourse_indicator=discourse_indicator,
        signal_group=signal_group,
        project_hits=project_hits,
        suggested_subgroup=suggested_subgroup,
        suggested_subgroup_reason=subgroup_reason,
        suggested_subgroup_confidence=subgroup_confidence,
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
