"""Iter 06 — Selection-Bias / Blind-Screening-Eval.

Memory: 65% der LES stammen aus intentional-positiven Quellen (citation/mixed/trigger/
complementarity), nur ~17% LES aus Blind-Screening. Der reale Use-Case ist aber der BLINDE
einlaufende Strom. Frage: bricht die Modell-Performance dort ein? Join selection_mode aus articles.db.
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression

df = E.load().reset_index(drop=True)
con = sqlite3.connect("articles.db")
sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left")
df["selection_mode"] = df["selection_mode"].fillna("unknown")

print("=== user_verdict × selection_mode ===")
ct = pd.crosstab(df["selection_mode"], df["y3"])
print(ct)
print("\nLES-Anteil je selection_mode:")
for mode, g in df.groupby("selection_mode"):
    les = (g["y3"] == "lesenswert").mean()
    print(f"  {mode:<20} n={len(g):<4} LES={les:.1%}  keep={(g['ykeep']==1).mean():.1%}")

# Blind-Screening-Teilmenge bestimmen (alles, was NICHT intentional-positiv ist)
INTENTIONAL = {"citation", "mixed", "trigger", "complementarity", "coauthor"}
df["blind"] = ~df["selection_mode"].isin(INTENTIONAL)
print(f"\nBlind-Teilmenge: n={df['blind'].sum()} (keep={df.loc[df.blind,'ykeep'].mean():.1%}) | "
      f"intentional: n={(~df['blind']).sum()} (keep={df.loc[~df.blind,'ykeep'].mean():.1%})")

# OOF-LogReg own+content, dann getrennt auswerten
feats = E.OWN_WORK + E.CONTENT
X = df[feats].astype(float)
mk = lambda: make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                           LogisticRegression(max_iter=3000, class_weight="balanced"))
df["oof"] = E.cv_oof(mk, X, df["y3"]).values
print("\n=== LogReg own+content — Performance nach Herkunft ===")
for label, mask in [("ALLE", np.ones(len(df), bool)), ("BLIND", df["blind"].values),
                    ("intentional-positiv", (~df["blind"]).values)]:
    sub = df[mask]
    m = E.metrics(sub["y3"], sub["oof"])
    print(f"  {label:<20} n={mask.sum():<4} f1_3cls={m['f1_3cls']:.3f} f1_keep={m['f1_keep']:.3f} LES-Rec={m['les_recall']:.3f}")
