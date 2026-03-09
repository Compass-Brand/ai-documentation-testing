"""Tests for stability metrics computation."""

from __future__ import annotations

import pytest

from agent_evals.reports.stability import (
    StabilityMetrics,
    compare_strategy_stability,
    compute_stability,
)


class TestComputeStability:
    def test_perfect_stability(self):
        scores = [0.8, 0.8, 0.8, 0.8, 0.8]
        result = compute_stability(scores)
        assert result.coefficient_of_variation == 0.0
        assert result.min_max_spread == 0.0

    def test_moderate_variance(self):
        scores = [0.7, 0.8, 0.75, 0.85, 0.9]
        result = compute_stability(scores)
        assert 0.0 < result.coefficient_of_variation < 0.2
        assert result.min_max_spread == pytest.approx(0.2)

    def test_high_variance(self):
        scores = [0.1, 0.9, 0.2, 0.8, 0.5]
        result = compute_stability(scores)
        assert result.coefficient_of_variation > 0.3

    def test_single_score_returns_zero_variance(self):
        result = compute_stability([0.5])
        assert result.coefficient_of_variation == 0.0
        assert result.min_max_spread == 0.0

    def test_empty_scores_returns_zero(self):
        result = compute_stability([])
        assert result.coefficient_of_variation == 0.0
        assert result.mean == 0.0

    def test_metrics_fields(self):
        result = compute_stability([0.6, 0.7, 0.8])
        assert hasattr(result, "mean")
        assert hasattr(result, "std_dev")
        assert hasattr(result, "coefficient_of_variation")
        assert hasattr(result, "min_max_spread")
        assert hasattr(result, "count")


class TestStabilityFallbackExclusion:
    def test_stability_excludes_fallback_trials(self):
        """When exclude_fallbacks=True, trials with provider fallbacks are removed."""
        from agent_evals.metrics import CostMetrics

        scores = [0.8, 0.5, 0.82, 0.79, 0.3]
        cost_metrics_list = [
            CostMetrics(
                prompt_tokens=100, completion_tokens=50, reasoning_tokens=0,
                cached_tokens=0, cache_write_tokens=0, total_cost_usd=0.005,
                cache_discount_usd=None, latency_ms=450.0, generation_time_ms=None,
                provider="Anthropic", generation_id="gen-1", provider_fallbacks=0,
            ),
            CostMetrics(
                prompt_tokens=100, completion_tokens=50, reasoning_tokens=0,
                cached_tokens=0, cache_write_tokens=0, total_cost_usd=0.005,
                cache_discount_usd=None, latency_ms=900.0, generation_time_ms=None,
                provider="Google", generation_id="gen-2", provider_fallbacks=2,
            ),
            CostMetrics(
                prompt_tokens=100, completion_tokens=50, reasoning_tokens=0,
                cached_tokens=0, cache_write_tokens=0, total_cost_usd=0.005,
                cache_discount_usd=None, latency_ms=460.0, generation_time_ms=None,
                provider="Anthropic", generation_id="gen-3", provider_fallbacks=0,
            ),
            CostMetrics(
                prompt_tokens=100, completion_tokens=50, reasoning_tokens=0,
                cached_tokens=0, cache_write_tokens=0, total_cost_usd=0.005,
                cache_discount_usd=None, latency_ms=440.0, generation_time_ms=None,
                provider="Anthropic", generation_id="gen-4", provider_fallbacks=0,
            ),
            CostMetrics(
                prompt_tokens=100, completion_tokens=50, reasoning_tokens=0,
                cached_tokens=0, cache_write_tokens=0, total_cost_usd=0.005,
                cache_discount_usd=None, latency_ms=1200.0, generation_time_ms=None,
                provider="Google", generation_id="gen-5", provider_fallbacks=1,
            ),
        ]

        # Without exclusion: includes noisy fallback trials
        result_all = compute_stability(scores)
        # With exclusion: only non-fallback trials [0.8, 0.82, 0.79]
        result_filtered = compute_stability(
            scores,
            exclude_fallbacks=True,
            cost_metrics_list=cost_metrics_list,
        )
        assert result_filtered.count == 3
        assert result_filtered.coefficient_of_variation < result_all.coefficient_of_variation


class TestPerStrategyStabilityComparison:
    def test_per_strategy_stability_comparison(self):
        """Computes stability independently per strategy."""
        trials_by_strategy = {
            "full_context": [0.80, 0.82, 0.79, 0.81, 0.80],
            "tool_based": [0.70, 0.90, 0.50, 0.85, 0.65],
        }
        result = compare_strategy_stability(trials_by_strategy)

        assert "full_context" in result
        assert "tool_based" in result
        assert isinstance(result["full_context"], StabilityMetrics)
        assert isinstance(result["tool_based"], StabilityMetrics)
        # full_context should be more stable (lower CV)
        assert result["full_context"].coefficient_of_variation < \
            result["tool_based"].coefficient_of_variation

    def test_empty_strategies_returns_empty(self):
        assert compare_strategy_stability({}) == {}
