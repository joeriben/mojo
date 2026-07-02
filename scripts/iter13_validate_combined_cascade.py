"""Iter 13 — Kombinationstest: alle algorithmischen Veto-Up-Regeln gestapelt.

Vorgeschichte:
  iter11h testete `f_own_coupling_union >= 1` (grobes Binär-Count) als Veto-Up:
    LES-Recall +2.6 pp, aber Macro-F1 0.588 → 0.577 (netto-negativ).
  iter12 testete das adversariale Blind-Spot-Signal: sauberes Per-Klassen-Signal,
    aber auf die Hard-Cases (Wrong-LES, n=28) praktisch wirkungslos.

Offener Schritt: die einzeln validierten Alternativen ZUSAMMEN im Cascade
gegen den Gold-Satz testen — und zwar mit den KALIBRIERTEN IDF-Scores
(own_coupling WEAK 0.60 / STRONG 1.50; adversarial WEAK 3.0 / STRONG 8.0)
plus der §2.6-Direktzitat-Regel, nicht dem groben union≥1 aus iter11h.

Frage: Schlägt irgendeine Kombination der entwickelten Alternativen die
TunedBase-Baseline (0.588) bzw. PerJournal (0.601) Macro-F1 — oder bestätigt
sie das Plateau gegenüber Opus (0.677)?

Reine Diagnostik, keine LLM-Calls, keine Schreib-Operationen.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import f1_score, precision_recall_fscore_support

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from journal_bot.adversarial.corpus_freq import load_or_compute_adversarial_corpus_freq
from journal_bot.adversarial.trigger_refs import load_or_compute_adversarial_index
from journal_bot.own_refs.index import load_own_refs_index
from journal_bot.signals import (
    ADVERSARIAL_STRONG_SCORE, ADVERSARIAL_WEAK_SCORE,
    OWN_COUPLING_STRONG_SCORE, OWN_COUPLING_WEAK_SCORE,
    signal_adversarial_blindspot, signal_own_coupling,
)
from journal_bot.own_refs.corpus_freq import load_or_compute_corpus_freq

FEATURES_GOLD = ROOT / "backtest_data" / "features_gold.parquet"
PREDICTIONS = ROOT / "backtest_data" / "predictions_iter11_full.parquet"
ARTICLES_DB = ROOT / "articles.db"
OWN_REFS_DB = ROOT / "own_refs.db"
TRIGGER_DIR = ROOT / "backtest_data" / "trigger_bibliographies"

LABELS3 = ["ignorieren", "scannen", "lesenswert"]
OPUS_MACRO_F1 = 0.677  # feedback_ground_truth_qualitaet.md (3-class)


def _normalize(pred: pd.Series) -> pd.Series:
    return pred.astype(str).where(pred.isin(LABELS3), "ignorieren")


def _compute_signals(gold_ids: set[str]) -> pd.DataFrame:
    """Berechne own_coupling- + adversarial-Score und selection_mode/n_union
    für alle Gold-Artikel aus articles.db (über die echten Signal-Funktionen)."""
    own_idx = load_own_refs_index(OWN_REFS_DB)
    corpus_freq = load_or_compute_corpus_freq(ARTICLES_DB, own_idx)
    adv = load_or_compute_adversarial_index(TRIGGER_DIR, own_idx, own_refs_db=OWN_REFS_DB)
    adv_freq = load_or_compute_adversarial_corpus_freq(ARTICLES_DB, adv, own_refs_db=OWN_REFS_DB)

    con = sqlite3.connect(str(ARTICLES_DB))
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, openalex_refs, crossref_refs, selection_mode FROM articles"
    ).fetchall()
    con.close()

    recs = []
    for r in rows:
        if r["id"] not in gold_ids:
            continue
        oa = []
        if r["openalex_refs"]:
            try:
                oa = json.loads(r["openalex_refs"])
            except json.JSONDecodeError:
                pass
        cr = []
        if r["crossref_refs"]:
            try:
                cr = json.loads(r["crossref_refs"])
            except json.JSONDecodeError:
                pass
        own = signal_own_coupling(cr, oa, own_idx, corpus_freq)
        advs = signal_adversarial_blindspot(oa, adv, adv_freq)
        recs.append({
            "id": r["id"],
            "own_score": float(own.get("score", 0.0) or 0.0),
            "own_n_union": int(own.get("n_union", 0) or 0),
            "adv_score": float(advs.get("score", 0.0) or 0.0),
            "selection_mode": r["selection_mode"] or "",
        })
    return pd.DataFrame(recs)


def _report(df: pd.DataFrame, col: str, label: str, base_col: str) -> dict:
    yt = df["user_verdict"]
    yp = df[col]
    macro = f1_score(yt, yp, labels=LABELS3, average="macro", zero_division=0)
    # binary LES
    p, r, f, _ = precision_recall_fscore_support(
        (yt == "lesenswert").astype(int), (yp == "lesenswert").astype(int),
        average="binary", zero_division=0,
    )
    lifted = (yp == "lesenswert") & (df[base_col] != "lesenswert")
    n_lift = int(lifted.sum())
    true_lift = int((lifted & (yt == "lesenswert")).sum())
    return {
        "label": label, "macro_f1": macro, "les_prec": p, "les_rec": r,
        "les_f1": f, "n_pred_les": int((yp == "lesenswert").sum()),
        "n_lift": n_lift, "true_lift": true_lift,
    }


def main() -> int:
    for f in (FEATURES_GOLD, PREDICTIONS, ARTICLES_DB, OWN_REFS_DB):
        if not f.exists():
            print(f"[ERR] fehlt: {f}", file=sys.stderr)
            return 2

    fg = pd.read_parquet(FEATURES_GOLD)
    pred = pd.read_parquet(PREDICTIONS)
    df = fg.merge(
        pred[["id", "M9_Cascade_TunedBase", "M9_Cascade_PerJournalBase"]],
        on="id", how="left",
    )
    df = df[df["user_verdict"] != "pflichtlektuere"].copy()

    sig = _compute_signals(set(df["id"]))
    df = df.merge(sig, on="id", how="left")
    for c in ["own_score", "adv_score", "own_n_union"]:
        df[c] = df[c].fillna(0.0)
    df["selection_mode"] = df["selection_mode"].fillna("")

    print(f"n={len(df)} (excl pflichtlektuere)")
    n_les = int((df["user_verdict"] == "lesenswert").sum())
    print(f"  LES (user_verdict): {n_les}")
    print(f"  Signal-Abdeckung (>0): own_coupling={int((df['own_score']>0).sum())}  "
          f"adversarial={int((df['adv_score']>0).sum())}  "
          f"citation-mode={int((df['selection_mode']=='citation').sum())}")
    print(f"  Schwellen: own WEAK={OWN_COUPLING_WEAK_SCORE} STRONG={OWN_COUPLING_STRONG_SCORE} | "
          f"adv WEAK={ADVERSARIAL_WEAK_SCORE} STRONG={ADVERSARIAL_STRONG_SCORE}")
    print()

    # Veto-Up-Regeln als Masken (STRONG → lesenswert, WEAK → mind. scannen)
    rule_own_strong = df["own_score"] >= OWN_COUPLING_STRONG_SCORE
    rule_own_weak = (df["own_score"] >= OWN_COUPLING_WEAK_SCORE) & ~rule_own_strong
    rule_adv_strong = df["adv_score"] >= ADVERSARIAL_STRONG_SCORE
    rule_adv_weak = (df["adv_score"] >= ADVERSARIAL_WEAK_SCORE) & ~rule_adv_strong
    rule_s26 = (df["selection_mode"] == "citation") & (df["own_n_union"] >= 2)

    def apply_up(base: pd.Series, to_les: pd.Series, to_scn: pd.Series | None = None) -> pd.Series:
        out = base.copy()
        if to_scn is not None:
            m = to_scn & (out == "ignorieren")
            out.loc[m] = "scannen"
        m = to_les & (out != "lesenswert")
        out.loc[m] = "lesenswert"
        return out

    for base_name, base_raw in [("TunedBase", "M9_Cascade_TunedBase"),
                                ("PerJournal", "M9_Cascade_PerJournalBase")]:
        base_col = f"base_{base_name}"
        df[base_col] = _normalize(df[base_raw])

        variants = {
            f"{base_name}: baseline": df[base_col],
            f"{base_name}: +own STRONG": apply_up(df[base_col], rule_own_strong),
            f"{base_name}: +own STRONG+WEAK": apply_up(df[base_col], rule_own_strong, rule_own_weak),
            f"{base_name}: +adv STRONG": apply_up(df[base_col], rule_adv_strong),
            f"{base_name}: +adv STRONG+WEAK": apply_up(df[base_col], rule_adv_strong, rule_adv_weak),
            f"{base_name}: +§2.6 double-hit": apply_up(df[base_col], rule_s26),
            f"{base_name}: +ALL STRONG": apply_up(
                df[base_col], rule_own_strong | rule_adv_strong | rule_s26),
            f"{base_name}: +ALL (STRONG→LES, WEAK→SCN)": apply_up(
                df[base_col], rule_own_strong | rule_adv_strong | rule_s26,
                rule_own_weak | rule_adv_weak),
        }
        rows = []
        for label, series in variants.items():
            col = f"_v_{len(rows)}_{base_name}"
            df[col] = series
            rows.append(_report(df, col, label, base_col))

        print(f"=== {base_name} — Veto-Up-Kombinationen ===")
        header = (f"{'Variante':<44} {'MacroF1':>7} {'LES-P':>6} {'LES-R':>6} "
                  f"{'LES-F1':>6} {'#pred':>5} {'lifts':>6} {'true':>5}")
        print(header)
        print("-" * len(header))
        base_macro = rows[0]["macro_f1"]
        for r in rows:
            delta = r["macro_f1"] - base_macro
            star = "  ←best" if r["macro_f1"] > base_macro + 1e-9 else ""
            lift_str = f"{r['n_lift']}" if r["n_lift"] else "—"
            true_str = f"{r['true_lift']}" if r["n_lift"] else "—"
            print(f"{r['label']:<44} {r['macro_f1']:>7.3f} {r['les_prec']:>6.3f} "
                  f"{r['les_rec']:>6.3f} {r['les_f1']:>6.3f} {r['n_pred_les']:>5} "
                  f"{lift_str:>6} {true_str:>5}  Δ{delta:+.3f}{star}")
        print(f"  (Opus 3-class Macro-F1 Referenz: {OPUS_MACRO_F1:.3f})")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
