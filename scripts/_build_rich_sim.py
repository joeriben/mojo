"""Hilfsskript: reiche Summary-per-Werk-Sim einmal berechnen + cachen (backtest_data/rich_sim.parquet).
Damit müssen iter_14+ den Encoder nicht jedes Mal laden. Spalten: id, rich_sim."""
import sys; sys.path.insert(0, "scripts")
import json
import numpy as np, pandas as pd
import fm_eval as E
from sentence_transformers import SentenceTransformer

df = E.load().reset_index(drop=True)
S = json.load(open("summaries.json"))["summaries"]
rich = lambda e: " ".join(p for p in [e.get("title",""), e.get("summary_de",""),
        " ".join(e.get("key_terms",[]) or []), " ".join(e.get("named_thinkers",[]) or [])] if p)
pub_text = [rich(e) for e in S.values()]
art_text = (df["title"].fillna("")+". "+df["abstract"].fillna("")+". "+
            df["concepts"].fillna("").str.replace("|"," ")+" "+df["topics"].fillna("").str.replace("|"," ")).tolist()
m = SentenceTransformer("all-MiniLM-L6-v2")
norm = lambda M: M/(np.linalg.norm(M,axis=1,keepdims=True)+1e-9)
A = norm(np.asarray(m.encode(art_text, show_progress_bar=False)))
P = norm(np.asarray(m.encode(pub_text, show_progress_bar=False)))
out = pd.DataFrame({"id": df["id"].values, "rich_sim": (A @ P.T).max(axis=1)})
out.to_parquet("backtest_data/rich_sim.parquet")
print(f"gecacht: backtest_data/rich_sim.parquet ({len(out)} Zeilen, rich_sim "
      f"min={out.rich_sim.min():.3f} max={out.rich_sim.max():.3f})")
