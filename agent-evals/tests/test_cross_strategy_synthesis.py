"""Tests for cross-strategy synthesis report (Phase C exit criteria)."""

from __future__ import annotations


class TestCrossStrategyRecommendation:
    def test_cross_strategy_recommendation_generated(self):
        from agent_evals.reports.cross_strategy_synthesis import (
            generate_cross_strategy_recommendation,
        )

        phase_results_by_strategy = {
            "full_context": {
                "optimal_levels": {
                    "axis_1": "yaml",
                    "axis_2": "hierarchical",
                    "axis_11": "tool-desc-detailed",
                },
                "factor_rankings": [
                    ("axis_1", 0.15),
                    ("axis_2", 0.10),
                    ("axis_11", 0.08),
                ],
                "mean_score": 0.82,
            },
            "system_prompt": {
                "optimal_levels": {
                    "axis_1": "yaml",
                    "axis_2": "hierarchical",
                    "axis_11": "tool-desc-standard",
                },
                "factor_rankings": [
                    ("axis_1", 0.12),
                    ("axis_2", 0.11),
                    ("axis_11", 0.05),
                ],
                "mean_score": 0.78,
            },
            "rag": {
                "optimal_levels": {
                    "axis_1": "json",
                    "axis_2": "flat",
                    "axis_11": "tool-desc-detailed",
                },
                "factor_rankings": [
                    ("axis_1", 0.18),
                    ("axis_2", 0.06),
                    ("axis_11", 0.09),
                ],
                "mean_score": 0.75,
            },
            "tool_based": {
                "optimal_levels": {
                    "axis_1": "yaml",
                    "axis_2": "hierarchical",
                    "axis_11": "tool-desc-detailed",
                },
                "factor_rankings": [
                    ("axis_1", 0.14),
                    ("axis_11", 0.12),
                    ("axis_2", 0.07),
                ],
                "mean_score": 0.80,
            },
            "mcp_native": {
                "optimal_levels": {
                    "axis_1": "yaml",
                    "axis_2": "hierarchical",
                    "axis_11": "tool-desc-detailed",
                },
                "factor_rankings": [
                    ("axis_11", 0.16),
                    ("axis_1", 0.13),
                    ("axis_2", 0.09),
                ],
                "mean_score": 0.79,
            },
            "compression": {
                "optimal_levels": {
                    "axis_1": "yaml",
                    "axis_2": "flat",
                    "axis_11": "tool-desc-standard",
                },
                "factor_rankings": [
                    ("axis_1", 0.20),
                    ("axis_2", 0.05),
                    ("axis_11", 0.04),
                ],
                "mean_score": 0.73,
            },
        }
        recommendation = generate_cross_strategy_recommendation(
            phase_results_by_strategy,
        )
        assert isinstance(recommendation, str)
        assert len(recommendation) > 100
        assert "format" in recommendation.lower() or "yaml" in recommendation.lower()

    def test_concordance_factors_identified(self):
        from agent_evals.reports.cross_strategy_synthesis import (
            find_concordant_factors,
        )

        results = {
            "strategy_a": {"optimal_levels": {"axis_1": "yaml", "axis_2": "flat"}},
            "strategy_b": {
                "optimal_levels": {"axis_1": "yaml", "axis_2": "hierarchical"},
            },
            "strategy_c": {"optimal_levels": {"axis_1": "yaml", "axis_2": "flat"}},
        }
        concordant = find_concordant_factors(results)
        assert "axis_1" in concordant
        assert concordant["axis_1"]["level"] == "yaml"
        assert concordant["axis_1"]["agreement"] >= 0.66

    def test_disagreement_factors_identified(self):
        from agent_evals.reports.cross_strategy_synthesis import (
            find_disagreement_factors,
        )

        results = {
            "strategy_a": {"optimal_levels": {"axis_1": "yaml", "axis_2": "flat"}},
            "strategy_b": {
                "optimal_levels": {"axis_1": "json", "axis_2": "hierarchical"},
            },
            "strategy_c": {"optimal_levels": {"axis_1": "xml", "axis_2": "flat"}},
        }
        disagreements = find_disagreement_factors(results)
        assert "axis_1" in disagreements


class TestRankFormatRecommendations:
    def test_rank_format_recommendations(self):
        from agent_evals.reports.cross_strategy_synthesis import (
            rank_format_recommendations,
        )

        results = {
            "mcp_native": {
                "optimal_levels": {"axis_1": "yaml", "axis_11": "tool-desc-detailed"},
                "mean_score": 0.79,
            },
            "full_context": {
                "optimal_levels": {"axis_1": "yaml", "axis_2": "hierarchical"},
                "mean_score": 0.82,
            },
        }
        recs = rank_format_recommendations(results)
        assert "mcp_native" in recs
        assert isinstance(recs["mcp_native"], str)
        assert len(recs["mcp_native"]) > 0
        assert "full_context" in recs
        assert "yaml" in recs["mcp_native"]

    def test_format_optimal_combination(self):
        from agent_evals.reports.cross_strategy_synthesis import (
            format_optimal_combination,
        )

        result = format_optimal_combination(
            {"axis_1": "yaml", "axis_2": "hierarchical"},
        )
        assert "yaml (axis_1)" in result
        assert "hierarchical (axis_2)" in result

    def test_format_optimal_combination_empty(self):
        from agent_evals.reports.cross_strategy_synthesis import (
            format_optimal_combination,
        )

        result = format_optimal_combination({})
        assert "no recommendation" in result
