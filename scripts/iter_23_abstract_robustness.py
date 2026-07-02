"""Iter 23 — Robustheit gegen fehlende/kurze Abstracts.

Der rich-Ranker (Iter 16) beruht auf Titel+Abstract+Konzepten. Realer Strom (OJS/RSS, Memory
Sonderfälle zkmb/e-flux) liefert oft KEINEN Abstract. Frage: wie viele Gold-Artikel sind abstract-arm,
und wie stark bricht der Ranker dort ein? Plus: trägt Titel+Konzepte allein als Fallback?
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3, json
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.metrics import roc_auc_score
from sentence_transformers import SentenceTransformer

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr=(df["selection_mode"].fillna("")=="screening").values
df["alen"] = df["abstract"].fillna("").str.len()
yk = df["ykeep"].values

print("Abstract-Verfügbarkeit:")
for lab, m in [("kein/sehr kurz (<50)", df["alen"]<50), ("kurz (50-200)", (df["alen"]>=50)&(df["alen"]<200)),
               ("voll (>=200)", df["alen"]>=200)]:
    print(f"  {lab:<22} {m.sum():>3} ({m.mean():.0%})  davon keeper {df.loc[m,'ykeep'].mean():.0%}")
print(f"  screening-Strom ohne Abstract (<50): {(scr&(df['alen']<50)).sum()}/{scr.sum()}")

# Fallback-rich: nur Titel+Konzepte (kein Abstract) neu berechnen
S = json.load(open("summaries.json"))["summaries"]
rich = lambda e: " ".join(p for p in [e.get("title",""), e.get("summary_de",""),
        " ".join(e.get("key_terms",[]) or []), " ".join(e.get("named_thinkers",[]) or [])] if p)
pub_text=[rich(e) for e in S.values()]
art_noabs=(df["title"].fillna("")+". "+df["concepts"].fillna("").str.replace("|"," ")+" "+
           df["topics"].fillna("").str.replace("|"," ")).tolist()
m=SentenceTransformer("all-MiniLM-L6-v2")
nrm=lambda M:M/(np.linalg.norm(M,axis=1,keepdims=True)+1e-9)
A=nrm(np.asarray(m.encode(art_noabs,show_progress_bar=False))); P=nrm(np.asarray(m.encode(pub_text,show_progress_bar=False)))
df["rich_noabs"]=(A@P.T).max(axis=1)

print("\nrich-Ranker keep-AUC, stratifiziert nach Abstract:")
print(f"  {'Teilmenge':<28}{'n':>5}{'rich (m.Abs)':>14}{'rich_noabs':>13}")
for lab, m_ in [("voll-Abstract (>=200)", df["alen"]>=200), ("abstract-arm (<200)", df["alen"]<200),
                ("screening voll", scr&(df["alen"]>=200)), ("screening arm", scr&(df["alen"]<200))]:
    n=m_.sum(); yy=yk[m_]
    if n>=10 and yy.sum()>0 and yy.sum()<n:
        a1=roc_auc_score(yy, df.loc[m_,"rich_sim"].astype(float))
        a2=roc_auc_score(yy, df.loc[m_,"rich_noabs"].astype(float))
        print(f"  {lab:<28}{n:>5}{a1:>14.3f}{a2:>13.3f}")
    else:
        print(f"  {lab:<28}{n:>5}{'(zu wenig/einseitig)':>27}")
