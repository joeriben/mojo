"""Iter 21 — drei Enrichment-Achsen kombiniert + named_thinker-Precision härten.

Iter 17/18/20: own-Ref (blind 4%), bez-direkt (blind 4%), named_thinker (blind 28%, aber Precision-Risiko).
Hier: (1) kombinierte blind-keeper-Coverage der drei Achsen; (2) named_thinker härten (Vollname ODER
distinktiver Nachname, Stoppliste für Namen-die-Wörter-sind) und Precision-Verlust quantifizieren.
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3, json, re
import numpy as np, pandas as pd
import fm_eval as E
from collections import defaultdict

norm = lambda s: str(s).rsplit("/",1)[-1].strip() if s else ""
df = E.load().reset_index(drop=True)
con = sqlite3.connect("articles.db")
ids = ",".join(f"'{i}'" for i in df["id"].astype(str))
arefs = {aid:set() for aid in df["id"]}
for aid, oaref in con.execute(f"SELECT id, openalex_refs FROM articles WHERE id IN ({ids})"):
    if oaref:
        try: arefs[aid]={norm(x.get('id') if isinstance(x,dict) else x) for x in json.loads(oaref)}
        except Exception: pass
sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()

con = sqlite3.connect("own_refs.db")
own_cloud={norm(o) for (o,) in con.execute("SELECT ref_oa_id FROM pub_refs WHERE ref_oa_id IS NOT NULL")}
con.close()
con = sqlite3.connect("bezugsautoren.db")
bez_work_ids={norm(w) for (w,) in con.execute("SELECT work_oa_id FROM author_works WHERE work_oa_id IS NOT NULL")}
con.close()

# named_thinkers: roh vs gehärtet
S = json.load(open("summaries.json"))["summaries"]
full_names, last_names = set(), {}
for e in S.values():
    for nm in (e.get("named_thinkers") or []):
        clean = re.sub(r"[^A-Za-zÀ-ÿ\- ]", "", str(nm)).strip()
        toks = clean.split()
        if len(toks) >= 2: full_names.add(clean.lower())
        if toks and len(toks[-1]) >= 4: last_names[toks[-1].lower()] = nm
# Stoppliste: Nachnamen, die auch Allerweltswörter/Vornamen sind
STOP = {"donna","hope","young","west","english","german","black","white","martin","may","bell","french"}
hard_last = {w:n for w,n in last_names.items() if len(w) >= 6 and w not in STOP}

text = (df["title"].fillna("")+" "+df["abstract"].fillna("")+" "+df["concepts"].fillna("").str.replace("|"," ")).str.lower()
def thinker_raw(t):  return [n for w,n in last_names.items() if re.search(r"\b"+re.escape(w)+r"\b", t)]
def thinker_hard(t):
    h = [n for w,n in hard_last.items() if re.search(r"\b"+re.escape(w)+r"\b", t)]
    h += [n for n in full_names if n in t]
    return list(set(h))
df["t_raw"]=text.map(lambda t:len(thinker_raw(t))>0)
df["t_hard"]=text.map(lambda t:len(thinker_hard(t))>0)
df["own"]=df["id"].map(lambda i:bool(arefs[i]&own_cloud))
df["bez"]=df["id"].map(lambda i:bool(arefs[i]&bez_work_ids))
df=df.merge(sm,on="id",how="left"); scr=(df["selection_mode"].fillna("")=="screening").values
yk=df["ykeep"].values; ign=(df['y3']=='ignorieren').values

print(f"named_thinkers: roh {len(last_names)} Nachnamen → gehärtet {len(hard_last)} + {len(full_names)} Vollnamen")
def ratio(flag):
    k,i = flag[yk==1].mean(), flag[ign].mean(); return k,i,(k/i if i else float('inf'))
print(f"\n{'Achse':<30}{'keeper':>8}{'IGN':>7}{'Ratio':>7}{'blind-keeper':>14}")
axes=[("own-Ref",df["own"]),("bez-direkt",df["bez"]),("named_thinker roh",df["t_raw"]),
      ("named_thinker gehärtet",df["t_hard"]),
      ("KOMBI own∪bez∪thinker-hart", df["own"]|df["bez"]|df["t_hard"])]
for name,flag in axes:
    k,i,r=ratio(flag); print(f"  {name:<28}{k:>7.0%}{i:>7.0%}{r:>7.2f}{flag[scr&(yk==1)].mean():>13.0%}")
