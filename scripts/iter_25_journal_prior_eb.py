"""Iter 25 — Journal-Prior-Stabilität (Empirical-Bayes-Shrinkage).

Iter 05: roher Per-Journal-Prior = in-sample-Leak (0.603→0.544 ehrlich). Frage: taugt ein
EB-geshrinkter Prior (jedes Journal zur Globalrate gezogen, proportional zur Dünne) als schwacher
Zusatz-Anker auf dem blinden Strom — oder ist die Per-Journal-Masse zu verrauscht? OOF gemessen.
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score

df = E.load().reset_index(drop=True)
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr=(df["selection_mode"].fillna("")=="screening").values
yk = df["ykeep"].values

jc = df.groupby("journal_short")["ykeep"].agg(["count","mean"]).sort_values("count", ascending=False)
print(f"Journals gesamt: {df['journal_short'].nunique()}, Median Artikel/Journal: {jc['count'].median():.0f}")
print(f"Journals mit >=10 Artikeln: {(jc['count']>=10).sum()}, mit ==1: {(jc['count']==1).sum()}")
print("Top-5 (n, keep-Rate):", [(j, int(r['count']), f"{r['mean']:.0%}") for j,r in jc.head(5).iterrows()])

def eb_prior(train_idx, eval_idx, k):
    """Empirical-Bayes: journal-keep-Rate zur Globalrate gezogen mit Pseudo-Count k."""
    g = yk[train_idx].mean()
    rate = {}
    tdf = df.iloc[train_idx]
    for j, sub in tdf.groupby("journal_short"):
        n = len(sub); m = sub["ykeep"].mean()
        rate[j] = (m*n + g*k)/(n + k)
    return np.array([rate.get(df.iloc[i]["journal_short"], g) for i in eval_idx])

# OOF: für jeden k den EB-Prior als keep-Score, AUC gesamt + screening
skf = StratifiedKFold(5, shuffle=True, random_state=42)
print(f"\n{'Shrinkage k':>12}{'AUC gesamt':>13}{'AUC screening':>15}")
for k in [0, 2, 5, 10, 20]:
    p = np.zeros(len(df))
    for tr, te in skf.split(df, yk):
        p[te] = eb_prior(tr, te, k)
    auc_all = roc_auc_score(yk, p)
    auc_scr = roc_auc_score(yk[scr], p[scr])
    tag = " (k=0: roh/Leak-nah)" if k==0 else ""
    print(f"{k:>12}{auc_all:>13.3f}{auc_scr:>15.3f}{tag}")
print(f"\nReferenz Globalrate-AUC = 0.500 (kein Signal); rich-Ranker screening-AUC = 0.632 (Iter 16)")
