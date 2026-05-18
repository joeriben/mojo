"""Persistent log of every LLM call MOJO makes.

Lightweight: writes to a separate `llm_calls` table in articles.db. Designed to
be called from anywhere (no Store instance needed) and to never crash callers.

Why this exists:
- `articles.cost_usd` only captures per-article digest cost.
- `batch_screen`, `summarize`, `triage`, `trends`, `research_agent` etc.
  previously dropped their cost on the floor — invisible after the response
  was returned.
- The $43-incident showed that without per-call accounting we cannot debug
  cost spikes after the fact.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from journal_bot.settings import PROJECT_ROOT

LLM_LOG_DB = PROJECT_ROOT / "articles.db"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_calls (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp          TEXT NOT NULL,
    endpoint           TEXT NOT NULL,
    model              TEXT NOT NULL,
    tokens_in          INTEGER DEFAULT 0,
    tokens_out         INTEGER DEFAULT 0,
    tokens_cached_read INTEGER DEFAULT 0,
    tokens_cache_write INTEGER DEFAULT 0,
    cost_usd           REAL DEFAULT 0.0,
    status             TEXT,
    article_id         TEXT,
    extra_json         TEXT
);
CREATE INDEX IF NOT EXISTS idx_llm_calls_ts        ON llm_calls(timestamp);
CREATE INDEX IF NOT EXISTS idx_llm_calls_endpoint  ON llm_calls(endpoint);
CREATE INDEX IF NOT EXISTS idx_llm_calls_model     ON llm_calls(model);
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)


def record_llm_call(
    *,
    endpoint: str,
    model: str,
    usage: dict | None = None,
    cost_usd: float | None = None,
    status: str = "ok",
    article_id: str | None = None,
    **extra: Any,
) -> None:
    """Append one row to llm_calls. Never raises.

    Args:
      endpoint: Where the call was made from. Examples:
        "batch_screen", "run_agent", "assess", "verify",
        "research_chat", "research_focused_db", "summarize", "triage",
        "trends", "scout".
      model: Full OpenRouter model id (e.g. "anthropic/claude-opus-4.6").
      usage: The usage object from the OpenRouter response (model_dump or dict).
      cost_usd: Override cost. If None, will try usage["cost"].
      status: "ok", "aborted_*", "error".
      article_id: Link to articles.id when applicable.
      **extra: Free-form metadata stored as JSON (batch_num, conversation_id,
               iteration, hypothesis count, ...).
    """
    try:
        usage = usage or {}
        if cost_usd is None:
            cost_usd = float(usage.get("cost") or 0.0)
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        pd = usage.get("prompt_tokens_details") or {}
        cached_read = int(pd.get("cached_tokens") or 0)
        cache_write = int(pd.get("cache_write_tokens") or 0)

        conn = sqlite3.connect(LLM_LOG_DB)
        try:
            _ensure_schema(conn)
            conn.execute(
                """
                INSERT INTO llm_calls (
                    timestamp, endpoint, model,
                    tokens_in, tokens_out, tokens_cached_read, tokens_cache_write,
                    cost_usd, status, article_id, extra_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    endpoint,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    cached_read,
                    cache_write,
                    float(cost_usd),
                    status,
                    article_id,
                    json.dumps(extra, ensure_ascii=False) if extra else None,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        # Never break the caller. Log to stderr so cost-tracking failures are
        # visible but don't take production runs down.
        print(f"[llm_log] record_llm_call failed: {exc}", file=sys.stderr)


def summarize_costs(
    *,
    since: str | None = None,
    until: str | None = None,
    by: str = "endpoint",
) -> list[dict]:
    """Aggregate costs for a UI panel. `by` is "endpoint", "model", or "day".

    `since`/`until` are ISO timestamps; defaults: all-time.
    """
    if by not in ("endpoint", "model", "day"):
        raise ValueError("by must be 'endpoint', 'model', or 'day'")

    group_expr = {
        "endpoint": "endpoint",
        "model": "model",
        "day": "substr(timestamp, 1, 10)",
    }[by]

    sql = (
        f"SELECT {group_expr} AS bucket, "
        "COUNT(*) AS calls, "
        "COALESCE(SUM(cost_usd), 0) AS total_cost, "
        "COALESCE(SUM(tokens_in), 0) AS total_in, "
        "COALESCE(SUM(tokens_out), 0) AS total_out, "
        "COALESCE(SUM(tokens_cached_read), 0) AS total_cached_read "
        "FROM llm_calls WHERE 1=1"
    )
    params: list[Any] = []
    if since:
        sql += " AND timestamp >= ?"
        params.append(since)
    if until:
        sql += " AND timestamp <= ?"
        params.append(until)
    sql += " GROUP BY bucket ORDER BY total_cost DESC"

    try:
        conn = sqlite3.connect(LLM_LOG_DB)
        try:
            _ensure_schema(conn)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception as exc:
        print(f"[llm_log] summarize_costs failed: {exc}", file=sys.stderr)
        return []


def recent_calls(limit: int = 100) -> list[dict]:
    """Last N calls in chronological reverse order."""
    try:
        conn = sqlite3.connect(LLM_LOG_DB)
        try:
            _ensure_schema(conn)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM llm_calls ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    except Exception as exc:
        print(f"[llm_log] recent_calls failed: {exc}", file=sys.stderr)
        return []


def total_cost_since(since: str) -> float:
    """Total recorded cost since an ISO timestamp."""
    try:
        conn = sqlite3.connect(LLM_LOG_DB)
        try:
            _ensure_schema(conn)
            row = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM llm_calls WHERE timestamp >= ?",
                (since,),
            ).fetchone()
            return float(row[0] or 0.0)
        finally:
            conn.close()
    except Exception as exc:
        print(f"[llm_log] total_cost_since failed: {exc}", file=sys.stderr)
        return 0.0


def wave_marker() -> str:
    """Return an ISO timestamp suitable as 'since' filter at wave start.

    Call this *before* the wave begins and pass the result to
    `cache_hit_stats(since=...)` after it finishes — that scopes the report
    to exactly this run.
    """
    return datetime.now(timezone.utc).isoformat()


def cache_hit_stats(
    *,
    since: str | None = None,
    until: str | None = None,
    endpoints: list[str] | None = None,
    models: list[str] | None = None,
) -> list[dict]:
    """Cache effectiveness aggregated per (endpoint, model).

    A call counts toward `cache_hit_rate` only if its tokens_in > 0 — calls
    with zero input (errors, no-cost paths) would otherwise distort the ratio.

    Returns one row per (endpoint, model) with fields:
      endpoint, model, calls, total_cost, total_in, total_cached_read,
      cache_hit_rate (cached_read / total_in, float 0..1),
      avg_cost_per_call, avg_cached_read_per_call.

    Sort: total_cost DESC — the rows where cache matters most for the wallet
    appear first.
    """
    sql = (
        "SELECT endpoint, model, "
        "COUNT(*) AS calls, "
        "COALESCE(SUM(cost_usd), 0) AS total_cost, "
        "COALESCE(SUM(tokens_in), 0) AS total_in, "
        "COALESCE(SUM(tokens_cached_read), 0) AS total_cached_read, "
        "COALESCE(SUM(tokens_cache_write), 0) AS total_cache_write "
        "FROM llm_calls WHERE 1=1"
    )
    params: list[Any] = []
    if since:
        sql += " AND timestamp >= ?"
        params.append(since)
    if until:
        sql += " AND timestamp <= ?"
        params.append(until)
    if endpoints:
        placeholders = ",".join("?" for _ in endpoints)
        sql += f" AND endpoint IN ({placeholders})"
        params.extend(endpoints)
    if models:
        placeholders = ",".join("?" for _ in models)
        sql += f" AND model IN ({placeholders})"
        params.extend(models)
    # Status filter: only successful calls — aborted ones report
    # questionable usage data.
    sql += " AND (status = 'ok' OR status IS NULL)"
    sql += " GROUP BY endpoint, model ORDER BY total_cost DESC"

    try:
        conn = sqlite3.connect(LLM_LOG_DB)
        try:
            _ensure_schema(conn)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
    except Exception as exc:
        print(f"[llm_log] cache_hit_stats failed: {exc}", file=sys.stderr)
        return []

    out: list[dict] = []
    for r in rows:
        d = dict(r)
        total_in = d["total_in"] or 0
        cached = d["total_cached_read"] or 0
        d["cache_hit_rate"] = (cached / total_in) if total_in > 0 else 0.0
        d["avg_cost_per_call"] = (d["total_cost"] / d["calls"]) if d["calls"] else 0.0
        d["avg_cached_read_per_call"] = (cached / d["calls"]) if d["calls"] else 0.0
        out.append(d)
    return out


# Endpoints whose cost is dominated by a cacheable system prompt — drift
# below the threshold here is the canary for the $43-class incident.
_CACHE_CRITICAL_ENDPOINTS = ("batch_screen", "run_agent", "assess", "verify")
_CACHE_HEALTHY_THRESHOLD = 0.80


def is_cache_warning(row: dict, *, min_calls: int = 2) -> bool:
    """Return True if an aggregated cache_hit_stats row deserves the ⚠ flag.

    Single source of truth for terminal report (format_cache_report) and the
    web UI (_scan_run_result.html via the cache_warning Jinja filter).

    Cold-start protection via min_calls:
    - In a per-wave report, min_calls=2 is fine — within one wave there's
      typically exactly one cold-start call, so 2+ calls below 80 % means
      the *non-cold* calls are also bad → real cache problem.
    - In a multi-wave (e.g. 7-day) report, min_calls=5 makes more sense —
      otherwise every 2-wave window with one cold-start call per wave would
      show up as a token-weighted ~50 % hit rate and trigger a false alarm.
    """
    return (
        row.get("endpoint") in _CACHE_CRITICAL_ENDPOINTS
        and (row.get("cache_hit_rate") or 0.0) < _CACHE_HEALTHY_THRESHOLD
        and (row.get("calls") or 0) >= min_calls
    )


def format_cache_report(
    stats: list[dict],
    *,
    title: str = "Cache-Hit-Rate",
    min_calls_for_flag: int = 2,
) -> str:
    """Render a human-readable table for the CLI / wave footer.

    Marks cache-critical endpoints below 80 % hit rate with a ⚠ flag —
    that's the signal to investigate, not the signal to abort (hard caps
    in agent.py already enforce abort).

    `min_calls_for_flag` controls cold-start sensitivity: use 2 for
    per-wave reports, 5+ for multi-wave aggregates (see is_cache_warning).
    """
    if not stats:
        return f"[{title}] keine LLM-Calls im Fenster."

    lines = [f"[{title}]"]
    header = f"  {'Endpoint':<14} {'Modell':<32} {'Calls':>5} {'Hit%':>5} {'Ø$':>7} {'Σ$':>8}"
    lines.append(header)
    lines.append("  " + "-" * (len(header) - 2))
    for r in stats:
        endpoint = r["endpoint"][:14]
        model = (r["model"] or "")[:32]
        calls = r["calls"]
        hit = r["cache_hit_rate"] * 100
        avg = r["avg_cost_per_call"]
        tot = r["total_cost"]
        flag = "  ⚠ unter 80%" if is_cache_warning(r, min_calls=min_calls_for_flag) else ""
        lines.append(
            f"  {endpoint:<14} {model:<32} {calls:>5} {hit:>4.0f}% "
            f"${avg:>6.3f} ${tot:>7.3f}{flag}"
        )
    return "\n".join(lines)
