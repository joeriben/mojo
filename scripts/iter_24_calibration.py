"""Iter 24 — Kalibrierungs-Ehrlichkeit des Keep-Rankers.

Der Komponist (Iter 19) gibt Score-Hinweise. Wenn er „rankt im oberen X %" / implizit „P(keep)≈p" sagt,
muss p stimmen. Isotonic-kalibrierte P(keep) aus rich_sim (OOF), Reliability auf dem screening-Strom,
getrennt abstract-voll/arm (Iter 23). ECE = mittlere |vorhergesagt − tatsächlich|. Ein lügender Score
ist schlimmer als keiner.
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.model_selection import StratifiedKFold
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr=(df["selection_mode"].fillna("")=="screening").values
df["alen"]=df["abstract"].fillna("").str.len()
yk = df["ykeep"].values
s = df["rich_sim"].astype(float).fillna(0).values

# OOF isotonic-Kalibrierung von rich_sim → P(keep)
skf = StratifiedKFold(5, shuffle=True, random_state=42); p = np.zeros(len(df))
for tr,te in skf.split(s.reshape(-1,1), yk):
    iso = IsotonicRegression(out_of_bounds="clip"); iso.fit(s[tr], yk[tr]); p[te]=iso.predict(s[te])

def reliability(mask, label, bins=5):
    pp, yy = p[mask], yk[mask]
    if mask.sum()<20: print(f"\n{label}: zu klein (n={mask.sum()})"); return
    edges = np.quantile(pp, np.linspace(0,1,bins+1)); edges[-1]+=1e-9
    print(f"\n{label} (n={mask.sum()}, keep-Basisrate {yy.mean():.0%}, Brier {brier_score_loss(yy,pp):.3f}):")
    print(f"  {'Bin (P̄ vorhergesagt)':<24}{'tatsächl. keep':>15}{'n':>5}")
    ece=0
    for b in range(bins):
        m=(pp>=edges[b])&(pp<edges[b+1])
        if m.sum():
            pred,act=pp[m].mean(),yy[m].mean(); ece+=m.sum()/mask.sum()*abs(pred-act)
            print(f"  {pred:>10.0%}{'':<14}{act:>14.0%}{m.sum():>5}")
    print(f"  → ECE (mittl. Kalibrierungsfehler): {ece:.3f}")

reliability(np.ones(len(df),bool), "GESAMT")
reliability(scr, "SCREENING (blind)")
reliability(scr&(df['alen']>=200), "SCREENING abstract-voll")
