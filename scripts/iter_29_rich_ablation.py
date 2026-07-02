"""Iter 29 — Ablation: welcher rich-Text-Bestandteil trägt die content-AUC?

Iter 13/27: reicher Eigenwerk-Text (summary_de + key_terms + named_thinkers) hebt die content-AUC.
Welcher Teil trägt? Kosten-Relevanz (P13): braucht es den teuren Opus-`summary_de`, oder reichen die
billigen `key_terms`/`named_thinkers`? Global-rich-Schwerpunkt (Iter 27: ≈ per-Werk, simpler).
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3, json
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.metrics import roc_auc_score
from sentence_transformers import SentenceTransformer

df = E.load().reset_index(drop=True)
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr=(df["selection_mode"].fillna("")=="screening").values
yk = df["ykeep"].values
S = json.load(open("summaries.json"))["summaries"]
art_text=(df["title"].fillna("")+". "+df["abstract"].fillna("")+". "+
          df["concepts"].fillna("").str.replace("|"," ")+" "+df["topics"].fillna("").str.replace("|"," ")).tolist()
m=SentenceTransformer("all-MiniLM-L6-v2")
nrm=lambda M:M/(np.linalg.norm(M,axis=1,keepdims=True)+1e-9)
A=nrm(np.asarray(m.encode(art_text,show_progress_bar=False)))

def pub_variant(fields):
    txt=[]
    for e in S.values():
        parts=[]
        if "title" in fields: parts.append(e.get("title",""))
        if "summary" in fields: parts.append(e.get("summary_de",""))
        if "terms" in fields: parts.append(" ".join(e.get("key_terms",[]) or []))
        if "thinkers" in fields: parts.append(" ".join(e.get("named_thinkers",[]) or []))
        txt.append(" ".join(p for p in parts if p))
    return txt

variants=[("nur Titel",["title"]), ("Titel+summary_de",["title","summary"]),
          ("Titel+key_terms",["title","terms"]), ("Titel+named_thinkers",["title","thinkers"]),
          ("key_terms allein",["terms"]), ("VOLL (alle)",["title","summary","terms","thinkers"])]
print(f"{'rich-Variante':<24}{'AUC gesamt':>12}{'AUC screening':>15}")
for name,fields in variants:
    P=nrm(np.asarray(m.encode(pub_variant(fields),show_progress_bar=False)))
    cent=nrm(P.mean(axis=0,keepdims=True)); s=(A@cent.T).ravel()
    print(f"  {name:<22}{roc_auc_score(yk,s):>12.3f}{roc_auc_score(yk[scr],s[scr]):>15.3f}")
