"""Tests for operational metrics data models."""

from __future__ import annotations

import pytest

from agent_evals.metrics import CostMetrics, TurnMetrics, aggregate_turn_metrics


class TestCostMetrics:
    def test_construction_with_all_fields(self):
        m = CostMetrics(
            prompt_tokens=100,
            completion_tokens=50,
            reasoning_tokens=10,
            cached_tokens=80,
            cache_write_tokens=20,
            total_cost_usd=0.005,
            cache_discount_usd=0.003,
            latency_ms=450.0,
            generation_time_ms=380.0,
            provider="Anthropic",
            generation_id="gen-123",
            provider_fallbacks=0,
        )
        assert m.total_cost_usd == 0.005
        assert m.cache_hit_rate == 0.8  # 80/100

    def test_cache_hit_rate_zero_when_no_prompt_tokens(self):
        m = CostMetrics(
            prompt_tokens=0,
            completion_tokens=50,
            reasoning_tokens=0,
            cached_tokens=0,
            cache_write_tokens=0,
            total_cost_usd=0.001,
            cache_discount_usd=None,
            latency_ms=None,
            generation_time_ms=None,
            provider=None,
            generation_id=None,
            provider_fallbacks=0,
        )
        assert m.cache_hit_rate == 0.0

    def test_to_dict_serializable(self):
        m = CostMetrics(
            prompt_tokens=100,
            completion_tokens=50,
            reasoning_tokens=0,
            cached_tokens=0,
            cache_write_tokens=0,
            total_cost_usd=0.005,
            cache_discount_usd=None,
            latency_ms=450.0,
            generation_time_ms=None,
            provider="Anthropic",
            generation_id="gen-123",
            provider_fallbacks=0,
        )
        d = m.to_dict()
        assert isinstance(d, dict)
        assert d["prompt_tokens"] == 100
        assert d["provider"] == "Anthropic"


class TestTurnMetrics:
    def test_construction(self):
        t = TurnMetrics(
            turn=1,
            prompt_tokens=50,
            completion_tokens=25,
            cost_usd=0.001,
            api_call_ms=200.0,
            tool_name="read_doc",
        )
        assert t.turn == 1
        assert t.tool_name == "read_doc"


class TestAggregateTurnMetrics:
    def test_aggregates_across_turns(self):
        turns = [
            TurnMetrics(1, 50, 25, 0.001, 200.0, "list_docs"),
            TurnMetrics(2, 80, 30, 0.002, 300.0, "read_doc"),
            TurnMetrics(3, 100, 40, 0.003, 250.0, None),
        ]
        agg = aggregate_turn_metrics(turns)
        assert agg.prompt_tokens == 230
        assert agg.completion_tokens == 95
        assert abs(agg.total_cost_usd - 0.006) < 0.0001

    def test_empty_turns_returns_zero_metrics(self):
        agg = aggregate_turn_metrics([])
        assert agg.prompt_tokens == 0
        assert agg.total_cost_usd == 0.0
