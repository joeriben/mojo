"""Iter 22 — zeitliche Validierung / Drift.

Phase D Robustheit: das own+content-Modell und der rich-Ranker werden mit zufälligem CV gemessen
(Iter 03/16). Realer Betrieb sagt aber ZUKUNFT aus VERGANGENHEIT vorher. Frage: bricht die Leistung
bei zeitlichem Split (Training alt → Test neu) ein? Lehrstuhl-Shift (Memory feedback_korpus_aufarbeitung:
bildungstheorie↓, ÄKB/resilienz↑) könnte driften. Erst Jahres-/Basisraten-Verteilung, dann Split-Eval.
"""
import sys; sys.path.insert(0, "scripts")
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
df["year"] = pd.to_numeric(df["year"], errors="coerce")
LAB = E.LABELS3; y3 = df["y3"].map({l:i for i,l in enumerate(LAB)}).values

print("Jahres-/keep-Basisraten-Verteilung:")
for y, g in df.groupby(df["year"]):
    if len(g) >= 8:
        print(f"  {int(y) if pd.notna(y) else '?'}: n={len(g):>3}  keep-Rate {g['ykeep'].mean():.0%}  LES {(g['y3']=='lesenswert').mean():.0%}")

# KEINE Zeitachse vorhanden → stattdessen: ist `year` ein Selection-Bias-Leck?
con_old = df["year"] < 2026
print(f"\nKonfund: ältere Jahrgänge (<2026, n={con_old.sum()}) = intentional-positiv (keep "
      f"{df.loc[con_old,'ykeep'].mean():.0%}); 2026 (n={(~con_old).sum()}) = Screening (keep "
      f"{df.loc[~con_old,'ykeep'].mean():.0%}). → `year` korreliert mit Label NUR über die Quelle.")
yk = df["ykeep"].values
auc_year = roc_auc_score(yk, df["f_year_normalized"].astype(float).fillna(df["f_year_normalized"].median()))
print(f"f_year_normalized keep-AUC (gesamt): {auc_year:.3f}  — wenn hoch, ist es ein Bias-Proxy, kein Inhalt")

def cv_macro(cols, mask=None):
    X = df[cols].astype(float).values; m = np.ones(len(df),bool) if mask is None else mask
    skf=StratifiedKFold(5,shuffle=True,random_state=42); p=np.zeros(len(df),int)
    for a,b in skf.split(X,y3):
        c=make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),LogisticRegression(max_iter=3000,class_weight="balanced"))
        c.fit(X[a],y3[a]); p[b]=c.predict(X[b])
    return E.metrics(np.array(LAB)[y3[m]], np.array(LAB)[p[m]])["f1_3cls"]

base = E.OWN_WORK + E.CONTENT
with_year = base + ["f_year_normalized"]
scr2026 = (~con_old).values   # 2026 = der echte Screening-Strom (Näherung)
print(f"\nLeak-Test (macro-F1, OOF):")
print(f"  own+content            gesamt {cv_macro(base):.3f}   |  nur 2026-Strom {cv_macro(base, scr2026):.3f}")
print(f"  own+content+YEAR       gesamt {cv_macro(with_year):.3f}   |  nur 2026-Strom {cv_macro(with_year, scr2026):.3f}")
print("  → springt 'gesamt' mit year, aber '2026-Strom' nicht, war year ein Bias-Leck.")
