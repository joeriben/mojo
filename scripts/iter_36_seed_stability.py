"""Iter 36 — Seed-/Split-Stabilität der Synthese-Kennwerte.

Phase E stützt sich auf Zahlen aus n=120/25 keep/8 LES. Wie stark streuen sie über CV-Seeds?
Beziffert die Konfidenz und entlarvt, welche Headline-Werte belastbar und welche Rauschen sind.
Streut: M-C blind-AUC, LES-Recall@20%, journal-prior blind-AUC, rich blind-AUC — über 20 Seeds.
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr=(df["selection_mode"].fillna("")=="screening").values
yk=df["ykeep"].values; les=(df["y3"]=="lesenswert").values
rich_raw=df["rich_sim"].astype(float).values
z=lambda v:(v-np.nanmin(v))/(np.nanmax(v)-np.nanmin(v)+1e-9)

def run_seed(seed):
    skf=StratifiedKFold(5,shuffle=True,random_state=seed)
    pj=np.zeros(len(df));G=np.zeros(len(df))
    for tr,te in skf.split(df,yk):
        g=yk[tr].mean();rate={}
        for j,sub in df.iloc[tr].groupby("journal_short"):
            n=len(sub);m=sub["ykeep"].mean();rate[j]=(m*n+g*5)/(n+5)
        for i in te: pj[i]=rate.get(df.iloc[i]["journal_short"],g); G[i]=g
    rich=z(rich_raw); mc=z(rich+0.5*z(np.maximum(0,pj-G)))
    yy=yk[scr]; ll=les[scr]
    auc_mc=roc_auc_score(yy,mc[scr]); auc_pj=roc_auc_score(yy,pj[scr]); auc_r=roc_auc_score(yy,rich[scr])
    k=int(round(0.20*scr.sum())); sel=np.argsort(-mc[scr])[:k]
    les20=ll[sel].sum()/ll.sum()
    return auc_mc,auc_pj,auc_r,les20

res=np.array([run_seed(s) for s in range(20)])
names=["M-C blind-AUC","journal-prior blind-AUC","rich blind-AUC","M-C LES-Recall@20%"]
print(f"Über 20 CV-Seeds (n=120 blind, 25 keep, 8 LES):")
print(f"  {'Kennwert':<26}{'Mittel':>8}{'Std':>7}{'Min':>7}{'Max':>7}{'Spanne':>9}")
for i,nm in enumerate(names):
    c=res[:,i]; print(f"  {nm:<26}{c.mean():>8.3f}{c.std():>7.3f}{c.min():>7.3f}{c.max():>7.3f}{c.max()-c.min():>9.3f}")
