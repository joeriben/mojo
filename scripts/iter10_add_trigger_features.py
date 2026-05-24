"""Iter 10 / Phase 3: 2nd-Trigger-Network-Features hinzufügen.

Erweitert features_gold.parquet um 6 neue Features auf Basis der Coupling-Statistik:

1. f_2nd_trigger_ref_overlap        — Refs ∩ ⋃coupled_ref_ids[any_discourse]
2. f_2nd_trigger_ref_overlap_dk     — Refs ∩ coupled_ref_ids["digitale_kultur"]
3. f_2nd_trigger_ref_overlap_ew     — Refs ∩ coupled_ref_ids["erziehungswiss"]
4. f_2nd_trigger_ref_overlap_mp     — Refs ∩ coupled_ref_ids["medienpaed"]
5. f_2nd_trigger_author_hit         — Anzahl Article-Autoren in ⋃top_cited_authors
6. f_2nd_trigger_journal_hit        — 1 wenn Article-Journal in ⋃top_cited_journals

Inputs:
  backtest_data/features_gold.parquet     (existierende Features)
  backtest_data/trigger_network/network_summary.json
  articles.db                              (openalex_refs, authors_json, journal_full)

Outputs:
  backtest_data/features_gold_pre_iter10.parquet  (Backup)
  backtest_data/features_gold.parquet              (überschrieben mit neuen Features)
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB = PROJECT_ROOT / "articles.db"
FEATURES_FILE = PROJECT_ROOT / "backtest_data" / "features_gold.parquet"
BACKUP_FILE = PROJECT_ROOT / "backtest_data" / "features_gold_pre_iter10.parquet"
NETWORK_SUMMARY = PROJECT_ROOT / "backtest_data" / "trigger_network" / "network_summary.json"


def main():
    print(f"Loading features:  {FEATURES_FILE}")
    print(f"Loading network:   {NETWORK_SUMMARY}\n")

    if not FEATURES_FILE.exists():
        print(f"  ! features_gold.parquet fehlt. Erst backtest_extract_features.py laufen lassen.")
        return 1
    if not NETWORK_SUMMARY.exists():
        print(f"  ! network_summary.json fehlt. Erst iter10_build_trigger_network.py laufen lassen.")
        return 1

    # Backup
    df = pd.read_parquet(FEATURES_FILE)
    if not BACKUP_FILE.exists():
        df.to_parquet(BACKUP_FILE, index=False)
        print(f"  Backup → {BACKUP_FILE}")
    else:
        print(f"  Backup existiert bereits: {BACKUP_FILE}")
    print(f"  Loaded {len(df)} articles, {len(df.columns)} cols\n")

    network = json.loads(NETWORK_SUMMARY.read_text())

    # Aggregate Sets
    all_coupled_ids: set[str] = set()
    coupled_by_disc: dict[str, set[str]] = {}
    for disc, info in network.items():
        ids = set(info.get("coupled_ref_ids", []))
        coupled_by_disc[disc] = ids
        all_coupled_ids |= ids
    print(f"  Coupled ref-ids ⋃ all discourse: {len(all_coupled_ids)}")
    for disc, ids in coupled_by_disc.items():
        print(f"    {disc}: {len(ids)}")

    all_top_authors: set[str] = set()
    for disc, info in network.items():
        for name in info.get("top_authors_for_features", []):
            if name:
                all_top_authors.add(name.lower())
    print(f"  ⋃ top cited authors (lowercase): {len(all_top_authors)}")

    all_top_journals: set[str] = set()
    for disc, info in network.items():
        for name in info.get("top_journals_for_features", []):
            if name:
                all_top_journals.add(name.lower())
    print(f"  ⋃ top cited journals (lowercase): {len(all_top_journals)}")

    # Lade SQLite-Daten für openalex_refs + authors + journal_full
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    ids_str = ",".join(f"'{i}'" for i in df["id"].astype(str))
    rows = conn.execute(
        f"SELECT id, openalex_refs, authors_json, journal_full "
        f"FROM articles WHERE id IN ({ids_str})"
    ).fetchall()
    by_id = {r["id"]: r for r in rows}
    print(f"  Lookup-Daten geladen für {len(by_id)} Articles\n")

    # Feature-Computation
    f_all_overlap = []
    f_dk_overlap = []
    f_ew_overlap = []
    f_mp_overlap = []
    f_author_hit = []
    f_journal_hit = []

    for art_id in df["id"].astype(str):
        r = by_id.get(art_id)
        if r is None:
            f_all_overlap.append(0)
            f_dk_overlap.append(0)
            f_ew_overlap.append(0)
            f_mp_overlap.append(0)
            f_author_hit.append(0)
            f_journal_hit.append(0)
            continue

        # OpenAlex-Ref-IDs des Articles
        refs = set()
        if r["openalex_refs"]:
            try:
                refs_list = json.loads(r["openalex_refs"])
                if isinstance(refs_list, list):
                    refs = {(str(rid).rsplit("/", 1)[-1]).strip() for rid in refs_list if rid}
            except Exception:
                pass

        f_all_overlap.append(len(refs & all_coupled_ids))
        f_dk_overlap.append(len(refs & coupled_by_disc.get("digitale_kultur", set())))
        f_ew_overlap.append(len(refs & coupled_by_disc.get("erziehungswiss", set())))
        f_mp_overlap.append(len(refs & coupled_by_disc.get("medienpaed", set())))

        # Author-Hit: Anzahl Article-Autoren, deren Name in all_top_authors
        # (lowercase, partial-match: jeder top-author muss ganz im author-string vorkommen)
        author_blob = ""
        if r["authors_json"]:
            try:
                authors = json.loads(r["authors_json"])
                if isinstance(authors, list):
                    author_blob = " | ".join(str(a) for a in authors).lower()
            except Exception:
                pass
        # Strenger: Top-Autor-Name (z.B. "ben williamson") muss im author_blob vorkommen.
        hits = sum(1 for top_a in all_top_authors if top_a in author_blob)
        f_author_hit.append(hits)

        # Journal-Hit: case-insensitive Substring-Match in beide Richtungen
        journal_lower = (r["journal_full"] or "").strip().lower()
        if journal_lower and any(
            (top_j == journal_lower) or (top_j in journal_lower) or (journal_lower in top_j)
            for top_j in all_top_journals
        ):
            f_journal_hit.append(1)
        else:
            f_journal_hit.append(0)

    df["f_2nd_trigger_ref_overlap"] = f_all_overlap
    df["f_2nd_trigger_ref_overlap_dk"] = f_dk_overlap
    df["f_2nd_trigger_ref_overlap_ew"] = f_ew_overlap
    df["f_2nd_trigger_ref_overlap_mp"] = f_mp_overlap
    df["f_2nd_trigger_author_hit"] = f_author_hit
    df["f_2nd_trigger_journal_hit"] = f_journal_hit

    # Distribution
    print("=== Verteilung der neuen Features (n=461) ===")
    new_cols = [
        "f_2nd_trigger_ref_overlap",
        "f_2nd_trigger_ref_overlap_dk",
        "f_2nd_trigger_ref_overlap_ew",
        "f_2nd_trigger_ref_overlap_mp",
        "f_2nd_trigger_author_hit",
        "f_2nd_trigger_journal_hit",
    ]
    for col in new_cols:
        vals = df[col]
        print(f"  {col:<38}  nonzero={int((vals>0).sum()):>4}  "
              f"mean={vals.mean():>6.3f}  max={int(vals.max()):>3d}")

    # Per-Class Mean
    print("\n=== Per-Klasse Mean (user_verdict) ===")
    print(f"{'Feature':<40}" + "".join(f"{c:>12}" for c in ["ignorieren", "scannen", "lesenswert"]))
    for col in new_cols:
        means = []
        for cls in ["ignorieren", "scannen", "lesenswert"]:
            mask = df["user_verdict"] == cls
            means.append(df.loc[mask, col].mean() if mask.any() else 0.0)
        print(f"{col:<40}" + "".join(f"{m:>12.3f}" for m in means))

    # Wrong-LES-Diagnose (vs. korrekt erkannten LES)
    # Hier brauchen wir Iter-9-Predictions, die in predictions.parquet stehen
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
            print(f"\n=== Hard-Case-Analyse: 2nd-Trigger-Signal auf den verfehlten LES ===")
            print(f"  wrong-LES (n={len(wrong_les)}): vom Algo verfehlt, vom User LES")
            print(f"  right-LES (n={len(right_les)}): vom Algo erkannt, vom User LES")
            print(f"  wrong-IGN (n={len(wrong_ign)}): vom Algo LES, vom User IGN (Hard-Cases der Gegenrichtung)")
            print(f"\n{'Feature':<40}{'wrong-LES':>12}{'right-LES':>12}{'wrong-IGN':>12}")
            for col in new_cols:
                wl = wrong_les[col].mean() if len(wrong_les) else 0
                rl = right_les[col].mean() if len(right_les) else 0
                wi = wrong_ign[col].mean() if len(wrong_ign) else 0
                print(f"{col:<40}{wl:>12.3f}{rl:>12.3f}{wi:>12.3f}")

    # Save
    df.to_parquet(FEATURES_FILE, index=False)
    print(f"\n  Wrote {FEATURES_FILE}: {len(df)} rows, {len(df.columns)} cols (+6 new)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
