"""Helpers for historical year/journal scans in the web app."""

from __future__ import annotations

import re
from statistics import mean
from typing import Any

import httpx

from journal_bot import fetch
from journal_bot.settings import JOURNALS, JournalConfig
from journal_bot.store import Store

OPENALEX_MAILTO = "mojo@localhost"


def get_journal_config(short: str) -> JournalConfig | None:
    return next((journal for journal in JOURNALS if journal.short == short), None)


def _openalex_source_ref(journal: JournalConfig) -> str:
    if journal.issn:
        return f"issn:{journal.issn}"

    raw = (journal.url or "").strip()
    if raw.startswith("issn:"):
        return raw
    if raw.startswith("openalex:"):
        source_id = raw[len("openalex:"):].strip()
        if source_id.startswith("https://openalex.org/"):
            source_id = source_id.rsplit("/", 1)[-1]
        return source_id

    issn_match = re.search(r"(\d{4}-\d{3}[\dXx])", raw)
    if issn_match:
        return f"issn:{issn_match.group(1)}"

    source_match = re.search(r"(S\d{6,})", raw)
    if source_match:
        return source_match.group(1)

    return ""


def _openalex_available_years(journal: JournalConfig) -> list[int]:
    source_ref = _openalex_source_ref(journal)
    if not source_ref:
        return []

    url = f"https://api.openalex.org/sources/{source_ref}"
    try:
        response = httpx.get(
            url,
            params={"mailto": OPENALEX_MAILTO},
            timeout=20,
        )
        if response.status_code == 404:
            return []
        response.raise_for_status()
    except Exception:
        return []

    payload = response.json()
    counts = payload.get("counts_by_year") or []
    years = [
        int(item["year"])
        for item in counts
        if item.get("year") and (item.get("works_count") or 0) > 0
    ]
    return sorted(set(years), reverse=True)


def _db_years(store: Store, journals: list[str] | None = None) -> list[int]:
    sql = "SELECT DISTINCT year FROM articles WHERE year IS NOT NULL"
    params: list[Any] = []
    if journals:
        placeholders = ",".join("?" * len(journals))
        sql += f" AND journal_short IN ({placeholders})"
        params.extend(journals)
    sql += " ORDER BY year DESC"
    with store._conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [int(row[0]) for row in rows if row[0]]


def discover_history_years(journal_short: str, store: Store | None = None) -> list[int]:
    store = store or Store()
    journal = get_journal_config(journal_short)
    if not journal:
        return []

    years = set(_db_years(store, [journal_short]))
    years.update(_openalex_available_years(journal))
    return sorted(years, reverse=True)


def estimate_cost_per_article(store: Store, journals: list[str] | None = None) -> dict[str, Any]:
    def _cost_rows(scope_journals: list[str] | None) -> list[float]:
        sql = (
            "SELECT cost_usd FROM articles "
            "WHERE agent_processed_at IS NOT NULL AND agent_processed_at != '' "
            "AND cost_usd IS NOT NULL AND cost_usd > 0"
        )
        params: list[Any] = []
        if scope_journals:
            placeholders = ",".join("?" * len(scope_journals))
            sql += f" AND journal_short IN ({placeholders})"
            params.extend(scope_journals)
        sql += " ORDER BY agent_processed_at DESC LIMIT 200"
        with store._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [float(row[0]) for row in rows if row[0] is not None]

    scoped = _cost_rows(journals)
    if len(scoped) >= 5:
        return {"avg_cost_usd": mean(scoped), "source": "scope_recent"}

    global_rows = _cost_rows(None)
    if global_rows:
        return {"avg_cost_usd": mean(global_rows), "source": "global_recent"}

    return {"avg_cost_usd": 0.05, "source": "fallback"}


def prepare_scan_scope(
    store: Store,
    *,
    start_year: int,
    end_year: int,
    journals: list[str] | None = None,
    verbose: bool = False,
    fetch_metadata: bool = True,
) -> dict[str, Any]:
    if fetch_metadata:
        fetch_stats = fetch.run(
            store=store,
            verbose=verbose,
            since_year=start_year,
            end_year=end_year,
            journals=journals,
        )
    else:
        fetch_stats = fetch.FetchStats()

    sql = (
        "SELECT "
        "COUNT(*) AS total, "
        "SUM(CASE WHEN agent_processed_at IS NOT NULL AND agent_processed_at != '' THEN 1 ELSE 0 END) AS processed, "
        "SUM(CASE WHEN agent_processed_at IS NULL OR agent_processed_at = '' THEN 1 ELSE 0 END) AS pending "
        "FROM articles WHERE year >= ? AND year <= ?"
    )
    params: list[Any] = [start_year, end_year]
    if journals:
        placeholders = ",".join("?" * len(journals))
        sql += f" AND journal_short IN ({placeholders})"
        params.extend(journals)

    with store._conn() as conn:
        counts = conn.execute(sql, params).fetchone()

    cost_info = estimate_cost_per_article(store, journals=journals)
    pending_count = int(counts["pending"] or 0)
    avg_cost = float(cost_info["avg_cost_usd"])

    return {
        "start_year": start_year,
        "end_year": end_year,
        "journals": journals or [],
        "total_articles": int(counts["total"] or 0),
        "processed_articles": int(counts["processed"] or 0),
        "pending_articles": pending_count,
        "avg_cost_usd": avg_cost,
        "avg_cost_source": cost_info["source"],
        "estimated_cost_usd": pending_count * avg_cost,
        "fetched_total": fetch_stats.total_fetched,
        "new_in_store": fetch_stats.new_in_store,
        "enriched_ok": fetch_stats.enriched_ok,
        "enrichment_skipped": fetch_stats.enrichment_skipped,
        "enrichment_failed": fetch_stats.enrichment_failed,
        "fetch_errors": list(fetch_stats.errors),
        "scope_years": _db_years(store, journals=journals),
    }
