"""Iter 05 — Per-Journal-Basisrate als Prior (der strukturelle Hebel zur Algo-Bar).

Drei verschiedene Lerner stranden bei ~0.51 (Iter 03/04). M9_PerJournalBase=0.603.
Hypothese: die Lücke ist die Journal-Basisrate (manche Journals sind fast immer ign,
andere oft keep). Prior STRENG out-of-fold aus dem Train-Fold (P3/P5, kein Leak).
"""
import sys; sys.path.insert(0, "scripts")
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression

df = E.load().reset_index(drop=True)
L = E.LABELS3
feats = E.OWN_WORK + E.CONTENT
X = df[feats].astype(float).values
y = df["y3"].values
jour = df["journal_short"].values

def journal_prior(tr_idx, alpha=2.0):
    glob = pd.Series(y[tr_idx]).value_counts(normalize=True)
    gv = np.array([glob.get(c, 0) for c in L]); gv = gv / gv.sum()
    pri = {}
    for j in np.unique(jour[tr_idx]):
        sub = y[tr_idx][jour[tr_idx] == j]
        cnt = np.array([(sub == c).sum() for c in L], float) + alpha * gv
        pri[j] = cnt / cnt.sum()
    return pri, gv

def lr(): return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                               LogisticRegression(max_iter=3000, class_weight="balanced"))

skf = StratifiedKFold(5, shuffle=True, random_state=42)
oof_prior = np.empty(len(df), object)
oof_blend = np.empty(len(df), object)
for tr, te in skf.split(X, y):
    pri, gv = journal_prior(tr)
    P = np.array([pri.get(jour[i], gv) for i in te])      # Journal-Prior je Test-Zeile
    oof_prior[te] = [L[k] for k in P.argmax(1)]
    m = lr(); m.fit(X[tr], y[tr])
    proba = m.predict_proba(X[te])
    order = list(m.classes_)
    proba = proba[:, [order.index(c) for c in L]]          # auf L-Reihenfolge bringen
    blend = proba * P                                       # Prior × Modell
    oof_blend[te] = [L[k] for k in blend.argmax(1)]

print("[Per-Journal-Prior allein     ]", E.metrics(df["y3"], pd.Series(oof_prior)))
print("[Prior × LogReg(own+content)  ]", E.metrics(df["y3"], pd.Series(oof_blend)))
print("\nReferenz: LogReg own+content 0.514 · Algo-Bar(M9 PerJournal) 0.603 · LLM 0.679")
