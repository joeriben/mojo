"""Baut docs/qcheck_gemini35_divergence_audit.md — eine zum Ausfüllen
gedachte Tabelle der 24 Divergenzen aus qcheck_gemini35_n50.json.

Pro Divergenz:
- Titel, Journal, Citation-Hits
- Opus-Verdict + Opus-Begründung (aus articles.agent_entry_json)
- Gemini low-effort: Verdict + Kernthese + Begründung
- Gemini high-effort: Verdict + Begründung (aus retest.json)
- Checkbox-Zeile zum Ankreuzen
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

DOCS = Path("docs")
DB_PATH = Path("articles.db")


def main():
    baseline = json.loads((DOCS / "qcheck_gemini35_n50.json").read_text())
    retest = {r["article_id"]: r for r in json.loads((DOCS / "qcheck_gemini35_retest.json").read_text())["results"]}
    divergences = [r for r in baseline["results"] if "gemini_verdict" in r and not r.get("match")]

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    md = [
        "# Gemini 3.5 Flash — Divergenz-Audit (Benjamin sichtet)",
        "",
        f"**Stand:** {baseline['ts'][:10]}",
        f"**Ziel:** Pro Divergenz entscheiden, wer eigentlich recht hat — Opus oder Gemini.",
        f"Wenn Gemini's Begründung tragfähig ist, ist der \"Fehler\" möglicherweise eine produktive Inklusions-Erweiterung.",
        "",
        "**Ausfüllen:** Pro Eintrag ein `[x]` setzen — `OPUS`, `GEMINI`, oder `BEIDE` (beide Lesarten vertretbar).",
        "",
        f"**Übersicht:** {len(divergences)} Divergenzen aus N=50.",
        "",
        "---",
        "",
    ]

    for i, r in enumerate(divergences, 1):
        aid = r["article_id"]
        # Opus-Begründung aus DB ziehen
        row = conn.execute("SELECT title, agent_entry_json, journal_full FROM articles WHERE id=?", (aid,)).fetchone()
        opus_entry = {}
        if row and row["agent_entry_json"]:
            try:
                opus_entry = json.loads(row["agent_entry_json"])
            except Exception:
                opus_entry = {}

        opus_begr = opus_entry.get("verdict_begruendung", "(keine Begründung in DB)")
        opus_kern = opus_entry.get("kernthese", "")

        # Gemini high-effort Daten
        retest_r = retest.get(aid, {})

        md.append(f"## {i}. {r['journal']} · `{r['discourse']}` — {row['title'][:130] if row else r['title']}")
        md.append("")
        md.append(f"_article_id_: `{aid}`")
        md.append(f"_Citation-Hits_: high={r['citation_hits_high']}, med={r['citation_hits_med']}")
        md.append("")
        md.append(f"### Opus (Goldstandard): **`{r['opus_verdict']}`**")
        if opus_kern:
            md.append(f"**Opus-Kernthese:** {opus_kern[:500]}")
        md.append(f"**Opus-Begründung:** {opus_begr[:500]}")
        md.append("")
        md.append(f"### Gemini (low-effort): **`{r['gemini_verdict']}`**")
        md.append(f"**Gemini-Kernthese:** {r['gemini_kernthese'][:500]}")
        md.append(f"**Gemini-Begründung:** {r['gemini_begruendung'][:500]}")
        md.append("")
        if retest_r.get("retest_verdict"):
            same_high = retest_r["retest_verdict"] == r["gemini_verdict"]
            tag = " (unverändert)" if same_high else " (geändert)"
            md.append(f"### Gemini (high-effort){tag}: **`{retest_r['retest_verdict']}`**")
            md.append(f"**Gemini-high-Begründung:** {retest_r.get('retest_begruendung','')[:500]}")
            md.append("")
        md.append("### Wer hat recht?")
        md.append("")
        md.append("- [ ] **OPUS** (Gemini liegt daneben)")
        md.append("- [ ] **GEMINI** (Opus zu konservativ / Gemini findet einen echten Anschluss)")
        md.append("- [ ] **BEIDE** (Lesart vertretbar, Grenzfall)")
        md.append("")
        md.append("**Anmerkung:** ")
        md.append("")
        md.append("---")
        md.append("")

    out_path = DOCS / "qcheck_gemini35_divergence_audit.md"
    out_path.write_text("\n".join(md), encoding="utf-8")
    print(f"  -> {out_path}")
    print(f"  {len(divergences)} Divergenzen aufbereitet")


if __name__ == "__main__":
    main()
