"""Iter 34 — Modell M-D: Zwei-Pfad-System (abstract-reich vs abstract-arm) + LES-Bilanz.

Iter 23/30: 43% des blinden Stroms abstract-arm, Ranker dort ≈Zufall, OpenAlex rettet 0.
M-D routet: abstract-reich → M-C-Ranker → LLM-Kaskade (Iter 33); abstract-arm → Bibliometrie-Präzisions-
Treffer + Eskalation (Volltext-Fetch). Hier: wie verteilen sich die LES auf die Pfade, und wie viele
fängt jeder Pfad mit welchem Mittel? Vollständige LES-Bilanz statt einer Headline.
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.model_selection import StratifiedKFold

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr=(df["selection_mode"].fillna("")=="screening").values
df["alen"]=df["abstract"].fillna("").str.len()
yk=df["ykeep"].values; les=(df["y3"]=="lesenswert").values
agent_keep=df["agent_verdict"].isin(E.KEEP).values
biblio=((df["f_own_coupling_union"]>=1)|(df["f_citation_hit_count"]>=1)).values
skf=StratifiedKFold(5,shuffle=True,random_state=42)
def eb(tr,te,k=5):
    g=yk[tr].mean();rate={}
    for j,sub in df.iloc[tr].groupby("journal_short"):
        n=len(sub);m=sub["ykeep"].mean();rate[j]=(m*n+g*k)/(n+k)
    return np.array([rate.get(df.iloc[i]["journal_short"],g) for i in te]),g
pj=np.zeros(len(df));G=np.zeros(len(df))
for tr,te in skf.split(df,yk): pj[te],g=eb(tr,te);G[te]=g
z=lambda v:(v-np.nanmin(v))/(np.nanmax(v)-np.nanmin(v)+1e-9)
mc=z(z(df["rich_sim"].astype(float).values)+0.5*z(np.maximum(0,pj-G)))

S=scr; rich_path = S & (df["alen"]>=200).values; poor_path = S & (df["alen"]<200).values
LES_tot=les[S].sum()
print(f"Blinder Strom n={S.sum()}, LES={LES_tot}")
print(f"  Pfad A (abstract-reich): n={rich_path.sum()}, LES={les[rich_path].sum()}")
print(f"  Pfad B (abstract-arm):   n={poor_path.sum()}, LES={les[poor_path].sum()}")

# Pfad A: M-C-Ranking, LLM-Kaskade Top-30% innerhalb Pfad A
idxA=np.where(rich_path)[0]; ordA=idxA[np.argsort(-mc[idxA])]
keptA=ordA[:int(round(0.30*len(idxA)))]
lesA_casc=(les[keptA] & agent_keep[keptA]).sum()
# Pfad B: Bibliometrie-Präzisions-Treffer (sofort), Rest Eskalation
lesB_biblio=(les[poor_path] & biblio[poor_path]).sum()
lesB_escal=les[poor_path].sum()-lesB_biblio
print(f"\nLES-Bilanz M-D:")
print(f"  Pfad A Kaskade (Top-30%→LLM):     {lesA_casc}/{les[rich_path].sum()} LES gefangen")
print(f"  Pfad B Bibliometrie (sofort):     {lesB_biblio}/{les[poor_path].sum()} LES")
print(f"  Pfad B → Eskalation nötig:        {lesB_escal} LES (nur via Volltext erreichbar)")
caught=lesA_casc+lesB_biblio
print(f"  ─────────────────────────────")
print(f"  ohne Eskalation gefangen:         {caught}/{LES_tot} = {caught/LES_tot:.0%}")
print(f"  mit Pfad-B-Eskalation max:        {(lesA_casc+les[poor_path].sum())}/{LES_tot} = {(lesA_casc+les[poor_path].sum())/LES_tot:.0%}")
print(f"\n  LLM-Calls: Pfad A {len(keptA)} (Kaskade) + Pfad B Eskalation {poor_path.sum()-((poor_path)&biblio).sum()} (Volltext)")
