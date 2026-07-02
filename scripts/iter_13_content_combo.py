"""Iter 13 — Kombination der zwei Content-Achsen (global Abstract-Sim ⊕ reiche Summary-Sim).

Iter 12: beide Achsen ~0.69 AUC, aber sie irren UNTERSCHIEDLICH (rich hebt 2/4 verfehlte LES).
Wenn die Komplementarität echt ist, schlägt die Kombination jede Einzelachse. Sonst ist die Decke total.
max / Mittel / beide-als-LogReg-Features, OOF CV, keep-AUC + LES-Recall (gesamt + screening).
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3, json
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

df = E.load().reset_index(drop=True)
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr = (df["selection_mode"].fillna("")=="screening").values
yk = df["ykeep"].values

S = json.load(open("summaries.json"))["summaries"]
rich = lambda e: " ".join(p for p in [e.get("title",""), e.get("summary_de",""),
        " ".join(e.get("key_terms",[]) or []), " ".join(e.get("named_thinkers",[]) or [])] if p)
pub_text = [rich(e) for e in S.values()]
art_text = (df["title"].fillna("")+". "+df["abstract"].fillna("")+". "+
            df["concepts"].fillna("").str.replace("|"," ")+" "+df["topics"].fillna("").str.replace("|"," ")).tolist()
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("all-MiniLM-L6-v2")
def norm(M): return M/(np.linalg.norm(M,axis=1,keepdims=True)+1e-9)
A = norm(np.asarray(m.encode(art_text, show_progress_bar=False)))
P = norm(np.asarray(m.encode(pub_text, show_progress_bar=False)))
s_rich = (A @ P.T).max(axis=1)
s_glob = df["score_M7_EmbeddingSimilarity"].astype(float).fillna(0).values
# auf [0,1] skalieren für faire max/mean-Kombi
z = lambda v: (v - v.min())/(v.max()-v.min()+1e-9)
zr, zg = z(s_rich), z(s_glob)

# LogReg-Kombi OOF
X = np.column_stack([s_rich, s_glob])
skf = StratifiedKFold(5, shuffle=True, random_state=42); p_lr = np.zeros(len(df))
for tr,te in skf.split(X,yk):
    clf = make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, class_weight="balanced"))
    clf.fit(X[tr],yk[tr]); p_lr[te]=clf.predict_proba(X[te])[:,list(clf.classes_).index(1)]

biblio = ((df["f_own_coupling_union"]>=1)|(df["f_citation_hit_count"]>=1)).values
invis = (yk==1)&(~biblio)
feats = {"global allein": zg, "rich allein": zr, "max(rich,global)": np.maximum(zr,zg),
         "mean(rich,global)": (zr+zg)/2, "LogReg(rich,global) OOF": p_lr}
print(f"{'Kombination':<26}{'keep-AUC':>10}{'unsichtbar-AUC':>16}{'screening-AUC':>15}")
print("-"*67)
for name,s in feats.items():
    mask = invis|(yk==0)
    auc = roc_auc_score(yk,s)
    auc_i = roc_auc_score(invis[mask].astype(int), s[mask])
    auc_s = roc_auc_score(yk[scr], s[scr]) if yk[scr].sum() else float("nan")
    print(f"{name:<26}{auc:>10.3f}{auc_i:>16.3f}{auc_s:>15.3f}")
