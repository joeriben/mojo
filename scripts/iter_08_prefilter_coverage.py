"""Iter 08 — 2-Stufen-Vorfilter: Kosten/Coverage-Frontier.

Iter 07 zeigt: der Filter taugt als hoher-Recall-Vorfilter, nicht als Urteil. Frage:
bei welchem keep-Recall schrumpft die LLM-Kandidatenmenge wie stark? (Memory-Ziel:
~50-60% Inferenz-Ersparnis). Gemessen gesamt UND screening-only (realer Strom).
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV

df = E.load().reset_index(drop=True)
con = sqlite3.connect("articles.db")
sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left")
scr = (df["selection_mode"].fillna("") == "screening").values

X = df[E.OWN_WORK + E.CONTENT].astype(float).values
yk = df["ykeep"].values
skf = StratifiedKFold(5, shuffle=True, random_state=42)
p = np.zeros(len(df))
for tr, te in skf.split(X, yk):
    clf = CalibratedClassifierCV(make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                 LogisticRegression(max_iter=3000)), method="isotonic", cv=3)
    clf.fit(X[tr], yk[tr]); j = list(clf.classes_).index(1)
    p[te] = clf.predict_proba(X[te])[:, j]

def frontier(mask, label):
    pk, yy = p[mask], yk[mask]
    print(f"\n{label} (n={mask.sum()}, keep={yy.sum()}):")
    print(f"  {'Ziel-Recall':>11}{'thr':>7}{'behaltene Kand.':>16}{'Ersparnis':>11}{'realer Recall':>14}")
    for target in [0.99, 0.95, 0.90, 0.80]:
        # größte Schwelle, die noch >= target keep-Recall hält
        thrs = np.unique(pk)
        best = 0.0
        for t in thrs:
            if (pk[yy == 1] >= t).mean() >= target:
                best = t
        kept = (pk >= best).mean()
        rec = (pk[yy == 1] >= best).mean()
        print(f"  {target:>11.0%}{best:>7.2f}{kept:>15.0%}{1-kept:>11.0%}{rec:>14.0%}")

frontier(np.ones(len(df), bool), "GESAMT")
frontier(scr, "SCREENING (realer blinder Strom)")
