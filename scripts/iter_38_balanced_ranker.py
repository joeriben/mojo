"""Iter 38 — per-Verortung-balancierter Ranker (Reparatur des blinden Flecks aus Iter 37).

Iter 37: globaler rich-Schwerpunkt ist ÄKB-dominiert → digitale_kultur/resilienz-keeper ranken tief.
Reparatur: pro Diskursraum einen Eigenwerk-Schwerpunkt (aus discourse-gelabelten Publikationen,
own_refs.discourse_json), Artikel gegen den Schwerpunkt SEINES Raums (journal_clusters) ranken.
Hebt das die Frontier, ohne den Kern zu beschädigen?
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3, json
import numpy as np, pandas as pd
import fm_eval as E
from sentence_transformers import SentenceTransformer

df = E.load().reset_index(drop=True)
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr=(df["selection_mode"].fillna("")=="screening").values
yk=df["ykeep"].values
# Publikationen mit discourse + Text
con=sqlite3.connect("own_refs.db")
pubs=pd.read_sql_query("SELECT title,venue,discourse_json FROM publications WHERE title IS NOT NULL",con); con.close()
m=SentenceTransformer("all-MiniLM-L6-v2"); nrm=lambda M:M/(np.linalg.norm(M,axis=1,keepdims=True)+1e-9)
ptext=(pubs["title"].fillna("")+". "+pubs["venue"].fillna("")).tolist()
PV=nrm(np.asarray(m.encode(ptext,show_progress_bar=False)))
# per-Diskurs-Schwerpunkt
disc_cent={}
for i,row in pubs.iterrows():
    try: ds=json.loads(row["discourse_json"]) if row["discourse_json"] else []
    except: ds=[]
    for d in ds: disc_cent.setdefault(d,[]).append(PV[i])
disc_cent={d:nrm(np.mean(v,axis=0,keepdims=True)) for d,v in disc_cent.items() if len(v)>=3}
glob_cent=nrm(PV.mean(axis=0,keepdims=True))

art_text=(df["title"].fillna("")+". "+df["abstract"].fillna("")+". "+df["concepts"].fillna("").str.replace("|"," ")).tolist()
A=nrm(np.asarray(m.encode(art_text,show_progress_bar=False)))
for f in ["diskursraeume.json","journal_bot/data/diskursraeume.json"]:
    try: JC=json.load(open(f)).get("journal_clusters",{}); break
    except Exception: JC={}
def jdisc(j):
    v=JC.get(j) or JC.get(str(j).lower())
    if isinstance(v,dict): v=v.get("clusters") or list(v.values())
    return [x for x in (v if isinstance(v,list) else []) if x in disc_cent]

s_global=(A@glob_cent.T).ravel()
s_bal=np.array([max([(A[i]@disc_cent[d].T).item() for d in jdisc(df.iloc[i]["journal_short"])], default=(A[i]@glob_cent.T).item()) for i in range(len(df))])

sidx=np.where(scr)[0]
def rank(s,i): return (s[scr]<s[i]).mean()
rows={}
for i in sidx:
    for d in (jdisc(df.iloc[i]["journal_short"]) or ["(?)"]):
        if yk[i]==1: rows.setdefault(d,{"g":[],"b":[]}); rows[d]["g"].append(rank(s_global,i)); rows[d]["b"].append(rank(s_bal,i))
print(f"keeper-Rang pro Diskursraum: global-Schwerpunkt → balanciert")
print(f"  {'Diskursraum':<30}{'keeper':>7}{'global':>9}{'balanciert':>12}")
for d,v in sorted(rows.items(),key=lambda x:-len(x[1]['g'])):
    if v["g"]: print(f"  {d:<30}{len(v['g']):>7}{np.mean(v['g']):>8.0%}{np.mean(v['b']):>12.0%}")
from sklearn.metrics import roc_auc_score
print(f"\nblind keep-AUC: global {roc_auc_score(yk[scr],s_global[scr]):.3f} → balanciert {roc_auc_score(yk[scr],s_bal[scr]):.3f}")
