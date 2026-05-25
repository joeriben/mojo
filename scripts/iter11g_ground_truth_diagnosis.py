"""Iter 11g — Ground-Truth-Diagnose über den 461-Backtest-Set.

OS-Schuld aus HANDOVER §4: Tabellen aus `docs/context/feedback_ground_truth_qualitaet.md`
(2026-05-24) wurden als Heredoc-Pipes produziert. Dieses Script reproduziert sie
aus `articles.db` × `features_gold.parquet` × `predictions_iter11_full.parquet`.

Output:
- Klassen-Verteilung (user_verdict)
- Selection-Bias: N + LES pro `selection_mode`
- Triage-Schwierigkeit pro selection_mode (Algo vs Opus Agree-Rate)
- Fehler-Overlap Algo (M9_Cascade_TunedBase) vs Opus (agent_verdict)
- 3-Klassen-Macro-F1 (excl pflichtlektuere)

Voraussetzungen:
- `articles.db` mit `selection_mode` Spalte (Benjamins live-DB)
- `backtest_data/features_gold.parquet` (461 × 33)
- `backtest_data/predictions_iter11_full.parquet` (Modell-Predictions)

Wenn `articles.db` fehlt, gibt das Script nur den feature_gold/predictions-Teil
aus (Klassen-Verteilung, Macro-F1, Fehler-Overlap) und überspringt
selection_mode-Analyse mit Hinweis.
"""

from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from sklearn.metrics import f1_score

ROOT = Path(__file__).parent.parent
ARTICLES_DB = ROOT / "articles.db"
FEATURES_GOLD = ROOT / "backtest_data" / "features_gold.parquet"
PREDICTIONS = ROOT / "backtest_data" / "predictions_iter11_full.parquet"

VERDICT_ORDER = ["ignorieren", "scannen", "lesenswert", "pflichtlektuere"]


def _check_files() -> None:
    for f in (FEATURES_GOLD, PREDICTIONS):
        if not f.exists():
            print(f"[ERR] fehlt: {f}", file=sys.stderr)
            sys.exit(2)


def main() -> int:
    _check_files()
    fg = pd.read_parquet(FEATURES_GOLD)
    pred = pd.read_parquet(PREDICTIONS)
    df = fg.merge(pred[["id", "M9_Cascade_TunedBase"]], on="id", how="left")
    n = len(df)

    print(f"=== 1. Klassen-Verteilung (user_verdict, n={n}) ===")
    vc = df["user_verdict"].value_counts()
    for v in VERDICT_ORDER:
        cnt = int(vc.get(v, 0))
        print(f"  {v:<18} {cnt:>4}  {cnt*100/n:>5.1f} %")
    print()

    # --- Selection-Bias (braucht articles.db) ---
    if ARTICLES_DB.exists():
        with sqlite3.connect(str(ARTICLES_DB)) as con:
            sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con)
        df = df.merge(sm, on="id", how="left")
        df["selection_mode"] = df["selection_mode"].fillna("unknown")

        print("=== 2. Selection-Bias: N + LES pro selection_mode ===")
        header = f"{'Mode':<16} {'N':>5} {'%':>5} {'LES':>4} {'LES-%':>7}"
        print(header)
        print("-" * len(header))
        modes = df["selection_mode"].value_counts()
        for mode, mn in modes.items():
            les = int(((df["selection_mode"] == mode) & (df["user_verdict"] == "lesenswert")).sum())
            pct = mn * 100 / n
            lpct = les * 100 / mn if mn else 0
            print(f"{mode:<16} {mn:>5} {pct:>4.1f}% {les:>4} {lpct:>6.1f} %")
        print()

        # --- Triage-Schwierigkeit pro Mode ---
        print("=== 3. Triage-Schwierigkeit pro selection_mode (Algo vs Opus Agree) ===")
        print(f"{'Mode':<16} {'N':>5} {'Algo-Agree':>11} {'Opus-Agree':>11}")
        print("-" * 50)
        # Algo-Klasse aus M9-Score
        df["algo_class"] = df["M9_Cascade_TunedBase"]
        for mode in sorted(df["selection_mode"].unique()):
            sub = df[df["selection_mode"] == mode]
            if len(sub) == 0:
                continue
            algo_ok = (sub["algo_class"] == sub["user_verdict"]).sum()
            opus_ok = (sub["agent_verdict"] == sub["user_verdict"]).sum()
            n_mode = len(sub)
            print(f"{mode:<16} {n_mode:>5} {algo_ok*100/n_mode:>9.1f} % {opus_ok*100/n_mode:>9.1f} %")
        print()
    else:
        print("[WARN] articles.db fehlt — selection_mode-Analyse übersprungen.", file=sys.stderr)
        print("       (Schritt 2+3 nur reproduzierbar mit Benjamins Live-DB.)")
        print()

    # --- Fehler-Overlap Algo vs Opus ---
    print("=== 4. Fehler-Overlap Algo (M9_Cascade_TunedBase) vs Opus (agent_verdict) ===")
    df["algo_ok"] = df["M9_Cascade_TunedBase"] == df["user_verdict"]
    df["opus_ok"] = df["agent_verdict"] == df["user_verdict"]
    cells = Counter()
    for _, row in df.iterrows():
        cells[(row["algo_ok"], row["opus_ok"])] += 1
    labels = {
        (True, True): "Beide richtig",
        (False, False): "Beide falsch",
        (True, False): "Nur Algo richtig",
        (False, True): "Nur Opus richtig",
    }
    for k, label in labels.items():
        c = cells[k]
        print(f"  {label:<22} {c:>4}  {c*100/n:>5.1f} %")
    print()

    # --- 3-Klassen-Macro-F1 (excl pflichtlektuere) ---
    print("=== 5. 3-Klassen-Macro-F1 (excl pflichtlektuere) ===")
    df3 = df[df["user_verdict"] != "pflichtlektuere"].copy()
    n3 = len(df3)
    labels3 = ["ignorieren", "scannen", "lesenswert"]
    opus = df3["agent_verdict"].where(df3["agent_verdict"].isin(labels3), "ignorieren")
    algo = df3["M9_Cascade_TunedBase"].where(df3["M9_Cascade_TunedBase"].isin(labels3), "ignorieren")
    f1_opus = f1_score(df3["user_verdict"], opus, labels=labels3, average="macro", zero_division=0)
    f1_algo = f1_score(df3["user_verdict"], algo, labels=labels3, average="macro", zero_division=0)
    print(f"  n={n3} (PFL ausgeschlossen)")
    print(f"  Opus  (agent_verdict)         Macro-F1 = {f1_opus:.3f}")
    print(f"  Algo  (M9_Cascade_TunedBase)  Macro-F1 = {f1_algo:.3f}")
    print(f"  Gap                            = {f1_opus - f1_algo:+.3f}")
    print()

    print("Reproduktion gegen `docs/context/feedback_ground_truth_qualitaet.md` —")
    print("kleine Drifts möglich, da Tabellen 2026-05-24 gegen damaligen DB-Stand.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
