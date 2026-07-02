"""Iter 11 — Anatomie der Fehler: welche LES verfehlt own+content, und sind sie geerdet?

Iter 10: Biblio-Veto wirkungslos auf blindem Strom. Bevor Phase C (geerdete Bezüge) baut:
WO scheitert das Basismodell? Teilen die verfehlten LES überhaupt IRGENDEIN geerdetes
Signal (Kopplung/Zitation/Coautor/Ref-Overlap/Inhalt)? Wenn nein → strukturell signalfrei,
dann kann auch Volltext-Erdung sie nicht retten (Memory feedback_ground_truth: 72 Hard-Cases).
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

LAB = E.LABELS3
y3 = df["y3"].map({l: i for i, l in enumerate(LAB)}).values
X = df[E.OWN_WORK + E.CONTENT].astype(float).values
skf = StratifiedKFold(5, shuffle=True, random_state=42)
pred = np.zeros(len(df), int)
for tr, te in skf.split(X, y3):
    clf = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                        LogisticRegression(max_iter=3000, class_weight="balanced"))
    clf.fit(X[tr], y3[tr]); pred[te] = clf.predict(X[te])

# geerdete Signale (alle aus dem Eigenwerk/Umfeld ableitbar)
GROUND = ["f_own_coupling_union", "f_citation_hit_count", "f_coauthor_hits",
          "f_ref_overlap_authored", "f_ref_overlap_trigger", "score_M7_EmbeddingSimilarity"]
for c in GROUND:
    df[c] = df[c].astype(float).fillna(0)
# „signalfrei" = kein bibliometrisches/biographisches Signal UND content-Sim unter Median-keep
m7_med = df.loc[df["ykeep"] == 1, "score_M7_EmbeddingSimilarity"].median()
biblio_bio = df[["f_own_coupling_union","f_citation_hit_count","f_coauthor_hits",
                 "f_ref_overlap_authored","f_ref_overlap_trigger"]].sum(axis=1).values
signalfrei = (biblio_bio == 0) & (df["score_M7_EmbeddingSimilarity"].values < m7_med)

les = (y3 == 2)
caught = les & (pred == 2)
missed = les & (pred != 2)
print(f"keep-Sim Median (echte keep): {m7_med:.3f}\n")
for label, mask in [("GESAMT", np.ones(len(df), bool)), ("SCREENING (blind)", scr)]:
    c, m = (caught & mask), (missed & mask)
    print(f"{label}: LES={les[mask].sum()}  getroffen={c.sum()}  verfehlt={m.sum()}")
    if m.sum():
        print(f"  verfehlte-LES signalfrei (kein biblio/bio + Sim<Median): "
              f"{signalfrei[m].sum()}/{m.sum()}")
    print(f"  {'Signal':<32}{'getroffene-LES Ø':>18}{'verfehlte-LES Ø':>18}")
    for col in GROUND:
        a = df.loc[c, col].mean() if c.sum() else float("nan")
        b = df.loc[m, col].mean() if m.sum() else float("nan")
        print(f"  {col:<32}{a:>18.3f}{b:>18.3f}")
    print()
