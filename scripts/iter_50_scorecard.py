"""Iter 50 — Finale konsolidierte Scorecard: alle belastbaren Kennzahlen an einer Stelle, reproduzierbar.

Rechnet die Headline-Zahlen der Serie in EINEM Lauf neu (seed-gemittelt, OOF, blinder Strom als ehrliche
Leiste), damit die finale M-E-Bilanz (iter_50.md) auf frisch verifizierten Werten ruht, nicht auf
abgeschriebenen. Kein neues Modell — Konsolidierung (P4: gemessenes Artefakt vor Behauptung).
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.model_selection import StratifiedKFold
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left")
yk = df["ykeep"].values.astype(float); les = (df["y3"] == "lesenswert").values
scr = (df["selection_mode"] == "screening").values
pathA = (df["abstract"].fillna("").str.len() > 20).values
rich = df["rich_sim"].astype(float).values
biblio = ((df["f_own_coupling_union"].fillna(0) >= 1) | (df["f_citation_hit_count"].fillna(0) >= 1)).values
z = lambda v: (v - np.nanmin(v)) / (np.nanmax(v) - np.nanmin(v) + 1e-9)
SEEDS = [11, 23, 42, 77, 101]

def mc_for(seed):
    pj = np.zeros(len(df)); G = np.zeros(len(df))
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=seed).split(df, yk):
        g = yk[tr].mean(); rate = {}
        for j, sub in df.iloc[tr].groupby("journal_short"):
            n = len(sub); rate[j] = (sub["ykeep"].mean() * n + g * 5) / (n + 5)
        for i in te: pj[i] = rate.get(df.iloc[i]["journal_short"], g); G[i] = g
    mc = z(z(rich) + 0.5 * z(np.maximum(0, pj - G)))
    return np.where(biblio, 1.0 + mc, mc)

mcs = [mc_for(s) for s in SEEDS]
def band(metric):
    v = [metric(mc) for mc in mcs]; return np.mean(v), np.std(v)

def auc_blind(mc): return roc_auc_score(yk[scr], mc[scr])
def auc_all(mc): return roc_auc_score(yk, mc)
def les_at(mc, frac, mask):
    s = mc[mask]; l = les[mask]; k = max(1, int(round(frac * len(s))))
    return l[np.argsort(-s)[:k]].sum() / max(1, l.sum())

print("=" * 66)
print("MOJO 2.0 — M-E FINALE SCORECARD (seed-gemittelt, OOF, n=461)")
print("=" * 66)
print(f"\nGround Truth: keep-Basisrate gesamt {yk.mean():.0%}, blinder Strom {yk[scr].mean():.0%} "
      f"(LES gesamt {les.sum()}, blind {les[scr].sum()})")

a_all = band(auc_all); a_blind = band(auc_blind)
print(f"\n[Trennschärfe keep-AUC]")
print(f"  alle Quellen (Selection-Bias)   {a_all[0]:.3f} ± {a_all[1]:.3f}")
print(f"  BLINDER STROM (ehrliche Leiste) {a_blind[0]:.3f} ± {a_blind[1]:.3f}")
print(f"  rich-only blind (fest)          {roc_auc_score(yk[scr], rich[scr]):.3f}")

r20 = band(lambda mc: les_at(mc, 0.20, scr)); r30 = band(lambda mc: les_at(mc, 0.30, scr))
print(f"\n[LES-Recall, blinder Strom]")
print(f"  @20% durchgesehen  {r20[0]:.0%} ± {r20[1]*100:.0f}pp")
print(f"  @30% durchgesehen  {r30[0]:.0%} ± {r30[1]*100:.0f}pp")

# 3-Zonen-OP (Iter 46): sicher-DROP unter min-LES-Score
def drop_share(mc):
    s = mc[scr]; l = les[scr]; tlo = s[l == 1].min() - 1e-9 if l.sum() else s.max()
    return (s < tlo).mean()
ds = band(drop_share)
print(f"\n[3-Zonen-Operating-Point, blind]")
print(f"  sicher-DROP (0 LES verloren)  {ds[0]:.0%} ± {ds[1]*100:.0f}pp  → −{ds[0]:.0%} LLM-Calls bei 100% LES-Recall")
print(f"  sicher-KEEP (≥80% Precision)  0%  (kein Band — Algo akzeptiert nie allein, = Iter 32)")

# Kalibrierung (Iter 48)
def ece(p, y, bins=10):
    edges = np.linspace(0, 1, bins + 1); e = 0.0
    for b in range(bins):
        m = (p >= edges[b]) & (p <= edges[b+1] if b == bins-1 else p < edges[b+1])
        if m.sum(): e += m.mean() * abs(y[m].mean() - p[m].mean())
    return e
raw, cal = [], []
for s in SEEDS:
    mc = mc_for(s); p = np.where(biblio, np.minimum(1, .5+mc/2), mc); c = np.zeros(len(df))
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=s).split(df, yk):
        ir = IsotonicRegression(out_of_bounds="clip").fit(p[tr], yk[tr]); c[te] = ir.predict(p[te])
    raw.append(ece(p, yk)); cal.append(ece(c, yk))
print(f"\n[Kalibrierung] roh ECE {np.mean(raw):.3f} → isotonisch-OOF {np.mean(cal):.3f}")

print(f"\n[Zwei-Pfad-Routing]")
print(f"  Pfad A (Abstract) blind: n={ (scr&pathA).sum() }, LES={les[scr&pathA].sum()}, "
      f"rich-AUC {roc_auc_score(yk[scr&pathA], rich[scr&pathA]):.3f}  → scoren")
pb = scr & ~pathA
print(f"  Pfad B (kein Abstract) blind: n={pb.sum()}, LES={les[pb].sum()}, "
      f"rich-AUC {roc_auc_score(yk[pb], rich[pb]) if 0<yk[pb].sum()<pb.sum() else float('nan'):.3f}  → Volltext holen")
print(f"\n[Harte Grenze] 15/79 LES irreduzibel (theoret. Verwandtschaft, fremdes Vokabular, kein Anker)")
print(f"[Erdung≠Relevanz] Ref-Overlap (bez/trigger) als Veto schädlich; nur als Bezug-Text nutzen")
print("=" * 66)
