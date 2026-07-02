"""Iter 18 — zweite Erdungsschicht: bezugsautoren.db (Umfeld-Autoren).

Iter 17: konkreter Bezug über Benjamins EIGENE Refs deckt nur 21% keeper (62/161 Pubs aufgelöst),
blind 0%. Zweite Schicht (Memory project_bezugsautoren_db): teilt der Artikel Refs mit WERKEN von
Autoren aus Benjamins direktem Umfeld (208 Autoren, 6404 Werke), oder zitiert er sie direkt?
Frage: hebt das die keeper-Coverage — OHNE die Diskrimination (keeper vs IGN) zu zerstören? Bleibt blind 0%?
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3, json
import numpy as np, pandas as pd
import fm_eval as E
from collections import defaultdict

norm = lambda s: str(s).rsplit("/",1)[-1].strip() if s else ""

df = E.load().reset_index(drop=True)
con = sqlite3.connect("articles.db")
ids = ",".join(f"'{i}'" for i in df["id"].astype(str))
arows = con.execute(f"SELECT id, openalex_refs FROM articles WHERE id IN ({ids})").fetchall()
sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
art_refs = {}
for aid, oaref in arows:
    s=set()
    if oaref:
        try:
            for x in json.loads(oaref):
                v=norm(x.get("id") if isinstance(x,dict) else x);  s.add(v) if v else None
        except Exception: pass
    art_refs[aid]=s

# Schicht 1: eigene Refs (Iter 17)
con = sqlite3.connect("own_refs.db")
own_cloud=set()
for (oa,) in con.execute("SELECT ref_oa_id FROM pub_refs WHERE ref_oa_id IS NOT NULL"): own_cloud.add(norm(oa))
con.close()
# Schicht 2: bezugsautoren — Werk-IDs (direktes Zitat) + Ref-Wolke (Kopplung)
con = sqlite3.connect("bezugsautoren.db")
bez_work_ids=set(); bez_ref_cloud=set()
for wid, refs_json in con.execute("SELECT work_oa_id, referenced_works_json FROM author_works"):
    if wid: bez_work_ids.add(norm(wid))
    if refs_json:
        try:
            for r in json.loads(refs_json):
                v=norm(r); bez_ref_cloud.add(v) if v else None
        except Exception: pass
con.close()

def flags(aid):
    a=art_refs.get(aid,set())
    return (bool(a & own_cloud), bool(a & bez_work_ids), bool(a & bez_ref_cloud))
F=df["id"].map(flags)
df["own"]=F.map(lambda x:x[0]); df["bez_cite"]=F.map(lambda x:x[1]); df["bez_couple"]=F.map(lambda x:x[2])
df = df.merge(sm,on="id",how="left"); scr=(df["selection_mode"].fillna("")=="screening").values

print(f"Wolken: own={len(own_cloud)}  bez_works={len(bez_work_ids)}  bez_ref_cloud={len(bez_ref_cloud)}\n")
layers=[("nur own (Iter 17)", df["own"]),
        ("+ bez direkt-zitiert", df["own"]|df["bez_cite"]),
        ("+ bez gekoppelt (breit)", df["own"]|df["bez_cite"]|df["bez_couple"])]
groups=[("keeper",df['ykeep'].values==1),("LES",(df['y3']=='lesenswert').values),
        ("IGN",(df['y3']=='ignorieren').values),("blind keeper",scr&(df['ykeep'].values==1))]
print(f"{'Schicht':<26}" + "".join(f"{g:>14}" for g,_ in groups))
for name,flag in layers:
    print(f"  {name:<24}" + "".join(f"{flag[m].mean():>13.0%} " for _,m in groups))
# Diskrimination: keeper-Coverage / IGN-Coverage (>1 = diskriminiert)
print("\nDiskriminations-Ratio keeper/IGN (höher=besser, ~1=Rauschen):")
for name,flag in layers:
    k=flag[df['ykeep'].values==1].mean(); i=flag[(df['y3']=='ignorieren').values].mean()
    print(f"  {name:<24}{k/i if i else float('inf'):>6.2f}   (keeper {k:.0%} / IGN {i:.0%})")
