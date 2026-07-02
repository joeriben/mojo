"""Iter 32 — Modell M-C vs MOJO-1 LLM-agent_verdict (der 2.0-vs-1.x-Test).

agent_verdict = die diskrete MOJO-1-LLM-Triage (ignorieren/scannen/lesenswert). Sie definiert implizit
eine Sichtungslast (ihr keep-Anteil). Fairer Vergleich: M-C (algorithmisch) bei DERSELBEN Last — fängt
es ebenso viele LES wie der teure LLM-Agent? Plus M7/rich als Zwischenstufen. Blinder Strom.
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
KEEP=E.KEEP
agent_keep = df["agent_verdict"].isin(KEEP).values

skf=StratifiedKFold(5,shuffle=True,random_state=42)
def eb(tr,te,k=5):
    g=yk[tr].mean();rate={}
    for j,sub in df.iloc[tr].groupby("journal_short"):
        n=len(sub);m=sub["ykeep"].mean();rate[j]=(m*n+g*k)/(n+k)
    return np.array([rate.get(df.iloc[i]["journal_short"],g) for i in te]),g
pj=np.zeros(len(df));G=np.zeros(len(df))
for tr,te in skf.split(df,yk): pj[te],g=eb(tr,te);G[te]=g
z=lambda v:(v-np.nanmin(v))/(np.nanmax(v)-np.nanmin(v)+1e-9)
rich=z(df["rich_sim"].astype(float).values)
mc=z(rich+0.5*z(np.maximum(0,pj-G)))
biblio=((df["f_own_coupling_union"]>=1)|(df["f_citation_hit_count"]>=1)).values
mc=np.where(biblio,1.0+mc,mc)
m7=df["score_M7_EmbeddingSimilarity"].astype(float).fillna(0).values

S=scr
n=S.sum(); yy=yk[S]; ll=les[S]
# Agent-Betriebspunkt
ak=agent_keep[S]; a_load=ak.mean()
a_rec=yy[ak].sum()/yy.sum(); a_prec=yy[ak].mean(); a_lrec=ll[ak].sum()/ll.sum()
print(f"Blinder Strom: n={n}, keep={yy.sum()}, LES={ll.sum()}")
print(f"\nMOJO-1 agent_verdict: Last {a_load:.0%} ({ak.sum()} behalten), keep-Recall {a_rec:.0%}, "
      f"keep-Prec {a_prec:.0%}, LES-Recall {a_lrec:.0%}")
print(f"\nAlgorithmische Ranker bei GLEICHER Last ({a_load:.0%}):")
k=int(round(a_load*n))
print(f"  {'Modell':<22}{'keep-Recall':>13}{'keep-Prec':>11}{'LES-Recall':>12}")
for name,s in [("M-A (M7, ~MOJO-1-Score)",m7),("M-B (rich)",rich),("M-C (rich+journal+anker)",mc)]:
    sel=np.argsort(-s[S])[:k]
    print(f"  {name:<22}{yy[sel].sum()/yy.sum():>13.0%}{yy[sel].mean():>11.0%}{ll[sel].sum()/ll.sum():>12.0%}")
print(f"\n(Agent behält {ak.sum()} Artikel via teurem LLM-Call; Ranker brauchen 0 LLM-Calls für die Reihung.)")
