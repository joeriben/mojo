"""articles.db — Source of Truth für alle gesichteten Journalbeiträge.

Schema-Philosophie:
- Eine Zeile pro Artikel (stable ID = sha256 von doi/url/title)
- Fetch-Zeit: Metadaten + OpenAlex/Crossref-Enrichment werden eingetragen
- Agent-Zeit: agent_verdict, agent_entry, citation_hits, token-/cost-Spalten werden befüllt
- Trend-Zeit: nur gelesen, niemals geschrieben

Format-agnostisch: Obsidian-Markdown, Zotero-Export etc. sind abgesetzte Render-Schichten.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from journal_bot.settings import PROJECT_ROOT


ARTICLES_DB = PROJECT_ROOT / "articles.db"


SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id                  TEXT PRIMARY KEY,
    journal_short       TEXT NOT NULL,
    journal_full        TEXT,
    title               TEXT NOT NULL,
    authors_json        TEXT,        -- JSON array of strings
    abstract            TEXT,
    doi                 TEXT,
    url                 TEXT,
    year                INTEGER,
    published           TEXT,        -- wie im Feed geliefert
    fetched_at          TEXT NOT NULL,

    -- Enrichment (nach fetch)
    openalex_id         TEXT,
    openalex_abstract   TEXT,
    openalex_concepts   TEXT,        -- JSON
    openalex_topics     TEXT,        -- JSON
    openalex_refs       TEXT,        -- JSON array of ids
    crossref_refs       TEXT,        -- JSON array of ref dicts
    enrichment_status   TEXT,        -- "ok" | "no_doi" | "failed" | null

    -- Agent (nach digest, null solange ungeprozessiert)
    agent_processed_at  TEXT,
    agent_verdict       TEXT,
    agent_entry_json    TEXT,        -- kompletter submit_digest_entry
    citation_hits_json  TEXT,
    tokens_in           INTEGER,
    tokens_out          INTEGER,
    tokens_cached_read  INTEGER,
    tokens_cache_write  INTEGER,
    cost_usd            REAL,
    iterations          INTEGER,

    -- User override (null = agrees with agent)
    user_verdict        TEXT,
    user_memo           TEXT,
    user_verdict_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_articles_journal     ON articles(journal_short);
CREATE INDEX IF NOT EXISTS idx_articles_year        ON articles(year);
CREATE INDEX IF NOT EXISTS idx_articles_processed   ON articles(agent_processed_at);
CREATE INDEX IF NOT EXISTS idx_articles_fetched_at  ON articles(fetched_at);
"""

MIGRATIONS = [
    # Add user verdict columns (idempotent)
    """
    ALTER TABLE articles ADD COLUMN user_verdict TEXT;
    """,
    """
    ALTER TABLE articles ADD COLUMN user_memo TEXT;
    """,
    """
    ALTER TABLE articles ADD COLUMN user_verdict_at TEXT;
    """,
]


def make_article_id(doi: str | None, url: str | None, title: str) -> str:
    key = (doi or url or title or "").strip().lower()
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


@dataclass
class StoredArticle:
    id: str
    journal_short: str
    journal_full: str
    title: str
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    doi: str = ""
    url: str = ""
    year: int | None = None
    published: str = ""
    fetched_at: str = ""

    # Enrichment
    openalex_id: str = ""
    openalex_abstract: str = ""
    openalex_concepts: list[dict] = field(default_factory=list)
    openalex_topics: list[dict] = field(default_factory=list)
    openalex_refs: list[str] = field(default_factory=list)
    crossref_refs: list[dict] = field(default_factory=list)
    enrichment_status: str = ""

    # Agent
    agent_processed_at: str = ""
    agent_verdict: str = ""
    agent_entry: dict | None = None
    citation_hits: list[dict] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    tokens_cached_read: int = 0
    tokens_cache_write: int = 0
    cost_usd: float = 0.0
    iterations: int = 0

    # User override
    user_verdict: str = ""
    user_memo: str = ""
    user_verdict_at: str = ""

    @property
    def effective_verdict(self) -> str:
        return self.user_verdict or self.agent_verdict


class Store:
    def __init__(self, path: Path = ARTICLES_DB) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(SCHEMA)
            self._migrate(c)

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        existing = {
            row[1] for row in conn.execute("PRAGMA table_info(articles)").fetchall()
        }
        for stmt in MIGRATIONS:
            col = stmt.strip().split()[-2].rstrip(";")  # extract column name
            if col not in existing:
                conn.execute(stmt)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------- Schreiben --

    def exists(self, article_id: str) -> bool:
        with self._conn() as c:
            row = c.execute("SELECT 1 FROM articles WHERE id = ?", (article_id,)).fetchone()
            return row is not None

    def upsert_article(self, article: StoredArticle) -> bool:
        """Fügt einen Artikel ein (oder aktualisiert Metadaten/Enrichment).

        Rückgabe: True wenn neu, False wenn existierte.
        """
        is_new = not self.exists(article.id)
        if not article.fetched_at:
            article.fetched_at = datetime.now(timezone.utc).isoformat()

        payload = {
            "id": article.id,
            "journal_short": article.journal_short,
            "journal_full": article.journal_full,
            "title": article.title,
            "authors_json": json.dumps(article.authors, ensure_ascii=False),
            "abstract": article.abstract,
            "doi": article.doi,
            "url": article.url,
            "year": article.year,
            "published": article.published,
            "fetched_at": article.fetched_at,
            "openalex_id": article.openalex_id,
            "openalex_abstract": article.openalex_abstract,
            "openalex_concepts": json.dumps(article.openalex_concepts, ensure_ascii=False),
            "openalex_topics": json.dumps(article.openalex_topics, ensure_ascii=False),
            "openalex_refs": json.dumps(article.openalex_refs, ensure_ascii=False),
            "crossref_refs": json.dumps(article.crossref_refs, ensure_ascii=False),
            "enrichment_status": article.enrichment_status,
        }
        cols = list(payload.keys())
        placeholders = ",".join(f":{c}" for c in cols)
        update_cols = ",".join(f"{c}=excluded.{c}" for c in cols if c != "id")

        with self._conn() as c:
            c.execute(
                f"INSERT INTO articles ({','.join(cols)}) VALUES ({placeholders}) "
                f"ON CONFLICT(id) DO UPDATE SET {update_cols}",
                payload,
            )
        return is_new

    def update_agent_result(
        self,
        article_id: str,
        *,
        verdict: str,
        entry: dict,
        citation_hits: list[dict],
        tokens_in: int,
        tokens_out: int,
        tokens_cached_read: int,
        tokens_cache_write: int,
        cost_usd: float,
        iterations: int,
    ) -> None:
        with self._conn() as c:
            c.execute(
                """
                UPDATE articles SET
                    agent_processed_at = ?,
                    agent_verdict = ?,
                    agent_entry_json = ?,
                    citation_hits_json = ?,
                    tokens_in = ?,
                    tokens_out = ?,
                    tokens_cached_read = ?,
                    tokens_cache_write = ?,
                    cost_usd = ?,
                    iterations = ?
                WHERE id = ?
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    verdict,
                    json.dumps(entry, ensure_ascii=False),
                    json.dumps(citation_hits, ensure_ascii=False),
                    tokens_in,
                    tokens_out,
                    tokens_cached_read,
                    tokens_cache_write,
                    cost_usd,
                    iterations,
                    article_id,
                ),
            )

    def set_user_verdict(
        self,
        article_id: str,
        *,
        verdict: str,
        memo: str = "",
    ) -> None:
        with self._conn() as c:
            c.execute(
                """
                UPDATE articles SET
                    user_verdict = ?,
                    user_memo = ?,
                    user_verdict_at = ?
                WHERE id = ?
                """,
                (
                    verdict or None,  # NULL = reset to agent verdict
                    memo or None,
                    datetime.now(timezone.utc).isoformat() if verdict else None,
                    article_id,
                ),
            )

    # --------------------------------------------------------------- Lesen ---

    def get(self, article_id: str) -> StoredArticle | None:
        with self._conn() as c:
            row = c.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
            return _row_to_article(row) if row else None

    def find_unprocessed(
        self,
        limit: int | None = None,
        journals: list[str] | None = None,
        since_year: int | None = None,
    ) -> list[StoredArticle]:
        sql = "SELECT * FROM articles WHERE (agent_processed_at IS NULL OR agent_processed_at = '')"
        params: list[Any] = []
        if journals:
            placeholders = ",".join("?" * len(journals))
            sql += f" AND journal_short IN ({placeholders})"
            params.extend(journals)
        if since_year is not None:
            sql += " AND year >= ?"
            params.append(since_year)
        sql += " ORDER BY year DESC, fetched_at DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        with self._conn() as c:
            rows = c.execute(sql, params).fetchall()
            return [_row_to_article(r) for r in rows]

    def find_in_window(
        self,
        start_year: int | None = None,
        end_year: int | None = None,
        journals: list[str] | None = None,
        only_processed: bool = False,
    ) -> list[StoredArticle]:
        sql = "SELECT * FROM articles WHERE 1=1"
        params: list[Any] = []
        if start_year is not None:
            sql += " AND year >= ?"
            params.append(start_year)
        if end_year is not None:
            sql += " AND year <= ?"
            params.append(end_year)
        if journals:
            placeholders = ",".join("?" * len(journals))
            sql += f" AND journal_short IN ({placeholders})"
            params.extend(journals)
        if only_processed:
            sql += " AND agent_processed_at IS NOT NULL"
        sql += " ORDER BY year DESC, fetched_at DESC"
        with self._conn() as c:
            rows = c.execute(sql, params).fetchall()
            return [_row_to_article(r) for r in rows]

    def stats(self) -> dict:
        with self._conn() as c:
            total = c.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            processed = c.execute(
                "SELECT COUNT(*) FROM articles WHERE agent_processed_at IS NOT NULL"
            ).fetchone()[0]
            by_journal = {
                r[0]: r[1]
                for r in c.execute(
                    "SELECT journal_short, COUNT(*) FROM articles GROUP BY journal_short"
                ).fetchall()
            }
            by_verdict = {
                r[0]: r[1]
                for r in c.execute(
                    "SELECT agent_verdict, COUNT(*) FROM articles "
                    "WHERE agent_verdict IS NOT NULL GROUP BY agent_verdict"
                ).fetchall()
            }
            total_cost = c.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM articles"
            ).fetchone()[0]
        return {
            "total": total,
            "processed": processed,
            "by_journal": by_journal,
            "by_verdict": by_verdict,
            "total_cost_usd": total_cost,
        }


def _row_to_article(row: sqlite3.Row) -> StoredArticle:
    def _j(key: str, default):
        v = row[key]
        if not v:
            return default
        try:
            return json.loads(v)
        except Exception:
            return default

    return StoredArticle(
        id=row["id"],
        journal_short=row["journal_short"],
        journal_full=row["journal_full"] or "",
        title=row["title"],
        authors=_j("authors_json", []),
        abstract=row["abstract"] or "",
        doi=row["doi"] or "",
        url=row["url"] or "",
        year=row["year"],
        published=row["published"] or "",
        fetched_at=row["fetched_at"] or "",
        openalex_id=row["openalex_id"] or "",
        openalex_abstract=row["openalex_abstract"] or "",
        openalex_concepts=_j("openalex_concepts", []),
        openalex_topics=_j("openalex_topics", []),
        openalex_refs=_j("openalex_refs", []),
        crossref_refs=_j("crossref_refs", []),
        enrichment_status=row["enrichment_status"] or "",
        agent_processed_at=row["agent_processed_at"] or "",
        agent_verdict=row["agent_verdict"] or "",
        agent_entry=_j("agent_entry_json", None),
        citation_hits=_j("citation_hits_json", []),
        tokens_in=row["tokens_in"] or 0,
        tokens_out=row["tokens_out"] or 0,
        tokens_cached_read=row["tokens_cached_read"] or 0,
        tokens_cache_write=row["tokens_cache_write"] or 0,
        cost_usd=row["cost_usd"] or 0.0,
        iterations=row["iterations"] or 0,
        user_verdict=row["user_verdict"] or "",
        user_memo=row["user_memo"] or "",
        user_verdict_at=row["user_verdict_at"] or "",
    )
