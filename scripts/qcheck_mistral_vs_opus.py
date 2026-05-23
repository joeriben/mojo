"""Q-Check: Mistral Large gegen Opus (Assessment) und MiMo (Trends).

Folgt der Struktur von `qcheck_mimo_vs_opus.py`, nutzt dieselbe fixierte
Stichprobe (`scripts/qcheck_assessment_ids.json`, 50 stratified articles) und
dieselben Trend-Cluster (digitale_kultur, medienpaed, erziehungswiss). Output
geht parallel in `docs/qcheck_mistral_*` ohne die MiMo-Resultate zu überschreiben.

Mistral-Konfig (verifiziert 2026-05-23):
  - Native API api.mistral.ai/v1 (DSGVO/EU)
  - mistral-large-latest, $0.50 / $1.50 pro Mtok (input/output)
  - Implicit Prefix-Caching server-side — KEIN `cache_control: ephemeral`
    (würde 422 auslösen). `make_messages()` baut das route-abhängig korrekt.
  - Tool-Use via OpenAI-Schema, `tool_choice="auto"`.

Ziel:
  - Assessment: Verdict-Match gegen Opus-Goldstandard, false-skip-Rate auf
    `lesenswert` (kritisch — MiMo hatte hier 22 %).
  - Trends: term-Jaccard und strukturelle Vergleichbarkeit gegen MiMo-Baseline
    aus docs/qcheck_trends.json. Frage: ist Mistral Large für billige
    Trend-Barometer-Runs viable?

Cost-Safety: $0.06/call cap nach 3 Calls — identisch zum MiMo-Script.
"""

from __future__ import annotations

import argparse
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
from journal_bot.settings import (
    CORPUS_JSON,
    DISCOURSE_SPACES,
    SUMMARIES_JSON,
    journals_in_cluster,
)
from journal_bot.store import Store
from journal_bot.trends import SYSTEM_PROMPT as TRENDS_SYSTEM_PROMPT, _format_article_for_llm

DOCS = Path("docs")
DOCS.mkdir(exist_ok=True)

ROUTE = ROUTES["mistral"]
MODEL_LABEL = ROUTE.label  # "Mistral Large (nativ EU)"

BUDGET_PER_CALL_LIMIT = 0.06  # USD; identisch zum MiMo-Script (CLAUDE.md-Style)


# ────────────────────────────────────────────────────────────────────
# Call-Helper (Mistral-spezifisch — implicit cache, kein cache_control)
# ────────────────────────────────────────────────────────────────────


def call_mistral(
    system_prompt: str,
    user_content: str,
    *,
    tools: list[dict] | None = None,
    forced_tool_name: str | None = None,
    max_tokens: int = 2500,
) -> dict[str, Any]:
    """Call Mistral Large via native API. tool_choice='auto'."""
    client = build_client(ROUTE.provider)
    messages = make_messages(system_prompt, user_content, ROUTE)

    params: dict[str, Any] = {
        "model": ROUTE.model,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if tools:
        params["tools"] = tools
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
            # 401/403/422 etc. — kein Retry-Sinn
            break

    if resp is None:
        return {
            "error": f"{type(last_err).__name__}: {str(last_err)[:600]}",
            "latency_s": time.time() - t0,
        }

    latency = time.time() - t0
    choice = resp.choices[0]
    msg = choice.message
    stats = extract_stats(resp.usage, ROUTE)

    out: dict[str, Any] = {
        "finish_reason": choice.finish_reason,
        "tokens_in": stats.tokens_in,
        "tokens_out": stats.tokens_out,
        "cached_read": stats.cached_read,
        "cost_usd": round(stats.cost_usd, 5),
        "cost_is_estimate": stats.fallback_cost,
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


def qcheck_assessment(
    ids_file: Path = Path("scripts/qcheck_assessment_ids.json"),
    *,
    limit: int | None = None,
) -> list[dict]:
    print(f"\n=== Q-CHECK ASSESSMENT (Mistral Large) {'[LIMIT '+str(limit)+']' if limit else ''} ===")
    ids = json.loads(ids_file.read_text())["ids"]
    if limit:
        ids = ids[:limit]
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

    # Idempotenz: Bestehende Ergebnisse weiterverwenden
    out_json = DOCS / "qcheck_mistral_assessment.json"
    existing: dict[str, dict] = {}
    if out_json.exists():
        try:
            prior = json.loads(out_json.read_text())
            for r in prior.get("results", []):
                if (r.get("mistral") or {}).get("verdict"):
                    existing[r["article_id"]] = r
            print(f"  (Resume: {len(existing)} Calls aus prior JSON übernommen)")
        except Exception as e:
            print(f"  (Konnte prior JSON nicht laden: {e})")

    results: list[dict] = []
    total_cost = 0.0
    cost_safety_hit = False
    new_calls_made = 0
    new_calls_cost = 0.0
    for i, row in enumerate(rows, 1):
        if row["id"] in existing:
            er = existing[row["id"]]
            results.append({**er, "i": i})
            total_cost += (er.get("mistral") or {}).get("cost_usd") or 0.0
            print(f"  #{i:>2}/{len(rows)} ⤴  skip (resume)  "
                  f"opus={er['opus'].get('verdict','?'):<11}  mistral={er['mistral'].get('verdict','?'):<11}")
            continue

        if cost_safety_hit:
            print(f"  #{i:>2}/{len(rows)} ⏭  skip (cost safety break)")
            continue

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

        res = call_mistral(
            system_prompt,
            user_content,
            tools=TOOLS_SUBMIT_ONLY,
            forced_tool_name="submit_digest_entry",
            max_tokens=2500,
        )

        # Falls Mistral den Tool-Call nicht macht — retry mit expliziter Bitte
        retried = False
        if not res.get("tool_args") and not res.get("error"):
            retried = True
            res2 = call_mistral(
                system_prompt,
                user_content + "\n\nWICHTIG: Antworte AUSSCHLIESSLICH durch Aufruf der submit_digest_entry-Funktion.",
                tools=TOOLS_SUBMIT_ONLY,
                forced_tool_name="submit_digest_entry",
                max_tokens=2500,
            )
            if res2.get("tool_args"):
                res = res2
                res["_retry"] = True

        mistral_args = res.get("tool_args") or {}
        opus_verdict = opus_entry.get("verdict") or row.get("agent_verdict")
        mistral_verdict = mistral_args.get("verdict")

        match = (opus_verdict == mistral_verdict)
        c = res.get("cost_usd") or 0.0
        total_cost += c
        if not res.get("error"):
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
            "mistral": {
                "verdict": mistral_verdict,
                "kernthese": mistral_args.get("kernthese", ""),
                "verdict_begruendung": mistral_args.get("verdict_begruendung", ""),
                "bezuege": mistral_args.get("bezuege", []),
                "bemerkenswert": mistral_args.get("bemerkenswert", []),
                "cost_usd": res.get("cost_usd"),
                "cost_is_estimate": res.get("cost_is_estimate"),
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
              f"opus={opus_verdict:<11}  mistral={str(mistral_verdict):<11}  "
              f"${res.get('cost_usd',0):.4f}  cache={res.get('cache_pct',0):.0f}%  "
              f"t={res.get('latency_s',0):.1f}s{retry_mark}{err_mark}")

        # Persistiere nach jedem Call (resume-safe)
        out_json.write_text(json.dumps(
            {"results": results, "ts": datetime.now().isoformat()},
            ensure_ascii=False, indent=2, default=str
        ))

    successful = [r for r in results if not (r.get("mistral") or {}).get("error")]
    matches = sum(1 for r in successful if r["verdict_match"])
    print(f"\n  Verdict-Match: {matches}/{len(successful)} = {matches/max(len(successful),1)*100:.1f}%")
    print(f"  Mistral total cost: ${total_cost:.4f}  "
          f"(Opus orig sum: ${sum(r['opus']['cost_usd'] or 0 for r in successful):.4f})")

    _render_assessment_md(results)
    return results


def _render_assessment_md(results: list[dict]) -> None:
    """Inline-Render statt separater Render-Script-Datei."""
    successful = [r for r in results if not (r.get("mistral") or {}).get("error")]
    matches_list = [r for r in successful if r["verdict_match"]]
    mismatches = [r for r in successful if not r["verdict_match"]]
    failed = [r for r in results if (r.get("mistral") or {}).get("error")]

    total_mistral_cost = sum((r["mistral"].get("cost_usd") or 0) for r in successful)
    total_opus_cost = sum((r["opus"].get("cost_usd") or 0) for r in successful)

    # Konfusionsmatrix
    matrix: dict[tuple[str, str], int] = {}
    for r in successful:
        ov = r["opus"]["verdict"] or "?"
        mv = r["mistral"]["verdict"] or "FAIL"
        matrix[(ov, mv)] = matrix.get((ov, mv), 0) + 1

    # Kritische Metrik: false-skip auf lesenswert
    lesenswert_total = sum(1 for r in successful if r["opus"]["verdict"] == "lesenswert")
    lesenswert_matched = sum(1 for r in successful
                             if r["opus"]["verdict"] == "lesenswert"
                             and r["mistral"]["verdict"] == "lesenswert")
    lesenswert_recall = (lesenswert_matched / lesenswert_total) if lesenswert_total else 0.0

    # Cache-Hit-Verhalten
    cache_pcts = [r["mistral"].get("cache_pct", 0) for r in successful if r["mistral"].get("tokens_in", 0) > 0]
    avg_cache = sum(cache_pcts) / max(len(cache_pcts), 1)

    md = [
        "# Q-Check Assessment — Mistral Large vs vorhandene Opus-Datensätze",
        "",
        f"**Datum:** {datetime.now().isoformat()}",
        f"**Stichprobe:** {len(results)} Artikel aus `scripts/qcheck_assessment_ids.json` (stratifiziert)",
        f"**Mistral-Konfig:** `{ROUTE.model}` nativ via api.mistral.ai (EU/DSGVO), `tool_choice='auto'`, implicit cache",
        "",
        "## TL;DR",
        "",
        f"- **Verdict-Match: {len(matches_list)}/{len(successful)} = {len(matches_list)/max(len(successful),1)*100:.1f} %**",
        f"- **Lesenswert-Recall: {lesenswert_matched}/{lesenswert_total} = {lesenswert_recall*100:.1f} %** _(kritisch — MiMo war hier bei 78 %)_",
        f"- **Avg Cache-Hit:** {avg_cache:.1f} % (implicit; rein server-side bei Mistral)",
        f"- **Kosten gesamt:** Mistral ${total_mistral_cost:.4f} · Opus orig ${total_opus_cost:.4f} · Faktor ~1/{(total_opus_cost/total_mistral_cost) if total_mistral_cost else 0:.1f}",
        f"- **Avg/Call Mistral:** ${total_mistral_cost/max(len(successful),1):.4f}",
        "",
        "## Verdict-Konfusionsmatrix",
        "",
    ]
    verdicts = sorted({k[0] for k in matrix} | {k[1] for k in matrix})
    if verdicts:
        md.append("| Opus → / Mistral ↓ | " + " | ".join(verdicts) + " |")
        md.append("|---|" + "---|" * len(verdicts))
        for mv in verdicts:
            row_str = f"| **{mv}** |"
            for ov in verdicts:
                row_str += f" {matrix.get((ov, mv), 0)} |"
            md.append(row_str)
        md.append("")

    if failed:
        md.append("## Failures")
        md.append("")
        md.append(f"_{len(failed)} Calls fehlgeschlagen:_")
        for r in failed[:5]:
            md.append(f"- `{r['article_id'][:12]}` ({r['journal']}): `{(r['mistral'].get('error') or '')[:200]}`")
        md.append("")

    md.append("## Mismatches (kritische Lektüre)")
    md.append("")
    for r in mismatches:
        md.append(f"### #{r['i']} `{r['journal']}` — {r['title'][:160]}")
        md.append(f"_article_id_: `{r['article_id']}`")
        md.append("")
        md.append(f"**Opus** — `{r['opus']['verdict']}`")
        md.append(f"  *Kernthese:* {(r['opus'].get('kernthese') or '')[:600]}")
        md.append("")
        md.append(f"**Mistral** — `{r['mistral']['verdict']}`")
        md.append(f"  *Kernthese:* {(r['mistral'].get('kernthese') or '')[:600]}")
        md.append("")
        md.append("---")
        md.append("")

    (DOCS / "qcheck_mistral_assessment.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  -> docs/qcheck_mistral_assessment.md")


# ────────────────────────────────────────────────────────────────────
# Trends-Q-Check (Mistral vs MiMo-Baseline)
# ────────────────────────────────────────────────────────────────────


def qcheck_trends(clusters: list[str] | None = None) -> list[dict]:
    print(f"\n=== Q-CHECK TRENDS (Mistral Large vs MiMo-Baseline) ===")
    if clusters is None:
        clusters = ["digitale_kultur", "medienpaed", "erziehungswiss"]
    store = Store()
    this_year = datetime.now().year
    start_year = this_year - 2

    # MiMo-Baselines aus docs/qcheck_trends.json laden (recyclen — kein neuer Call)
    mimo_by_cluster: dict[str, dict] = {}
    mimo_src = DOCS / "qcheck_trends.json"
    if mimo_src.exists():
        try:
            prior = json.loads(mimo_src.read_text())
            for r in prior.get("results", []):
                mimo_by_cluster[r["cluster"]] = r.get("mimo", {})
            print(f"  (MiMo-Baselines aus {mimo_src.name}: {len(mimo_by_cluster)} Cluster)")
        except Exception as e:
            print(f"  (Konnte MiMo-Baseline nicht laden: {e})")

    results: list[dict] = []
    total_mistral = 0.0
    total_mimo_recycled = sum(r.get("cost_usd", 0) for r in mimo_by_cluster.values())

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

        # MiMo recyclen
        mimo_rec = mimo_by_cluster.get(ckey, {})
        mimo_text = mimo_rec.get("text", "") or ""

        # Mistral frisch fahren
        client = build_client(ROUTE.provider)
        msgs = make_messages(system_prompt, user_content, ROUTE)
        t0 = time.time()
        try:
            resp = client.chat.completions.create(
                model=ROUTE.model, max_tokens=16000, messages=msgs,
            )
            err = None
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:400]}"
            resp = None

        if resp is None:
            print(f"  #{i}/{len(clusters)} {ckey}: ERR={err}")
            results.append({
                "cluster": ckey,
                "cluster_name": meta["name"],
                "articles_count": len(arts),
                "mimo": mimo_rec,
                "mistral": {"error": err, "latency_s": round(time.time() - t0, 2)},
            })
            continue

        stats = extract_stats(resp.usage, ROUTE)
        mistral_text = resp.choices[0].message.content or ""
        latency = round(time.time() - t0, 2)
        total_mistral += stats.cost_usd

        results.append({
            "cluster": ckey,
            "cluster_name": meta["name"],
            "articles_count": len(arts),
            "mimo": mimo_rec,
            "mistral": {
                "cost_usd": round(stats.cost_usd, 5),
                "cost_is_estimate": stats.fallback_cost,
                "tokens_in": stats.tokens_in,
                "tokens_out": stats.tokens_out,
                "cached_read": stats.cached_read,
                "cache_pct": round(stats.cached_read / max(stats.tokens_in, 1) * 100, 1),
                "latency_s": latency,
                "output_chars": len(mistral_text),
                "text": mistral_text,
            },
        })
        mimo_cost = mimo_rec.get("cost_usd", 0)
        mimo_chars = len(mimo_rec.get("text", "") or "")
        print(f"  #{i}/{len(clusters)} {ckey}: "
              f"mimo(rec) ${mimo_cost:.4f}/{mimo_chars:,}c   "
              f"mistral ${stats.cost_usd:.4f}/{len(mistral_text):,}c  "
              f"cache={results[-1]['mistral']['cache_pct']}%  t={latency:.1f}s")

        # Persistiere nach jedem Cluster
        (DOCS / "qcheck_mistral_trends.json").write_text(json.dumps(
            {"results": results, "ts": datetime.now().isoformat()},
            ensure_ascii=False, indent=2, default=str
        ))

    print(f"\n  Mistral total: ${total_mistral:.4f}  (MiMo recycled: ${total_mimo_recycled:.4f})")
    _render_trends_md(results)
    return results


def _jaccard_terms(text_a: str, text_b: str, *, min_len: int = 4) -> float:
    """Jaccard-Index über die Lowercased-Wörter (≥ min_len Zeichen)."""
    import re
    tok = lambda t: set(w for w in re.findall(r"[a-zäöüß][a-zäöüß\-]+", t.lower()) if len(w) >= min_len)
    a, b = tok(text_a), tok(text_b)
    if not a and not b:
        return 0.0
    return len(a & b) / max(len(a | b), 1)


def _render_trends_md(results: list[dict]) -> None:
    md = [
        "# Q-Check Trends — Mistral Large vs MiMo-Baseline",
        "",
        f"**Datum:** {datetime.now().isoformat()}",
        f"**Stichprobe:** {len(results)} Cluster × bis zu 40 Artikel",
        f"**Mistral-Konfig:** `{ROUTE.model}` nativ via api.mistral.ai (EU/DSGVO), max_tokens=16000",
        "",
        "## Übersicht",
        "",
        "| Cluster | Artikel | Mistral $ | Mistral chars | Mistral cache | MiMo $ | MiMo chars | Jaccard |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    total_mistral_cost = 0.0
    total_mimo_cost = 0.0
    jaccards = []
    for r in results:
        mi = r.get("mistral") or {}
        mo = r.get("mimo") or {}
        if mi.get("error"):
            md.append(f"| {r['cluster']} | {r['articles_count']} | ERR | - | - | "
                      f"${mo.get('cost_usd',0):.4f} | {len(mo.get('text','') or ''):,} | - |")
            continue
        j = _jaccard_terms(mi.get("text", "") or "", mo.get("text", "") or "")
        jaccards.append(j)
        total_mistral_cost += mi.get("cost_usd", 0)
        total_mimo_cost += mo.get("cost_usd", 0)
        md.append(
            f"| {r['cluster']} | {r['articles_count']} | "
            f"${mi.get('cost_usd',0):.4f} | {mi.get('output_chars',0):,} | "
            f"{mi.get('cache_pct',0):.0f}% | "
            f"${mo.get('cost_usd',0):.4f} | {len(mo.get('text','') or ''):,} | "
            f"{j:.2f} |"
        )

    md.extend([
        "",
        f"**Summen:** Mistral ${total_mistral_cost:.4f}  ·  MiMo (recycled) ${total_mimo_cost:.4f}  "
        f"·  Faktor ~1/{(total_mimo_cost/total_mistral_cost) if total_mistral_cost else 0:.2f}",
        f"**Avg term-Jaccard:** {sum(jaccards)/max(len(jaccards),1):.3f}",
        "",
        "## Output-Vergleich (volle Markdown-Texte)",
        "",
    ])

    for r in results:
        mi = r.get("mistral") or {}
        mo = r.get("mimo") or {}
        md.append(f"### Cluster: `{r['cluster']}` — {r.get('cluster_name','?')}")
        md.append("")
        md.append(f"_Artikel:_ {r['articles_count']}  ·  _Jaccard:_ {_jaccard_terms(mi.get('text','') or '', mo.get('text','') or ''):.2f}")
        md.append("")
        md.append(f"#### Mistral Large (${mi.get('cost_usd',0):.4f}, {mi.get('output_chars',0):,}c, "
                  f"cache={mi.get('cache_pct',0):.0f}%, {mi.get('latency_s',0):.1f}s)")
        md.append("")
        md.append(mi.get("text", "") or "_(kein Output)_")
        md.append("")
        md.append(f"#### MiMo (${mo.get('cost_usd',0):.4f}, {len(mo.get('text','') or ''):,}c, recycled)")
        md.append("")
        md.append(mo.get("text", "") or "_(kein Baseline-Text)_")
        md.append("")
        md.append("---")
        md.append("")

    (DOCS / "qcheck_mistral_trends.md").write_text("\n".join(md), encoding="utf-8")
    print(f"  -> docs/qcheck_mistral_trends.md")


# ────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assess", action="store_true", help="Run assessment Q-Check")
    ap.add_argument("--trends", action="store_true", help="Run trends Q-Check")
    ap.add_argument("--all", action="store_true", help="Run both")
    ap.add_argument("--limit", type=int, default=None, help="Assessment: limit articles (für Single-Call-Verifikation)")
    args = ap.parse_args()

    if not (args.assess or args.trends or args.all):
        ap.print_help()
        sys.exit(1)

    if args.all or args.assess:
        qcheck_assessment(limit=args.limit)
    if args.all or args.trends:
        qcheck_trends()


if __name__ == "__main__":
    main()
