"""Multi-Label-Klassifikation eigener Publikationen in Diskursräume.

Methode: V3 substring-match gegen *venue + title* (kein Volltext, keine LLM).
Patterns sind Regex-Strings, gespeichert in `journal_bot/data/discourse_patterns.json`.
Eine Pub kann zu mehreren Räumen gehören (Multi-Label).

Ergebnis-Stabilität: gleicher (venue, title)-Input liefert deterministisch
dieselbe sortierte Labelliste. Patterns sind Modul-global gecacht, einmal
kompiliert.

Portiert am 2026-05-24 aus dem Iter-11-Backtest-Artefakt
`backtest_data/own_bibliography/discourse_classification.json` (siehe
HANDOVER §3 und `docs/mojo_2_grundorientierung.md` §3.1).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATTERNS_PATH = PROJECT_ROOT / "journal_bot" / "data" / "discourse_patterns.json"


@lru_cache(maxsize=1)
def _load_patterns(path_str: str) -> dict[str, list[re.Pattern[str]]]:
    """Lade Patterns aus JSON, kompiliere zu re.Pattern, cache modulglobal."""
    raw = json.loads(Path(path_str).read_text(encoding="utf-8"))
    ppd = raw["patterns_per_discourse"]
    compiled: dict[str, list[re.Pattern[str]]] = {}
    for discourse, patterns in ppd.items():
        compiled[discourse] = [re.compile(p, re.IGNORECASE) for p in patterns]
    return compiled


def available_discourses(patterns_path: Path | None = None) -> list[str]:
    """Liste aller Diskursräume, für die Patterns existieren."""
    path = patterns_path or DEFAULT_PATTERNS_PATH
    return sorted(_load_patterns(str(path)).keys())


def classify(
    title: str | None,
    venue: str | None,
    patterns_path: Path | None = None,
) -> list[str]:
    """Multi-Label-Klassifikation eines Items.

    Match-Feld: ' | '.join([title, venue]) (case-insensitive Substring-Match
    via Regex). Leere Eingaben liefern []. Ergebnis ist alphabetisch sortiert
    für Stabilität.
    """
    path = patterns_path or DEFAULT_PATTERNS_PATH
    compiled = _load_patterns(str(path))
    haystack = " | ".join(s for s in (title or "", venue or "") if s)
    if not haystack.strip():
        return []
    matched = [d for d, regs in compiled.items() if any(r.search(haystack) for r in regs)]
    return sorted(matched)


def classify_many(
    items: Iterable[tuple[str | None, str | None]],
    patterns_path: Path | None = None,
) -> list[list[str]]:
    """Convenience: Batch-Klassifikation. Reihenfolge = Reihenfolge der Eingabe."""
    return [classify(t, v, patterns_path) for t, v in items]
