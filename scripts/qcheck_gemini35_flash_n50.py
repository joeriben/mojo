"""Q-Check N=50: Gemini 3.5 Flash gegen Opus-Goldstandard,
stratifiziert über 5 Diskursräume × alle drei Verdicts.

Stichprobenkonstruktion:
- 5 Diskursräume: erziehungswiss, digitale_kultur, medienpaed,
  bildungstheorie, aesthetische_kulturelle_bildung (= Benjamins 5 disziplinäre
  Beheimatungen, siehe CLAUDE.md)
- Pro Raum ~10 Artikel, mit Verdict-Mix:
    * alle verfügbaren `pflichtlektuere` (1 gesamt)
    * möglichst viele `lesenswert` (34 gesamt, sehr knapp)
    * aufgefüllt mit random scannen + ignorieren (50/50)
- Artikel-Pool: nur Opus-Vollanalysen (tokens_in > 25000, kein C-Tier-Placeholder)
  → Goldstandard ist anthropic/claude-opus-4.6 aus articles.agent_verdict
- Deduplikation: jeder Artikel max 1× insgesamt, auch wenn er in zwei Räumen wäre

Modell unter Test: google/gemini-3.5-flash via OpenRouter
- max_tokens=8192, reasoning.effort=low (Thinking-Mode würde sonst Output sprengen)
- Erwartete Kosten: 50 × ~$0.055 ≈ $2.75

Output:
- docs/qcheck_gemini35_n50.json — Rohdaten + Per-Artikel-Verdicts
- docs/qcheck_gemini35_n50.md — Report mit Konfusionsmatrix + Per-Diskursraum-Tabelle
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

DOCS = Path("docs")
DB_PATH = Path("articles.db")
DISKURS_JSON = Path("diskursraeume.json")
SEED = 42  # reproduzierbare Stichprobe

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

# 5 wichtigste Diskursräume — Benjamins disziplinäre Beheimatungen
DISCOURSES = [
    "erziehungswiss",
    "digitale_kultur",
    "medienpaed",
    "bildungstheorie",
    "aesthetische_kulturelle_bildung",
]
PER_DISCOURSE = 10
VERDICTS = ("ignorieren", "scannen", "lesenswert", "pflichtlektuere")


# ────────────────────────────────────────────────────────────────────
# Stichprobenkonstruktion
# ────────────────────────────────────────────────────────────────────


def build_sample() -> list[dict[str, Any]]:
    """Liefert die N=50-Stichprobe als Liste {article_id, journal, opus_verdict, discourse}."""
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
        # Pool: Opus-Vollanalysen für diesen Raum
        q = f"""
            SELECT id, journal_short, agent_verdict, title
            FROM articles
            WHERE journal_short IN ({placeholders})
              AND agent_verdict IS NOT NULL
              AND tokens_in > 25000
              AND agent_entry_json NOT LIKE '%C-Tier%'
        """
        rows = [dict(r) for r in conn.execute(q, journals).fetchall()]
        # Nur Artikel die noch nicht in Stichprobe sind (cross-discourse dedup)
        rows = [r for r in rows if r["id"] not in seen_ids]
        by_verdict: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            by_verdict[r["agent_verdict"]].append(r)
        for v in by_verdict:
            rng.shuffle(by_verdict[v])

        chosen: list[dict] = []
        # Greedy: alle pflichtlektuere, alle lesenswert (bis Quote), Rest 50/50 scn/ign
        for v in ("pflichtlektuere", "lesenswert"):
            take = min(len(by_verdict[v]), PER_DISCOURSE - len(chosen))
            chosen.extend(by_verdict[v][:take])

        remaining = PER_DISCOURSE - len(chosen)
        # Aufteilen: rest // 2 scannen, rest - rest//2 ignorieren (oder umgekehrt)
        scn_quota = remaining // 2
        ign_quota = remaining - scn_quota
        chosen.extend(by_verdict["scannen"][:scn_quota])
        chosen.extend(by_verdict["ignorieren"][:ign_quota])

        for r in chosen:
            seen_ids.add(r["id"])
            sample.append({
                "article_id": r["id"],
                "journal": r["journal_short"],
                "title": r["title"][:120],
                "opus_verdict": r["agent_verdict"],
                "discourse": disc,
            })

    conn.close()
    return sample


# ────────────────────────────────────────────────────────────────────
# Gemini-Call
# ────────────────────────────────────────────────────────────────────


def call_gemini(system_prompt: str, user_content: str) -> dict[str, Any]:
    route = GEMINI_35_FLASH
    client = build_client(route.provider)
    messages = make_messages(system_prompt, user_content, route)
    params = {
        "model": route.model,
        "max_tokens": 8192,
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
        "cached_read": s.cached_read,
        "cost_usd": round(s.cost_usd, 5),
        "cache_pct": round(s.cached_read / max(s.tokens_in, 1) * 100, 1),
        "latency_s": round(latency, 2),
        "text": msg.content or "",
        "tool_args": tool_args,
        "fallback_cost": s.fallback_cost,
    }


# ────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────


def main():
    sample = build_sample()
    print(f"Stichprobe: {len(sample)} Artikel über {len(DISCOURSES)} Diskursräume")
    composition = Counter((s["discourse"], s["opus_verdict"]) for s in sample)
    for disc in DISCOURSES:
        row = {v: composition.get((disc, v), 0) for v in VERDICTS}
        print(f"  {disc:32s}  ign={row['ignorieren']:2d} scn={row['scannen']:2d} "
              f"les={row['lesenswert']:2d} pl={row['pflichtlektuere']:2d}")

    summaries = json.loads(SUMMARIES_JSON.read_text())["summaries"]
    sys_prompt = build_system_prompt(summaries, outro=ASSESSMENT_OUTRO)
    print(f"\nSystem-Prompt (production): {len(sys_prompt):,} chars")

    corpus = json.loads(CORPUS_JSON.read_text())
    authored_all = corpus.get("authored_all", [])
    store = Store()

    results: list[dict] = []
    total_cost = 0.0
    safety_break = False

    for idx, s in enumerate(sample, 1):
        aid = s["article_id"]
        with store._conn() as conn:
            row = conn.execute("SELECT * FROM articles WHERE id=?", (aid,)).fetchone()
            if row is None:
                print(f"  [{idx:>2}/{len(sample)}] {aid[:10]}  MISSING IN DB")
                continue
            row = dict(row)

        new_art = {
            "title": row["title"],
            "authors": json.loads(row.get("authors_json") or "[]"),
            "abstract": row.get("openalex_abstract") or row.get("abstract") or "",
            "doi": row.get("doi") or "",
            "url": row.get("url") or "",
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

        if safety_break:
            print(f"  [{idx:>2}/{len(sample)}] skip (safety break)")
            continue

        res = call_gemini(sys_prompt, user_content)
        if res.get("error"):
            print(f"  [{idx:>2}/{len(sample)}] {s['journal']:10s} ERROR — {res['error'][:120]}")
            results.append({
                **s, "error": res["error"][:400],
            })
            continue

        c = res.get("cost_usd") or 0.0
        total_cost += c
        if idx >= 5 and total_cost / idx > 0.15:
            safety_break = True
            print(f"  ⚠ Safety-Break: avg ${total_cost/idx:.4f}/call > $0.15")

        gem = res.get("tool_args") or {}
        gem_verdict = gem.get("verdict")
        match = (gem_verdict == s["opus_verdict"])
        mark = "✓" if match else "✗"

        results.append({
            **s,
            "gemini_verdict": gem_verdict,
            "gemini_kernthese": (gem.get("kernthese") or "")[:500],
            "gemini_begruendung": (gem.get("verdict_begruendung") or "")[:500],
            "cost_usd": c,
            "tokens_in": res.get("tokens_in"),
            "tokens_out": res.get("tokens_out"),
            "cache_pct": res.get("cache_pct"),
            "latency_s": res.get("latency_s"),
            "finish_reason": res.get("finish_reason"),
            "fallback_cost": res.get("fallback_cost"),
            "match": match,
            "citation_hits_high": sum(1 for h in hits if h.confidence == "high"),
            "citation_hits_med": sum(1 for h in hits if h.confidence == "medium"),
        })
        print(f"  [{idx:>2}/{len(sample)}] {s['journal']:10s} disc={s['discourse'][:16]:16s} "
              f"opus={s['opus_verdict']:<14s} gem={(gem_verdict or 'None'):<14s} {mark} "
              f"${c:.4f}  {res.get('latency_s')}s  {res.get('finish_reason')}")

    # ───────── Aggregation ─────────
    valid = [r for r in results if "gemini_verdict" in r]
    matched = sum(1 for r in valid if r["match"])
    n = len(valid)

    # Konfusionsmatrix Opus × Gemini
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in valid:
        confusion[r["opus_verdict"]][r["gemini_verdict"] or "(none)"] += 1

    # Per-Diskursraum-Match-Rate
    per_disc: dict[str, dict[str, int]] = defaultdict(lambda: {"match": 0, "total": 0})
    for r in valid:
        per_disc[r["discourse"]]["total"] += 1
        if r["match"]:
            per_disc[r["discourse"]]["match"] += 1

    # Per-Verdict-Recall (wie gut findet Gemini die echten Opus-Verdicts?)
    per_verdict: dict[str, dict[str, int]] = defaultdict(lambda: {"match": 0, "total": 0})
    for r in valid:
        per_verdict[r["opus_verdict"]]["total"] += 1
        if r["match"]:
            per_verdict[r["opus_verdict"]]["match"] += 1

    print()
    print(f"  Gemini matches Opus: {matched}/{n} = {matched/max(n,1)*100:.1f}%")
    print(f"  Cost total:          ${total_cost:.4f}")

    out = {
        "ts": datetime.now().isoformat(),
        "model": GEMINI_35_FLASH.model,
        "n": n,
        "matched": matched,
        "match_rate": round(matched / max(n, 1), 3),
        "cost_total_usd": round(total_cost, 4),
        "confusion": {k: dict(v) for k, v in confusion.items()},
        "per_discourse": dict(per_disc),
        "per_verdict_recall": dict(per_verdict),
        "results": results,
    }
    (DOCS / "qcheck_gemini35_n50.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str)
    )

    # ───────── Markdown-Report ─────────
    md = [
        "# Gemini 3.5 Flash — Q-Check N=50 vs. Opus-Goldstandard",
        "",
        f"**Datum:** {datetime.now().isoformat()}",
        f"**Modell:** `{GEMINI_35_FLASH.model}` ($1.50 in / $9.00 out per Mtok, OpenRouter)",
        f"**Goldstandard:** `articles.agent_verdict` (Opus 4.6/4.7 Vollanalyse, tokens_in > 25k, kein C-Tier)",
        f"**Stichprobe:** 5 Diskursräume × {PER_DISCOURSE} = {len(sample)} Artikel, balanciert über alle Verdicts (seed={SEED})",
        f"**Prompt:** PRODUKTIVES `ASSESSMENT_OUTRO` ohne Patches",
        f"**Gemini-Config:** `max_tokens=8192`, `reasoning.effort=low`",
        "",
        f"## Headline-Resultat: **{matched}/{n} = {matched/max(n,1)*100:.1f}%** Gemini-Verdicts treffen Opus",
        f"**Q-Check-Kosten:** ${total_cost:.4f}",
        "",
        "## Konfusionsmatrix (Zeile = Opus, Spalte = Gemini)",
        "",
        "| Opus ↓ \\ Gemini → | ignorieren | scannen | lesenswert | pflichtlektuere | (none/Fehler) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for opus_v in VERDICTS:
        cells = []
        for gem_v in VERDICTS:
            n_cell = confusion[opus_v].get(gem_v, 0)
            cells.append(f"{n_cell}" if n_cell == 0 else f"**{n_cell}**" if opus_v == gem_v else f"{n_cell}")
        none_cell = confusion[opus_v].get("(none)", 0)
        md.append(f"| **{opus_v}** | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} | {none_cell} |")
    md.append("")
    md.append("_Diagonale (fett) = Match. Off-diagonale Werte zeigen typische Verschiebungen._")
    md.append("")

    md.append("## Recall pro Opus-Verdict")
    md.append("")
    md.append("| Opus-Verdict | n | Gemini-Match | Recall |")
    md.append("|---|---:|---:|---:|")
    for v in VERDICTS:
        pv = per_verdict.get(v)
        if pv and pv["total"] > 0:
            md.append(f"| `{v}` | {pv['total']} | {pv['match']} | {pv['match']/pv['total']*100:.1f}% |")
    md.append("")

    md.append("## Match-Rate pro Diskursraum")
    md.append("")
    md.append("| Diskursraum | n | Match | Rate |")
    md.append("|---|---:|---:|---:|")
    for disc in DISCOURSES:
        pd = per_disc.get(disc, {"match": 0, "total": 0})
        md.append(f"| {disc} | {pd['total']} | {pd['match']} | {pd['match']/max(pd['total'],1)*100:.1f}% |")
    md.append("")

    md.append("## Per-Artikel-Detail")
    md.append("")
    md.append("| # | Disk | Journal | Opus | Gemini | M | Titel |")
    md.append("|---:|---|---|---|---|---|---|")
    for i, r in enumerate(results, 1):
        if "gemini_verdict" not in r:
            md.append(f"| {i} | {r['discourse'][:8]} | {r['journal']} | `{r['opus_verdict']}` | ERROR | ✗ | {r['title'][:80]} |")
            continue
        mark = "✓" if r["match"] else "✗"
        md.append(
            f"| {i} | {r['discourse'][:8]} | {r['journal']} | `{r['opus_verdict']}` | "
            f"`{r['gemini_verdict']}` | {mark} | {r['title'][:80]} |"
        )
    md.append("")

    # Failure-Modes-Liste
    md.append("## Divergenzen (Gemini ≠ Opus) — Details")
    md.append("")
    for r in results:
        if "gemini_verdict" not in r or r.get("match"):
            continue
        md.append(f"### {r['journal']} · {r['discourse']} · `{r['opus_verdict']}` → `{r['gemini_verdict']}`")
        md.append(f"**{r['title']}**")
        md.append(f"- _article_id_: `{r['article_id']}`")
        md.append(f"- _Citation-Hits_: high={r['citation_hits_high']}, med={r['citation_hits_med']}")
        md.append(f"- _Gemini cost_: ${r['cost_usd']:.4f} · {r['latency_s']}s · {r['finish_reason']}")
        md.append(f"- **Gemini-Kernthese:** {r['gemini_kernthese'][:400]}")
        md.append(f"- **Gemini-Begründung:** {r['gemini_begruendung'][:400]}")
        md.append("")

    (DOCS / "qcheck_gemini35_n50.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  -> docs/qcheck_gemini35_n50.md")
    print(f"  -> docs/qcheck_gemini35_n50.json")


if __name__ == "__main__":
    main()
