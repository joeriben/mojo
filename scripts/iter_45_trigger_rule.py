"""Iter 45 — Trigger-Autoren-Regel als Relevanz-Signal: Precision/Recall standalone.

Memory project_trigger_autoren: MacGilchrist/Jarke/Chun → Eskalation unabhängig vom Tier (dokumentierte
harte Regel). Anders als bezugsautoren (Iter 44, kein Relevanz-Hebel) — verdient diese Regel ihren Platz?
Zwei Operationalisierungen:
  (A) direkter Autoren-Match  (f_trigger_author_match) — Artikel VON einem Trigger-Autor
  (B) Trigger-Ref-Overlap     (f_ref_overlap_trigger)  — Artikel ZITIERT ein Trigger-Autor-Werk
Precision/Recall gegen keep und LES, voll + blinder Strom. Keine Seeds nötig (deterministische Regel).
"""
import sys; sys.path.insert(0, "scripts")
import json
import numpy as np, pandas as pd
import fm_eval as E

df = E.load().reset_index(drop=True)
import sqlite3
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left")
yk = df["ykeep"].values; les = (df["y3"] == "lesenswert").values
scr = (df["selection_mode"] == "screening").values
try:
    pats = json.load(open("profile.json")).get("trigger_author_patterns", [])
except Exception: pats = []
print(f"Trigger-Autoren-Patterns (profile.json): {pats}\n")

A = (df["f_trigger_author_match"].fillna(0) >= 1).values   # Artikel VON Trigger-Autor
B = (df["f_ref_overlap_trigger"].fillna(0) >= 1).values     # Artikel ZITIERT Trigger-Autor

def pr(rule, target, mask, name):
    r, t = rule[mask], target[mask]
    fired = r.sum()
    if fired == 0: print(f"  {name:<46} feuert 0×"); return
    prec = (r & t).sum() / fired
    rec = (r & t).sum() / max(1, t.sum())
    print(f"  {name:<46} feuert {fired:3d}× | Precision {prec:.0%} | Recall {rec:.0%} "
          f"(fängt {(r&t).sum()}/{t.sum()})")

print("(A) direkter Trigger-Autoren-Match:")
pr(A, yk, np.ones(len(df), bool), "→ keep (alle Quellen)")
pr(A, les, np.ones(len(df), bool), "→ LES (alle Quellen)")
pr(A, yk, scr, "→ keep (blinder Strom)")
print("\n(B) Trigger-Ref-Overlap (zitiert Trigger-Autor-Werk):")
pr(B, yk, np.ones(len(df), bool), "→ keep (alle Quellen)")
pr(B, les, np.ones(len(df), bool), "→ LES (alle Quellen)")
pr(B, yk, scr, "→ keep (blinder Strom)")
pr(B, les, scr, "→ LES (blinder Strom)")

base = yk.mean(); base_scr = yk[scr].mean()
print(f"\nBasisrate keep: gesamt {base:.0%}, blinder Strom {base_scr:.0%}")
print(f"Lift von (B) auf blindem Strom: Precision {yk[scr&B].mean():.0%} vs Basis {base_scr:.0%} "
      f"= {yk[scr&B].mean()/base_scr:.1f}×" if (scr&B).sum() else "  (B feuert 0× blind)")
