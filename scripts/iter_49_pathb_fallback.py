"""Iter 49 — Pfad-B-Fallback: was kann M-E ohne Abstract, bevor Volltext geholt wird?

Iter 34: alle blind-LES in Pfad A (abstract-reich); Pfad B (kein Abstract) hatte 0 LES. Hier: wie verteilt
sich keep/LES über die Pfade, und wie stark ist rich_sim ohne Abstract (Titel-only)? Frage: ist Pfad B
sicher zu deprioritisieren (→ erst Volltext holen), oder versteckt er Relevantes? Blinder Strom + gesamt.
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.metrics import roc_auc_score

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left")
yk = df["ykeep"].values; les = (df["y3"] == "lesenswert").values
scr = (df["selection_mode"] == "screening").values
pathA = (df["abstract"].fillna("").str.len() > 20).values   # abstract-reich
rich = df["rich_sim"].astype(float).values

def stats(mask, name):
    n = mask.sum()
    if n == 0: print(f"  {name:<34} n=0"); return
    sub_auc = (roc_auc_score(yk[mask], rich[mask])
               if 0 < yk[mask].sum() < n else float("nan"))
    print(f"  {name:<34} n={n:3d} | keep {yk[mask].sum():2d} ({yk[mask].mean():.0%}) | "
          f"LES {les[mask].sum():2d} | Ø rich {rich[mask].mean():.2f} | rich-AUC {sub_auc:.3f}")

print("Pfad-Aufteilung — GESAMT:")
stats(pathA, "Pfad A (Abstract)")
stats(~pathA, "Pfad B (kein Abstract)")
print(f"\nPfad-Aufteilung — BLINDER STROM (screening):")
stats(scr & pathA, "Pfad A blind")
stats(scr & ~pathA, "Pfad B blind")

# Was kostet es, Pfad B blind komplett zu deprioritisieren (erst Volltext)?
pb = scr & ~pathA
print(f"\nPfad B blind: {pb.sum()} Artikel, davon {les[pb].sum()} LES, {yk[pb].sum()} keeper")
print(f"  → deprioritisieren (erst Volltext holen) verliert {les[pb].sum()} blind-LES sofort, "
      f"{yk[pb].sum()} keeper bis Volltext da")
# rich auf Pfad B = Titel-only-Signal: trennt es überhaupt?
if 0 < yk[scr & ~pathA].sum() < (scr & ~pathA).sum():
    print(f"  rich (Titel-only) trennt Pfad B blind: keeper Ø {rich[pb & (yk==1)].mean():.2f} "
          f"vs non Ø {rich[pb & (yk==0)].mean():.2f}")
else:
    print(f"  rich-Trennung auf Pfad B blind nicht bestimmbar (keeper={yk[pb].sum()})")
