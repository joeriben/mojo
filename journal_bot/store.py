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


# --- Digest-Entry-Normalisierung -------------------------------------------
#
# Display-kritische Felder, die jede Render-Schicht (Web, Markdown, Obsidian,
# Zotero) direkt vom agent_entry liest. Der Agent — besonders Gemini 3.5 Flash
# — lässt `kernthese` im submit_digest_entry-Tool-Call gelegentlich weg, obwohl
# das Tool-Schema es als `required` führt (siehe journal_bot/agent.py TOOLS).
# Templates greifen ungeschützt zu (`a.agent_entry.kernthese[:300]`), ein
# fehlender Key hat damit die ganze Digest-View mit einem 500 lahmgelegt.
# Statt dem Modell zu vertrauen, garantieren wir die Felder am Schreib-Choke-
# point (update_agent_result / set_attention_profile). Die Feldmenge spiegelt
# die `required`-Liste von submit_digest_entry.
_DIGEST_ENTRY_STR_FIELDS = ("kernthese", "verdict_begruendung", "theoretisch_methodisch")
_DIGEST_ENTRY_LIST_FIELDS = ("bezuege", "bemerkenswert")
# Listen-Felder, deren Items Strings sind (nicht Objekte). Bei diesen darf ein
# unparsbarer String verlustfrei als EINZELNE Notiz erhalten bleiben; bei
# Objekt-Listen (bezuege) ginge das nicht — die Templates rufen b.get(...).
_DIGEST_ENTRY_STRING_LIST_FIELDS = ("bemerkenswert",)


def _unwrap_single_note(s: str) -> str:
    """Schäle einen kaputten ['…']-Array-Wrapper zu einer lesbaren Notiz ab.

    Greift nur, wenn json.loads den String NICHT parsen konnte (z.B. weil das
    Modell ein inneres `"` nicht escaped hat). Entfernt eine äußere []-Klammer
    und äußere Anführungszeichen, damit die Notiz ohne JSON-Müll angezeigt wird.
    """
    s = s.strip()
    if len(s) >= 2 and s[0] == "[" and s[-1] == "]":
        s = s[1:-1].strip()
    if len(s) >= 2 and s[0] in "\"'" and s[-1] in "\"'":
        s = s[1:-1].strip()
    return s


def _coerce_to_list(v: Any, *, wrap_scalar: bool = False) -> list:
    """Bringe ein Listen-Feld auf eine echte Liste — verlustarm.

    Gemini serialisiert Listen-Felder gelegentlich als JSON-String
    ('["a", "b"]') statt als echtes Array. Wir parsen das zurück, damit der
    Inhalt überlebt — die Templates iterieren über diese Felder, ein roher
    String würde über die EINZELZEICHEN iterieren (latenter Display-Bug).

    `wrap_scalar=True` (nur für String-Item-Listen wie bemerkenswert): ein
    nicht-leerer, aber unparsbarer String (kaputtes/un-escaptes JSON) wird als
    EINZELNE Notiz erhalten statt verworfen. Bei Objekt-Listen (bezuege) bleibt
    es bei [] — ein String-Item würde die Templates (b.get(...)) sprengen.
    """
    if isinstance(v, list):
        return v
    if isinstance(v, str) and v.strip():
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        if wrap_scalar:
            note = _unwrap_single_note(v)
            return [note] if note else []
    return []


def _derive_kernthese(entry: dict) -> str:
    """Best-effort kernthese aus den Feldern, die der Agent tatsächlich gefüllt hat.

    Priorität nach Register-Nähe zur kernthese (deskriptiv, was der Artikel
    behandelt): `theoretisch_methodisch` (deskriptiv, in der Praxis bei allen
    fehlenden Fällen vorhanden) → erstes `bemerkenswert` → `verdict_begruendung`
    (evaluativ, daher letzte Wahl).
    """
    tm = entry.get("theoretisch_methodisch")
    if isinstance(tm, str) and tm.strip():
        return tm.strip()
    bem = entry.get("bemerkenswert") or []
    if bem and isinstance(bem[0], str) and bem[0].strip():
        return bem[0].strip()
    vb = entry.get("verdict_begruendung")
    if isinstance(vb, str) and vb.strip():
        return vb.strip()
    return ""


def normalize_digest_entry(entry: Any) -> dict:
    """Garantiert alle display-kritischen Keys eines agent_entry. Idempotent.

    - Stellt die drei String- und zwei Listen-Felder mit sicheren, korrekt
      typisierten Defaults bereit (fehlend/None/falscher Typ → "" bzw. []).
    - Ist `kernthese` leer/fehlend, wird sie lokal aus den vom Agenten
      gefüllten Feldern rekonstruiert (siehe _derive_kernthese). KEIN
      LLM-Repair-Call → keine zusätzlichen API-Kosten (vgl. CLAUDE.md
      Kostenregel).

    Mutiert und liefert dasselbe Dict zurück (Vertrag wie der bisherige
    _normalize_agent_entry in web/app.py). Nicht-Dict-Input ergibt ein frisches
    Default-Dict. Bestehende, nicht-leere Werte bleiben unangetastet.
    """
    if not isinstance(entry, dict):
        entry = {}
    for f in _DIGEST_ENTRY_STR_FIELDS:
        v = entry.get(f)
        if not isinstance(v, str):
            entry[f] = "" if v is None else str(v)
    for f in _DIGEST_ENTRY_LIST_FIELDS:
        if not isinstance(entry.get(f), list):
            entry[f] = _coerce_to_list(
                entry.get(f), wrap_scalar=(f in _DIGEST_ENTRY_STRING_LIST_FIELDS)
            )
    if not entry["kernthese"].strip():
        entry["kernthese"] = _derive_kernthese(entry)
    return entry


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
    selection_mode      TEXT,
    discourse_indicator TEXT,
    signal_group        TEXT,
    suggested_subgroup  TEXT,
    suggested_subgroup_reason TEXT,
    suggested_subgroup_confidence REAL,

    -- User override (null = agrees with agent)
    user_verdict        TEXT,
    user_memo           TEXT,
    user_verdict_at     TEXT,

    -- Workflow
    archived_at         TEXT,
    zotero_key          TEXT          -- Zotero item key after export
);

CREATE INDEX IF NOT EXISTS idx_articles_journal     ON articles(journal_short);
CREATE INDEX IF NOT EXISTS idx_articles_year        ON articles(year);
CREATE INDEX IF NOT EXISTS idx_articles_processed   ON articles(agent_processed_at);
CREATE INDEX IF NOT EXISTS idx_articles_fetched_at  ON articles(fetched_at);
"""

MIGRATIONS = [
    # Add user verdict columns (idempotent)
    """
    ALTER TABLE articles ADD COLUMN selection_mode TEXT;
    """,
    """
    ALTER TABLE articles ADD COLUMN discourse_indicator TEXT;
    """,
    """
    ALTER TABLE articles ADD COLUMN signal_group TEXT;
    """,
    """
    ALTER TABLE articles ADD COLUMN suggested_subgroup TEXT;
    """,
    """
    ALTER TABLE articles ADD COLUMN suggested_subgroup_reason TEXT;
    """,
    """
    ALTER TABLE articles ADD COLUMN suggested_subgroup_confidence REAL;
    """,
    """
    ALTER TABLE articles ADD COLUMN user_verdict TEXT;
    """,
    """
    ALTER TABLE articles ADD COLUMN user_memo TEXT;
    """,
    """
    ALTER TABLE articles ADD COLUMN user_verdict_at TEXT;
    """,
    """
    ALTER TABLE articles ADD COLUMN archived_at TEXT;
    """,
    """
    ALTER TABLE articles ADD COLUMN zotero_key TEXT;
    """,
    """
    ALTER TABLE articles ADD COLUMN composed_entry_json TEXT;
    """,
    """
    ALTER TABLE articles ADD COLUMN algo_mc REAL;
    """,
    """
    ALTER TABLE articles ADD COLUMN algo_zone TEXT;
    """,
]


def make_article_id(
    doi: str | None,
    url: str | None,
    title: str,
    journal_short: str = "",
) -> str:
    """Stable id derived from (in priority): DOI, URL, then journal+title.

    DOI and URL are globally unique. Title alone is NOT — two journals can
    publish papers with the same title, and HTML feeds without DOI/URL would
    silently collapse them into one row. Falling back to journal_short+title
    keeps title-only IDs at least journal-disjoint, which is the right
    granularity for MOJO (one journal-issue = one entry).

    Older callers that don't pass journal_short keep their previous id, so
    this is backward compatible for the existing DB.
    """
    doi_key = (doi or "").strip().lower()
    if doi_key:
        return hashlib.sha256(doi_key.encode("utf-8")).hexdigest()[:32]
    url_key = (url or "").strip().lower()
    if url_key:
        return hashlib.sha256(url_key.encode("utf-8")).hexdigest()[:32]
    title_key = (title or "").strip().lower()
    if journal_short:
        title_key = f"{journal_short.strip().lower()}::{title_key}"
    return hashlib.sha256(title_key.encode("utf-8")).hexdigest()[:32]


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
    selection_mode: str = ""
    discourse_indicator: str = ""
    signal_group: str = ""
    suggested_subgroup: str = ""
    suggested_subgroup_reason: str = ""
    suggested_subgroup_confidence: float = 0.0

    # User override
    user_verdict: str = ""
    user_memo: str = ""
    user_verdict_at: str = ""

    # Workflow
    archived_at: str = ""
    zotero_key: str = ""

    # MOJO 2.0: substitutiver Eintrag (entry_composer, rein algorithmisch)
    composed_entry: dict | None = None

    # MOJO 2.0: M-E-Ranker-Score der Welle (journal_bot/ranker.py) — für
    # Nachkalibrierung auf dem Produktions-Strom (iter_48-Caveat)
    algo_mc: float | None = None
    algo_zone: str = ""

    @property
    def effective_verdict(self) -> str:
        return self.user_verdict or self.agent_verdict

    @property
    def is_archived(self) -> bool:
        return bool(self.archived_at)


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
        selection_mode: str = "",
        discourse_indicator: str = "",
        signal_group: str = "",
        suggested_subgroup: str = "",
        suggested_subgroup_reason: str = "",
        suggested_subgroup_confidence: float = 0.0,
    ) -> None:
        # Guarantee display-critical fields before persisting — the agent may
        # have omitted `kernthese`. This is the single write choke point for
        # agent results (CLI batch_digest + web deepen both route here), so
        # normalizing here keeps every downstream renderer (web, markdown,
        # Obsidian, Zotero) safe at the source.
        entry = normalize_digest_entry(entry)
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
                    iterations = ?,
                    selection_mode = ?,
                    discourse_indicator = ?,
                    signal_group = ?,
                    suggested_subgroup = ?,
                    suggested_subgroup_reason = ?,
                    suggested_subgroup_confidence = ?
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
                    selection_mode or None,
                    discourse_indicator or None,
                    signal_group or None,
                    suggested_subgroup or None,
                    suggested_subgroup_reason or None,
                    suggested_subgroup_confidence or None,
                    article_id,
                ),
            )

    def update_composed_entry(self, article_id: str, composed: dict | None) -> None:
        """MOJO 2.0: substitutiven Eintrag persistieren (additiv, berührt weder
        Verdikte noch agent_entry_json). None löscht den komponierten Stand."""
        with self._conn() as c:
            c.execute(
                "UPDATE articles SET composed_entry_json = ? WHERE id = ?",
                (
                    json.dumps(composed, ensure_ascii=False) if composed else None,
                    article_id,
                ),
            )

    def update_ranker_score(
        self, article_id: str, mc: float | None, zone: str
    ) -> None:
        """MOJO 2.0: M-E-Score der Welle persistieren (nur Sortier-/Zonen-
        Metadatum, nie ein Verdikt)."""
        with self._conn() as c:
            c.execute(
                "UPDATE articles SET algo_mc = ?, algo_zone = ? WHERE id = ?",
                (mc, zone or None, article_id),
            )

    def set_archived(self, article_id: str, archived: bool = True) -> None:
        ts = datetime.now(timezone.utc).isoformat() if archived else None
        with self._conn() as c:
            c.execute(
                "UPDATE articles SET archived_at = ? WHERE id = ?",
                (ts, article_id),
            )

    def set_zotero_key(self, article_id: str, zotero_key: str) -> None:
        with self._conn() as c:
            c.execute(
                "UPDATE articles SET zotero_key = ? WHERE id = ?",
                (zotero_key, article_id),
            )

    def set_attention_profile(
        self,
        article_id: str,
        *,
        selection_mode: str = "",
        discourse_indicator: str = "",
        signal_group: str = "",
        suggested_subgroup: str = "",
        suggested_subgroup_reason: str = "",
        suggested_subgroup_confidence: float = 0.0,
        entry: dict | None = None,
    ) -> None:
        with self._conn() as c:
            if entry is None:
                c.execute(
                    """
                    UPDATE articles SET
                        selection_mode = ?,
                        discourse_indicator = ?,
                        signal_group = ?,
                        suggested_subgroup = ?,
                        suggested_subgroup_reason = ?,
                        suggested_subgroup_confidence = ?
                    WHERE id = ?
                    """,
                    (
                        selection_mode or None,
                        discourse_indicator or None,
                        signal_group or None,
                        suggested_subgroup or None,
                        suggested_subgroup_reason or None,
                        suggested_subgroup_confidence or None,
                        article_id,
                    ),
                )
            else:
                # Same guarantee as update_agent_result: never persist an
                # agent_entry that is missing display-critical fields.
                entry = normalize_digest_entry(entry)
                c.execute(
                    """
                    UPDATE articles SET
                        selection_mode = ?,
                        discourse_indicator = ?,
                        signal_group = ?,
                        suggested_subgroup = ?,
                        suggested_subgroup_reason = ?,
                        suggested_subgroup_confidence = ?,
                        agent_entry_json = ?
                    WHERE id = ?
                    """,
                    (
                        selection_mode or None,
                        discourse_indicator or None,
                        signal_group or None,
                        suggested_subgroup or None,
                        suggested_subgroup_reason or None,
                        suggested_subgroup_confidence or None,
                        json.dumps(entry, ensure_ascii=False),
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
        end_year: int | None = None,
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
        if end_year is not None:
            sql += " AND year <= ?"
            params.append(end_year)
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
        selection_mode=row["selection_mode"] or "",
        discourse_indicator=row["discourse_indicator"] or "",
        signal_group=row["signal_group"] or "",
        suggested_subgroup=row["suggested_subgroup"] or "",
        suggested_subgroup_reason=row["suggested_subgroup_reason"] or "",
        suggested_subgroup_confidence=row["suggested_subgroup_confidence"] or 0.0,
        user_verdict=row["user_verdict"] or "",
        user_memo=row["user_memo"] or "",
        user_verdict_at=row["user_verdict_at"] or "",
        archived_at=row["archived_at"] or "",
        zotero_key=row["zotero_key"] or "",
        composed_entry=_j("composed_entry_json", None),
        algo_mc=row["algo_mc"],
        algo_zone=row["algo_zone"] or "",
    )
