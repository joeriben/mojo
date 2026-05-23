"""Gemini 3.5 Flash mit V3-Patches (Konsistenz + Beheimatungen) auf N=50.

V3 ersetzt die MiMo-Patches (die hier nicht halfen, netto -1) durch zwei
diagnostisch zielgenauere Patches, abgeleitet aus Benjamin's manueller
Bewertung der 14 von 24 Divergenzen:

- **Konsistenz-Regel**: wenn die eigene Begründung "keine Anknüpfung" / "kein
  spezifischer Anschluss" / "außerhalb" enthält, MUSS verdict=ignorieren sein.
  Beobachtet z.B. an Audit-Eintrag #6/#7: Gemini erkennt mangelnden Anschluss
  in der Begründung, klassifiziert aber trotzdem als lesenswert/scannen.

- **Beheimatungen-Stärkung**: die 5 disziplinären Beheimatungen Benjamins als
  gleichrangige Anschluss-Kanäle, nicht nur die aktiven Projekte. Beobachtet
  an Audit-Eintrag #15: klassisch-analytische Bildungsphilosophie zur
  Lehrerrolle gehört zu Beheimatung 1 (Allgemeine Pädagogik), wurde aber
  übersehen weil der Prompt nur Projekte priorisiert.

Apples-to-Apples zum Baseline-Lauf (qcheck_gemini35_n50.json, 26/50 = 52%):
gleiche Stichprobe (seed=42), gleiche Modell-Konfig (reasoning.effort=low).
"""

from __future__ import annotations

import json
import random
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from journal_bot.agent import (
    ASSESSMENT_OUTRO,
    TOOLS_SUBMIT_ONLY,
    _format_new_article,
    build_system_prompt,
)
from journal_bot.citation_tracker import find_citations, format_for_agent
from journal_bot.multi_provider import Route, build_client, extract_stats, make_messages
from journal_bot.settings import CORPUS_JSON, SUMMARIES_JSON
from journal_bot.store import Store

V3_PATCHES = """

=== ZUSÄTZLICHE REGELN (V3 Kalibrierung) ===

**Regel 1 — Konsistenz zwischen Begründung und Verdict:**
Bevor du das Verdict festlegst, prüfe deine eigene verdict_begruendung. Wenn
sie eine der folgenden Formulierungen (oder eine sinngleiche) enthält:
- "keine Anknüpfungspunkte"
- "kein spezifischer Anschluss"
- "kein konkreter Bezug"
- "außerhalb [...] Forschungsfeld[es]"
- "nur tangential"
- "berührt nicht"
- "keine substanzielle Verbindung"
... dann MUSS verdict="ignorieren" sein. Die Verdict-Stufen "scannen" und
"lesenswert" setzen einen positiv formulierten, konkret benannten Anschluss
voraus. Eine Begründung darf nicht in zwei Richtungen lesen — entweder es gibt
einen Anschluss (dann benenne ihn), oder es gibt keinen (dann ignorieren).

**Regel 2 — Fünf disziplinäre Beheimatungen als gleichrangige Anschluss-Kanäle:**
Anschluss-Möglichkeiten existieren NICHT NUR über die aktiven Projekte
(Cultural Resilience, MetaKuBi, AI4ArtsEd, ComeArts, DiäS-KuBi), sondern auch
über die fünf disziplinären Beheimatungen Benjamins:

1. **Allgemeine Pädagogik / Bildungstheorie** (institutionelle Heimat) — auch
   klassisch-analytische Bildungsphilosophie, epistemische Rolle des
   Lehrenden, Subjektivierungstheorie, Erziehungs- und Schultheorie,
   Bildungsphilosophie im weiten Sinn.
2. **Posthumanismus / STS / Resilienz**
3. **Medienbildung / Medienpädagogik**
4. **Pädagogische Medienforschung / Medienwissenschaft**
5. **Kulturwissenschaft / Ästhetik**

Ein Artikel KANN über jede dieser Beheimatungen anschlussfähig sein, auch
ohne Bezug zu einem aktuellen Projekt. Klassische Bildungsphilosophie zur
Lehrerrolle ist für Beheimatung 1 relevant — verdict mindestens "scannen",
ggf. "lesenswert" wenn substanziell. Aktive Projekte sind EIN Anschluss-Kanal
unter sechs (5 Beheimatungen + aktive Projekte), nicht der dominante.
"""

PATCHED_OUTRO = ASSESSMENT_OUTRO + V3_PATCHES

DOCS = Path("docs")
DB_PATH = Path("articles.db")
DISKURS_JSON = Path("diskursraeume.json")
SEED = 42

GEMINI_35_FLASH = Route(
    provider="openrouter",
    model="google/gemini-3.5-flash",
    label="Gemini 3.5 Flash (OpenRouter)",
    input_usd_per_mtok=1.5,
    output_usd_per_mtok=9.0,
    region="US",
    dsgvo=False,
    supports_anthropic_cache=False,
    has_implicit_cache=True,
)

DISCOURSES = [
    "erziehungswiss", "digitale_kultur", "medienpaed",
    "bildungstheorie", "aesthetische_kulturelle_bildung",
]
PER_DISCOURSE = 10
VERDICTS = ("ignorieren", "scannen", "lesenswert", "pflichtlektuere")


def build_sample() -> list[dict[str, Any]]:
    """Identische Stichprobe wie qcheck_gemini35_flash_n50.py (gleicher seed)."""
    clusters = json.loads(DISKURS_JSON.read_text())["journal_clusters"]
    disc_journals: dict[str, list[str]] = defaultdict(list)
    for j, ds in clusters.items():
        for d in ds:
            disc_journals[d].append(j)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rng = random.Random(SEED)

    sample: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for disc in DISCOURSES:
        journals = disc_journals[disc]
        placeholders = ",".join("?" * len(journals))
        q = f"""
            SELECT id, journal_short, agent_verdict, title
            FROM articles
            WHERE journal_short IN ({placeholders})
              AND agent_verdict IS NOT NULL
              AND tokens_in > 25000
              AND agent_entry_json NOT LIKE '%C-Tier%'
        """
        rows = [dict(r) for r in conn.execute(q, journals).fetchall()]
        rows = [r for r in rows if r["id"] not in seen_ids]
        by_verdict: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            by_verdict[r["agent_verdict"]].append(r)
        for v in by_verdict:
            rng.shuffle(by_verdict[v])

        chosen: list[dict] = []
        for v in ("pflichtlektuere", "lesenswert"):
            take = min(len(by_verdict[v]), PER_DISCOURSE - len(chosen))
            chosen.extend(by_verdict[v][:take])

        remaining = PER_DISCOURSE - len(chosen)
        scn_quota = remaining // 2
        ign_quota = remaining - scn_quota
        chosen.extend(by_verdict["scannen"][:scn_quota])
        chosen.extend(by_verdict["ignorieren"][:ign_quota])

        for r in chosen:
            seen_ids.add(r["id"])
            sample.append({
                "article_id": r["id"], "journal": r["journal_short"],
                "title": r["title"][:120], "opus_verdict": r["agent_verdict"],
                "discourse": disc,
            })
    conn.close()
    return sample


def call_gemini(system_prompt: str, user_content: str) -> dict[str, Any]:
    route = GEMINI_35_FLASH
    client = build_client(route.provider)
    messages = make_messages(system_prompt, user_content, route)
    params = {
        "model": route.model,
        "messages": messages,
        "tools": TOOLS_SUBMIT_ONLY,
        "tool_choice": "auto",
        "extra_body": {
            "usage": {"include": True},
            "reasoning": {"effort": "low"},
        },
    }
    t0 = time.time()
    try:
        resp = client.chat.completions.create(**params)
    except Exception as e:
        return {"error": str(e)[:400]}
    latency = time.time() - t0
    choice = resp.choices[0]
    msg = choice.message
    s = extract_stats(resp.usage, route)

    tool_args = None
    for tc in (getattr(msg, "tool_calls", None) or []):
        if tc.function.name == "submit_digest_entry":
            try:
                tool_args = json.loads(tc.function.arguments)
            except Exception:
                tool_args = {"_raw": tc.function.arguments}
            break

    return {
        "finish_reason": choice.finish_reason,
        "tokens_in": s.tokens_in,
        "tokens_out": s.tokens_out,
        "cost_usd": round(s.cost_usd, 5),
        "latency_s": round(latency, 2),
        "tool_args": tool_args,
    }


def main():
    sample = build_sample()
    print(f"Stichprobe: {len(sample)} Artikel (gleicher seed=42 wie Baseline)")

    summaries = json.loads(SUMMARIES_JSON.read_text())["summaries"]
    sys_prompt = build_system_prompt(summaries, outro=PATCHED_OUTRO)
    print(f"System-Prompt (V3): {len(sys_prompt):,} chars")

    corpus = json.loads(CORPUS_JSON.read_text())
    authored_all = corpus.get("authored_all", [])
    store = Store()

    baseline = {r["article_id"]: r for r in json.loads(
        (DOCS / "qcheck_gemini35_n50.json").read_text())["results"]}

    results: list[dict] = []
    total_cost = 0.0

    for idx, s in enumerate(sample, 1):
        aid = s["article_id"]
        with store._conn() as conn:
            row = dict(conn.execute("SELECT * FROM articles WHERE id=?", (aid,)).fetchone())

        new_art = {
            "title": row["title"],
            "authors": json.loads(row.get("authors_json") or "[]"),
            "abstract": row.get("openalex_abstract") or row.get("abstract") or "",
            "doi": row.get("doi") or "", "url": row.get("url") or "",
            "journal": row.get("journal_full") or row.get("journal_short") or "",
        }
        enr = {
            "openalex_abstract": row.get("openalex_abstract") or "",
            "references_crossref": json.loads(row.get("crossref_refs") or "[]") or [],
            "openalex_concepts": json.loads(row.get("openalex_concepts") or "[]") or [],
            "openalex_topics": json.loads(row.get("openalex_topics") or "[]") or [],
        }
        hits = find_citations(enr["references_crossref"], authored_all)
        user_content = _format_new_article(new_art, enr) + format_for_agent(hits)

        res = call_gemini(sys_prompt, user_content)
        if res.get("error"):
            print(f"  [{idx:>2}/50] {s['journal']:10s} ERROR {res['error'][:120]}")
            results.append({**s, "error": res["error"][:300]})
            continue

        c = res.get("cost_usd") or 0.0
        total_cost += c
        gem = res.get("tool_args") or {}
        new_v = gem.get("verdict")
        baseline_v = baseline.get(aid, {}).get("gemini_verdict")
        opus_v = s["opus_verdict"]
        match_patch = (new_v == opus_v)
        match_baseline = (baseline_v == opus_v)
        change = (new_v != baseline_v)
        mark = "✓✓" if match_patch and not match_baseline else "✓" if match_patch else "✗"

        results.append({
            **s, "patched_verdict": new_v,
            "patched_begruendung": (gem.get("verdict_begruendung") or "")[:500],
            "patched_kernthese": (gem.get("kernthese") or "")[:400],
            "baseline_verdict": baseline_v,
            "match_patch": match_patch, "match_baseline": match_baseline,
            "changed": change, "cost_usd": c,
            "tokens_in": res.get("tokens_in"), "tokens_out": res.get("tokens_out"),
            "latency_s": res.get("latency_s"), "finish_reason": res.get("finish_reason"),
            "citation_hits_high": sum(1 for h in hits if h.confidence == "high"),
            "citation_hits_med": sum(1 for h in hits if h.confidence == "medium"),
        })
        print(f"  [{idx:>2}/50] {s['journal']:10s} disc={s['discourse'][:16]:16s} "
              f"opus={opus_v:<13s} base={(baseline_v or '?'):<13s} v3={(new_v or 'None'):<13s} "
              f"{mark} ${c:.4f}")

    valid = [r for r in results if "patched_verdict" in r]
    match_patch_n = sum(1 for r in valid if r["match_patch"])
    match_baseline_n = sum(1 for r in valid if r["match_baseline"])
    changed = sum(1 for r in valid if r["changed"])
    changed_better = sum(1 for r in valid if r["changed"] and r["match_patch"] and not r["match_baseline"])
    changed_worse = sum(1 for r in valid if r["changed"] and not r["match_patch"] and r["match_baseline"])

    print()
    print(f"  V3-Patches geändert: {changed}/50")
    print(f"    davon zum Besseren: {changed_better} (V3 korrekt, Baseline falsch)")
    print(f"    davon zum Schlechteren: {changed_worse} (V3 falsch, Baseline korrekt)")
    print(f"  Match-Rate:  Baseline {match_baseline_n}/50  →  V3 {match_patch_n}/50  ({(match_patch_n-match_baseline_n):+d})")
    print(f"  Kosten: ${total_cost:.4f}")

    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in valid:
        confusion[r["opus_verdict"]][r["patched_verdict"] or "(none)"] += 1

    out = {
        "ts": datetime.now().isoformat(),
        "model": GEMINI_35_FLASH.model,
        "config": {"reasoning_effort": "low", "patches": "V3 (Konsistenz + Beheimatungen)"},
        "n": len(valid),
        "matched_patched": match_patch_n,
        "matched_baseline": match_baseline_n,
        "delta": match_patch_n - match_baseline_n,
        "changed": changed,
        "changed_better": changed_better,
        "changed_worse": changed_worse,
        "cost_total_usd": round(total_cost, 4),
        "confusion_patched": {k: dict(v) for k, v in confusion.items()},
        "results": results,
    }
    (DOCS / "qcheck_gemini35_patched_v3.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str))

    md = [
        "# Gemini 3.5 Flash + V3-Patches (Konsistenz + Beheimatungen) — N=50",
        "",
        f"**Datum:** {datetime.now().isoformat()}",
        "**Konfig:** ASSESSMENT_OUTRO + V3-Patches (Konsistenz-Regel + 5 Beheimatungen)",
        "**Gleiche Stichprobe** wie Baseline (seed=42), **gleiche Modell-Konfig** (reasoning.effort=low)",
        "",
        f"## Headline: Baseline **{match_baseline_n}/50 = {match_baseline_n*2}%** → V3 **{match_patch_n}/50 = {match_patch_n*2}%** ({(match_patch_n-match_baseline_n):+d})",
        f"**Kosten:** ${total_cost:.4f}",
        "",
        f"- {changed}/50 Verdicts haben sich geändert",
        f"- davon **{changed_better} zum Besseren** (V3 korrigiert Baseline-Fehler)",
        f"- davon **{changed_worse} zum Schlechteren** (V3 zerstört Baseline-Treffer)",
        f"- Saldo: {changed_better - changed_worse:+d}",
        "",
        "## Konfusionsmatrix (V3)",
        "",
        "| Opus → Gemini V3 | ignorieren | scannen | lesenswert | pflichtlektuere |",
        "|---|---:|---:|---:|---:|",
    ]
    for opus_v in VERDICTS:
        cells = [confusion[opus_v].get(gem_v, 0) for gem_v in VERDICTS]
        cells_fmt = [f"**{c}**" if VERDICTS[i] == opus_v else f"{c}" for i, c in enumerate(cells)]
        md.append(f"| **{opus_v}** | {cells_fmt[0]} | {cells_fmt[1]} | {cells_fmt[2]} | {cells_fmt[3]} |")
    md.append("")

    md.append("## Geänderte Verdicts (V3 vs. Baseline)")
    md.append("")
    md.append("| Journal | Opus | Baseline | V3 | Effekt | V3-Begründung |")
    md.append("|---|---|---|---|---|---|")
    for r in valid:
        if not r["changed"]:
            continue
        if r["match_patch"] and not r["match_baseline"]:
            eff = "✓ besser"
        elif not r["match_patch"] and r["match_baseline"]:
            eff = "✗ schlechter"
        elif r["match_patch"] and r["match_baseline"]:
            eff = "= (beide korrekt)"
        else:
            eff = "≈ anders falsch"
        md.append(f"| {r['journal']} | `{r['opus_verdict']}` | `{r['baseline_verdict']}` | "
                  f"`{r['patched_verdict']}` | {eff} | {r['patched_begruendung'][:180]} |")
    md.append("")

    (DOCS / "qcheck_gemini35_patched_v3.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  -> docs/qcheck_gemini35_patched_v3.md")


if __name__ == "__main__":
    main()
