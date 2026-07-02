"""Bezugsautoren-DB — Autor-Ebenen-Basis für den grounded Abgleich.

Idee (Benjamin 2026-05-30): Der grounded Werk-Abgleich auf Artikel-Ebene
scheitert an dünnen Referenzlisten (ein Artikel mit 13 Refs koppelt schwach).
Robuster ist die AUTOR-Ebene: Für den Erstautor eines Kandidaten-Artikels
ziehen wir aus OpenAlex seine **10 neuesten + 10 meistzitierten** Werke
(Union, dedupliziert) samt deren Referenzen und koppeln dieses breitere
Footprint gegen Benjamins Korpus (own_refs.db).

  - neueste 10   → aktuelle Forschungsrichtung
  - meistzit. 10 → Kern-/Referenzwerke des Autors

Persistent + erweiterbar (SQLite `bezugsautoren.db`): Autoren/Werke werden
idempotent ge-upsertet; spätere Läufe ergänzen weitere Autoren, ohne Bestehendes
zu verlieren. Kein LLM. OpenAlex Polite-Pool mit Throttle.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from journal_bot.settings import OPENALEX_MAILTO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = PROJECT_ROOT / "bezugsautoren.db"

# Polite Pool nur mit ECHTER Kontakt-Mail (profile.json "openalex_mailto");
# Fake-Mailtos provozieren Rate-Limits (Vorfall 2026-07-02: 429 auf allen
# Werk-Listen-Queries ab ~500 Autoren, still als leere Œuvres gespeichert).
USER_AGENT = "mojo/2.0 bezugsautoren" + (
    f" (mailto:{OPENALEX_MAILTO})" if OPENALEX_MAILTO else ""
)
THROTTLE_SECONDS = 0.12
# Backoff-Stufen für 429/5xx; Retry-After-Header wird bevorzugt (Cap 120 s)
RETRY_SLEEPS = (1.0, 4.0, 16.0, 60.0)


class WorksFetchError(RuntimeError):
    """Werk-Listen-Query endgültig gescheitert (z. B. anhaltendes 429).

    Wird geworfen statt still ein leeres Œuvre zu speichern — der Aufrufer
    entscheidet (Retry später / lauter Abbruch), der Bestand bleibt sauber.
    """
# N kalibriert (scripts/bezugsautoren_sensitivity2.py): Sättigung ~30, darüber
# nur noch Zufallszuwachs. 10 neueste + 10 meistzit. war zu früh abgeschnitten.
RECENT_N = 30
CITED_N = 30
WORK_SELECT = "id,title,doi,publication_year,cited_by_count,referenced_works"

SCHEMA_VERSION = "1"


def _bare(oa_id: str | None) -> str:
    return (oa_id or "").rstrip("/").rsplit("/", 1)[-1].strip()


# ── DB ──────────────────────────────────────────────────────────────────────

def init_db(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_version (version TEXT, applied_at TEXT);
        CREATE TABLE IF NOT EXISTS authors (
            author_oa_id   TEXT PRIMARY KEY,
            display_name   TEXT,
            works_count    INTEGER,
            cited_by_count INTEGER,
            n_works_fetched INTEGER,
            last_refreshed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS author_works (
            author_oa_id   TEXT,
            work_oa_id     TEXT,
            title          TEXT,
            doi            TEXT,
            publication_year INTEGER,
            cited_by_count INTEGER,
            referenced_works_json TEXT,
            n_refs         INTEGER,
            selection      TEXT,            -- 'recent' | 'cited' | 'both'
            fetched_at     TEXT,
            PRIMARY KEY (author_oa_id, work_oa_id)
        );
        CREATE TABLE IF NOT EXISTS author_seed (
            author_oa_id   TEXT,
            article_id     TEXT,
            role           TEXT,            -- 'first_author'
            first_seen_at  TEXT,
            PRIMARY KEY (author_oa_id, article_id)
        );
        CREATE INDEX IF NOT EXISTS idx_aw_author ON author_works(author_oa_id);
        CREATE INDEX IF NOT EXISTS idx_aw_work   ON author_works(work_oa_id);
        """
    )
    if not con.execute("SELECT 1 FROM schema_version").fetchone():
        con.execute("INSERT INTO schema_version VALUES (?, datetime('now'))", (SCHEMA_VERSION,))
    con.commit()


def author_exists(con: sqlite3.Connection, author_oa_id: str) -> bool:
    return con.execute(
        "SELECT 1 FROM authors WHERE author_oa_id=? AND last_refreshed_at IS NOT NULL",
        (author_oa_id,),
    ).fetchone() is not None


# ── OpenAlex ────────────────────────────────────────────────────────────────

def make_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30.0)


def fetch_first_author(client: httpx.Client, work_oa_id: str) -> tuple[str, str] | None:
    """Work-OA-ID → (author_oa_id, display_name) des Erstautors."""
    wid = _bare(work_oa_id)
    if not wid.startswith("W"):
        return None
    try:
        r = client.get(f"https://api.openalex.org/works/{wid}",
                       params={"select": "authorships"})
        r.raise_for_status()
        auths = r.json().get("authorships") or []
    except httpx.HTTPError:
        return None
    if not auths:
        return None
    a = auths[0].get("author") or {}
    aid = _bare(a.get("id"))
    if not aid.startswith("A"):
        return None
    return aid, a.get("display_name") or ""


def _fetch_works_sorted(client: httpx.Client, author_oa_id: str, sort: str,
                        per_page: int) -> tuple[list[dict], int]:
    """Werk-Liste mit Retry/Backoff; wirft WorksFetchError statt still [] zu
    liefern (429/5xx werden mit Retry-After respektiert)."""
    last_exc: Exception | None = None
    for attempt in range(len(RETRY_SLEEPS) + 1):
        try:
            r = client.get("https://api.openalex.org/works", params={
                "filter": f"author.id:{author_oa_id}",
                "sort": sort, "per-page": per_page, "select": WORK_SELECT,
            })
            if r.status_code in (429, 500, 502, 503) and attempt < len(RETRY_SLEEPS):
                wait = RETRY_SLEEPS[attempt]
                try:
                    wait = max(wait, float(r.headers.get("Retry-After") or 0))
                except ValueError:
                    pass
                time.sleep(min(wait, 120.0))
                continue
            r.raise_for_status()
            j = r.json()
            return j.get("results", []), int(j.get("meta", {}).get("count") or 0)
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt < len(RETRY_SLEEPS):
                time.sleep(RETRY_SLEEPS[attempt])
    raise WorksFetchError(
        f"OpenAlex-Werk-Query für {author_oa_id} gescheitert: {last_exc}"
    )


def fetch_author_works(client: httpx.Client, author_oa_id: str
                       ) -> tuple[dict[str, dict], int]:
    """10 neueste ∪ 10 meistzitierte Werke; markiert 'recent'/'cited'/'both'.

    Wirft WorksFetchError, wenn eine der beiden Listen endgültig scheitert —
    lieber gar nicht speichern als ein leeres/halbes Œuvre als „fertig" markieren.
    """
    recent, total = _fetch_works_sorted(client, author_oa_id, "publication_date:desc", RECENT_N)
    time.sleep(THROTTLE_SECONDS)
    cited, _ = _fetch_works_sorted(client, author_oa_id, "cited_by_count:desc", CITED_N)
    recent_ids = {_bare(w.get("id")) for w in recent}
    cited_ids = {_bare(w.get("id")) for w in cited}
    merged: dict[str, dict] = {}
    for w in recent + cited:
        wid = _bare(w.get("id"))
        if not wid:
            continue
        in_r, in_c = wid in recent_ids, wid in cited_ids
        sel = "both" if (in_r and in_c) else ("recent" if in_r else "cited")
        w["_selection"] = sel
        merged[wid] = w
    return merged, total


# ── Build ───────────────────────────────────────────────────────────────────

@dataclass
class BuildResult:
    author_oa_id: str
    display_name: str
    n_works: int
    cached: bool


def build_for_article(con: sqlite3.Connection, client: httpx.Client,
                      article_id: str, work_oa_id: str,
                      force: bool = False) -> BuildResult | None:
    """Erstautor auflösen, Werke ziehen, idempotent speichern."""
    fa = fetch_first_author(client, work_oa_id)
    time.sleep(THROTTLE_SECONDS)
    if fa is None:
        return None
    aid, name = fa

    # Seed-Provenienz immer verlinken
    con.execute(
        "INSERT OR IGNORE INTO author_seed VALUES (?,?,?,datetime('now'))",
        (aid, article_id, "first_author"),
    )

    if author_exists(con, aid) and not force:
        con.commit()
        n = con.execute("SELECT count(*) FROM author_works WHERE author_oa_id=?", (aid,)).fetchone()[0]
        return BuildResult(aid, name, n, cached=True)

    n = _store_author(con, client, aid, name)
    return BuildResult(aid, name, n, cached=False)


def _store_author(con: sqlite3.Connection, client: httpx.Client,
                  aid: str, name: str = "") -> int:
    """Werke des Autors ziehen (10+10 bzw. RECENT_N+CITED_N) und upserten."""
    works, total = fetch_author_works(client, aid)
    time.sleep(THROTTLE_SECONDS)
    # Alte Werke des Autors ersetzen (sauberer Refresh bei geändertem N)
    con.execute("DELETE FROM author_works WHERE author_oa_id=?", (aid,))
    for wid, w in works.items():
        refs = [_bare(x) for x in (w.get("referenced_works") or []) if x]
        con.execute(
            "INSERT OR REPLACE INTO author_works VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
            (aid, wid, w.get("title"), (w.get("doi") or "").replace("https://doi.org/", ""),
             w.get("publication_year"), w.get("cited_by_count"),
             json.dumps(refs), len(refs), w.get("_selection")),
        )
    con.execute(
        "INSERT OR REPLACE INTO authors VALUES (?,?,?,?,?,datetime('now'))",
        (aid, name, total,
         max((w.get("cited_by_count") or 0) for w in works.values()) if works else 0,
         len(works)),
    )
    con.commit()
    return len(works)


def refresh_author(con: sqlite3.Connection, client: httpx.Client,
                   author_oa_id: str, force: bool = True) -> int:
    """Bekannten Autor (per OA-ID) neu ziehen — für N-Wechsel/Refresh."""
    aid = _bare(author_oa_id)
    if not force and author_exists(con, aid):
        return con.execute("SELECT count(*) FROM author_works WHERE author_oa_id=?",
                           (aid,)).fetchone()[0]
    name = ""
    row = con.execute("SELECT display_name FROM authors WHERE author_oa_id=?", (aid,)).fetchone()
    if row and row[0]:
        name = row[0]
    return _store_author(con, client, aid, name)


# IDF-Schwellen für die Autor-Kopplung, kalibriert gegen Null-Kontrolle
# (scripts/bezugsautoren_idf.py): binär ≥1 koppelt 39 % unbeteiligter Autoren
# (Zufallsboden aus Allerwelts-Refs). WEAK=1.0 drückt die Kontrolle auf 14 %,
# STRONG=3.0 auf 5.7 %. corroborated (exakt benanntes Werk) ist schwellen-unabhängig.
AUTHOR_COUPLING_WEAK = 1.0
AUTHOR_COUPLING_STRONG = 3.0


def coupling_idf(shared_oa, corpus_freq) -> float:
    """IDF-gewichtete Kopplungsstärke über geteilte OA-Refs (Allerwelts-Refs ~0).

    Spiegelt signal_own_coupling: häufige Refs (corpus_freq hoch) zählen wenig,
    seltene/spezifische schwer. Drückt den Zufallsboden (~40 % via binär ≥1) weg.
    """
    if corpus_freq is None or getattr(corpus_freq, "is_empty", False):
        return float(len(shared_oa))
    return float(sum(corpus_freq.idf_weight_oa(h) for h in shared_oa))


def author_ref_set(con: sqlite3.Connection, author_oa_id: str) -> set[str]:
    """Aggregierte OA-Referenzen über alle gespeicherten Werke des Autors."""
    refs: set[str] = set()
    for (rj,) in con.execute(
        "SELECT referenced_works_json FROM author_works WHERE author_oa_id=?",
        (author_oa_id,),
    ):
        if rj:
            try:
                refs.update(json.loads(rj))
            except json.JSONDecodeError:
                pass
    refs.discard("")
    return refs
