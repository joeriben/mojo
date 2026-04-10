"""Deduplizierungs-State — SQLite, hashed auf DOI oder URL."""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS seen (
    fingerprint TEXT PRIMARY KEY,
    journal     TEXT NOT NULL,
    title       TEXT NOT NULL,
    url         TEXT,
    doi         TEXT,
    seen_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_seen_journal ON seen(journal);
"""


def fingerprint(doi: str | None, url: str | None, title: str) -> str:
    """Stabiler Hash: bevorzugt DOI, dann URL, sonst Titel."""
    key = (doi or url or title).strip().lower()
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class State:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def is_seen(self, fp: str) -> bool:
        with self._conn() as c:
            row = c.execute("SELECT 1 FROM seen WHERE fingerprint = ?", (fp,)).fetchone()
            return row is not None

    def mark_seen(
        self, fp: str, journal: str, title: str, url: str | None, doi: str | None
    ) -> None:
        with self._conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO seen (fingerprint, journal, title, url, doi, seen_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (fp, journal, title, url, doi, datetime.now(timezone.utc).isoformat()),
            )

    def count(self) -> int:
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM seen").fetchone()[0]
