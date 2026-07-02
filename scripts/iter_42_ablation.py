"""Iter 42 — Feature-Ablation: welches Signal trägt M-C wirklich?

M-C = z(z(rich_sim) + 0.5*z(max(0,pj-G)))  danach Biblio-Veto-Up: where(biblio, 1+mc, mc).
Drop-one-out: jede Komponente einzeln entfernen, keep-AUC + LES-Recall@20% messen, ÜBER SEEDS
gemittelt (P15: keine Glücksseed-Punktwerte, Spannen). Liefert die Essenz-vs-Schmuck-Bilanz für M-E.
"""
import sys; sys.path.insert(0, "scripts")
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
yk = df["ykeep"].values
les = (df["y3"] == "lesenswert").values
rich = df["rich_sim"].astype(float).values
biblio = ((df["f_own_coupling_union"] >= 1) | (df["f_citation_hit_count"] >= 1)).values
z = lambda v: (v - np.nanmin(v)) / (np.nanmax(v) - np.nanmin(v) + 1e-9)
SEEDS = [11, 23, 42, 77, 101]

def pj_for(seed):
    pj = np.zeros(len(df)); G = np.zeros(len(df))
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=seed).split(df, yk):
        g = yk[tr].mean(); rate = {}
        for j, sub in df.iloc[tr].groupby("journal_short"):
            n = len(sub); rate[j] = (sub["ykeep"].mean() * n + g * 5) / (n + 5)
        for i in te:
            pj[i] = rate.get(df.iloc[i]["journal_short"], g); G[i] = g
    return pj, G

def les_recall_at(score, frac=0.20):
    k = max(1, int(round(frac * len(score))))
    top = np.argsort(-score)[:k]
    return les[top].sum() / les.sum()

variants = {
    "M-C voll (rich+Prior+Biblio-Veto)": lambda rich_, pj, G: _mc(rich_, pj, G, biblio),
    "ohne Biblio-Veto":                  lambda rich_, pj, G: _mc(rich_, pj, G, np.zeros(len(df), bool)),
    "ohne Journal-Prior":                lambda rich_, pj, G: _mc(rich_, pj * 0, G * 0, biblio),
    "ohne rich_sim (nur Prior+Veto)":    lambda rich_, pj, G: _mc(np.zeros(len(df)), pj, G, biblio),
}
def _mc(rich_, pj, G, bib):
    mc = z(z(rich_) + 0.5 * z(np.maximum(0, pj - G)))
    return np.where(bib, 1.0 + mc, mc)

print(f"Ablation (seed-gemittelt über {len(SEEDS)} Seeds): keep-AUC | LES-Recall@20%")
rows = {}
for name in variants:
    aucs, recs = [], []
    for s in SEEDS:
        pj, G = pj_for(s)
        sc = variants[name](rich, pj, G)
        aucs.append(roc_auc_score(yk, sc)); recs.append(les_recall_at(sc))
    rows[name] = (np.mean(aucs), np.std(aucs), np.mean(recs), np.std(recs))
    print(f"  {name:<36} {np.mean(aucs):.3f}±{np.std(aucs):.3f} | "
          f"{np.mean(recs):.0%}±{np.std(recs)*100:.0f}pp")

full = rows["M-C voll (rich+Prior+Biblio-Veto)"]
print(f"\nBeitrag jeder Komponente (Δ keep-AUC vs voll {full[0]:.3f}):")
for name in variants:
    if name == "M-C voll (rich+Prior+Biblio-Veto)": continue
    comp = {"ohne Biblio-Veto": "Biblio-Veto", "ohne Journal-Prior": "Journal-Prior",
            "ohne rich_sim (nur Prior+Veto)": "rich_sim"}[name]
    print(f"  {comp:<16} trägt {full[0]-rows[name][0]:+.3f} AUC")
