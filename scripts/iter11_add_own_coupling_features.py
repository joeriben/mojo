"""Iter 11 / Phase 4: Eigenwerk-basierte Coupling-Features hinzufügen.

Erweitert features_gold.parquet um Coupling-Features auf Basis der aus
Benjamins eigenen Publikationen extrahierten Refs-Wolke (Iter 11 a-c).

Neu (zweiseitig: `|article_refs ∩ benjamin_refs|`):
  f_own_coupling_oa            — Article.openalex_refs ∩ benjamin_ref_oa_wolke
  f_own_coupling_doi           — Article.crossref_refs.doi ∩ benjamin_ref_dois
  f_own_coupling_union         — Vereinigung beider Trefferarten
  f_own_coupling_jaccard_oa    — |A∩B| / |A∪B| auf OA-IDs
  f_own_coupling_log_union     — log1p(union)

Diese Features unterscheiden sich grundlegend von Iter 10:
- Iter 10 (f_2nd_trigger_ref_overlap): einseitig, Article-Refs gegen Refs der
  3 Trigger-Autoren (Macgilchrist/Jarke/Chun).
- Iter 11 (f_own_coupling_*): zweiseitig, Article-Refs gegen Refs, die Benjamin
  in 109 eigenen Publikationen tatsächlich zitiert hat.

Iter 10 Befund (Plateau bei 0.607 F1) motivierte Benjamin zu fragen:
  "Gibt es z.B. Informationen über Korrelationen der von mir zitierten Werke
  mit den Literaturlisten der durchsuchten Titel?"
Iter 11 prüft diese Hypothese empirisch.

Inputs:
  backtest_data/features_gold.parquet            (Iter-10-Stand)
  backtest_data/own_bibliography/refs_resolved.json
  articles.db                                     (openalex_refs, crossref_refs)

Outputs:
  backtest_data/features_gold_pre_iter11.parquet  (Backup)
  backtest_data/features_gold.parquet              (überschrieben + 5 Features)
"""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB = PROJECT_ROOT / "articles.db"
FEATURES_FILE = PROJECT_ROOT / "backtest_data" / "features_gold.parquet"
BACKUP_FILE = PROJECT_ROOT / "backtest_data" / "features_gold_pre_iter11.parquet"
OWN_REFS_RESOLVED = PROJECT_ROOT / "backtest_data" / "own_bibliography" / "refs_resolved.json"

# Bewusst nur 2 nicht-kollineare Features:
# - count (union OA+DOI), nicht aufgeteilt → keine Lin-Abhängigkeit
# - jaccard auf OA → normalisierte Variante
# Frühere 5-Feature-Version führte zu Coef-Splitting (alle nahezu kollinear)
# und reduzierte M9_Cascade_TunedBase um −0.03 F1 (siehe Devlog Iter 11).
NEW_COLS = [
    "f_own_coupling_union",
    "f_own_coupling_jaccard_oa",
]


def normalize_oa_id(s: str) -> str:
    """https://openalex.org/Wxxxx → Wxxxx."""
    if not s:
        return ""
    return str(s).rsplit("/", 1)[-1].strip()


def main():
    if not FEATURES_FILE.exists():
        sys.exit(f"FEATURES_FILE fehlt: {FEATURES_FILE}")
    if not OWN_REFS_RESOLVED.exists():
        sys.exit(f"refs_resolved.json fehlt: {OWN_REFS_RESOLVED}. Erst iter11_resolve_refs_to_openalex.py laufen lassen.")

    print(f"Loading features:  {FEATURES_FILE}")
    print(f"Loading own refs:  {OWN_REFS_RESOLVED}\n")

    df = pd.read_parquet(FEATURES_FILE)
    if not BACKUP_FILE.exists():
        df.to_parquet(BACKUP_FILE, index=False)
        print(f"  Backup → {BACKUP_FILE}")
    else:
        print(f"  Backup existiert bereits: {BACKUP_FILE}")
    print(f"  Loaded {len(df)} articles, {len(df.columns)} cols\n")

    own = json.loads(OWN_REFS_RESOLVED.read_text())
    benjamin_oa: set[str] = {normalize_oa_id(s) for s in own["all_own_ref_oa_ids"] if s}
    benjamin_dois: set[str] = {d.lower() for d in own["all_own_ref_dois"] if d}
    print(f"  Benjamin ref-wolke: {len(benjamin_oa)} OA Work-IDs, {len(benjamin_dois)} DOIs")
    print(f"  Resolved aus {own['resolution_summary']['n_items_with_doi_refs']} eigenen Publikationen.\n")

    # SQLite-Daten: openalex_refs + crossref_refs
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    ids_str = ",".join(f"'{i}'" for i in df["id"].astype(str))
    rows = conn.execute(
        f"SELECT id, openalex_refs, crossref_refs FROM articles WHERE id IN ({ids_str})"
    ).fetchall()
    by_id = {r["id"]: r for r in rows}
    print(f"  Lookup-Daten geladen für {len(by_id)} Articles\n")

    # Feature-Computation
    f_oa: list[int] = []
    f_doi: list[int] = []
    f_union: list[int] = []
    f_jacc: list[float] = []
    f_log_union: list[float] = []

    coverage_oa = 0  # articles mit ≥1 oa-ref
    coverage_doi = 0  # articles mit ≥1 doi-ref
    for art_id in df["id"].astype(str):
        r = by_id.get(art_id)
        if r is None:
            f_oa.append(0); f_doi.append(0); f_union.append(0)
            f_jacc.append(0.0); f_log_union.append(0.0)
            continue

        # Article-OpenAlex-Refs
        oa_refs: set[str] = set()
        if r["openalex_refs"]:
            try:
                xs = json.loads(r["openalex_refs"])
                if isinstance(xs, list):
                    oa_refs = {normalize_oa_id(x) for x in xs if x}
            except Exception:
                pass
        if oa_refs:
            coverage_oa += 1

        # Article-Crossref-DOIs (aus crossref_refs.[].doi)
        doi_refs: set[str] = set()
        if r["crossref_refs"]:
            try:
                xs = json.loads(r["crossref_refs"])
                if isinstance(xs, list):
                    for x in xs:
                        if isinstance(x, dict):
                            d = (x.get("doi") or "").strip().lower()
                            if d.startswith("10."):
                                doi_refs.add(d)
            except Exception:
                pass
        if doi_refs:
            coverage_doi += 1

        # Coupling-Intersections
        oa_hits = oa_refs & benjamin_oa
        doi_hits = doi_refs & benjamin_dois
        n_oa = len(oa_hits)
        n_doi = len(doi_hits)
        # Union: dedup via union of (OA-IDs we hit) + (DOIs we hit, only those nicht
        # bereits über OA-Match gezählt). Da wir per-DOI nicht wissen ob OA-Match
        # denselben Ref betrifft, nehmen wir konservativ max(oa, doi).
        n_union = max(n_oa, n_doi)

        # Jaccard auf OA: |A∩B| / |A∪B|
        union_oa = oa_refs | benjamin_oa
        jacc = (n_oa / len(union_oa)) if union_oa else 0.0

        f_oa.append(n_oa)
        f_doi.append(n_doi)
        f_union.append(n_union)
        f_jacc.append(round(jacc, 6))
        f_log_union.append(round(math.log1p(n_union), 4))

    # Nur 2 nicht-kollineare Features ins finale DataFrame (siehe NEW_COLS Kommentar).
    df["f_own_coupling_union"] = f_union
    df["f_own_coupling_jaccard_oa"] = f_jacc

    # Diagnostik-Werte (nicht im DataFrame, nur für die print-Statistik unten):
    diag_oa = f_oa
    diag_doi = f_doi
    diag_log_union = f_log_union

    print(f"  Ref-Coverage: openalex_refs={coverage_oa}/{len(df)}, crossref_refs={coverage_doi}/{len(df)}\n")

    # Distribution
    print("=== Verteilung der neuen Features (n={}) ===".format(len(df)))
    for col in NEW_COLS:
        vals = df[col]
        print(
            f"  {col:<30}  nonzero={int((vals>0).sum()):>4}  "
            f"mean={vals.mean():>7.3f}  max={vals.max():>7.3f}"
        )

    # Per-Klasse Mean
    print("\n=== Per-Klasse Mean (user_verdict) ===")
    classes = ["ignorieren", "scannen", "lesenswert"]
    header = f"{'Feature':<32}" + "".join(f"{c:>12}" for c in classes)
    print(header)
    for col in NEW_COLS:
        cells = []
        for cls in classes:
            mask = df["user_verdict"] == cls
            cells.append(df.loc[mask, col].mean() if mask.any() else 0.0)
        print(f"{col:<32}" + "".join(f"{v:>12.3f}" for v in cells))

    # Per-Klasse Hit-Rate
    print("\n=== Per-Klasse Hit-Rate (% articles mit ≥1 coupling) ===")
    print(f"{'Threshold':<32}" + "".join(f"{c:>12}" for c in classes))
    cells = []
    for cls in classes:
        mask = df["user_verdict"] == cls
        n_total = int(mask.sum())
        n_hit = int(((df["f_own_coupling_union"] > 0) & mask).sum())
        pct = 100.0 * n_hit / max(1, n_total)
        cells.append(f"{n_hit}/{n_total} ({pct:.1f}%)")
    print(f"{'f_own_coupling_union':<32}" + "".join(f"{v:>20}" for v in cells))

    # Hard-Case-Diagnose: wirken die Features auf wrong-LES?
    pred_file = PROJECT_ROOT / "backtest_data" / "predictions.parquet"
    if pred_file.exists():
        preds = pd.read_parquet(pred_file)
        if "M9_Cascade_TunedBase" in preds.columns:
            merged = df.merge(preds[["id", "M9_Cascade_TunedBase"]], on="id", how="left")
            wrong_les = merged[(merged["user_verdict"] == "lesenswert") &
                              (merged["M9_Cascade_TunedBase"] != "lesenswert")]
            right_les = merged[(merged["user_verdict"] == "lesenswert") &
                              (merged["M9_Cascade_TunedBase"] == "lesenswert")]
            wrong_ign = merged[(merged["user_verdict"] == "ignorieren") &
                              (merged["M9_Cascade_TunedBase"] == "lesenswert")]
            print(f"\n=== Hard-Case Analyse: own-coupling-Signal auf wrong-LES ===")
            print(f"  wrong-LES (n={len(wrong_les)}): User LES, Algo nicht-LES")
            print(f"  right-LES (n={len(right_les)}): User LES, Algo LES")
            print(f"  wrong-IGN (n={len(wrong_ign)}): User IGN, Algo LES")
            print(f"\n{'Feature':<32}{'wrong-LES':>12}{'right-LES':>12}{'wrong-IGN':>12}")
            for col in NEW_COLS:
                wl = wrong_les[col].mean() if len(wrong_les) else 0
                rl = right_les[col].mean() if len(right_les) else 0
                wi = wrong_ign[col].mean() if len(wrong_ign) else 0
                print(f"{col:<32}{wl:>12.3f}{rl:>12.3f}{wi:>12.3f}")

    df.to_parquet(FEATURES_FILE, index=False)
    print(f"\n  Wrote {FEATURES_FILE}: {len(df)} rows, {len(df.columns)} cols (+{len(NEW_COLS)} new)")


if __name__ == "__main__":
    sys.exit(main())
