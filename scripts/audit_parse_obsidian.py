"""Liest das in Obsidian ausgefüllte Audit-MD ein, extrahiert die geklickten
Checkboxen + Anmerkungen pro Divergenz und schreibt das nach
docs/qcheck_gemini35_audit_results.json (gleiches Format wie das CLI).

Verträgt sich mit audit_divergences_cli.py — der Parser merged in dieselbe
Datei (CLI-Antworten bleiben erhalten, Obsidian-Antworten überschreiben sie
nur wenn das Obsidian-File neuer ist).

Heuristik:
- Eintrag = Block zwischen zwei `## N. ...`-Headern
- article_id wird aus `_article_id_: \`<hex>\`` extrahiert
- Erste mit [x] markierte Checkbox bestimmt das Verdict
- Mehrere [x] in einem Eintrag → erste gewinnt, Warnung ausgegeben
- Anmerkung = Text nach `**Anmerkung:**` bis zum nächsten `---`
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

OBS_FILE = Path("/Users/joerissen/Documents/Obsidian Vault/research/mojo/2026-05-23_gemini35_divergenz_audit.md")
RESULTS = Path("docs/qcheck_gemini35_audit_results.json")

ENTRY_RE = re.compile(r"^## (\d+)\. ", re.MULTILINE)
AID_RE = re.compile(r"_article_id_:\s*`([^`]+)`")
CHECK_RE = re.compile(r"- \[(.)\] \*\*(OPUS|GEMINI|BEIDE)\*\*")
NOTE_RE = re.compile(r"\*\*Anmerkung:\*\*(.*?)(?=\n---|\Z)", re.DOTALL)
TITLE_RE = re.compile(r"^## \d+\. ([^·]+) · `([^`]+)` — (.+)$", re.MULTILINE)


def parse_entries(md: str) -> list[dict]:
    """Spaltet das MD an `## N. ` und parst pro Block."""
    matches = list(ENTRY_RE.finditer(md))
    if not matches:
        return []
    entries = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        block = md[start:end]
        num = int(m.group(1))

        aid_m = AID_RE.search(block)
        if not aid_m:
            continue
        aid = aid_m.group(1)

        # alle checked checkboxes
        checked = [v for ch, v in CHECK_RE.findall(block) if ch.strip().lower() == "x"]
        verdict = checked[0] if checked else None
        ambiguous = len(checked) > 1

        note = ""
        nm = NOTE_RE.search(block)
        if nm:
            raw = nm.group(1).strip()
            # entferne trailing --- und whitespace
            raw = re.sub(r"\n---\s*$", "", raw).strip()
            note = raw

        # title-zeile
        tm = TITLE_RE.search(block)
        journal = tm.group(1).strip() if tm else ""
        discourse = tm.group(2).strip() if tm else ""
        title_short = tm.group(3).strip() if tm else ""

        entries.append({
            "num": num,
            "article_id": aid,
            "verdict": verdict,
            "ambiguous_checkboxes": ambiguous,
            "note": note,
            "journal": journal,
            "discourse": discourse,
            "title": title_short,
        })
    return entries


def load_baseline_verdicts() -> dict[str, dict]:
    """Holt opus_verdict/gemini_verdict aus baseline für die JSON-Spalten."""
    baseline = json.loads(Path("docs/qcheck_gemini35_n50.json").read_text())
    out = {}
    for r in baseline["results"]:
        if r.get("article_id"):
            out[r["article_id"]] = r
    return out


def main():
    if not OBS_FILE.exists():
        print(f"ERROR: {OBS_FILE} fehlt.")
        return
    md = OBS_FILE.read_text()
    entries = parse_entries(md)
    if not entries:
        print("Keine Einträge gefunden — Format-Mismatch?")
        return

    baseline = load_baseline_verdicts()

    # bestehenden State laden, mergen
    state = {"ts_started": datetime.now().isoformat(), "answers": {}}
    if RESULTS.exists():
        state = json.loads(RESULTS.read_text())
        state.setdefault("answers", {})

    n_total = len(entries)
    n_filled = 0
    n_ambig = 0
    added_or_updated = 0
    counts = {"OPUS": 0, "GEMINI": 0, "BEIDE": 0}

    for e in entries:
        if e["ambiguous_checkboxes"]:
            n_ambig += 1
            print(f"  ⚠ #{e['num']} {e['journal']}: mehrere Checkboxen geklickt — nehme '{e['verdict']}'")
        if not e["verdict"]:
            continue
        n_filled += 1
        counts[e["verdict"]] = counts.get(e["verdict"], 0) + 1
        aid = e["article_id"]
        b = baseline.get(aid, {})
        new_entry = {
            "verdict": e["verdict"],
            "note": e["note"],
            "ts": datetime.now().isoformat(),
            "source": "obsidian",
            "journal": e["journal"] or b.get("journal", ""),
            "discourse": e["discourse"] or b.get("discourse", ""),
            "opus_verdict": b.get("opus_verdict", ""),
            "gemini_verdict": b.get("gemini_verdict", ""),
        }
        # CLI-Antworten nicht überschreiben, außer Obsidian-File ist eindeutig
        prev = state["answers"].get(aid)
        if not prev or prev.get("source") == "obsidian":
            state["answers"][aid] = new_entry
            added_or_updated += 1

    state["ts_updated"] = datetime.now().isoformat()
    RESULTS.write_text(json.dumps(state, ensure_ascii=False, indent=2))

    print()
    print(f"Audit-Parse: {n_filled}/{n_total} Einträge ausgefüllt")
    if n_ambig:
        print(f"  ⚠ {n_ambig} Einträge mit mehreren Checkboxen (jeweils erste genommen)")
    print(f"  Verteilung: {counts}")
    print(f"  Geschrieben/aktualisiert in {RESULTS}: {added_or_updated}")
    print()
    if n_filled < n_total:
        print(f"  Noch offen: {n_total - n_filled}")


if __name__ == "__main__":
    main()
