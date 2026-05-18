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


class CacheHitStatsTests(unittest.TestCase):
    """`cache_hit_stats` is the wave-end report — must aggregate by
    (endpoint, model), compute hit rate from tokens not from calls, and
    flag cache-critical endpoints below 80 %."""

    def setUp(self) -> None:
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self._tmp_path = Path(self._tmp.name)

        from journal_bot import llm_log
        self._patcher = mock.patch.object(llm_log, "LLM_LOG_DB", self._tmp_path)
        self._patcher.start()

    def tearDown(self) -> None:
        self._patcher.stop()
        self._tmp_path.unlink(missing_ok=True)

    @staticmethod
    def _record(endpoint: str, prompt: int, cached: int, cost: float,
                model: str = "anthropic/claude-opus-4.6") -> None:
        from journal_bot.llm_log import record_llm_call
        record_llm_call(
            endpoint=endpoint, model=model,
            usage={
                "prompt_tokens": prompt,
                "completion_tokens": 100,
                "cost": cost,
                "prompt_tokens_details": {"cached_tokens": cached},
            },
        )

    def test_hit_rate_is_token_weighted_not_call_weighted(self) -> None:
        # Three calls with same hit rate (50 %) — aggregated must stay 50 %,
        # not average-of-percentages.
        for _ in range(3):
            self._record("assess", prompt=1000, cached=500, cost=0.05)

        from journal_bot.llm_log import cache_hit_stats
        rows = cache_hit_stats()
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["cache_hit_rate"], 0.5, places=4)
        self.assertEqual(rows[0]["calls"], 3)

    def test_hit_rate_weights_by_tokens(self) -> None:
        # One small call with 100 % hit, one huge call with 0 % hit —
        # token-weighted hit rate must reflect the huge call's dominance.
        self._record("assess", prompt=100, cached=100, cost=0.001)
        self._record("assess", prompt=10_000, cached=0, cost=0.50)

        from journal_bot.llm_log import cache_hit_stats
        rows = cache_hit_stats()
        self.assertAlmostEqual(rows[0]["cache_hit_rate"], 100 / 10_100, places=4)

    def test_groups_by_endpoint_and_model_separately(self) -> None:
        self._record("assess", prompt=1000, cached=900, cost=0.02)
        self._record("verify", prompt=1000, cached=900, cost=0.02)
        self._record("assess", prompt=1000, cached=900, cost=0.02,
                     model="deepseek/deepseek-v3.2")

        from journal_bot.llm_log import cache_hit_stats
        rows = cache_hit_stats()
        keys = {(r["endpoint"], r["model"]) for r in rows}
        self.assertIn(("assess", "anthropic/claude-opus-4.6"), keys)
        self.assertIn(("verify", "anthropic/claude-opus-4.6"), keys)
        self.assertIn(("assess", "deepseek/deepseek-v3.2"), keys)

    def test_endpoint_filter_restricts_rows(self) -> None:
        self._record("assess", prompt=1000, cached=900, cost=0.02)
        self._record("trends", prompt=1000, cached=0, cost=0.55)

        from journal_bot.llm_log import cache_hit_stats
        rows = cache_hit_stats(endpoints=["assess"])
        self.assertEqual([r["endpoint"] for r in rows], ["assess"])

    def test_since_filter_excludes_old_rows(self) -> None:
        self._record("assess", prompt=1000, cached=500, cost=0.02)

        from journal_bot.llm_log import cache_hit_stats
        # Far-future cutoff: no rows survive.
        rows = cache_hit_stats(since="2999-01-01")
        self.assertEqual(rows, [])

    def test_format_cache_report_flags_critical_below_80(self) -> None:
        from journal_bot.llm_log import format_cache_report

        stats = [
            # Cache-critical endpoint, below 80 % — must get the ⚠ flag.
            {"endpoint": "assess", "model": "anthropic/claude-opus-4.6",
             "calls": 5, "cache_hit_rate": 0.45,
             "avg_cost_per_call": 0.08, "total_cost": 0.40},
            # Cache-critical, healthy — must NOT get the flag.
            {"endpoint": "verify", "model": "anthropic/claude-opus-4.6",
             "calls": 5, "cache_hit_rate": 0.92,
             "avg_cost_per_call": 0.03, "total_cost": 0.15},
            # Non-critical endpoint at 0 % — must NOT get the flag.
            {"endpoint": "trends", "model": "xiaomi/mimo-v2.5-pro",
             "calls": 1, "cache_hit_rate": 0.0,
             "avg_cost_per_call": 0.55, "total_cost": 0.55},
        ]
        rendered = format_cache_report(stats)
        # The flag annotation must show up exactly once.
        self.assertEqual(rendered.count("⚠ unter 80%"), 1)
        # And it must be on the assess line.
        assess_line = [
            line for line in rendered.splitlines()
            if line.lstrip().startswith("assess")
        ][0]
        self.assertIn("⚠ unter 80%", assess_line)

    def test_format_report_empty_input(self) -> None:
        from journal_bot.llm_log import format_cache_report
        text = format_cache_report([])
        self.assertIn("keine LLM-Calls", text)

    def test_wave_marker_yields_iso_timestamp(self) -> None:
        from journal_bot.llm_log import wave_marker
        ts = wave_marker()
        # Sanity: 'T' between date and time, '+' for offset, parseable.
        self.assertIn("T", ts)
        from datetime import datetime
        # Must round-trip through fromisoformat without raising.
        datetime.fromisoformat(ts)

    def test_verify_endpoint_appears_in_wave_report(self) -> None:
        """Verify is cache-critical and structurally symmetric to assess —
        a real wave with assess+verify must surface both rows in the report,
        and verify must get the ⚠ flag if it falls below 80 %."""
        # Simulate a wave: 5 assess calls (healthy), 3 verify calls (cold).
        for _ in range(5):
            self._record("assess", prompt=4000, cached=3800, cost=0.04)
        for _ in range(3):
            self._record("verify", prompt=5000, cached=1500, cost=0.06)

        from journal_bot.llm_log import cache_hit_stats, format_cache_report
        rows = cache_hit_stats()
        by_endpoint = {r["endpoint"]: r for r in rows}
        self.assertIn("assess", by_endpoint)
        self.assertIn("verify", by_endpoint)
        # Assess token-weighted hit rate: 5*3800 / 5*4000 = 0.95 → no flag.
        self.assertAlmostEqual(by_endpoint["assess"]["cache_hit_rate"], 0.95, places=4)
        # Verify token-weighted hit rate: 3*1500 / 3*5000 = 0.30 → must flag.
        self.assertAlmostEqual(by_endpoint["verify"]["cache_hit_rate"], 0.30, places=4)

        rendered = format_cache_report(rows)
        # Both endpoints must appear in the rendered table.
        self.assertIn("assess", rendered)
        self.assertIn("verify", rendered)
        # Flag must show up exactly once — on the verify row.
        self.assertEqual(rendered.count("⚠ unter 80%"), 1)
        verify_line = [
            line for line in rendered.splitlines()
            if line.lstrip().startswith("verify")
        ][0]
        self.assertIn("⚠ unter 80%", verify_line)

    def test_verify_single_call_does_not_trigger_flag(self) -> None:
        """Cold-start protection: first verify call in a wave (after a
        5-min cache eviction) is naturally 0 % hit — must not alarm."""
        self._record("verify", prompt=5000, cached=0, cost=0.10)

        from journal_bot.llm_log import cache_hit_stats, format_cache_report
        rendered = format_cache_report(cache_hit_stats())
        self.assertIn("verify", rendered)
        # Single call → no flag even though hit rate is 0 %.
        self.assertEqual(rendered.count("⚠ unter 80%"), 0)

    def test_min_calls_for_flag_suppresses_multi_wave_cold_starts(self) -> None:
        """The 7-day aggregate must use min_calls_for_flag=5 to avoid
        false-positives. Two waves of batch_screen (1 cold + 1 hot each)
        token-weighted aggregate to ~50 % — looks bad, but is normal
        operation. The stricter flag threshold suppresses this."""
        # Wave 1: cold + hot
        self._record("batch_screen", prompt=30_000, cached=0, cost=0.016,
                     model="deepseek/deepseek-v3.2")
        self._record("batch_screen", prompt=30_000, cached=29_900, cost=0.008,
                     model="deepseek/deepseek-v3.2")
        # Wave 2: cold + hot
        self._record("batch_screen", prompt=30_000, cached=0, cost=0.016,
                     model="deepseek/deepseek-v3.2")
        self._record("batch_screen", prompt=30_000, cached=29_900, cost=0.008,
                     model="deepseek/deepseek-v3.2")

        from journal_bot.llm_log import cache_hit_stats, format_cache_report
        rows = cache_hit_stats()
        # Token-weighted aggregate hit rate is ~50 % (29900*2 / 30000*4)
        self.assertAlmostEqual(rows[0]["cache_hit_rate"], 29_900 * 2 / (30_000 * 4), places=3)

        # Per-wave threshold (min=2): flag fires (false positive for multi-wave data)
        per_wave = format_cache_report(rows, min_calls_for_flag=2)
        self.assertEqual(per_wave.count("⚠ unter 80%"), 1)

        # 7-day threshold (min=5): flag suppressed because only 4 calls
        weekly = format_cache_report(rows, min_calls_for_flag=5)
        self.assertEqual(weekly.count("⚠ unter 80%"), 0)

    def test_min_calls_for_flag_still_catches_real_breakdown(self) -> None:
        """A genuine cache breakdown (8 calls all below 80 %) must still
        trigger the flag even at the stricter 5-call threshold."""
        for _ in range(8):
            self._record("assess", prompt=5_000, cached=1_000, cost=0.08)

        from journal_bot.llm_log import cache_hit_stats, format_cache_report
        rendered = format_cache_report(cache_hit_stats(), min_calls_for_flag=5)
        # 8 calls, 20 % hit, cache-critical endpoint → must flag.
        self.assertEqual(rendered.count("⚠ unter 80%"), 1)


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
