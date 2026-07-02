"""Iter 14 — reiche Summary-Sim ins volle 3-Klassen-Modell falten.

Iter 13: rich-Sim ist auf dem blinden Strom der bessere Content-Hebel (0.632 vs 0.517 AUC).
Frage: hebt das die TATSÄCHLICHE Triage-macro-F1 / LES-Recall, oder bleibt der Gewinn in der
AUC-Rangordnung stecken? Gegen die ehrliche Leiste: Boden 0.544/0.589, own+content 0.514.
OOF CV, gesamt + screening-only.
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

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr = (df["selection_mode"].fillna("")=="screening").values

LAB = E.LABELS3
y3 = df["y3"].map({l:i for i,l in enumerate(LAB)}).values
GLOBAL = ["score_M7_EmbeddingSimilarity"]
RICH = ["rich_sim"]

def oof(cols):
    X = df[cols].astype(float).values
    skf = StratifiedKFold(5, shuffle=True, random_state=42); pred = np.zeros(len(df), int)
    for tr,te in skf.split(X,y3):
        clf = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                            LogisticRegression(max_iter=3000, class_weight="balanced"))
        clf.fit(X[tr],y3[tr]); pred[te]=clf.predict(X[te])
    return pred

def row(name, pred, mask):
    yt = np.array(LAB)[y3[mask]]; yp = np.array(LAB)[pred[mask]]
    m = E.metrics(yt,yp)
    print(f"  {name:<30}{m['f1_3cls']:>9.3f}{m['f1_keep']:>9.3f}{m['les_recall']:>10.3f}")

configs = [
    ("own+content (Iter 03 Basis)", E.OWN_WORK + E.CONTENT),
    ("own+content+rich",            E.OWN_WORK + E.CONTENT + RICH),
    ("own+rich (ohne global-M7)",   E.OWN_WORK + RICH),
    ("own+global+rich (schlank)",   E.OWN_WORK + GLOBAL + RICH),
    ("nur rich+global",             GLOBAL + RICH),
]
preds = {n: oof(c) for n,c in configs}
for label, mask in [("GESAMT", np.ones(len(df),bool)), ("SCREENING (blind)", scr)]:
    print(f"\n{label} (n={mask.sum()}, LES={(y3[mask]==2).sum()}):")
    print(f"  {'Modell':<30}{'macro-F1':>9}{'keep-F1':>9}{'LES-Rec':>10}")
    for n in preds: row(n, preds[n], mask)
print("\nLeiste: Boden 0.544/0.589 · Decke 0.679 · own+content 0.514")
