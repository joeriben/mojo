"""Harte Konstanten + Diskursraum-Laden aus diskursraeume.json."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


@dataclass
class JournalConfig:
    name: str                               # voller Name
    short: str                              # Kurzname, z.B. "ZfE"
    type: str                               # "rss" | "ojs" | "html" | "openalex"
    url: str
    enabled: bool = True
    issn: str = ""                          # ISSN für OpenAlex-Backfill (bei RSS/OJS-Journals)
    tier: str = "B"                         # "A" | "B" | "C" — Analysetiefe
    clusters: list[str] = field(default_factory=list)  # Diskursraum-Zuordnung

# --- Researcher profile ---
# Defaults below; overridden by profile.json in project root (written by web UI).
# Priority: profile.json > environment > defaults here.

PROFILE_JSON = PROJECT_ROOT / "profile.json"

def _load_profile() -> dict:
    """Load profile.json if it exists, return empty dict otherwise."""
    if PROFILE_JSON.exists():
        try:
            return json.loads(PROFILE_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

_profile = _load_profile()

RESEARCHER_NAME = _profile.get("name", "Your Name")
RESEARCHER_INSTITUTION = _profile.get("institution", "Your Institution")
RESEARCHER_AREAS = _profile.get("areas", "your research areas")
RESEARCHER_TRIAGE_TOPICS = _profile.get("triage_topics", [
    "Topic 1",
    "Topic 2",
])

# --- Trigger-Autoren (MOJO 2.0 §2.2 + Cascade-Veto-Up) ---
# User-spezifische Wahl: Autor*innen, deren neue Arbeiten unabhängig vom
# Journal-Tier eskaliert werden sollen, und deren Bibliographien als
# adversariale Blind-Spot-Quelle benutzt werden.
#
# Defaults sind leer — ohne Konfiguration deaktiviert sich der Pfad sauber
# (`trigger_author_hit` immer False, AdversarialIndex leer, Cascade fließt
# unverändert durch). Pflege via `profile.json`:
#   "trigger_author_patterns": ["macgilchrist", "jarke", "wendy chun", ...]
#   "trigger_author_slugs":    ["macgilchrist", "jarke", "wendy_chun"]
#
# `*_patterns`: Lowercase-Substrings für Autor-String-Matching (signals.py).
# `*_slugs`:    File-Stems für `backtest_data/trigger_bibliographies/<slug>.json`
#               (adversarial/trigger_refs.py).
# Die beiden sind getrennt, weil patterns ggf. mehrere Varianten pro Person
# enthalten ("wendy chun" + "wendy hui kyong"), slugs aber 1:1 zu einem
# Bibliographie-File gehören.
#
# Verfahren zur Auswahl: vorerst kein Algorithmus, Auswahl liegt beim User.
# Methodische Hinweise + geplante Vorschlags-Komponente:
# docs/mojo_profile_modelling_sketch.md (§X-Vorhaben).
TRIGGER_AUTHOR_PATTERNS: tuple[str, ...] = tuple(
    _profile.get("trigger_author_patterns") or ()
)
TRIGGER_AUTHOR_SLUGS: tuple[str, ...] = tuple(
    _profile.get("trigger_author_slugs") or ()
)

# --- Zotero ---
# Override via profile.json or environment: MOJO_ZOTERO_STORAGE, MOJO_ZOTERO_COLLECTION
ZOTERO_STORAGE = Path(
    _profile.get("zotero_storage",
        os.environ.get("MOJO_ZOTERO_STORAGE", str(Path.home() / "Zotero" / "storage")))
)
ZOTERO_COLLECTION = _profile.get("zotero_collection",
    os.environ.get("MOJO_ZOTERO_COLLECTION", "My publications"))
SINCE_YEAR = _profile.get("since_year", 2018)

# --- Projekt-Dateien ---
CORPUS_JSON = PROJECT_ROOT / "corpus.json"
SUMMARIES_JSON = PROJECT_ROOT / "summaries.json"
STATE_DB = PROJECT_ROOT / "seen.db"

# --- Ausgabe ---
DIGEST_DIR = Path(
    _profile.get("digest_dir",
        os.environ.get("MOJO_DIGEST_DIR", str(PROJECT_ROOT / "output")))
)

# --- LLM (OpenRouter) ---
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL_SUMMARIZE = _profile.get("model_summarize", "anthropic/claude-opus-4.6")
MODEL_AGENT = _profile.get("model_agent", "anthropic/claude-opus-4.6")
# Trends-Modell separat — Q-Check 2026-05 belegt MiMo als Quality-neutralen, ~9× günstigeren
# Default. Falls Opus-Refresh gewünscht ist (z. B. quartalsweise), via profile.json setzen.
MODEL_TRENDS = _profile.get("model_trends", "xiaomi/mimo-v2.5-pro")
# Trends-Modelle wie MiMo brauchen mehr completion-Tokens als der Opus-Default (5000).
# 32000 reicht für die Markdown-Dossiers (Q-Check-Outputs: 9518–11406 chars, finish=stop).
MAX_TOKENS_TRENDS = int(_profile.get("max_tokens_trends", 32000))

# --- API-Key-Ablage ---
_KEY_DIR = Path.home() / ".config" / "mojo"
KEY_FILE = _KEY_DIR / "openrouter_key"
S2_KEY_FILE = _KEY_DIR / "s2_api_key"
ZOTERO_USER_ID_FILE = _KEY_DIR / "zotero_user_id"
ZOTERO_API_KEY_FILE = _KEY_DIR / "zotero_api_key"
MISTRAL_KEY_FILE = _KEY_DIR / "mistral_key"


def save_profile(data: dict) -> None:
    """Write profile.json and update module-level constants in-place."""
    import journal_bot.settings as _self
    PROFILE_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # Update module globals so running process sees changes immediately
    _self.RESEARCHER_NAME = data.get("name", _self.RESEARCHER_NAME)
    _self.RESEARCHER_INSTITUTION = data.get("institution", _self.RESEARCHER_INSTITUTION)
    _self.RESEARCHER_AREAS = data.get("areas", _self.RESEARCHER_AREAS)
    _self.RESEARCHER_TRIAGE_TOPICS = data.get("triage_topics", _self.RESEARCHER_TRIAGE_TOPICS)
    _self.ZOTERO_STORAGE = Path(data["zotero_storage"]) if data.get("zotero_storage") else _self.ZOTERO_STORAGE
    _self.ZOTERO_COLLECTION = data.get("zotero_collection", _self.ZOTERO_COLLECTION)
    _self.SINCE_YEAR = data.get("since_year", _self.SINCE_YEAR)
    _self.DIGEST_DIR = Path(data["digest_dir"]) if data.get("digest_dir") else _self.DIGEST_DIR
    _self.MODEL_SUMMARIZE = data.get("model_summarize", _self.MODEL_SUMMARIZE)
    _self.MODEL_AGENT = data.get("model_agent", _self.MODEL_AGENT)
    _self.MODEL_TRENDS = data.get("model_trends", _self.MODEL_TRENDS)
    _self.MAX_TOKENS_TRENDS = int(data.get("max_tokens_trends", _self.MAX_TOKENS_TRENDS))
    _self.TRIGGER_AUTHOR_PATTERNS = tuple(data.get("trigger_author_patterns") or ())
    _self.TRIGGER_AUTHOR_SLUGS = tuple(data.get("trigger_author_slugs") or ())


# --- Diskursräume ---
# Kategorien: "deutsche, erziehungswiss, digitale_kultur (mit/ohne Erz.),
# medienpäd, bildungstheorie, resilienz". Ein Journal kann zu mehreren Räumen gehören.
# Zuordnungen unten sind editierbar.

DISCOURSE_SPACES: dict[str, dict[str, str]] = {
    "deutsche": {
        "name": "Deutschsprachige Journals",
        "description": "Journals mit primär deutscher Publikationssprache (cross-cutting).",
    },
    "erziehungswiss": {
        "name": "Erziehungswissenschaftliche Journals",
        "description": "Empirische und theoretische Erziehungswissenschaft, Bildungsforschung.",
    },
    "digitale_kultur": {
        "name": "Digitale Kultur",
        "description": "Diskursraum digitale/postdigitale Kultur, mit oder ohne Bildungsfokus.",
    },
    "medienpaed": {
        "name": "Medienpädagogik",
        "description": "Medienpädagogische Fachzeitschriften.",
    },
    "bildungstheorie": {
        "name": "Bildungstheorie und -philosophie",
        "description": "Theoretische und philosophische Auseinandersetzung mit Bildung / "
                       "Education.",
    },
    "aesthetische_kulturelle_bildung": {
        "name": "Ästhetische und kulturelle Bildung",
        "description": "Ästhetische Bildung, kulturelle Bildung, Kunstpädagogik, "
                       "Kunst-Bildungs-Verhältnis.",
    },
    "resilienz": {
        "name": "Resilienz & Nachhaltigkeit / Environmental Humanities",
        "description": "Kulturelle und ökologische Resilienz, Nachhaltigkeit, "
                       "Umweltbildung, Transformation.",
    },
}


# --- Diskursräume aus JSON laden (Vorrang vor Hardcoded-Defaults) ---
DISKURSRAEUME_JSON = PROJECT_ROOT / "diskursraeume.json"
_JOURNAL_CLUSTERS: dict[str, list[str]] = {}

if DISKURSRAEUME_JSON.exists():
    _dr_data = json.loads(DISKURSRAEUME_JSON.read_text(encoding="utf-8"))
    # Override discourse space definitions
    DISCOURSE_SPACES = {
        k: {"name": v["name"], "description": v["description"]}
        for k, v in _dr_data.get("discourse_spaces", {}).items()
    }
    _JOURNAL_CLUSTERS = _dr_data.get("journal_clusters", {})
    del _dr_data


def journals_in_cluster(cluster_key: str) -> list["JournalConfig"]:
    return [j for j in JOURNALS if j.enabled and cluster_key in j.clusters]


def available_clusters() -> list[tuple[str, dict[str, str], int]]:
    """Gibt (key, meta, count) für jeden Cluster zurück — Count zählt aktive Journals."""
    return [
        (k, meta, len(journals_in_cluster(k)))
        for k, meta in DISCOURSE_SPACES.items()
    ]


# --- Journals ---
# Loaded from journals.json (data file). Cluster assignments come from diskursraeume.json.

JOURNALS_JSON = PROJECT_ROOT / "journals.json"

def _load_journals() -> list[JournalConfig]:
    """Load journal configs from journals.json, apply cluster overrides."""
    journals: list[JournalConfig] = []

    if JOURNALS_JSON.exists():
        data = json.loads(JOURNALS_JSON.read_text(encoding="utf-8"))
        for j in data.get("journals", []):
            journals.append(JournalConfig(
                name=j["name"],
                short=j["short"],
                type=j["type"],
                url=j["url"],
                enabled=j.get("enabled", True),
                issn=j.get("issn", ""),
                tier=j.get("tier", "B"),
                clusters=j.get("clusters", []),
            ))
    else:
        raise FileNotFoundError(f"journals.json nicht gefunden: {JOURNALS_JSON}")

    # Apply cluster overrides from diskursraeume.json
    if _JOURNAL_CLUSTERS:
        short_to_journal = {j.short: j for j in journals}
        for short, clusters in _JOURNAL_CLUSTERS.items():
            if short in short_to_journal:
                short_to_journal[short].clusters = list(clusters)

    return journals


JOURNALS: list[JournalConfig] = _load_journals()
