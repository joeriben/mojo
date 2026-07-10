"""Re-Test der bezuege-Härtung (agent.py: Schema-Vorgabe + _coerce_bezuege).

Fährt die GLM-tools-Läufe des A/B-Tests 2026-07-10 nach, die im Erstlauf
befüllte Bezüge lieferten (dort: 3 von 7 als double-encoded String defekt),
und misst die Defektquote NACH der Härtung. Eigene Output-Datei — der
committete A/B-Datenstand (glm52_vs_gemini_ab_2026-07-10.json) bleibt
unangetastet. articles-Tabelle read-only (gleiche Mechanik wie das
A/B-Skript); Kosten laufen normal über den llm_calls-Ledger.

CLI:
  python scripts/_bezuege_retest.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import _glm52_vs_gemini_agent_ab as ab  # noqa: E402

GLM_MODEL = ab.MODELS["glm"]
OUT_FILE = ab.OUT_DIR / "bezuege_retest_2026-07-11.json"
MAX_TOTAL_COST_USD = 1.50


def glm_runs_with_bezuege() -> list[dict]:
    data = json.loads(ab.FINAL_JSON.read_text())
    picked = []
    for rec in data["records"]:
        if rec.get("model_key") != "glm" or rec.get("mode") != "tools":
            continue
        entry = rec.get("entry") or {}
        bez = entry.get("bezuege")
        if bez:  # Liste mit Inhalt ODER (Defektfall) nicht-leerer String
            picked.append(
                {
                    "article_id": rec["article_id"],
                    "old_type": type(bez).__name__,
                    "old_was_defect": isinstance(bez, str),
                }
            )
    return picked


def ledger_cost_since(ts_iso: str) -> float:
    uri = f"file:{ab.ARTICLES_DB}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    row = conn.execute(
        "SELECT COALESCE(sum(cost_usd),0) FROM llm_calls WHERE timestamp >= ? AND model = ?",
        (ts_iso, GLM_MODEL),
    ).fetchone()
    conn.close()
    return float(row[0])


def main() -> None:
    started = datetime.now(timezone.utc).isoformat()
    targets = glm_runs_with_bezuege()
    print(f"Re-Test bezuege-Härtung: {len(targets)} GLM-Läufe mit Bezügen im Erstlauf")
    for t in targets:
        print(f"  {t['article_id'][:12]}…  Erstlauf-Typ: {t['old_type']}"
              f"{'  << DEFEKT' if t['old_was_defect'] else ''}")

    rows = ab.load_rows([t["article_id"] for t in targets])
    results = []
    for i, t in enumerate(targets, 1):
        aid = t["article_id"]
        article = ab.article_dict_from_row(rows[aid])
        print(f"\n[{i}/{len(targets)}] {aid[:12]}… ({GLM_MODEL})")
        rec = ab.call_tools(article, GLM_MODEL, aid)
        entry = rec.get("entry") or {}
        bez = entry.get("bezuege")
        results.append(
            {
                "article_id": aid,
                "old_type": t["old_type"],
                "old_was_defect": t["old_was_defect"],
                "exception": rec.get("exception"),
                "verdict": entry.get("verdict"),
                "new_bezuege_type": type(bez).__name__ if bez is not None else None,
                "new_bezuege_len": len(bez) if isinstance(bez, list) else None,
                "bezuege_repaired": entry.get("bezuege_repaired", False),
                "bezuege_repair_method": entry.get("bezuege_repair_method"),
                "bezuege_unparsed_present": bool(entry.get("bezuege_unparsed")),
                "latency_s": rec.get("latency_s"),
                "cost_usd": rec.get("cost_usd"),
            }
        )
        total = ledger_cost_since(started)
        print(f"  verdict={entry.get('verdict')}  bezuege={type(bez).__name__}"
              f"  repaired={entry.get('bezuege_repaired', False)}"
              f"  method={entry.get('bezuege_repair_method')}"
              f"  unparsed={bool(entry.get('bezuege_unparsed'))}"
              f"  | Ledger gesamt ${total:.3f}")
        if total > MAX_TOTAL_COST_USD:
            print(f"ABBRUCH: Kosten-Deckel ${MAX_TOTAL_COST_USD} überschritten.")
            break

    clean_lists = sum(
        1 for r in results
        if r["new_bezuege_type"] == "list" and not r["bezuege_repaired"] and not r["exception"]
    )
    repaired = sum(1 for r in results if r["bezuege_repaired"])
    unparsed = sum(1 for r in results if r["bezuege_unparsed_present"])
    summary = {
        "generated_at": started,
        "model": GLM_MODEL,
        "n": len(results),
        "clean_list_first_try": clean_lists,
        "repaired_by_cascade": repaired,
        "still_unparsed": unparsed,
        "ledger_cost_usd": round(ledger_cost_since(started), 4),
        "results": results,
    }
    OUT_FILE.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n== Summary: n={summary['n']}  sauber={clean_lists}  "
          f"kaskaden-repariert={repaired}  unparsed={unparsed}  "
          f"Kosten=${summary['ledger_cost_usd']}")
    print(f"→ {OUT_FILE}")


if __name__ == "__main__":
    main()
