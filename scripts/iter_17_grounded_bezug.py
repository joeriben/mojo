"""Iter 17 — geerdeter Bezugs-Extraktor: welche KONKRETE Eigenpublikation teilt der Artikel?

Das eigentliche 2.0-Motiv (feedback_llm_bezuege_konfabulation): nicht „wie relevant" (Score), sondern
„welcher konkrete Werk-Bezug". Audit-Befund: LLM-Behauptungen nur 12.7% corroborated, 55.9% ungrounded.
Hier: pro Artikel die geteilten Referenzen mit BENANNTEN Eigenpublikationen (own_refs.pub_refs), als
substitutive Komponente. Diagnose: für wie viele keeper lässt sich ≥1 konkreter Bezug benennen?
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3, json
import numpy as np, pandas as pd
import fm_eval as E
from collections import defaultdict

def norm_oa(s):
    if not s: return ""
    return str(s).rsplit("/", 1)[-1].strip()

df = E.load().reset_index(drop=True)
# Artikel-OpenAlex-Refs aus articles.db
con = sqlite3.connect("articles.db")
ids = ",".join(f"'{i}'" for i in df["id"].astype(str))
arows = con.execute(f"SELECT id, openalex_refs FROM articles WHERE id IN ({ids})").fetchall()
con.close()
art_refs = {}
for aid, oaref in arows:
    s = set()
    if oaref:
        try:
            for x in json.loads(oaref):
                v = norm_oa(x.get("id") if isinstance(x, dict) else x)
                if v: s.add(v)
        except Exception: pass
    art_refs[aid] = s

# Eigenpublikationen: canonical_id → (titel, jahr) + ref_oa_id-Set
con = sqlite3.connect("own_refs.db")
pubs = {r[0]: (r[1], r[2]) for r in con.execute("SELECT canonical_id, title, year FROM publications")}
pub_ref_oa = defaultdict(set)
for cid, oa in con.execute("SELECT canonical_id, ref_oa_id FROM pub_refs WHERE ref_oa_id IS NOT NULL"):
    pub_ref_oa[cid].add(norm_oa(oa))
con.close()

def bezuege(aid):
    """Liste (pub_titel, jahr, n_geteilte_refs) für Publikationen mit ≥1 geteilter Ref."""
    a = art_refs.get(aid, set())
    if not a: return []
    out = []
    for cid, refs in pub_ref_oa.items():
        shared = a & refs
        if shared:
            t, y = pubs.get(cid, ("?", "?"))
            out.append((t, y, len(shared)))
    return sorted(out, key=lambda x: -x[2])

df["n_bezug_pubs"] = df["id"].map(lambda i: len(bezuege(i)))
df["has_bezug"] = df["n_bezug_pubs"] > 0

con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr = (df["selection_mode"].fillna("")=="screening").values

print(f"Artikel mit OpenAlex-Refs: {sum(1 for s in art_refs.values() if s)}/{len(df)}")
print(f"Eigenpublikationen mit aufgelösten Refs: {len(pub_ref_oa)}/{len(pubs)}\n")
print(f"{'Gruppe':<28}{'n':>5}{'≥1 konkreter Bezug':>22}")
for name, mask in [("alle", np.ones(len(df),bool)), ("keeper (scan+les)", df['ykeep'].values==1),
                   ("LES (lesenswert)", (df['y3']=='lesenswert').values),
                   ("blind keeper (screening)", scr & (df['ykeep'].values==1)),
                   ("IGN (ignorieren)", (df['y3']=='ignorieren').values)]:
    n = mask.sum(); cov = df.loc[mask, "has_bezug"].mean() if n else 0
    print(f"  {name:<26}{n:>5}{cov:>21.0%}")

# 3 konkrete Beispiele (keeper mit Bezug)
print("\n--- konkrete Bezüge (Beispiele, keeper) ---")
ex = df[(df['ykeep'].values==1) & df['has_bezug']].head(3)
for _, r in ex.iterrows():
    print(f"\n[{r['journal_short']}] {str(r['title'])[:80]}  (user={r['user_verdict']})")
    for t, y, n in bezuege(r['id'])[:3]:
        print(f"   ↔ {n} geteilte Ref(s) mit: „{str(t)[:70]}" + (f"\" ({y})" if y else "\""))
