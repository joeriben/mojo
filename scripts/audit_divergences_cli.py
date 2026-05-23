"""Interaktives CLI für den Gemini-Divergenz-Audit.

Geht die 24 Divergenzen aus qcheck_gemini35_n50.json einzeln durch und fragt
pro Eintrag per Tastendruck: o (OPUS), g (GEMINI), b (BEIDE), s (skip).

- Speichert nach JEDER Antwort in docs/qcheck_gemini35_audit_results.json
- Beim Wiederstart werden bereits beantwortete Einträge übersprungen
- Mit `q` jederzeit beenden; Fortschritt bleibt erhalten
- Anmerkung optional (Enter = leer lassen)

Nutzung:
    python scripts/audit_divergences_cli.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DOCS = Path("docs")
DB_PATH = Path("articles.db")
RESULTS = DOCS / "qcheck_gemini35_audit_results.json"

VERDICT_KEY = {"o": "OPUS", "g": "GEMINI", "b": "BEIDE", "s": "SKIP"}


def load_existing() -> dict:
    if RESULTS.exists():
        return json.loads(RESULTS.read_text())
    return {"ts_started": datetime.now().isoformat(), "answers": {}}


def save(state: dict) -> None:
    state["ts_updated"] = datetime.now().isoformat()
    RESULTS.write_text(json.dumps(state, ensure_ascii=False, indent=2))


def wrap(text: str, width: int = 92) -> str:
    """Sehr simples Wort-Wrap."""
    import textwrap
    if not text:
        return ""
    return "\n".join(textwrap.fill(line, width=width, subsequent_indent="  ")
                     for line in text.splitlines() if line.strip())


def render(idx: int, total: int, r: dict, opus: dict, retest: dict | None, title: str) -> None:
    print("\n" + "=" * 96)
    print(f" [{idx}/{total}]  {r['journal']}  ·  {r['discourse']}")
    print(f" {title[:140]}")
    print(f" article_id: {r['article_id']}   citation_hits: high={r['citation_hits_high']} med={r['citation_hits_med']}")
    print("=" * 96)

    print(f"\n  >>> OPUS (Goldstandard):  {r['opus_verdict'].upper()}")
    if opus.get("kernthese"):
        print("\n  Opus-Kernthese:")
        print("    " + wrap(opus["kernthese"][:600]).replace("\n", "\n    "))
    print("\n  Opus-Begründung:")
    print("    " + wrap(opus.get("verdict_begruendung", "(keine)")[:600]).replace("\n", "\n    "))

    print(f"\n  >>> GEMINI (low-effort):  {r['gemini_verdict'].upper()}")
    print("\n  Gemini-Kernthese:")
    print("    " + wrap((r.get("gemini_kernthese") or "")[:600]).replace("\n", "\n    "))
    print("\n  Gemini-Begründung:")
    print("    " + wrap((r.get("gemini_begruendung") or "")[:600]).replace("\n", "\n    "))

    if retest and retest.get("retest_verdict"):
        changed = retest["retest_verdict"] != r["gemini_verdict"]
        tag = "GEÄNDERT" if changed else "unverändert"
        print(f"\n  >>> GEMINI (high-effort, {tag}):  {retest['retest_verdict'].upper()}")
        if changed:
            print("\n  Gemini-high-Begründung:")
            print("    " + wrap((retest.get("retest_begruendung") or "")[:600]).replace("\n", "\n    "))

    print("\n" + "-" * 96)
    print("  Wer hat recht?")
    print("    o = OPUS (Gemini liegt daneben)")
    print("    g = GEMINI (Opus zu konservativ, Gemini findet echten Anschluss)")
    print("    b = BEIDE (Lesart vertretbar, Grenzfall)")
    print("    s = skip (später entscheiden)")
    print("    q = quit (Fortschritt bleibt gespeichert)")


def main():
    baseline = json.loads((DOCS / "qcheck_gemini35_n50.json").read_text())
    divergences = [r for r in baseline["results"] if "gemini_verdict" in r and not r.get("match")]

    retest_path = DOCS / "qcheck_gemini35_retest.json"
    retest = {}
    if retest_path.exists():
        retest = {r["article_id"]: r for r in json.loads(retest_path.read_text())["results"]}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    state = load_existing()
    answers = state["answers"]

    pending = [(i, r) for i, r in enumerate(divergences, 1) if r["article_id"] not in answers]
    done = len(answers)

    print(f"\nAudit-CLI · {len(divergences)} Divergenzen aus N=50")
    print(f"Bereits bearbeitet: {done}   ·   offen: {len(pending)}")
    if done > 0:
        counts = {}
        for v in answers.values():
            counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
        print(f"Bisheriger Stand: {counts}")
    if not pending:
        print("\nAlles bearbeitet. Lauf scripts/audit_divergences_summary.py für die Auswertung.")
        return

    for idx, r in pending:
        aid = r["article_id"]
        row = conn.execute(
            "SELECT title, agent_entry_json FROM articles WHERE id=?", (aid,)
        ).fetchone()
        opus = {}
        if row and row["agent_entry_json"]:
            try:
                opus = json.loads(row["agent_entry_json"])
            except Exception:
                pass
        title = (row["title"] if row else r.get("title", "")) or ""

        render(idx, len(divergences), r, opus, retest.get(aid), title)

        while True:
            key = input("\n  Eingabe [o/g/b/s/q]: ").strip().lower()
            if key in VERDICT_KEY or key == "q":
                break
            print("  Bitte o, g, b, s oder q.")

        if key == "q":
            print(f"\nAbgebrochen. {len(answers)}/{len(divergences)} beantwortet — Fortschritt in {RESULTS}.")
            return

        if key == "s":
            print("  → übersprungen (kein Eintrag gespeichert; erscheint beim nächsten Lauf wieder).")
            continue

        note = input("  Anmerkung (Enter zum Überspringen): ").strip()
        answers[aid] = {
            "verdict": VERDICT_KEY[key],
            "note": note,
            "ts": datetime.now().isoformat(),
            "journal": r["journal"],
            "discourse": r["discourse"],
            "opus_verdict": r["opus_verdict"],
            "gemini_verdict": r["gemini_verdict"],
        }
        save(state)
        print(f"  → gespeichert ({VERDICT_KEY[key]}). [{len(answers)}/{len(divergences)} fertig]")

    print(f"\n✓ Alle {len(divergences)} Divergenzen durch.")
    counts = {}
    for v in answers.values():
        counts[v["verdict"]] = counts.get(v["verdict"], 0) + 1
    print(f"  Verteilung: {counts}")
    print(f"  Ergebnisse: {RESULTS}")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n\nAbgebrochen — Fortschritt ist gespeichert.")
        sys.exit(0)
