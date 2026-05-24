"""IDF-Gewichtung für das Adversarial-Set (§2.2).

Spiegelt `journal_bot.own_refs.corpus_freq` für die Set-Differenz
`trigger_refs \\ benjamin_refs`. Trigger-Daten enthalten in der Praxis
nur OA-Work-IDs (kein DOI-Set verfügbar aus dem Iter-10-Snapshot), darum
ist die Klasse OA-only.

Persistenz: JSON-Sidecar `adversarial_corpus_freq.json` neben own_refs.db.
Cache-Schlüssel: (articles_db_mtime, adversarial_built_from-mtimes).
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from journal_bot.adversarial.trigger_refs import AdversarialIndex
from journal_bot.own_refs.index import _normalize_oa_id


CACHE_FILENAME = "adversarial_corpus_freq.json"


@dataclass(frozen=True)
class AdversarialCorpusFreq:
    """Globale Häufigkeit der Adversarial-Refs im Article-Corpus."""

    oa_counts: dict[str, int] = field(default_factory=dict)
    n_articles_scanned: int = 0
    articles_db_mtime: float = 0.0
    adversarial_built_from: dict[str, float] = field(default_factory=dict)

    def idf_weight_oa(self, oa_id: str) -> float:
        """1/log(1 + count). Ungesehene Refs: 1.44 (= max)."""
        c = self.oa_counts.get(oa_id, 1)
        return 1.0 / math.log(1.0 + max(1, c))

    @property
    def is_empty(self) -> bool:
        return not self.oa_counts

    @property
    def summary(self) -> str:
        if self.is_empty:
            return "(adversarial_corpus_freq empty)"
        mx = max(self.oa_counts.values()) if self.oa_counts else 0
        return (
            f"{len(self.oa_counts)} OA-Counts über {self.n_articles_scanned} "
            f"Artikel; max OA={mx}"
        )


def _scan_articles_db_oa(
    articles_db: Path,
    target_oa: frozenset[str],
) -> tuple[Counter, int]:
    """Zähle die globale Article-Häufigkeit pro OA-ID im Adversarial-Set."""
    counts: Counter[str] = Counter()
    n = 0
    con = sqlite3.connect(f"file:{articles_db}?mode=ro", uri=True)
    try:
        for (oa_json,) in con.execute("SELECT openalex_refs FROM articles"):
            n += 1
            if not oa_json:
                continue
            try:
                xs = json.loads(oa_json)
            except (json.JSONDecodeError, TypeError):
                continue
            if not isinstance(xs, list):
                continue
            seen: set[str] = set()
            for x in xs:
                if not isinstance(x, str):
                    continue
                norm = _normalize_oa_id(x)
                if norm and norm in target_oa:
                    seen.add(norm)
            for w in seen:
                counts[w] += 1
    finally:
        con.close()
    return counts, n


def compute_adversarial_corpus_freq(
    articles_db: Path,
    adversarial_index: AdversarialIndex,
) -> AdversarialCorpusFreq:
    """Berechne AdversarialCorpusFreq frisch aus articles.db."""
    if adversarial_index.is_empty or not articles_db.exists():
        return AdversarialCorpusFreq()
    try:
        a_mtime = articles_db.stat().st_mtime
    except OSError:
        a_mtime = 0.0
    counts, n = _scan_articles_db_oa(articles_db, adversarial_index.oa_ids)
    return AdversarialCorpusFreq(
        oa_counts=dict(counts),
        n_articles_scanned=n,
        articles_db_mtime=a_mtime,
        adversarial_built_from=dict(adversarial_index.built_from),
    )


def load_or_compute_adversarial_corpus_freq(
    articles_db: Path,
    adversarial_index: AdversarialIndex,
    *,
    own_refs_db: Path | None = None,
    force_rebuild: bool = False,
) -> AdversarialCorpusFreq:
    """Lade gecachten AdversarialCorpusFreq oder berechne neu.

    Cache-Schlüssel: (articles_db_mtime, adversarial.built_from-mtimes).
    Wenn entweder articles.db oder eine Trigger-Bibliographie neuer ist als
    der Cache, wird neu berechnet.
    """
    if adversarial_index.is_empty:
        return AdversarialCorpusFreq()
    if not articles_db.exists():
        return AdversarialCorpusFreq()

    cache_path: Path | None = None
    if own_refs_db is not None:
        cache_path = own_refs_db.parent / CACHE_FILENAME

    a_mtime = articles_db.stat().st_mtime
    built_from = dict(adversarial_index.built_from)

    if not force_rebuild and cache_path and cache_path.exists():
        try:
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            cached_built = {k: float(v) for k, v in data.get("adversarial_built_from", {}).items()}
            mtimes_match = (
                set(cached_built) == set(built_from)
                and all(
                    abs(cached_built[k] - built_from[k]) < 0.001
                    for k in cached_built
                )
            )
            a_match = abs(float(data.get("articles_db_mtime", 0)) - a_mtime) < 0.001
            if data.get("schema") == 1 and mtimes_match and a_match:
                return AdversarialCorpusFreq(
                    oa_counts=dict(data.get("oa_counts", {})),
                    n_articles_scanned=int(data.get("n_articles_scanned", 0)),
                    articles_db_mtime=a_mtime,
                    adversarial_built_from=built_from,
                )
        except (OSError, json.JSONDecodeError, ValueError):
            pass

    freq = compute_adversarial_corpus_freq(articles_db, adversarial_index)
    if cache_path is not None:
        try:
            cache_path.write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "articles_db_mtime": a_mtime,
                        "adversarial_built_from": built_from,
                        "n_articles_scanned": freq.n_articles_scanned,
                        "oa_counts": freq.oa_counts,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass
    return freq
