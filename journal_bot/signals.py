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

from journal_bot.adversarial.corpus_freq import (
    AdversarialCorpusFreq, load_or_compute_adversarial_corpus_freq,
)
from journal_bot.adversarial.trigger_refs import (
    AdversarialIndex, load_or_compute_adversarial_index,
)
from journal_bot.citation_tracker import find_citations, CitationHit, load_authored_all
from journal_bot.own_refs.corpus_freq import CorpusFreq, load_or_compute_corpus_freq
from journal_bot.own_refs.index import OwnRefsIndex, load_own_refs_index
from journal_bot.settings import CORPUS_JSON, SUMMARIES_JSON, PROJECT_ROOT


ZOTERO_LIBRARY_JSON = PROJECT_ROOT / "zotero_library.json"
PROJECTS_JSON = PROJECT_ROOT / "projects.json"
OWN_REFS_DB = PROJECT_ROOT / "own_refs.db"
ARTICLES_DB = PROJECT_ROOT / "articles.db"
TRIGGER_BIBLIOGRAPHIES_DIR = PROJECT_ROOT / "backtest_data" / "trigger_bibliographies"

# IDF-Score-Schwellen für die Bibliographic-Coupling-Veto-Regel (§2.1b).
# Kalibriert gegen Live-Verteilung in articles.db (18 212 Artikel, Stand
# 2026-05-24):
#   - Score ≥ 0.6 → LES/IGN-Trefferquote 10× (schwacher Indikator)
#   - Score ≥ 1.5 → LES/IGN-Trefferquote 38× (starker Indikator)
# Bestseller-Refs (z. B. 10.1080/00131857.2018.1454000, 249× im Korpus)
# haben IDF ≈ 0.18; ein einzelner solcher Treffer reicht NICHT für die
# weak-Schwelle, exakt was Benjamin als Anforderung gestellt hatte.
OWN_COUPLING_WEAK_SCORE = 0.60
OWN_COUPLING_STRONG_SCORE = 1.50

# Adversariale Set-Differenz-Schwellen (§2.2). Kalibriert gegen Live-Verteilung
# in articles.db (18 212 Artikel, Stand 2026-05-24):
#   - Score ≥ 3.0  → LES/IGN-Trefferquote  6.5x (schwacher Indikator, ~700 Lifts)
#   - Score ≥ 8.0  → LES/IGN-Trefferquote 16x   (starker Indikator,  ~50 Lifts)
# Adversarial ist NICHT so trennscharf wie own_coupling (das bei 1.5 schon 38x
# schafft). Das spiegelt den methodischen Unterschied: Trigger-Anschluss heißt
# "diskursiv relevant", nicht zwangsläufig "muss lesen". Schwellen entsprechend
# konservativer gesetzt — adversarial signalisiert Blind-Spot-Anschluss, nicht
# Pflichtlektüre.
ADVERSARIAL_WEAK_SCORE = 3.00
ADVERSARIAL_STRONG_SCORE = 8.00
TRIGGER_AUTHORS = ("macgilchrist", "jarke", "wendy chun", "wendy hui kyong")
SELECTION_MODES = {
    "none", "screening", "similarity", "complementarity",
    "citation", "own_coupling", "adversarial", "trigger", "mixed",
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
        "auschwitz", "shoah", "holocaust",
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

_PROJECT_OVERLAP_STOP = _STOP | {
    "active", "agency", "ai", "algorithmic", "algorithms", "artificial",
    "arts", "basis", "becoming", "care", "change", "collective",
    "condition", "conditions", "context", "contexts", "crisis", "crises",
    "critical", "data", "decision", "describes", "digitality",
    "digitalization", "diversity", "ethics", "field", "future", "futures",
    "global", "governance", "human", "humannonhuman", "identity",
    "inheritances", "intelligence", "international", "investigates",
    "labor", "management", "model", "models", "modules", "music",
    "networked", "nonhuman", "orders", "others", "participatory", "period",
    "post", "postdigital", "practice", "practices", "professional",
    "programme", "programme", "relates", "responding", "review", "social",
    "societal", "structures", "supported", "suppoerted", "systemic",
    "teaching", "terms", "theory", "training", "transformation",
    "transformations", "transformational", "work", "world",
}

_PROJECT_CONTEXT_RULES = {
    "ai4artsed": {
        "context_any": [
            "art", "arts", "aesthetic", "cultural", "creativity", "creative",
            "music", "pedagog", "teacher", "classroom", "education",
            "learning", "bias", "decolonial", "indigenous", "representation",
            "training data", "artistic", "co-creation", "prompt", "colonial",
            "hegemony", "lifeworld", "power", "manipulation", "control",
            "subjectiv", "xr", "extended reality", "ästhet", "kunst",
            "musik", "bildung", "unterricht",
        ],
        "block_any": [
            "healthcare", "medicine", "medical", "clinical", "patient",
            "hospital", "project management", "public service",
            "administrative", "legal process", "court", "labour", "labor",
            "interview",
        ],
        "rescue_any": [
            "art", "arts", "aesthetic", "cultural", "creative", "artistic",
            "bias", "decolonial", "indigenous", "representation",
            "training data", "co-creation", "prompt", "chatgpt",
            "generative ai", "llm", "xr", "extended reality",
        ],
        "min_score": 3,
        "strong_score": 5,
    },
    "metakubi": {
        "context_any": [
            "arts", "cultural", "education", "school", "schulkultur",
            "schule", "schul", "unterricht", "bildung", "transformation",
            "krise", "digitalisierungsprozess", "digitalisierungsprozesse",
            "mapping", "bibliometric", "meta-analysis",
            "research synthesis", "systematic review", "institutional",
        ],
        "hard_block_any": ["interview"],
        "block_any": [
            "healthcare", "medicine", "medical", "clinical", "patient",
            "hospital", "project management", "public service",
            "administrative", "legal process", "court", "labour", "labor",
            "workplace",
        ],
        "rescue_any": [
            "arts", "cultural", "school", "schule", "schul",
            "schulkultur", "systematic review", "meta-analysis",
            "mapping", "bibliometric", "research synthesis", "krise",
        ],
        "min_score": 3,
        "strong_score": 5,
    },
    "comearts": {
        "context_any": [
            "arts", "music", "aesthetic", "cultural", "youth",
            "community", "network", "teacher", "training", "diversity",
            "postcolonial", "intersectional", "kunst", "musik", "bildung",
        ],
        "min_score": 3,
        "strong_score": 5,
    },
    "diaes_kubi": {
        "context_any": [
            "aesthetic", "arts", "music", "cultural", "teacher",
            "citizenship", "sovereignty", "pedagog", "education",
            "bildung", "ästhet", "xr", "extended reality", "kunst",
            "musik",
        ],
        "min_score": 3,
        "strong_score": 5,
    },
    "cultural_resilience": {
        "context_any": [
            "education", "pedagog", "bildung", "erziehung", "aesthetic",
            "cultural", "ecological", "climate", "anthropocene", "mourning",
            "grief", "hope", "justice", "resistance", "care", "affect",
            "multispecies", "posthuman", "subjectiv", "body", "bodies",
            "media", "shoah", "auschwitz", "holocaust",
        ],
        "block_any": [
            "healthcare", "medicine", "medical", "clinical", "patient",
            "hospital", "project management", "public service",
            "administrative", "legal process", "court", "interview",
        ],
        "rescue_any": [
            "aesthetic", "cultural", "ecological", "climate",
            "anthropocene", "mourning", "grief", "hope", "justice",
            "resistance", "affect",
            "multispecies", "posthuman", "shoah", "auschwitz", "holocaust",
            "body", "bodies", "subjectiv",
        ],
        "min_score": 3,
        "strong_score": 5,
    },
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
    own_coupling: dict[str, Any] = field(default_factory=dict)
    # own_coupling-Schema (siehe signal_own_coupling):
    #   {"oa_hits": list[str], "doi_hits": list[str], "n_union": int}
    # Leer wenn own_refs.db fehlt, der Article keine Refs hat, oder kein Treffer.
    adversarial: dict[str, Any] = field(default_factory=dict)
    # adversarial-Schema (siehe signal_adversarial_blindspot, §2.2):
    #   {"oa_hits": list[str], "n_hits": int, "score": float}
    # Schnittpunkte zwischen Article-Refs und (trigger_refs \ benjamin_refs).
    # Bedeutung: "was zitieren die Trigger-Autoren (Macgilchrist/Jarke/Chun),
    # was Benjamin noch nicht zitiert" — Blind-Spot-Detektor.

    @property
    def has_any_signal(self) -> bool:
        # Coupling-Signal nur dann zählen, wenn der IDF-Score über der WEAK-
        # Schwelle liegt — Bestseller-Einzelhits sind kein Signal (§2.1b).
        # Schwellen-Konstante ist hier per Default eingebaut, um zirkuläre
        # Imports zu vermeiden; Aufrufer können _has_coupling_signal() explizit
        # mit anderer Schwelle aufrufen.
        return bool(
            self.cites_researcher
            or self.zotero_overlap
            or self.keyword_hits
            or self._has_coupling_signal()
        )

    @property
    def signal_count(self) -> int:
        return sum([
            bool(self.cites_researcher),
            bool(self.zotero_overlap),
            bool(self.keyword_hits),
            bool(self._has_coupling_signal()),
        ])

    def _has_coupling_signal(self, weak_threshold: float = 0.60) -> bool:
        """True wenn der IDF-Coupling-Score die WEAK-Schwelle überschreitet.

        Die Konstante 0.60 spiegelt OWN_COUPLING_WEAK_SCORE (Modul-Level);
        sie ist hier hart kodiert, um Import-Zyklen mit Modul-Konstanten zu
        vermeiden. Wenn die Modul-Schwelle sich ändert, sollte sie hier
        nachgezogen werden — Tests in test_signals_own_coupling decken den
        Drift ab.
        """
        return self.f_own_coupling_score >= weak_threshold

    @property
    def f_own_coupling_union(self) -> int:
        """Roher Treffer-Count, primär für Diagnostik.

        Iter-11-Feature: max(|article_oa ∩ benjamin_oa|, |article_doi ∩ benjamin_doi|).
        Wird NICHT mehr direkt für die Cascade-Veto-Regel benutzt — der
        IDF-gewichtete Score (`f_own_coupling_score`) entscheidet, weil ein
        einzelner Treffer auf ein Standardwerk kein Signal ist.
        """
        return int(self.own_coupling.get("n_union", 0) or 0)

    @property
    def f_own_coupling_score(self) -> float:
        """IDF-gewichteter Coupling-Score (§2.1b).

        Score = max(sum_oa(idf(hit)), sum_doi(idf(hit))). Spezifische
        Refs zählen schwer (idf ~1.4), Bestseller leicht (idf ~0.2). Treibt
        die Drei-Stufen-Veto-Regel:
            score ≥ OWN_COUPLING_STRONG_SCORE → starker_indikator
            score ≥ OWN_COUPLING_WEAK_SCORE   → schwacher_indikator
        """
        return float(self.own_coupling.get("score", 0.0) or 0.0)

    @property
    def f_adversarial_score(self) -> float:
        """IDF-gewichteter Score auf der Set-Differenz `trigger_refs \\ benjamin_refs`.

        Misst die Anschlussfähigkeit zu Diskursen, die Benjamin (noch) nicht
        aufgegriffen hat. Treibt einen eigenen Indikator-Pfad (§2.2.c) —
        Veto-Up- vs. Veto-Down-Charakter wird datenbasiert entschieden.
        """
        return float(self.adversarial.get("score", 0.0) or 0.0)

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
        if self.f_own_coupling_union:
            oa_hits = self.own_coupling.get("oa_hits") or []
            doi_hits = self.own_coupling.get("doi_hits") or []
            parts.append(
                f"own_coupling(union={self.f_own_coupling_union}, "
                f"oa={len(oa_hits)}, doi={len(doi_hits)})"
            )
        if self.adversarial:
            adv_hits = self.adversarial.get("oa_hits") or []
            parts.append(
                f"adversarial(n={len(adv_hits)}, "
                f"score={self.f_adversarial_score:.2f})"
            )
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


def _normalize_oa_id(s: str | None) -> str:
    """https://openalex.org/Wxxxx → Wxxxx (Iter-11-Konvention)."""
    if not s:
        return ""
    return str(s).rsplit("/", 1)[-1].strip()


def _normalize_doi_local(s: str | None) -> str:
    """Lowercase, Präfixe entfernt — synchron zu own_refs/index._normalize_doi."""
    if not s:
        return ""
    raw = str(s).strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    return raw.rstrip(".")


def signal_own_coupling(
    crossref_refs: list[dict] | None,
    openalex_refs: list[str] | None,
    own_refs_index: OwnRefsIndex | None,
    corpus_freq: CorpusFreq | None = None,
) -> dict[str, Any]:
    """Signal d: Bibliographic Coupling gegen Benjamins Refs-Wolke (IDF-gewichtet).

    Hintergrund (Benjamin 2026-05-24): ein ungewichteter Binär-Treffer ist
    keine Intelligenz, sondern eine primitive Suchfunktion. Standardwerke
    wie `10.1080/00131857.2018.1454000` (249× im Korpus) erzeugen sonst Rauschen.
    Lösung: IDF-Gewichtung — spezifische Treffer wiegen schwer, generische leicht.

    Berechnung:
      oa_hits  = article.openalex_refs ∩ own_refs_index.oa_ids
      doi_hits = article.crossref_refs[].doi ∩ own_refs_index.dois
      oa_score  = sum(1/log(1+global_count(h))) over oa_hits
      doi_score = sum(1/log(1+global_count(h))) over doi_hits
      score     = max(oa_score, doi_score)    # konservativ wie n_union

    Wenn `corpus_freq=None`, wird jeder Treffer mit dem Default-Gewicht 1/log(2)
    ≈ 1.44 gezählt (Iter-11-Verhalten, primitiv). Für die Cascade-Veto-Regel
    sollte immer `corpus_freq` mitgegeben werden — `load_signal_resources()`
    lädt es automatisch.

    Returns:
        Dict mit `oa_hits`, `doi_hits` (sorted lists), `n_union` (int, alt),
        `score` (float, IDF-gewichtet). Bei leerem Index oder Null-Schnitt:
        leeres Dict.
    """
    if own_refs_index is None or own_refs_index.is_empty:
        return {}

    # Article-OA-Refs intersecten
    oa_hits: list[str] = []
    if openalex_refs:
        normalized = {_normalize_oa_id(x) for x in openalex_refs if x}
        normalized.discard("")
        oa_hits = sorted(normalized & own_refs_index.oa_ids)

    # Article-DOI-Refs aus crossref_refs intersecten
    doi_hits: list[str] = []
    if crossref_refs:
        article_dois: set[str] = set()
        for ref in crossref_refs:
            if not isinstance(ref, dict):
                continue
            d = _normalize_doi_local(ref.get("doi"))
            if d.startswith("10."):
                article_dois.add(d)
        doi_hits = sorted(article_dois & own_refs_index.dois)

    if not oa_hits and not doi_hits:
        return {}

    n_union = max(len(oa_hits), len(doi_hits))

    # IDF-gewichteter Score
    if corpus_freq is not None and not corpus_freq.is_empty:
        oa_score = sum(corpus_freq.idf_weight_oa(h) for h in oa_hits)
        doi_score = sum(corpus_freq.idf_weight_doi(h) for h in doi_hits)
    else:
        # Fallback: jedes Hit mit dem Default-Gewicht (für Tests ohne Freq-Index)
        default_w = 1.0 / __import__("math").log(2.0)
        oa_score = default_w * len(oa_hits)
        doi_score = default_w * len(doi_hits)

    score = max(oa_score, doi_score)
    return {
        "oa_hits": oa_hits,
        "doi_hits": doi_hits,
        "n_union": n_union,
        "score": round(score, 4),
    }


def signal_adversarial_blindspot(
    openalex_refs: list[str] | None,
    adversarial_index: AdversarialIndex | None,
    adversarial_corpus_freq: AdversarialCorpusFreq | None = None,
) -> dict[str, Any]:
    """Signal e: Adversarial-Set-Differenz `trigger_refs \\ benjamin_refs` (§2.2).

    Misst, wieviele Refs der Artikel mit den Trigger-Autoren teilt, die NICHT
    in Benjamins eigener Refs-Wolke vorkommen. Bedeutung: Anschluss an
    benachbarte Diskurse (Macgilchrist/Jarke/Chun), die Benjamin aktuell
    nicht selbst zitiert — Blind-Spot-Indikator.

    Nur OA-IDs werden ausgewertet, weil die Trigger-Daten aus dem
    Iter-10-Snapshot keine sauberen DOI-Sets liefern. Wenn das später ergänzt
    wird, kann die Funktion analog zu `signal_own_coupling` erweitert werden.

    Returns:
        Dict mit `oa_hits` (sorted list), `n_hits`, `score` (IDF-gewichtet).
        Leer wenn Index leer oder keine Refs.
    """
    if adversarial_index is None or adversarial_index.is_empty:
        return {}
    if not openalex_refs:
        return {}

    normalized = {_normalize_oa_id(x) for x in openalex_refs if x}
    normalized.discard("")
    oa_hits = sorted(normalized & adversarial_index.oa_ids)
    if not oa_hits:
        return {}

    if adversarial_corpus_freq is not None and not adversarial_corpus_freq.is_empty:
        score = sum(adversarial_corpus_freq.idf_weight_oa(h) for h in oa_hits)
    else:
        default_w = 1.0 / __import__("math").log(2.0)
        score = default_w * len(oa_hits)

    return {
        "oa_hits": oa_hits,
        "n_hits": len(oa_hits),
        "score": round(score, 4),
    }


# --------------------------------------------------------- Composite Score --


def _coerce_refs_list(value: str | list | None) -> list:
    """JSON-String oder Liste → Liste, sonst []."""
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    if isinstance(value, list):
        return value
    return []


def compute_signals(
    article_id: str,
    title: str,
    crossref_refs_json: str | list | None,
    *,
    openalex_refs_json: str | list | None = None,
    authored_all: list[dict] | None = None,
    key_terms: set[str] | None = None,
    zotero_doi_index: dict[str, ZoteroItem] | None = None,
    zotero_word_index: dict[str, list[ZoteroItem]] | None = None,
    own_refs_index: OwnRefsIndex | None = None,
    corpus_freq: CorpusFreq | None = None,
    adversarial_index: AdversarialIndex | None = None,
    adversarial_corpus_freq: AdversarialCorpusFreq | None = None,
) -> SignalProfile:
    """Compute all deterministic signals for one article.

    `openalex_refs_json`, `own_refs_index`, `corpus_freq`, `adversarial_index`
    und `adversarial_corpus_freq` sind alle optional — fehlt eines davon,
    bleiben die jeweiligen Signale leer. Das hält ältere Aufrufer
    (Smoke-Tests, Backtest-Replay) kompatibel.
    """
    refs = _coerce_refs_list(crossref_refs_json)
    oa_refs = _coerce_refs_list(openalex_refs_json)
    # `openalex_refs` ist eine flache Liste von Work-IDs (Strings).
    oa_ref_strings = [x for x in oa_refs if isinstance(x, str)]

    return SignalProfile(
        article_id=article_id,
        cites_researcher=signal_cites_researcher(refs, authored_all),
        zotero_overlap=signal_zotero_overlap(
            refs, zotero_doi_index, zotero_word_index,
        ),
        keyword_hits=signal_keyword_hits(title, key_terms),
        own_coupling=signal_own_coupling(
            refs, oa_ref_strings, own_refs_index, corpus_freq,
        ),
        adversarial=signal_adversarial_blindspot(
            oa_ref_strings, adversarial_index, adversarial_corpus_freq,
        ),
    )


def _load_active_projects(path: Path = PROJECTS_JSON) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [p for p in data.get("projects", []) if p.get("status") == "active"]


def _project_overlap_words(project: dict[str, Any]) -> set[str]:
    project_text = " ".join(
        [
            project.get("name", ""),
            project.get("description", ""),
            " ".join(project.get("relevance_shifts", [])),
        ]
    )
    return _text_words(project_text) - _PROJECT_OVERLAP_STOP


def _match_any_cues(cues: list[str], text_blob: str) -> list[str]:
    return [cue for cue in cues if _cue_hits_text(cue, text_blob)]


def _project_match_score(project: dict[str, Any], text_blob: str, text_words: set[str]) -> int:
    score = 0
    phrase_score = 0
    for phrase in _PROJECT_SIGNAL_KEYWORDS.get(project.get("key", ""), []):
        if phrase.lower() in text_blob:
            hit_score = 2 if " " in phrase else 1
            score += hit_score
            phrase_score += hit_score

    overlap = text_words & _project_overlap_words(project)
    overlap_score = min(len(overlap), 4)
    score += overlap_score

    rules = _PROJECT_CONTEXT_RULES.get(project.get("key", ""))
    if not rules:
        return score

    if _match_any_cues(rules.get("hard_block_any", []), text_blob):
        return 0

    block_hits = _match_any_cues(rules.get("block_any", []), text_blob)
    rescue_hits = _match_any_cues(rules.get("rescue_any", []), text_blob)
    if block_hits and not rescue_hits:
        return 0

    context_hits = len(_match_any_cues(rules["context_any"], text_blob))
    score += min(context_hits, 2)
    if score < rules["min_score"]:
        return 0
    if context_hits == 0 and phrase_score < rules["strong_score"]:
        return 0
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
    # Iter-11-Veto-Up, IDF-gewichtet (§2.1b): Bibliographic Coupling gegen
    # Benjamins Refs-Wolke. Nur wenn der Score über der WEAK-Schwelle liegt
    # — ein einzelner Bestseller-Treffer reicht NICHT (das war der primitive
    # Pre-§2.1b-Stand). Schwächer als citation/trigger, stärker als project.
    if signal_profile.f_own_coupling_score >= OWN_COUPLING_WEAK_SCORE:
        return "own_coupling"
    # Adversariales Set-Coupling (§2.2): Anschluss an Trigger-Diskurse, die
    # Benjamin noch nicht aufgegriffen hat. NUR bei sehr hohem Score
    # (STRONG-Schwelle), weil das Signal deutlich weniger trennscharf ist
    # als own_coupling (16x LES/IGN vs 38x). Schwacher adversarial-Score
    # wird im discourse_indicator berücksichtigt, ändert aber den Mode nicht.
    if signal_profile.f_adversarial_score >= ADVERSARIAL_STRONG_SCORE:
        return "adversarial"
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
    # Iter-11-Veto-Up, IDF-gewichtete Drei-Stufen-Regel (§2.1b):
    #   score ≥ OWN_COUPLING_STRONG_SCORE (1.50) → starker_indikator
    #       (LES/IGN-Trefferquote 38× — sehr verlässlich; Bestseller-Hits
    #        addieren sich kaum auf diese Höhe)
    #   score ≥ OWN_COUPLING_WEAK_SCORE   (0.60) → schwacher_indikator
    #       (LES/IGN-Trefferquote 10×)
    # Ein einzelner Bestseller-Treffer (Score ~0.18-0.30) bleibt unter beiden
    # Schwellen — genau das Verhalten, das Benjamin als primitive Suchfunktion
    # rausoperiert haben wollte.
    score = signal_profile.f_own_coupling_score
    adv_score = signal_profile.f_adversarial_score
    if score >= OWN_COUPLING_STRONG_SCORE:
        return "starker_indikator"
    # Adversarial-STRONG (§2.2): selektiver Blind-Spot-Hebel, schwächer als
    # own_coupling-STRONG (16x vs 38x LES/IGN). Reicht trotzdem für
    # starker_indikator, weil bei Score ≥ 8 nur ~50 Items insgesamt betroffen
    # sind — kleines aber hochwertiges Aufmerksamkeits-Signal.
    if adv_score >= ADVERSARIAL_STRONG_SCORE:
        return "starker_indikator"
    if verdict == "scannen" and project_hits and (bemerkenswert or signal_profile.signal_count > 0):
        return "starker_indikator"
    if score >= OWN_COUPLING_WEAK_SCORE:
        return "schwacher_indikator"
    # Adversarial-WEAK (§2.2): mittlerer Diskurs-Anschluss → schwacher_indikator.
    # Wirkt nur, wenn nichts Stärkeres feuert.
    if adv_score >= ADVERSARIAL_WEAK_SCORE:
        return "schwacher_indikator"
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
    openalex_refs: list[str] | None = None,
    entry: dict[str, Any] | None = None,
    signal_resources: dict[str, Any] | None = None,
) -> AttentionProfile:
    """Derive attention metadata from existing article + agent data.

    `openalex_refs` (flache Liste von Work-ID-Strings aus
    `articles.openalex_refs`) wird für die Iter-11-Bibliographic-Coupling-
    Veto-Up-Regel benötigt. Aufrufer ohne diesen Wert (z. B. ältere Pfade
    oder Tests) lassen ihn weg — `own_coupling` bleibt dann leer.
    """
    entry = entry or {}
    signal_resources = signal_resources or load_signal_resources()
    signal_profile = compute_signals(
        article_id,
        title,
        crossref_refs or [],
        openalex_refs_json=openalex_refs or [],
        **signal_resources,
    )

    bemerkenswert = entry.get("bemerkenswert") or []
    bezuege = entry.get("bezuege") or []
    article_blob = "\n".join(
        [
            title or "",
            abstract or "",
            openalex_abstract or "",
        ]
    ).lower()
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
    project_hits = detect_project_hits(article_blob)
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
    own_refs_db: Path = OWN_REFS_DB,
    articles_db: Path = ARTICLES_DB,
    trigger_bibliographies_dir: Path = TRIGGER_BIBLIOGRAPHIES_DIR,
) -> dict[str, Any]:
    """Pre-load all resources needed for batch signal computation.

    `own_refs_index` ist die Refs-Wolke aus `own_refs.db` (Iter-11-Coupling).
    `corpus_freq` ist die globale Häufigkeit der Refs in `articles.db`
    (IDF-Gewichtung gegen Bestseller-Rauschen, §2.1b). `adversarial_index`
    ist die Set-Differenz `trigger_refs \\ benjamin_refs` (§2.2). Alle
    werden lazy geladen; fehlen sie, läuft die Pipeline graceful weiter.
    """
    zotero_lib = load_zotero_library(zotero_path)
    own_refs_index = load_own_refs_index(own_refs_db)
    corpus_freq = load_or_compute_corpus_freq(articles_db, own_refs_index)
    adversarial_index = load_or_compute_adversarial_index(
        trigger_bibliographies_dir, own_refs_index, own_refs_db=own_refs_db,
    )
    adversarial_corpus_freq = load_or_compute_adversarial_corpus_freq(
        articles_db, adversarial_index, own_refs_db=own_refs_db,
    )
    return {
        "authored_all": load_authored_all(corpus_path),
        "key_terms": load_key_terms(summaries_path),
        "zotero_doi_index": _build_zotero_doi_index(zotero_lib),
        "zotero_word_index": _build_zotero_word_index(zotero_lib),
        "own_refs_index": own_refs_index,
        "corpus_freq": corpus_freq,
        "adversarial_index": adversarial_index,
        "adversarial_corpus_freq": adversarial_corpus_freq,
    }
