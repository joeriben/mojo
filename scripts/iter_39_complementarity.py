"""Iter 39 — Complementarity-Pool: trifft M-C die schwer-begründbaren keeper?

Memory feedback_ground_truth: 41% der LES aus complementarity-Quelle = die „Triage-Falle" (Algo+Opus
nur ~58-62% Agreement). Diese keeper sind NICHT über Zitation/Trigger offensichtlich, sondern
inhaltlich-komplementär. Reiht M-C sie ähnlich hoch wie die offensichtlichen (citation/trigger), oder
versagt es genau dort? Mittlerer M-C-Perzentil-Rang der keeper pro selection_mode.
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
yk=df["ykeep"].values; les=(df["y3"]=="lesenswert").values
z=lambda v:(v-np.nanmin(v))/(np.nanmax(v)-np.nanmin(v)+1e-9)
skf=StratifiedKFold(5,shuffle=True,random_state=42); pj=np.zeros(len(df));G=np.zeros(len(df))
for tr,te in skf.split(df,yk):
    g=yk[tr].mean();rate={}
    for j,sub in df.iloc[tr].groupby("journal_short"):
        n=len(sub);m=sub["ykeep"].mean();rate[j]=(m*n+g*5)/(n+5)
    for i in te: pj[i]=rate.get(df.iloc[i]["journal_short"],g);G[i]=g
mc=z(z(df["rich_sim"].astype(float).values)+0.5*z(np.maximum(0,pj-G)))
# Rang über die GANZE Menge (alle Quellen gemischt, wie der Ranker sie sähe)
rank=np.array([(mc<mc[i]).mean() for i in range(len(df))])

print(f"keeper-Rang (M-C, Perzentil) pro selection_mode:")
print(f"  {'selection_mode':<18}{'keeper':>8}{'Ø Rang':>9}{'rich-Rang':>11}{'biblio-Treffer':>15}")
rich_rank=np.array([(df['rich_sim'].values<df['rich_sim'].values[i]).mean() for i in range(len(df))])
biblio=((df["f_own_coupling_union"]>=1)|(df["f_citation_hit_count"]>=1)).values
for mode,sub in df[yk==1].groupby("selection_mode"):
    idx=sub.index.values
    print(f"  {str(mode):<18}{len(idx):>8}{rank[idx].mean():>8.0%}{rich_rank[idx].mean():>11.0%}{biblio[idx].mean():>14.0%}")
# Fokus complementarity vs citation/trigger
comp=df[(yk==1)&(df["selection_mode"]=="complementarity")].index.values
obv=df[(yk==1)&(df["selection_mode"].isin(["citation","trigger"]))].index.values
if len(comp) and len(obv):
    print(f"\ncomplementarity-keeper Ø Rang {rank[comp].mean():.0%} vs citation/trigger {rank[obv].mean():.0%}")
    print(f"  → {'M-C trifft komplementäre schlechter' if rank[comp].mean()<rank[obv].mean()-0.1 else 'vergleichbar'}")
