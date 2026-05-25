"""Iter 11e — Diskurs-Klassifikation für 161-Items-Korpus reproduzieren.

OS-Schuld aus HANDOVER §4: Output `discourse_classification.json` (V3-Patterns +
Multi-Label-Klassifikation) wurde 2026-05-24 als Heredoc-Pipe produziert. Dieses
Script reproduziert dieselbe Klassifikation aus `inventory.json` und den im
JSON persistierten `patterns_per_discourse`, sodass die Validierungs-Pipeline
ohne Notebook/Heredoc-Reproduktion auskommt.

Wird aufgerufen mit:

    python3 scripts/iter11e_classify_discourses.py

Output:
- Distribution-Tabelle (N pro Diskursraum, mit Mehrfach-Tagging)
- Verifikation gegen `distribution`-Block in `discourse_classification.json`

Verhalten ist read-only — überschreibt `discourse_classification.json` NICHT.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "backtest_data" / "own_bibliography"
INVENTORY = DATA_DIR / "inventory.json"
CLASSIFICATION = DATA_DIR / "discourse_classification.json"

# Sammelband-/Tagungs-Venues, die keinen Diskurs-Tag erzwingen sollen
GENERIC_VENUES = {
    "", "edition assemblage", "merve", "transcript", "kohlhammer",
    "springer", "vs verlag", "routledge", "palgrave macmillan",
    "campus", "beltz juventa", "kopaed", "kopäd", "bertelsmann",
}


def _norm(text: str) -> str:
    return (text or "").lower()


# DOI-Container-Fallback (für Items ohne title/venue im Inventory)
DOI_PREFIX_TO_DISCOURSE: dict[str, list[str]] = {
    "10.1007/s00146": ["digitale_kultur"],     # Springer AI & Society
}


def _classify(title: str, venue: str, patterns: dict[str, list[str]],
              doi: str | None = None) -> list[str]:
    haystack = f"{_norm(venue)} || {_norm(title)}"
    hits: list[str] = []
    for discourse, pats in patterns.items():
        for p in pats:
            if re.search(p, haystack):
                hits.append(discourse)
                break
    if not hits and doi:
        d_norm = doi.lower().strip()
        for prefix, discourses in DOI_PREFIX_TO_DISCOURSE.items():
            if d_norm.startswith(prefix):
                hits.extend(discourses)
                break
    return hits


def main() -> int:
    if not INVENTORY.exists():
        print(f"[ERR] inventory.json fehlt: {INVENTORY}", file=sys.stderr)
        return 2
    if not CLASSIFICATION.exists():
        print(f"[ERR] discourse_classification.json fehlt: {CLASSIFICATION}", file=sys.stderr)
        return 2

    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    cls = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
    items = inv["items"]
    patterns = cls["patterns_per_discourse"]
    persisted_items = {it["zotero_key"]: it for it in cls["items"]}

    print(f"Method: {cls['method']}")
    print(f"Items in inventory: {len(items)}; in classification: {len(persisted_items)}")
    print()

    # Re-klassifikation
    distribution: Counter[str] = Counter()
    multi_label = 0
    unclassified = 0
    mismatches: list[tuple[str, list[str], list[str]]] = []

    for item in items:
        key = item["zotero_key"]
        title = item.get("title", "") or ""
        venue = item.get("venue", "") or ""
        doi = item.get("doi") or None
        hits = _classify(title, venue, patterns, doi=doi)
        if not hits:
            hits = ["kulturwiss_other"] if title or venue else []
        if not hits:
            unclassified += 1
            continue
        if len(hits) > 1:
            multi_label += 1
        for h in hits:
            distribution[h] += 1
        persisted = persisted_items.get(key, {}).get("discourses", [])
        if set(hits) != set(persisted) and persisted:
            mismatches.append((key, sorted(hits), sorted(persisted)))

    print(f"{'Diskursraum':<38}  {'N':>4}")
    print("-" * 46)
    for d, n in sorted(distribution.items(), key=lambda kv: -kv[1]):
        marker = "*" if d in patterns else " "
        print(f"{marker} {d:<36}  {n:>4}")
    print()
    print(f"Multi-Label-Items: {multi_label}")
    print(f"Unklassifiziert:   {unclassified}")
    print()

    # Verifikation gegen persistierte Klassifikation
    persisted_dist = cls.get("distribution", {})
    print("Distribution-Drift (re-klass vs persistiert):")
    for d in sorted(set(distribution) | set(persisted_dist)):
        a, b = distribution.get(d, 0), persisted_dist.get(d, 0)
        flag = "" if a == b else f"  Δ={a-b:+d}"
        print(f"  {d:<38}  re={a:>3}  persisted={b:>3}{flag}")

    if mismatches:
        print()
        print(f"Item-level Mismatches: {len(mismatches)} (re-klass vs persisted)")
        for key, hits, persisted in mismatches[:5]:
            print(f"  {key}: {hits} ≠ {persisted}")
        if len(mismatches) > 5:
            print(f"  ... ({len(mismatches) - 5} weitere)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
