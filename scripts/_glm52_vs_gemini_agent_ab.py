"""A/B-Test Phase-2-Agent-Lektüre: z-ai/glm-5.2 vs. google/gemini-3.5-flash.

Auftrag Benjamin Jörissen, 2026-07-10. Testet AUSSCHLIESSLICH die Agent-Stufe
(assess_then_verify / run_agent — Verdikt-Empfehlung), NICHT das Batch-Screening
(MODEL_SCREEN in journal_bot/agent.py bleibt unangetastet, wird hier nie importiert
noch aufgerufen).

Architektur:
  - `articles` Tabelle in articles.db wird NUR gelesen (read-only sqlite3-Connection,
    mode=ro). Es wird an keiner Stelle store.update_agent_result() oder eine sonstige
    schreibende Store-Methode aufgerufen — agent.run_agent()/assess_then_verify()
    schreiben selbst nie in `articles` (verifiziert durch Lesen von journal_bot/agent.py:
    keine store-Imports).
  - Kosten-Buchführung läuft normal über journal_bot.llm_log.record_llm_call() (Choke-
    Point, wird von run_agent() intern aufgerufen) — landet in der llm_calls-Tabelle
    in articles.db, NICHT in der articles-Tabelle. Das ist gewollt (Kosten-Ledger).
  - Der "tools"-Modus repliziert agent.assess_then_verify() eins zu eins (Phase 1:
    assessment ohne Tools, 1 Iteration; Phase 2: verification MIT read_publication,
    nur falls candidate_reads). Repliziert statt importiert, damit ein Absturz in
    Phase 2 nicht das bereits erfolgreiche Phase-1-Ergebnis verschluckt — inhaltlich
    IDENTISCHE Aufrufe (gleiche Funktionen, gleiche Argumente, gleiches Prompt/Tools),
    nur mit eigener try/except-Grenze zwischen den Phasen. Der "no_tools"-Modus ist
    Phase 1 pur (run_agent mit allow_read=False, max_iterations=1) — das historische
    "B-Tier ohne Tools" aus DEVLOG.md.
  - Ergebnisse pro (model, mode) gehen in ein eigenes Shard-JSON (unabhängige
    Prozesse können damit ohne Race-Condition parallel laufen). `--merge` fasst alle
    Shards in scripts/out/glm52_vs_gemini_ab_2026-07-10.json zusammen und druckt die
    Metriken.

CLI:
  python scripts/_glm52_vs_gemini_agent_ab.py --model glm --mode tools --limit 3
  python scripts/_glm52_vs_gemini_agent_ab.py --model glm --mode tools
  python scripts/_glm52_vs_gemini_agent_ab.py --model gemini --mode tools
  python scripts/_glm52_vs_gemini_agent_ab.py --model glm --mode no_tools
  python scripts/_glm52_vs_gemini_agent_ab.py --model gemini --mode no_tools
  python scripts/_glm52_vs_gemini_agent_ab.py --merge
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from journal_bot import agent as agent_mod  # noqa: E402
from journal_bot.settings import CORPUS_JSON, SUMMARIES_JSON  # noqa: E402

ARTICLES_DB = PROJECT_ROOT / "articles.db"
OUT_DIR = PROJECT_ROOT / "scripts" / "out"
FINAL_JSON = OUT_DIR / "glm52_vs_gemini_ab_2026-07-10.json"

MODELS: dict[str, str] = {
    "glm": "z-ai/glm-5.2",
    "gemini": "google/gemini-3.5-flash",  # amtierend, MODEL_AGENT aus profile.json
}

# Kosten-Circuit-Breaker (Auftrag §"MoJo-Kostenkultur")
MAX_COST_PER_ARTICLE_AFTER_3 = 0.15
MAX_TOTAL_COST_USD = 5.00
HARD_SINGLE_ARTICLE_CAP_USD = 1.00  # Notbremse falls ein Lauf entgleist

# ---------------------------------------------------------------- Stichprobe --
# Fest codierte Artikel-ID-Liste (Auftrag: "reproduzierbar, mit fixer
# Artikel-ID-Liste im Skript"). Stratifiziert aus articles.db (user_verdict),
# über 12 Journals verteilt, überwiegend abstract-reich (>=200 Zeichen in
# abstract ODER openalex_abstract), 2 bewusst abstract-arme Fälle markiert.
SAMPLE: list[dict] = [
    # --- lesenswert (6) ---
    {"id": "eaab8fbec10635679dd7e8d38320dff3", "user_verdict": "lesenswert", "journal": "BJET", "abstract_poor": False},
    {"id": "de4ac5cbc17b7e9f498c2a0efd47bb40", "user_verdict": "lesenswert", "journal": "AIandSoc", "abstract_poor": False},
    {"id": "283be2524522d8febff069c11f2fc3d3", "user_verdict": "lesenswert", "journal": "MedienPaed", "abstract_poor": False},
    {"id": "59b41fadc626dac8d50c95250ab72b47", "user_verdict": "lesenswert", "journal": "ZfE", "abstract_poor": False},
    {"id": "e8a2c291f8a7e54f2b3797c5ab2bebf2", "user_verdict": "lesenswert", "journal": "BDS", "abstract_poor": False},
    {"id": "910d8402db4d5cde8691d36bdc87c08c", "user_verdict": "lesenswert", "journal": "CompCult", "abstract_poor": False},
    # --- pflichtlektuere (1 — das einzige Vorkommen in der gesamten DB) ---
    {"id": "5600ea9e78f4119c6e3c297d7cac22d3", "user_verdict": "pflichtlektuere", "journal": "MedienPaed", "abstract_poor": False},
    # --- scannen (6, davon 1 abstract-arm) ---
    {"id": "af6f9705f1c19ad76d563fa1e137b28b", "user_verdict": "scannen", "journal": "AIandSoc", "abstract_poor": False},
    {"id": "721e8ae04e772623006908ddbaf2f808", "user_verdict": "scannen", "journal": "BDS", "abstract_poor": False},
    {"id": "a61faadb88daa6af4a8eb1d5e7cd1bc4", "user_verdict": "scannen", "journal": "REPCS", "abstract_poor": False},
    {"id": "598d79c944193dab810dea751015fc88", "user_verdict": "scannen", "journal": "EthicsEd", "abstract_poor": False},
    {"id": "ac3bc611f5e0f4be6575f885001d33e2", "user_verdict": "scannen", "journal": "JRTE", "abstract_poor": False},
    {"id": "74f223f51fced5138d20b7ba94fc5504", "user_verdict": "scannen", "journal": "MedienPaed", "abstract_poor": True},
    # --- ignorieren (7, davon 1 abstract-arm) ---
    {"id": "b756f0c8e6190877f982fde045878a90", "user_verdict": "ignorieren", "journal": "AIandSoc", "abstract_poor": False},
    {"id": "b56e34a4cf6a1be4257ea32e9c97fa7f", "user_verdict": "ignorieren", "journal": "BJET", "abstract_poor": False},
    {"id": "9c28670eeb0d8171190dcce10ec76a51", "user_verdict": "ignorieren", "journal": "Discourse", "abstract_poor": False},
    {"id": "10e15383607724179c30f37cca278760", "user_verdict": "ignorieren", "journal": "EERJ", "abstract_poor": False},
    {"id": "285f36c132b2761190d95a0366b45320", "user_verdict": "ignorieren", "journal": "PDSE", "abstract_poor": False},
    {"id": "45972f0bbd137f84ec1b7aac1f68dcc1", "user_verdict": "ignorieren", "journal": "ZfE", "abstract_poor": False},
    {"id": "167708764b14244eacea2f87b91c7abd", "user_verdict": "ignorieren", "journal": "AIandSoc", "abstract_poor": True},
]
SAMPLE_IDS = [s["id"] for s in SAMPLE]

KEEP_VERDICTS = {"lesenswert", "pflichtlektuere"}


# ------------------------------------------------------------------- DB read --


def load_rows(ids: list[str]) -> dict[str, dict]:
    """Read-only fetch aus articles.db. Öffnet mode=ro — ein UPDATE/INSERT/DELETE
    würde von SQLite selbst mit 'attempt to write a readonly database' abgelehnt."""
    uri = f"file:{ARTICLES_DB}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    rows: dict[str, dict] = {}
    placeholders = ",".join("?" for _ in ids)
    cur = conn.execute(
        f"SELECT id, journal_short, journal_full, title, authors_json, abstract, "
        f"openalex_abstract, openalex_concepts, openalex_topics, crossref_refs, "
        f"doi, url, year, enrichment_status, user_verdict, agent_verdict "
        f"FROM articles WHERE id IN ({placeholders})",
        ids,
    )
    for r in cur.fetchall():
        rows[r["id"]] = dict(r)
    conn.close()
    return rows


def article_dict_from_row(row: dict) -> dict:
    """Identisch zu digest._article_dict_from_stored — nur auf dem rohen DB-Dict
    statt auf StoredArticle."""
    return {
        "title": row["title"],
        "authors": json.loads(row["authors_json"] or "[]"),
        "abstract": row["abstract"] or "",
        "doi": row["doi"] or "",
        "url": row["url"] or "",
        "journal": row["journal_full"] or row["journal_short"],
        "enrichment": {
            "openalex": {
                "abstract": row["openalex_abstract"],
                "concepts": json.loads(row["openalex_concepts"] or "[]"),
                "topics": json.loads(row["openalex_topics"] or "[]"),
            } if row["openalex_abstract"] or row["openalex_concepts"] else None,
            "references_crossref": json.loads(row["crossref_refs"] or "[]"),
        } if row["enrichment_status"] == "ok" else None,
    }


# --------------------------------------------------------------- Agent-Calls --


def _run_agent_captured(**kwargs) -> tuple[dict, str, float]:
    buf = io.StringIO()
    t0 = time.time()
    with contextlib.redirect_stdout(buf):
        result = agent_mod.run_agent(**kwargs)
    latency = time.time() - t0
    return result, buf.getvalue(), latency


def call_no_tools(article: dict, model: str, article_id: str) -> dict:
    """Phase-1-pur — historisches 'B-Tier ohne Tools' (DEVLOG.md): allow_read=False,
    max_iterations=1, ASSESSMENT_OUTRO. Identischer Aufruf wie Phase 1 von
    assess_then_verify()."""
    rec: dict = {"mode": "no_tools", "phase2_triggered": False}
    t0 = time.time()
    try:
        result, stdout, _ = _run_agent_captured(
            new_article=article,
            model=model,
            max_iterations=1,
            verbose=True,
            allow_read=False,
            system_outro=agent_mod.ASSESSMENT_OUTRO,
            log_endpoint="qcheck_glm_vs_gemini_no_tools",
            article_id=article_id,
        )
        rec.update(_extract_common(result))
        rec["stdout"] = stdout
    except Exception as exc:  # Protokollfehler / API-Fehler sichtbar machen, nicht schlucken
        rec["exception"] = f"{type(exc).__name__}: {str(exc)[:800]}"
        rec["entry"] = None
    rec["latency_s"] = round(time.time() - t0, 2)
    return rec


def call_tools(article: dict, model: str, article_id: str) -> dict:
    """Repliziert agent.assess_then_verify() 1:1 (gleiche Funktionsaufrufe, gleiche
    Argumente), aber mit eigener try/except-Grenze zwischen Phase 1 und Phase 2 —
    ein Absturz in Phase 2 darf das erfolgreiche Phase-1-Ergebnis nicht verschlucken.
    Das ändert NICHTS an dem, was an das Modell geschickt wird."""
    rec: dict = {"mode": "tools"}
    t0 = time.time()
    try:
        assessment, stdout1, lat1 = _run_agent_captured(
            new_article=article,
            model=model,
            max_iterations=1,
            verbose=True,
            allow_read=False,
            system_outro=agent_mod.ASSESSMENT_OUTRO,
            log_endpoint="assess",
            article_id=article_id,
        )
    except Exception as exc:
        rec["exception"] = f"Phase1 {type(exc).__name__}: {str(exc)[:800]}"
        rec["entry"] = None
        rec["phase2_triggered"] = False
        rec["latency_s"] = round(time.time() - t0, 2)
        return rec

    entry = assessment.get("entry") or {}
    candidates = entry.get("candidate_reads") or []
    rec["phase1_stdout"] = stdout1
    rec["phase1_verdict"] = entry.get("verdict")
    rec["phase1_latency_s"] = round(lat1, 2)

    if not candidates:
        entry.pop("candidate_reads", None)
        if "bezuege" not in entry:
            entry["bezuege"] = []
        rec.update(_extract_common(assessment))
        rec["phase2_triggered"] = False
        rec["latency_s"] = round(time.time() - t0, 2)
        return rec

    rec["phase2_triggered"] = True
    max_iter_verify = min(len(candidates) * 2 + 2, 10)
    try:
        verification, stdout2, lat2 = _run_agent_captured(
            new_article=article,
            model=model,
            max_iterations=max_iter_verify,
            verbose=True,
            allow_read=True,
            extra_user_content=agent_mod._format_verification_context(entry, candidates),
            log_endpoint="verify",
            article_id=article_id,
        )
    except Exception as exc:
        # Phase 2 gescheitert — Phase-1-Ergebnis bleibt als Befund erhalten,
        # aber der GESAMTLAUF gilt als gescheitert (kein finaler Digest-Eintrag,
        # exakt wie es dem User in der Praxis passieren würde).
        rec["exception"] = f"Phase2 {type(exc).__name__}: {str(exc)[:800]}"
        rec["entry"] = None
        rec["assessment_entry"] = entry
        rec["tokens_in"] = assessment.get("tokens_in", 0)
        rec["tokens_out"] = assessment.get("tokens_out", 0)
        rec["tokens_cached_read"] = assessment.get("tokens_cached_read", 0)
        rec["tokens_cache_write"] = assessment.get("tokens_cache_write", 0)
        rec["cost_usd"] = assessment.get("est_cost_usd", 0.0)
        rec["iterations"] = assessment.get("iterations", 0)
        rec["tool_calls"] = assessment.get("tool_calls", [])
        rec["latency_s"] = round(time.time() - t0, 2)
        return rec

    for key in ("tokens_in", "tokens_out", "tokens_cached_read", "tokens_cache_write", "est_cost_usd"):
        verification[key] = verification.get(key, 0) + assessment.get(key, 0)
    verification["iterations"] = assessment.get("iterations", 0) + verification.get("iterations", 0)
    verification["tool_calls"] = assessment.get("tool_calls", []) + verification.get("tool_calls", [])
    verification["assessment"] = entry

    if verification.get("entry") is None and entry:
        fallback = dict(entry)
        fallback.pop("candidate_reads", None)
        fallback["verdict_begruendung"] = (
            fallback.get("verdict_begruendung", "")
            + " (Verifikation ohne Ergebnis abgebrochen, Assessment-Verdict übernommen)"
        )
        verification["entry"] = fallback
    else:
        final = verification.get("entry") or {}
        final.pop("candidate_reads", None)

    rec.update(_extract_common(verification))
    rec["phase2_stdout"] = stdout2
    rec["latency_s"] = round(time.time() - t0, 2)
    return rec


def _extract_common(result: dict) -> dict:
    entry = result.get("entry")
    tool_calls = result.get("tool_calls") or []
    return {
        "entry": entry,
        "agent_verdict": (entry or {}).get("verdict"),
        "iterations": result.get("iterations", 0),
        "tool_calls": tool_calls,
        "read_publication_count": sum(1 for t in tool_calls if t.get("tool") == "read_publication"),
        "submit_logged": any(t.get("tool") == "submit_digest_entry" for t in tool_calls),
        "tokens_in": result.get("tokens_in", 0),
        "tokens_out": result.get("tokens_out", 0),
        "tokens_cached_read": result.get("tokens_cached_read", 0),
        "tokens_cache_write": result.get("tokens_cache_write", 0),
        "cost_usd": result.get("est_cost_usd", 0.0),
    }


# ---------------------------------------------------------------- Shard I/O --


def shard_path(model_key: str, mode: str) -> Path:
    return OUT_DIR / f"_shard_{model_key}_{mode}.json"


def load_shard(model_key: str, mode: str) -> dict:
    p = shard_path(model_key, mode)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def save_shard(model_key: str, mode: str, data: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p = shard_path(model_key, mode)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(p)


def total_cost_all_shards() -> float:
    total = 0.0
    for model_key in MODELS:
        for mode in ("tools", "no_tools"):
            shard = load_shard(model_key, mode)
            for rec in shard.values():
                total += float(rec.get("cost_usd") or 0.0)
    return total


# -------------------------------------------------------------------- Runner --


def run(model_key: str, mode: str, limit: int | None, force: bool) -> None:
    model_id = MODELS[model_key]
    rows = load_rows(SAMPLE_IDS)
    shard = load_shard(model_key, mode)

    todo = [s for s in SAMPLE if force or s["id"] not in shard]
    if limit is not None:
        todo = todo[:limit]

    if not todo:
        print(f"[ab] {model_key}/{mode}: nichts zu tun (bereits {len(shard)}/{len(SAMPLE)} erledigt).")
        return

    print(f"[ab] {model_key} ({model_id}) / mode={mode}: {len(todo)} Artikel geplant "
          f"(bereits erledigt: {len(shard)}/{len(SAMPLE)})")

    done_this_run = 0
    for spec in todo:
        total_so_far = total_cost_all_shards()
        if total_so_far >= MAX_TOTAL_COST_USD:
            print(f"[ab] ABBRUCH: Gesamtbudget ${MAX_TOTAL_COST_USD:.2f} erreicht "
                  f"(${total_so_far:.3f}). Stoppe vor {spec['id']}.")
            break

        aid = spec["id"]
        row = rows.get(aid)
        if row is None:
            print(f"[ab] {aid}: NICHT in articles.db gefunden — skip.")
            continue

        article = article_dict_from_row(row)
        print(f"\n[ab] --- {model_key}/{mode} · {spec['journal']} · user_verdict={spec['user_verdict']} "
              f"· {aid[:10]} · {article['title'][:60]}")

        started_at = datetime.now(timezone.utc).isoformat()
        if mode == "tools":
            rec = call_tools(article, model_id, aid)
        else:
            rec = call_no_tools(article, model_id, aid)
        rec["finished_at"] = datetime.now(timezone.utc).isoformat()
        rec["started_at"] = started_at
        rec["model_key"] = model_key
        rec["model_id"] = model_id
        rec["article_id"] = aid
        rec["journal_short"] = spec["journal"]
        rec["user_verdict"] = spec["user_verdict"]
        rec["abstract_poor"] = spec["abstract_poor"]

        cost = float(rec.get("cost_usd") or 0.0)
        exc = rec.get("exception")
        verdict = rec.get("agent_verdict")
        print(f"[ab] ==> verdict={verdict!r}  cost=${cost:.4f}  latency={rec.get('latency_s')}s "
              f"iters={rec.get('iterations')}"
              + (f"  EXCEPTION: {exc}" if exc else ""))

        if cost > HARD_SINGLE_ARTICLE_CAP_USD:
            print(f"[ab] ⚠ HARD-CAP: Einzelartikel kostete ${cost:.3f} > "
                  f"${HARD_SINGLE_ARTICLE_CAP_USD:.2f}. Notiere, aber fahre NICHT automatisch fort — "
                  f"bitte manuell prüfen.")
            shard[aid] = rec
            save_shard(model_key, mode, shard)
            print("[ab] ABBRUCH nach Hard-Cap-Verletzung.")
            break

        shard[aid] = rec
        save_shard(model_key, mode, shard)
        done_this_run += 1

        if done_this_run == 3:
            costs = [float(v.get("cost_usd") or 0.0) for v in shard.values()]
            avg = mean(costs) if costs else 0.0
            print(f"\n[ab] === Kosten-Checkpoint nach 3 Artikeln ({model_key}/{mode}): "
                  f"Ø ${avg:.4f}/Artikel ===")
            if avg > MAX_COST_PER_ARTICLE_AFTER_3:
                print(f"[ab] ABBRUCH: Ø-Kosten ${avg:.4f} > Schwelle ${MAX_COST_PER_ARTICLE_AFTER_3:.2f}.")
                break
            n_errors = sum(1 for v in shard.values() if v.get("exception") or v.get("entry") is None)
            print(f"[ab] Protokoll-Status: {n_errors}/{len(shard)} ohne verwertbares Verdikt "
                  f"(Exception oder entry=None). Fahre fort, falls das Budget hält.")

    total_so_far = total_cost_all_shards()
    print(f"\n[ab] {model_key}/{mode}: Lauf beendet. Shard: {len(shard)}/{len(SAMPLE)} erledigt. "
          f"Gesamtkosten aller Shards bisher: ${total_so_far:.4f}")


# --------------------------------------------------------------------- Merge --


def merge_and_report() -> None:
    combined: dict = {"generated_at": datetime.now(timezone.utc).isoformat(), "sample": SAMPLE, "records": []}
    for model_key in MODELS:
        for mode in ("tools", "no_tools"):
            shard = load_shard(model_key, mode)
            combined["records"].extend(shard.values())

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_JSON.write_text(json.dumps(combined, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"[ab] Merged {len(combined['records'])} Records -> {FINAL_JSON}")

    print_metrics(combined["records"])


def print_metrics(records: list[dict]) -> None:
    for model_key in MODELS:
        for mode in ("tools", "no_tools"):
            group = [r for r in records if r["model_key"] == model_key and r["mode"] == mode]
            if not group:
                continue
            print(f"\n=== {model_key} / {mode} (n={len(group)}) ===")

            n_exc = sum(1 for r in group if r.get("exception"))
            n_no_entry = sum(1 for r in group if r.get("entry") is None)
            print(f"  Exceptions: {n_exc}  |  entry=None (kein Verdikt): {n_no_entry}")

            exact = [r for r in group if r.get("agent_verdict") and r.get("user_verdict")]
            n_match = sum(1 for r in exact if r["agent_verdict"] == r["user_verdict"])
            print(f"  Exact-4-Klassen-Agreement: {n_match}/{len(exact)}"
                  + (f" ({n_match/len(exact):.0%})" if exact else ""))

            def _keep(v: str) -> bool:
                return v in KEEP_VERDICTS
            n_bin_match = sum(1 for r in exact if _keep(r["agent_verdict"]) == _keep(r["user_verdict"]))
            print(f"  Binär keep/rest-Agreement: {n_bin_match}/{len(exact)}"
                  + (f" ({n_bin_match/len(exact):.0%})" if exact else ""))

            les = [r for r in group if r.get("user_verdict") in ("lesenswert", "pflichtlektuere")]
            les_recall = sum(1 for r in les if _keep(r.get("agent_verdict") or ""))
            print(f"  LES/Pflicht-Recall: {les_recall}/{len(les)}")

            costs = [float(r.get("cost_usd") or 0.0) for r in group]
            lat = [float(r.get("latency_s") or 0.0) for r in group]
            iters = [r.get("iterations") or 0 for r in group]
            tin = [r.get("tokens_in") or 0 for r in group]
            tout = [r.get("tokens_out") or 0 for r in group]
            tcache = [r.get("tokens_cached_read") or 0 for r in group]
            print(f"  Kosten: Σ${sum(costs):.4f}  Ø${mean(costs):.4f}  median${median(costs):.4f}")
            print(f"  Latenz: Ø{mean(lat):.1f}s  median{median(lat):.1f}s")
            print(f"  Iterationen: Ø{mean(iters):.1f}")
            print(f"  Tokens: in Ø{mean(tin):.0f}  out Ø{mean(tout):.0f}  cached Ø{mean(tcache):.0f}")


# ---------------------------------------------------------------------- CLI --


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", choices=list(MODELS.keys()))
    ap.add_argument("--mode", choices=["tools", "no_tools"])
    ap.add_argument("--limit", type=int, default=None, help="Nur die ersten N offenen Artikel.")
    ap.add_argument("--force", action="store_true", help="Bereits erledigte Artikel erneut laufen lassen.")
    ap.add_argument("--merge", action="store_true", help="Shards zusammenführen + Metriken drucken.")
    args = ap.parse_args()

    if args.merge:
        merge_and_report()
        return

    if not args.model or not args.mode:
        ap.error("--model und --mode erforderlich (oder --merge).")

    run(args.model, args.mode, args.limit, args.force)


if __name__ == "__main__":
    main()
