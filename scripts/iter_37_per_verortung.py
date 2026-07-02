"""Iter 37 — Per-Verortung-Fairness: vernachlässigt M-C eine disziplinäre Heimat?

Benjamin hat 5-7 Verortungen mit verschiedenen Signal-Stärken. Fairness-Diagnostik (NICHT Relevanz-
Signal): blind-keeper über journal_clusters den Diskursräumen zuordnen, dann den mittleren M-C-
Perzentil-Rang pro Raum. Ein Raum, dessen keeper systematisch tief ranken, wird vom Scout vernachlässigt.
Perzentil-Rang (statt Recall@k) ist bei kleinem n stabiler.
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3, json
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.model_selection import StratifiedKFold

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr=(df["selection_mode"].fillna("")=="screening").values
yk=df["ykeep"].values; les=(df["y3"]=="lesenswert").values
z=lambda v:(v-np.nanmin(v))/(np.nanmax(v)-np.nanmin(v)+1e-9)
skf=StratifiedKFold(5,shuffle=True,random_state=42); pj=np.zeros(len(df));G=np.zeros(len(df))
for tr,te in skf.split(df,yk):
    g=yk[tr].mean();rate={}
    for j,sub in df.iloc[tr].groupby("journal_short"):
        n=len(sub);m=sub["ykeep"].mean();rate[j]=(m*n+g*5)/(n+5)
    for i in te: pj[i]=rate.get(df.iloc[i]["journal_short"],g);G[i]=g
mc=z(z(df["rich_sim"].astype(float).values)+0.5*z(np.maximum(0,pj-G)))

# journal → Diskursräume
for f in ["diskursraeume.json","journal_bot/data/diskursraeume.json"]:
    try: JC=json.load(open(f)).get("journal_clusters",{}); break
    except Exception: JC={}
def spaces(j):
    v=JC.get(j) or JC.get(str(j).lower())
    if isinstance(v,dict): v=v.get("clusters") or list(v.values())
    return v if isinstance(v,list) else ([v] if v else ["(unbekannt)"])

sc=mc[scr]; sidx=np.where(scr)[0]
pct = {i: (sc < mc[i]).mean() for i in sidx}   # Perzentil im blinden Strom
rows={}
for i in sidx:
    for sp in spaces(df.iloc[i]["journal_short"]):
        rows.setdefault(sp,{"n":0,"keep":0,"keep_pct":[]})
        rows[sp]["n"]+=1
        if yk[i]==1: rows[sp]["keep"]+=1; rows[sp]["keep_pct"].append(pct[i])
print(f"Per-Diskursraum (blinder Strom), mittlerer M-C-Perzentil-Rang der keeper:")
print(f"  {'Diskursraum':<30}{'Artikel':>8}{'keeper':>8}{'Ø keeper-Rang':>16}")
for sp,d in sorted(rows.items(), key=lambda x:-x[1]["n"]):
    mp=np.mean(d["keep_pct"]) if d["keep_pct"] else float("nan")
    print(f"  {sp:<30}{d['n']:>8}{d['keep']:>8}{mp:>15.0%}")
print("\n(höherer Ø keeper-Rang = besser bedient; ein Raum mit deutlich niedrigem Rang wird vernachlässigt)")
