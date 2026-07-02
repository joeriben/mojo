"""Iter 30 — Abstract-Anreicherung: rettet OpenAlex-Backfill den Ranker auf abstract-losen Artikeln?

Iter 23: 43% des blinden Stroms abstract-los, Ranker dort ≈Zufall (0.532). articles.db hat
`openalex_abstract` (teils gefüllt). Frage: wie viele abstract-lose Artikel bekommen via OpenAlex einen,
und erholt sich die rich-AUC auf der erholten Teilmenge Richtung 0.648? Wie groß ist die irreduzible Lücke?
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3, json
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.metrics import roc_auc_score
from sentence_transformers import SentenceTransformer

df = E.load().reset_index(drop=True)
con = sqlite3.connect("articles.db")
extra = pd.read_sql_query("SELECT id, selection_mode, openalex_abstract FROM articles", con); con.close()
df = df.merge(extra, on="id", how="left"); scr=(df["selection_mode"].fillna("")=="screening").values
df["alen"]=df["abstract"].fillna("").str.len()
df["oalen"]=df["openalex_abstract"].fillna("").str.len()
yk=df["ykeep"].values
poor = df["alen"]<50

print(f"abstract-arm (<50): {poor.sum()} ({poor.mean():.0%}), davon blind {(poor&scr).sum()}")
rescued = poor & (df["oalen"]>=50)
print(f"  davon mit OpenAlex-Abstract rettbar: {rescued.sum()} ({rescued.sum()/max(poor.sum(),1):.0%})")
print(f"  irreduzibel abstract-los (auch ohne OA): {(poor&(df['oalen']<50)).sum()}")
print(f"  blind abstract-arm gerettet: {(poor&scr&(df['oalen']>=50)).sum()}/{(poor&scr).sum()}")

# angereicherter Abstract: OA wo Haupt-Abstract fehlt
df["abs_enriched"]=np.where(df["alen"]>=50, df["abstract"].fillna(""), df["openalex_abstract"].fillna(""))
S=json.load(open("summaries.json"))["summaries"]
rich=lambda e:" ".join(p for p in [e.get("title",""),e.get("summary_de","")] if p)
pub_text=[rich(e) for e in S.values()]
def artvec(absc):
    return (df["title"].fillna("")+". "+absc+". "+df["concepts"].fillna("").str.replace("|"," ")).tolist()
m=SentenceTransformer("all-MiniLM-L6-v2"); nrm=lambda M:M/(np.linalg.norm(M,axis=1,keepdims=True)+1e-9)
P=nrm(np.asarray(m.encode(pub_text,show_progress_bar=False))); cent=nrm(P.mean(axis=0,keepdims=True))
def sim(absc):
    A=nrm(np.asarray(m.encode(artvec(absc),show_progress_bar=False))); return (A@cent.T).ravel()
s_orig=sim(df["abstract"].fillna("")); s_enr=sim(df["abs_enriched"])

def auc(s,mask):
    return roc_auc_score(yk[mask],s[mask]) if (yk[mask].sum()>0 and yk[mask].sum()<mask.sum()) else float("nan")
print(f"\nrich-AUC auf zuvor abstract-armen Artikeln (n={poor.sum()}):")
print(f"  ohne Anreicherung: {auc(s_orig,poor.values):.3f}")
print(f"  mit OA-Anreicherung: {auc(s_enr,poor.values):.3f}")
print(f"rich-AUC blind gesamt:  ohne {auc(s_orig,scr):.3f}  →  mit Anreicherung {auc(s_enr,scr):.3f}")
