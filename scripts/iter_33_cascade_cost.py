"""Iter 33 — Vorfilter-Kaskade: M-C reiht → LLM-Agent entscheidet die Spitze.

Iter 32: LLM-only = 88% LES-Recall @120 Calls. Kaskade: Algo behält Top-X%, LLM läuft NUR darauf.
Frage: Kosten (LLM-Calls) vs LES-Recall — wie viel Last spart die Reihung, ohne LES vor dem LLM zu
verlieren? Gegen Iter 08 (Vorfilter spart bei hohem Recall wenig). Kaskade-Recall = LES, die Algo
DURCHLÄSST und LLM dann behält.
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
agent_keep=df["agent_verdict"].isin(E.KEEP).values
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

S=scr; n=S.sum(); ll=les[S]; ak=agent_keep[S]; order=np.argsort(-mc[S])
les_total=ll.sum()
llm_only = ll[ak].sum()/les_total
print(f"Blinder Strom n={n}, LES={les_total}.")
print(f"LLM-only (kein Vorfilter): LES-Recall {llm_only:.0%} bei {n} LLM-Calls (100% Last)\n")
print(f"Kaskade M-C→LLM:  {'Algo-Cutoff':>11}{'LLM-Calls':>10}{'Kosten':>8}{'LES-Recall (Kaskade)':>22}")
for f in [0.20,0.30,0.40,0.50,0.70]:
    k=int(round(f*n)); kept=np.zeros(n,bool); kept[order[:k]]=True
    casc = (ll & kept & ak).sum()/les_total      # LES: durchgelassen UND vom LLM behalten
    print(f"  {'':>0}{f:>11.0%}{k:>10}{f:>8.0%}{casc:>21.0%}")
print("\nLese-Hinweis: Kaskade-LES-Recall < LLM-only, weil der Algo LES VOR dem LLM wegschneidet.")
