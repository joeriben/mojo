"""Iter 44 — bezugsautoren-Coupling als Zusatz-Signal: Relevanz-Lift oder Redundanz/Zirkularität?

Iter 43: bez-direct (Artikel-Refs ∩ Bezugsautoren-Werke) ist der produktivste Anker (30 % der keeper),
aber teils zirkulär (DB aus Gold-Erstautoren geseedet). Frage am Triage-Ziel: hebt ein bez-Veto-Up
die keep-AUC / LES-Recall über M-C hinaus — und vor allem: auf dem BLINDEN Strom (unverzerrt) oder nur
auf dem intentional-positiven Pool (wo die Zirkularität wirkt)? Seed-gemittelt (P15).
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3, json, re
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
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
con = sqlite3.connect("bezugsautoren.db")
bez = set(r[0] for r in con.execute("SELECT DISTINCT work_oa_id FROM author_works WHERE work_oa_id IS NOT NULL")); con.close()

yk = df["ykeep"].values; les = (df["y3"] == "lesenswert").values
rich = df["rich_sim"].astype(float).values
biblio = ((df["f_own_coupling_union"].fillna(0) >= 1) | (df["f_citation_hit_count"].fillna(0) >= 1)).values
bezhit = df["refset"].apply(lambda s: len(s & bez) >= 1).values
scr = (df["selection_mode"] == "screening").values
z = lambda v: (v - np.nanmin(v)) / (np.nanmax(v) - np.nanmin(v) + 1e-9)
SEEDS = [11, 23, 42, 77, 101]

def mc_scores(extra_veto):
    out = []
    for s in SEEDS:
        pj = np.zeros(len(df)); G = np.zeros(len(df))
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=s).split(df, yk):
            g = yk[tr].mean(); rate = {}
            for j, sub in df.iloc[tr].groupby("journal_short"):
                n = len(sub); rate[j] = (sub["ykeep"].mean() * n + g * 5) / (n + 5)
            for i in te: pj[i] = rate.get(df.iloc[i]["journal_short"], g); G[i] = g
        mc = z(z(rich) + 0.5 * z(np.maximum(0, pj - G)))
        veto = biblio | extra_veto
        out.append(np.where(veto, 1.0 + mc, mc))
    return out

def report(label, scores_list, mask):
    aucs, recs = [], []
    for sc in scores_list:
        s, y, l = sc[mask], yk[mask], les[mask]
        if y.sum() in (0, len(y)): continue
        aucs.append(roc_auc_score(y, s))
        k = max(1, int(round(0.20 * len(s)))); top = np.argsort(-s)[:k]
        recs.append(l[top].sum() / max(1, l.sum()))
    print(f"  {label:<28} keep-AUC {np.mean(aucs):.3f}±{np.std(aucs):.3f} | "
          f"LES@20% {np.mean(recs):.0%}±{np.std(recs)*100:.0f}pp")

base = mc_scores(np.zeros(len(df), bool))
withbez = mc_scores(bezhit)
print(f"bez-Treffer: gesamt {bezhit.mean():.0%}, blinder Strom {bezhit[scr].mean():.0%}\n")
print("ALLE Quellen (Zirkularität wirkt):")
report("M-C", base, np.ones(len(df), bool)); report("M-C + bez-Veto", withbez, np.ones(len(df), bool))
print("\nBLINDER Strom (screening, unverzerrt):")
m = scr
report("M-C", base, m); report("M-C + bez-Veto", withbez, m)
