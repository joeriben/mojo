"""Q-Check: MiMo gegen vorhandene Opus-Datensätze fahren.

- Assessment: 50 stratified articles aus articles.db, deren agent_entry_json
  bereits Opus-Verdict + bezuege + kernthese trägt → MiMo neu fahren, Side-by-Side.
- Summarize: 5 publikationen aus summaries.json (Opus-generiert) → MiMo neu
  fahren, Side-by-Side für named_thinkers/key_terms/methods.
- Trends: 3 Cluster mit beiden Modellen frisch fahren (keine alten Reports da).

MiMo-Konfig (verifiziert 2026-05-16):
  - tool_choice="auto" (forced bricht Cache; auto greift mit 99 % Hit-Rate)
  - cache_control: ephemeral auf system-Block
  - max_tokens=2500 (Assessment), 2000 (Summarize), 32000 (Trends)

Output: docs/qcheck_assessment.md, docs/qcheck_summarize.md, docs/qcheck_trends.md
"""

from __future__ import annotations

import argparse
import json
import re
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
from journal_bot.settings import (
    CORPUS_JSON,
    DISCOURSE_SPACES,
    SUMMARIES_JSON,
    journals_in_cluster,
)
from journal_bot.store import Store
from journal_bot.summarize import (
    SUMMARY_TOOL,
    SYSTEM as SUMMARIZE_SYSTEM,
    USER_TEMPLATE as SUMMARIZE_USER_TEMPLATE,
)
from journal_bot.trends import SYSTEM_PROMPT as TRENDS_SYSTEM_PROMPT, _format_article_for_llm

DOCS = Path("docs")
DOCS.mkdir(exist_ok=True)


# ────────────────────────────────────────────────────────────────────
# Call-Helper (MiMo-spezifisch korrekt: tool_choice="auto")
# ────────────────────────────────────────────────────────────────────


def call_mimo(
    system_prompt: str,
    user_content: str,
    *,
    tools: list[dict] | None = None,
    forced_tool_name: str | None = None,
    max_tokens: int = 2500,
) -> dict[str, Any]:
    """Call MiMo via OpenRouter mit korrekter Konfig (auto tool_choice für Cache)."""
    route = ROUTES["mimo"]
    client = build_client(route.provider)
    messages = make_messages(system_prompt, user_content, route)

    params: dict[str, Any] = {
        "model": route.model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if tools:
        params["tools"] = tools
        # WICHTIG: "auto" — forced bricht Cache. Wir lassen das Modell den Call
        # selbst entscheiden. Falls forced_tool_name gesetzt, wird im
        # User-Prompt explizit gebeten (Workaround statt tool_choice forced).
        params["tool_choice"] = "auto"

    t0 = time.time()
    last_err: Exception | None = None
    resp = None
    for wait in (0, 5, 15, 45):
        if wait > 0:
            time.sleep(wait)
        try:
            resp = client.chat.completions.create(**params)
            break
        except Exception as e:
            last_err = e
            status = getattr(e, "status_code", None) or getattr(e, "status", None)
            if status == 429 or "429" in str(e):
                continue
            break

    if resp is None:
        return {"error": f"{type(last_err).__name__}: {str(last_err)[:600]}", "latency_s": time.time() - t0}

    latency = time.time() - t0
    choice = resp.choices[0]
    msg = choice.message
    stats = extract_stats(resp.usage, route)

    out: dict[str, Any] = {
        "finish_reason": choice.finish_reason,
        "tokens_in": stats.tokens_in,
        "tokens_out": stats.tokens_out,
        "cached_read": stats.cached_read,
        "cost_usd": round(stats.cost_usd, 5),
        "cache_pct": round(stats.cached_read / max(stats.tokens_in, 1) * 100, 1),
        "latency_s": round(latency, 2),
        "text": msg.content or "",
    }

    tool_args = None
    for tc in getattr(msg, "tool_calls", None) or []:
        if forced_tool_name and tc.function.name != forced_tool_name:
            continue
        try:
            tool_args = json.loads(tc.function.arguments)
        except Exception:
            tool_args = {"_raw": tc.function.arguments}
        break
    out["tool_args"] = tool_args
    return out


# ────────────────────────────────────────────────────────────────────
# Assessment-Q-Check
# ────────────────────────────────────────────────────────────────────


def qcheck_assessment(ids_file: Path = Path("scripts/qcheck_assessment_ids.json")):
    print("\n=== Q-CHECK ASSESSMENT ===")
    ids = json.loads(ids_file.read_text())["ids"]
    store = Store()

    summaries_data = json.loads(SUMMARIES_JSON.read_text(encoding="utf-8"))
    system_prompt = build_system_prompt(summaries_data["summaries"], outro=ASSESSMENT_OUTRO)
    corpus_data = json.loads(CORPUS_JSON.read_text(encoding="utf-8"))
    authored_all = corpus_data.get("authored_all", [])

    rows: list[dict] = []
    with store._conn() as conn:
        for aid in ids:
            r = conn.execute("SELECT * FROM articles WHERE id=?", (aid,)).fetchone()
            if r:
                rows.append(dict(r))

    # Idempotenz: vorhandene Ergebnisse laden, schon erfolgreiche Calls
    # überspringen. Nur Records mit MiMo-Verdict gelten als "fertig"; 402/403
    # werden re-versucht.
    out_json = DOCS / "qcheck_assessment.json"
    existing: dict[str, dict] = {}
    if out_json.exists():
        try:
            prior = json.loads(out_json.read_text())
            for r in prior.get("results", []):
                if (r.get("mimo") or {}).get("verdict"):
                    existing[r["article_id"]] = r
            print(f"  (Resume: {len(existing)} Calls aus prior JSON übernommen)")
        except Exception as e:
            print(f"  (Konnte prior JSON nicht laden: {e})")

    results: list[dict] = []
    total_cost = 0.0
    payment_required_hit = False
    cost_safety_hit = False
    new_calls_made = 0
    new_calls_cost = 0.0
    BUDGET_PER_CALL_LIMIT = 0.06  # CLAUDE.md-Style: abort if avg > $0.06/call after 3 calls
    for i, row in enumerate(rows, 1):
        # Resume: schon erfolgreich Q-gecheckte Artikel überspringen
        if row["id"] in existing:
            er = existing[row["id"]]
            results.append({**er, "i": i})
            total_cost += (er.get("mimo") or {}).get("cost_usd") or 0.0
            print(f"  #{i:>2}/{len(rows)} ⤴  skip (resume)  "
                  f"opus={er['opus'].get('verdict','?'):<11}  mimo={er['mimo'].get('verdict','?'):<11}")
            continue

        if payment_required_hit:
            print(f"  #{i:>2}/{len(rows)} ⏭  skip (402 noch aktiv)")
            continue
        if cost_safety_hit:
            print(f"  #{i:>2}/{len(rows)} ⏭  skip (cost safety break)")
            continue

        # Existierender Opus-Verdict aus DB
        opus_entry = json.loads(row.get("agent_entry_json") or "{}")
        new_article = {
            "title": row["title"],
            "authors": json.loads(row.get("authors_json") or "[]"),
            "abstract": row.get("openalex_abstract") or row.get("abstract") or "",
            "doi": row.get("doi") or "",
            "url": row.get("url") or "",
            "journal": row.get("journal_full") or row.get("journal_short") or "",
        }
        enrichment_data = {
            "openalex_abstract": row.get("openalex_abstract") or "",
            "references_crossref": json.loads(row.get("crossref_refs") or "[]") or [],
            "openalex_concepts": json.loads(row.get("openalex_concepts") or "[]") or [],
            "openalex_topics": json.loads(row.get("openalex_topics") or "[]") or [],
        }
        citation_hits = find_citations(enrichment_data["references_crossref"], authored_all)
        citations_block = format_for_agent(citation_hits)
        user_content = _format_new_article(new_article, enrichment_data) + citations_block

        res = call_mimo(
            system_prompt,
            user_content,
            tools=TOOLS_SUBMIT_ONLY,
            forced_tool_name="submit_digest_entry",
            max_tokens=2500,
        )

        # Falls MiMo den Tool-Call nicht macht (Empty-Response-Quirk), retry forced
        retried = False
        if not res.get("tool_args") and not res.get("error"):
            retried = True
            res2 = call_mimo(
                system_prompt,
                user_content + "\n\nWICHTIG: Antworte AUSSCHLIESSLICH durch Aufruf der submit_digest_entry-Funktion.",
                tools=TOOLS_SUBMIT_ONLY,
                forced_tool_name="submit_digest_entry",
                max_tokens=2500,
            )
            if res2.get("tool_args"):
                res = res2
                res["_retry"] = True

        mimo_args = res.get("tool_args") or {}
        opus_verdict = opus_entry.get("verdict") or row.get("agent_verdict")
        mimo_verdict = mimo_args.get("verdict")

        # 402 / 403 = Wochenlimit / Provider-Permission → Abbruch
        err_str = res.get("error") or ""
        if "402" in err_str or "403" in err_str or "requires more credits" in err_str:
            payment_required_hit = True
            print(f"  ⚠  Hit OpenRouter weekly key limit (402/403). Breche restlichen Lauf ab.")

        match = (opus_verdict == mimo_verdict)
        c = res.get("cost_usd") or 0.0
        total_cost += c
        if not payment_required_hit and not res.get("error"):
            new_calls_made += 1
            new_calls_cost += c
            if new_calls_made >= 3 and (new_calls_cost / new_calls_made) > BUDGET_PER_CALL_LIMIT:
                cost_safety_hit = True
                print(f"  ⚠  Cost-Safety: avg ${new_calls_cost/new_calls_made:.4f}/call > ${BUDGET_PER_CALL_LIMIT}. Stop.")

        results.append({
            "i": i,
            "article_id": row["id"],
            "journal": row["journal_short"],
            "title": row["title"],
            "opus": {
                "verdict": opus_verdict,
                "kernthese": opus_entry.get("kernthese", ""),
                "verdict_begruendung": opus_entry.get("verdict_begruendung", ""),
                "bezuege": opus_entry.get("bezuege", []),
                "bemerkenswert": opus_entry.get("bemerkenswert", []),
                "cost_usd": row.get("cost_usd"),
            },
            "mimo": {
                "verdict": mimo_verdict,
                "kernthese": mimo_args.get("kernthese", ""),
                "verdict_begruendung": mimo_args.get("verdict_begruendung", ""),
                "bezuege": mimo_args.get("bezuege", []),
                "bemerkenswert": mimo_args.get("bemerkenswert", []),
                "cost_usd": res.get("cost_usd"),
                "cache_pct": res.get("cache_pct"),
                "tokens_in": res.get("tokens_in"),
                "tokens_out": res.get("tokens_out"),
                "latency_s": res.get("latency_s"),
                "finish": res.get("finish_reason"),
                "error": res.get("error"),
                "_retry": res.get("_retry", False),
            },
            "verdict_match": match,
        })

        marker = "✓" if match else "✗"
        retry_mark = " [retry]" if retried else ""
        err_mark = f" ERR={res.get('error','')[:40]}" if res.get('error') else ""
        print(f"  #{i:>2}/{len(rows)} {marker} {row['journal_short']:>12}  "
              f"opus={opus_verdict:<11}  mimo={str(mimo_verdict):<11}  "
              f"${res.get('cost_usd',0):.4f}  cache={res.get('cache_pct',0):.0f}%{retry_mark}{err_mark}")

    matches = sum(1 for r in results if r["verdict_match"])
    print(f"\n  Verdict-Match: {matches}/{len(results)} = {matches/len(results)*100:.1f}%")
    print(f"  MiMo total cost: ${total_cost:.4f}  (Opus orig sum: ${sum(r['opus']['cost_usd'] or 0 for r in results):.4f})")

    # JSON-Roh
    out_json = DOCS / "qcheck_assessment.json"
    out_json.write_text(json.dumps({"results": results, "ts": datetime.now().isoformat()}, ensure_ascii=False, indent=2, default=str))

    # Markdown-Render delegieren — sauber separat, robust gegen heterogene Shapes
    import subprocess
    subprocess.run([sys.executable, "scripts/qcheck_render_assessment.py"], check=True)
    return results


# ────────────────────────────────────────────────────────────────────
# Summarize-Q-Check
# ────────────────────────────────────────────────────────────────────


def qcheck_summarize(pub_ids: list[str] | None = None):
    print("\n=== Q-CHECK SUMMARIZE ===")
    corpus = json.loads(CORPUS_JSON.read_text(encoding="utf-8"))
    pubs_by_id = {p["pub_id"]: p for p in corpus["publications"]}

    summaries_data = json.loads(SUMMARIES_JSON.read_text(encoding="utf-8"))
    opus_summaries = summaries_data["summaries"]

    if pub_ids is None:
        # 5 zufällige Pubs mit nicht-trivialem Fulltext nehmen
        candidates = [pid for pid, p in pubs_by_id.items()
                      if pid in opus_summaries and p.get("fulltext_chars", 0) > 10000]
        import random
        random.seed(42)
        pub_ids = random.sample(candidates, min(5, len(candidates)))

    results: list[dict] = []
    total_cost = 0.0
    for i, pid in enumerate(pub_ids, 1):
        pub = pubs_by_id.get(pid)
        if not pub:
            print(f"  #{i} {pid} not found in corpus, skip")
            continue
        opus_sum = opus_summaries.get(pid, {})
        fulltext = pub["fulltext"][:560_000]
        user_msg = SUMMARIZE_USER_TEMPLATE.format(
            title=pub["title"],
            authors=", ".join(pub["authors"]),
            year=pub.get("year") or "",
            venue=pub.get("venue") or "",
            fulltext=fulltext,
        )
        res = call_mimo(
            SUMMARIZE_SYSTEM,
            user_msg,
            tools=[SUMMARY_TOOL],
            forced_tool_name="record_summary",
            max_tokens=2000,
        )
        if not res.get("tool_args") and not res.get("error"):
            res2 = call_mimo(
                SUMMARIZE_SYSTEM,
                user_msg + "\n\nWICHTIG: Antworte AUSSCHLIESSLICH über record_summary.",
                tools=[SUMMARY_TOOL],
                forced_tool_name="record_summary",
                max_tokens=2000,
            )
            if res2.get("tool_args"):
                res = res2
                res["_retry"] = True

        mimo = res.get("tool_args") or {}
        total_cost += res.get("cost_usd") or 0.0

        def _coerce(v):
            if isinstance(v, list):
                return v
            if isinstance(v, str):
                s = v.strip()
                if s.startswith("[") and s.endswith("]"):
                    try:
                        return json.loads(s)
                    except Exception:
                        pass
                return [s] if s else []
            return []

        results.append({
            "i": i,
            "pub_id": pid,
            "title": pub["title"],
            "year": pub.get("year"),
            "fulltext_chars": pub.get("fulltext_chars"),
            "opus": {
                "summary_de": opus_sum.get("summary_de", ""),
                "key_terms": opus_sum.get("key_terms", []),
                "named_thinkers": opus_sum.get("named_thinkers", []),
                "methods": opus_sum.get("methods", []),
                "cases_examples": opus_sum.get("cases_examples", []),
            },
            "mimo": {
                "summary_de": mimo.get("summary_de", ""),
                "key_terms": _coerce(mimo.get("key_terms")),
                "named_thinkers": _coerce(mimo.get("named_thinkers")),
                "methods": _coerce(mimo.get("methods")),
                "cases_examples": _coerce(mimo.get("cases_examples")),
                "cost_usd": res.get("cost_usd"),
                "cache_pct": res.get("cache_pct"),
                "latency_s": res.get("latency_s"),
                "tokens_in": res.get("tokens_in"),
                "tokens_out": res.get("tokens_out"),
                "error": res.get("error"),
            },
        })
        print(f"  #{i}/{len(pub_ids)}  {pid}  ${res.get('cost_usd',0):.4f}  cache={res.get('cache_pct',0):.0f}%  "
              f"keys={len(results[-1]['mimo']['key_terms'])} thinkers={len(results[-1]['mimo']['named_thinkers'])}")

    (DOCS / "qcheck_summarize.json").write_text(json.dumps({"results": results, "ts": datetime.now().isoformat()}, ensure_ascii=False, indent=2, default=str))

    md = [
        f"# Q-Check Summarize — MiMo vs vorhandene Opus-Datensätze",
        f"",
        f"**Datum:** {datetime.now().isoformat()}",
        f"**Stichprobe:** {len(results)} Publikationen aus summaries.json (Opus-generiert)",
        f"**MiMo-Konfig:** `xiaomi/mimo-v2.5-pro`, `tool_choice='auto'`, `cache_control: ephemeral`",
        f"**MiMo total cost:** ${total_cost:.4f}",
        f"",
    ]
    for r in results:
        md.append(f"## #{r['i']} `{r['pub_id']}` ({r['year']}) — {r['title']}")
        md.append("")
        md.append(f"_MiMo Kosten:_ ${r['mimo']['cost_usd']:.4f} · _Cache:_ {r['mimo']['cache_pct']}% · _Latency:_ {r['mimo']['latency_s']}s")
        md.append("")
        md.append(f"### Opus key_terms ({len(r['opus']['key_terms'])})")
        md.append("- " + "\n- ".join(r['opus']['key_terms']))
        md.append("")
        md.append(f"### MiMo key_terms ({len(r['mimo']['key_terms'])})")
        md.append("- " + "\n- ".join(r['mimo']['key_terms']))
        md.append("")
        md.append(f"### Opus named_thinkers ({len(r['opus']['named_thinkers'])})")
        md.append("- " + "\n- ".join(r['opus']['named_thinkers']))
        md.append("")
        md.append(f"### MiMo named_thinkers ({len(r['mimo']['named_thinkers'])})")
        md.append("- " + "\n- ".join(r['mimo']['named_thinkers']))
        md.append("")
        md.append(f"### Opus methods ({len(r['opus']['methods'])})")
        md.append("- " + "\n- ".join(r['opus']['methods']))
        md.append("")
        md.append(f"### MiMo methods ({len(r['mimo']['methods'])})")
        md.append("- " + "\n- ".join(r['mimo']['methods']))
        md.append("")
        md.append(f"### Opus summary_de")
        md.append(r['opus']['summary_de'])
        md.append("")
        md.append(f"### MiMo summary_de")
        md.append(r['mimo']['summary_de'])
        md.append("")
        md.append("---")
        md.append("")

    (DOCS / "qcheck_summarize.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  -> docs/qcheck_summarize.md")
    return results


# ────────────────────────────────────────────────────────────────────
# Trends-Q-Check
# ────────────────────────────────────────────────────────────────────


def qcheck_trends(clusters: list[str] | None = None):
    print("\n=== Q-CHECK TRENDS ===")
    if clusters is None:
        clusters = ["digitale_kultur", "medienpaed", "erziehungswiss"]
    store = Store()
    this_year = datetime.now().year
    start_year = this_year - 2

    # Opus-Output aus existierender sarah_v2-Datei recyclen (spart $0.50)
    opus_by_cluster: dict[str, dict] = {}
    opus_src = DOCS / "cost_test_sarah_v2_mimo_cached.json"
    if opus_src.exists():
        prior = json.loads(opus_src.read_text())
        for r in prior.get("results", {}).get("trends", []):
            if r.get("route") == "opus":
                opus_by_cluster[r["cluster"]] = r
        print(f"  (Opus-Baselines aus {opus_src.name}: {len(opus_by_cluster)} Cluster)")

    results: list[dict] = []
    total_mimo = 0.0
    total_opus_recycled = sum(r.get("cost_usd", 0) for r in opus_by_cluster.values())

    for i, ckey in enumerate(clusters, 1):
        meta = DISCOURSE_SPACES[ckey]
        journals = [j.short for j in journals_in_cluster(ckey)]
        arts = store.find_in_window(start_year=start_year, journals=journals)
        arts = [a for a in arts if a.title and (a.openalex_abstract or a.abstract)][:40]

        journal_list = ", ".join(sorted(set(a.journal_short for a in arts)))
        window_label = f"{start_year}–{this_year}"
        parts = [
            f"DISKURSRAUM:   {meta['name']}",
            f"BESCHREIBUNG:  {meta['description']}",
            f"ZEITFENSTER:   {window_label}",
            f"JOURNALS:      {journal_list}",
            f"ARTIKELANZAHL: {len(arts)}",
            "",
            "=== ARTIKEL ===",
        ]
        for j, sa in enumerate(arts, 1):
            parts.append("")
            parts.append(_format_article_for_llm(sa, j))
        user_content = "\n".join(parts)
        system_prompt = TRENDS_SYSTEM_PROMPT.format(
            cluster_name=meta["name"],
            cluster_description=meta["description"],
            window=window_label,
        )

        # Opus: recycled (kein neuer Call)
        opus_rec = opus_by_cluster.get(ckey, {})
        opus_text = opus_rec.get("markdown", "") or ""
        opus_cost = opus_rec.get("cost_usd", 0)
        opus_lat = opus_rec.get("latency_s", 0)
        opus_tin = opus_rec.get("tokens_in", 0)
        opus_tout = opus_rec.get("tokens_out", 0)

        # MiMo: frisch
        mimo_route = ROUTES["mimo"]
        client_mimo = build_client(mimo_route.provider)
        msgs_mimo = make_messages(system_prompt, user_content, mimo_route)
        t0 = time.time()
        resp_m = client_mimo.chat.completions.create(
            model=mimo_route.model, max_tokens=32000, messages=msgs_mimo,
        )
        s_m = extract_stats(resp_m.usage, mimo_route)
        mimo_text = resp_m.choices[0].message.content or ""
        mimo_lat = round(time.time() - t0, 2)
        total_mimo += s_m.cost_usd

        results.append({
            "cluster": ckey,
            "cluster_name": meta["name"],
            "articles_count": len(arts),
            "opus": {"cost_usd": opus_cost, "tokens_in": opus_tin, "tokens_out": opus_tout,
                     "cache_pct": 0, "latency_s": opus_lat,
                     "output_chars": len(opus_text), "text": opus_text,
                     "_source": "recycled from cost_test_sarah_v2_mimo_cached.json"},
            "mimo": {"cost_usd": round(s_m.cost_usd, 5), "tokens_in": s_m.tokens_in, "tokens_out": s_m.tokens_out,
                     "cache_pct": round(s_m.cached_read / max(s_m.tokens_in, 1) * 100, 1),
                     "latency_s": mimo_lat, "output_chars": len(mimo_text), "text": mimo_text},
        })
        print(f"  #{i}/{len(clusters)} {ckey}: opus(recyc) ${opus_cost:.4f}/{len(opus_text):,}c   mimo ${s_m.cost_usd:.4f}/{len(mimo_text):,}c  cache_m={results[-1]['mimo']['cache_pct']}%")

    total_opus = total_opus_recycled

    (DOCS / "qcheck_trends.json").write_text(json.dumps({"results": results, "ts": datetime.now().isoformat()}, ensure_ascii=False, indent=2, default=str))

    md = [
        f"# Q-Check Trends — MiMo vs Opus (frische Generierung pro Cluster)",
        f"",
        f"**Datum:** {datetime.now().isoformat()}",
        f"**Cluster:** {', '.join(clusters)}",
        f"**Opus total:** ${total_opus:.4f} · **MiMo total:** ${total_mimo:.4f}",
        f"",
    ]
    for r in results:
        md.append(f"## Cluster: `{r['cluster']}` — {r['cluster_name']}")
        md.append("")
        md.append(f"_Opus:_ ${r['opus']['cost_usd']:.4f} · {r['opus']['output_chars']:,} chars · {r['opus']['latency_s']}s · cache={r['opus']['cache_pct']}%")
        md.append(f"_MiMo:_ ${r['mimo']['cost_usd']:.4f} · {r['mimo']['output_chars']:,} chars · {r['mimo']['latency_s']}s · cache={r['mimo']['cache_pct']}%")
        md.append("")
        md.append(f"### Opus-Output")
        md.append("")
        md.append(r['opus']['text'])
        md.append("")
        md.append(f"### MiMo-Output")
        md.append("")
        md.append(r['mimo']['text'])
        md.append("")
        md.append("---")
        md.append("")

    (DOCS / "qcheck_trends.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  -> docs/qcheck_trends.md")
    return results


# ────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--op", choices=["assessment", "summarize", "trends", "all"], default="all")
    args = ap.parse_args()
    ops = ["assessment", "summarize", "trends"] if args.op == "all" else [args.op]
    if "assessment" in ops:
        qcheck_assessment()
    if "summarize" in ops:
        qcheck_summarize()
    if "trends" in ops:
        qcheck_trends()


if __name__ == "__main__":
    main()
