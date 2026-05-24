"""Backtest-Runner: 8 algorithmische Verfahren vs. LLM-Agent.

Lädt features_gold.parquet (n=461), instantiiert alle Methoden, optimiert
Schwellen via Grid-Search auf 5-fold StratifiedKFold (für M1–M7 nur Threshold-
Tuning, für M8 echter ML-Cross-Val), berechnet Metriken und schreibt einen
Vergleichsreport gegen die Agent-Baseline (71.6% Agreement).

Usage:
    .venv/bin/python scripts/backtest_run.py
    .venv/bin/python scripts/backtest_run.py --quick   # ohne M7 (Embeddings)
    .venv/bin/python scripts/backtest_run.py --report-out docs/backtest_algorithmic_v1.md

Output:
    docs/backtest_algorithmic_v1.md          (Hauptreport)
    backtest_data/predictions.parquet        (per-Methode Predictions + Scores)
    backtest_data/run_log.jsonl              (Run-Log)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from backtest_methods import (  # noqa: E402
    M1_CitationHit,
    M2_TriggerAuthor,
    M3_CitationOrTrigger,
    M4_TopicConceptJaccard,
    M5_RefOverlapTrigger,
    M6_TfidfSimilarity,
    M7_EmbeddingSimilarity,
    M8_CombinedML,
    M9_Cascade,
    M10_ConceptVector,
    VERDICT_CLASSES,
    build_corpus_concept_profile_weighted,
    build_corpus_topic_concept_profile,
    load_corpus_texts,
    thresholds_to_predict,
)

DATA = ROOT / "backtest_data"
GOLD_PATH = DATA / "features_gold.parquet"
CONCEPT_PATH = DATA / "concept_scores_gold.json"

# pflichtlektuere (n=1) → lesenswert kollabieren, sonst zerschießt es Stratifikation
CLASS_COLLAPSE = {"pflichtlektuere": "lesenswert"}


# ─────────────────────────────── Metriken ───────────────────────────────────

def per_class_prf(y_true: pd.Series, y_pred: pd.Series) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for cls in VERDICT_CLASSES:
        tp = int(((y_pred == cls) & (y_true == cls)).sum())
        fp = int(((y_pred == cls) & (y_true != cls)).sum())
        fn = int(((y_pred != cls) & (y_true == cls)).sum())
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        out[cls] = {"precision": p, "recall": r, "f1": f1, "support": int((y_true == cls).sum())}
    return out


def macro_f1(prf: dict[str, dict[str, float]]) -> float:
    return float(np.mean([prf[c]["f1"] for c in VERDICT_CLASSES]))


def agreement(y_true: pd.Series, y_pred: pd.Series) -> float:
    return float((y_true == y_pred).mean())


def top_k_precision(scores: pd.Series, y_true: pd.Series, k_frac: float = 0.05,
                    positive_classes=("lesenswert",)) -> float:
    n = len(scores)
    k = max(1, int(round(n * k_frac)))
    top_idx = scores.nlargest(k).index
    hits = y_true.loc[top_idx].isin(positive_classes).sum()
    return float(hits / k)


def recall_agent_missed_lesenswert(df: pd.DataFrame, y_pred: pd.Series) -> dict[str, Any]:
    """Wie viele LESENSWERT, die der Agent verfehlt hat, fängt das Verfahren?"""
    missed = df[(df["user_verdict"] == "lesenswert") & (df["agent_verdict"] != "lesenswert")]
    if len(missed) == 0:
        return {"n_missed": 0, "recovered": 0, "recall": 0.0}
    rec_mask = y_pred.loc[missed.index] == "lesenswert"
    return {
        "n_missed": int(len(missed)),
        "recovered": int(rec_mask.sum()),
        "recall": float(rec_mask.mean()),
    }


# ─────────────────────────────── Threshold-Optimierung ──────────────────────

def best_thresholds_macro_f1(score: pd.Series, y_true: pd.Series,
                              n_grid: int = 25) -> tuple[float, float, float]:
    """Grid-search auf zwei Schwellen für 3-Klassen-Mapping."""
    qs = np.linspace(0.10, 0.95, n_grid)
    score_grid = np.quantile(score.values, qs)
    best = (-1.0, 0.5, 1.0)
    for i, t_scn in enumerate(score_grid):
        for t_les in score_grid[i:]:
            if t_les <= t_scn:
                t_les = t_scn + 1e-9
            y_pred = thresholds_to_predict(score, t_scn, t_les)
            prf = per_class_prf(y_true, y_pred)
            f1 = macro_f1(prf)
            if f1 > best[0]:
                best = (f1, float(t_scn), float(t_les))
    return best  # (f1, thr_scannen, thr_lesenswert)


# ─────────────────────────────── Cross-Val für M8 ───────────────────────────

def run_m8_cv(df: pd.DataFrame, y: pd.Series, feature_cols: list[str],
              n_splits: int = 5, seed: int = 42,
              add_journal_prior: bool = True,
              prior_alpha: float = 5.0,
              gold_embeddings: np.ndarray | None = None,
              knn_ks: tuple[int, ...] = (5, 10, 20)) -> dict[str, Any]:
    """5-fold StratifiedKFold mit mehreren Klassifikatoren.

    Optional: smoothed Bayesian journal-prior leak-safe per Fold injizieren
    (Smoothing-Stärke alpha = pseudo-Counts global-prior, Default 5).

    Optional: gold_embeddings (n, d) — wenn übergeben, werden pro Fold k-NN-
    Voting-Features berechnet (Anteile der k nächsten Train-Nachbarn pro Klasse,
    Mean-Top-k-Similarity) und temporär dem Train/Test-DataFrame hinzugefügt.
    Leak-safe, da nur Train-Indizes als kNN-Datenbank dienen.
    """
    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning)

    from sklearn.model_selection import StratifiedKFold
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import LabelEncoder

    # XGBoost auf macOS + libomp/torch im selben Prozess crasht silent
    # (Loop-Krasch nach Fold-Fit). LGBM deckt denselben Gradient-Boosting-Slot ab.
    has_xgb = False
    has_lgbm = False
    try:
        from lightgbm import LGBMClassifier
        has_lgbm = True
    except ImportError:
        pass

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    y_arr = y.values
    # Label-Encoder für XGB (sortiert: ignorieren=0, lesenswert=1, scannen=2)
    le = LabelEncoder().fit(VERDICT_CLASSES)
    y_enc = le.transform(y_arr)

    def make_models():
        m = {
            "LogReg": Pipeline([
                ("imp", SimpleImputer(strategy="median")),
                ("sc", StandardScaler()),
                ("clf", LogisticRegression(max_iter=3000, class_weight="balanced", C=0.5)),
            ]),
            "GBM": Pipeline([
                ("imp", SimpleImputer(strategy="median")),
                ("clf", GradientBoostingClassifier(n_estimators=300, max_depth=3,
                                                   learning_rate=0.05, random_state=seed)),
            ]),
            "RF": Pipeline([
                ("imp", SimpleImputer(strategy="median")),
                ("clf", RandomForestClassifier(n_estimators=500, max_depth=None,
                                               class_weight="balanced",
                                               random_state=seed, n_jobs=1)),
            ]),
        }
        if has_lgbm:
            m["LGBM"] = Pipeline([
                ("imp", SimpleImputer(strategy="median")),
                ("clf", LGBMClassifier(n_estimators=400, max_depth=-1, num_leaves=31,
                                       learning_rate=0.05, subsample=0.8,
                                       colsample_bytree=0.8, class_weight="balanced",
                                       random_state=seed, n_jobs=1, verbose=-1)),
            ])
        return m

    feat_view = feature_cols[:]
    if add_journal_prior and "journal_short" in df.columns:
        feat_view = feat_view + ["_journal_prior_les", "_journal_prior_scn",
                                 "_journal_prior_ign"]

    # Top-15 Journale als One-Hot
    top_journals: list[str] = []
    if "journal_short" in df.columns:
        top_journals = list(df["journal_short"].value_counts().head(15).index)
        for j in top_journals:
            col = f"_jrn_{j}"
            df[col] = (df["journal_short"] == j).astype(int)
            feat_view.append(col)

    # kNN-Voting-Features (leak-safe per Fold): n_knn_<k>_{les,scn,ign}
    # + Mean-Top-k-Similarity. Werden in jedem Fold neu berechnet.
    knn_feat_names: list[str] = []
    if gold_embeddings is not None:
        for k in knn_ks:
            for cls in ("les", "scn", "ign"):
                col = f"_knn_{k}_p_{cls}"
                df[col] = 0.0
                knn_feat_names.append(col)
            col = f"_knn_{k}_sim_mean"
            df[col] = 0.0
            knn_feat_names.append(col)
        feat_view.extend(knn_feat_names)

    results: dict[str, Any] = {}
    proba_lookup: dict[str, np.ndarray] = {}

    def smoothed_prior(y_tr: pd.Series, journals_tr: pd.Series, cls: str,
                       alpha: float) -> tuple[dict, float]:
        global_rate = float((y_tr == cls).mean())
        counts = pd.crosstab(journals_tr, y_tr == cls)
        rates = {}
        for j in counts.index:
            n = int(counts.loc[j].sum())
            k = int(counts.loc[j].get(True, 0))
            rates[j] = (k + alpha * global_rate) / (n + alpha)
        return rates, global_rate

    def compute_knn_block(tr_idx: np.ndarray, te_idx: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Berechne kNN-Features für Train- und Test-Indizes anhand der
        gold_embeddings. Train-Indizes dienen sich gegenseitig als Datenbank
        (mit Self-Exclusion)."""
        emb_tr = gold_embeddings[tr_idx]  # (n_tr, d)
        emb_te = gold_embeddings[te_idx]
        # Sim-Matrices
        sim_tr = emb_tr @ emb_tr.T   # (n_tr, n_tr)
        sim_te = emb_te @ emb_tr.T   # (n_te, n_tr)
        # Self-exclude im Train: diag -> -inf
        np.fill_diagonal(sim_tr, -np.inf)
        y_tr = y_arr[tr_idx]
        tr_data = {col: np.zeros(len(tr_idx)) for col in knn_feat_names}
        te_data = {col: np.zeros(len(te_idx)) for col in knn_feat_names}
        cls_map = {"lesenswert": "les", "scannen": "scn", "ignorieren": "ign"}
        for k in knn_ks:
            k_eff = min(k, len(tr_idx) - 1)
            # Train kNN (Top-k Nachbarn nach Sim-Wert)
            idx_tr = np.argpartition(-sim_tr, k_eff, axis=1)[:, :k_eff]
            idx_te = np.argpartition(-sim_te, k_eff, axis=1)[:, :k_eff]
            for cls, suffix in cls_map.items():
                lbl_tr = (y_tr[idx_tr] == cls).mean(axis=1)
                lbl_te = (y_tr[idx_te] == cls).mean(axis=1)
                tr_data[f"_knn_{k}_p_{suffix}"] = lbl_tr
                te_data[f"_knn_{k}_p_{suffix}"] = lbl_te
            # Mean-Top-k-Similarity
            sim_top_tr = np.take_along_axis(sim_tr, idx_tr, axis=1).mean(axis=1)
            sim_top_te = np.take_along_axis(sim_te, idx_te, axis=1).mean(axis=1)
            tr_data[f"_knn_{k}_sim_mean"] = sim_top_tr
            te_data[f"_knn_{k}_sim_mean"] = sim_top_te
        return (pd.DataFrame(tr_data, index=df.index[tr_idx]),
                pd.DataFrame(te_data, index=df.index[te_idx]))

    for name, pipe in make_models().items():
        oof_pred = pd.Series(index=df.index, dtype=object)
        oof_proba = pd.DataFrame(np.nan, index=df.index, columns=VERDICT_CLASSES, dtype=float)
        fold_scores = []
        for fold, (tr, te) in enumerate(skf.split(np.zeros(len(df)), y_arr)):
            df_tr, df_te = df.iloc[tr].copy(), df.iloc[te].copy()
            if add_journal_prior and "journal_short" in df.columns:
                jr_les, gl_les = smoothed_prior(y.iloc[tr], df_tr["journal_short"],
                                                "lesenswert", prior_alpha)
                jr_scn, gl_scn = smoothed_prior(y.iloc[tr], df_tr["journal_short"],
                                                "scannen", prior_alpha)
                jr_ign, gl_ign = smoothed_prior(y.iloc[tr], df_tr["journal_short"],
                                                "ignorieren", prior_alpha)
                df_tr["_journal_prior_les"] = df_tr["journal_short"].map(jr_les).fillna(gl_les)
                df_te["_journal_prior_les"] = df_te["journal_short"].map(jr_les).fillna(gl_les)
                df_tr["_journal_prior_scn"] = df_tr["journal_short"].map(jr_scn).fillna(gl_scn)
                df_te["_journal_prior_scn"] = df_te["journal_short"].map(jr_scn).fillna(gl_scn)
                df_tr["_journal_prior_ign"] = df_tr["journal_short"].map(jr_ign).fillna(gl_ign)
                df_te["_journal_prior_ign"] = df_te["journal_short"].map(jr_ign).fillna(gl_ign)
            if gold_embeddings is not None and knn_feat_names:
                knn_tr, knn_te = compute_knn_block(tr, te)
                for c in knn_feat_names:
                    df_tr[c] = knn_tr[c].values
                    df_te[c] = knn_te[c].values
            X_tr = df_tr[feat_view].astype(float).values
            X_te = df_te[feat_view].astype(float).values
            try:
                pipe.fit(X_tr, y_arr[tr])
            except Exception as e:
                print(f"  {name} fit error fold {fold}: {e}")
                continue
            yp = pipe.predict(X_te)
            oof_pred.iloc[te] = yp
            try:
                classes = list(pipe.classes_)
            except AttributeError:
                classes = list(pipe.named_steps["clf"].classes_)
            proba = pipe.predict_proba(X_te)
            for i, cls in enumerate(classes):
                if cls in VERDICT_CLASSES:
                    oof_proba.iloc[te, oof_proba.columns.get_loc(cls)] = proba[:, i]
            prf = per_class_prf(pd.Series(y_arr[te]), pd.Series(yp))
            fold_scores.append(macro_f1(prf))
        prf = per_class_prf(y, oof_pred)
        proba_lookup[name] = oof_proba.values
        results[name] = {
            "oof_pred": oof_pred,
            "oof_score_les": oof_proba["lesenswert"],
            "oof_score_scn": oof_proba["scannen"],
            "oof_score_ign": oof_proba["ignorieren"],
            "macro_f1": macro_f1(prf),
            "agreement": agreement(y, oof_pred),
            "prf": prf,
            "fold_macro_f1_mean": float(np.mean(fold_scores)) if fold_scores else 0.0,
            "fold_macro_f1_std": float(np.std(fold_scores)) if fold_scores else 0.0,
        }

    # ──── XGB getrennt (braucht encoded labels) ────
    if has_xgb:
        try:
            from xgboost import XGBClassifier
        except ImportError:
            pass
        else:
            pipe = Pipeline([
                ("imp", SimpleImputer(strategy="median")),
                ("clf", XGBClassifier(n_estimators=400, max_depth=4, learning_rate=0.05,
                                      subsample=0.8, colsample_bytree=0.8,
                                      random_state=seed, n_jobs=1, eval_metric="mlogloss")),
            ])
            oof_pred = pd.Series(index=df.index, dtype=object)
            oof_proba = pd.DataFrame(np.nan, index=df.index, columns=VERDICT_CLASSES, dtype=float)
            fold_scores = []
            for fold, (tr, te) in enumerate(skf.split(np.zeros(len(df)), y_enc)):
                df_tr, df_te = df.iloc[tr].copy(), df.iloc[te].copy()
                if add_journal_prior and "journal_short" in df.columns:
                    jr_les, gl_les = smoothed_prior(y.iloc[tr], df_tr["journal_short"],
                                                    "lesenswert", prior_alpha)
                    jr_scn, gl_scn = smoothed_prior(y.iloc[tr], df_tr["journal_short"],
                                                    "scannen", prior_alpha)
                    jr_ign, gl_ign = smoothed_prior(y.iloc[tr], df_tr["journal_short"],
                                                    "ignorieren", prior_alpha)
                    df_tr["_journal_prior_les"] = df_tr["journal_short"].map(jr_les).fillna(gl_les)
                    df_te["_journal_prior_les"] = df_te["journal_short"].map(jr_les).fillna(gl_les)
                    df_tr["_journal_prior_scn"] = df_tr["journal_short"].map(jr_scn).fillna(gl_scn)
                    df_te["_journal_prior_scn"] = df_te["journal_short"].map(jr_scn).fillna(gl_scn)
                    df_tr["_journal_prior_ign"] = df_tr["journal_short"].map(jr_ign).fillna(gl_ign)
                    df_te["_journal_prior_ign"] = df_te["journal_short"].map(jr_ign).fillna(gl_ign)
                X_tr = df_tr[feat_view].astype(float).values
                X_te = df_te[feat_view].astype(float).values
                pipe.fit(X_tr, y_enc[tr])
                yp_enc = pipe.predict(X_te)
                yp = le.inverse_transform(yp_enc)
                oof_pred.iloc[te] = yp
                proba = pipe.predict_proba(X_te)
                for i, cls in enumerate(le.classes_):
                    if cls in VERDICT_CLASSES:
                        oof_proba.iloc[te, oof_proba.columns.get_loc(cls)] = proba[:, i]
                prf = per_class_prf(pd.Series(y_arr[te]), pd.Series(yp))
                fold_scores.append(macro_f1(prf))
            prf = per_class_prf(y, oof_pred)
            proba_lookup["XGB"] = oof_proba.values
            results["XGB"] = {
                "oof_pred": oof_pred,
                "oof_score_les": oof_proba["lesenswert"],
                "oof_score_scn": oof_proba["scannen"],
                "oof_score_ign": oof_proba["ignorieren"],
                "macro_f1": macro_f1(prf),
                "agreement": agreement(y, oof_pred),
                "prf": prf,
                "fold_macro_f1_mean": float(np.mean(fold_scores)) if fold_scores else 0.0,
                "fold_macro_f1_std": float(np.std(fold_scores)) if fold_scores else 0.0,
            }

    # ───── Soft-Vote Ensemble über alle Models ─────
    if len(proba_lookup) >= 2:
        # mittlere Proba über Modelle
        proba_stack = np.nanmean(np.stack(list(proba_lookup.values()), axis=0), axis=0)
        proba_df = pd.DataFrame(proba_stack, index=df.index, columns=VERDICT_CLASSES)
        ens_pred = pd.Series(proba_df.idxmax(axis=1), index=df.index)
        prf = per_class_prf(y, ens_pred)
        results["Ensemble"] = {
            "oof_pred": ens_pred,
            "oof_score_les": proba_df["lesenswert"],
            "oof_score_scn": proba_df["scannen"],
            "oof_score_ign": proba_df["ignorieren"],
            "macro_f1": macro_f1(prf),
            "agreement": agreement(y, ens_pred),
            "prf": prf,
            "fold_macro_f1_mean": 0.0,
            "fold_macro_f1_std": 0.0,
        }
    return results


def optimize_proba_thresholds(proba_les: pd.Series, proba_scn: pd.Series,
                               proba_ign: pd.Series, y_true: pd.Series,
                               n_grid: int = 25) -> tuple[float, dict[str, float]]:
    """Suche optimale Schwellen auf Probabilities für 3-Klassen-Mapping.
    Maximiere macro-F1. Regel:
       if proba_les ≥ t_les → lesenswert
       elif proba_ign ≥ t_ign → ignorieren
       else → scannen
    """
    t_les_grid = np.linspace(0.20, 0.70, n_grid)
    t_ign_grid = np.linspace(0.20, 0.80, n_grid)
    best = (-1.0, {"t_les": 0.5, "t_ign": 0.5})
    for tl in t_les_grid:
        for ti in t_ign_grid:
            yp = pd.Series(["scannen"] * len(y_true), index=y_true.index)
            yp[proba_ign >= ti] = "ignorieren"
            yp[proba_les >= tl] = "lesenswert"
            prf = per_class_prf(y_true, yp)
            f1 = macro_f1(prf)
            if f1 > best[0]:
                best = (f1, {"t_les": float(tl), "t_ign": float(ti)})
    return best


def per_journal_thresholds_with_shrinkage(
    proba_les: pd.Series, proba_scn: pd.Series, proba_ign: pd.Series,
    y_true: pd.Series, journals: pd.Series,
    global_thr: dict[str, float],
    top_n: int = 15, shrink_n: float = 30.0,
    n_grid: int = 15,
) -> tuple[pd.Series, dict[str, dict], dict[str, float]]:
    """Per-Top-N-Journal Threshold-Tuning mit Shrinkage zur globalen Schwelle.

    Methodischer Hinweis: Die lokalen Schwellen werden auf denselben OOF-Probas
    optimiert wie evaluiert (leichtes Optimismus-Bias). Shrinkage zur globalen
    Schwelle mit w = min(1, n_journal / shrink_n) hält die per-Journal-Korrektur
    konservativ — bei n=15 und shrink_n=30 ist w=0.5 (50/50 lokal/global).

    Returns:
        yp: Series mit per-Journal-Schwelle erzeugte Predictions
        journal_thr: dict[journal -> {'t_les', 't_ign', 'n', 'w', 't_les_local', 't_ign_local'}]
        diagnostics: {'top_n': int, 'shrink_n': float}
    """
    top_journals = list(journals.value_counts().head(top_n).index)
    journal_thr: dict[str, dict] = {}
    t_les_grid = np.linspace(0.20, 0.70, n_grid)
    t_ign_grid = np.linspace(0.20, 0.80, n_grid)

    for j in top_journals:
        mask = journals == j
        n_j = int(mask.sum())
        if n_j < 4:
            continue
        sub_les = proba_les[mask]
        sub_ign = proba_ign[mask]
        sub_y = y_true[mask]
        best_local = (-1.0, global_thr["t_les"], global_thr["t_ign"])
        for tl in t_les_grid:
            for ti in t_ign_grid:
                yp = pd.Series(["scannen"] * n_j, index=sub_y.index)
                yp[sub_ign >= ti] = "ignorieren"
                yp[sub_les >= tl] = "lesenswert"
                prf = per_class_prf(sub_y, yp)
                f1 = macro_f1(prf)
                if f1 > best_local[0]:
                    best_local = (f1, float(tl), float(ti))
        w = min(1.0, n_j / shrink_n)
        t_les_eff = (1 - w) * global_thr["t_les"] + w * best_local[1]
        t_ign_eff = (1 - w) * global_thr["t_ign"] + w * best_local[2]
        journal_thr[j] = {
            "t_les": float(t_les_eff), "t_ign": float(t_ign_eff),
            "n": n_j, "w": float(w),
            "t_les_local": float(best_local[1]),
            "t_ign_local": float(best_local[2]),
        }

    yp_full = pd.Series(["scannen"] * len(y_true), index=y_true.index)
    for j in journals.unique():
        mask = journals == j
        if j in journal_thr:
            t_les = journal_thr[j]["t_les"]
            t_ign = journal_thr[j]["t_ign"]
        else:
            t_les = global_thr["t_les"]
            t_ign = global_thr["t_ign"]
        sub_les = proba_les[mask]
        sub_ign = proba_ign[mask]
        sub_yp = pd.Series(["scannen"] * int(mask.sum()), index=sub_les.index)
        sub_yp[sub_ign >= t_ign] = "ignorieren"
        sub_yp[sub_les >= t_les] = "lesenswert"
        yp_full[mask] = sub_yp
    return yp_full, journal_thr, {"top_n": top_n, "shrink_n": shrink_n}


def per_journal_thresholds_cv_validated(
    proba_les: pd.Series, proba_scn: pd.Series, proba_ign: pd.Series,
    y_true: pd.Series, journals: pd.Series,
    n_splits: int = 5, seed: int = 42,
    top_n: int = 15, shrink_n: float = 30.0,
) -> tuple[pd.Series, dict[str, Any]]:
    """Per-Fold-CV-validierte Per-Journal-Threshold-Tuning.

    Zweite Stufe nach M8-OOF: Auf den bereits OOF-Probas läuft NOCHMAL eine
    5-fold StratifiedKFold. In jedem Fold:
      1. Tune globale Schwelle nur auf Train-OOF-Probas
      2. Tune per-Journal-Schwellen nur auf Train-OOF-Probas (mit Shrinkage)
      3. Wende auf Test-OOF-Probas an

    So sind Schwellen-Tuning und Evaluation strikt getrennt → kein Optimismus-Bias.
    Modell-Fits werden NICHT wiederholt (nur Threshold-Tuning auf Probas).
    """
    from sklearn.model_selection import StratifiedKFold
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    y_arr = y_true.values
    yp_full = pd.Series(["scannen"] * len(y_true), index=y_true.index)
    fold_diags: list[dict[str, Any]] = []

    for fold, (tr, te) in enumerate(skf.split(np.zeros(len(y_arr)), y_arr)):
        # Step 1: Globale Schwelle nur auf Train-OOF-Probas tunen
        f1_g, thr_g = optimize_proba_thresholds(
            proba_les.iloc[tr], proba_scn.iloc[tr], proba_ign.iloc[tr],
            y_true.iloc[tr]
        )
        # Step 2: Per-Journal-Schwellen nur auf Train-OOF-Probas tunen
        _, journal_thr, _ = per_journal_thresholds_with_shrinkage(
            proba_les.iloc[tr], proba_scn.iloc[tr], proba_ign.iloc[tr],
            y_true.iloc[tr], journals.iloc[tr],
            global_thr=thr_g, top_n=top_n, shrink_n=shrink_n
        )
        # Step 3: Anwenden auf Test-OOF-Probas
        te_idx = y_true.index[te]
        te_journals = journals.iloc[te]
        for j in te_journals.unique():
            sub_mask_local = (te_journals == j)
            sub_idx = te_idx[sub_mask_local.values]
            if j in journal_thr:
                t_les = journal_thr[j]["t_les"]
                t_ign = journal_thr[j]["t_ign"]
            else:
                t_les = thr_g["t_les"]
                t_ign = thr_g["t_ign"]
            sub_les = proba_les.loc[sub_idx]
            sub_ign = proba_ign.loc[sub_idx]
            sub_yp = pd.Series(["scannen"] * len(sub_idx), index=sub_idx)
            sub_yp[sub_ign >= t_ign] = "ignorieren"
            sub_yp[sub_les >= t_les] = "lesenswert"
            yp_full.loc[sub_idx] = sub_yp
        fold_diags.append({
            "fold": fold, "global_thr": thr_g,
            "n_journal_thr": len(journal_thr),
        })

    return yp_full, {
        "n_splits": n_splits, "top_n": top_n, "shrink_n": shrink_n,
        "fold_diags": fold_diags,
    }


def single_journal_bias_adjust_cv(
    proba_les: pd.Series, proba_scn: pd.Series, proba_ign: pd.Series,
    y_true: pd.Series, journals: pd.Series,
    target_journal: str,
    n_splits: int = 5, seed: int = 42,
) -> tuple[pd.Series, dict[str, Any]]:
    """Per-Fold ein-Parameter-Bias-Adjustment für genau ein Ziel-Journal.

    Konservativste Variante von Per-Journal-Threshold: statt 30 individuell getuneter
    Schwellen nur EINE Verschiebung von t_les nach (rate_overall - rate_target) skaliert
    durch ein im Fold getuneten alpha-Parameter, angewendet nur auf target_journal.

    Per Fold:
      1. Globale Schwelle auf Train-OOF tunen → t_les_g, t_ign_g
      2. Wähle alpha ∈ {-0.2, -0.1, 0.0, +0.1, +0.2} auf Train-OOF (Grid-Search nach macro-F1)
      3. Anwenden: für target_journal_test: t_les_eff = t_les_g + alpha
                   andere Journals: globale Schwelle
    """
    from sklearn.model_selection import StratifiedKFold
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    y_arr = y_true.values
    yp_full = pd.Series(["scannen"] * len(y_true), index=y_true.index)
    fold_diags: list[dict[str, Any]] = []
    alpha_grid = np.linspace(-0.30, 0.30, 13)

    for fold, (tr, te) in enumerate(skf.split(np.zeros(len(y_arr)), y_arr)):
        f1_g, thr_g = optimize_proba_thresholds(
            proba_les.iloc[tr], proba_scn.iloc[tr], proba_ign.iloc[tr],
            y_true.iloc[tr]
        )
        tr_idx = y_true.index[tr]
        tr_journals = journals.iloc[tr]
        tr_mask_target = (tr_journals == target_journal)
        # Tune alpha auf Train
        best_alpha = (-1.0, 0.0)
        for alpha in alpha_grid:
            yp = pd.Series(["scannen"] * len(tr), index=tr_idx)
            sub_les_tr = proba_les.iloc[tr]
            sub_ign_tr = proba_ign.iloc[tr]
            # Default: global thresholds
            yp[sub_ign_tr.values >= thr_g["t_ign"]] = "ignorieren"
            yp[sub_les_tr.values >= thr_g["t_les"]] = "lesenswert"
            # Override für target_journal: shifted t_les
            if tr_mask_target.any():
                t_les_t = thr_g["t_les"] + alpha
                target_idx_tr = tr_idx[tr_mask_target.values]
                sub_les_t = proba_les.loc[target_idx_tr]
                sub_ign_t = proba_ign.loc[target_idx_tr]
                sub_yp_t = pd.Series(["scannen"] * len(target_idx_tr),
                                     index=target_idx_tr)
                sub_yp_t[sub_ign_t >= thr_g["t_ign"]] = "ignorieren"
                sub_yp_t[sub_les_t >= t_les_t] = "lesenswert"
                yp.loc[target_idx_tr] = sub_yp_t
            prf = per_class_prf(y_true.iloc[tr], yp)
            f1 = macro_f1(prf)
            if f1 > best_alpha[0]:
                best_alpha = (f1, float(alpha))
        alpha_opt = best_alpha[1]
        # Apply to test
        te_idx = y_true.index[te]
        te_journals = journals.iloc[te]
        te_mask_target = (te_journals == target_journal)
        sub_les_te = proba_les.iloc[te]
        sub_ign_te = proba_ign.iloc[te]
        sub_yp_te = pd.Series(["scannen"] * len(te), index=te_idx)
        sub_yp_te[sub_ign_te.values >= thr_g["t_ign"]] = "ignorieren"
        sub_yp_te[sub_les_te.values >= thr_g["t_les"]] = "lesenswert"
        if te_mask_target.any():
            t_les_t = thr_g["t_les"] + alpha_opt
            target_idx_te = te_idx[te_mask_target.values]
            sub_les_t = proba_les.loc[target_idx_te]
            sub_ign_t = proba_ign.loc[target_idx_te]
            sub_yp_t = pd.Series(["scannen"] * len(target_idx_te),
                                 index=target_idx_te)
            sub_yp_t[sub_ign_t >= thr_g["t_ign"]] = "ignorieren"
            sub_yp_t[sub_les_t >= t_les_t] = "lesenswert"
            sub_yp_te.loc[target_idx_te] = sub_yp_t
        yp_full.loc[te_idx] = sub_yp_te
        fold_diags.append({
            "fold": fold, "global_thr": thr_g, "alpha_opt": alpha_opt,
            "n_target_tr": int(tr_mask_target.sum()),
            "n_target_te": int(te_mask_target.sum()),
        })
    return yp_full, {
        "n_splits": n_splits, "target_journal": target_journal,
        "fold_diags": fold_diags,
    }


# ─────────────────────────────── Reporting ──────────────────────────────────

def format_method_block(name: str, agreement_val: float, prf: dict[str, dict[str, float]],
                        macro: float, top5: float, missed_info: dict[str, Any],
                        extra: dict[str, Any] | None = None) -> str:
    lines = [f"### {name}", ""]
    if extra and "fitted_thresholds" in extra:
        t = extra["fitted_thresholds"]
        lines.append(f"_Tuned thresholds: scannen ≥ {t[0]:.3f}, lesenswert ≥ {t[1]:.3f}_")
        lines.append("")
    lines += [
        f"- **Agreement vs. User**: {100*agreement_val:.1f}%",
        f"- **Macro-F1** (3 Klassen): {macro:.3f}",
        f"- **Top-5%-Precision (LESENSWERT)**: {100*top5:.1f}%",
        f"- **Recall der 28 vom Agent verpassten LESENSWERT**: "
        f"{missed_info['recovered']}/{missed_info['n_missed']} = "
        f"{100*missed_info['recall']:.1f}%",
        "",
        "| Klasse | P | R | F1 | n |",
        "|---|---:|---:|---:|---:|",
    ]
    for cls in VERDICT_CLASSES:
        m = prf[cls]
        lines.append(f"| {cls} | {m['precision']:.3f} | {m['recall']:.3f} | "
                     f"{m['f1']:.3f} | {m['support']} |")
    lines.append("")
    if extra and "extra_notes" in extra:
        lines.extend(extra["extra_notes"])
        lines.append("")
    return "\n".join(lines)


def confusion_md(y_true: pd.Series, y_pred: pd.Series) -> str:
    ct = pd.crosstab(y_pred, y_true, margins=True, dropna=False)
    return ct.to_markdown()


# ─────────────────────────────── Main ───────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true",
                        help="Skip M7 (Embeddings) für schnellen Lauf")
    parser.add_argument("--embedding-model", default="BAAI/bge-m3",
                        help="sentence-transformers Model-Name (Default: BGE-M3)")
    parser.add_argument("--report-out", default=str(ROOT / "docs" / "backtest_algorithmic_v1.md"))
    parser.add_argument("--predictions-out", default=str(DATA / "predictions.parquet"))
    parser.add_argument("--log-out", default=str(DATA / "run_log.jsonl"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    t0 = time.time()
    df = pd.read_parquet(GOLD_PATH)
    # Class collapse
    df["user_verdict_orig"] = df["user_verdict"]
    df["user_verdict"] = df["user_verdict"].replace(CLASS_COLLAPSE)
    df["agent_verdict"] = df["agent_verdict"].replace(CLASS_COLLAPSE)
    y_true = df["user_verdict"]

    print(f"Loaded gold: {len(df)} articles")
    print(f"Class distribution (after collapse): {y_true.value_counts().to_dict()}")

    # Agent baseline
    agent_pred = df["agent_verdict"]
    agent_agree = agreement(y_true, agent_pred)
    agent_prf = per_class_prf(y_true, agent_pred)
    agent_macro = macro_f1(agent_prf)
    print(f"\nAgent baseline: agreement={100*agent_agree:.1f}% macro-F1={agent_macro:.3f}")

    # Korpus-Profile bauen
    corpus_topics, corpus_concepts = build_corpus_topic_concept_profile(df)
    print(f"Corpus topic profile: {len(corpus_topics)} topics, {len(corpus_concepts)} concepts")

    corpus_texts, authored_idx = load_corpus_texts(return_authored_idx=True)
    print(f"Corpus texts (non-LLM only): {len(corpus_texts)} docs, "
          f"{sum(len(t) for t in corpus_texts):,} chars "
          f"({len(authored_idx)} authored, {len(corpus_texts)-len(authored_idx)} projects)")

    predictions_store: dict[str, pd.Series] = {"agent": agent_pred, "true": y_true}
    scores_store: dict[str, pd.Series] = {}
    results: dict[str, dict[str, Any]] = {}

    # ─── M1–M5 (rule-based / bibliometric) ─────────────────────────────────
    rule_methods: list = [
        M1_CitationHit(),
        M2_TriggerAuthor(),
        M3_CitationOrTrigger(),
        M4_TopicConceptJaccard(corpus_topics, corpus_concepts),
        M5_RefOverlapTrigger(),
    ]

    # ─── M6 TF-IDF ────────────────────────────────────────────────────────
    print("\nFitting M6 (TF-IDF)…")
    rule_methods.append(M6_TfidfSimilarity(corpus_texts))

    # ─── M7 Embeddings (optional skip) ────────────────────────────────────
    m7_instance = None
    if not args.quick:
        model_name = args.embedding_model
        print(f"Fitting M7 (Embeddings — {model_name})…")
        m7_instance = M7_EmbeddingSimilarity(corpus_texts, model_name=model_name,
                                              authored_idx=authored_idx)
        if m7_instance.cluster_centroids is not None:
            sizes = m7_instance.cluster_sizes.tolist()
            print(f"  Verortungs-Cluster K-Means(k={m7_instance.n_clusters}) auf "
                  f"{len(authored_idx)} authored Embeddings: Größen {sizes}",
                  flush=True)
        rule_methods.append(m7_instance)
    else:
        print("Skipping M7 (--quick)")

    # ─── M10 Concept-Vector (wenn concept_scores_gold.json existiert) ─────
    m10_instance = None
    if CONCEPT_PATH.exists():
        concept_lookup = json.loads(CONCEPT_PATH.read_text())
        # Korpus-Concept-Profil aus Trigger-/Citation-Nachbarschaft im Gold-Set
        nbhd_ids = df[(df["f_trigger_author_match"] == 1) |
                      (df["f_citation_hit_count"] >= 1)]["id"].tolist()
        concept_profile = build_corpus_concept_profile_weighted(concept_lookup, nbhd_ids)
        print(f"M10 Concept-Profile: {len(concept_profile)} weighted concepts "
              f"aus {len(nbhd_ids)} Nachbarschafts-Artikeln")
        m10_instance = M10_ConceptVector(concept_lookup, concept_profile)
        rule_methods.append(m10_instance)
    else:
        print(f"Skipping M10 (kein {CONCEPT_PATH.name})")

    for m in rule_methods:
        t_m = time.time()
        score = m.score(df)
        scores_store[m.name] = score
        # Threshold-Tuning auf 5-fold StratifiedKFold-OOF, dann finale Schwellen auf
        # Gesamtdaten anwenden (für M2 binär: kein Tuning sinnvoll).
        if m.name == "M2_TriggerAuthor":
            y_pred = m.predict(df)
            fitted = (0.5, 0.5)
        else:
            f1, t_scn, t_les = best_thresholds_macro_f1(score, y_true)
            y_pred = thresholds_to_predict(score, t_scn, t_les)
            fitted = (t_scn, t_les)
        predictions_store[m.name] = y_pred
        prf = per_class_prf(y_true, y_pred)
        results[m.name] = {
            "agreement": agreement(y_true, y_pred),
            "macro_f1": macro_f1(prf),
            "prf": prf,
            "top5_precision": top_k_precision(score, y_true),
            "missed": recall_agent_missed_lesenswert(df, y_pred),
            "fitted_thresholds": fitted,
            "fit_seconds": time.time() - t_m,
        }
        print(f"  {m.name}: agree={100*results[m.name]['agreement']:.1f}% "
              f"macroF1={results[m.name]['macro_f1']:.3f} "
              f"({results[m.name]['fit_seconds']:.1f}s)")

    # ─── M8: Combined ML mit Cross-Val ────────────────────────────────────
    print("\nFitting M8 (Combined ML, 5-fold CV)…")
    # Feature set: alle f_* + M4-M7-Scores + abstract_len/has_abstract/year
    base_feats = [c for c in df.columns if c.startswith("f_")]
    for extra in ["abstract_len", "has_abstract", "year"]:
        if extra in df.columns and extra not in base_feats:
            base_feats.append(extra)
    df_with_scores = df.copy()
    for nm, s in scores_store.items():
        col = f"score_{nm}"
        df_with_scores[col] = s
        base_feats.append(col)
    # M7 embedding-Multi-Statistik-Features
    if m7_instance is not None:
        emb_feats = m7_instance.compute_embedding_features(df)
        for c in emb_feats.columns:
            df_with_scores[c] = emb_feats[c].values
            base_feats.append(c)
        print(f"  + {len(emb_feats.columns)} embedding multi-stat features", flush=True)

    # M10 Concept-Vector-Features (4 stats)
    if m10_instance is not None:
        c_feats = m10_instance.compute_features(df)
        for c in c_feats.columns:
            df_with_scores[c] = c_feats[c].values
            base_feats.append(c)
        print(f"  + {len(c_feats.columns)} concept-vector features", flush=True)
        # BGE-M3 frei machen (1+ GB), bevor sklearn-Parallel-Worker starten
        if m7_instance is not None and getattr(m7_instance, "model", None) is not None:
            del m7_instance.model
            m7_instance.model = None
        import gc
        gc.collect()
        try:
            import torch
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except Exception:
            pass

    # Gold-Embeddings für kNN-Voting (Iteration 5) — nutzt Cache nach BGE-M3-Freigabe
    gold_emb = None
    if m7_instance is not None:
        gold_emb = m7_instance.get_article_embeddings(df)
        if gold_emb is not None:
            print(f"  + kNN-Voting per Fold mit BGE-M3-Gold-Embeddings "
                  f"({gold_emb.shape[0]} × {gold_emb.shape[1]}), k∈(5,10,20)", flush=True)

    m8_results = run_m8_cv(df_with_scores, y_true, base_feats,
                           n_splits=5, seed=args.seed, add_journal_prior=True,
                           gold_embeddings=gold_emb)
    best_m8_key = None
    best_m8_f1 = -1.0
    for nm, info in m8_results.items():
        key = f"M8_{nm}"
        predictions_store[key] = info["oof_pred"]
        if not info["oof_score_les"].isna().all():
            scores_store[key] = info["oof_score_les"]
            top5 = top_k_precision(info["oof_score_les"], y_true)
        else:
            top5 = float("nan")
        results[key] = {
            "agreement": info["agreement"],
            "macro_f1": info["macro_f1"],
            "prf": info["prf"],
            "top5_precision": top5,
            "missed": recall_agent_missed_lesenswert(df, info["oof_pred"]),
            "fold_macro_f1_mean": info["fold_macro_f1_mean"],
            "fold_macro_f1_std": info["fold_macro_f1_std"],
            "feature_count": len(base_feats),
        }
        print(f"  {key}: agree={100*info['agreement']:.1f}% "
              f"macroF1={info['macro_f1']:.3f} "
              f"(fold mean {info['fold_macro_f1_mean']:.3f} ± "
              f"{info['fold_macro_f1_std']:.3f})", flush=True)
        if info["macro_f1"] > best_m8_f1:
            best_m8_f1 = info["macro_f1"]
            best_m8_key = nm

    # ─── M8b: Threshold-Tuning auf Probabilities des besten M8 ────────────
    if best_m8_key:
        best_info = m8_results[best_m8_key]
        f1_opt, thr = optimize_proba_thresholds(
            best_info["oof_score_les"],
            best_info["oof_score_scn"],
            best_info["oof_score_ign"],
            y_true,
        )
        yp = pd.Series(["scannen"] * len(y_true), index=y_true.index)
        yp[best_info["oof_score_ign"] >= thr["t_ign"]] = "ignorieren"
        yp[best_info["oof_score_les"] >= thr["t_les"]] = "lesenswert"
        key = f"M8_{best_m8_key}_TunedProba"
        predictions_store[key] = yp
        scores_store[key] = best_info["oof_score_les"]
        prf = per_class_prf(y_true, yp)
        results[key] = {
            "agreement": agreement(y_true, yp),
            "macro_f1": macro_f1(prf),
            "prf": prf,
            "top5_precision": top_k_precision(best_info["oof_score_les"], y_true),
            "missed": recall_agent_missed_lesenswert(df, yp),
            "tuned_thresholds": thr,
        }
        print(f"  {key}: agree={100*results[key]['agreement']:.1f}% "
              f"macroF1={results[key]['macro_f1']:.3f} "
              f"(t_les={thr['t_les']:.2f}, t_ign={thr['t_ign']:.2f})")

        # ─── M8c: Per-Top-15-Journal-Threshold mit Shrinkage (Iter 7) ──────
        if "journal_short" in df.columns:
            yp_pj, journal_thr_map, pj_diag = per_journal_thresholds_with_shrinkage(
                best_info["oof_score_les"],
                best_info["oof_score_scn"],
                best_info["oof_score_ign"],
                y_true,
                df["journal_short"],
                global_thr=thr,
                top_n=15, shrink_n=30.0,
            )
            key_pj = f"M8_{best_m8_key}_TunedProba_PerJournal"
            predictions_store[key_pj] = yp_pj
            scores_store[key_pj] = best_info["oof_score_les"]
            prf_pj = per_class_prf(y_true, yp_pj)
            results[key_pj] = {
                "agreement": agreement(y_true, yp_pj),
                "macro_f1": macro_f1(prf_pj),
                "prf": prf_pj,
                "top5_precision": top_k_precision(best_info["oof_score_les"], y_true),
                "missed": recall_agent_missed_lesenswert(df, yp_pj),
                "tuned_thresholds": {"global": thr, "per_journal": journal_thr_map,
                                     **pj_diag},
            }
            print(f"  {key_pj}: agree={100*results[key_pj]['agreement']:.1f}% "
                  f"macroF1={results[key_pj]['macro_f1']:.3f} "
                  f"(top_n={pj_diag['top_n']}, shrink_n={pj_diag['shrink_n']:.0f}, "
                  f"{len(journal_thr_map)} per-journal Schwellen tuned)")

            # ─── M8d: CV-validierte Per-Journal-Variante (Iter 8) ──────────
            yp_pj_cv, pj_cv_diag = per_journal_thresholds_cv_validated(
                best_info["oof_score_les"],
                best_info["oof_score_scn"],
                best_info["oof_score_ign"],
                y_true,
                df["journal_short"],
                n_splits=5, seed=args.seed, top_n=15, shrink_n=30.0,
            )
            key_pj_cv = f"M8_{best_m8_key}_TunedProba_PerJournalCV"
            predictions_store[key_pj_cv] = yp_pj_cv
            scores_store[key_pj_cv] = best_info["oof_score_les"]
            prf_pj_cv = per_class_prf(y_true, yp_pj_cv)
            results[key_pj_cv] = {
                "agreement": agreement(y_true, yp_pj_cv),
                "macro_f1": macro_f1(prf_pj_cv),
                "prf": prf_pj_cv,
                "top5_precision": top_k_precision(best_info["oof_score_les"], y_true),
                "missed": recall_agent_missed_lesenswert(df, yp_pj_cv),
                "tuned_thresholds": pj_cv_diag,
            }
            print(f"  {key_pj_cv}: agree={100*results[key_pj_cv]['agreement']:.1f}% "
                  f"macroF1={results[key_pj_cv]['macro_f1']:.3f} "
                  f"(nested CV {pj_cv_diag['n_splits']}-fold, "
                  f"shrink_n={pj_cv_diag['shrink_n']:.0f})")

            # ─── M8e: AIandSoc-only Bias-Adjust, CV-validiert (Iter 9) ─────
            if "AIandSoc" in df["journal_short"].values:
                yp_aia, aia_diag = single_journal_bias_adjust_cv(
                    best_info["oof_score_les"],
                    best_info["oof_score_scn"],
                    best_info["oof_score_ign"],
                    y_true, df["journal_short"],
                    target_journal="AIandSoc",
                    n_splits=5, seed=args.seed,
                )
                key_aia = f"M8_{best_m8_key}_TunedProba_AIandSocAdjust"
                predictions_store[key_aia] = yp_aia
                scores_store[key_aia] = best_info["oof_score_les"]
                prf_aia = per_class_prf(y_true, yp_aia)
                results[key_aia] = {
                    "agreement": agreement(y_true, yp_aia),
                    "macro_f1": macro_f1(prf_aia),
                    "prf": prf_aia,
                    "top5_precision": top_k_precision(best_info["oof_score_les"], y_true),
                    "missed": recall_agent_missed_lesenswert(df, yp_aia),
                    "tuned_thresholds": aia_diag,
                }
                alphas = [fd["alpha_opt"] for fd in aia_diag["fold_diags"]]
                print(f"  {key_aia}: agree={100*results[key_aia]['agreement']:.1f}% "
                      f"macroF1={results[key_aia]['macro_f1']:.3f} "
                      f"(α per Fold: {['%+.2f' % a for a in alphas]})")

    # ─── M9: Cascade über bestem M8 + Veto-Regeln ─────────────────────────
    if best_m8_key:
        print(f"\nFitting M9 Cascade über M8_{best_m8_key}…")
        # Score-Lookup für Veto-Down: M4, M5, M6, M7 (was vorhanden ist)
        veto_scores = {
            nm: s for nm, s in scores_store.items()
            if nm in ["M4_TopicConceptJaccard", "M5_RefOverlapTrigger",
                      "M6_TfidfSimilarity", "M7_EmbeddingSimilarity"]
        }
        best_info = m8_results[best_m8_key]
        # Cascade-Grid: cit_thr × coauthor_thr × veto_down_quantile (None erlaubt)
        best_cascade = (-1.0, None, None)
        for cit in [1, 2]:
            for use_trg in [True, False]:
                for ca in [None, 1, 2]:
                    for vq in [None, 0.05, 0.10, 0.20]:
                        casc = M9_Cascade(veto_scores, best_info["oof_pred"],
                                          best_info["oof_score_les"],
                                          cit_thr=cit, use_trigger=use_trg,
                                          coauthor_thr=ca, veto_down_quantile=vq)
                        yp = casc.predict(df)
                        prf = per_class_prf(y_true, yp)
                        f1 = macro_f1(prf)
                        if f1 > best_cascade[0]:
                            best_cascade = (f1, yp, {
                                "cit_thr": cit, "use_trigger": use_trg,
                                "coauthor_thr": ca, "veto_down_q": vq,
                            })
        if best_cascade[1] is not None:
            yp = best_cascade[1]
            predictions_store["M9_Cascade"] = yp
            scores_store["M9_Cascade"] = best_info["oof_score_les"]
            prf = per_class_prf(y_true, yp)
            results["M9_Cascade"] = {
                "agreement": agreement(y_true, yp),
                "macro_f1": macro_f1(prf),
                "prf": prf,
                "top5_precision": top_k_precision(best_info["oof_score_les"], y_true),
                "missed": recall_agent_missed_lesenswert(df, yp),
                "tuned_thresholds": best_cascade[2],
            }
            print(f"  M9_Cascade: agree={100*results['M9_Cascade']['agreement']:.1f}% "
                  f"macroF1={results['M9_Cascade']['macro_f1']:.3f} "
                  f"(over M8_{best_m8_key}, settings={best_cascade[2]})")

        # Auch: Cascade über M8_LogReg_TunedProba (oft besser als raw best_m8)
        if f"M8_{best_m8_key}_TunedProba" in predictions_store:
            tp_pred = predictions_store[f"M8_{best_m8_key}_TunedProba"]
            best_cascade2 = (-1.0, None, None)
            for cit in [1, 2]:
                for use_trg in [True, False]:
                    for ca in [None, 1, 2]:
                        for vq in [None, 0.05, 0.10, 0.20]:
                            casc = M9_Cascade(veto_scores, tp_pred,
                                              best_info["oof_score_les"],
                                              cit_thr=cit, use_trigger=use_trg,
                                              coauthor_thr=ca, veto_down_quantile=vq)
                            yp = casc.predict(df)
                            prf = per_class_prf(y_true, yp)
                            f1 = macro_f1(prf)
                            if f1 > best_cascade2[0]:
                                best_cascade2 = (f1, yp, {
                                    "cit_thr": cit, "use_trigger": use_trg,
                                    "coauthor_thr": ca, "veto_down_q": vq,
                                })
            if best_cascade2[1] is not None:
                yp = best_cascade2[1]
                predictions_store["M9_Cascade_TunedBase"] = yp
                scores_store["M9_Cascade_TunedBase"] = best_info["oof_score_les"]
                prf = per_class_prf(y_true, yp)
                results["M9_Cascade_TunedBase"] = {
                    "agreement": agreement(y_true, yp),
                    "macro_f1": macro_f1(prf),
                    "prf": prf,
                    "top5_precision": top_k_precision(best_info["oof_score_les"], y_true),
                    "missed": recall_agent_missed_lesenswert(df, yp),
                    "tuned_thresholds": best_cascade2[2],
                }
                print(f"  M9_Cascade_TunedBase: agree={100*results['M9_Cascade_TunedBase']['agreement']:.1f}% "
                      f"macroF1={results['M9_Cascade_TunedBase']['macro_f1']:.3f} "
                      f"(over M8_{best_m8_key}_TunedProba, settings={best_cascade2[2]})")

        # ─── Cascade über M8_TunedProba_PerJournal (Iter 7) ────────────────
        pj_key = f"M8_{best_m8_key}_TunedProba_PerJournal"
        if pj_key in predictions_store:
            pj_pred = predictions_store[pj_key]
            best_cascade3 = (-1.0, None, None)
            for cit in [1, 2]:
                for use_trg in [True, False]:
                    for ca in [None, 1, 2]:
                        for vq in [None, 0.05, 0.10, 0.20]:
                            casc = M9_Cascade(veto_scores, pj_pred,
                                              best_info["oof_score_les"],
                                              cit_thr=cit, use_trigger=use_trg,
                                              coauthor_thr=ca, veto_down_quantile=vq)
                            yp = casc.predict(df)
                            prf = per_class_prf(y_true, yp)
                            f1 = macro_f1(prf)
                            if f1 > best_cascade3[0]:
                                best_cascade3 = (f1, yp, {
                                    "cit_thr": cit, "use_trigger": use_trg,
                                    "coauthor_thr": ca, "veto_down_q": vq,
                                })
            if best_cascade3[1] is not None:
                yp = best_cascade3[1]
                predictions_store["M9_Cascade_PerJournalBase"] = yp
                scores_store["M9_Cascade_PerJournalBase"] = best_info["oof_score_les"]
                prf = per_class_prf(y_true, yp)
                results["M9_Cascade_PerJournalBase"] = {
                    "agreement": agreement(y_true, yp),
                    "macro_f1": macro_f1(prf),
                    "prf": prf,
                    "top5_precision": top_k_precision(best_info["oof_score_les"], y_true),
                    "missed": recall_agent_missed_lesenswert(df, yp),
                    "tuned_thresholds": best_cascade3[2],
                }
                print(f"  M9_Cascade_PerJournalBase: "
                      f"agree={100*results['M9_Cascade_PerJournalBase']['agreement']:.1f}% "
                      f"macroF1={results['M9_Cascade_PerJournalBase']['macro_f1']:.3f} "
                      f"(over {pj_key}, settings={best_cascade3[2]})")

        # ─── Cascade über M8_TunedProba_PerJournalCV (Iter 8, CV-validiert) ─
        pj_cv_key = f"M8_{best_m8_key}_TunedProba_PerJournalCV"
        if pj_cv_key in predictions_store:
            pj_cv_pred = predictions_store[pj_cv_key]
            best_cascade4 = (-1.0, None, None)
            for cit in [1, 2]:
                for use_trg in [True, False]:
                    for ca in [None, 1, 2]:
                        for vq in [None, 0.05, 0.10, 0.20]:
                            casc = M9_Cascade(veto_scores, pj_cv_pred,
                                              best_info["oof_score_les"],
                                              cit_thr=cit, use_trigger=use_trg,
                                              coauthor_thr=ca, veto_down_quantile=vq)
                            yp = casc.predict(df)
                            prf = per_class_prf(y_true, yp)
                            f1 = macro_f1(prf)
                            if f1 > best_cascade4[0]:
                                best_cascade4 = (f1, yp, {
                                    "cit_thr": cit, "use_trigger": use_trg,
                                    "coauthor_thr": ca, "veto_down_q": vq,
                                })
            if best_cascade4[1] is not None:
                yp = best_cascade4[1]
                predictions_store["M9_Cascade_PerJournalCVBase"] = yp
                scores_store["M9_Cascade_PerJournalCVBase"] = best_info["oof_score_les"]
                prf = per_class_prf(y_true, yp)
                results["M9_Cascade_PerJournalCVBase"] = {
                    "agreement": agreement(y_true, yp),
                    "macro_f1": macro_f1(prf),
                    "prf": prf,
                    "top5_precision": top_k_precision(best_info["oof_score_les"], y_true),
                    "missed": recall_agent_missed_lesenswert(df, yp),
                    "tuned_thresholds": best_cascade4[2],
                }
                print(f"  M9_Cascade_PerJournalCVBase: "
                      f"agree={100*results['M9_Cascade_PerJournalCVBase']['agreement']:.1f}% "
                      f"macroF1={results['M9_Cascade_PerJournalCVBase']['macro_f1']:.3f} "
                      f"(over {pj_cv_key}, settings={best_cascade4[2]})")

    # ─── Speichern ─────────────────────────────────────────────────────────
    pred_df = pd.DataFrame({"id": df["id"], **{k: v.values for k, v in predictions_store.items()}})
    for k, v in scores_store.items():
        pred_df[f"score_{k}"] = v.values
    Path(args.predictions_out).parent.mkdir(parents=True, exist_ok=True)
    pred_df.to_parquet(args.predictions_out, index=False)
    print(f"\nWrote {args.predictions_out}")

    # Run-Log
    log_entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "n": int(len(df)),
        "agent_agreement": agent_agree,
        "agent_macro_f1": agent_macro,
        "methods": {
            k: {kk: vv for kk, vv in v.items() if kk != "prf" and kk != "missed"}
            for k, v in results.items()
        },
        "seed": args.seed,
        "quick": args.quick,
        "runtime_seconds": time.time() - t0,
    }
    log_path = Path(args.log_out)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a") as f:
        f.write(json.dumps(log_entry, default=float) + "\n")

    # ─── Markdown-Report ──────────────────────────────────────────────────
    lines: list[str] = []
    lines.append(f"# Backtest: Algorithmische Triage vs. LLM-Agent")
    lines.append("")
    lines.append(f"_Run: {datetime.now(timezone.utc).isoformat()} | n={len(df)} | "
                 f"seed={args.seed} | Laufzeit {time.time()-t0:.1f}s_")
    lines.append("")
    lines.append("## TL;DR")
    lines.append("")
    # Sort methods by macro-F1
    ranking = sorted(results.items(), key=lambda x: -x[1]["macro_f1"])
    lines.append("| # | Methode | Agreement | Macro-F1 | Top-5%-Prec | Missed-Recall |")
    lines.append("|---|---|---:|---:|---:|---:|")
    lines.append(f"| — | **Agent (Opus 4.6, Baseline)** | {100*agent_agree:.1f}% | "
                 f"{agent_macro:.3f} | n/a | n/a |")
    for i, (nm, r) in enumerate(ranking, 1):
        lines.append(f"| {i} | {nm} | {100*r['agreement']:.1f}% | {r['macro_f1']:.3f} | "
                     f"{100*r['top5_precision']:.1f}% | "
                     f"{r['missed']['recovered']}/{r['missed']['n_missed']} = "
                     f"{100*r['missed']['recall']:.0f}% |")
    lines.append("")

    # Best method summary
    best_name, best_r = ranking[0]
    delta_f1 = best_r["macro_f1"] - agent_macro
    delta_agree = best_r["agreement"] - agent_agree
    sign_f1 = "+" if delta_f1 >= 0 else ""
    sign_a = "+" if delta_agree >= 0 else ""
    lines.append(f"**Bestes Verfahren**: {best_name} mit Macro-F1 {best_r['macro_f1']:.3f} "
                 f"({sign_f1}{delta_f1:.3f} vs. Agent) und Agreement "
                 f"{100*best_r['agreement']:.1f}% ({sign_a}{100*delta_agree:.1f} pp).")
    lines.append("")

    lines.append("## Setup")
    lines.append("")
    lines.append(f"- Gold-Set: **{len(df)}** Artikel mit user_verdict")
    lines.append(f"- Klassen (nach Kollaps pflichtlektuere→lesenswert): "
                 f"{y_true.value_counts().to_dict()}")
    lines.append(f"- Agent-Baseline: Opus 4.6 (pre 2026-05-24), Agreement 71.6%")
    lines.append("- Cross-Validation: 5-fold StratifiedKFold (für M8, Schwellen-Tuning auf voller Tabelle)")
    lines.append("- Methodische Disziplin: non-LLM-Daten only (siehe docs/context/project_backtest_algorithmic_heuristics.md)")
    lines.append("")

    lines.append("## Agent-Baseline (zum Vergleich)")
    lines.append("")
    lines.append(format_method_block("Agent (Opus 4.6)", agent_agree, agent_prf, agent_macro,
                                     top_k_precision(
                                         pd.Series((agent_pred == "lesenswert").astype(float).values
                                                   + 0.5*(agent_pred == "scannen").astype(float).values,
                                                   index=df.index),
                                         y_true),
                                     {"n_missed": 0, "recovered": 0, "recall": 0.0}))
    lines.append("**Konfusion (Agent vs. User):**")
    lines.append("")
    lines.append(confusion_md(y_true, agent_pred))
    lines.append("")

    lines.append("## Methoden-Detail")
    lines.append("")
    for nm, r in ranking:
        extra: dict[str, Any] = {}
        if "fitted_thresholds" in r:
            extra["fitted_thresholds"] = r["fitted_thresholds"]
        if "fold_macro_f1_mean" in r:
            extra["extra_notes"] = [
                f"_5-fold CV Macro-F1: {r['fold_macro_f1_mean']:.3f} ± {r['fold_macro_f1_std']:.3f}_",
                f"_n_features: {r['feature_count']}_",
            ]
        lines.append(format_method_block(nm, r["agreement"], r["prf"], r["macro_f1"],
                                         r["top5_precision"], r["missed"], extra=extra))
        lines.append("**Konfusion:**")
        lines.append("")
        lines.append(confusion_md(y_true, predictions_store[nm]))
        lines.append("")

    Path(args.report_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report_out).write_text("\n".join(lines))
    print(f"\nWrote report: {args.report_out}")
    print(f"\nDone in {time.time()-t0:.1f}s")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        print(f"\n!!! FEHLER in main(): {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
