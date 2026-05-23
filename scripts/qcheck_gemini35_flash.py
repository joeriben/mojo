"""Q-Check: Google Gemini 3.5 Flash (via OpenRouter) gegen die 5 Mismatch-Artikel
aus docs/qcheck_assessment.json.

Vorgehen wie qcheck_mistral_med35.py:
- PRODUCTION-Prompt (ASSESSMENT_OUTRO ohne Patches)
- Modell: google/gemini-3.5-flash via OpenRouter
- Vergleich gegen Opus (Goldstandard) und MiMo v1 (aus prior JSON)
- Tool-Call submit_digest_entry erwartet (OpenRouter normalisiert Gemini → OpenAI tool_calls)

ACHTUNG: n=5. Qualitativ-indikativ, KEIN Migrations-Test.

Pricing (laut OpenRouter, Stand 2026-05):
- $1.50 / Mtok input
- $9.00 / Mtok output
- 1M context window
"""

from __future__ import annotations

import json
import sys
import time
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

# Ad-hoc Route — nicht in ROUTES persistiert.
GEMINI_35_FLASH = Route(
    provider="openrouter",
    model="google/gemini-3.5-flash",
    label="Gemini 3.5 Flash (OpenRouter)",
    input_usd_per_mtok=1.5,
    output_usd_per_mtok=9.0,
    region="US",
    dsgvo=False,
    supports_anthropic_cache=False,  # Gemini eigener cache-Mechanismus, nicht anthropic-style
    has_implicit_cache=True,          # OpenRouter macht implicit caching für Gemini
)

# Test-Set — gleich wie Mistral-Q-Check, für direkte Vergleichbarkeit
MISMATCHES = {
    10: "merz / Friedrich-Rezension (Opus=lesenswert)",
    22: "BJET / Bearman+Ajjawi black-box (Opus=lesenswert, User: hochrelevant)",
    25: "EERJ / Zembylas anti-complicity (Opus=ignorieren, User: ignorieren)",
    44: "MedienPaed / de Witt+Leineweber (Opus=lesenswert, Zitation-Hit, User: must-read)",
    48: "ZfPaed / Höhne+Karcher+Voss Wolkige Verheißungen (Opus=lesenswert)",
}


def call_gemini(system_prompt: str, user_content: str) -> dict[str, Any]:
    route = GEMINI_35_FLASH
    client = build_client(route.provider)
    messages = make_messages(system_prompt, user_content, route)
    params = {
        "model": route.model,
        # Gemini 3.5 Flash macht reasoning vor dem Tool-Call. Mit nur 2500
        # max_tokens läuft der Output ins Limit, BEVOR submit_digest_entry
        # gefeuert wird. 8192 gibt Raum für reasoning + tool args.
        "max_tokens": 8192,
        "messages": messages,
        "tools": TOOLS_SUBMIT_ONLY,
        "tool_choice": "auto",
        "extra_body": {
            "usage": {"include": True},
            # Reasoning auf "low" begrenzen — wir brauchen kein deep-thinking,
            # nur ein strukturiertes Verdict. Spart Tokens und Latenz.
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


def main():
    prior = json.loads((DOCS / "qcheck_assessment.json").read_text())
    by_i = {r["i"]: r for r in prior["results"]}

    # Optional: existierende Mistral-Verdicts mit reinziehen, falls vorhanden
    mistral_by_i: dict[int, dict] = {}
    mistral_path = DOCS / "qcheck_mistral_med35.json"
    if mistral_path.exists():
        mj = json.loads(mistral_path.read_text())
        mistral_by_i = {r["i"]: r for r in mj.get("results", []) if "mistral_verdict" in r}

    print(f"Lade {len(MISMATCHES)} Mismatch-Artikel")
    print(f"Modell: {GEMINI_35_FLASH.model}  ({GEMINI_35_FLASH.input_usd_per_mtok}/{GEMINI_35_FLASH.output_usd_per_mtok} per Mtok)")

    summaries = json.loads(SUMMARIES_JSON.read_text())["summaries"]
    sys_prompt = build_system_prompt(summaries, outro=ASSESSMENT_OUTRO)
    print(f"System-Prompt (production): {len(sys_prompt):,} chars")

    corpus = json.loads(CORPUS_JSON.read_text())
    authored_all = corpus.get("authored_all", [])
    store = Store()

    results: list[dict] = []
    total_cost = 0.0
    safety_break = False
    new_calls = 0

    for i in sorted(MISMATCHES):
        prior_r = by_i.get(i)
        if not prior_r:
            print(f"  #{i:>2}: nicht in prior JSON, skip")
            continue
        aid = prior_r["article_id"]

        with store._conn() as conn:
            row = dict(conn.execute("SELECT * FROM articles WHERE id=?", (aid,)).fetchone())

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
            print(f"  #{i:>2}: skip (safety break)")
            continue

        res = call_gemini(sys_prompt, user_content)
        if res.get("error"):
            print(f"  #{i:>2}: ERROR — {res['error'][:200]}")
            results.append({
                "i": i, "article_id": aid, "label": MISMATCHES[i],
                "error": res["error"][:400],
            })
            continue

        c = res.get("cost_usd") or 0.0
        total_cost += c
        new_calls += 1
        if new_calls >= 3 and total_cost / new_calls > 0.10:
            safety_break = True
            print(f"  ⚠ Safety-Break: avg ${total_cost/new_calls:.4f}/call > $0.10")

        gem = res.get("tool_args") or {}
        opus_verdict = prior_r["opus"]["verdict"]
        mimo_v1 = prior_r["mimo"]["verdict"]
        mist_v = (mistral_by_i.get(i) or {}).get("mistral_verdict")
        gem_verdict = gem.get("verdict")
        match = (gem_verdict == opus_verdict)
        mark = "✓ matches opus" if match else "✗ diverged"

        results.append({
            "i": i,
            "article_id": aid,
            "label": MISMATCHES[i],
            "opus_verdict": opus_verdict,
            "mimo_v1_verdict": mimo_v1,
            "mistral_verdict": mist_v,
            "gemini_verdict": gem_verdict,
            "gemini_kernthese": gem.get("kernthese", ""),
            "gemini_begruendung": gem.get("verdict_begruendung", ""),
            "gemini_bemerkenswert": gem.get("bemerkenswert", []),
            "cost_usd": c,
            "cache_pct": res.get("cache_pct"),
            "tokens_in": res.get("tokens_in"),
            "tokens_out": res.get("tokens_out"),
            "latency_s": res.get("latency_s"),
            "finish_reason": res.get("finish_reason"),
            "fallback_cost": res.get("fallback_cost"),
            "mark": mark,
            "citation_hits_high": sum(1 for h in hits if h.confidence == "high"),
            "citation_hits_med": sum(1 for h in hits if h.confidence == "medium"),
        })
        print(f"  #{i:>2}  opus={opus_verdict:<11}  mimo_v1={mimo_v1 or 'None':<11}  "
              f"mistral={mist_v or 'None':<11}  gemini={gem_verdict or 'None':<11}  "
              f"${c:.4f}  cache={res.get('cache_pct'):.0f}%  {mark}")

    matched = sum(1 for r in results if r.get("mark", "").startswith("✓"))
    n = sum(1 for r in results if "mark" in r)
    print()
    print(f"  Gemini matches Opus: {matched}/{n}")
    print(f"  Cost total:          ${total_cost:.4f}")

    out = {
        "results": results,
        "ts": datetime.now().isoformat(),
        "model": GEMINI_35_FLASH.model,
        "summary": {"matched": matched, "n": n, "cost_total": round(total_cost, 4)},
    }
    (DOCS / "qcheck_gemini35_flash.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str)
    )

    md = [
        "# Gemini 3.5 Flash — Q-Check gegen die 5 Mismatches",
        "",
        f"**Datum:** {datetime.now().isoformat()}",
        f"**Modell:** `{GEMINI_35_FLASH.model}` ($1.50 in / $9.00 out per Mtok, OpenRouter)",
        f"**Test-Set:** 5 Mismatch-Artikel aus `qcheck_assessment.json` (gleiche IDs wie Mistral-Q-Check)",
        f"**Prompt:** PRODUKTIVES `ASSESSMENT_OUTRO` ohne Patches",
        f"**Resultat:** **{matched}/{n}** Gemini-Verdicts treffen Opus",
        f"**Q-Check-Kosten:** ${total_cost:.4f}",
        "",
        "_n=5 — qualitativ-indikativ, keine statistische Aussage._",
        "",
        "## Ergebnistabelle",
        "",
        "| #  | Opus 4.7 | MiMo v1 | Mistral 3.5 | Gemini 3.5 Flash | Match |",
        "|---:|---|---|---|---|---|",
    ]
    for r in results:
        if "mark" not in r:
            md.append(f"| #{r['i']} | — | — | — | ERROR | `{r.get('error','')[:80]}` |")
            continue
        md.append(
            f"| #{r['i']} | `{r['opus_verdict']}` | `{r['mimo_v1_verdict']}` | "
            f"`{r.get('mistral_verdict') or '—'}` | "
            f"`{r['gemini_verdict']}` | {r['mark']} |"
        )
    md.append("")
    md.append("## Pro Artikel — Detail")
    md.append("")
    for r in results:
        md.append(f"### #{r['i']} — {r['label']}")
        md.append(f"- _article_id_: `{r['article_id']}`")
        if "mark" not in r:
            md.append(f"- _ERROR_: {r.get('error','')[:300]}")
            md.append("")
            md.append("---")
            md.append("")
            continue
        md.append(f"- _Citation-Hits_: high={r['citation_hits_high']}, med={r['citation_hits_med']}")
        md.append(
            f"- _Gemini_: ${r['cost_usd']:.4f} · cache={r['cache_pct']}% · "
            f"{r['latency_s']}s · {r['finish_reason']} · in={r['tokens_in']} out={r['tokens_out']}"
            + (" · (cost fallback aus Preisliste)" if r.get("fallback_cost") else "")
        )
        md.append("")
        md.append(f"**Opus:** `{r['opus_verdict']}`")
        md.append(f"**MiMo v1:** `{r['mimo_v1_verdict']}`")
        if r.get("mistral_verdict"):
            md.append(f"**Mistral 3.5:** `{r['mistral_verdict']}`")
        md.append(f"**Gemini 3.5 Flash:** `{r['gemini_verdict']}` — {r['mark']}")
        md.append("")
        md.append(f"**Kernthese:** {(r['gemini_kernthese'] or '')[:600]}")
        md.append(f"**Begründung:** {(r['gemini_begruendung'] or '')[:600]}")
        md.append("")
        md.append("---")
        md.append("")
    (DOCS / "qcheck_gemini35_flash.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  -> docs/qcheck_gemini35_flash.md")


if __name__ == "__main__":
    main()
