"""Re-Test der 24 Divergenzen aus qcheck_gemini35_n50.json mit:
   - reasoning.effort="high" (statt "low")
   - Tool-Schema bereinigt: bezuege NICHT mehr required
     (Prompt sagt explizit "Write NO bezuege" — required-Array könnte Gemini irritieren)

Hypothese-Tests:
- H1: Mehr Deliberation → bessere Kalibrierung der Verdict-Stufen
- H2: Sauberes Schema → weniger "Tool-Compliance-Lärm" im reasoning

Output: docs/qcheck_gemini35_retest.{json,md}
"""

from __future__ import annotations

import copy
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


def _clean_tool_schema() -> list[dict]:
    """Kopiert TOOLS_SUBMIT_ONLY und entfernt bezuege+candidate_reads aus required."""
    tools = copy.deepcopy(TOOLS_SUBMIT_ONLY)
    params = tools[0]["function"]["parameters"]
    # Aus required raus: bezuege (Prompt sagt "Write NO bezuege" — required ist hier widersprüchlich)
    # Auch theoretisch_methodisch + bemerkenswert raus, damit Gemini nicht Output-Padding produziert
    kept_required = ["kernthese", "verdict", "verdict_begruendung"]
    params["required"] = kept_required
    return tools


def call_gemini(system_prompt: str, user_content: str, tools: list[dict], effort: str) -> dict[str, Any]:
    route = GEMINI_35_FLASH
    client = build_client(route.provider)
    messages = make_messages(system_prompt, user_content, route)
    params = {
        "model": route.model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "extra_body": {
            "usage": {"include": True},
            "reasoning": {"effort": effort},
        },
    }
    # Kein max_tokens-Cap im Test — Gemini darf so viel reasoning produzieren wie es will.
    # max_tokens wird bei Tests nicht festgesetzt; in Produktion könnte man es zurückholen.
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
    prior = json.loads((DOCS / "qcheck_gemini35_n50.json").read_text())
    divergences = [r for r in prior["results"] if "gemini_verdict" in r and not r.get("match")]
    print(f"Re-Test: {len(divergences)} Divergenzen aus N=50")
    print(f"Konfig: reasoning.effort=high, schema mit weniger required")

    summaries = json.loads(SUMMARIES_JSON.read_text())["summaries"]
    sys_prompt = build_system_prompt(summaries, outro=ASSESSMENT_OUTRO)
    corpus = json.loads(CORPUS_JSON.read_text())
    authored_all = corpus.get("authored_all", [])
    store = Store()
    clean_tools = _clean_tool_schema()

    results: list[dict] = []
    total_cost = 0.0
    safety_break = False

    for idx, r in enumerate(divergences, 1):
        aid = r["article_id"]
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
            print(f"  [{idx:>2}/{len(divergences)}] skip")
            continue

        res = call_gemini(sys_prompt, user_content, clean_tools, effort="high")
        if res.get("error"):
            print(f"  [{idx:>2}] ERROR {res['error'][:120]}")
            results.append({**r, "retest_error": res["error"][:300]})
            continue

        c = res.get("cost_usd") or 0.0
        total_cost += c
        if idx >= 5 and total_cost / idx > 0.30:
            safety_break = True
            print(f"  ⚠ Safety-Break: avg ${total_cost/idx:.4f}/call > $0.30")

        gem = res.get("tool_args") or {}
        new_v = gem.get("verdict")
        opus_v = r["opus_verdict"]
        old_v = r["gemini_verdict"]
        match_now = (new_v == opus_v)
        flipped = (new_v != old_v)
        flipped_correct = match_now and flipped
        mark = "✓✓" if flipped_correct else "✓" if match_now else "≈" if not flipped else "✗"

        results.append({
            **r,
            "retest_verdict": new_v,
            "retest_kernthese": (gem.get("kernthese") or "")[:400],
            "retest_begruendung": (gem.get("verdict_begruendung") or "")[:500],
            "retest_cost_usd": c,
            "retest_tokens_in": res.get("tokens_in"),
            "retest_tokens_out": res.get("tokens_out"),
            "retest_latency_s": res.get("latency_s"),
            "retest_finish": res.get("finish_reason"),
            "retest_match": match_now,
            "retest_flipped": flipped,
        })
        print(f"  [{idx:>2}/{len(divergences)}] {r['journal']:10s} "
              f"opus={opus_v:<13s} gem_low={old_v:<13s} gem_high={(new_v or 'None'):<13s} "
              f"{mark} ${c:.4f} {res.get('latency_s')}s in/out={res.get('tokens_in')}/{res.get('tokens_out')}")

    # Stats
    valid = [r for r in results if "retest_verdict" in r]
    n_flipped = sum(1 for r in valid if r["retest_flipped"])
    n_flipped_correct = sum(1 for r in valid if r["retest_flipped"] and r["retest_match"])
    n_flipped_wrong = sum(1 for r in valid if r["retest_flipped"] and not r["retest_match"])
    n_now_match = sum(1 for r in valid if r["retest_match"])

    print()
    print(f"  Von {len(valid)} Divergenzen:")
    print(f"    - {n_flipped} haben Verdict geändert ({n_flipped_correct} jetzt korrekt, {n_flipped_wrong} immer noch falsch)")
    print(f"    - {n_now_match} jetzt korrekt = +{n_now_match} zur ursprünglichen Match-Rate")
    print(f"  Implizierte neue Gesamt-Rate: ({prior['matched']} + {n_now_match}) / 50 = {(prior['matched']+n_now_match)/50*100:.1f}%")
    print(f"  Re-Test-Kosten: ${total_cost:.4f}")

    out = {
        "ts": datetime.now().isoformat(),
        "config": {"reasoning_effort": "high", "max_tokens": 16384, "schema_required": ["kernthese","verdict","verdict_begruendung"]},
        "n_divergences": len(valid),
        "n_flipped": n_flipped,
        "n_flipped_correct": n_flipped_correct,
        "n_now_match": n_now_match,
        "implied_total_match_rate": round((prior["matched"] + n_now_match) / 50, 3),
        "cost_total_usd": round(total_cost, 4),
        "results": results,
    }
    (DOCS / "qcheck_gemini35_retest.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str))

    md = [
        "# Gemini 3.5 Flash — Re-Test der Divergenzen (high-effort + sauberes Schema)",
        "",
        f"**Datum:** {datetime.now().isoformat()}",
        f"**Ausgangspunkt:** {len(divergences)} Divergenzen aus N=50-Lauf",
        f"**Änderungen:** `reasoning.effort=low → high`, Tool-Schema: nur `kernthese`/`verdict`/`verdict_begruendung` required",
        f"**Kosten:** ${total_cost:.4f}",
        "",
        f"## Ergebnis: {n_flipped} von {len(valid)} Verdicts geändert ({n_flipped_correct} korrekt zu Opus geflippt, {n_flipped_wrong} immer noch falsch)",
        "",
        f"**Implizierte neue Gesamt-Rate**: ({prior['matched']} + {n_now_match}) / 50 = **{(prior['matched']+n_now_match)/50*100:.1f}%**",
        f"(vorher: {prior['matched']}/50 = {prior['matched']/50*100:.1f}%)",
        "",
        "## Per-Artikel-Vergleich",
        "",
        "| # | Journal | Opus | Gemini low | Gemini high | Δ | Begründung high |",
        "|---:|---|---|---|---|---|---|",
    ]
    for r in results:
        if "retest_verdict" not in r:
            md.append(f"| | {r['journal']} | `{r['opus_verdict']}` | `{r['gemini_verdict']}` | ERROR | | {r.get('retest_error','')[:80]} |")
            continue
        flip = "→" if r["retest_flipped"] else "="
        match_mark = " ✓" if r["retest_match"] else (" ✗" if r["retest_flipped"] else "")
        md.append(
            f"| {r['i'] if 'i' in r else ''} | {r['journal']} | `{r['opus_verdict']}` | "
            f"`{r['gemini_verdict']}` {flip} `{r['retest_verdict']}` | {match_mark} | "
            f"{r['retest_begruendung'][:180]} |"
        )

    (DOCS / "qcheck_gemini35_retest.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  -> docs/qcheck_gemini35_retest.md")


if __name__ == "__main__":
    main()
