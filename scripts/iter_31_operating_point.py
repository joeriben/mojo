"""Iter 31 — Modell M-C Betriebspunkt-Tabelle (Synthese-Start).

Das empfohlene blinde Ranking-Modell aus 01-30:
  M-C = mean(rich-Content, journal-prior-lift-only) + Bibliometrie-Präzisions-Anker (Veto-up).
Hier als BETRIEBSPUNKT gemessen: bei Sichtungslast X% — keep-Recall, keep-Precision, LES-Recall.
Das sind die Zahlen für die Cutoff-Entscheidung (nicht eine Headline-AUC).
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.model_selection import StratifiedKFold

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr=(df["selection_mode"].fillna("")=="screening").values
yk=df["ykeep"].values; les=(df["y3"]=="lesenswert").values
skf=StratifiedKFold(5,shuffle=True,random_state=42)
def eb(tr,te,k=5):
    g=yk[tr].mean();rate={}
    for j,sub in df.iloc[tr].groupby("journal_short"):
        n=len(sub);m=sub["ykeep"].mean();rate[j]=(m*n+g*k)/(n+k)
    return np.array([rate.get(df.iloc[i]["journal_short"],g) for i in te]),g
pj=np.zeros(len(df));G=np.zeros(len(df))
for tr,te in skf.split(df,yk): pj[te],g=eb(tr,te); G[te]=g
z=lambda v:(v-np.nanmin(v))/(np.nanmax(v)-np.nanmin(v)+1e-9)
rich=z(df["rich_sim"].astype(float).values)
lift=z(np.maximum(0,pj-G))
biblio=((df["f_own_coupling_union"]>=1)|(df["f_citation_hit_count"]>=1)).values
mc=rich+0.5*lift
mc=np.where(biblio,1.0+z(mc),z(mc))   # Bibliometrie-Anker ganz oben

s=mc[scr]; yy=yk[scr]; ll=les[scr]; order=np.argsort(-s); n=len(s)
print(f"Modell M-C — blinder Strom (n={n}, keep={yy.sum()}, LES={ll.sum()}, Basisrate keep {yy.mean():.0%})")
print(f"  {'Sichtungslast':>13}{'gelesen':>9}{'keep-Recall':>13}{'keep-Prec':>11}{'LES-Recall':>12}")
for f in [0.10,0.20,0.30,0.40,0.50,0.70,1.00]:
    k=int(round(f*n)); sel=order[:k]
    rec=yy[sel].sum()/yy.sum(); prec=yy[sel].mean(); lrec=ll[sel].sum()/ll.sum()
    print(f"  {f:>12.0%}{k:>9}{rec:>13.0%}{prec:>11.0%}{lrec:>12.0%}")
print("\nReferenz M7 (aktuell) zum Vergleich:")
s2=df["score_M7_EmbeddingSimilarity"].astype(float).fillna(0).values[scr]; o2=np.argsort(-s2)
for f in [0.20,0.50]:
    k=int(round(f*n)); sel=o2[:k]
    print(f"  M7 @{f:.0%}: keep-Recall {yy[sel].sum()/yy.sum():.0%}, LES-Recall {ll[sel].sum()/ll.sum():.0%}")
