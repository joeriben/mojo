"""Exportiert die Triage-Kombination auf dem Gold-Satz als JSON für die Web-Ansicht.

Schreibt combine_gold.json: pro Artikel beide Stimmen (Cascade M9 + LLM), das
kombinierte Verdikt/Zustand und Benjamins echtes Urteil als Wahrheit — plus eine
Zusammenfassung (FN-Vergleich, Zustands-Reinheit). Die Web-Route liest nur dieses
JSON (keine pandas/pyarrow-Abhängigkeit in der Flask-Laufzeit).

Reine Lese-/Schreib-Diagnostik, keine LLM-Calls.
"""

from __future__ import annotations

import json
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
OUT = ROOT / "combine_gold.json"

STATE_ORDER = ["konsens_behalten", "dissens", "ein_signal", "konsens_wegwerfen"]


def _is_keep(v) -> bool:
    return isinstance(v, str) and v.strip().lower() in KEEP


def main() -> int:
    for f in (FEATURES_GOLD, PREDICTIONS, ARTICLES_DB):
        if not f.exists():
            print(f"[ERR] fehlt: {f}", file=sys.stderr)
            return 2

    fg = pd.read_parquet(FEATURES_GOLD)
    pr = pd.read_parquet(PREDICTIONS)
    df = fg[["id", "title", "journal_full", "year", "user_verdict"]].merge(
        pr[["id", "M9_Cascade_TunedBase"]], on="id", how="left")
    con = sqlite3.connect(str(ARTICLES_DB))
    av = pd.read_sql_query(
        "SELECT id, agent_verdict FROM articles "
        "WHERE agent_verdict IS NOT NULL AND agent_verdict!=''", con)
    con.close()
    df = df.merge(av, on="id", how="left")
    df = df[df["user_verdict"] != "pflichtlektuere"].copy()
    df = df.dropna(subset=["M9_Cascade_TunedBase", "agent_verdict"])

    entries = []
    fn_cascade = fn_llm = fn_comb = 0
    for _, r in df.iterrows():
        cascade = r["M9_Cascade_TunedBase"]
        llm = r["agent_verdict"]
        user = r["user_verdict"]
        c = combine_triage(cascade, llm)
        truth_keep = _is_keep(user)
        if not _is_keep(cascade) and truth_keep:
            fn_cascade += 1
        if not _is_keep(llm) and truth_keep:
            fn_llm += 1
        if not c.keep and truth_keep:
            fn_comb += 1
        entries.append({
            "id": r["id"],
            "title": (r["title"] or "")[:240],
            "journal": r["journal_full"] or "",
            "year": int(r["year"]) if pd.notna(r["year"]) else None,
            "cascade": cascade,
            "llm": llm,
            "user": user,
            "decision": c.decision,
            "state": c.state,
            "flagged": c.flagged,
            "correct": c.keep == truth_keep,
        })

    # Zustands-Zusammenfassung
    states = {}
    for st in STATE_ORDER:
        sub = [e for e in entries if e["state"] == st]
        if not sub:
            continue
        kt = sum(1 for e in sub if _is_keep(e["user"]))
        states[st] = {
            "n": len(sub),
            "wahr_behalten": kt,
            "pct_behalten": round(100 * kt / len(sub)),
        }

    n = len(entries)
    n_keep_true = sum(1 for e in entries if _is_keep(e["user"]))
    n_correct = sum(1 for e in entries if e["correct"])
    payload = {
        "n": n,
        "wahr_behalten": n_keep_true,
        "n_correct": n_correct,
        "fn_cascade": fn_cascade,
        "fn_llm": fn_llm,
        "fn_comb": fn_comb,
        "states": states,
        "state_order": [s for s in STATE_ORDER if s in states],
        "entries": entries,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"geschrieben: {OUT.name}  ({n} Artikel, FN Cascade {fn_cascade} · LLM {fn_llm} · Kombi {fn_comb})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
