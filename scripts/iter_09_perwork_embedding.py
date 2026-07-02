"""Iter 09 — Per-Werk-max-Similarity zum Œuvre (Profil-Sketch: per-Werk statt global).

Iter 02: globale Korpus-Ähnlichkeit (score_M7) hat nur AUC 0.66. Hypothese (Memory
project_profile_modelling): Per-Werk-Embedding + max über Eigenwerke trägt mehr als der
globale Schwerpunkt, weil Benjamins Werk multimodal ist. Offline, kein API-Cost.
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.metrics import roc_auc_score

df = E.load().reset_index(drop=True)
con = sqlite3.connect("own_refs.db")
pubs = pd.read_sql_query("SELECT title, venue, year FROM publications WHERE title IS NOT NULL", con)
con.close()
pub_text = (pubs["title"].fillna("") + ". " + pubs["venue"].fillna("")).tolist()
art_text = (df["title"].fillna("") + ". " + df["abstract"].fillna("")).tolist()
yk = df["ykeep"].values

def maxsim_from_vectors(A, P):
    A = A / (np.linalg.norm(A, axis=1, keepdims=True) + 1e-9)
    P = P / (np.linalg.norm(P, axis=1, keepdims=True) + 1e-9)
    return (A @ P.T).max(axis=1)        # je Artikel: max Cosine zu irgendeinem Eigenwerk

results = {}
# (a) Sentence-Transformer, falls verfügbar (sonst überspringen)
try:
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer("all-MiniLM-L6-v2")
    A = np.asarray(m.encode(art_text, show_progress_bar=False))
    P = np.asarray(m.encode(pub_text, show_progress_bar=False))
    results["ST per-Werk-max"] = maxsim_from_vectors(A, P)
except Exception as e:
    print(f"(SentenceTransformer übersprungen: {str(e)[:80]})")

# (b) TF-IDF per-Werk-max (immer, offline)
from sklearn.feature_extraction.text import TfidfVectorizer
vec = TfidfVectorizer(max_features=8000, ngram_range=(1, 2), min_df=2)
allv = vec.fit_transform(art_text + pub_text)
A = allv[:len(art_text)].toarray(); P = allv[len(art_text):].toarray()
results["TFIDF per-Werk-max"] = maxsim_from_vectors(A, P)

# Vergleich: globale Korpus-Ähnlichkeit (score_M7) als keep-Diskriminator
glob = df["score_M7_EmbeddingSimilarity"].astype(float).fillna(0).values
results["score_M7 (global, Ref)"] = glob

biblio = ((df["f_own_coupling_union"] >= 1) | (df["f_citation_hit_count"] >= 1)).values
invis = (yk == 1) & (~biblio)
print(f"{'Feature':<26}{'keep-AUC':>10}{'AUC unsichtbare-keep vs disc':>30}")
print("-" * 66)
for name, s in results.items():
    auc_all = roc_auc_score(yk, s)
    mask = invis | (yk == 0)
    auc_inv = roc_auc_score(invis[mask].astype(int), s[mask])
    print(f"{name:<26}{auc_all:>10.3f}{auc_inv:>30.3f}")
