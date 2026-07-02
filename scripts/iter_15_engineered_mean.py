"""Iter 15 — mean(rich,global) als EIN engineertes Feature + explizite Ranker-Bewertung.

Iter 14: rich roh neben M7 schadet der 3-Klassen-macro-F1. Iter 13: mean(rich,global) war der beste
Kombinierer (AUC 0.728 > LogReg 0.722). Test 1: hilft mean als EIN Feature der 3-Klassen-Entscheidung?
Test 2 (Re-Framing): als reiner KEEP-RANKER — wie viel keep-Recall hält der mean-Ranker vs content-only
bei gleicher behaltener Fraktion auf dem blinden Strom (der reale Vorfilter-Use-Case)?
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr = (df["selection_mode"].fillna("")=="screening").values

LAB = E.LABELS3
y3 = df["y3"].map({l:i for i,l in enumerate(LAB)}).values
yk = df["ykeep"].values
z = lambda v: (v - np.nanmin(v))/(np.nanmax(v)-np.nanmin(v)+1e-9)
df["content_mean"] = (z(df["rich_sim"].astype(float).values) + z(df["score_M7_EmbeddingSimilarity"].astype(float).fillna(0).values))/2

def oof_pred(cols):
    X = df[cols].astype(float).values
    skf = StratifiedKFold(5, shuffle=True, random_state=42); pred = np.zeros(len(df), int)
    for tr,te in skf.split(X,y3):
        clf = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                            LogisticRegression(max_iter=3000, class_weight="balanced"))
        clf.fit(X[tr],y3[tr]); pred[te]=clf.predict(X[te])
    return pred

OWN_NOSCORE = [c for c in E.OWN_WORK if c.startswith("f_")]
print("=== Test 1: 3-Klassen-macro-F1 (OOF) ===")
configs = [("own+content (Basis)", E.OWN_WORK+E.CONTENT),
           ("own+content+mean", E.OWN_WORK+E.CONTENT+["content_mean"]),
           ("own + mean (1 content-Feat)", OWN_NOSCORE+["content_mean"])]
for label,mask in [("GESAMT",np.ones(len(df),bool)),("SCREENING",scr)]:
    print(f"\n{label} (LES={(y3[mask]==2).sum()}):  {'macro-F1':>9}{'keep-F1':>9}{'LES-Rec':>9}")
    for n,c in configs:
        p=oof_pred(c); yt=np.array(LAB)[y3[mask]]; yp=np.array(LAB)[p[mask]]; mm=E.metrics(yt,yp)
        print(f"  {n:<28}{mm['f1_3cls']:>9.3f}{mm['f1_keep']:>9.3f}{mm['les_recall']:>9.3f}")

print("\n=== Test 2: KEEP-RANKER auf blindem Strom (welcher Ranker hält mehr Treffer bei gleicher Last) ===")
rankers = {"content_mean (rich⊕global)": df["content_mean"].values,
           "score_M7 allein (global)":   df["score_M7_EmbeddingSimilarity"].astype(float).fillna(0).values,
           "rich allein":                z(df["rich_sim"].astype(float).values)}
ys, n_les = yk[scr], int(yk[scr].sum())
print(f"  blinder Strom: n={scr.sum()}, keep={n_les}")
print(f"  {'Ranker':<28}{'AUC':>7}{'Recall@top30%':>15}{'Recall@top50%':>15}")
for name,s in rankers.items():
    ss = s[scr]; order = np.argsort(-ss)
    auc = roc_auc_score(ys, ss)
    r30 = ys[order[:int(0.30*len(ss))]].sum()/n_les
    r50 = ys[order[:int(0.50*len(ss))]].sum()/n_les
    print(f"  {name:<28}{auc:>7.3f}{r30:>15.0%}{r50:>15.0%}")
