"""Iter 41 — Temporal-Holdout: driftet Benjamins Relevanz-Signatur über die Zeit?

ZUERST der Konfundierungs-Check (P3): im Gold ist `year` fast ein selection_mode-Proxy —
2020-2025 = intentional-positiver Backfill (keep-rate 0.75-1.00), 2026 = blinder Strom (keep 0.33).
Ein naiver train-alt/test-neu-Split misst also SELECTION-BIAS, nicht Drift. Wird explizit gezeigt.
DANN der einzig valide Drift-Probe: Intra-2026 auf dem BLINDEN Strom (screening), Monats-Split
früh (Jan+Feb) → spät (Mär+Apr). Klein (n~120, 8 LES), als Stabilitäts-Indikator, nicht als Beweis.
"""
import sys; sys.path.insert(0, "scripts")
import re, sqlite3
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.metrics import roc_auc_score

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
con = sqlite3.connect("articles.db")
meta = pd.read_sql_query("SELECT id, published, selection_mode FROM articles", con); con.close()
df = df.merge(meta, on="id", how="left")
rich = df["rich_sim"].astype(float).values
yk = df["ykeep"].values

# (1) Konfundierungs-Beleg: keep-rate alt vs 2026
old = df["year"] <= 2025
print("(1) Konfundierung year↔selection_mode:")
print(f"  2020-2025 (Backfill): n={old.sum():3d}  keep-rate={yk[old.values].mean():.2f}  "
      f"screening-Anteil={(df.loc[old,'selection_mode']=='screening').mean():.0%}")
print(f"  2026      (Strom)   : n={(~old).sum():3d}  keep-rate={yk[(~old).values].mean():.2f}  "
      f"screening-Anteil={(df.loc[~old,'selection_mode']=='screening').mean():.0%}")
print("  → Cross-Year-Split misst Selection-Bias, NICHT Drift. Verworfen.")

# (2) valider Intra-2026-Drift auf dem blinden Strom
scr = df[df["selection_mode"] == "screening"].copy()
scr["month"] = scr["published"].str.extract(r"(202\d-\d\d)")[0]
scr = scr[scr["month"].notna()]
early = scr[scr["month"].isin(["2026-01", "2026-02"])]
late = scr[scr["month"].isin(["2026-03", "2026-04"])]
print(f"\n(2) Intra-2026-Drift, blinder Strom (screening):")
print(f"  früh (Jan+Feb): n={len(early):3d}  keep={early['ykeep'].sum():2d}  "
      f"LES={ (early['y3']=='lesenswert').sum()}")
print(f"  spät (Mär+Apr): n={len(late):3d}  keep={late['ykeep'].sum():2d}  "
      f"LES={ (late['y3']=='lesenswert').sum()}")

def auc(sub):
    yy = sub["ykeep"].values
    if yy.sum() == 0 or yy.sum() == len(yy): return float("nan")
    return roc_auc_score(yy, sub["rich_sim"].astype(float).values)

print(f"\n  rich-sim keep-AUC früh: {auc(early):.3f}")
print(f"  rich-sim keep-AUC spät: {auc(late):.3f}")
# Train-früh → Test-spät: nur Schwelle/Schwerpunkt aus früh, AUC auf spät ist train-frei (AUC=Rangmaß),
# darum zusätzlich: mittlere rich-sim der keeper vs non-keeper je Periode (Signaltrennung stabil?)
for name, sub in [("früh", early), ("spät", late)]:
    k = sub.loc[sub["ykeep"] == 1, "rich_sim"].mean()
    n = sub.loc[sub["ykeep"] == 0, "rich_sim"].mean()
    print(f"  {name}: Ø rich-sim keeper={k:.3f} vs non-keeper={n:.3f}  Δ={k-n:+.3f}")
