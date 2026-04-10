"""Harte Konstanten + Diskursraum-Laden aus diskursraeume.json."""

from __future__ import annotations

import json
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
    clusters: list[str] = field(default_factory=list)  # Diskursraum-Zuordnung

# --- Zotero ---
ZOTERO_STORAGE = Path("/Users/joerissen/FAUbox/Zotero/storage")
ZOTERO_COLLECTION = "Benjamin's publications"
SINCE_YEAR = 2018

# --- Projekt-Dateien ---
CORPUS_JSON = PROJECT_ROOT / "corpus.json"
SUMMARIES_JSON = PROJECT_ROOT / "summaries.json"
STATE_DB = PROJECT_ROOT / "seen.db"

# --- Ausgabe ---
DIGEST_DIR = Path("/Users/joerissen/Documents/Obsidian Vault/research/mojo")

# --- LLM (OpenRouter) ---
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Für die Summarisation — billig und faktisch
MODEL_SUMMARIZE = "anthropic/claude-haiku-4.5"
# Für den Agent-Lauf — das eigentliche Reasoning
MODEL_AGENT = "anthropic/claude-opus-4.6"

# --- API-Key-Ablage (interaktiv abgefragt, nicht .env) ---
KEY_FILE = Path.home() / ".config" / "mojo" / "openrouter_key"


# --- Diskursräume ---
# Kategorien nach Benjamin: "deutsche, erziehungswiss, digitale_kultur (mit/ohne Erz.),
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
