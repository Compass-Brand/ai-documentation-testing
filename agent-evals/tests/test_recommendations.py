"""Tests for plain-language recommendation generation."""

from __future__ import annotations

import pytest

from agent_evals.reports.recommendations import (
    Finding,
    StrategyBreakdown,
    extract_strategy_breakdowns,
    generate_findings,
    render_anova_table,
    render_findings_text,
)


class TestGenerateFindings:
    def test_generates_finding_per_significant_factor(self):
        """One Finding object per factor with p < alpha."""
        anova_results = {
            "axis_1_structure": {"p_value": 0.001, "significant": True},
            "axis_2_metadata": {"p_value": 0.02, "significant": True},
            "axis_3_format": {"p_value": 0.5, "significant": False},
        }
        main_effects = {
            "axis_1_structure": {
                "flat": 65.0, "2-tier": 82.0, "3-tier": 78.0,
            },
            "axis_2_metadata": {
                "path-only": 70.0, "with-summary": 80.0,
            },
            "axis_3_format": {
                "markdown": 75.0, "yaml": 74.0,
            },
        }
        findings = generate_findings(anova_results, main_effects)
        assert len(findings) == 2
        assert findings[0].factor_name == "axis_1_structure"
        assert findings[0].best_level == "2-tier"
        assert findings[0].worst_level == "flat"

    def test_finding_includes_effect_size(self):
        anova_results = {
            "axis_1_structure": {"p_value": 0.001, "significant": True},
        }
        main_effects = {
            "axis_1_structure": {"flat": 65.0, "2-tier": 82.0},
        }
        findings = generate_findings(anova_results, main_effects)
        assert findings[0].effect_size == pytest.approx(17.0)

    def test_no_significant_factors_returns_empty(self):
        anova_results = {
            "axis_1": {"p_value": 0.5, "significant": False},
        }
        main_effects = {"axis_1": {"flat": 75.0, "2-tier": 76.0}}
        findings = generate_findings(anova_results, main_effects)
        assert len(findings) == 0

    def test_findings_sorted_by_effect_size_descending(self):
        anova_results = {
            "axis_1": {"p_value": 0.01, "significant": True},
            "axis_2": {"p_value": 0.01, "significant": True},
        }
        main_effects = {
            "axis_1": {"a": 70.0, "b": 75.0},  # effect=5
            "axis_2": {"a": 60.0, "b": 80.0},  # effect=20
        }
        findings = generate_findings(anova_results, main_effects)
        assert findings[0].effect_size > findings[1].effect_size

    def test_missing_main_effects_skipped(self):
        anova_results = {
            "axis_1": {"p_value": 0.01, "significant": True},
        }
        main_effects = {}  # No effects for axis_1
        findings = generate_findings(anova_results, main_effects)
        assert len(findings) == 0


class TestRenderFindingsText:
    def test_renders_human_readable_output(self):
        findings = [
            Finding(
                factor_name="axis_1_structure",
                best_level="2-tier",
                worst_level="flat",
                effect_size=17.0,
                p_value=0.001,
                confidence_interval=(12.0, 22.0),
                strategy_breakdowns=[],
            ),
        ]
        text = render_findings_text(findings)
        assert "2-tier" in text
        assert "flat" in text
        assert "17.0" in text

    def test_includes_strategy_breakdown_when_present(self):
        findings = [
            Finding(
                factor_name="axis_1_structure",
                best_level="2-tier",
                worst_level="flat",
                effect_size=17.0,
                p_value=0.001,
                confidence_interval=(12.0, 22.0),
                strategy_breakdowns=[
                    StrategyBreakdown("full_context", "2-tier", 14.1),
                    StrategyBreakdown("rag", "3-tier", 9.2),
                ],
            ),
        ]
        text = render_findings_text(findings)
        assert "full_context" in text
        assert "rag" in text
        assert "3-tier" in text  # RAG disagrees

    def test_no_findings_returns_message(self):
        text = render_findings_text([])
        assert "No statistically significant findings" in text

    def test_confidence_interval_rendered(self):
        findings = [
            Finding(
                factor_name="axis_1",
                best_level="b",
                worst_level="a",
                effect_size=10.0,
                p_value=0.01,
                confidence_interval=(5.0, 15.0),
                strategy_breakdowns=[],
            ),
        ]
        text = render_findings_text(findings)
        assert "5.0" in text
        assert "15.0" in text

    def test_strategy_agreement_indicated(self):
        findings = [
            Finding(
                factor_name="axis_1",
                best_level="b",
                worst_level="a",
                effect_size=10.0,
                p_value=0.01,
                strategy_breakdowns=[
                    StrategyBreakdown("s1", "b", 10.0),
                    StrategyBreakdown("s2", "b", 8.0),
                ],
            ),
        ]
        text = render_findings_text(findings)
        assert "yes" in text.lower()  # strategies agree


class TestRenderAnovaTable:
    def test_anova_table_format(self):
        anova_results = {
            "axis_1_structure": {
                "sum_of_squares": 1250.5,
                "df": 2,
                "mean_square": 625.25,
                "f_statistic": 14.32,
                "p_value": 0.001,
                "significant": True,
            },
            "axis_2_metadata": {
                "sum_of_squares": 82.3,
                "df": 1,
                "mean_square": 82.3,
                "f_statistic": 1.88,
                "p_value": 0.18,
                "significant": False,
            },
        }
        table = render_anova_table(anova_results)

        # Required columns
        assert "Factor" in table
        assert "Sum of Squares" in table
        assert "df" in table
        assert "Mean Square" in table
        assert "F-statistic" in table
        assert "p-value" in table
        assert "Significant" in table

        assert "axis_1_structure" in table
        assert "Yes" in table
        assert "No" in table
        assert "1250.5" in table or "1250.50" in table
        assert "Benjamini-Hochberg" in table


class TestExtractStrategyBreakdowns:
    def test_per_strategy_breakdown_from_taguchi(self):
        strategy_phase_results = {
            "full_context": {
                "main_effects": {
                    "axis_1_structure": {
                        "flat": 60.0, "2-tier": 80.0, "3-tier": 75.0,
                    },
                },
            },
            "rag": {
                "main_effects": {
                    "axis_1_structure": {
                        "flat": 55.0, "2-tier": 70.0, "3-tier": 78.0,
                    },
                },
            },
        }

        breakdowns = extract_strategy_breakdowns(
            strategy_phase_results, factor="axis_1_structure"
        )
        assert len(breakdowns) == 2

        fc_bd = next(b for b in breakdowns if b.strategy == "full_context")
        assert fc_bd.best_level == "2-tier"
        assert fc_bd.effect_size == pytest.approx(20.0)  # 80 - 60

        rag_bd = next(b for b in breakdowns if b.strategy == "rag")
        assert rag_bd.best_level == "3-tier"  # RAG disagrees!
        assert rag_bd.effect_size == pytest.approx(23.0)  # 78 - 55

    def test_missing_factor_returns_empty(self):
        strategy_phase_results = {
            "full_context": {
                "main_effects": {
                    "axis_2": {"a": 50.0, "b": 60.0},
                },
            },
        }
        breakdowns = extract_strategy_breakdowns(
            strategy_phase_results, factor="axis_1"
        )
        assert len(breakdowns) == 0

    def test_four_strategies(self):
        strategy_phase_results = {
            "full_context": {
                "main_effects": {
                    "axis_1": {"flat": 58.0, "2-tier": 82.0, "3-tier": 74.0},
                },
            },
            "system_prompt": {
                "main_effects": {
                    "axis_1": {"flat": 55.0, "2-tier": 79.0, "3-tier": 76.0},
                },
            },
            "rag": {
                "main_effects": {
                    "axis_1": {"flat": 52.0, "2-tier": 71.0, "3-tier": 80.0},
                },
            },
            "tool_based": {
                "main_effects": {
                    "axis_1": {"flat": 60.0, "2-tier": 83.0, "3-tier": 77.0},
                },
            },
        }
        breakdowns = extract_strategy_breakdowns(
            strategy_phase_results, factor="axis_1"
        )
        assert len(breakdowns) == 4
        best_levels = {b.strategy: b.best_level for b in breakdowns}
        assert best_levels["full_context"] == "2-tier"
        assert best_levels["rag"] == "3-tier"  # RAG disagrees


class TestMultiStrategyIntegration:
    def test_recommendations_consume_multistrategy_results(self):
        """Verify generate_findings + extract_strategy_breakdowns +
        Kendall's W work together end-to-end."""
        from agent_evals.reports.statistics import kendalls_w

        strategy_phase_results = {
            "full_context": {
                "main_effects": {
                    "axis_1_structure": {
                        "flat": 58.0, "2-tier": 82.0, "3-tier": 74.0,
                    },
                },
            },
            "system_prompt": {
                "main_effects": {
                    "axis_1_structure": {
                        "flat": 55.0, "2-tier": 79.0, "3-tier": 76.0,
                    },
                },
            },
            "rag": {
                "main_effects": {
                    "axis_1_structure": {
                        "flat": 52.0, "2-tier": 71.0, "3-tier": 80.0,
                    },
                },
            },
            "tool_based": {
                "main_effects": {
                    "axis_1_structure": {
                        "flat": 60.0, "2-tier": 83.0, "3-tier": 77.0,
                    },
                },
            },
        }

        # Extract breakdowns
        breakdowns = extract_strategy_breakdowns(
            strategy_phase_results, factor="axis_1_structure"
        )
        assert len(breakdowns) == 4

        # Generate findings
        aggregate_anova = {
            "axis_1_structure": {"p_value": 0.002, "significant": True},
        }
        aggregate_effects = strategy_phase_results["full_context"]["main_effects"]
        findings = generate_findings(aggregate_anova, aggregate_effects)
        assert len(findings) == 1

        # Render text
        text = render_findings_text(findings)
        assert len(text) > 0

        # Kendall's W for cross-strategy concordance
        levels = ["flat", "2-tier", "3-tier"]
        rankings = []
        for strategy in ["full_context", "system_prompt", "rag", "tool_based"]:
            effects = strategy_phase_results[strategy]["main_effects"][
                "axis_1_structure"
            ]
            sorted_levels = sorted(levels, key=lambda lv: effects[lv])
            ranks = [sorted_levels.index(lv) + 1 for lv in levels]
            rankings.append(ranks)

        w = kendalls_w(rankings)
        assert 0.0 <= w <= 1.0
        # 3 of 4 strategies agree on "2-tier" as best => moderate concordance
        assert w > 0.5
