"""Backfill llm_calls from existing articles.cost_usd entries.

The llm_calls table only captures calls made AFTER the cost-tracking patch
landed. To make historical costs visible in the cost panel, we replay every
article with cost_usd > 0 as a synthetic llm_call entry.

Run once after deploying the cost-tracking patch:

    python3 scripts/backfill_llm_calls.py

Idempotent: if a synthetic entry for an article already exists (same article_id
and endpoint='historical_article'), it is skipped.
"""

from __future__ import annotations

import sqlite3
from journal_bot.store import ARTICLES_DB
from journal_bot.llm_log import LLM_LOG_DB


def main() -> None:
    if ARTICLES_DB != LLM_LOG_DB:
        raise SystemExit(
            f"Expected articles.db and llm_log to live in the same file. "
            f"Got {ARTICLES_DB} vs {LLM_LOG_DB}."
        )

    conn = sqlite3.connect(ARTICLES_DB)
    conn.row_factory = sqlite3.Row
    try:
        # Ensure llm_calls table exists.
        conn.executescript(
            """
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
            """
        )

        rows = conn.execute(
            """
            SELECT id, agent_processed_at, cost_usd,
                   tokens_in, tokens_out, tokens_cached_read, tokens_cache_write
            FROM articles
            WHERE agent_processed_at IS NOT NULL
              AND agent_processed_at != ''
              AND cost_usd IS NOT NULL
              AND cost_usd > 0
            """
        ).fetchall()

        existing_ids = {
            row[0]
            for row in conn.execute(
                "SELECT article_id FROM llm_calls WHERE endpoint = 'historical_article'"
            ).fetchall()
        }

        inserted = 0
        skipped = 0
        for r in rows:
            if r["id"] in existing_ids:
                skipped += 1
                continue
            conn.execute(
                """
                INSERT INTO llm_calls (
                    timestamp, endpoint, model,
                    tokens_in, tokens_out, tokens_cached_read, tokens_cache_write,
                    cost_usd, status, article_id, extra_json
                ) VALUES (?, 'historical_article', 'unknown',
                          ?, ?, ?, ?, ?, 'ok', ?, NULL)
                """,
                (
                    r["agent_processed_at"],
                    r["tokens_in"] or 0,
                    r["tokens_out"] or 0,
                    r["tokens_cached_read"] or 0,
                    r["tokens_cache_write"] or 0,
                    r["cost_usd"],
                    r["id"],
                ),
            )
            inserted += 1
        conn.commit()
    finally:
        conn.close()

    print(
        f"[backfill] Inserted {inserted} synthetic historical_article entries; "
        f"skipped {skipped} that were already backfilled."
    )


if __name__ == "__main__":
    main()
