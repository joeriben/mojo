"""Iter 46 — Confidence-banded Operating Point: drei Zonen statt Scheinsicherheit.

Statt jeden Artikel hart keep/drop zu labeln (M-C-AUC 0.66 → ~34 % Fehlordnung), die Ausgabe in drei
Zonen schneiden:
  sicher-DROP   (M-C < t_lo)        → auto-ignorieren, KEIN LLM
  unsicher      (t_lo ≤ M-C < t_hi) → an LLM/Volltext-Lektüre eskalieren
  sicher-KEEP   (M-C ≥ t_hi)        → auto-surface
Ziel: t_lo so, dass im DROP-Band 0 LES verloren gehen (Serendipitäts-Schutz); t_hi so, dass das
KEEP-Band hohe Precision hat. Misst, wie groß das teure Mittelband (LLM) sein MUSS, um 100 % LES-Recall
zu halten. Auf dem BLINDEN Strom (ehrlich), M-C seed-gemittelt.
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.model_selection import StratifiedKFold

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left")
yk = df["ykeep"].values; les = (df["y3"] == "lesenswert").values
rich = df["rich_sim"].astype(float).values
biblio = ((df["f_own_coupling_union"].fillna(0) >= 1) | (df["f_citation_hit_count"].fillna(0) >= 1)).values
scr = (df["selection_mode"] == "screening").values
z = lambda v: (v - np.nanmin(v)) / (np.nanmax(v) - np.nanmin(v) + 1e-9)
SEEDS = [11, 23, 42, 77, 101]

# M-C seed-gemittelt (Rang ist stabil; wir mitteln den Score)
mcs = []
for s in SEEDS:
    pj = np.zeros(len(df)); G = np.zeros(len(df))
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=s).split(df, yk):
        g = yk[tr].mean(); rate = {}
        for j, sub in df.iloc[tr].groupby("journal_short"):
            n = len(sub); rate[j] = (sub["ykeep"].mean() * n + g * 5) / (n + 5)
        for i in te: pj[i] = rate.get(df.iloc[i]["journal_short"], g); G[i] = g
    mc = z(z(rich) + 0.5 * z(np.maximum(0, pj - G)))
    mcs.append(np.where(biblio, 1.0 + mc, mc))
mc = np.mean(mcs, axis=0)

# Auf dem blinden Strom
m = scr
s, y, l = mc[m], yk[m], les[m]
order = np.argsort(s)
# t_lo: höchster Score, unter dem KEIN LES liegt → maximales sicheres DROP-Band
les_scores = s[l == 1]
t_lo = les_scores.min() - 1e-9 if l.sum() else s.max()
drop = s < t_lo
# t_hi: Score-Schwelle, ab der keep-Precision ≥ 80 % (oder Top, falls unerreichbar)
cands = np.unique(s)[::-1]; t_hi = s.max() + 1
for c in cands:
    sel = s >= c
    if sel.sum() >= 3 and y[sel].mean() >= 0.80: t_hi = c; break
keep = s >= t_hi
mid = ~drop & ~keep

print(f"BLINDER Strom: n={m.sum()}, keep={y.sum()}, LES={l.sum()}, Basisrate keep={y.mean():.0%}\n")
def band(mask, name):
    n = mask.sum()
    if n == 0: print(f"  {name:<26} n=0"); return
    print(f"  {name:<26} n={n:3d} ({n/len(s):.0%}) | keep-rate {y[mask].mean():.0%} | "
          f"LES darin {l[mask].sum()} | keep {y[mask].sum()}")
band(drop, "sicher-DROP (kein LLM)")
band(mid,  "unsicher → LLM/Lektüre")
band(keep, "sicher-KEEP (auto)")
print(f"\nLES-Recall (keep+mid, also NICHT gedroppt): {l[~drop].sum()}/{l.sum()} = {l[~drop].sum()/max(1,l.sum()):.0%}")
print(f"LLM-Last (Mittelband): {mid.sum()}/{len(s)} = {mid.mean():.0%} der Artikel")
print(f"Eingesparte LLM-Calls (sicher-DROP + sicher-KEEP): {(drop|keep).mean():.0%}")
