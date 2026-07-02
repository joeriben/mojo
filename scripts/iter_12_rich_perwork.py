"""Iter 12 — Per-Werk-Sim mit REICHEM Eigenwerk-Text (Summaries) statt Titeln.

Iter 09 fand per-Werk≈global, ABER nur mit Titel+Venue (zu dünn, ehrlich vermerkt).
Iter 11 zeigt: die verfehlten LES sind KONZEPTUELL einschlägig (Adorno, Haraway, Datafizierung).
summaries.json hat 53 Opus-Summaries mit summary_de + key_terms + named_thinkers — Benjamins Werk
konzept-reich. Test: hebt reicher Eigenwerk-Text die content-AUC, und steigen die 4 blind-verfehlten LES?
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3, json
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.metrics import roc_auc_score

df = E.load().reset_index(drop=True)
con = sqlite3.connect("articles.db"); sm = pd.read_sql_query("SELECT id, selection_mode FROM articles", con); con.close()
df = df.merge(sm, on="id", how="left"); scr = (df["selection_mode"].fillna("") == "screening").values
yk = df["ykeep"].values

S = json.load(open("summaries.json"))["summaries"]
def rich(e):
    parts = [e.get("title",""), e.get("summary_de",""),
             " ".join(e.get("key_terms",[]) or []), " ".join(e.get("named_thinkers",[]) or [])]
    return " ".join(p for p in parts if p)
pub_text = [rich(e) for e in S.values()]                       # 53 reiche Eigenwerk-Texte
# Konzept-reicher Artikel-Text: Abstract + OpenAlex concepts + topics
art_text = (df["title"].fillna("") + ". " + df["abstract"].fillna("") + ". " +
            df["concepts"].fillna("").str.replace("|"," ") + " " +
            df["topics"].fillna("").str.replace("|"," ")).tolist()

def maxsim(A, P):
    A = A/(np.linalg.norm(A,axis=1,keepdims=True)+1e-9); P = P/(np.linalg.norm(P,axis=1,keepdims=True)+1e-9)
    return (A @ P.T).max(axis=1)

from sentence_transformers import SentenceTransformer
m = SentenceTransformer("all-MiniLM-L6-v2")
A = np.asarray(m.encode(art_text, show_progress_bar=False))
P = np.asarray(m.encode(pub_text, show_progress_bar=False))
sim_rich = maxsim(A, P)
glob = df["score_M7_EmbeddingSimilarity"].astype(float).fillna(0).values

biblio = ((df["f_own_coupling_union"]>=1)|(df["f_citation_hit_count"]>=1)).values
invis = (yk==1)&(~biblio)
print(f"{'Feature':<26}{'keep-AUC':>10}{'unsichtbare-keep AUC':>22}")
print("-"*58)
for name, s in [("Summary-reich per-Werk", sim_rich), ("score_M7 (global, Ref)", glob)]:
    mask = invis|(yk==0)
    print(f"{name:<26}{roc_auc_score(yk,s):>10.3f}{roc_auc_score(invis[mask].astype(int), s[mask]):>22.3f}")

# Steigen die 4 blind-verfehlten LES? Perzentil-Rang innerhalb screening-Strom
miss_titles = ["Die AfD","Rating villagers","Making Queer Kin","Mikrokosmoksia"]
print(f"\n4 blind-verfehlte LES — Perzentil-Rang (screening-Strom, höher=relevanter):")
sc_idx = np.where(scr)[0]
for t in miss_titles:
    hit = df[scr & df["title"].fillna("").str.contains(t, regex=False)]
    if len(hit):
        i = hit.index[0]
        pr_rich = (sim_rich[sc_idx] < sim_rich[i]).mean()
        pr_glob = (glob[sc_idx] < glob[i]).mean()
        print(f"  {t:<18} reich={pr_rich:>5.0%}  global={pr_glob:>5.0%}")
