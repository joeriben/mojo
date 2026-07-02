"""Iter 10 — Cascade-Komposition: own+content-Basis + Bibliometrie-Veto-up.

Iter 01: Bibliometrie ist hochpräzise (0.83-1.0) aber sieht nur 19% der Treffer.
Iter 03: own+content LogReg = 0.514 macro-F1. Dokumentierte Cascade-Idee: das schwache
Basismodell mit hochpräzisem Biblio-Veto-up kombinieren (wo Kopplung/Zitation feuert →
hochstufen). Memory (iter13) vermutet: redundant, weil Veto-Treffer schon LES sind.
Hier ehrlich auf user_verdict gemessen (OOF CV), gesamt UND screening-only.
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
con = sqlite3.connect("articles.db")
sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left")
scr = (df["selection_mode"].fillna("") == "screening").values

X = df[E.OWN_WORK + E.CONTENT].astype(float).values
LAB = E.LABELS3                 # ["ignorieren","scannen","lesenswert"]
y3 = df["y3"].map({l: i for i, l in enumerate(LAB)}).values   # → 0/1/2
biblio = ((df["f_own_coupling_union"] >= 1) | (df["f_citation_hit_count"] >= 1)).values

# OOF 3-Klassen-Basismodell
skf = StratifiedKFold(5, shuffle=True, random_state=42)
base = np.zeros(len(df), int)
for tr, te in skf.split(X, y3):
    clf = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                        LogisticRegression(max_iter=3000, class_weight="balanced"))
    clf.fit(X[tr], y3[tr]); base[te] = clf.predict(X[te])

# Veto-Varianten
veto_scan = np.where(biblio, np.maximum(base, 1), base)   # mind. scannen
veto_les  = np.where(biblio, np.maximum(base, 2), base)   # auf lesenswert

LAB = E.LABELS3
def show(name, pred, mask):
    yt = np.array(LAB)[y3[mask]]; yp = np.array(LAB)[pred[mask]]
    m = E.metrics(yt, yp)
    print(f"  {name:<22}{m['f1_3cls']:>9.3f}{m['f1_keep']:>9.3f}{m['les_recall']:>11.3f}{m['keep_prec']:>11.3f}")

print(f"Biblio-Veto feuert: {biblio.sum()} gesamt, {(biblio&scr).sum()} im screening-Strom")
print(f"  davon echt-keep: {df['ykeep'][biblio].mean():.0%} (gesamt)\n")
for label, mask in [("GESAMT", np.ones(len(df), bool)), ("SCREENING (blind)", scr)]:
    print(f"{label} (n={mask.sum()}, LES={ (y3[mask]==2).sum() }):")
    print(f"  {'Modell':<22}{'macro-F1':>9}{'keep-F1':>9}{'LES-Rec':>11}{'keep-Prec':>11}")
    show("Basis own+content", base, mask)
    show("+ Veto→scannen", veto_scan, mask)
    show("+ Veto→lesenswert", veto_les, mask)
    print()
