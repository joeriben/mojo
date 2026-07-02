"""Iter 27 — Per-Cluster-Ranking (Profil-Sketch-Topologie).

project_profile_modelling: Embedding pro Eigenwerk + Soft-Cluster statt globaler Haufen-Aggregation.
Iter 12: per-Werk-max ≈ global (Extreme). Mittelweg: Eigenwerk-Summaries in K Cluster, Artikel gegen
den ÄHNLICHSTEN Cluster-Schwerpunkt ranken. Trennt das schärfer als global — oder sind 53 Werke / K
Cluster zu dünn? Voll geerdet (Cluster aus Benjamins Werk-Embeddings), KEINE Diskurs-Labels (anti-zirkulär).
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3, json
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.metrics import roc_auc_score
from sklearn.cluster import KMeans
from sentence_transformers import SentenceTransformer

df = E.load().reset_index(drop=True)
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr=(df["selection_mode"].fillna("")=="screening").values
yk = df["ykeep"].values

S = json.load(open("summaries.json"))["summaries"]
rich = lambda e: " ".join(p for p in [e.get("title",""), e.get("summary_de",""),
        " ".join(e.get("key_terms",[]) or []), " ".join(e.get("named_thinkers",[]) or [])] if p)
pub_text=[rich(e) for e in S.values()]
art_text=(df["title"].fillna("")+". "+df["abstract"].fillna("")+". "+
          df["concepts"].fillna("").str.replace("|"," ")+" "+df["topics"].fillna("").str.replace("|"," ")).tolist()
m=SentenceTransformer("all-MiniLM-L6-v2")
nrm=lambda M:M/(np.linalg.norm(M,axis=1,keepdims=True)+1e-9)
A=nrm(np.asarray(m.encode(art_text,show_progress_bar=False)))
P=nrm(np.asarray(m.encode(pub_text,show_progress_bar=False)))

glob_centroid = nrm(P.mean(axis=0, keepdims=True))
s_global = (A @ glob_centroid.T).ravel()
s_perwork = (A @ P.T).max(axis=1)

def auc(s, mask): return roc_auc_score(yk[mask], s[mask])
print(f"{'Repräsentation':<26}{'AUC gesamt':>12}{'AUC screening':>15}")
print(f"  {'global Schwerpunkt':<24}{auc(s_global,np.ones(len(df),bool)):>12.3f}{auc(s_global,scr):>15.3f}")
for K in [3, 5, 7, 10]:
    km = KMeans(n_clusters=K, random_state=42, n_init=10).fit(P)
    cent = nrm(km.cluster_centers_)
    s_cluster = (A @ cent.T).max(axis=1)   # je Artikel: Sim zum ähnlichsten Cluster
    print(f"  {('per-Cluster K='+str(K)):<24}{auc(s_cluster,np.ones(len(df),bool)):>12.3f}{auc(s_cluster,scr):>15.3f}")
print(f"  {'per-Werk-max (Iter12)':<24}{auc(s_perwork,np.ones(len(df),bool)):>12.3f}{auc(s_perwork,scr):>15.3f}")
