"""Iter 40 — Journal-Holdout: generalisiert der EB-Journal-Prior auf UNGESEHENE Journals?

Ehrlichkeitsbefund aus dem Ledger: die „Bar" hatte einen Per-Journal-Leak (Prior aus denselben Zeilen
gelernt, gegen die getestet wird). StratifiedKFold mischt Journals über Train/Test — ein Journal ist
in beiden. Der harte Test: GroupKFold NACH Journal — jedes Test-Journal ist im Train NICHT gesehen.
Dann fällt der Prior auf den globalen Schnitt G zurück (max(0,pj-G)=0) → M-C kollabiert auf rich-only.
Das misst, wie viel der Journal-Prior auf wirklich NEUEN Journals beiträgt (Erwartung: ~0) — und
ordnet den Befund ein (die Scout-Watchlist ist fix ~49 Journals, also sind Journals in Produktion
fast immer BEKANNT; GroupKFold ist das pessimistische, selten reale Szenario).
"""
import sys; sys.path.insert(0, "scripts")
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.model_selection import StratifiedKFold, GroupKFold
from sklearn.metrics import roc_auc_score

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
yk = df["ykeep"].values
z = lambda v: (v - np.nanmin(v)) / (np.nanmax(v) - np.nanmin(v) + 1e-9)
rich = df["rich_sim"].astype(float).values

# Journal-Landschaft im Gold
nj = df["journal_short"].nunique()
vc = df["journal_short"].value_counts()
sings = (vc == 1).sum()
print(f"Journal-Landschaft: {nj} unique Journals, {sings} Singletons, "
      f"Top-Journal {vc.iloc[0]} Artikel ({vc.index[0]})")

def pj_cv(splitter, groups=None):
    pj = np.zeros(len(df)); G = np.zeros(len(df))
    it = splitter.split(df, yk, groups) if groups is not None else splitter.split(df, yk)
    for tr, te in it:
        g = yk[tr].mean(); rate = {}
        for j, sub in df.iloc[tr].groupby("journal_short"):
            n = len(sub); m = sub["ykeep"].mean(); rate[j] = (m * n + g * 5) / (n + 5)
        for i in te:
            pj[i] = rate.get(df.iloc[i]["journal_short"], g); G[i] = g
    return pj, G

# (a) StratifiedKFold — Journal in Train UND Test (optimistisch, der gewohnte Messmodus)
pj_s, G_s = pj_cv(StratifiedKFold(5, shuffle=True, random_state=42))
mc_s = z(z(rich) + 0.5 * z(np.maximum(0, pj_s - G_s)))
# (b) GroupKFold nach Journal — Test-Journal im Train UNGESEHEN (pessimistisch, ehrlich für neue Journals)
pj_g, G_g = pj_cv(GroupKFold(5), groups=df["journal_short"].values)
mc_g = z(z(rich) + 0.5 * z(np.maximum(0, pj_g - G_g)))
# Anteil Test-Zeilen, deren Prior auf G zurückfiel (= ungesehenes Journal)
fellback = np.isclose(pj_g, G_g).mean()

print(f"\nkeep-AUC (alle Quellen):")
print(f"  rich-only                         {roc_auc_score(yk, rich):.3f}")
print(f"  M-C  StratifiedKFold (Journal bekannt)  {roc_auc_score(yk, mc_s):.3f}")
print(f"  M-C  GroupKFold      (Journal UNGESEHEN) {roc_auc_score(yk, mc_g):.3f}")
print(f"  → {fellback:.0%} der GroupKFold-Test-Zeilen fielen auf G zurück (Prior trug dort 0 bei)")
print(f"  Prior-Beitrag = AUC(Strat) − AUC(rich): {roc_auc_score(yk,mc_s)-roc_auc_score(yk,rich):+.3f}")
print(f"  davon generalisiert auf neue Journals : {roc_auc_score(yk,mc_g)-roc_auc_score(yk,rich):+.3f}")
