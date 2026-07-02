"""Iter 26 — vollständiger blinder Ranker (Ensemble) + Serendipitäts-Lackmustest.

Iter 25: mean(journal-prior, rich)=0.702 blind. Hier: (1) Ensemble + biblio-veto als Recall@Last vs M7;
(2) KRITISCH — verschluckt die Journal-Komponente die „Serendipitäts"-keeper (keeper in Journals, die
sonst kaum keeper haben)? Das ist der Robustheits-Test fürs Scout-Versprechen: ranks die Journal-Erdung
genau die unerwarteten Funde nach unten?
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr=(df["selection_mode"].fillna("")=="screening").values
yk = df["ykeep"].values
skf = StratifiedKFold(5, shuffle=True, random_state=42)
def eb(tr,te,k=5):
    g=yk[tr].mean(); rate={}
    for j,sub in df.iloc[tr].groupby("journal_short"):
        n=len(sub);m=sub["ykeep"].mean();rate[j]=(m*n+g*k)/(n+k)
    return np.array([rate.get(df.iloc[i]["journal_short"],g) for i in te])
pj=np.zeros(len(df))
for tr,te in skf.split(df,yk): pj[te]=eb(tr,te)
z=lambda v:(v-np.nanmin(v))/(np.nanmax(v)-np.nanmin(v)+1e-9)
rich=z(df["rich_sim"].astype(float).values); pjz=z(pj)
biblio=((df["f_own_coupling_union"]>=1)|(df["f_citation_hit_count"]>=1)).values
ens=(rich+pjz)/2
ens_veto=np.where(biblio,1.0+ens,ens)
m7=df["score_M7_EmbeddingSimilarity"].astype(float).fillna(0).values

def recall_at(s,y,f):
    o=np.argsort(-s); return y[o[:int(f*len(s))]].sum()/y.sum()
print(f"SCREENING Recall@Sichtungslast (n={scr.sum()}, keep={yk[scr].sum()}):")
print(f"  {'Ranker':<24}{'AUC':>7}{'R@10%':>8}{'R@20%':>8}{'R@30%':>8}{'R@50%':>8}")
for name,s in [("M7 (aktuell)",m7),("rich (Iter16)",rich),("ens(journal,rich)",ens),("ens+biblio-veto",ens_veto)]:
    ss=s[scr];yy=yk[scr]
    print(f"  {name:<24}{roc_auc_score(yy,ss):>7.3f}"+"".join(f"{recall_at(ss,yy,f):>8.0%}" for f in [.1,.2,.3,.5]))

# Serendipitäts-Test: screening-keeper in Journals mit wenig ANDEREN keepern (leave-one-out)
sidx=np.where(scr)[0]
jk=df[scr].groupby("journal_short")["ykeep"].sum()
print(f"\nSerendipitäts-keeper (screening-keeper, deren Journal ≤1 keeper insgesamt hat):")
sk=[i for i in sidx if yk[i]==1 and jk.get(df.iloc[i]['journal_short'],0)<=1]
print(f"  Anzahl: {len(sk)}")
for i in sk:
    r_rich=(rich[scr]<rich[i]).mean(); r_ens=(ens[scr]<ens[i]).mean()
    print(f"  [{df.iloc[i]['journal_short']}] {str(df.iloc[i]['title'])[:52]:<52} "
          f"rich-Rang {r_rich:>4.0%} → ens-Rang {r_ens:>4.0%}  {'↓verschluckt' if r_ens<r_rich-0.1 else 'ok'}")
