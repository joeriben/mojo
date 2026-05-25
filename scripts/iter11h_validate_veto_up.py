"""Iter 11h — Veto-Up-Validierung: `f_own_coupling_union ≥ 1` als Lift-Regel.

OS-Schuld aus HANDOVER §4: Veto-Up-Validierung war Heredoc-Output in
`feedback_iter11_two_sided_coupling.md` (2026-05-24). Dieses Script reproduziert
die Bilanz aus `features_gold.parquet` + `predictions_iter11_full.parquet`.

Behauptung (Memory-Eintrag `feedback_iter11_two_sided_coupling.md`):

> LES-Recall +5.2 pp (55 % → 60 %) durch Veto-Up `f_own_coupling_union ≥ 1`.
> Im LogReg-Mischen führte das Coupling-Feature dagegen zu −0.011 F1.

Regel: wenn `f_own_coupling_union >= 1` und der Cascade-Predict ist
`ignorieren` oder `scannen`, dann lift auf `lesenswert`.

Output:
- LES-Recall + Precision Baseline (M9_Cascade_TunedBase) vs Veto-Up-Variante
- Macro-F1 vergleich (3-class, excl pflichtlektuere)
- Lift-Trefferquote: wie viele True-LES profitieren, wie viele False-Lifts
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import precision_recall_fscore_support, f1_score

ROOT = Path(__file__).parent.parent
FEATURES_GOLD = ROOT / "backtest_data" / "features_gold.parquet"
PREDICTIONS = ROOT / "backtest_data" / "predictions_iter11_full.parquet"

LIFTABLE_FROM = {"ignorieren", "scannen"}
LABELS3 = ["ignorieren", "scannen", "lesenswert"]


def _normalize(pred: pd.Series) -> pd.Series:
    return pred.where(pred.isin(LABELS3), "ignorieren")


def _apply_veto_up(df: pd.DataFrame, pred_col: str) -> pd.Series:
    new = df[pred_col].astype(str).copy()
    mask = (df["f_own_coupling_union"] >= 1) & (new.isin(LIFTABLE_FROM))
    new.loc[mask] = "lesenswert"
    return new


def _binary_report(df: pd.DataFrame, pred_col: str, label: str) -> dict:
    y_true = (df["user_verdict"] == "lesenswert").astype(int)
    y_pred = (df[pred_col] == "lesenswert").astype(int)
    p, r, f, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    return {"label": label, "precision": p, "recall": r, "f1": f,
            "n_pred_les": int(y_pred.sum())}


def main() -> int:
    for f in (FEATURES_GOLD, PREDICTIONS):
        if not f.exists():
            print(f"[ERR] fehlt: {f}", file=sys.stderr)
            return 2

    fg = pd.read_parquet(FEATURES_GOLD)
    pred = pd.read_parquet(PREDICTIONS)
    # Zusätzlich Pre-Coupling-Baseline (Iter 1–10) aus predictions.parquet, falls vorhanden
    pre_iter11 = ROOT / "backtest_data" / "predictions.parquet"
    cols_full = ["id", "M9_Cascade_TunedBase", "M9_Cascade_PerJournalBase"]
    df = fg.merge(pred[cols_full], on="id", how="left")
    if pre_iter11.exists():
        pre = pd.read_parquet(pre_iter11)
        if "M9_Cascade" in pre.columns:
            df = df.merge(pre[["id", "M9_Cascade"]].rename(columns={"M9_Cascade": "M9_PreCoupling"}),
                          on="id", how="left")
    df3 = df[df["user_verdict"] != "pflichtlektuere"].copy()
    print(f"n={len(df3)} (excl pflichtlektuere)")
    n_les = int((df3["user_verdict"] == "lesenswert").sum())
    n_coupled = int((df3["f_own_coupling_union"] >= 1).sum())
    n_les_coupled = int(((df3["user_verdict"] == "lesenswert") &
                         (df3["f_own_coupling_union"] >= 1)).sum())
    print(f"  davon LES (user_verdict): {n_les}")
    print(f"  davon mit f_own_coupling_union >= 1: {n_coupled}")
    print(f"  Schnitt LES ∩ coupled:    {n_les_coupled}")
    print()

    # Baseline-Variante: TunedBase (mit Iter-11-Coupling-Features integriert)
    df3["base"] = _normalize(df3["M9_Cascade_TunedBase"])
    df3["base_veto_up"] = _apply_veto_up(df3, "base")
    # PerJournal-Variante (sanity-check zweite Variante)
    df3["pj"] = _normalize(df3["M9_Cascade_PerJournalBase"])
    df3["pj_veto_up"] = _apply_veto_up(df3, "pj")
    # Pre-Coupling-Baseline (Iter 1–10, ohne f_own_coupling*-Features in LogReg)
    has_pre = "M9_PreCoupling" in df3.columns
    if has_pre:
        df3["pre"] = _normalize(df3["M9_PreCoupling"])
        df3["pre_veto_up"] = _apply_veto_up(df3, "pre")

    # === Binary LES-Recall/Precision ===
    print("=== LES-Recall + Precision (binary, lesenswert vs. rest) ===")
    rows = [
        _binary_report(df3, "base",          "M9_Cascade_TunedBase    (baseline)"),
        _binary_report(df3, "base_veto_up",  "M9_Cascade_TunedBase    + veto-up"),
        _binary_report(df3, "pj",            "M9_Cascade_PerJournal   (baseline)"),
        _binary_report(df3, "pj_veto_up",    "M9_Cascade_PerJournal   + veto-up"),
    ]
    if has_pre:
        rows.append(_binary_report(df3, "pre",         "M9_PreCoupling (Iter ≤10)   (baseline)"))
        rows.append(_binary_report(df3, "pre_veto_up", "M9_PreCoupling (Iter ≤10)   + veto-up"))
    header = f"{'Variante':<40} {'Prec':>6} {'Recall':>7} {'F1':>6} {'#LES-pred':>10}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(f"{r['label']:<40} {r['precision']:>5.3f}  {r['recall']:>6.3f} {r['f1']:>5.3f} {r['n_pred_les']:>10}")
    # Recall-Delta
    base = rows[0]
    veto = rows[1]
    delta_recall = veto["recall"] - base["recall"]
    print()
    print(f"→ LES-Recall TunedBase: {base['recall']:.3f} → {veto['recall']:.3f} "
          f"({delta_recall*100:+.1f} pp)")
    delta_pred = veto["n_pred_les"] - base["n_pred_les"]
    print(f"→ #LES-Predictions:    {base['n_pred_les']:>3} → {veto['n_pred_les']:>3} "
          f"({delta_pred:+d} Lifts)")
    print()

    # === Macro-F1 (3-class) ===
    print("=== Macro-F1 (3-class, excl pflichtlektuere) ===")
    for col, label in [
        ("base", "M9_Cascade_TunedBase   (baseline)"),
        ("base_veto_up", "M9_Cascade_TunedBase   + veto-up"),
        ("pj", "M9_Cascade_PerJournal  (baseline)"),
        ("pj_veto_up", "M9_Cascade_PerJournal  + veto-up"),
    ]:
        f1 = f1_score(df3["user_verdict"], df3[col], labels=LABELS3, average="macro", zero_division=0)
        print(f"  {label:<40}  Macro-F1 = {f1:.3f}")
    print()

    # === Lift-Trefferquote ===
    base_pred = df3["base"]
    veto_pred = df3["base_veto_up"]
    lifted = (veto_pred == "lesenswert") & (base_pred != "lesenswert")
    n_lifted = int(lifted.sum())
    if n_lifted == 0:
        print("Keine Lifts ausgelöst — Regel hat in den Daten keinen Effekt.")
        return 0
    true_lifts = int((lifted & (df3["user_verdict"] == "lesenswert")).sum())
    false_lifts = int((lifted & (df3["user_verdict"] != "lesenswert")).sum())
    print("=== Lift-Trefferquote (Veto-Up auf TunedBase) ===")
    print(f"  Lifts gesamt:     {n_lifted}")
    print(f"  davon True-LES:   {true_lifts}  ({true_lifts*100/n_lifted:.1f} %)")
    print(f"  davon False-Lift: {false_lifts}")
    # Aufschlüsselung des False-Lift nach true class
    for cls in ("ignorieren", "scannen"):
        c = int((lifted & (df3["user_verdict"] == cls)).sum())
        if c:
            print(f"    ↪ {cls}: {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
