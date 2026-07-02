"""Iter 19 — substitutiver Eintrags-Komponist + Ehrlichkeits-Messung.

Festlegung feedback_llm_bezuege_konfabulation: Eintrag substitutiv komponieren (Abstract verbatim +
Signale + GEERDETE Bezüge), LLM raus aus der Erzähler-Rolle. Hier: Komponist, der pro keeper einen
Eintrag baut, und die Verteilung der Eintrags-Typen misst — (a) konkreter Bezug, (b) nur Score,
(c) bewusste Leerstelle. KEIN LLM, jede benannte Bezugnahme ist verifizierbar.
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3, json
import numpy as np, pandas as pd
import fm_eval as E
from collections import defaultdict

norm = lambda s: str(s).rsplit("/",1)[-1].strip() if s else ""
df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
con = sqlite3.connect("articles.db")
ids = ",".join(f"'{i}'" for i in df["id"].astype(str))
arefs = {aid:set() for aid in df["id"]}
for aid, oaref in con.execute(f"SELECT id, openalex_refs FROM articles WHERE id IN ({ids})"):
    if oaref:
        try: arefs[aid]={norm(x.get('id') if isinstance(x,dict) else x) for x in json.loads(oaref)}
        except Exception: pass
sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()

# own: ref_oa → [pub_titel]
con = sqlite3.connect("own_refs.db")
pubtitle = {c:(t,y) for c,t,y in con.execute("SELECT canonical_id,title,year FROM publications")}
ref2pub = defaultdict(set)
for c,oa in con.execute("SELECT canonical_id,ref_oa_id FROM pub_refs WHERE ref_oa_id IS NOT NULL"):
    ref2pub[norm(oa)].add(c)
con.close()
# bezugsautor: work_oa → (author_name, work_title)
con = sqlite3.connect("bezugsautoren.db")
aname = {a:n for a,n in con.execute("SELECT author_oa_id,display_name FROM authors")}
work2author = {}
for aid_,wid,title in con.execute("SELECT author_oa_id,work_oa_id,title FROM author_works"):
    work2author[norm(wid)] = (aname.get(aid_,"?"), title)
con.close()

def compose(aid):
    a = arefs.get(aid,set())
    own_bez = sorted({pubtitle[c] for r in a for c in ref2pub.get(r,())}, key=lambda x:-(x[1] or 0))
    bez_cites = [work2author[r] for r in a if r in work2author]
    return own_bez, bez_cites

rich = (df["rich_sim"].astype(float) - df["rich_sim"].astype(float).min())
rich = rich/(rich.max()+1e-9)
thr = rich[df['ykeep'].values==1].quantile(0.33)   # „nennenswerter" Score = oberes 2/3 der keeper-Sim
typ=[]
for i,aid in enumerate(df["id"]):
    ob, bc = compose(aid)
    if ob or bc: typ.append("konkret")
    elif rich.iloc[i] >= thr: typ.append("score")
    else: typ.append("leer")
df["etype"]=typ
df=df.merge(sm,on="id",how="left"); scr=(df["selection_mode"].fillna("")=="screening").values

for label,mask in [("alle keeper", df['ykeep'].values==1), ("LES", (df['y3']=='lesenswert').values),
                   ("blind keeper", scr&(df['ykeep'].values==1))]:
    vc = df.loc[mask,"etype"].value_counts(normalize=True)
    n=mask.sum()
    print(f"{label} (n={n}): konkret {vc.get('konkret',0):.0%} · nur-Score {vc.get('score',0):.0%} · "
          f"Leerstelle {vc.get('leer',0):.0%}")

print("\n--- 2 komponierte Einträge (verbatim, kein LLM) ---")
for _,r in df[(df['ykeep'].values==1)&(df['etype']=='konkret')].head(2).iterrows():
    ob,bc = compose(r['id'])
    print(f"\n■ [{r['journal_short']}] {str(r['title'])[:78]}")
    print(f"  Verdikt(user): {r['user_verdict']}  ·  Abstract: {str(r['abstract'])[:90].strip()}…")
    print(f"  Signal: rich-Sim-Perzentil {(rich< rich[df.index[df['id']==r['id']][0]]).mean():.0%}")
    for t,y in ob[:2]: print(f"  ↔ teilt Referenz mit deiner Publikation: „{str(t)[:62]}\" ({y})")
    for au,ti in bc[:2]: print(f"  ↔ zitiert Umfeld-Autor {au}: „{str(ti)[:55]}\"")
