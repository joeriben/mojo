"""Vernünftiger Test: SARAH-Stack (Mistral basal + MiMo synthesis) vs. Opus für MOJOs teuerste Operationen.

Im Unterschied zu test_alt_models.py (Matrix-Lauf, kleine Stichproben, kein
Cache-Warmup) testet dieses Skript SARAHs konkrete Modellzuweisung:

  - Assessment (basal, Cache-amortisiert): Opus 4.6 vs Mistral Large nativ
    20 Artikel hintereinander pro Modell → Mistral-Implicit-Cache wird warm
  - Summarize (synthesis, Tool-Use, kein Cache): Opus vs MiMo 2.5 Pro
  - Trends (synthesis, Long-Context Prose, kein Cache): Opus vs MiMo

Reproduzierbar: Artikel-IDs + Pub-IDs + Cluster aus scripts/cost_test_fixture.json,
nicht zufällig gezogen.

Pro Call wird geloggt:
  - Reihenfolge (call_index), damit Cache-Warmup messbar ist
  - cost, cached_read, latency, finish_reason, tokens_in/out
  - Tool-Args (verdict, summary_de, key_terms, named_thinkers, ...)
  - Bei trends/MiMo: voller Markdown-Output

Konkordanz-Metriken (Mistral/MiMo vs Opus als Goldstand):
  - Assessment: verdict-Match-Quote, Kernthese-Termoverlap
  - Summarize: Jaccard key_terms, Jaccard named_thinkers, Jaccard methods
  - Trends: erwähnte Artikel-IDs, Output-Länge

Aufruf:
    python scripts/test_sarah_v2.py            # alle drei Ops
    python scripts/test_sarah_v2.py --op assessment
    python scripts/test_sarah_v2.py --resume   # fortsetzen falls abgebrochen
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import traceback
from datetime import datetime
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
from journal_bot.summarize import (
    SUMMARY_TOOL,
    SYSTEM as SUMMARIZE_SYSTEM,
    USER_TEMPLATE as SUMMARIZE_USER_TEMPLATE,
)
from journal_bot.trends import SYSTEM_PROMPT as TRENDS_SYSTEM_PROMPT, _format_article_for_llm


FIXTURE_PATH = Path(__file__).parent / "cost_test_fixture.json"
TOOLS_SUBMIT_ONLY = [t for t in TOOLS if t["function"]["name"] == "submit_digest_entry"]


# ────────────────────────────────────────────────────────────────────
# SARAH-Tier-Zuweisung
# ────────────────────────────────────────────────────────────────────
#
# aa.paragraph  (basal, viele Calls, Cache-amortisiert) → Mistral Large
# aa.synthesis  (synthesis, wenige Calls, prose)       → MiMo 2.5 Pro
# ri.paragraph  (per-Absatz-Memo, prose)               → MiMo 2.5 Pro
#
# Opus dient als Goldstandard für Substanz-Vergleich.

PAIRS_PER_OP: dict[str, tuple[str, str]] = {
    # Mistral ist im Run 1 für assessment durch Verdict-Bias durchgefallen
    # (4/20 verdict-match, 0× "ignorieren") → MiMo übernimmt die Alt-Spur
    # für alle drei Operationen. MiMo mit cache_control aktivem ephemeral-Cache.
    "assessment": ("opus", "mimo"),
    "summarize":  ("opus", "mimo"),
    "trends":     ("opus", "mimo"),
}


# ────────────────────────────────────────────────────────────────────
# Single-Shot-Call mit 429-Retry
# ────────────────────────────────────────────────────────────────────


def call_route(
    route: Route,
    system_prompt: str,
    user_content: str,
    *,
    tools: list[dict] | None = None,
    tool_choice: dict | str | None = None,
    max_tokens: int = 2500,
    temperature: float | None = None,
) -> dict[str, Any]:
    client = build_client(route.provider)
    messages = make_messages(system_prompt, user_content, route)

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
    backoffs_s = [0, 5, 15, 45]
    last_err: Exception | None = None
    resp = None
    for wait in backoffs_s:
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
        "text": (msg.content or ""),
    }

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
# Fixture
# ────────────────────────────────────────────────────────────────────


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


# ────────────────────────────────────────────────────────────────────
# Assessment-Runner
# ────────────────────────────────────────────────────────────────────


def _build_assessment_prompts(article_row: dict) -> tuple[str, str]:
    summaries_data = json.loads(SUMMARIES_JSON.read_text(encoding="utf-8"))
    system_prompt = build_system_prompt(summaries_data["summaries"], outro=ASSESSMENT_OUTRO)

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
    citation_hits = find_citations(enrichment_data["references_crossref"], authored_all)
    citations_block = format_for_agent(citation_hits)
    user_content = _format_new_article(new_article, enrichment_data) + citations_block
    return system_prompt, user_content


def run_assessment(article_ids: list[str], pair: tuple[str, str]) -> list[dict]:
    """Pro Modell die volle Sequenz hintereinander → Cache wird warm."""
    store = Store()
    results: list[dict] = []
    # Artikel-Rows laden (in fixture-Reihenfolge)
    rows_by_id: dict[str, dict] = {}
    with store._conn() as conn:
        cur = conn.execute(
            f"SELECT * FROM articles WHERE id IN ({','.join(['?']*len(article_ids))})",
            article_ids,
        )
        for r in cur.fetchall():
            rows_by_id[r["id"]] = dict(r)
    rows = [rows_by_id[i] for i in article_ids if i in rows_by_id]

    # Pre-baue prompts (System-Prompt ist identisch für alle Calls — wichtig für Cache)
    prepared: list[tuple[dict, str, str]] = []
    for r in rows:
        sysp, userc = _build_assessment_prompts(r)
        prepared.append((r, sysp, userc))

    for route_key in pair:
        route = ROUTES[route_key]
        print(f"\n[assess] === MODELL: {route.label} — {len(prepared)} Artikel ===")
        # BUG-FIX 2026-05-16: tool_choice={"type":"function",...} (forced) bricht
        # den MiMo-Cache auf OpenRouter (empirisch verifiziert: 0% vs 99% Hit-Rate
        # zwischen forced und auto). Opus ist davon nicht betroffen.
        # Workaround: tool_choice="auto" für MiMo, forced für Opus.
        tool_choice_for_route: dict | str = (
            "auto" if route_key == "mimo"
            else {"type": "function", "function": {"name": "submit_digest_entry"}}
        )
        for call_idx, (article, system_prompt, user_content) in enumerate(prepared, 1):
            res = call_route(
                route=route,
                system_prompt=system_prompt,
                user_content=user_content,
                tools=TOOLS_SUBMIT_ONLY,
                tool_choice=tool_choice_for_route,
                max_tokens=2500,
            )
            entry_args = None
            for tc in res.get("tool_calls") or []:
                if tc["name"] == "submit_digest_entry":
                    entry_args = tc["arguments"]
                    break

            verdict = entry_args.get("verdict") if entry_args else None
            kernthese = (entry_args.get("kernthese") or "")[:1000] if entry_args else ""
            bezuege = entry_args.get("bezuege") or [] if entry_args else []
            bemerk = entry_args.get("bemerkenswert") or [] if entry_args else []

            cached = res.get("cached_read", 0)
            tin = res.get("tokens_in", 0)
            cache_pct = (cached / tin * 100) if tin else 0
            err_marker = ""
            if res.get("error"):
                err_marker = f" ERROR={res['error'][:80]}"
            elif res.get("finish_reason") == "error" or not entry_args:
                err_marker = f" FAIL finish={res.get('finish_reason')}"

            print(f"[assess] {route_key:<8} #{call_idx:>2}/{len(prepared)}  "
                  f"{article['journal_short']:>12}  "
                  f"verdict={str(verdict):<11} cost=${res.get('cost_usd', 0):.4f}  "
                  f"tok={tin}/{res.get('tokens_out', 0)}  "
                  f"cache={cache_pct:.0f}%  lat={res.get('latency_s', 0):.0f}s{err_marker}")

            results.append({
                "operation": "assessment",
                "route": route_key,
                "call_index": call_idx,
                "article_id": article["id"],
                "journal": article["journal_short"],
                "title": article["title"][:160],
                "orig_db_verdict": article.get("agent_verdict"),
                "orig_db_cost": article.get("cost_usd"),
                "cost_usd": res.get("cost_usd"),
                "cost_fallback_estimated": res.get("cost_fallback_estimated"),
                "tokens_in": tin,
                "tokens_out": res.get("tokens_out"),
                "cached_read": cached,
                "cache_pct": round(cache_pct, 1),
                "latency_s": res.get("latency_s"),
                "finish_reason": res.get("finish_reason"),
                "error": res.get("error"),
                "verdict": verdict,
                "kernthese": kernthese,
                "verdict_begruendung": (entry_args.get("verdict_begruendung") or "")[:400] if entry_args else "",
                "bezuege_count": len(bezuege),
                "bemerkenswert_count": len(bemerk),
                "bemerkenswert_sample": bemerk[:3] if bemerk else [],
                "tool_args_full": entry_args,  # für spätere Inspektion
            })
    return results


# ────────────────────────────────────────────────────────────────────
# Summarize-Runner
# ────────────────────────────────────────────────────────────────────


def run_summarize(pub_ids: list[str], pair: tuple[str, str]) -> list[dict]:
    corpus = json.loads(CORPUS_JSON.read_text(encoding="utf-8"))
    pubs_by_id = {p["pub_id"]: p for p in corpus["publications"]}
    pubs = [pubs_by_id[pid] for pid in pub_ids if pid in pubs_by_id]

    results: list[dict] = []
    for route_key in pair:
        route = ROUTES[route_key]
        print(f"\n[summarize] === MODELL: {route.label} — {len(pubs)} Publikationen ===")
        for call_idx, pub in enumerate(pubs, 1):
            fulltext = pub["fulltext"][:560_000]
            user_msg = SUMMARIZE_USER_TEMPLATE.format(
                title=pub["title"],
                authors=", ".join(pub["authors"]),
                year=pub.get("year") or "",
                venue=pub.get("venue") or "",
                fulltext=fulltext,
            )
            # Siehe BUG-FIX in run_assessment: MiMo-Cache bricht bei forced tool_choice.
            tool_choice_for_route: dict | str = (
                "auto" if route_key == "mimo"
                else {"type": "function", "function": {"name": "record_summary"}}
            )
            res = call_route(
                route=route,
                system_prompt=SUMMARIZE_SYSTEM,
                user_content=user_msg,
                tools=[SUMMARY_TOOL],
                tool_choice=tool_choice_for_route,
                max_tokens=2000,
            )
            tool_args = None
            for tc in res.get("tool_calls") or []:
                if tc["name"] == "record_summary":
                    tool_args = tc["arguments"]
                    break

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

            key_terms = _coerce(tool_args.get("key_terms")) if tool_args else []
            thinkers = _coerce(tool_args.get("named_thinkers")) if tool_args else []
            methods = _coerce(tool_args.get("methods")) if tool_args else []
            cases = _coerce(tool_args.get("cases_examples")) if tool_args else []
            summary_de = tool_args.get("summary_de", "") if tool_args else ""

            err_marker = ""
            if res.get("error"):
                err_marker = f" ERROR={res['error'][:80]}"
            elif not tool_args:
                err_marker = f" FAIL finish={res.get('finish_reason')}"

            print(f"[summarize] {route_key:<8} #{call_idx}/{len(pubs)}  "
                  f"{pub['pub_id']}  "
                  f"cost=${res.get('cost_usd', 0):.4f}  "
                  f"tok={res.get('tokens_in', 0)}/{res.get('tokens_out', 0)}  "
                  f"keys={len(key_terms)} thinkers={len(thinkers)} methods={len(methods)}{err_marker}")

            results.append({
                "operation": "summarize",
                "route": route_key,
                "call_index": call_idx,
                "pub_id": pub["pub_id"],
                "year": pub.get("year"),
                "title": pub["title"][:160],
                "fulltext_chars": pub["fulltext_chars"],
                "cost_usd": res.get("cost_usd"),
                "cost_fallback_estimated": res.get("cost_fallback_estimated"),
                "tokens_in": res.get("tokens_in"),
                "tokens_out": res.get("tokens_out"),
                "cached_read": res.get("cached_read", 0),
                "latency_s": res.get("latency_s"),
                "finish_reason": res.get("finish_reason"),
                "error": res.get("error"),
                "summary_de": summary_de,
                "key_terms": key_terms,
                "named_thinkers": thinkers,
                "methods": methods,
                "cases_examples": cases,
            })
    return results


# ────────────────────────────────────────────────────────────────────
# Trends-Runner
# ────────────────────────────────────────────────────────────────────


# Route-spezifische max_tokens für Trends:
#   - opus  : 5000 (terminiert zuverlässig mit finish=stop)
#   - mimo  : 32000 (MiMo nutzt unvorhersagbar viel Reasoning-Budget;
#             User-Direktive: Cache macht das billig, also lieber großzügig
#             als abgeschnitten)
TRENDS_MAX_TOKENS_PER_ROUTE = {
    "opus": 5000,
    "mimo": 32000,
}


def run_trends(cluster_keys: list[str], pair: tuple[str, str]) -> list[dict]:
    store = Store()
    this_year = datetime.now().year
    start_year = this_year - 2

    prepared: list[tuple[str, dict, list, str, str]] = []
    for ckey in cluster_keys:
        meta = DISCOURSE_SPACES[ckey]
        journals = [j.short for j in journals_in_cluster(ckey)]
        arts = store.find_in_window(start_year=start_year, journals=journals)
        arts = [a for a in arts if a.title and (a.openalex_abstract or a.abstract)]
        arts = arts[:40]

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
        for i, sa in enumerate(arts, 1):
            parts.append("")
            parts.append(_format_article_for_llm(sa, i))
        user_content = "\n".join(parts)
        system_prompt = TRENDS_SYSTEM_PROMPT.format(
            cluster_name=meta["name"],
            cluster_description=meta["description"],
            window=window_label,
        )
        prepared.append((ckey, meta, arts, system_prompt, user_content))

    results: list[dict] = []
    for route_key in pair:
        route = ROUTES[route_key]
        print(f"\n[trends] === MODELL: {route.label} — {len(prepared)} Cluster ===")
        max_tok = TRENDS_MAX_TOKENS_PER_ROUTE.get(route_key, 5000)
        for call_idx, (ckey, meta, arts, system_prompt, user_content) in enumerate(prepared, 1):
            res = call_route(
                route=route,
                system_prompt=system_prompt,
                user_content=user_content,
                max_tokens=max_tok,
            )
            text = res.get("text") or ""
            # Artikel-IDs im Output zählen (Pattern „#1“, „#23“ etc.)
            mentioned_ids = sorted(set(int(m.group(1)) for m in re.finditer(r"#(\d+)", text) if 1 <= int(m.group(1)) <= len(arts)))

            err_marker = ""
            if res.get("error"):
                err_marker = f" ERROR={res['error'][:80]}"
            elif res.get("finish_reason") not in ("stop", "end_turn", None):
                err_marker = f" finish={res.get('finish_reason')}"

            print(f"[trends] {route_key:<8} #{call_idx}/{len(prepared)}  "
                  f"{ckey:<20}  "
                  f"cost=${res.get('cost_usd', 0):.4f}  "
                  f"tok={res.get('tokens_in', 0)}/{res.get('tokens_out', 0)}  "
                  f"out={len(text):,}chars  "
                  f"art_refs={len(mentioned_ids)}/{len(arts)}{err_marker}")

            results.append({
                "operation": "trends",
                "route": route_key,
                "call_index": call_idx,
                "cluster": ckey,
                "cluster_name": meta["name"],
                "articles_count": len(arts),
                "max_tokens_set": max_tok,
                "cost_usd": res.get("cost_usd"),
                "cost_fallback_estimated": res.get("cost_fallback_estimated"),
                "tokens_in": res.get("tokens_in"),
                "tokens_out": res.get("tokens_out"),
                "cached_read": res.get("cached_read", 0),
                "latency_s": res.get("latency_s"),
                "finish_reason": res.get("finish_reason"),
                "error": res.get("error"),
                "markdown": text,
                "output_chars": len(text),
                "mentioned_article_indices": mentioned_ids,
                "mentioned_article_count": len(mentioned_ids),
            })
    return results


# ────────────────────────────────────────────────────────────────────
# Konkordanz-Analyse
# ────────────────────────────────────────────────────────────────────


def _jaccard(a: list[str], b: list[str]) -> float:
    sa = {x.lower().strip() for x in a if x}
    sb = {x.lower().strip() for x in b if x}
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / max(len(sa | sb), 1)


def _term_overlap(a: str, b: str) -> float:
    """Jaccard-Term-Overlap (sehr grobe Kernthese-Ähnlichkeit)."""
    def tokens(s):
        s = s.lower()
        s = re.sub(r"[^a-z0-9äöüß\s]", " ", s)
        toks = [t for t in s.split() if len(t) > 3]
        return set(toks)
    ta, tb = tokens(a), tokens(b)
    if not ta and not tb:
        return 1.0
    return len(ta & tb) / max(len(ta | tb), 1)


def analyze_concordance(report: dict) -> dict:
    """Berechnet pro Operation harte Vergleichsmetriken."""
    analysis: dict[str, Any] = {}

    # ASSESSMENT
    asr = report.get("results", {}).get("assessment", [])
    if asr:
        by_article: dict[str, dict[str, dict]] = {}
        for r in asr:
            by_article.setdefault(r["article_id"], {})[r["route"]] = r
        baseline, alt = PAIRS_PER_OP["assessment"]
        verdicts_match = 0
        kernthese_overlaps = []
        per_article = []
        for aid, by_route in by_article.items():
            o = by_route.get(baseline)
            m = by_route.get(alt)
            if not o or not m:
                continue
            ov, mv = o.get("verdict"), m.get("verdict")
            match = (ov == mv) and ov is not None
            if match:
                verdicts_match += 1
            kt_overlap = _term_overlap(o.get("kernthese") or "", m.get("kernthese") or "")
            kernthese_overlaps.append(kt_overlap)
            per_article.append({
                "article_id": aid,
                "journal": o.get("journal"),
                "title": o.get("title"),
                "opus_verdict": ov,
                "alt_verdict": mv,
                "match": match,
                "kernthese_term_overlap": round(kt_overlap, 3),
                "opus_kernthese": (o.get("kernthese") or "")[:300],
                "alt_kernthese": (m.get("kernthese") or "")[:300],
            })
        n_pairs = len(per_article)
        analysis["assessment"] = {
            "n_pairs": n_pairs,
            "verdict_match_rate": round(verdicts_match / max(n_pairs, 1), 3),
            "verdict_matches": verdicts_match,
            "kernthese_overlap_avg": round(sum(kernthese_overlaps) / max(len(kernthese_overlaps), 1), 3),
            "kernthese_overlap_min": round(min(kernthese_overlaps) if kernthese_overlaps else 0, 3),
            "per_article": per_article,
        }

    # SUMMARIZE
    smr = report.get("results", {}).get("summarize", [])
    if smr:
        by_pub: dict[str, dict[str, dict]] = {}
        for r in smr:
            by_pub.setdefault(r["pub_id"], {})[r["route"]] = r
        baseline, alt = PAIRS_PER_OP["summarize"]
        per_pub = []
        for pid, by_route in by_pub.items():
            o = by_route.get(baseline)
            m = by_route.get(alt)
            if not o or not m:
                continue
            per_pub.append({
                "pub_id": pid,
                "title": o.get("title"),
                "key_terms_jaccard": round(_jaccard(o["key_terms"], m["key_terms"]), 3),
                "thinkers_jaccard": round(_jaccard(o["named_thinkers"], m["named_thinkers"]), 3),
                "methods_jaccard": round(_jaccard(o["methods"], m["methods"]), 3),
                "summary_overlap": round(_term_overlap(o["summary_de"], m["summary_de"]), 3),
                "opus_keys_n": len(o["key_terms"]),
                "alt_keys_n": len(m["key_terms"]),
                "opus_thinkers_n": len(o["named_thinkers"]),
                "alt_thinkers_n": len(m["named_thinkers"]),
            })
        n = len(per_pub)
        analysis["summarize"] = {
            "n_pairs": n,
            "key_terms_jaccard_avg": round(sum(p["key_terms_jaccard"] for p in per_pub) / max(n, 1), 3),
            "thinkers_jaccard_avg": round(sum(p["thinkers_jaccard"] for p in per_pub) / max(n, 1), 3),
            "methods_jaccard_avg":  round(sum(p["methods_jaccard"]  for p in per_pub) / max(n, 1), 3),
            "summary_overlap_avg":  round(sum(p["summary_overlap"]  for p in per_pub) / max(n, 1), 3),
            "per_pub": per_pub,
        }

    # TRENDS
    trr = report.get("results", {}).get("trends", [])
    if trr:
        by_cluster: dict[str, dict[str, dict]] = {}
        for r in trr:
            by_cluster.setdefault(r["cluster"], {})[r["route"]] = r
        baseline, alt = PAIRS_PER_OP["trends"]
        per_cluster = []
        for ckey, by_route in by_cluster.items():
            o = by_route.get(baseline)
            m = by_route.get(alt)
            if not o or not m:
                continue
            per_cluster.append({
                "cluster": ckey,
                "articles_count": o.get("articles_count"),
                "opus_output_chars": o.get("output_chars"),
                "alt_output_chars": m.get("output_chars"),
                "opus_art_refs": o.get("mentioned_article_count"),
                "alt_art_refs": m.get("mentioned_article_count"),
                "output_term_overlap": round(_term_overlap(o["markdown"], m["markdown"]), 3),
            })
        n = len(per_cluster)
        analysis["trends"] = {
            "n_pairs": n,
            "output_term_overlap_avg": round(sum(p["output_term_overlap"] for p in per_cluster) / max(n, 1), 3),
            "per_cluster": per_cluster,
        }

    return analysis


def aggregate_costs(report: dict) -> dict:
    """Pro Operation × Route: total_cost, avg_cost, cached_pct etc."""
    agg: dict[str, dict] = {}
    for op, items in report.get("results", {}).items():
        per_route: dict[str, dict] = {}
        for r in items:
            rk = r["route"]
            d = per_route.setdefault(rk, {
                "n": 0, "errors": 0, "cost": 0.0, "tokens_in": 0, "tokens_out": 0,
                "cached_read": 0, "latency_s": 0.0, "fallback_count": 0,
                "cold_cost": 0.0, "warm_cost": 0.0,  # split at call_index<=5 vs >5
                "cold_n": 0, "warm_n": 0,
            })
            d["n"] += 1
            if r.get("error") or r.get("finish_reason") == "error":
                d["errors"] += 1
                continue
            d["cost"] += r.get("cost_usd") or 0
            d["tokens_in"] += r.get("tokens_in") or 0
            d["tokens_out"] += r.get("tokens_out") or 0
            d["cached_read"] += r.get("cached_read") or 0
            d["latency_s"] += r.get("latency_s") or 0
            if r.get("cost_fallback_estimated"):
                d["fallback_count"] += 1
            # cold = calls 1-5 (Cache warming), warm = calls 6+
            ci = r.get("call_index", 1)
            if ci <= 5:
                d["cold_cost"] += r.get("cost_usd") or 0
                d["cold_n"] += 1
            else:
                d["warm_cost"] += r.get("cost_usd") or 0
                d["warm_n"] += 1
        agg[op] = per_route
    return agg


# ────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--op", choices=["assessment", "summarize", "trends", "all"], default="all")
    ap.add_argument("--out", default=None,
                    help="Output-JSON-Pfad (default: docs/cost_test_sarah_v2_<ts>.json)")
    args = ap.parse_args()

    out_path = Path(args.out) if args.out else (
        Path("docs") / f"cost_test_sarah_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fixture = load_fixture()
    report: dict[str, Any] = {
        "started_at": datetime.now().isoformat(),
        "fixture_path": str(FIXTURE_PATH),
        "pairs_per_op": {k: list(v) for k, v in PAIRS_PER_OP.items()},
        "fixture_summary": {
            "assessment_n": len(fixture["assessment_article_ids"]),
            "summarize_n": len(fixture["summarize_pub_ids"]),
            "trends_clusters": fixture["trends_clusters"],
        },
        "results": {},
    }

    ops = ["assessment", "summarize", "trends"] if args.op == "all" else [args.op]

    for op in ops:
        print(f"\n{'=' * 70}\n[main] Starte Operation: {op}\n{'=' * 70}")
        try:
            if op == "assessment":
                report["results"]["assessment"] = run_assessment(
                    fixture["assessment_article_ids"], PAIRS_PER_OP["assessment"]
                )
            elif op == "summarize":
                report["results"]["summarize"] = run_summarize(
                    fixture["summarize_pub_ids"], PAIRS_PER_OP["summarize"]
                )
            elif op == "trends":
                report["results"]["trends"] = run_trends(
                    fixture["trends_clusters"], PAIRS_PER_OP["trends"]
                )
        except Exception as e:
            print(f"[!] Operation {op} fehlgeschlagen: {e}")
            traceback.print_exc()
            report["results"][op] = {"_error": str(e), "_traceback": traceback.format_exc()}
        # Inkrementell speichern
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    # Konkordanz + Kostenaggregat
    report["analysis"] = {
        "costs": aggregate_costs(report),
        "concordance": analyze_concordance(report),
    }
    report["finished_at"] = datetime.now().isoformat()
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    # Konsolen-Summary
    print("\n" + "=" * 70 + "\nERGEBNIS")
    print("=" * 70)
    for op, per_route in report["analysis"]["costs"].items():
        print(f"\n[{op}]")
        for rk, d in per_route.items():
            avg = d["cost"] / max(d["n"] - d["errors"], 1)
            cache_pct = d["cached_read"] / max(d["tokens_in"], 1) * 100
            cold_avg = d["cold_cost"] / max(d["cold_n"], 1) if d["cold_n"] else 0
            warm_avg = d["warm_cost"] / max(d["warm_n"], 1) if d["warm_n"] else 0
            print(f"  {rk:<10}  n={d['n']:>2}  err={d['errors']}  total=${d['cost']:.4f}  avg=${avg:.4f}  "
                  f"cold(1-5)=${cold_avg:.4f}  warm(6+)=${warm_avg:.4f}  cache={cache_pct:.0f}%")
    conc = report["analysis"].get("concordance", {})
    if "assessment" in conc:
        c = conc["assessment"]
        print(f"\n[assessment-Konkordanz] verdict-match {c['verdict_matches']}/{c['n_pairs']} = "
              f"{c['verdict_match_rate']*100:.1f}%  kernthese-overlap avg={c['kernthese_overlap_avg']:.2f}")
    if "summarize" in conc:
        c = conc["summarize"]
        print(f"[summarize-Konkordanz] key_terms Jaccard avg={c['key_terms_jaccard_avg']:.2f}  "
              f"thinkers={c['thinkers_jaccard_avg']:.2f}  methods={c['methods_jaccard_avg']:.2f}  "
              f"summary-overlap={c['summary_overlap_avg']:.2f}")
    if "trends" in conc:
        c = conc["trends"]
        print(f"[trends-Konkordanz] output-term-overlap avg={c['output_term_overlap_avg']:.2f}")

    print(f"\nBericht: {out_path}")


if __name__ == "__main__":
    main()
