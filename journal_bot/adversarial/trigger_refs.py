"""AdversarialIndex: trigger_refs \\ benjamin_refs (MOJO 2.0 §2.2).

Lädt die Bibliographien der drei Trigger-Autoren (Macgilchrist, Jarke, Chun)
und konstruiert die Set-Differenz zur Benjamin-Refs-Wolke aus `own_refs.db`.
Diese Set-Differenz ist die "Blind-Spot-Wolke" — Refs, die im benachbarten
Diskurs zentral sind und in Benjamins bisherigem Werk fehlen.

Datenquelle: `backtest_data/trigger_bibliographies/*.json` (Snapshot aus
Iter 10, 374 Trigger-Works, 6 728 unique OA-Refs). Refresh-Pfad ist im Modul
vorgesehen aber nicht implementiert — wird bei Bedarf als
`mojo refs trigger-refresh` ergänzt. Aktualisierung ist nicht zeitkritisch,
weil die Trigger-Autoren-Bibliographien sich langsam verändern.

Persistenz: JSON-Sidecar `trigger_refs_index.json` neben own_refs.db.
Wird invalidiert, sobald entweder die Snapshot-Files oder die own_refs.db
(über Benjamin-Set-Änderungen) neuer sind.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from journal_bot.own_refs.index import OwnRefsIndex


CACHE_FILENAME = "trigger_refs_index.json"
DEFAULT_TRIGGER_AUTHORS = ("macgilchrist", "jarke", "wendy_chun")


@dataclass(frozen=True)
class AdversarialIndex:
    """Set-Differenz `trigger_refs \\ benjamin_refs` als eingefrorenes Set.

    - `oa_ids`: Adversarial-Set, normalisierte OpenAlex-Work-IDs (ohne URL-Präfix).
    - `n_trigger_total`: Größe der Trigger-Union (vor Abzug Benjamin).
    - `n_redundant_with_benjamin`: Schnittmenge `trigger ∩ benjamin`.
    - `per_author`: Pro-Autor-Größe der OA-Refs (Diagnose).
    - `built_from`: Pfade der Quell-Files, für Cache-Invalidierung.

    Mtimes werden beim Cache-Laden geprüft.
    """

    oa_ids: frozenset[str] = field(default_factory=frozenset)
    n_trigger_total: int = 0
    n_redundant_with_benjamin: int = 0
    per_author: dict[str, int] = field(default_factory=dict)
    built_from: dict[str, float] = field(default_factory=dict)  # path → mtime
    benjamin_db_mtime: float = 0.0

    @property
    def is_empty(self) -> bool:
        return not self.oa_ids

    @property
    def summary(self) -> str:
        if self.is_empty:
            return "(adversarial index empty — Trigger-Daten fehlen)"
        per_author_str = ", ".join(f"{a}={n}" for a, n in self.per_author.items())
        return (
            f"{len(self.oa_ids)} Blind-Spot-OA-IDs (aus {self.n_trigger_total} "
            f"Trigger-Refs, {self.n_redundant_with_benjamin} redundant mit Benjamin) "
            f"[{per_author_str}]"
        )


def _normalize_oa_id(s: str) -> str:
    if not s:
        return ""
    return str(s).rsplit("/", 1)[-1].strip()


def _load_trigger_author_oa(
    bibliographies_dir: Path,
    author_keys: tuple[str, ...],
) -> tuple[dict[str, set[str]], dict[str, float]]:
    """Lade pro Autor das OA-Set + mtimes der Quell-Dateien.

    Returns:
        (per_author_oa_set, paths_to_mtimes)
    """
    per_author: dict[str, set[str]] = {}
    mtimes: dict[str, float] = {}
    for key in author_keys:
        file = bibliographies_dir / f"{key}.json"
        if not file.exists():
            continue
        try:
            mtimes[str(file)] = file.stat().st_mtime
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        refs: set[str] = set()
        for work in data.get("works", []):
            for r in (work.get("referenced_works") or []):
                if isinstance(r, str):
                    n = _normalize_oa_id(r)
                    if n:
                        refs.add(n)
        per_author[key] = refs
    return per_author, mtimes


def _cache_path_for(own_refs_db: Path | None) -> Path | None:
    """Sidecar liegt im Verzeichnis von own_refs.db."""
    if own_refs_db is None:
        return None
    return own_refs_db.parent / CACHE_FILENAME


def compute_adversarial_index(
    bibliographies_dir: Path,
    benjamin_index: OwnRefsIndex,
    author_keys: tuple[str, ...] = DEFAULT_TRIGGER_AUTHORS,
) -> AdversarialIndex:
    """Berechne `trigger_refs \\ benjamin_refs` frisch (kein Cache-Lookup)."""
    per_author_sets, mtimes = _load_trigger_author_oa(bibliographies_dir, author_keys)
    if not per_author_sets:
        return AdversarialIndex(benjamin_db_mtime=benjamin_index.db_mtime)

    trigger_union: set[str] = set()
    for s in per_author_sets.values():
        trigger_union |= s

    benjamin_oa = set(benjamin_index.oa_ids)
    adversarial = trigger_union - benjamin_oa
    redundant = len(trigger_union & benjamin_oa)

    return AdversarialIndex(
        oa_ids=frozenset(adversarial),
        n_trigger_total=len(trigger_union),
        n_redundant_with_benjamin=redundant,
        per_author={k: len(v) for k, v in per_author_sets.items()},
        built_from=mtimes,
        benjamin_db_mtime=benjamin_index.db_mtime,
    )


def load_or_compute_adversarial_index(
    bibliographies_dir: Path,
    benjamin_index: OwnRefsIndex,
    *,
    own_refs_db: Path | None = None,
    author_keys: tuple[str, ...] = DEFAULT_TRIGGER_AUTHORS,
    force_rebuild: bool = False,
) -> AdversarialIndex:
    """Lade gecachten AdversarialIndex oder berechne neu.

    Cache-Schlüssel: alle Source-mtimes + benjamin-db-mtime. Ändert sich
    einer der mtimes, wird neu berechnet und persistiert. Bei
    Lese-/Schreibfehlern fällt der Loader auf In-Memory-Berechnung zurück.
    """
    if own_refs_db is None and benjamin_index.db_path:
        own_refs_db = Path(benjamin_index.db_path)
    cache_path = _cache_path_for(own_refs_db)

    # mtimes der Source-Files vorab sammeln (für Cache-Check)
    current_mtimes: dict[str, float] = {}
    for key in author_keys:
        f = bibliographies_dir / f"{key}.json"
        if f.exists():
            try:
                current_mtimes[str(f)] = f.stat().st_mtime
            except OSError:
                pass

    if not force_rebuild and cache_path and cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            cached_mtimes = {k: float(v) for k, v in data.get("built_from", {}).items()}
            cached_benj = float(data.get("benjamin_db_mtime", 0))
            mtimes_match = (
                set(cached_mtimes) == set(current_mtimes)
                and all(
                    abs(cached_mtimes[k] - current_mtimes[k]) < 0.001
                    for k in cached_mtimes
                )
            )
            benj_match = abs(cached_benj - benjamin_index.db_mtime) < 0.001
            if data.get("schema") == 1 and mtimes_match and benj_match:
                return AdversarialIndex(
                    oa_ids=frozenset(data.get("oa_ids", [])),
                    n_trigger_total=int(data.get("n_trigger_total", 0)),
                    n_redundant_with_benjamin=int(data.get("n_redundant_with_benjamin", 0)),
                    per_author=dict(data.get("per_author", {})),
                    built_from=current_mtimes,
                    benjamin_db_mtime=benjamin_index.db_mtime,
                )
        except (OSError, json.JSONDecodeError, ValueError):
            pass

    idx = compute_adversarial_index(bibliographies_dir, benjamin_index, author_keys)

    if cache_path is not None:
        try:
            cache_path.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "oa_ids": sorted(idx.oa_ids),
                        "n_trigger_total": idx.n_trigger_total,
                        "n_redundant_with_benjamin": idx.n_redundant_with_benjamin,
                        "per_author": idx.per_author,
                        "built_from": idx.built_from,
                        "benjamin_db_mtime": idx.benjamin_db_mtime,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    return idx
