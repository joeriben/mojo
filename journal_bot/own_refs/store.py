"""SQLite-Schicht für `own_refs.db`: Dataclasses, UPSERT-Operations, Queries.

Alle UPSERT-Methoden sind idempotent: gleicher Aufruf zweimal → identischer
DB-Zustand, `last_seen_at` wird aktualisiert, `first_seen_at` bleibt.

Inverser Refs-Index (welche eigenen Pubs zitieren OpenAlex-ID X?) wird über
`pubs_citing_oa_id` als Query bedient, nicht als materialisierte Tabelle.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from journal_bot.own_refs.schema import connect


# ----------------------------- Dataclasses ----------------------------------


@dataclass
class Publication:
    canonical_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    doi: str | None = None
    year: int | None = None
    item_type: str | None = None
    venue: str | None = None
    discourse: list[str] | None = None
    fulltext_path: str | None = None
    fulltext_chars: int = 0
    fulltext_extracted_at: str | None = None
    refs_extracted_at: str | None = None
    refs_header_label: str | None = None
    refs_used_fallback: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass
class SourceRef:
    canonical_id: str
    source_type: str            # "zotero" | "folder"
    source_key: str             # collection-key oder absolute folder path
    source_item_id: str         # zotero-item-key oder absolute pdf-path
    pdf_path: str | None = None
    pdf_mtime: float | None = None
    zotero_date_modified: str | None = None
    match_score: float | None = None


@dataclass
class PubRef:
    canonical_id: str
    ref_id: str
    ref_doi: str | None = None
    ref_oa_id: str | None = None
    ref_year: int | None = None
    ref_text: str | None = None
    resolution_state: str = "doi_unresolved"
    # Erlaubte Werte: doi_resolved | doi_unresolved | text_resolved | text_unresolved


VALID_RESOLUTION_STATES = {
    "doi_resolved", "doi_unresolved", "text_resolved", "text_unresolved"
}


# ----------------------------- Helpers --------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row_to_publication(r: sqlite3.Row) -> Publication:
    return Publication(
        canonical_id=r["canonical_id"],
        title=r["title"],
        authors=json.loads(r["authors_json"]) if r["authors_json"] else [],
        doi=r["doi"],
        year=r["year"],
        item_type=r["item_type"],
        venue=r["venue"],
        discourse=json.loads(r["discourse_json"]) if r["discourse_json"] else None,
        fulltext_path=r["fulltext_path"],
        fulltext_chars=r["fulltext_chars"] or 0,
        fulltext_extracted_at=r["fulltext_extracted_at"],
        refs_extracted_at=r["refs_extracted_at"],
        refs_header_label=r["refs_header_label"],
        refs_used_fallback=bool(r["refs_used_fallback"]),
        notes=json.loads(r["notes_json"]) if r["notes_json"] else [],
    )


# ----------------------------- Store ----------------------------------------


class OwnRefsStore:
    """Thin wrapper über sqlite3.Connection mit typisierter API.

    Use als Context-Manager:
        with OwnRefsStore(db_path) as store:
            store.upsert_publication(pub)
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.con: sqlite3.Connection = connect(db_path)

    def __enter__(self) -> "OwnRefsStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        self.con.close()

    # --- publications ---

    def upsert_publication(self, pub: Publication) -> None:
        now = _now()
        self.con.execute(
            """
            INSERT INTO publications (
                canonical_id, doi, title, year, item_type, venue,
                authors_json, discourse_json, fulltext_path, fulltext_chars,
                fulltext_extracted_at, refs_extracted_at, refs_header_label,
                refs_used_fallback, last_seen_at, notes_json
            ) VALUES (
                :canonical_id, :doi, :title, :year, :item_type, :venue,
                :authors_json, :discourse_json, :fulltext_path, :fulltext_chars,
                :fulltext_extracted_at, :refs_extracted_at, :refs_header_label,
                :refs_used_fallback, :last_seen_at, :notes_json
            )
            ON CONFLICT(canonical_id) DO UPDATE SET
                doi = COALESCE(excluded.doi, publications.doi),
                title = excluded.title,
                year = COALESCE(excluded.year, publications.year),
                item_type = COALESCE(excluded.item_type, publications.item_type),
                venue = COALESCE(excluded.venue, publications.venue),
                authors_json = excluded.authors_json,
                discourse_json = COALESCE(excluded.discourse_json, publications.discourse_json),
                fulltext_path = COALESCE(excluded.fulltext_path, publications.fulltext_path),
                fulltext_chars = MAX(excluded.fulltext_chars, publications.fulltext_chars),
                fulltext_extracted_at = COALESCE(excluded.fulltext_extracted_at, publications.fulltext_extracted_at),
                refs_extracted_at = COALESCE(excluded.refs_extracted_at, publications.refs_extracted_at),
                refs_header_label = COALESCE(excluded.refs_header_label, publications.refs_header_label),
                refs_used_fallback = COALESCE(excluded.refs_used_fallback, publications.refs_used_fallback),
                last_seen_at = excluded.last_seen_at,
                notes_json = excluded.notes_json
            """,
            {
                "canonical_id": pub.canonical_id,
                "doi": pub.doi or None,
                "title": pub.title,
                "year": pub.year,
                "item_type": pub.item_type,
                "venue": pub.venue,
                "authors_json": json.dumps(pub.authors, ensure_ascii=False),
                "discourse_json": (
                    json.dumps(pub.discourse, ensure_ascii=False)
                    if pub.discourse is not None else None
                ),
                "fulltext_path": pub.fulltext_path,
                "fulltext_chars": pub.fulltext_chars,
                "fulltext_extracted_at": pub.fulltext_extracted_at,
                "refs_extracted_at": pub.refs_extracted_at,
                "refs_header_label": pub.refs_header_label,
                "refs_used_fallback": 1 if pub.refs_used_fallback else 0,
                "last_seen_at": now,
                "notes_json": (
                    json.dumps(pub.notes, ensure_ascii=False) if pub.notes else None
                ),
            },
        )
        self.con.commit()

    def get_publication(self, canonical_id: str) -> Publication | None:
        row = self.con.execute(
            "SELECT * FROM publications WHERE canonical_id = ?", (canonical_id,)
        ).fetchone()
        return _row_to_publication(row) if row else None

    def get_publication_by_doi(self, doi_normalized: str) -> Publication | None:
        row = self.con.execute(
            "SELECT * FROM publications WHERE doi = ?", (doi_normalized,)
        ).fetchone()
        return _row_to_publication(row) if row else None

    def iter_publications(self) -> Iterator[Publication]:
        for row in self.con.execute("SELECT * FROM publications ORDER BY year, canonical_id"):
            yield _row_to_publication(row)

    def count_publications(self) -> int:
        return self.con.execute("SELECT COUNT(*) FROM publications").fetchone()[0]

    # --- source refs ---

    def upsert_source_ref(self, sr: SourceRef) -> None:
        now = _now()
        self.con.execute(
            """
            INSERT INTO source_refs (
                canonical_id, source_type, source_key, source_item_id,
                pdf_path, pdf_mtime, zotero_date_modified, match_score,
                first_seen_at, last_seen_at
            ) VALUES (
                :canonical_id, :source_type, :source_key, :source_item_id,
                :pdf_path, :pdf_mtime, :zotero_date_modified, :match_score,
                :first_seen_at, :last_seen_at
            )
            ON CONFLICT(canonical_id, source_type, source_key, source_item_id)
            DO UPDATE SET
                pdf_path = COALESCE(excluded.pdf_path, source_refs.pdf_path),
                pdf_mtime = COALESCE(excluded.pdf_mtime, source_refs.pdf_mtime),
                zotero_date_modified = COALESCE(
                    excluded.zotero_date_modified, source_refs.zotero_date_modified
                ),
                match_score = COALESCE(excluded.match_score, source_refs.match_score),
                last_seen_at = excluded.last_seen_at
            """,
            {
                "canonical_id": sr.canonical_id,
                "source_type": sr.source_type,
                "source_key": sr.source_key,
                "source_item_id": sr.source_item_id,
                "pdf_path": sr.pdf_path,
                "pdf_mtime": sr.pdf_mtime,
                "zotero_date_modified": sr.zotero_date_modified,
                "match_score": sr.match_score,
                "first_seen_at": now,
                "last_seen_at": now,
            },
        )
        self.con.commit()

    def get_source_refs(self, canonical_id: str) -> list[SourceRef]:
        rows = self.con.execute(
            "SELECT * FROM source_refs WHERE canonical_id = ?", (canonical_id,)
        ).fetchall()
        return [
            SourceRef(
                canonical_id=r["canonical_id"],
                source_type=r["source_type"],
                source_key=r["source_key"],
                source_item_id=r["source_item_id"],
                pdf_path=r["pdf_path"],
                pdf_mtime=r["pdf_mtime"],
                zotero_date_modified=r["zotero_date_modified"],
                match_score=r["match_score"],
            )
            for r in rows
        ]

    def pdf_mtime_for_source_item(
        self, source_type: str, source_key: str, source_item_id: str
    ) -> float | None:
        """Liefert die zuletzt gesehene pdf_mtime für (source, item).
        Wird vom Build-Orchestrator genutzt, um zu entscheiden, ob ein PDF neu
        extrahiert werden muss.
        """
        row = self.con.execute(
            """
            SELECT pdf_mtime FROM source_refs
            WHERE source_type = ? AND source_key = ? AND source_item_id = ?
            """,
            (source_type, source_key, source_item_id),
        ).fetchone()
        return row["pdf_mtime"] if row else None

    # --- pub refs ---

    def replace_pub_refs(self, canonical_id: str, refs: Iterable[PubRef]) -> None:
        """Refs einer Publikation atomisch neu setzen.

        Idempotent in dem Sinn, dass eine erneute Extraktion mit gleichem Output
        denselben Endzustand erzeugt. Wir löschen erst alle Refs der Pub und
        legen sie neu an — das macht das Tracking simpler als per-Ref-UPSERT
        mit Diff.

        Defensive Dedup: kommt eine ref_id zweimal vor (z. B. weil zwei
        identische Citation-Strings denselben SHA1-Hash produzieren), gewinnt
        die *aufgelöste* Version. Sonst würde der PRIMARY-KEY-Constraint
        (canonical_id, ref_id) bei executemany abbrechen.
        """
        now = _now()
        # Dedup: dict ref_id → PubRef. Last-write-wins, bevorzugt Resolved.
        deduped: dict[str, PubRef] = {}
        for r in refs:
            if r.resolution_state not in VALID_RESOLUTION_STATES:
                raise ValueError(
                    f"Invalid resolution_state {r.resolution_state!r} for ref {r.ref_id!r}"
                )
            existing = deduped.get(r.ref_id)
            if existing is None:
                deduped[r.ref_id] = r
                continue
            # Bei Kollision: nimm den mit höherer Resolution-Stufe
            existing_resolved = existing.resolution_state.endswith("_resolved")
            new_resolved = r.resolution_state.endswith("_resolved")
            if new_resolved and not existing_resolved:
                deduped[r.ref_id] = r

        self.con.execute("DELETE FROM pub_refs WHERE canonical_id = ?", (canonical_id,))
        rows = [
            (
                r.canonical_id, r.ref_id, r.ref_doi, r.ref_oa_id,
                r.ref_year, r.ref_text, r.resolution_state,
                now if r.resolution_state.endswith("_resolved") else None,
            )
            for r in deduped.values()
        ]
        if rows:
            self.con.executemany(
                """
                INSERT INTO pub_refs (
                    canonical_id, ref_id, ref_doi, ref_oa_id, ref_year,
                    ref_text, resolution_state, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        self.con.commit()

    def get_pub_refs(self, canonical_id: str) -> list[PubRef]:
        rows = self.con.execute(
            "SELECT * FROM pub_refs WHERE canonical_id = ?", (canonical_id,)
        ).fetchall()
        return [
            PubRef(
                canonical_id=r["canonical_id"],
                ref_id=r["ref_id"],
                ref_doi=r["ref_doi"],
                ref_oa_id=r["ref_oa_id"],
                ref_year=r["ref_year"],
                ref_text=r["ref_text"],
                resolution_state=r["resolution_state"],
            )
            for r in rows
        ]

    def pubs_citing_oa_id(self, oa_id: str) -> list[str]:
        """Inverse Refs-Query: welche eigenen Pubs zitieren OpenAlex-Work `oa_id`?"""
        rows = self.con.execute(
            "SELECT DISTINCT canonical_id FROM pub_refs WHERE ref_oa_id = ?",
            (oa_id,),
        ).fetchall()
        return [r["canonical_id"] for r in rows]

    def all_cited_oa_ids(self) -> set[str]:
        """Union aller von eigenen Pubs zitierten OpenAlex-Work-IDs.
        Das ist der Kern-Input für die zweiseitige Bibliographic-Coupling-
        Cascade-Regel (`f_own_coupling_union ≥ 1`).
        """
        rows = self.con.execute(
            "SELECT DISTINCT ref_oa_id FROM pub_refs WHERE ref_oa_id IS NOT NULL"
        ).fetchall()
        return {r["ref_oa_id"] for r in rows}


# ----------------------------- Status / Report ------------------------------


def status_report(db_path: Path) -> dict:
    """Knappe Status-Diagnose: counts, coverage, last-ingest-per-source.

    Wird von `mojo refs status` aufgerufen. Mehr Details (Coverage pro
    Source × Jahr-Bucket) liefert `mojo refs report`, das nicht hier liegt,
    sondern im Build-Modul.
    """
    if not db_path.exists():
        return {
            "db_path": str(db_path),
            "exists": False,
            "n_publications": 0,
        }
    with OwnRefsStore(db_path) as store:
        con = store.con
        n_pubs = con.execute("SELECT COUNT(*) FROM publications").fetchone()[0]
        n_with_pdf = con.execute(
            "SELECT COUNT(*) FROM publications WHERE fulltext_chars > 0"
        ).fetchone()[0]
        n_with_refs = con.execute(
            "SELECT COUNT(DISTINCT canonical_id) FROM pub_refs"
        ).fetchone()[0]
        n_refs_total = con.execute("SELECT COUNT(*) FROM pub_refs").fetchone()[0]
        n_refs_resolved = con.execute(
            "SELECT COUNT(*) FROM pub_refs WHERE ref_oa_id IS NOT NULL"
        ).fetchone()[0]
        n_unique_oa = con.execute(
            "SELECT COUNT(DISTINCT ref_oa_id) FROM pub_refs WHERE ref_oa_id IS NOT NULL"
        ).fetchone()[0]
        sources = con.execute(
            """
            SELECT source_type, source_key,
                   COUNT(DISTINCT canonical_id) AS n_items,
                   MAX(last_seen_at) AS last_ingest
            FROM source_refs
            GROUP BY source_type, source_key
            ORDER BY source_type, source_key
            """
        ).fetchall()
    return {
        "db_path": str(db_path),
        "exists": True,
        "n_publications": n_pubs,
        "n_with_fulltext": n_with_pdf,
        "n_with_refs": n_with_refs,
        "n_refs_total": n_refs_total,
        "n_refs_resolved_oa": n_refs_resolved,
        "n_unique_oa_ids": n_unique_oa,
        "sources": [
            {
                "source_type": r["source_type"],
                "source_key": r["source_key"],
                "n_items": r["n_items"],
                "last_ingest": r["last_ingest"],
            }
            for r in sources
        ],
    }
