"""Iter 47 — Fehleranalyse: die irreduziblen Hard-Cases konkret benennen.

Die LES, an denen Algo UND Erdung gemeinsam scheitern = tief im M-C-Rang UND kein geerdeter Anker.
Qualitative Diagnose: was steht in diesen Artikeln? Titel/Journal/Concepts/Abstract-Snippet, damit die
harte Grenze (Iter 11/39/43/46) nicht nur eine Zahl, sondern eine benennbare Artikel-Klasse ist.
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3, json, re
import numpy as np, pandas as pd
import fm_eval as E
from sklearn.model_selection import StratifiedKFold

df = E.load().reset_index(drop=True)
df = df.merge(pd.read_parquet("backtest_data/rich_sim.parquet"), on="id", how="left")
con = sqlite3.connect("articles.db")
arts = pd.read_sql_query("SELECT id, openalex_refs, selection_mode FROM articles", con); con.close()
def wset(s):
    if not s: return set()
    try: items = json.loads(s)
    except Exception: items = re.findall(r"W\d+", str(s))
    return {re.sub(r".*/", "", str(x)) for x in items if "W" in str(x)}
arts["refset"] = arts["openalex_refs"].apply(wset)
df = df.merge(arts[["id", "refset", "selection_mode"]], on="id", how="left")
df["refset"] = df["refset"].apply(lambda x: x if isinstance(x, set) else set())
con = sqlite3.connect("bezugsautoren.db")
bez = set(r[0] for r in con.execute("SELECT DISTINCT work_oa_id FROM author_works WHERE work_oa_id IS NOT NULL")); con.close()

yk = df["ykeep"].values; les = (df["y3"] == "lesenswert").values
rich = df["rich_sim"].astype(float).values
biblio = ((df["f_own_coupling_union"].fillna(0) >= 1) | (df["f_citation_hit_count"].fillna(0) >= 1)).values
bezhit = df["refset"].apply(lambda s: len(s & bez) >= 1).values
anchor = biblio | bezhit
z = lambda v: (v - np.nanmin(v)) / (np.nanmax(v) - np.nanmin(v) + 1e-9)
pj = np.zeros(len(df)); G = np.zeros(len(df))
for tr, te in StratifiedKFold(5, shuffle=True, random_state=42).split(df, yk):
    g = yk[tr].mean(); rate = {}
    for j, sub in df.iloc[tr].groupby("journal_short"):
        n = len(sub); rate[j] = (sub["ykeep"].mean() * n + g * 5) / (n + 5)
    for i in te: pj[i] = rate.get(df.iloc[i]["journal_short"], g); G[i] = g
mc = np.where(biblio, 1.0 + z(z(rich) + 0.5 * z(np.maximum(0, pj - G))), z(z(rich) + 0.5 * z(np.maximum(0, pj - G))))
rank = np.array([(mc < mc[i]).mean() for i in range(len(df))])

# Hard-Case = LES, M-C-Rang < 50 %, kein Anker
hard = les & (rank < 0.50) & (~anchor)
print(f"Irreduzible Hard-Case-LES (LES & M-C-Rang<50% & kein Anker): {hard.sum()} von {les.sum()} LES\n")
cols = ["title", "journal_short", "selection_mode", "concepts"]
for i in np.where(hard)[0]:
    r = df.iloc[i]
    ab = str(df.iloc[i].get("abstract", "") or "")[:240].replace("\n", " ")
    con_ = str(r.get("concepts", "") or "").replace("|", ", ")[:140]
    print(f"• [{rank[i]:.0%}-Rang | rich={rich[i]:.2f}] {str(r['title'])[:90]}")
    print(f"    {r['journal_short']} | mode={r['selection_mode']} | concepts: {con_}")
    if ab: print(f"    abstract: {ab}…")
    print()

# Kontrast: die LES, die M-C HOCH reiht (Top 25 %) — woran erkennt es die?
easy = les & (rank >= 0.75)
print(f"Kontrast — leicht erkannte LES (Rang≥75%): {easy.sum()}")
print(f"  davon mit Anker: {anchor[easy].mean():.0%}, Ø rich-sim {rich[easy].mean():.2f} (Hard-Cases: {rich[hard].mean():.2f})")
