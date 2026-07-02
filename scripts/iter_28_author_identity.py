"""Iter 28 — Author-Identitäts-Achse: taugt sie, oder ist sie zu dünn/zirkulär?

Bisherige Achsen: Refs (own/bez-works), Inhalt (rich), Journal-Prior. Fehlt: Autor-Identität.
Kandidaten: f_coauthor_hits (Koautor von Benjamin), f_trigger_author_match (Trigger-Liste),
bezugsautoren-Autor-Match. Geprüft auf Diskrimination, blind-Coverage UND Zirkularität (P3).
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.metrics import roc_auc_score

df = E.load().reset_index(drop=True)
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr=(df["selection_mode"].fillna("")=="screening").values
yk = df["ykeep"].values; ign=(df['y3']=='ignorieren').values

# Zirkularitäts-Check: bezugsautoren-Herkunft
con = sqlite3.connect("bezugsautoren.db")
roles = dict(con.execute("SELECT role,count(*) FROM author_seed GROUP BY role").fetchall())
con.close()
print(f"bezugsautoren author_seed-Rollen: {roles}")
print("→ alle aus den Gold-Artikeln als first_author geseedet → Autor-Identitäts-Match ZIRKULÄR (P3, nicht nutzbar)\n")

print(f"{'Achse':<26}{'feuert':>8}{'keeper':>8}{'IGN':>7}{'Ratio':>7}{'blind-keeper':>14}")
for name, col in [("f_coauthor_hits","f_coauthor_hits"), ("f_trigger_author_match","f_trigger_author_match")]:
    v = (df[col].astype(float).fillna(0) > 0).values
    k,i = v[yk==1].mean(), v[ign].mean()
    print(f"  {name:<24}{v.sum():>8}{k:>8.0%}{i:>7.0%}{(k/i if i else float('inf')):>7.2f}{v[scr&(yk==1)].mean():>13.0%}")
    if v.sum() >= 5:
        print(f"     keep-AUC (gesamt {roc_auc_score(yk, df[col].astype(float).fillna(0)):.3f})")
