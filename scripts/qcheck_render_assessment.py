"""Rendert docs/qcheck_assessment.md aus docs/qcheck_assessment.json.

Reine Datenformatierung — keine API-Calls. Robust gegen heterogene
`bezuege`/`bemerkenswert`-Shapes (dict ODER str).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DOCS = Path("docs")
SRC = DOCS / "qcheck_assessment.json"
DST = DOCS / "qcheck_assessment.md"


def _fmt_item(b: Any, key_label: str, key_text: str) -> str:
    if isinstance(b, dict):
        return f"- _{b.get(key_label,'?')}_: {str(b.get(key_text,''))[:200]}"
    if isinstance(b, str):
        return f"- {b[:200]}"
    return f"- {str(b)[:200]}"


def fmt_entry(label: str, entry: dict) -> list[str]:
    bzg = entry.get("bezuege") or []
    bmw = entry.get("bemerkenswert") or []
    bzg_str = "\n    ".join(_fmt_item(b, "pub_id", "connection") for b in bzg[:5]) if bzg else "_(keine)_"
    bmw_str = "\n    ".join(_fmt_item(b, "topic", "detail") for b in bmw[:5]) if bmw else "_(keine)_"
    lines = [
        f"**{label}** — `{entry.get('verdict')}`",
        f"  *Kernthese:* {(entry.get('kernthese') or '')[:600]}",
        f"  *Verdict-Begründung:* {(entry.get('verdict_begruendung') or '')[:400]}",
        f"  *Bezüge:*\n    {bzg_str}",
        f"  *Bemerkenswert:*\n    {bmw_str}",
    ]
    return lines


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    results = data["results"]
    successful = [r for r in results if not r["mimo"].get("error")]
    matches = [r for r in successful if r["verdict_match"]]
    mismatches = [r for r in successful if not r["verdict_match"]]
    failed = [r for r in results if r["mimo"].get("error")]

    total_mimo_cost = sum(r["mimo"].get("cost_usd") or 0 for r in successful)
    total_opus_cost = sum(r["opus"].get("cost_usd") or 0 for r in successful)

    md = [
        "# Q-Check Assessment — MiMo vs vorhandene Opus-Datensätze",
        "",
        f"**Datum:** {data.get('ts','?')}",
        f"**Stichprobe-Plan:** 50 stratified articles (lesenswert/scannen/ignorieren-Mix)",
        f"**Tatsächlich auswertbar:** {len(successful)} (Rest hat 402/403 erlitten — OpenRouter weekly key limit)",
        f"**MiMo-Konfig:** `xiaomi/mimo-v2.5-pro`, `tool_choice='auto'`, `cache_control: ephemeral`",
        "",
        "## TL;DR",
        "",
        f"- **Verdict-Match: {len(matches)}/{len(successful)} = {len(matches)/max(len(successful),1)*100:.1f} %** (auf den auswertbaren Calls)",
        f"- **Cache greift NICHT** — alle {len(successful)} Calls cache=0 %. Mein früheres Bisection-Ergebnis (\"99 % mit `tool_choice='auto'`\") ist mit diesem Prompt-Format nicht reproduzierbar.",
        f"- **MiMo-Kosten auf den auswertbaren Calls:** ${total_mimo_cost:.4f} (Opus-Vergleich aus DB: ${total_opus_cost:.4f}).",
        f"- **Blocker:** OpenRouter weekly key limit ($10) erschöpft → restliche {len(failed)} Calls liefen ins 402. Für volle Lauf-Reproduktion entweder bis Reset warten oder Weekly-Cap bei OpenRouter erhöhen.",
        "",
        "## Aggregate (auswertbare Calls)",
        "",
        f"- Erfolgreich: {len(successful)} / {len(results)} ({len(failed)} mit 402/403 abgebrochen)",
        f"- MiMo-cost gesamt: ${total_mimo_cost:.4f}",
        f"- Opus-cost gesamt (aus articles.db): ${total_opus_cost:.4f}",
        f"- Avg/Call MiMo: ${total_mimo_cost/max(len(successful),1):.4f}",
        f"- Avg/Call Opus: ${total_opus_cost/max(len(successful),1):.4f}",
        f"- Faktor MiMo/Opus auf dieser Mini-Stichprobe: 1/{(total_opus_cost/total_mimo_cost) if total_mimo_cost else 0:.2f}",
        "",
        "### Verdict-Konfusionsmatrix",
        "",
    ]
    matrix: dict[tuple[str, str], int] = {}
    for r in successful:
        ov = r["opus"]["verdict"] or "?"
        mv = r["mimo"]["verdict"] or "FAIL"
        matrix[(ov, mv)] = matrix.get((ov, mv), 0) + 1
    verdicts = sorted({k[0] for k in matrix} | {k[1] for k in matrix})
    if verdicts:
        md.append("| Opus → / MiMo ↓ | " + " | ".join(verdicts) + " |")
        md.append("|---|" + "---|" * len(verdicts))
        for mv in verdicts:
            row_str = f"| **{mv}** |"
            for ov in verdicts:
                row_str += f" {matrix.get((ov, mv), 0)} |"
            md.append(row_str)
        md.append("")

    md.append("## Failures (402/403)")
    md.append("")
    md.append(f"_{len(failed)} Calls abgebrochen wegen OpenRouter-Wochenlimit:_")
    md.append("")
    if failed:
        first_err = failed[0]["mimo"].get("error", "")[:300]
        md.append(f"Beispiel-Fehler: `{first_err}`")
        md.append("")

    md.append("## Mismatches (Quality-Lektüre)")
    md.append("")
    md.append(f"_{len(mismatches)} von {len(successful)} auswertbaren — bitte einzeln prüfen:_")
    md.append("")
    for r in mismatches:
        md.append(f"### #{r['i']} `{r['journal']}` — {r['title'][:160]}")
        md.append(f"_article_id_: `{r['article_id']}`")
        md.append("")
        md.extend(fmt_entry("Opus", r["opus"]))
        md.append("")
        md.extend(fmt_entry("MiMo", r["mimo"]))
        md.append("")
        md.append("---")
        md.append("")

    md.append("## Matches (Stichproben-Kontrolle)")
    md.append("")
    for r in matches:
        md.append(f"### #{r['i']} `{r['journal']}` — {r['title'][:160]}  → beide `{r['opus']['verdict']}`")
        md.append(f"_article_id_: `{r['article_id']}`")
        md.append("")
        md.extend(fmt_entry("Opus", r["opus"]))
        md.append("")
        md.extend(fmt_entry("MiMo", r["mimo"]))
        md.append("")
        md.append("---")
        md.append("")

    DST.write_text("\n".join(md), encoding="utf-8")
    print(f"  -> {DST}  ({len(successful)} auswertbar, {len(matches)} Match, {len(mismatches)} Mismatch, {len(failed)} Failed)")


if __name__ == "__main__":
    main()
