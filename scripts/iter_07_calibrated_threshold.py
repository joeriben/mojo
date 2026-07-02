"""Iter 07 — Kalibrierte Relevanz-Wahrscheinlichkeit + Threshold auf LES-Recall.

Iter 06: der reale Wert sitzt im blinden Strom (screening), wo LES selten (6.7%) ist.
Iter 03/05: class_weight=balanced ist brutal. Hier: kalibrierte P(keep)/P(LES) + bewusst
gewählter Threshold, sauber out-of-fold, getrennt auf screening-only ausgewertet.
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
df["screening"] = df["selection_mode"].fillna("") == "screening"

feats = E.OWN_WORK + E.CONTENT
X = df[feats].astype(float).values
y = df["y3"].values
ykeep = df["ykeep"].values

def base():
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         LogisticRegression(max_iter=3000))

# OOF kalibrierte P(keep): binär keep vs ign
skf = StratifiedKFold(5, shuffle=True, random_state=42)
pkeep = np.zeros(len(df))
for tr, te in skf.split(X, ykeep):
    clf = CalibratedClassifierCV(base(), method="isotonic", cv=3)
    clf.fit(X[tr], ykeep[tr])
    j = list(clf.classes_).index(1)
    pkeep[te] = clf.predict_proba(X[te])[:, j]

def keep_at(thr):
    return (pkeep >= thr).astype(int)

print("Threshold-Sweep P(keep) — gesamt vs screening-only:")
print(f"{'thr':>5}{'keepF1·all':>11}{'keepRec·all':>12}{'keepF1·scr':>11}{'keepRec·scr':>12}{'keepN·scr':>10}")
scr = df["screening"].values
for thr in [0.3, 0.4, 0.5, 0.6, 0.7]:
    pred = keep_at(thr)
    from sklearn.metrics import f1_score, recall_score
    fa = f1_score(ykeep, pred, zero_division=0); ra = recall_score(ykeep, pred, zero_division=0)
    fs = f1_score(ykeep[scr], pred[scr], zero_division=0); rs = recall_score(ykeep[scr], pred[scr], zero_division=0)
    print(f"{thr:>5}{fa:>11.3f}{ra:>12.3f}{fs:>11.3f}{rs:>12.3f}{pred[scr].sum():>10}")

# Reliabilität: ist die Kalibrierung ehrlich? (mittlere P(keep) vs reale keep-Rate je Bin)
print("\nKalibrierung (Bin: mittlere P(keep) → reale keep-Rate, n):")
bins = pd.cut(pkeep, [0,.2,.4,.6,.8,1.0])
for b, g in pd.DataFrame({"p": pkeep, "y": ykeep, "b": bins}).groupby("b", observed=True):
    print(f"  {str(b):<12} P̄={g['p'].mean():.2f}  real={g['y'].mean():.2f}  n={len(g)}")
