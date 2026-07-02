"""Iter 16 — operativer Keep-Ranker: rich-Sim + Bibliometrie-Veto-up als Top-Anker.

Verbindet die zwei belastbaren Befunde: Bibliometrie ist hochpräzise (Iter 01, 0.83-1.0) aber selten;
rich-Sim ist der beste blinde Ranking-Hebel (Iter 15, 0.632). Operativer Ranker = rich-Sim, aber
Biblio-Treffer ganz nach oben. Deliverable: Recall@Sichtungslast-Kurve gegen den aktuellen M7-Score.
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.metrics import roc_auc_score

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr = (df["selection_mode"].fillna("")=="screening").values
yk = df["ykeep"].values

z = lambda v: (v - np.nanmin(v))/(np.nanmax(v)-np.nanmin(v)+1e-9)
rich = z(df["rich_sim"].astype(float).values)
m7 = df["score_M7_EmbeddingSimilarity"].astype(float).fillna(0).values
biblio = ((df["f_own_coupling_union"]>=1)|(df["f_citation_hit_count"]>=1)).values
# Veto-up: Biblio-Treffer auf >1 heben (über jeden rich-Wert), Reihenfolge darunter = rich
rich_veto = np.where(biblio, 1.0 + rich, rich)

def recall_at(score, y, fracs=(0.10,0.20,0.30,0.50)):
    order = np.argsort(-score); npos = y.sum()
    return [y[order[:int(f*len(score))]].sum()/npos for f in fracs]

for label, mask in [("GESAMT", np.ones(len(df),bool)), ("SCREENING (blind)", scr)]:
    yy = yk[mask]; npos = int(yy.sum())
    print(f"\n{label} (n={mask.sum()}, keep={npos}, Basisrate {yy.mean():.0%}):")
    print(f"  {'Ranker':<26}{'AUC':>7}{'R@10%':>8}{'R@20%':>8}{'R@30%':>8}{'R@50%':>8}")
    for name, s in [("M7 (aktuell)", m7), ("rich", rich), ("rich+Biblio-Veto", rich_veto)]:
        r = recall_at(s[mask], yy)
        auc = roc_auc_score(yy, s[mask])
        print(f"  {name:<26}{auc:>7.3f}" + "".join(f"{x:>8.0%}" for x in r))
