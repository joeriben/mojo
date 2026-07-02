"""Iter 20 — named_thinkers als geerdete KONZEPTUELLE Achse (jenseits geteilter Refs).

Iter 11: die blind-verfehlten LES sind konzeptuell verwandt (Haraway/„Queer Kin", Adorno/„Auschwitz"),
teilen aber keine Referenzen → Iter 17/18 (Refs) erreichen sie nicht (blind 4%). Neue Achse: die
summaries.json listen Benjamins `named_thinkers` (Barad, Haraway, Rancière, Ernst…). Nennt der
Artikel-Text (Titel+Abstract+Konzepte) dieselben Denker? Geerdete, NICHT-bibliometrische Verwandtschaft.
Test: diskriminiert das, und fängt es speziell die konzeptuell-verwandten blind-keeper?
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3, json, re
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.metrics import roc_auc_score

df = E.load().reset_index(drop=True)
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr = (df["selection_mode"].fillna("")=="screening").values

S = json.load(open("summaries.json"))["summaries"]
# Benjamins Denker-Set: Nachnamen (>=4 Zeichen, um Initialen/Allerweltsnamen zu meiden)
thinkers = {}
for e in S.values():
    for nm in (e.get("named_thinkers") or []):
        last = re.sub(r"[^A-Za-zÀ-ÿ\- ]", "", str(nm)).strip().split()[-1:]
        if last and len(last[0]) >= 4:
            thinkers.setdefault(last[0].lower(), nm)
thinker_last = sorted(thinkers)
print(f"Benjamins named_thinkers (eindeutige Nachnamen): {len(thinker_last)}")
print("  z.B.:", ", ".join(list(thinkers.values())[:12]))

text = (df["title"].fillna("")+" "+df["abstract"].fillna("")+" "+
        df["concepts"].fillna("").str.replace("|"," ")+" "+df["authors_lower"].fillna("")).str.lower()
def count_thinkers(t):
    hits = [thinkers[w] for w in thinker_last if re.search(r"\b"+re.escape(w)+r"\b", t)]
    return hits
df["thinker_hits"] = text.map(lambda t: count_thinkers(t))
df["n_thinker"] = df["thinker_hits"].map(len)
df["has_thinker"] = df["n_thinker"] > 0
yk = df["ykeep"].values

print(f"\n{'Gruppe':<22}{'≥1 Denker':>11}{'Ø Denker':>10}")
for name,mask in [("keeper",yk==1),("LES",(df['y3']=='lesenswert').values),
                  ("IGN",(df['y3']=='ignorieren').values),("blind keeper",scr&(yk==1))]:
    print(f"  {name:<20}{df.loc[mask,'has_thinker'].mean():>10.0%}{df.loc[mask,'n_thinker'].mean():>10.2f}")
k=df.loc[yk==1,'has_thinker'].mean(); i=df.loc[(df['y3']=='ignorieren').values,'has_thinker'].mean()
print(f"  Diskriminations-Ratio keeper/IGN: {k/i:.2f}")
print(f"  keep-AUC (n_thinker als Score): {roc_auc_score(yk, df['n_thinker']):.3f}  "
      f"| blind: {roc_auc_score(yk[scr], df['n_thinker'].values[scr]):.3f}")

# Speziell: die 4 blind-verfehlten LES aus Iter 11
print("\n4 blind-verfehlte LES (Iter 11) — welche Denker werden genannt?")
for t in ["Die AfD","Rating villagers","Making Queer Kin","Mikrokosmoksia"]:
    h = df[df["title"].fillna("").str.contains(t, regex=False)]
    if len(h):
        hits=h.iloc[0]["thinker_hits"]
        print(f"  {t:<18} {('→ '+', '.join(hits)) if hits else '— keine'}")
