"""Read-only Index über `own_refs.db` für die Cascade-Veto-Up-Regel.

Stellt die Refs-Wolke (alle OpenAlex-Work-IDs und DOIs, die in Benjamins
eigenen Publikationen zitiert werden) als zwei eingefrorene Sets bereit.
Verbraucher ist `journal_bot.signals.signal_own_coupling`, das die
Bibliographic-Coupling-Veto-Up-Regel (`f_own_coupling_union ≥ 1` → LES,
+5.2 pp LES-Recall, Iter 11) auf den **produktiven** Refs-Index umstellt
statt auf den `backtest_data/.../refs_resolved.json`-Snapshot.

Architektur-Hinweis (MOJO 2.0, §1):
- `own_refs.db` ist die wachsende, multi-source Datenbasis (Zotero + Folders).
- Dieser Index ist ein **dünner Reader** — keine Schema-Logik, keine Schreiber,
  keine Migration. Schema und UPSERT liegen in `own_refs/store.py`.
- Cache ist mtime-keyed: wenn `mojo refs build` die DB anfasst, invalidiert
  der nächste Lookup automatisch.
- Wenn die DB fehlt (Erstinstallation, Backup-Restore, etc.) liefert der
  Loader einen leeren Index — Aufrufer müssen graceful degraden.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class OwnRefsIndex:
    """Eingefrorene Refs-Wolke für O(1)-Intersection-Tests.

    - `oa_ids`: alle OpenAlex-Work-IDs, die irgendeine eigene Pub zitiert.
      Normalisiert ohne `https://openalex.org/`-Präfix (Iter-11-Konvention).
    - `dois`: alle normalisierten DOIs, die irgendeine eigene Pub zitiert.
      Lowercase, ohne Präfixe, gleich dem `ref_doi`-Wert in `pub_refs`.
    - `n_pubs_with_refs`: Anzahl Publikationen mit ≥1 Ref. Für `summary`.
    - `n_refs_total`: Anzahl Rows in `pub_refs`. Für Sanity-Check.
    - `db_mtime`: Letzte Modifikation der DB, dient als Cache-Schlüssel.
    - `db_path`: Pfad zur DB für Diagnose.
    """

    oa_ids: frozenset[str] = field(default_factory=frozenset)
    dois: frozenset[str] = field(default_factory=frozenset)
    n_pubs_with_refs: int = 0
    n_refs_total: int = 0
    db_mtime: float = 0.0
    db_path: str = ""

    @property
    def is_empty(self) -> bool:
        return not (self.oa_ids or self.dois)

    @property
    def summary(self) -> str:
        if self.is_empty:
            return "(own_refs index empty — run `mojo refs build`)"
        return (
            f"{len(self.oa_ids)} OA-IDs, {len(self.dois)} DOIs "
            f"aus {self.n_pubs_with_refs} Pubs ({self.n_refs_total} Refs total)"
        )


# Module-level cache: (db_path_str, mtime) → OwnRefsIndex.
# Klein gehalten, weil pro Prozess nur wenige DBs adressiert werden
# (in der Regel genau eine: `own_refs.db` im PROJECT_ROOT).
_INDEX_CACHE: dict[tuple[str, float], OwnRefsIndex] = {}


def _normalize_oa_id(s: str | None) -> str | None:
    """https://openalex.org/Wxxxx → Wxxxx (Iter-11-Konvention)."""
    if not s:
        return None
    return str(s).rsplit("/", 1)[-1].strip() or None


def _normalize_doi(s: str | None) -> str | None:
    """Lowercase, Präfixe entfernt. Schreibung wie in pub_refs."""
    if not s:
        return None
    raw = str(s).strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    raw = raw.rstrip(".")
    return raw or None


def load_own_refs_index(db_path: Path) -> OwnRefsIndex:
    """Lade die Refs-Wolke aus `own_refs.db` als eingefrorene Sets.

    Cache-Strategie: Schlüssel ist `(absolute_path, mtime)`. Wenn `mojo refs
    build` die DB neu schreibt, ändert sich `mtime` und der nächste Aufruf
    liest frisch. Innerhalb desselben Prozesses ist Wiederholungs-Lookup O(1).

    Robustheit: fehlende DB, fehlende Tabelle, leere Tabelle → leerer Index.
    Niemals Exception ins Aufruferland — Signals dürfen wegen fehlendem
    Refs-Index nicht crashen.
    """
    if not db_path.exists():
        return OwnRefsIndex(db_path=str(db_path))

    try:
        mtime = db_path.stat().st_mtime
    except OSError:
        return OwnRefsIndex(db_path=str(db_path))

    cache_key = (str(db_path.resolve()), mtime)
    cached = _INDEX_CACHE.get(cache_key)
    if cached is not None:
        return cached

    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return OwnRefsIndex(db_path=str(db_path), db_mtime=mtime)

    try:
        # Schema-Existenz prüfen — robuste Fallback wenn DB noch leer/inkomplett.
        tables = {
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "pub_refs" not in tables:
            return OwnRefsIndex(db_path=str(db_path), db_mtime=mtime)

        oa_rows = con.execute(
            "SELECT DISTINCT ref_oa_id FROM pub_refs WHERE ref_oa_id IS NOT NULL"
        ).fetchall()
        doi_rows = con.execute(
            "SELECT DISTINCT ref_doi FROM pub_refs WHERE ref_doi IS NOT NULL"
        ).fetchall()

        oa_ids = frozenset(
            x for x in (_normalize_oa_id(r[0]) for r in oa_rows) if x
        )
        dois = frozenset(
            x for x in (_normalize_doi(r[0]) for r in doi_rows) if x
        )

        (n_pubs,) = con.execute(
            "SELECT COUNT(DISTINCT canonical_id) FROM pub_refs"
        ).fetchone()
        (n_refs,) = con.execute("SELECT COUNT(*) FROM pub_refs").fetchone()

        idx = OwnRefsIndex(
            oa_ids=oa_ids,
            dois=dois,
            n_pubs_with_refs=int(n_pubs or 0),
            n_refs_total=int(n_refs or 0),
            db_mtime=mtime,
            db_path=str(db_path),
        )
        _INDEX_CACHE[cache_key] = idx
        return idx
    finally:
        con.close()


def clear_cache() -> None:
    """Test-Helper: invalidiere den Modul-Cache (z. B. zwischen tmp_path-Tests)."""
    _INDEX_CACHE.clear()
