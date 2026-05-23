"""Gemini 3.5 Flash mit MiMo v2-Patches auf den N=50-Set.

Apples-to-Apples zum Baseline-Lauf (qcheck_gemini35_n50.json, 26/50 = 52%):
- gleiche 50 Artikel (gleicher seed, gleiche Stichprobenkonstruktion)
- gleiche Modell-Konfig (reasoning.effort=low, kein max_tokens-Cap, gleiches Tool-Schema)
- EINZIGE Änderung: ASSESSMENT_OUTRO + MIMO_OUTRO_PATCHES (Regel A/B/C)

Hypothese: Die MiMo-Patches adressieren v.a. UNTER-Inklusion (Regel A: Zitations-Trigger,
Regel B: pragmatische Übersetzung). Bei Gemini ist das Problem ÜBER-Inklusion. Aber
Regel C (Cultural-Resilience-Abgrenzung) zielt direkt auf Gemini's #25-Pattern (Zembylas
und ähnliche Anti-Komplizenschafts/Resistance-Artikel).

Mögliche Ergebnisse:
- A) Match-Rate steigt → Patches helfen auch hier
- B) Bleibt bei ~52% → modellinhärenter Bias dominiert
- C) Wird schlechter → Regel A treibt Gemini noch weiter zu lesenswert
"""

from __future__ import annotations

import json
import random
import sqlite3
import sys
import time
from collections import Counter, defaultdict
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

# MiMo-Patches 1:1 übernommen aus scripts/qcheck_mimo_promptv2.py
MIMO_OUTRO_PATCHES = """

=== ZUSÄTZLICHE REGELN (Kalibrierung) ===

**Regel A — Zitations-Trigger (hartes Inklusionskriterium):**
Wenn der Citation-Tracker im User-Prompt einen "Sicheren Treffer" oder "Wahrscheinlichen
Treffer" meldet, ist das Verdict MINDESTENS `lesenswert` — unabhängig von theoretischer
Tradition oder thematischer Distanz. Die Begründung MUSS die Zitation explizit aufgreifen
und eine Hypothese formulieren, WIE die Autoren die zitierte Arbeit nutzen (affirmativ,
kritisch, modifizierend, als Grundlage, als Kontrast).

**Regel B — Anschluss auch bei pragmatischer Übersetzung:**
Auch wenn das theoretische Vokabular fremd ist, gilt: wenn der Text einen SCHLÜSSELBEGRIFF
der eigenen Arbeit (Bildung, Datafizierung, Medienbildung, Resilienz, ästhetische Praxis,
agentieller Realismus, Wahrnehmungskrise, Black-Box, Postdigitalität, Subjektivierung, …)
substantiell verhandelt — affirmativ, kritisch oder pragmatisch übersetzend — ist er
`lesenswert`. Eine didaktische/pragmatische Lesart einer der eigenen Theoriearbeiten ist
ANLASS zur Lektüre, KEIN Abwertungsgrund. "Andere theoretische Tradition" ist kein
Ausschlussgrund, wenn die zentralen Begriffe geteilt werden.

**Regel C — Cultural Resilience negativ abgrenzen:**
"Cultural Resilience" im Jörissen-Forschungsprogramm ist spezifisch
ÄSTHETISCH-BILDUNGSTHEORETISCH fundiert (Vergegenständlichung, Resonanz, ästhetische
Welterzeugung, kulturelle Praxis als Resilienzform). Es ist NICHT identisch mit:
- politischer Resistance / Widerstandspädagogik (Ahmed/Butler/Zembylas-Stil)
- postkolonialer Komplizenschafts-Pädagogik
- affekttheoretischer Mobilisierung als Selbstzweck
- Resilienz im psychologisch-individuellen Sinn

Texte, die diese politisch-affektiven oder psychologischen Konzepte ohne ästhetisch-
bildungstheoretischen Anschluss verhandeln, sind NICHT automatisch `lesenswert` für
dieses Programm. Eine reine Keyword-Übereinstimmung ("resistance", "resilience") genügt
NICHT.
"""

PATCHED_OUTRO = ASSESSMENT_OUTRO + MIMO_OUTRO_PATCHES

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
    print(f"System-Prompt (PATCHED): {len(sys_prompt):,} chars (Baseline war 112,421)")

    corpus = json.loads(CORPUS_JSON.read_text())
    authored_all = corpus.get("authored_all", [])
    store = Store()

    # Baseline laden für Vergleich
    baseline = {r["article_id"]: r for r in json.loads((DOCS / "qcheck_gemini35_n50.json").read_text())["results"]}

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
            "patched_begruendung": (gem.get("verdict_begruendung") or "")[:400],
            "baseline_verdict": baseline_v,
            "match_patch": match_patch, "match_baseline": match_baseline,
            "changed": change, "cost_usd": c,
            "tokens_in": res.get("tokens_in"), "tokens_out": res.get("tokens_out"),
            "latency_s": res.get("latency_s"), "finish_reason": res.get("finish_reason"),
            "citation_hits_high": sum(1 for h in hits if h.confidence == "high"),
            "citation_hits_med": sum(1 for h in hits if h.confidence == "medium"),
        })
        print(f"  [{idx:>2}/50] {s['journal']:10s} disc={s['discourse'][:16]:16s} "
              f"opus={opus_v:<13s} base={(baseline_v or '?'):<13s} patch={(new_v or 'None'):<13s} "
              f"{mark} ${c:.4f}")

    valid = [r for r in results if "patched_verdict" in r]
    match_patch_n = sum(1 for r in valid if r["match_patch"])
    match_baseline_n = sum(1 for r in valid if r["match_baseline"])
    changed = sum(1 for r in valid if r["changed"])
    changed_better = sum(1 for r in valid if r["changed"] and r["match_patch"] and not r["match_baseline"])
    changed_worse = sum(1 for r in valid if r["changed"] and not r["match_patch"] and r["match_baseline"])

    print()
    print(f"  Patches geändert: {changed}/50")
    print(f"    davon zum Besseren: {changed_better} (Patch korrekt, Baseline falsch)")
    print(f"    davon zum Schlechteren: {changed_worse} (Patch falsch, Baseline korrekt)")
    print(f"  Match-Rate:  Baseline {match_baseline_n}/50  →  Patched {match_patch_n}/50  ({(match_patch_n-match_baseline_n):+d})")
    print(f"  Kosten: ${total_cost:.4f}")

    # Konfusionsmatrix Patched
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in valid:
        confusion[r["opus_verdict"]][r["patched_verdict"] or "(none)"] += 1

    out = {
        "ts": datetime.now().isoformat(),
        "model": GEMINI_35_FLASH.model,
        "config": {"reasoning_effort": "low", "patches": "MIMO_OUTRO_PATCHES (A/B/C)"},
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
    (DOCS / "qcheck_gemini35_patched_n50.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str))

    md = [
        "# Gemini 3.5 Flash + MiMo-Patches — N=50 Vergleich zur Baseline",
        "",
        f"**Datum:** {datetime.now().isoformat()}",
        f"**Konfig:** PATCHED_OUTRO = ASSESSMENT_OUTRO + MIMO_OUTRO_PATCHES (Regel A/B/C aus qcheck_mimo_promptv2.py)",
        f"**Gleiche Stichprobe** wie Baseline (seed=42), **gleiche Modell-Konfig** (reasoning.effort=low)",
        "",
        f"## Headline: Baseline **{match_baseline_n}/50 = {match_baseline_n*2}%** → Patched **{match_patch_n}/50 = {match_patch_n*2}%** ({(match_patch_n-match_baseline_n):+d})",
        f"**Kosten:** ${total_cost:.4f}",
        "",
        f"- {changed}/50 Verdicts haben sich geändert",
        f"- davon **{changed_better} zum Besseren** (Patch korrigiert Baseline-Fehler)",
        f"- davon **{changed_worse} zum Schlechteren** (Patch zerstört Baseline-Treffer)",
        f"- Saldo: {changed_better - changed_worse:+d}",
        "",
        "## Konfusionsmatrix (Patched)",
        "",
        "| Opus → Gemini patched | ignorieren | scannen | lesenswert | pflichtlektuere |",
        "|---|---:|---:|---:|---:|",
    ]
    for opus_v in VERDICTS:
        cells = [confusion[opus_v].get(gem_v, 0) for gem_v in VERDICTS]
        cells_fmt = [f"**{c}**" if VERDICTS[i] == opus_v else f"{c}" for i, c in enumerate(cells)]
        md.append(f"| **{opus_v}** | {cells_fmt[0]} | {cells_fmt[1]} | {cells_fmt[2]} | {cells_fmt[3]} |")
    md.append("")

    md.append("## Geänderte Verdicts (Patches haben Verdict gegenüber Baseline geflippt)")
    md.append("")
    md.append("| Journal | Opus | Baseline | Patched | Effekt | Patched-Begründung |")
    md.append("|---|---|---|---|---|---|")
    for r in valid:
        if not r["changed"]: continue
        if r["match_patch"] and not r["match_baseline"]: eff = "✓ besser"
        elif not r["match_patch"] and r["match_baseline"]: eff = "✗ schlechter"
        elif r["match_patch"] and r["match_baseline"]: eff = "= (beide korrekt)"
        else: eff = "≈ anders falsch"
        md.append(f"| {r['journal']} | `{r['opus_verdict']}` | `{r['baseline_verdict']}` | "
                  f"`{r['patched_verdict']}` | {eff} | {r['patched_begruendung'][:180]} |")
    md.append("")

    (DOCS / "qcheck_gemini35_patched_n50.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  -> docs/qcheck_gemini35_patched_n50.md")


if __name__ == "__main__":
    main()
