"""Q-Check: Mistral Medium 3.5 (nativ via api.mistral.ai) gegen die 5
Mismatch-Artikel aus docs/qcheck_assessment.json.

Vorgehen wie qcheck_mimo_promptv2.py, aber:
- PRODUCTION-Prompt (ASSESSMENT_OUTRO ohne Patches)
- Modell: mistral-medium-latest via Mistral-Native-API (SARAH-Pfad)
- Vergleich gegen Opus (Goldstandard aus articles.db) und MiMo v1 (aus qcheck JSON)

Ad-hoc Route, kein Eintrag in multi_provider.py — Mistral-Provider-Eintrag
existiert dort schon (PROVIDERS["mistral"]).

ACHTUNG: n=5. Das ist KEIN Migrations-Test. Ergebnis ist qualitativ-indikativ:
"verhält sich Mistral näher an Opus als MiMo oder nicht?"
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import replace
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
from journal_bot.multi_provider import ROUTES, Route, build_client, extract_stats, make_messages
from journal_bot.settings import CORPUS_JSON, SUMMARIES_JSON
from journal_bot.store import Store

DOCS = Path("docs")

# Ad-hoc Route — nicht in ROUTES persistiert.
# Pricing: User-Angabe $7.50/Mtok output; Input geschätzt $1.50/Mtok
# (Mistral nativ liefert keine cost im usage, extract_stats macht den Fallback).
MISTRAL_MED_35 = Route(
    provider="mistral",
    model="mistral-medium-latest",
    label="Mistral Medium 3.5 (nativ EU)",
    input_usd_per_mtok=1.5,
    output_usd_per_mtok=7.5,
    region="EU",
    dsgvo=True,
    supports_anthropic_cache=False,  # Mistral-Style: kein cache_control, sonst 422
    has_implicit_cache=True,          # Mistral macht server-side prefix caching
)

# Test-Set — nur Mismatches, ohne Kontrollen (User-Wunsch)
MISMATCHES = {
    10: "merz / Friedrich-Rezension (Opus=lesenswert)",
    22: "BJET / Bearman+Ajjawi black-box (Opus=lesenswert, User: hochrelevant)",
    25: "EERJ / Zembylas anti-complicity (Opus=ignorieren, User: ignorieren)",
    44: "MedienPaed / de Witt+Leineweber (Opus=lesenswert, Zitation-Hit, User: must-read)",
    48: "ZfPaed / Höhne+Karcher+Voss Wolkige Verheißungen (Opus=lesenswert)",
}


def call_mistral(system_prompt: str, user_content: str) -> dict[str, Any]:
    route = MISTRAL_MED_35
    client = build_client(route.provider)
    messages = make_messages(system_prompt, user_content, route)
    params = {
        "model": route.model,
        "max_tokens": 2500,
        "messages": messages,
        "tools": TOOLS_SUBMIT_ONLY,
        "tool_choice": "auto",
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
    }


def main():
    prior = json.loads((DOCS / "qcheck_assessment.json").read_text())
    by_i = {r["i"]: r for r in prior["results"]}

    print(f"Lade {len(MISMATCHES)} Mismatch-Artikel")
    print(f"Modell: {MISTRAL_MED_35.model}  ({MISTRAL_MED_35.input_usd_per_mtok}/{MISTRAL_MED_35.output_usd_per_mtok} per Mtok)")

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

        res = call_mistral(sys_prompt, user_content)
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

        mist = res.get("tool_args") or {}
        opus_verdict = prior_r["opus"]["verdict"]
        mimo_v1 = prior_r["mimo"]["verdict"]
        mist_verdict = mist.get("verdict")
        match = (mist_verdict == opus_verdict)
        mark = "✓ matches opus" if match else "✗ diverged"

        results.append({
            "i": i,
            "article_id": aid,
            "label": MISMATCHES[i],
            "opus_verdict": opus_verdict,
            "mimo_v1_verdict": mimo_v1,
            "mistral_verdict": mist_verdict,
            "mistral_kernthese": mist.get("kernthese", ""),
            "mistral_begruendung": mist.get("verdict_begruendung", ""),
            "mistral_bemerkenswert": mist.get("bemerkenswert", []),
            "cost_usd": c,
            "cache_pct": res.get("cache_pct"),
            "tokens_in": res.get("tokens_in"),
            "tokens_out": res.get("tokens_out"),
            "latency_s": res.get("latency_s"),
            "finish_reason": res.get("finish_reason"),
            "mark": mark,
            "citation_hits_high": sum(1 for h in hits if h.confidence == "high"),
            "citation_hits_med": sum(1 for h in hits if h.confidence == "medium"),
        })
        print(f"  #{i:>2}  opus={opus_verdict:<11}  mimo_v1={mimo_v1 or 'None':<11}  "
              f"mistral={mist_verdict or 'None':<11}  ${c:.4f}  cache={res.get('cache_pct'):.0f}%  {mark}")

    matched = sum(1 for r in results if r.get("mark", "").startswith("✓"))
    n = sum(1 for r in results if "mark" in r)
    print()
    print(f"  Mistral matches Opus: {matched}/{n}")
    print(f"  Cost total:           ${total_cost:.4f}")

    out = {
        "results": results,
        "ts": datetime.now().isoformat(),
        "model": MISTRAL_MED_35.model,
        "summary": {"matched": matched, "n": n, "cost_total": round(total_cost, 4)},
    }
    (DOCS / "qcheck_mistral_med35.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str)
    )

    md = [
        "# Mistral Medium 3.5 — Q-Check gegen die 5 Mismatches",
        "",
        f"**Datum:** {datetime.now().isoformat()}",
        f"**Modell:** `{MISTRAL_MED_35.model}` ($1.50 in / $7.50 out per Mtok, OpenRouter)",
        f"**Test-Set:** 5 Mismatch-Artikel aus `qcheck_assessment.json` (gleiche IDs wie MiMo-Round-2)",
        f"**Prompt:** PRODUKTIVES `ASSESSMENT_OUTRO` ohne Patches",
        f"**Resultat:** **{matched}/{n}** Mistral-Verdicts treffen Opus",
        f"**Q-Check-Kosten:** ${total_cost:.4f}",
        "",
        "_n=5 — qualitativ-indikativ, keine statistische Aussage._",
        "",
        "## Ergebnistabelle",
        "",
        "| #  | Opus | MiMo v1 | Mistral 3.5 | Match |",
        "|---:|---|---|---|---|",
    ]
    for r in results:
        if "mark" not in r:
            md.append(f"| #{r['i']} | — | — | ERROR | `{r.get('error','')[:80]}` |")
            continue
        md.append(
            f"| #{r['i']} | `{r['opus_verdict']}` | `{r['mimo_v1_verdict']}` | "
            f"`{r['mistral_verdict']}` | {r['mark']} |"
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
        md.append(f"- _Mistral cost_: ${r['cost_usd']:.4f} · cache={r['cache_pct']}% · {r['latency_s']}s · {r['finish_reason']}")
        md.append("")
        md.append(f"**Opus:** `{r['opus_verdict']}`")
        md.append(f"**MiMo v1:** `{r['mimo_v1_verdict']}`")
        md.append(f"**Mistral 3.5:** `{r['mistral_verdict']}` — {r['mark']}")
        md.append("")
        md.append(f"**Kernthese:** {r['mistral_kernthese'][:600]}")
        md.append(f"**Begründung:** {r['mistral_begruendung'][:600]}")
        md.append("")
        md.append("---")
        md.append("")
    (DOCS / "qcheck_mistral_med35.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  -> docs/qcheck_mistral_med35.md")


if __name__ == "__main__":
    main()
