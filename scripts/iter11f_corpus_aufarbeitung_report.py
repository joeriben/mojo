"""Iter 11f — Korpus-Aufarbeitungs-Report (161-Items-Korpus).

OS-Schuld aus HANDOVER §4: Tabellen aus `docs/context/feedback_korpus_aufarbeitung.md`
(2026-05-24) wurden als Heredoc-Pipe produziert. Dieses Script reproduziert sie
aus `inventory.json` + `refs/{key}.json` + `discourse_classification.json`.

Output:
- Aufarbeitungs-Bilanz (PDF, ≥10 cits, ≥1 DOI) — gesamt + Jahr-Buckets
- Diskurs-Verteilung mit PDF/≥10 cits/≥1 DOI pro Diskursraum
- Diskurs × Jahr-Bucket (N / mit-PDF)
- Lückenliste 2020+ ÄKB/Resilienz mit unzureichender Aufarbeitung
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "backtest_data" / "own_bibliography"
INVENTORY = DATA_DIR / "inventory.json"
REFS_DIR = DATA_DIR / "refs"
CLASSIFICATION = DATA_DIR / "discourse_classification.json"

YEAR_BUCKETS = [
    ("vor 2010", lambda y: y is not None and y < 2010),
    ("2010-2019", lambda y: y is not None and 2010 <= y < 2020),
    ("2020+", lambda y: y is not None and y >= 2020),
    ("ohne Jahr", lambda y: y is None),
]

DISCOURSE_LABELS = {
    "aesthetische_kulturelle_bildung": "ÄKB",
    "digitale_kultur": "digitale_kultur",
    "medienpaed": "medienpaed",
    "bildungstheorie": "bildungstheorie",
    "erziehungswiss": "erziehungswiss",
    "resilienz": "resilienz",
    "kulturwiss_other": "kulturwiss_other",
}

GAP_DISCOURSES = {
    "aesthetische_kulturelle_bildung",
    "resilienz",
    "medienpaed",
    "digitale_kultur",
}


def _has_pdf(item: dict) -> bool:
    return bool(item.get("primary_pdf") or item.get("fallback_pdf"))


def _refs_meta(key: str) -> tuple[int, int]:
    """(n_citations_total, n_dois_resolved). 0/0 wenn refs-File fehlt."""
    f = REFS_DIR / f"{key}.json"
    if not f.exists():
        return (0, 0)
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return (0, 0)
    return (int(data.get("n_citations") or 0), int(data.get("n_dois") or 0))


def main() -> int:
    if not INVENTORY.exists():
        print(f"[ERR] inventory.json fehlt: {INVENTORY}", file=sys.stderr)
        return 2

    inv = json.loads(INVENTORY.read_text(encoding="utf-8"))
    items = inv["items"]
    cls_data = json.loads(CLASSIFICATION.read_text(encoding="utf-8")) if CLASSIFICATION.exists() else {}
    by_key_discourses = {it["zotero_key"]: it.get("discourses", []) for it in cls_data.get("items", [])}

    # Pro Item: meta sammeln
    enriched = []
    for it in items:
        key = it["zotero_key"]
        year = it.get("year")
        has_pdf = _has_pdf(it)
        n_cits, n_dois = _refs_meta(key)
        discourses = by_key_discourses.get(key, [])
        enriched.append({
            "key": key,
            "year": year,
            "has_pdf": has_pdf,
            "n_cits": n_cits,
            "n_dois": n_dois,
            "discourses": discourses,
            "title": it.get("title", ""),
            "venue": it.get("venue", ""),
        })

    # === Aufarbeitungs-Bilanz ===
    print("Aufarbeitungs-Bilanz")
    print("=" * 60)
    header = f"{'Kategorie':<14} {'N':>4} {'mit PDF':>10} {'>=10 cits':>11} {'>=1 DOI':>10}"
    print(header)
    print("-" * len(header))

    def fmt_row(label: str, subset: list[dict]) -> str:
        n = len(subset)
        if n == 0:
            return f"{label:<14} {n:>4} {'-':>10} {'-':>11} {'-':>10}"
        n_pdf = sum(1 for x in subset if x["has_pdf"])
        n_cits = sum(1 for x in subset if x["n_cits"] >= 10)
        n_doi = sum(1 for x in subset if x["n_dois"] >= 1)
        return (f"{label:<14} {n:>4}"
                f" {n_pdf:>4} ({n_pdf*100//n:>2} %)"
                f" {n_cits:>4} ({n_cits*100//n:>2} %)"
                f" {n_doi:>3} ({n_doi*100//n:>2} %)")

    print(fmt_row("GESAMT", enriched))
    for label, pred in YEAR_BUCKETS:
        subset = [x for x in enriched if pred(x["year"])]
        print(fmt_row(label, subset))
    print()

    # === Diskurs-Verteilung ===
    print("Diskurs-Verteilung (Multi-Label)")
    print("=" * 60)
    header = f"{'Diskursraum':<22} {'N':>4} {'%':>4} {'PDF':>4} {'>=10':>5} {'>=DOI':>6}"
    print(header)
    print("-" * len(header))
    total = len(enriched)
    for disc, label in DISCOURSE_LABELS.items():
        subset = [x for x in enriched if disc in x["discourses"]]
        n = len(subset)
        if n == 0:
            continue
        n_pdf = sum(1 for x in subset if x["has_pdf"])
        n_cits = sum(1 for x in subset if x["n_cits"] >= 10)
        n_doi = sum(1 for x in subset if x["n_dois"] >= 1)
        print(f"{label:<22} {n:>4} {n*100//total:>3}% {n_pdf:>4} {n_cits:>5} {n_doi:>6}")
    multi = sum(1 for x in enriched if len(x["discourses"]) > 1)
    print(f"\n→ {total} klassifiziert; {multi} mehrfach-getaggt; 0 unklassifiziert")
    print()

    # === Diskurs × Jahr-Bucket ===
    print("Diskurs × Jahr-Bucket (N / mit-PDF)")
    print("=" * 60)
    bucket_labels = [b[0] for b in YEAR_BUCKETS if b[0] != "ohne Jahr"]
    header = f"{'Diskursraum':<22}  " + "  ".join(f"{b:>10}" for b in bucket_labels)
    print(header)
    print("-" * len(header))
    for disc, label in DISCOURSE_LABELS.items():
        cells = []
        for b_label, pred in YEAR_BUCKETS:
            if b_label == "ohne Jahr":
                continue
            subset = [x for x in enriched if disc in x["discourses"] and pred(x["year"])]
            n_pdf = sum(1 for x in subset if x["has_pdf"])
            cells.append(f"{len(subset):>3}/{n_pdf:<3}")
        # Print only if discourse has any items
        if any(c.split("/")[0].strip() != "0" for c in cells):
            print(f"{label:<22}  " + "  ".join(f"{c:>10}" for c in cells))
    print()

    # === Lückenliste 2020+ ===
    print("Lückenliste: 2020+ Items in ÄKB/Resilienz/MediaPed/DigitaleKultur")
    print("              ohne PDF oder mit n_citations < 10")
    print("=" * 70)
    gap_items = [
        x for x in enriched
        if x["year"] is not None and x["year"] >= 2020
        and any(d in GAP_DISCOURSES for d in x["discourses"])
        and (not x["has_pdf"] or x["n_cits"] < 10)
    ]
    for x in sorted(gap_items, key=lambda e: (-(e["year"] or 0), e["title"])):
        title = (x["title"] or "<no title>")[:60]
        venue = (x["venue"] or "<no venue>")[:30]
        gap_reasons = []
        if not x["has_pdf"]:
            gap_reasons.append("no-PDF")
        if x["n_cits"] < 10:
            gap_reasons.append(f"cits={x['n_cits']}")
        d_short = ",".join(DISCOURSE_LABELS.get(d, d)[:5] for d in x["discourses"][:3])
        print(f"  [{x['year']}] {title:<60} | {venue:<30} | {d_short:<20} | {','.join(gap_reasons)}")
    print(f"\n→ {len(gap_items)} Items mit Aufarbeitungs-Lücke (2020+ Zukunftsdiskurse)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
