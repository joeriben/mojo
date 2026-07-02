"""Iter 43 — Grounded-Bezug-Coverage auf der keep-Menge (der eigentliche Produkt-Output).

Memory feedback_llm_bezuege: das 2.0-Motiv ist nicht Triage-Quote, sondern brauchbare Einträge ohne
konfabulierte Werk-Bezüge. Der substitutive Komponist kann nur dort einen ECHTEN Bezug schreiben, wo
ein geerdeter Anker existiert. Drei Anker-Typen:
  (1) own_coupling   — Artikel teilt ≥1 Referenz mit Benjamins Werk (f_own_coupling_union)
  (2) citation       — Artikel zitiert Benjamin direkt (f_citation_hit_count)
  (3) bezugsautoren  — Artikel-Refs ∩ Werke von Benjamins Bezugsautoren (bezugsautoren.db)
Frage: welcher Anteil der keeper / der LES bekommt einen geerdeten Bezug, welcher bleibt „Leerstelle"?
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3, json, re
import numpy as np, pandas as pd
import fm_eval as E

df = E.load().reset_index(drop=True)
yk = df["ykeep"].values; les = (df["y3"] == "lesenswert").values

# Artikel-Refs als W-id-Sets
con = sqlite3.connect("articles.db")
arts = pd.read_sql_query("SELECT id, openalex_refs, selection_mode FROM articles", con); con.close()
def wset(s):
    if not s: return set()
    try: items = json.loads(s)
    except Exception: items = re.findall(r"W\d+", str(s))
    return {re.sub(r".*/", "", str(x)) for x in items if "W" in str(x)}
arts["refset"] = arts["openalex_refs"].apply(wset)
df = df.merge(arts[["id", "refset", "selection_mode"]], on="id", how="left")
df["refset"] = df["refset"].apply(lambda x: x if isinstance(x, set) else set())

# Bezugsautoren-Werk-Universum
con = sqlite3.connect("bezugsautoren.db")
bez = set(r[0] for r in con.execute("SELECT DISTINCT work_oa_id FROM author_works WHERE work_oa_id IS NOT NULL"))
con.close()

own = (df["f_own_coupling_union"].fillna(0) >= 1).values
cit = (df["f_citation_hit_count"].fillna(0) >= 1).values
bezhit = df["refset"].apply(lambda s: len(s & bez) >= 1).values
any_anchor = own | cit | bezhit

def cov(mask, label):
    n = mask.sum()
    if n == 0: print(f"  {label:<34} n=0"); return
    print(f"  {label:<34} n={n:3d} | geerdet {any_anchor[mask].mean():.0%} "
          f"(own {own[mask].mean():.0%}, cit {cit[mask].mean():.0%}, bez {bezhit[mask].mean():.0%}) "
          f"| Leerstelle {1-any_anchor[mask].mean():.0%}")

print(f"Bezugsautoren-Werk-Universum: {len(bez)} W-ids | Artikel mit Refs: {(df['refset'].apply(len)>0).mean():.0%}")
print("\nGeerdete-Bezug-Coverage:")
cov(yk == 1, "alle keeper")
cov(les, "LES (lesenswert)")
scr = (df["selection_mode"] == "screening").values
cov((yk == 1) & scr, "keeper im BLINDEN Strom (screening)")
cov(les & scr, "LES im BLINDEN Strom")
cov((yk == 0), "non-keeper (Kontrast)")

# Leerstelle-Diagnose: wie viele Leerstellen haben überhaupt Refs?
leer = (yk == 1) & ~any_anchor
norefs = leer & (df["refset"].apply(len) == 0).values
print(f"\nLeerstellen unter keepern: {leer.sum()} — davon {norefs.sum()} ohne JEGLICHE OpenAlex-Refs "
      f"(echte Datenarmut), {leer.sum()-norefs.sum()} mit Refs aber ohne Anker-Treffer")
