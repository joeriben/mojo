"""Wiederverwendbares Eval-Harness für die Filtermodell-Iterationen (docs/filter_models/).

Lädt features_gold.parquet + predictions_iter11_full.parquet (via .venv mit pyarrow),
merged auf id, liefert Feature-Matrix, Labels und Metriken. KEINE LLM-Calls,
keine Netzkosten. Ground truth = user_verdict (Relevanz für Benjamins Arbeit), n=461.

Aufruf immer mit dem Projekt-venv:  .venv/bin/python scripts/iter_XX_*.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.model_selection import StratifiedKFold

ROOT = Path(__file__).resolve().parent.parent
FG = ROOT / "backtest_data" / "features_gold.parquet"
PR = ROOT / "backtest_data" / "predictions_iter11_full.parquet"

KEEP = {"lesenswert", "scannen", "pflichtlektuere"}
LABELS3 = ["ignorieren", "scannen", "lesenswert"]

# Reale numerische Spalten aus features_gold (namentlich belegt, P2)
NUMERIC_FEATURES = [
    "f_citation_hit_count", "f_trigger_author_match", "f_ref_overlap_authored",
    "f_ref_overlap_trigger", "f_ref_count_total", "f_openalex_ref_count",
    "f_topic_count", "f_concept_count", "f_coauthor_hits", "f_title_len",
    "f_year_normalized", "f_2nd_trigger_ref_overlap", "f_2nd_trigger_ref_overlap_dk",
    "f_2nd_trigger_ref_overlap_ew", "f_2nd_trigger_ref_overlap_mp",
    "f_2nd_trigger_author_hit", "f_2nd_trigger_journal_hit",
    "f_own_coupling_union", "f_own_coupling_jaccard_oa", "abstract_len", "has_abstract",
]
# Inhalts-Ähnlichkeits-Scores (bereits berechnet — wiederverwendbar als Feature)
SCORE_FEATURES = ["score_M6_TfidfSimilarity", "score_M7_EmbeddingSimilarity",
                  "score_M10_ConceptVector"]

# Werk-geerdete vs. Trigger- vs. Inhalts-Familien (P2/P3-Buchhaltung)
OWN_WORK = ["f_citation_hit_count", "f_ref_overlap_authored", "f_coauthor_hits",
            "f_own_coupling_union", "f_own_coupling_jaccard_oa"]
TRIGGER = ["f_trigger_author_match", "f_ref_overlap_trigger", "f_2nd_trigger_ref_overlap",
           "f_2nd_trigger_ref_overlap_dk", "f_2nd_trigger_ref_overlap_ew",
           "f_2nd_trigger_ref_overlap_mp", "f_2nd_trigger_author_hit",
           "f_2nd_trigger_journal_hit"]
CONTENT = ["score_M6_TfidfSimilarity", "score_M7_EmbeddingSimilarity",
           "score_M10_ConceptVector"]

# Gemessene Anker 2026-05-31, n=461, vs user_verdict (P15-Vergleichsleiste)
BASELINES = {
    "keep-all":                 {"f1_3cls": None,  "f1_keep": 0.580},
    "M7_EmbeddingSimilarity":   {"f1_3cls": 0.465, "f1_keep": 0.614},
    "M8_LogReg_TunedProba":     {"f1_3cls": 0.585, "f1_keep": 0.695},
    "M9_Cascade_PerJournalBase":{"f1_3cls": 0.603, "f1_keep": 0.720},
    "agent (LLM-Decke)":        {"f1_3cls": 0.679, "f1_keep": 0.749},
}


def fold3(s: pd.Series) -> pd.Series:
    return s.replace({"pflichtlektuere": "lesenswert"})


def load() -> pd.DataFrame:
    fg = pd.read_parquet(FG)
    pr = pd.read_parquet(PR)
    keep_cols = ["id"] + [c for c in SCORE_FEATURES if c in pr.columns]
    df = fg.merge(pr[keep_cols], on="id", how="left")
    df["y3"] = fold3(df["user_verdict"])
    df["ykeep"] = df["user_verdict"].isin(KEEP).astype(int)
    return df


def metrics(y_true3, y_pred3) -> dict:
    yt = pd.Series(list(y_true3)); yp = pd.Series(list(y_pred3))
    ytk = yt.isin(KEEP).astype(int); ypk = yp.isin(KEEP).astype(int)
    return {
        "f1_3cls": round(f1_score(yt, yp, average="macro", labels=LABELS3, zero_division=0), 3),
        "f1_keep": round(f1_score(ytk, ypk, zero_division=0), 3),
        "les_recall": round(recall_score((yt == "lesenswert").astype(int),
                                          (yp == "lesenswert").astype(int), zero_division=0), 3),
        "keep_prec": round(precision_score(ytk, ypk, zero_division=0), 3),
        "keep_recall": round(recall_score(ytk, ypk, zero_division=0), 3),
    }


def cv_oof(make_model, X, y3, n_splits=5, seed=42) -> pd.Series:
    """Out-of-fold 3-Klassen-Vorhersagen (StratifiedKFold). make_model()->fit/predict."""
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    Xv = X.values if hasattr(X, "values") else np.asarray(X)
    yy = pd.Series(list(y3))
    oof = np.empty(len(yy), dtype=object)
    for tr, te in skf.split(Xv, yy):
        m = make_model(); m.fit(Xv[tr], yy.iloc[tr])
        oof[te] = m.predict(Xv[te])
    return pd.Series(oof)


def report(name: str, y_pred3, df: pd.DataFrame) -> dict:
    m = metrics(df["y3"], y_pred3)
    bar = BASELINES["M9_Cascade_PerJournalBase"]["f1_3cls"]
    ceil = BASELINES["agent (LLM-Decke)"]["f1_3cls"]
    delta = "" if m["f1_3cls"] is None else f"  (Δ Algo-Bar {m['f1_3cls']-bar:+.3f} · Δ LLM-Decke {m['f1_3cls']-ceil:+.3f})"
    print(f"[{name}]  f1_3cls={m['f1_3cls']}  f1_keep={m['f1_keep']}  "
          f"LES-Rec={m['les_recall']}  keepPrec={m['keep_prec']}  keepRec={m['keep_recall']}{delta}")
    return m


if __name__ == "__main__":
    df = load()
    print("geladen:", df.shape, "| y3:", dict(df["y3"].value_counts()))
    print("Feature-Familien — own:", len(OWN_WORK), "trigger:", len(TRIGGER), "content:", len(CONTENT))
