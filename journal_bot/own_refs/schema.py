"""SQLite-Schema für `own_refs.db`.

Drei Tabellen:
- `publications`: eine Zeile pro eindeutiger eigener Publikation
  (`canonical_id`). Identität: DOI bevorzugt, sonst Hash aus
  title+year+first_author_lastname.
- `source_refs`: Provenienz, n-zu-1 zu `publications`. Eine Pub kann aus
  Zotero UND aus einem Folder gleichzeitig stammen — beide Einträge bleiben
  erhalten, nichts wird überschrieben.
- `pub_refs`: Refs OUT einer Publikation. Drei Resolution-States:
  doi_resolved / doi_unresolved / text_unresolved / text_resolved — damit
  Phase-2-Resolution (Free-Text → OpenAlex-Search) später ohne Schema-
  Migration nachgezogen werden kann.

Schema-Version wird in einer `schema_version`-Tabelle festgehalten, damit
spätere Migrationen idempotent eingreifen können.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

DDL_V1 = """
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publications (
    canonical_id            TEXT PRIMARY KEY,
    doi                     TEXT,
    title                   TEXT NOT NULL,
    year                    INTEGER,
    item_type               TEXT,
    venue                   TEXT,
    authors_json            TEXT NOT NULL,
    discourse_json          TEXT,
    fulltext_path           TEXT,
    fulltext_chars          INTEGER DEFAULT 0,
    fulltext_extracted_at   TEXT,
    refs_extracted_at       TEXT,
    refs_header_label       TEXT,
    refs_used_fallback      INTEGER DEFAULT 0,
    last_seen_at            TEXT NOT NULL,
    notes_json              TEXT
);

CREATE INDEX IF NOT EXISTS idx_publications_doi  ON publications(doi);
CREATE INDEX IF NOT EXISTS idx_publications_year ON publications(year);

CREATE TABLE IF NOT EXISTS source_refs (
    canonical_id            TEXT NOT NULL,
    source_type             TEXT NOT NULL,
    source_key              TEXT NOT NULL,
    source_item_id          TEXT NOT NULL,
    pdf_path                TEXT,
    pdf_mtime               REAL,
    zotero_date_modified    TEXT,
    match_score             REAL,
    first_seen_at           TEXT NOT NULL,
    last_seen_at            TEXT NOT NULL,
    PRIMARY KEY (canonical_id, source_type, source_key, source_item_id),
    FOREIGN KEY (canonical_id) REFERENCES publications(canonical_id)
);

CREATE INDEX IF NOT EXISTS idx_source_refs_source ON source_refs(source_type, source_key);

CREATE TABLE IF NOT EXISTS pub_refs (
    canonical_id        TEXT NOT NULL,
    ref_id              TEXT NOT NULL,
    ref_doi             TEXT,
    ref_oa_id           TEXT,
    ref_year            INTEGER,
    ref_text            TEXT,
    resolution_state    TEXT NOT NULL,
    resolved_at         TEXT,
    PRIMARY KEY (canonical_id, ref_id),
    FOREIGN KEY (canonical_id) REFERENCES publications(canonical_id)
);

CREATE INDEX IF NOT EXISTS idx_pub_refs_oa_id ON pub_refs(ref_oa_id);
CREATE INDEX IF NOT EXISTS idx_pub_refs_doi   ON pub_refs(ref_doi);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    """Open the DB, ensure schema is at SCHEMA_VERSION.

    Idempotent: no-op if schema already present.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(DDL_V1)
    current = con.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    if current is None:
        con.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, datetime('now'))",
            (SCHEMA_VERSION,),
        )
        con.commit()
    return con
