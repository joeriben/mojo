"""Iter 48 — Kalibrierung: ist der M-E-Score eine Wahrscheinlichkeit oder nur ein Rang?

Die Confidence-Bänder (Iter 46) ruhten auf Perzentilen. Dürfen sie auf kalibrierten p-Schwellen ruhen?
Test: ECE (Expected Calibration Error) + Reliabilitätskurve, (a) roh (M-C als p genommen), (b) isotonisch
out-of-fold kalibriert (M-C → keep-Wahrscheinlichkeit). Seed-gemittelt (P15). Out-of-fold, kein Leak (P3/P5).
"""
import sys; sys.path.insert(0, "scripts")
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.model_selection import StratifiedKFold
from sklearn.isotonic import IsotonicRegression

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
yk = df["ykeep"].values.astype(float)
rich = df["rich_sim"].astype(float).values
biblio = ((df["f_own_coupling_union"].fillna(0) >= 1) | (df["f_citation_hit_count"].fillna(0) >= 1)).values
z = lambda v: (v - np.nanmin(v)) / (np.nanmax(v) - np.nanmin(v) + 1e-9)
SEEDS = [11, 23, 42, 77, 101]

def ece(p, y, bins=10):
    edges = np.linspace(0, 1, bins + 1); e = 0.0
    for b in range(bins):
        m = (p >= edges[b]) & (p < edges[b + 1] if b < bins - 1 else p <= edges[b + 1])
        if m.sum() == 0: continue
        e += m.mean() * abs(y[m].mean() - p[m].mean())
    return e

raw_eces, cal_eces = [], []
cal_all = np.zeros(len(df))
for s in SEEDS:
    pj = np.zeros(len(df)); G = np.zeros(len(df)); cal = np.zeros(len(df))
    skf = StratifiedKFold(5, shuffle=True, random_state=s)
    # erst Prior OOF
    for tr, te in skf.split(df, yk):
        g = yk[tr].mean(); rate = {}
        for j, sub in df.iloc[tr].groupby("journal_short"):
            n = len(sub); rate[j] = (sub["ykeep"].mean() * n + g * 5) / (n + 5)
        for i in te: pj[i] = rate.get(df.iloc[i]["journal_short"], g); G[i] = g
    mc = z(z(rich) + 0.5 * z(np.maximum(0, pj - G)))
    mc = np.where(biblio, np.minimum(1.0, 0.5 + mc / 2), mc)  # roh als p in [0,1]
    # isotonische Kalibrierung OOF (auf mc → yk)
    for tr, te in skf.split(df, yk):
        ir = IsotonicRegression(out_of_bounds="clip"); ir.fit(mc[tr], yk[tr])
        cal[te] = ir.predict(mc[te])
    raw_eces.append(ece(mc, yk)); cal_eces.append(ece(cal, yk)); cal_all += cal / len(SEEDS)

print(f"ECE (alle Quellen, {len(SEEDS)} Seeds, 10 Bins, OOF):")
print(f"  roh (M-C als p)        ECE = {np.mean(raw_eces):.3f} ± {np.std(raw_eces):.3f}")
print(f"  isotonisch kalibriert  ECE = {np.mean(cal_eces):.3f} ± {np.std(cal_eces):.3f}")
print(f"\nReliabilitätskurve (kalibriert, gemittelt): vorhergesagt → beobachtet")
edges = np.linspace(0, 1, 6)
for b in range(5):
    m = (cal_all >= edges[b]) & (cal_all <= edges[b + 1])
    if m.sum(): print(f"  p∈[{edges[b]:.1f},{edges[b+1]:.1f}]  n={m.sum():3d}  "
                       f"Ø-p={cal_all[m].mean():.2f}  beobachtet keep={yk[m].mean():.2f}")
print(f"\nBasisrate keep gesamt: {yk.mean():.2f}")
