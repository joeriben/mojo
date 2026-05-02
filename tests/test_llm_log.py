"""Tests for llm_log persistence and the hardened cache guard in agent.py."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class LlmLogPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        # Redirect llm_log to a temp DB so tests don't pollute articles.db.
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._tmp_path = Path(self._tmp.name)

        from journal_bot import llm_log
        self._patcher = mock.patch.object(llm_log, "LLM_LOG_DB", self._tmp_path)
        self._patcher.start()

    def tearDown(self) -> None:
        self._patcher.stop()
        self._tmp_path.unlink(missing_ok=True)

    def test_record_creates_table_and_row(self) -> None:
        from journal_bot.llm_log import record_llm_call

        usage = {
            "prompt_tokens": 1234,
            "completion_tokens": 56,
            "cost": 0.012,
            "prompt_tokens_details": {"cached_tokens": 1000, "cache_write_tokens": 100},
        }
        record_llm_call(
            endpoint="test_endpoint",
            model="test/model",
            usage=usage,
            status="ok",
            article_id="abc123",
            iteration=2,
        )

        conn = sqlite3.connect(self._tmp_path)
        try:
            row = conn.execute("SELECT * FROM llm_calls").fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)

    def test_record_never_raises_on_bad_input(self) -> None:
        from journal_bot.llm_log import record_llm_call

        # Passing nonsense should not raise — the helper has its own try/except.
        record_llm_call(endpoint="x", model="y", usage="not a dict")  # type: ignore[arg-type]
        record_llm_call(endpoint="x", model="y", cost_usd=None)  # type: ignore[arg-type]

    def test_summarize_costs_groups_correctly(self) -> None:
        from journal_bot.llm_log import record_llm_call, summarize_costs

        for endpoint, cost in [
            ("a", 0.10),
            ("a", 0.20),
            ("b", 0.05),
        ]:
            record_llm_call(
                endpoint=endpoint, model="m",
                usage={"prompt_tokens": 100, "completion_tokens": 10},
                cost_usd=cost,
            )

        rows = summarize_costs(by="endpoint")
        as_map = {r["bucket"]: r for r in rows}
        self.assertAlmostEqual(as_map["a"]["total_cost"], 0.30, places=4)
        self.assertEqual(as_map["a"]["calls"], 2)
        self.assertAlmostEqual(as_map["b"]["total_cost"], 0.05, places=4)

    def test_total_cost_since_filters_by_timestamp(self) -> None:
        from journal_bot.llm_log import record_llm_call, total_cost_since

        record_llm_call(endpoint="x", model="m", cost_usd=0.5)
        # Anything since 1970 should equal 0.5
        self.assertAlmostEqual(total_cost_since("1970-01-01"), 0.5, places=4)
        # Anything since 2999 should be 0
        self.assertEqual(total_cost_since("2999-01-01"), 0.0)

    def test_recent_calls_returns_newest_first(self) -> None:
        from journal_bot.llm_log import record_llm_call, recent_calls

        for i in range(5):
            record_llm_call(endpoint=f"call_{i}", model="m", cost_usd=0.01 * i)
        calls = recent_calls(limit=3)
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0]["endpoint"], "call_4")
        self.assertEqual(calls[1]["endpoint"], "call_3")


class CacheGuardCapTests(unittest.TestCase):
    """The hardened cache guard must abort regardless of cache reporting."""

    def test_max_total_budget_routing(self) -> None:
        from journal_bot.agent import (
            _max_total_batch_screen_cost_usd,
            _MAX_TOTAL_BATCH_COST_CHEAP_USD,
            _MAX_TOTAL_BATCH_COST_EXPENSIVE_USD,
        )

        # DeepSeek (price 0.26 < 2.0) → cheap tier
        self.assertEqual(
            _max_total_batch_screen_cost_usd("deepseek/deepseek-v3.2"),
            _MAX_TOTAL_BATCH_COST_CHEAP_USD,
        )
        # Opus (price 15 >= 2.0) → expensive tier
        self.assertEqual(
            _max_total_batch_screen_cost_usd("anthropic/claude-opus-4.6"),
            _MAX_TOTAL_BATCH_COST_EXPENSIVE_USD,
        )
        # Sonnet (price 3 >= 2.0) → expensive tier
        self.assertEqual(
            _max_total_batch_screen_cost_usd("anthropic/claude-sonnet-4.6"),
            _MAX_TOTAL_BATCH_COST_EXPENSIVE_USD,
        )
        # Haiku (price 1.0 < 2.0) → cheap tier
        self.assertEqual(
            _max_total_batch_screen_cost_usd("anthropic/claude-haiku-4.5"),
            _MAX_TOTAL_BATCH_COST_CHEAP_USD,
        )
        # Unknown model → defaults to cheap (stricter)
        self.assertEqual(
            _max_total_batch_screen_cost_usd("unknown/model"),
            _MAX_TOTAL_BATCH_COST_CHEAP_USD,
        )

    def test_single_batch_cap_constant_is_strict(self) -> None:
        """The single-batch cap must catch a typical Opus uncached batch
        ($0.45 expected for ~28k token prompt). Don't accidentally raise it
        without thinking."""
        from journal_bot.agent import _MAX_SINGLE_BATCH_COST_USD

        # An Opus batch without cache costs ~$0.45 for 28k token prompt.
        # Cap must trigger *below* that.
        self.assertLess(_MAX_SINGLE_BATCH_COST_USD, 0.45)


if __name__ == "__main__":
    unittest.main()
