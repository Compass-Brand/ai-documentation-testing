"""Phase B integration tests — operational metrics pipeline."""

from __future__ import annotations

from agent_evals.llm.client import GenerationResult
from agent_evals.metrics import CostMetrics
from agent_evals.reports.stability import compute_stability


class TestMetricsPipelineIntegration:
    def test_generation_result_to_cost_metrics(self):
        """GenerationResult fields populate CostMetrics correctly."""
        gen = GenerationResult(
            content="response",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.005,
            model="test-model",
            generation_id="gen-123",
            api_call_ms=450.0,
            cached_tokens=80,
            cache_write_tokens=20,
            reasoning_tokens=10,
            provider="Anthropic",
        )
        metrics = CostMetrics(
            prompt_tokens=gen.prompt_tokens,
            completion_tokens=gen.completion_tokens,
            reasoning_tokens=gen.reasoning_tokens,
            cached_tokens=gen.cached_tokens,
            cache_write_tokens=gen.cache_write_tokens,
            total_cost_usd=gen.cost,
            cache_discount_usd=None,
            latency_ms=gen.api_call_ms,
            generation_time_ms=None,
            provider=gen.provider,
            generation_id=gen.generation_id,
            provider_fallbacks=0,
        )
        assert metrics.cache_hit_rate == 0.8
        d = metrics.to_dict()
        assert d["provider"] == "Anthropic"

    def test_stability_feeds_cost_efficiency(self):
        """Stability metrics integrate with cost-efficiency rows."""
        scores = [0.80, 0.82, 0.78, 0.81, 0.79]
        stability = compute_stability(scores)

        # Import here to avoid failing if cost_efficiency isn't created yet
        from agent_evals.reports.cost_efficiency import CostEfficiencyRow

        row = CostEfficiencyRow(
            variant_name="2-tier-md",
            accuracy=stability.mean * 100,
            cost_per_trial=0.004,
            variance=stability.coefficient_of_variation * 100,
        )
        assert row.accuracy > 0
        assert row.variance < 10  # Low CV = stable

    def test_pareto_and_render_pipeline(self):
        """Full pipeline: metrics → Pareto → rendered table."""
        from agent_evals.reports.cost_efficiency import (
            CostEfficiencyRow,
            compute_pareto_frontier,
            render_cost_efficiency_table,
        )

        rows = [
            CostEfficiencyRow("A", 82.0, 0.004, 3.0),
            CostEfficiencyRow("B", 71.0, 0.003, 2.0),
            CostEfficiencyRow("C", 60.0, 0.010, 10.0),
        ]
        frontier = compute_pareto_frontier(rows)
        assert len(frontier) >= 1

        text = render_cost_efficiency_table(rows)
        assert "A" in text
