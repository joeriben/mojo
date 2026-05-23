"""Cost/Substanz-Test: Mistral Large + MiMo 2.5 Pro gegen Opus 4.6 für die teuersten MOJO-Operationen.

Inspiriert vom SARAH-Stack (`feedback_kosten_differenzierung`, SARAH model-tiers.ts):
Dort hat sich Mistral Large für hochvolumige Per-Atom-Calls und MiMo 2.5 Pro für
Synthese-Stufen als ~1/10 bis 1/20 der Opus-Kosten bei vergleichbarer Substanz
herausgestellt. Hier prüfen wir das für MOJOs Pendants:

  - Assessment (agent.run_agent mit allow_read=False) — Tool-Use, dominanter Kostenposten
  - Summarize (summarize.run) — Tool-Use, skaliert mit Corpus-Wachstum
  - Trends (trends.run) — Markdown-Prose, Long-Context-Synthese

Pro Operation laufen wir 3 Test-Eingaben durch alle Kandidaten-Modelle, vergleichen
Kosten und schreiben die Outputs zur händischen Substanzprüfung in ein Report-JSON.

Aufruf:
    python scripts/test_alt_models.py --op assessment --n 3
    python scripts/test_alt_models.py --op summarize --n 2
    python scripts/test_alt_models.py --op trends --n 1
    python scripts/test_alt_models.py --op all
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from journal_bot.agent import (
    ASSESSMENT_OUTRO,
    TOOLS,
    _format_new_article,
    build_system_prompt,
)
from journal_bot.citation_tracker import find_citations, format_for_agent
from journal_bot.multi_provider import (
    ROUTES,
    Route,
    build_client,
    extract_stats,
    make_messages,
)
from journal_bot.settings import (
    CORPUS_JSON,
    DISCOURSE_SPACES,
    SUMMARIES_JSON,
    journals_in_cluster,
)
from journal_bot.store import Store
from journal_bot.summarize import SUMMARY_TOOL, SYSTEM as SUMMARIZE_SYSTEM, USER_TEMPLATE as SUMMARIZE_USER_TEMPLATE
from journal_bot.trends import SYSTEM_PROMPT as TRENDS_SYSTEM_PROMPT, _format_article_for_llm


# Tool-Use-only-Subset (Assessment-Phase: nur submit_digest_entry)
TOOLS_SUBMIT_ONLY = [t for t in TOOLS if t["function"]["name"] == "submit_digest_entry"]


# SARAH-Stack-konformer Vergleich, NICHT Quermatrix:
#   - assessment (basal, viele Calls hintereinander, Cache-amortisierend):
#       Opus (Baseline) vs Mistral (SARAH `aa.paragraph` recommended)
#   - summarize (synthesis-shaped, wenig Calls, prose-output via Tool-Use):
#       Opus (Baseline) vs MiMo (SARAH `aa.synthesis`/`ri.paragraph` recommended)
#   - trends (synthesis-shaped, wenige Calls, Long-Context):
#       Opus (Baseline) vs MiMo
# Mistral-Cache greift erst ab ~Call 3-6 (server-side implicit prefix caching).
# Deshalb n_per_verdict bei assessment hochsetzen, damit Cache messbar wird.
ROUTE_KEYS_PER_OP: dict[str, list[str]] = {
    "assessment": ["opus", "mistral"],
    "summarize":  ["opus", "mimo"],
    "trends":     ["opus", "mimo"],
}


def _resolve_routes(op: str) -> list[Route]:
    return [ROUTES[k] for k in ROUTE_KEYS_PER_OP[op]]


# ────────────────────────────────────────────────────────────────────
# Gemeinsamer Single-Shot-Call
# ────────────────────────────────────────────────────────────────────


def call_route(
    route: Route,
    system_prompt: str,
    user_content: str,
    *,
    tools: list[dict] | None = None,
    tool_choice: dict | str | None = None,
    max_tokens: int = 2000,
    temperature: float | None = None,
    second_user: str | None = None,
) -> dict[str, Any]:
    client = build_client(route.provider)
    messages = make_messages(system_prompt, user_content, route, second_user_for_sticky_routing=second_user)

    params: dict[str, Any] = {
        "model": route.model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if tools:
        params["tools"] = tools
    if tool_choice is not None:
        params["tool_choice"] = tool_choice
    if temperature is not None:
        params["temperature"] = temperature

    t0 = time.time()
    # 429-Backoff: OpenRouter/MiMo throttelt manchmal — drei Versuche mit
    # wachsendem Wait reichen für die Test-Cadence.
    backoffs_s = [0, 5, 15, 45]
    last_err: Exception | None = None
    resp = None
    for attempt, wait in enumerate(backoffs_s):
        if wait > 0:
            time.sleep(wait)
        try:
            resp = client.chat.completions.create(**params)
            break
        except Exception as e:
            last_err = e
            status = getattr(e, "status_code", None) or getattr(e, "status", None)
            msg = str(e)
            if status == 429 or " 429 " in msg or "rate-limited" in msg.lower():
                continue
            break
    if resp is None:
        return {
            "route": route.label,
            "model": route.model,
            "provider": route.provider,
            "error": f"{type(last_err).__name__}: {str(last_err)[:600]}",
            "latency_s": round(time.time() - t0, 2),
        }
    latency = time.time() - t0

    choice = resp.choices[0]
    msg = choice.message
    stats = extract_stats(resp.usage, route)

    out: dict[str, Any] = {
        "route": route.label,
        "model": route.model,
        "provider": route.provider,
        "finish_reason": choice.finish_reason,
        "tokens_in": stats.tokens_in,
        "tokens_out": stats.tokens_out,
        "cached_read": stats.cached_read,
        "cost_usd": round(stats.cost_usd, 5),
        "cost_fallback_estimated": stats.fallback_cost,
        "latency_s": round(latency, 2),
        "text": (msg.content or "")[:4000] if msg.content else "",
    }

    # Tool-Calls einsammeln
    tool_calls = getattr(msg, "tool_calls", None) or []
    if tool_calls:
        out["tool_calls"] = []
        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except Exception:
                args = {"_raw_arguments": tc.function.arguments}
            out["tool_calls"].append({
                "name": tc.function.name,
                "arguments": args,
            })
    return out


# ────────────────────────────────────────────────────────────────────
# Operation 1: Assessment (run_agent mit allow_read=False, 1 Iteration)
# ────────────────────────────────────────────────────────────────────


def _build_assessment_prompts(article_row: dict) -> tuple[str, str]:
    summaries_data = json.loads(SUMMARIES_JSON.read_text(encoding="utf-8"))
    system_prompt = build_system_prompt(summaries_data["summaries"], outro=ASSESSMENT_OUTRO)

    # User-Content rekonstruieren wie agent.run_agent es täte
    new_article = {
        "title": article_row["title"],
        "authors": json.loads(article_row.get("authors_json") or "[]"),
        "abstract": article_row.get("openalex_abstract") or article_row.get("abstract") or "",
        "doi": article_row.get("doi") or "",
        "url": article_row.get("url") or "",
        "journal": article_row.get("journal_full") or article_row.get("journal_short") or "",
    }
    enrichment_data = {
        "openalex_abstract": article_row.get("openalex_abstract") or "",
        "references_crossref": json.loads(article_row.get("crossref_refs") or "[]") or [],
        "openalex_concepts": json.loads(article_row.get("openalex_concepts") or "[]") or [],
        "openalex_topics": json.loads(article_row.get("openalex_topics") or "[]") or [],
    }

    corpus_data = json.loads(CORPUS_JSON.read_text(encoding="utf-8"))
    authored_all = corpus_data.get("authored_all", [])
    citation_hits = find_citations(
        enrichment_data["references_crossref"],
        authored_all,
    )
    citations_block = format_for_agent(citation_hits)
    user_content = _format_new_article(new_article, enrichment_data) + citations_block
    return system_prompt, user_content


def _pick_assessment_articles(n: int) -> list[dict]:
    """Mix aus lesenswert / scannen / ignorieren, alle mit Abstract."""
    store = Store()
    rows: list[dict] = []
    with store._conn() as conn:
        for verdict in ("lesenswert", "scannen", "ignorieren"):
            cur = conn.execute(
                """
                SELECT * FROM articles
                WHERE agent_processed_at IS NOT NULL
                  AND agent_verdict = ?
                  AND COALESCE(openalex_abstract, abstract) != ''
                  AND LENGTH(COALESCE(openalex_abstract, abstract)) > 600
                ORDER BY RANDOM()
                LIMIT ?
                """,
                (verdict, n),
            )
            for row in cur.fetchall():
                rows.append(dict(row))
    return rows


def run_assessment_test(n_per_verdict: int, routes: list[Route]) -> list[dict]:
    articles = _pick_assessment_articles(n_per_verdict)
    print(f"[assess] {len(articles)} Test-Artikel ausgewählt.")

    results: list[dict] = []
    for i, article in enumerate(articles, 1):
        print(f"\n[assess] === Artikel {i}/{len(articles)} — {article['journal_short']} — "
              f"original verdict: {article['agent_verdict']} ===")
        system_prompt, user_content = _build_assessment_prompts(article)
        print(f"[assess] System ~{len(system_prompt)//4} Tok, User ~{len(user_content)//4} Tok")

        # Originale Agent-Antwort als Referenz
        original_entry = json.loads(article.get("agent_entry_json") or "{}")
        article_record: dict[str, Any] = {
            "article_id": article["id"],
            "journal": article["journal_short"],
            "title": article["title"][:160],
            "original_verdict": article.get("agent_verdict"),
            "original_cost_usd": article.get("cost_usd"),
            "original_tokens_in": article.get("tokens_in"),
            "original_tokens_out": article.get("tokens_out"),
            "original_iterations": article.get("iterations"),
            "original_entry": {
                "kernthese": original_entry.get("kernthese", "")[:600],
                "bezuege_count": len(original_entry.get("bezuege") or []),
                "bemerkenswert_count": len(original_entry.get("bemerkenswert") or []),
            },
            "by_route": [],
        }

        for route in routes:
            print(f"[assess]   → {route.label}")
            res = call_route(
                route=route,
                system_prompt=system_prompt,
                user_content=user_content,
                tools=TOOLS_SUBMIT_ONLY,
                tool_choice={"type": "function", "function": {"name": "submit_digest_entry"}},
                max_tokens=2500,
            )
            # Verdict aus Tool-Call ziehen, falls vorhanden
            entry = None
            for tc in res.get("tool_calls") or []:
                if tc["name"] == "submit_digest_entry":
                    entry = tc["arguments"]
                    break
            if entry:
                res["verdict"] = entry.get("verdict")
                res["kernthese"] = (entry.get("kernthese") or "")[:600]
                res["bezuege_count"] = len(entry.get("bezuege") or [])
                res["bemerkenswert_count"] = len(entry.get("bemerkenswert") or [])
                res["bemerkenswert_sample"] = (entry.get("bemerkenswert") or [None])[:2]
                res["verdict_begruendung"] = (entry.get("verdict_begruendung") or "")[:300]
            else:
                res["verdict"] = None
            article_record["by_route"].append(res)

            cost = res.get("cost_usd", 0.0)
            v = res.get("verdict")
            err = res.get("error")
            if err:
                print(f"[assess]     ERROR: {err[:200]}")
            else:
                cached = res.get("cached_read", 0)
                cache_pct = (cached / max(res["tokens_in"], 1)) * 100
                print(f"[assess]     verdict={v}  cost=${cost:.4f}  tok={res['tokens_in']}/{res['tokens_out']}  cache={cached}/{res['tokens_in']} ({cache_pct:.0f}%)")
        results.append(article_record)
    return results


# ────────────────────────────────────────────────────────────────────
# Operation 2: Summarize (rein faktisch, Tool-Use)
# ────────────────────────────────────────────────────────────────────


def _pick_summarize_pubs(n: int) -> list[dict]:
    """Wir nutzen Einträge aus corpus.json mit Volltext."""
    corpus_data = json.loads(CORPUS_JSON.read_text(encoding="utf-8"))
    pubs = corpus_data["publications"]
    with_text = [
        p for p in pubs
        if p.get("fulltext_chars", 0) > 5000 and p.get("fulltext_chars", 0) < 100_000
    ]
    # Deterministisch: nach Größe in der Mitte (typische Publikationslänge)
    with_text.sort(key=lambda p: p["fulltext_chars"])
    mid = len(with_text) // 2
    return with_text[mid - n // 2 : mid + (n + 1) // 2]


def run_summarize_test(n: int, routes: list[Route]) -> list[dict]:
    pubs = _pick_summarize_pubs(n)
    print(f"[summarize] {len(pubs)} Test-Publikationen ausgewählt.")

    summaries_existing = json.loads(SUMMARIES_JSON.read_text(encoding="utf-8")).get("summaries", {})
    results: list[dict] = []
    for i, pub in enumerate(pubs, 1):
        print(f"\n[summarize] === Pub {i}/{len(pubs)} — {pub.get('year')} — "
              f"{pub['title'][:80]} (Volltext {pub['fulltext_chars']:,} chars) ===")
        fulltext = pub["fulltext"][:560_000]
        user_msg = SUMMARIZE_USER_TEMPLATE.format(
            title=pub["title"],
            authors=", ".join(pub["authors"]),
            year=pub.get("year") or "",
            venue=pub.get("venue") or "",
            fulltext=fulltext,
        )
        print(f"[summarize] System ~{len(SUMMARIZE_SYSTEM)//4} Tok, User ~{len(user_msg)//4} Tok")

        existing = summaries_existing.get(pub["pub_id"], {})
        record: dict[str, Any] = {
            "pub_id": pub["pub_id"],
            "title": pub["title"][:160],
            "year": pub.get("year"),
            "fulltext_chars": pub["fulltext_chars"],
            "existing_summary": {
                "summary_de": (existing.get("summary_de") or "")[:600],
                "key_terms": existing.get("key_terms") or [],
                "named_thinkers": existing.get("named_thinkers") or [],
            },
            "by_route": [],
        }

        for route in routes:
            print(f"[summarize]   → {route.label}")
            res = call_route(
                route=route,
                system_prompt=SUMMARIZE_SYSTEM,
                user_content=user_msg,
                tools=[SUMMARY_TOOL],
                tool_choice={"type": "function", "function": {"name": "record_summary"}},
                max_tokens=1500,
            )
            tool_args = None
            for tc in res.get("tool_calls") or []:
                if tc["name"] == "record_summary":
                    tool_args = tc["arguments"]
                    break
            if tool_args:
                # Normalisieren — Haiku-Pattern: Arrays als JSON-String
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

                res["summary_de"] = (tool_args.get("summary_de") or "")[:800]
                res["key_terms"] = _coerce(tool_args.get("key_terms"))
                res["named_thinkers"] = _coerce(tool_args.get("named_thinkers"))
                res["methods"] = _coerce(tool_args.get("methods"))
                res["cases_examples"] = _coerce(tool_args.get("cases_examples"))
                # Bei Overlap mit Original-Haiku-Summary
                existing_terms_set = {t.lower() for t in (existing.get("key_terms") or [])}
                new_terms_set = {t.lower() for t in res["key_terms"]}
                if existing_terms_set:
                    overlap = len(existing_terms_set & new_terms_set) / len(existing_terms_set)
                    res["key_terms_overlap_with_existing"] = round(overlap, 2)
            record["by_route"].append(res)

            cost = res.get("cost_usd", 0.0)
            err = res.get("error")
            if err:
                print(f"[summarize]     ERROR: {err[:200]}")
            else:
                print(f"[summarize]     cost=${cost:.4f}  tok={res['tokens_in']}/{res['tokens_out']}  "
                      f"keys={len(res.get('key_terms') or [])} thinkers={len(res.get('named_thinkers') or [])}")
        results.append(record)
    return results


# ────────────────────────────────────────────────────────────────────
# Operation 3: Trends (Markdown-Prose, Long-Context-Synthese)
# ────────────────────────────────────────────────────────────────────


def run_trends_test(n_clusters: int, routes: list[Route]) -> list[dict]:
    store = Store()
    this_year = datetime.now().year
    start_year = this_year - 2

    # Cluster auswählen: die mit den meisten Artikeln im Fenster
    cluster_counts = []
    for key, meta in DISCOURSE_SPACES.items():
        journals = [j.short for j in journals_in_cluster(key)]
        if not journals:
            continue
        arts = store.find_in_window(start_year=start_year, journals=journals)
        arts = [a for a in arts if a.title and (a.openalex_abstract or a.abstract)]
        if len(arts) >= 8:
            cluster_counts.append((key, meta, arts))
    cluster_counts.sort(key=lambda x: -len(x[2]))
    chosen = cluster_counts[:n_clusters]

    results: list[dict] = []
    for cluster_key, cluster_meta, articles in chosen:
        # Maximal 40 Artikel pro Cluster, sonst werden die Tests zu teuer
        articles = articles[:40]
        journal_list = ", ".join(sorted(set(a.journal_short for a in articles)))
        window_label = f"{start_year}–{this_year}"

        parts = [
            f"DISKURSRAUM:   {cluster_meta['name']}",
            f"BESCHREIBUNG:  {cluster_meta['description']}",
            f"ZEITFENSTER:   {window_label}",
            f"JOURNALS:      {journal_list}",
            f"ARTIKELANZAHL: {len(articles)}",
            "",
            "=== ARTIKEL ===",
        ]
        for i, sa in enumerate(articles, 1):
            parts.append("")
            parts.append(_format_article_for_llm(sa, i))
        user_content = "\n".join(parts)

        system_prompt = TRENDS_SYSTEM_PROMPT.format(
            cluster_name=cluster_meta["name"],
            cluster_description=cluster_meta["description"],
            window=window_label,
        )

        print(f"\n[trends] === Cluster {cluster_key} ({cluster_meta['name']}) — "
              f"{len(articles)} Artikel ===")
        print(f"[trends] System ~{len(system_prompt)//4} Tok, User ~{len(user_content)//4} Tok")

        record: dict[str, Any] = {
            "cluster": cluster_key,
            "cluster_name": cluster_meta["name"],
            "articles_count": len(articles),
            "by_route": [],
        }

        for route in routes:
            print(f"[trends]   → {route.label}")
            res = call_route(
                route=route,
                system_prompt=system_prompt,
                user_content=user_content,
                max_tokens=5000,
            )
            # Markdown-Text behalten zur händischen Prüfung
            text = res.get("text") or ""
            res["output_length_chars"] = len(text)
            record["by_route"].append(res)

            cost = res.get("cost_usd", 0.0)
            err = res.get("error")
            if err:
                print(f"[trends]     ERROR: {err[:200]}")
            else:
                print(f"[trends]     cost=${cost:.4f}  tok={res['tokens_in']}/{res['tokens_out']}  "
                      f"out_len={len(text):,} chars")
        results.append(record)
    return results


# ────────────────────────────────────────────────────────────────────
# Reporting
# ────────────────────────────────────────────────────────────────────


def summarize_report(report: dict) -> str:
    """Kompaktes Konsolen-Summary über alle Ops."""
    lines = []
    for op, op_results in report.get("operations", {}).items():
        if not op_results:
            continue
        lines.append(f"\n=== {op.upper()} ===")
        # Aggregat pro Route
        per_route: dict[str, dict[str, float]] = {}
        for item in op_results:
            for r in item.get("by_route", []):
                k = r["route"]
                if k not in per_route:
                    per_route[k] = {"n": 0, "errors": 0, "cost": 0.0, "tok_in": 0, "tok_out": 0}
                per_route[k]["n"] += 1
                if r.get("error"):
                    per_route[k]["errors"] += 1
                    continue
                per_route[k]["cost"] += r.get("cost_usd", 0.0)
                per_route[k]["tok_in"] += r.get("tokens_in", 0)
                per_route[k]["tok_out"] += r.get("tokens_out", 0)
        # Baseline = Opus zum Vergleich
        baseline_cost = next(
            (v["cost"] for k, v in per_route.items() if "Opus" in k),
            None,
        )
        for k, v in per_route.items():
            n_ok = v["n"] - v["errors"]
            avg_cost = (v["cost"] / n_ok) if n_ok else 0.0
            ratio = (v["cost"] / baseline_cost) if baseline_cost else None
            ratio_str = f"  ({ratio*100:>5.1f}% von Opus)" if ratio is not None and "Opus" not in k else ""
            err_str = f"  ERR {v['errors']}" if v["errors"] else ""
            lines.append(
                f"  {k:<46s} avg ${avg_cost:.4f}  total ${v['cost']:.4f}{ratio_str}{err_str}"
            )
    return "\n".join(lines)


# ────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--op", choices=["assessment", "summarize", "trends", "all"], default="all")
    ap.add_argument("--n", type=int, default=2,
                    help="Pro Verdict/Operation, n=2 ist meist genug für Cost-Signal.")
    ap.add_argument("--out", default=None,
                    help="Output-JSON-Pfad (default: docs/cost_test_<timestamp>.json)")
    ap.add_argument("--routes", default=None,
                    help="Komma-Liste von Route-Keys (überschreibt Default pro Operation).")
    args = ap.parse_args()

    out_path = Path(args.out) if args.out else Path("docs") / f"cost_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "started_at": datetime.now().isoformat(),
        "n_per_verdict": args.n,
        "routes_per_op": ROUTE_KEYS_PER_OP,
        "operations": {},
    }

    ops_to_run = ["assessment", "summarize", "trends"] if args.op == "all" else [args.op]

    for op in ops_to_run:
        if args.routes:
            keys = [k.strip() for k in args.routes.split(",") if k.strip()]
            routes = [ROUTES[k] for k in keys]
        else:
            routes = _resolve_routes(op)
        try:
            if op == "assessment":
                report["operations"]["assessment"] = run_assessment_test(args.n, routes)
            elif op == "summarize":
                report["operations"]["summarize"] = run_summarize_test(args.n, routes)
            elif op == "trends":
                report["operations"]["trends"] = run_trends_test(args.n, routes)
        except Exception as e:
            print(f"\n[!] Operation {op!r} fehlgeschlagen: {e}")
            traceback.print_exc()
            report["operations"][op] = {"_error": str(e), "_traceback": traceback.format_exc()}

        # Inkrementell wegschreiben — falls nächste Op crasht, haben wir Ergebnisse
        out_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )

    report["finished_at"] = datetime.now().isoformat()
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print("\n" + "=" * 70)
    print(summarize_report(report))
    print("=" * 70)
    print(f"\nBericht geschrieben: {out_path}")


if __name__ == "__main__":
    main()
