"""Globale Refs-Häufigkeit im Article-Corpus, für IDF-Gewichtung.

Hintergrund (Benjamin 2026-05-24): die ungewichtete Schwellen-Regel
`f_own_coupling_union ≥ 1 → starker_indikator` ist eine primitive
Suchfunktion. Ein Treffer auf ein vielzitiertes Standardwerk
(z. B. `10.1080/00131857.2018.1454000` — 248-mal als Article-Ref im
Korpus) ist kein Signal, sondern Hintergrundrauschen.

IDF-Gewichtung (Information Retrieval-Standard):

    weight(ref) = 1 / log(1 + global_count_in_articles)

    global_count = 1   → weight ≈ 1.44  (sehr spezifisch, starkes Signal)
    global_count = 10  → weight ≈ 0.42  (mäßig häufig)
    global_count = 100 → weight ≈ 0.22
    global_count = 248 → weight ≈ 0.18  (Bestseller, schwach)

Score eines Artikels (analog zur konservativen Iter-11-Union-Logik):

    oa_score  = sum(weight(h) for h in oa_hits)
    doi_score = sum(weight(h) for h in doi_hits)
    score     = max(oa_score, doi_score)

Wir berechnen die Häufigkeit nur für Refs, die im `OwnRefsIndex` enthalten
sind — alles andere ist irrelevant, weil es nie zu einem Treffer führen kann.
Bei 255 OA + 298 DOI entspricht das ~553 Counter-Einträgen, einmaliger
Scan über articles.db dauert wenige Sekunden.

Persistenz: JSON-Sidecar `own_refs_corpus_freq.json` neben own_refs.db.
Invalidiert durch (own_refs_mtime, articles_mtime) im Header.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from journal_bot.own_refs.index import OwnRefsIndex, _normalize_doi, _normalize_oa_id


CACHE_FILENAME = "own_refs_corpus_freq.json"


@dataclass(frozen=True)
class CorpusFreq:
    """Globale Häufigkeit der Refs im Article-Corpus.

    Nur Refs aus dem zugehörigen `OwnRefsIndex` werden gezählt — alle anderen
    Refs sind für `signal_own_coupling` irrelevant.
    """

    oa_counts: dict[str, int] = field(default_factory=dict)
    doi_counts: dict[str, int] = field(default_factory=dict)
    n_articles_scanned: int = 0
    articles_db_mtime: float = 0.0
    own_refs_db_mtime: float = 0.0

    def idf_weight_oa(self, oa_id: str) -> float:
        """IDF-Gewicht für einen OA-ID-Treffer. Ungesehene Refs: weight=1.44."""
        c = self.oa_counts.get(oa_id, 1)
        return 1.0 / math.log(1.0 + max(1, c))

    def idf_weight_doi(self, doi: str) -> float:
        """IDF-Gewicht für einen DOI-Treffer."""
        c = self.doi_counts.get(doi, 1)
        return 1.0 / math.log(1.0 + max(1, c))

    @property
    def is_empty(self) -> bool:
        return not (self.oa_counts or self.doi_counts)

    @property
    def summary(self) -> str:
        if self.is_empty:
            return "(corpus_freq empty)"
        max_oa = max(self.oa_counts.values()) if self.oa_counts else 0
        max_doi = max(self.doi_counts.values()) if self.doi_counts else 0
        return (
            f"{len(self.oa_counts)} OA-Counts, {len(self.doi_counts)} DOI-Counts "
            f"über {self.n_articles_scanned} Artikel; "
            f"max OA={max_oa}, max DOI={max_doi}"
        )


def _scan_articles_db(
    articles_db: Path,
    target_oa: frozenset[str],
    target_doi: frozenset[str],
) -> tuple[Counter, Counter, int]:
    """Zähle für jede Ref in target_*, wie oft sie als Article-Ref erscheint.

    Eingelesen werden `openalex_refs` (JSON-Liste von Work-IDs) und
    `crossref_refs` (JSON-Liste von Ref-Dicts mit `.doi`).
    """
    oa_counts: Counter[str] = Counter()
    doi_counts: Counter[str] = Counter()
    n = 0

    con = sqlite3.connect(f"file:{articles_db}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT openalex_refs, crossref_refs FROM articles"
        )
        for oa_json, cr_json in rows:
            n += 1
            if oa_json:
                try:
                    xs = json.loads(oa_json)
                    if isinstance(xs, list):
                        seen_oa: set[str] = set()
                        for x in xs:
                            normalized = _normalize_oa_id(x) if isinstance(x, str) else None
                            if normalized and normalized in target_oa:
                                seen_oa.add(normalized)
                        # Count once per article — globale Häufigkeit = in wie vielen
                        # Artikeln die Ref auftaucht, nicht wie oft sie im JSON steht.
                        for w in seen_oa:
                            oa_counts[w] += 1
                except (json.JSONDecodeError, TypeError):
                    pass
            if cr_json:
                try:
                    xs = json.loads(cr_json)
                    if isinstance(xs, list):
                        seen_doi: set[str] = set()
                        for x in xs:
                            if not isinstance(x, dict):
                                continue
                            d = _normalize_doi(x.get("doi"))
                            if d and d in target_doi:
                                seen_doi.add(d)
                        for d in seen_doi:
                            doi_counts[d] += 1
                except (json.JSONDecodeError, TypeError):
                    pass
    finally:
        con.close()
    return oa_counts, doi_counts, n


def compute_corpus_freq(
    articles_db: Path,
    own_refs_index: OwnRefsIndex,
) -> CorpusFreq:
    """Berechne CorpusFreq frisch aus articles.db (kein Cache-Lookup).

    Aufrufer benutzt typischerweise `load_or_compute_corpus_freq`, das einen
    JSON-Sidecar-Cache verwendet. Diese Funktion ist auch direkt nutzbar für
    Tests / Debug.
    """
    if own_refs_index.is_empty or not articles_db.exists():
        return CorpusFreq()
    try:
        a_mtime = articles_db.stat().st_mtime
    except OSError:
        a_mtime = 0.0
    oa_counts, doi_counts, n = _scan_articles_db(
        articles_db, own_refs_index.oa_ids, own_refs_index.dois
    )
    return CorpusFreq(
        oa_counts=dict(oa_counts),
        doi_counts=dict(doi_counts),
        n_articles_scanned=n,
        articles_db_mtime=a_mtime,
        own_refs_db_mtime=own_refs_index.db_mtime,
    )


def _cache_path_for(own_refs_db: Path) -> Path:
    """Sidecar liegt im selben Verzeichnis wie own_refs.db."""
    return own_refs_db.parent / CACHE_FILENAME


def load_or_compute_corpus_freq(
    articles_db: Path,
    own_refs_index: OwnRefsIndex,
    *,
    own_refs_db: Path | None = None,
    force_rebuild: bool = False,
) -> CorpusFreq:
    """Lade gecachtes CorpusFreq oder berechne neu.

    Cache-Schlüssel: (articles_db_mtime, own_refs_db_mtime). Ändert sich
    eines der mtimes (oder fehlt der Cache), wird neu berechnet und
    persistiert. Bei Lese-/Schreibfehlern auf den Cache fallen wir
    transparent auf In-Memory-Berechnung zurück.
    """
    if own_refs_db is None:
        own_refs_db = Path(own_refs_index.db_path) if own_refs_index.db_path else None
    if own_refs_index.is_empty:
        return CorpusFreq()
    if not articles_db.exists():
        return CorpusFreq()

    cache_path = _cache_path_for(own_refs_db) if own_refs_db else None
    a_mtime = articles_db.stat().st_mtime
    o_mtime = own_refs_index.db_mtime

    if not force_rebuild and cache_path and cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            if (
                data.get("schema") == 1
                and abs(float(data.get("articles_db_mtime", 0)) - a_mtime) < 0.001
                and abs(float(data.get("own_refs_db_mtime", 0)) - o_mtime) < 0.001
            ):
                return CorpusFreq(
                    oa_counts=dict(data.get("oa_counts", {})),
                    doi_counts=dict(data.get("doi_counts", {})),
                    n_articles_scanned=int(data.get("n_articles_scanned", 0)),
                    articles_db_mtime=a_mtime,
                    own_refs_db_mtime=o_mtime,
                )
        except (OSError, json.JSONDecodeError, ValueError):
            pass  # Cache kaputt → neu bauen

    freq = compute_corpus_freq(articles_db, own_refs_index)

    if cache_path is not None:
        try:
            cache_path.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "articles_db_mtime": a_mtime,
                        "own_refs_db_mtime": o_mtime,
                        "n_articles_scanned": freq.n_articles_scanned,
                        "oa_counts": freq.oa_counts,
                        "doi_counts": freq.doi_counts,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    return freq
