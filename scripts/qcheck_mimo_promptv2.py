"""MiMo Q-Check Round 2: getunter Prompt gegen die 5 Mismatches + 3 Kontroll-Matches.

Vorgehen:
- 3 chirurgische Ergänzungen zum ASSESSMENT_OUTRO, nur für MiMo
- Test gegen die 5 Mismatches (#10, #22, #25, #44, #48) → Erwartung: ≥4/5 konvergieren zu Opus
- 3 Kontroll-Matches (#3, #6, #11) sollen stabil bleiben — kein regression
- Output: docs/qcheck_mimo_promptv2.md mit before/after pro Artikel
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
from journal_bot.multi_provider import ROUTES, build_client, extract_stats, make_messages
from journal_bot.settings import CORPUS_JSON, SUMMARIES_JSON
from journal_bot.store import Store

DOCS = Path("docs")

# ────────────────────────────────────────────────────────────────────
# Drei Patches als Ergänzung zum ASSESSMENT_OUTRO — nur für MiMo
# ────────────────────────────────────────────────────────────────────

MIMO_OUTRO_PATCHES = """

=== ZUSÄTZLICHE REGELN (MiMo-Kalibrierung) ===

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


# ────────────────────────────────────────────────────────────────────
# Test-Set
# ────────────────────────────────────────────────────────────────────

# Artikel-IDs aus docs/qcheck_assessment.json
# Mismatches (mit Opus-Goldstandard laut User-Verdicts: Opus on point)
MISMATCHES = {
    10: "merz / Friedrich-Rezension (Opus=lesenswert)",
    22: "BJET / Bearman+Ajjawi black-box (Opus=lesenswert, User: hochrelevant)",
    25: "EERJ / Zembylas anti-complicity (Opus=ignorieren, User: ignorieren)",
    44: "MedienPaed / de Witt+Leineweber (Opus=lesenswert, Zitation-Hit, User: must-read)",
    48: "ZfPaed / Höhne+Karcher+Voss Wolkige Verheißungen (Opus=lesenswert)",
}

# Matches als Kontrolle — sollen stabil bleiben
CONTROLS = {
    3: "MedienPaed (Opus+MiMo = lesenswert)",
    6: "MedienPaed (Opus+MiMo = ignorieren)",
    11: "MedienPaed (Opus+MiMo = scannen)",
}


# ────────────────────────────────────────────────────────────────────
# Helper
# ────────────────────────────────────────────────────────────────────


def call_mimo_patched(system_prompt: str, user_content: str) -> dict[str, Any]:
    """MiMo mit patched system prompt; tool_choice='auto'."""
    route = ROUTES["mimo"]
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
    resp = client.chat.completions.create(**params)
    latency = time.time() - t0
    choice = resp.choices[0]
    msg = choice.message
    s = extract_stats(resp.usage, route)

    tool_args = None
    for tc in (getattr(msg, "tool_calls", None) or []):
        if tc.function.name == "submit_digest_entry":
            try: tool_args = json.loads(tc.function.arguments)
            except Exception: tool_args = {"_raw": tc.function.arguments}
            break

    return {
        "finish_reason": choice.finish_reason,
        "tokens_in": s.tokens_in, "tokens_out": s.tokens_out,
        "cached_read": s.cached_read,
        "cost_usd": round(s.cost_usd, 5),
        "cache_pct": round(s.cached_read / max(s.tokens_in, 1) * 100, 1),
        "latency_s": round(latency, 2),
        "text": msg.content or "",
        "tool_args": tool_args,
    }


def main():
    # Hole Artikel-IDs aus prior q-check JSON
    prior = json.loads((DOCS / "qcheck_assessment.json").read_text())
    by_i = {r["i"]: r for r in prior["results"]}

    test_set = {**MISMATCHES, **CONTROLS}
    print(f"Lade {len(test_set)} Artikel ({len(MISMATCHES)} Mismatches + {len(CONTROLS)} Kontrollen)")

    # System-Prompt mit patches
    summaries = json.loads(SUMMARIES_JSON.read_text())["summaries"]
    patched_outro = ASSESSMENT_OUTRO + MIMO_OUTRO_PATCHES
    sys_prompt = build_system_prompt(summaries, outro=patched_outro)
    print(f"System-Prompt (patched): {len(sys_prompt):,} chars")

    # Vorbereitung
    corpus = json.loads(CORPUS_JSON.read_text())
    authored_all = corpus.get("authored_all", [])
    store = Store()

    results: list[dict] = []
    total_cost = 0.0
    safety_break = False
    new_calls = 0

    for i in sorted(test_set):
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

        res = call_mimo_patched(sys_prompt, user_content)
        c = res.get("cost_usd") or 0.0
        total_cost += c
        new_calls += 1
        if new_calls >= 3 and total_cost / new_calls > 0.06:
            safety_break = True
            print(f"  ⚠ Safety-Break: avg ${total_cost/new_calls:.4f}/call > $0.06")

        mimo_v2 = res.get("tool_args") or {}
        opus_verdict = prior_r["opus"]["verdict"]
        mimo_v1 = prior_r["mimo"]["verdict"]
        mimo_v2_verdict = mimo_v2.get("verdict")

        kind = "MISMATCH" if i in MISMATCHES else "CONTROL"
        # Verbessert? (für Mismatches: konvergiert mimo_v2 zu opus?)
        if kind == "MISMATCH":
            improved = (mimo_v2_verdict == opus_verdict)
            mark = "✓ fixed" if improved else "✗ still diverged"
        else:
            stable = (mimo_v2_verdict == opus_verdict)
            mark = "✓ stable" if stable else "⚠ regressed"

        results.append({
            "i": i,
            "article_id": aid,
            "label": test_set[i],
            "kind": kind,
            "opus_verdict": opus_verdict,
            "mimo_v1_verdict": mimo_v1,
            "mimo_v2_verdict": mimo_v2_verdict,
            "mimo_v2_kernthese": mimo_v2.get("kernthese", ""),
            "mimo_v2_begruendung": mimo_v2.get("verdict_begruendung", ""),
            "mimo_v2_bemerkenswert": mimo_v2.get("bemerkenswert", []),
            "cost_usd": c,
            "cache_pct": res.get("cache_pct"),
            "tokens_in": res.get("tokens_in"),
            "tokens_out": res.get("tokens_out"),
            "latency_s": res.get("latency_s"),
            "mark": mark,
            "citation_hits_high": sum(1 for h in hits if h.confidence == "high"),
            "citation_hits_med": sum(1 for h in hits if h.confidence == "medium"),
        })
        print(f"  #{i:>2} {kind:<8}  opus={opus_verdict:<11}  "
              f"v1={mimo_v1 or 'None':<11}  v2={mimo_v2_verdict or 'None':<11}  "
              f"${c:.4f}  cache={res.get('cache_pct'):.0f}%  {mark}")

    # Auswertung
    fixed = sum(1 for r in results if r["kind"] == "MISMATCH" and r["mark"].startswith("✓"))
    mismatches_n = sum(1 for r in results if r["kind"] == "MISMATCH")
    stable = sum(1 for r in results if r["kind"] == "CONTROL" and r["mark"].startswith("✓"))
    controls_n = sum(1 for r in results if r["kind"] == "CONTROL")
    print()
    print(f"  Fixed Mismatches: {fixed}/{mismatches_n}")
    print(f"  Stable Controls:  {stable}/{controls_n}")
    print(f"  Cost total:       ${total_cost:.4f}")

    # JSON + Markdown
    out = {"results": results, "patches": MIMO_OUTRO_PATCHES, "ts": datetime.now().isoformat(),
           "summary": {"fixed": fixed, "mismatches_n": mismatches_n,
                       "stable": stable, "controls_n": controls_n,
                       "cost_total": round(total_cost, 4)}}
    (DOCS / "qcheck_mimo_promptv2.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str))

    md = [
        "# MiMo Q-Check Round 2 — Prompt-Patches getestet",
        "",
        f"**Datum:** {datetime.now().isoformat()}",
        f"**Test-Set:** 5 Mismatches + 3 Kontroll-Matches aus `qcheck_assessment.json`",
        f"**Patches:** 3 Ergänzungen am ASSESSMENT_OUTRO — siehe Abschnitt unten",
        f"**Resultat:** **{fixed}/{mismatches_n} Mismatches gefixt**, **{stable}/{controls_n} Kontrollen stabil**",
        f"**Q-Check-Kosten:** ${total_cost:.4f}",
        "",
        "## Ergebnistabelle",
        "",
        "| #  | Art | Opus | MiMo v1 | MiMo v2 (patched) | Bewertung |",
        "|---:|---|---|---|---|---|",
    ]
    for r in results:
        md.append(f"| #{r['i']} | {r['kind']} | `{r['opus_verdict']}` | "
                  f"`{r['mimo_v1_verdict']}` | `{r['mimo_v2_verdict']}` | {r['mark']} |")
    md.append("")
    md.append("## Pro Artikel — Detail")
    md.append("")
    for r in results:
        md.append(f"### #{r['i']} — {r['label']}")
        md.append(f"- _article_id_: `{r['article_id']}`")
        md.append(f"- _Citation-Hits_: high={r['citation_hits_high']}, med={r['citation_hits_med']}")
        md.append(f"- _MiMo v2 cost_: ${r['cost_usd']:.4f} · cache={r['cache_pct']}% · {r['latency_s']}s")
        md.append("")
        md.append(f"**Opus:** `{r['opus_verdict']}`")
        md.append(f"**MiMo v1 (alter Prompt):** `{r['mimo_v1_verdict']}`")
        md.append(f"**MiMo v2 (patched):** `{r['mimo_v2_verdict']}` — {r['mark']}")
        md.append("")
        md.append(f"**v2 Kernthese:** {r['mimo_v2_kernthese'][:600]}")
        md.append(f"**v2 Begründung:** {r['mimo_v2_begruendung'][:600]}")
        md.append("")
        md.append("---")
        md.append("")
    md.append("## Eingesetzte Patches (Ergänzung zum ASSESSMENT_OUTRO)")
    md.append("")
    md.append("```")
    md.append(MIMO_OUTRO_PATCHES.strip())
    md.append("```")
    (DOCS / "qcheck_mimo_promptv2.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  -> docs/qcheck_mimo_promptv2.md")


if __name__ == "__main__":
    main()
