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
# Die `clusters`-Zuordnungen sind ein ERSTER VORSCHLAG. Bitte prüfen und anpassen.
# Mehrfach-Zuordnung ist erlaubt und sinnvoll (z.B. ZfE = deutsche + erziehungswiss).

JOURNALS: list[JournalConfig] = [
    # --- RSS/OJS-native Feeds ---
    JournalConfig(
        name="Zeitschrift für Erziehungswissenschaft", short="ZfE", type="rss",
        url="https://link.springer.com/search.rss?facet-journal-id=11618&facet-content-type=Article",
        clusters=["deutsche", "erziehungswiss"],
    ),
    JournalConfig(
        name="MedienPädagogik (medienpaed.com)", short="MedienPaed", type="ojs",
        url="https://www.medienpaed.com/gateway/plugin/WebFeedGatewayPlugin/rss2",
        clusters=["deutsche", "medienpaed", "aesthetische_kulturelle_bildung"],
    ),

    # --- Englischsprachige Kern-Journals via OpenAlex ---
    JournalConfig(
        name="Postdigital Science and Education", short="PDSE", type="openalex",
        url="issn:2524-485X",
        clusters=["digitale_kultur", "medienpaed", "bildungstheorie"],
    ),
    JournalConfig(
        name="Educational Philosophy and Theory", short="EPT", type="openalex",
        url="issn:0013-1857",
        clusters=["bildungstheorie"],
    ),
    JournalConfig(
        name="Educational Theory", short="EduTheory", type="openalex",
        url="issn:1741-5446",
        clusters=["bildungstheorie"],
    ),
    JournalConfig(
        name="AI & Society", short="AIandSoc", type="openalex",
        url="issn:0951-5666",
        clusters=["digitale_kultur"],
    ),
    JournalConfig(
        name="Learning, Media and Technology", short="LMT", type="openalex",
        url="issn:1743-9884",
        clusters=["digitale_kultur", "medienpaed"],
    ),
    JournalConfig(
        name="Pedagogy, Culture & Society", short="PCS", type="openalex",
        url="issn:1468-1366",
        clusters=["erziehungswiss", "bildungstheorie"],
    ),
    JournalConfig(
        name="Discourse: Studies in the Cultural Politics of Education",
        short="Discourse", type="openalex",
        url="issn:0159-6306",
        clusters=["erziehungswiss"],
    ),
    JournalConfig(
        name="European Educational Research Journal", short="EERJ", type="openalex",
        url="issn:1474-9041",
        clusters=["erziehungswiss"],
    ),
    JournalConfig(
        name="Journal of Research on Technology in Education",
        short="JRTE", type="openalex",
        url="issn:1539-1523",
        clusters=["erziehungswiss", "digitale_kultur"],
    ),
    JournalConfig(
        name="Journal of Transformative Education", short="JTE", type="openalex",
        url="issn:1552-7840",
        clusters=["bildungstheorie", "resilienz"],
    ),
    JournalConfig(
        name="The Journal of Environmental Education", short="JEE", type="openalex",
        url="issn:0095-8964",
        clusters=["resilienz"],
    ),
    JournalConfig(
        name="Diaspora, Indigenous, and Minority Education",
        short="DIME", type="openalex",
        url="issn:1559-5692",
        clusters=["erziehungswiss"],
    ),
    JournalConfig(
        name="Digital Culture & Education", short="DCE", type="openalex",
        url="issn:1836-8301",
        clusters=["digitale_kultur"],
    ),
    JournalConfig(
        name="Digital Culture & Society", short="DCS", type="openalex",
        url="issn:2364-2122",
        clusters=["digitale_kultur"],
    ),
    JournalConfig(
        name="Journal of Aesthetic Education", short="JAE", type="openalex",
        url="issn:0021-8510",
        clusters=["bildungstheorie", "aesthetische_kulturelle_bildung"],
    ),
    JournalConfig(
        name="Resilience: A Journal of the Environmental Humanities",
        short="Resilience", type="openalex",
        url="issn:2330-8117",
        clusters=["resilienz"],
    ),

    # --- Deutschsprachige Journals via OpenAlex ---
    JournalConfig(
        name="Journal for Educational Research Online",
        short="JERO", type="openalex",
        url="issn:1866-6671",
        clusters=["deutsche", "erziehungswiss"],
    ),
    JournalConfig(
        name="merz | medien + erziehung", short="merz", type="openalex",
        url="issn:0176-4918",
        clusters=["deutsche", "medienpaed", "aesthetische_kulturelle_bildung"],
    ),

    # --- Sonderfälle (Scraper fehlen) ---
    # zkmb — Zeitschrift Kunst Medien Bildung (issn:2193-2980, nicht in OpenAlex)
    # e-flux Journal (issn:2164-1625, nicht in OpenAlex, stabile /journal/<nr>/ Struktur)
]

# Apply cluster overrides from diskursraeume.json (if loaded)
if _JOURNAL_CLUSTERS:
    _short_to_journal = {j.short: j for j in JOURNALS}
    for _short, _clusters in _JOURNAL_CLUSTERS.items():
        if _short in _short_to_journal:
            _short_to_journal[_short].clusters = list(_clusters)
