"""Prüft die Kombinationslogik (journal_bot/combine.py) an Benjamins echten Urteilen.

Achse: BEHALTEN {lesenswert, scannen, pflichtlektuere} vs WEGWERFEN {ignorieren}.
Datenquellen (Gold-Satz, n=460):
  - Wahrheit:        user_verdict        (features_gold.parquet)
  - Cascade-Triage:  M9_Cascade_TunedBase (predictions_iter11_full.parquet)
  - LLM-Triage:      agent_verdict        (articles.db)

Beantwortet die drei offenen Punkte:
  (1) 1+1 (Konsens behalten) als stärkstes Signal → wie rein ist es wirklich?
  (2) Dissens → wie groß, was steckt drin?
  (3) Falsch-Negativ-Bestand → senkt die Kombination ihn gegenüber jedem
      Einzelklassifikator (Benjamins Vermutung)?

Keine LLM-Calls, keine Schreib-Operationen.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from journal_bot.combine import KEEP, combine_triage

FEATURES_GOLD = ROOT / "backtest_data" / "features_gold.parquet"
PREDICTIONS = ROOT / "backtest_data" / "predictions_iter11_full.parquet"
ARTICLES_DB = ROOT / "articles.db"


def _is_keep(v) -> bool:
    return isinstance(v, str) and v.strip().lower() in KEEP


def _confusion(keep_pred, keep_true):
    """TP=behalten&wahr-behalten, FP=behalten&wahr-wegwerfen,
    FN=weggeworfen&wahr-behalten, TN=weggeworfen&wahr-wegwerfen."""
    tp = sum(1 for p, t in zip(keep_pred, keep_true) if p and t)
    fp = sum(1 for p, t in zip(keep_pred, keep_true) if p and not t)
    fn = sum(1 for p, t in zip(keep_pred, keep_true) if not p and t)
    tn = sum(1 for p, t in zip(keep_pred, keep_true) if not p and not t)
    return tp, fp, fn, tn


def _line(label, keep_pred, keep_true, n):
    tp, fp, fn, tn = _confusion(keep_pred, keep_true)
    keep_recall = tp / (tp + fn) if (tp + fn) else 0.0       # behalten-Recall
    dropped = fn + tn
    noise_caught = tn / (fp + tn) if (fp + tn) else 0.0       # wegwerfen-Recall
    print(f"{label:<26} FN={fn:>3}  behalten-Recall={100*keep_recall:>5.1f}%   "
          f"weggeworfen={dropped:>3}/{n} ({100*dropped/n:>4.1f}%)  "
          f"davon Rauschen-Treffer={100*noise_caught:>5.1f}%")
    return fn


def main() -> int:
    for f in (FEATURES_GOLD, PREDICTIONS, ARTICLES_DB):
        if not f.exists():
            print(f"[ERR] fehlt: {f}", file=sys.stderr)
            return 2

    fg = pd.read_parquet(FEATURES_GOLD)
    pr = pd.read_parquet(PREDICTIONS)
    df = fg[["id", "user_verdict"]].merge(
        pr[["id", "M9_Cascade_TunedBase"]], on="id", how="left")
    con = sqlite3.connect(str(ARTICLES_DB))
    av = pd.read_sql_query(
        "SELECT id, agent_verdict FROM articles "
        "WHERE agent_verdict IS NOT NULL AND agent_verdict!=''", con)
    con.close()
    df = df.merge(av, on="id", how="left")
    df = df[df["user_verdict"] != "pflichtlektuere"].copy()
    df = df.dropna(subset=["M9_Cascade_TunedBase", "agent_verdict"])
    n = len(df)

    cascade = df["M9_Cascade_TunedBase"].tolist()
    llm = df["agent_verdict"].tolist()
    truth = df["user_verdict"].tolist()
    keep_true = [_is_keep(t) for t in truth]
    n_keep_true = sum(keep_true)

    combos = [combine_triage(c, l) for c, l in zip(cascade, llm)]

    print(f"Gold-Satz n={n}  ·  wahr-behalten {n_keep_true} ({100*n_keep_true/n:.0f}%)  ·  "
          f"wahr-wegwerfen {n-n_keep_true} ({100*(n-n_keep_true)/n:.0f}%)\n")

    # (3) Falsch-Negativ-Vergleich der drei Strategien
    print("── Strategie-Vergleich (FN = verlorene Lesenswerte/Scannenswerte) ──")
    fn_casc = _line("Cascade allein", [_is_keep(c) for c in cascade], keep_true, n)
    fn_llm = _line("LLM allein", [_is_keep(l) for l in llm], keep_true, n)
    fn_comb = _line("Kombination (Vereinig.)", [c.keep for c in combos], keep_true, n)
    print(f"\n  → Falsch-Negative: Cascade {fn_casc} · LLM {fn_llm} · Kombination {fn_comb}")
    best_single = min(fn_casc, fn_llm)
    if fn_comb < best_single:
        print(f"    Kombination senkt FN um {best_single - fn_comb} gegenüber dem besseren "
              f"Einzelklassifikator ({100*(best_single-fn_comb)/best_single:.0f}% weniger verlorene Treffer).")
    elif fn_comb == best_single:
        print("    Kombination gleichauf mit dem besseren Einzelklassifikator (kein FN-Gewinn).")
    else:
        print("    Kombination schlechter — Vermutung widerlegt.")

    # (1)+(2) Zustands-Zellen: Reinheit je Kombinationszustand
    print("\n── Kombinations-Zustände (Benjamins 1+1 / Dissens) ──")
    print(f"{'Zustand':<20} {'n':>4} {'%aller':>7}   {'wahr-behalten':>14}   {'Lesart'}")
    order = ["konsens_behalten", "dissens", "ein_signal", "konsens_wegwerfen"]
    lesart = {
        "konsens_behalten": "stärkstes Signal — sicher behalten",
        "dissens": "geflaggt — recall-schützend behalten",
        "ein_signal": "nur ein Signal",
        "konsens_wegwerfen": "sicheres Rauschen — einziger Wegwurf",
    }
    for st in order:
        idx = [i for i, c in enumerate(combos) if c.state == st]
        if not idx:
            continue
        kt = sum(keep_true[i] for i in idx)
        print(f"{st:<20} {len(idx):>4} {100*len(idx)/n:>6.1f}%   "
              f"{kt:>4}/{len(idx):<4} ({100*kt/len(idx):>3.0f}%)   {lesart[st]}")

    # Headline-Reinheiten
    cb = [i for i, c in enumerate(combos) if c.state == "konsens_behalten"]
    cw = [i for i, c in enumerate(combos) if c.state == "konsens_wegwerfen"]
    ds = [i for i, c in enumerate(combos) if c.state == "dissens"]
    if cb:
        print(f"\n(1) Konsens-behalten (1+1): {100*sum(keep_true[i] for i in cb)/len(cb):.0f}% "
              f"wirklich behaltenswert  →  Präzision des stärksten Signals.")
    if cw:
        lost = sum(keep_true[i] for i in cw)
        print(f"    Konsens-wegwerfen: {100*(len(cw)-lost)/len(cw):.0f}% wirklich Rauschen "
              f"(nur {lost} echte Treffer im Wegwurf = der gesamte FN-Bestand der Kombination).")
    if ds:
        rescued = sum(keep_true[i] for i in ds)
        print(f"(2) Dissens: {len(ds)} Artikel, davon {rescued} wirklich behaltenswert "
              f"— genau die Treffer, die die Vereinigung gegenüber dem Schnitt rettet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
