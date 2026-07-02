"""Iter 02 — Inhalts-Achse: Embedding/TFIDF/Concept-Similarity als Relevanz-Score.

Frage: Holt Inhalts-Ähnlichkeit den Recall, den Bibliometrie nicht hat (Iter 01: Decke 19%)?
Und vor allem: rettet sie die bibliometrisch UNSICHTBAREN Treffer?
"""
import sys; sys.path.insert(0, "scripts")
import numpy as np, pandas as pd
import fm_eval as E

df = E.load()
yk = df["ykeep"].values

def sweep(col):
    s = df[col].astype(float).fillna(df[col].astype(float).median())
    best = None
    for q in np.linspace(0.30, 0.90, 25):
        thr = s.quantile(q)
        keep = (s >= thr)
        m = E.metrics(df["y3"], pd.Series(["scannen" if k else "ignorieren" for k in keep]))
        if best is None or m["f1_keep"] > best[1]["f1_keep"]:
            best = (round(q, 2), m, round(thr, 4))
    return best

for col in E.CONTENT:
    q, m, thr = sweep(col)
    print(f"{col:<32} best@q={q} thr={thr}  f1_keep={m['f1_keep']:.3f}  "
          f"keepPrec={m['keep_prec']:.3f} keepRec={m['keep_recall']:.3f} LES-Rec={m['les_recall']:.3f}")

# Kernfrage: rettet Embedding die bibliometrisch unsichtbaren Treffer?
biblio = ((df["f_own_coupling_union"] >= 1) | (df["f_citation_hit_count"] >= 1) |
          (df["f_trigger_author_match"] == 1) | (df["f_ref_overlap_authored"] >= 1)).values
emb = df["score_M7_EmbeddingSimilarity"].astype(float).fillna(0).values
invisible_keepers = (yk == 1) & (~biblio)        # die 81%-Lücke aus Iter 01
discards = (yk == 0)
print(f"\nEmbedding-Sim Median:")
print(f"  unsichtbare keep-Treffer (n={invisible_keepers.sum()}): {np.median(emb[invisible_keepers]):.3f}")
print(f"  discards            (n={discards.sum()}): {np.median(emb[discards]):.3f}")
# AUC der unsichtbaren Treffer vs discards anhand Embedding allein
from sklearn.metrics import roc_auc_score
mask = invisible_keepers | discards
auc = roc_auc_score(invisible_keepers[mask].astype(int), emb[mask])
print(f"  AUC (unsichtbare keep vs discards, nur Embedding): {auc:.3f}")
