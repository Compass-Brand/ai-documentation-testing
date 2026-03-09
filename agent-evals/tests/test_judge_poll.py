"""Tests for Panel of LLM evaluators (PoLL)."""

from __future__ import annotations

import pytest

from agent_evals.judge.calibrator import JudgeScore
from agent_evals.judge.poll import (
    PanelScore,
    PollConfig,
    PollResult,
    aggregate_panel_scores,
    build_poll_result,
    format_poll_report,
    identify_disagreements,
    validate_panel_correlation,
)


class TestAggregatePanelScores:
    def test_mean_aggregation(self):
        scores = {
            "model_a": [JudgeScore("ex_0", "model_a", 0.8, "", "")],
            "model_b": [JudgeScore("ex_0", "model_b", 0.6, "", "")],
        }
        result = aggregate_panel_scores(scores, aggregation="mean")
        assert len(result) == 1
        assert abs(result[0].aggregated_score - 0.7) < 0.001

    def test_median_aggregation(self):
        scores = {
            "model_a": [JudgeScore("ex_0", "model_a", 0.8, "", "")],
            "model_b": [JudgeScore("ex_0", "model_b", 0.6, "", "")],
            "model_c": [JudgeScore("ex_0", "model_c", 0.9, "", "")],
        }
        result = aggregate_panel_scores(scores, aggregation="median")
        assert abs(result[0].aggregated_score - 0.8) < 0.001

    def test_spread_calculation(self):
        scores = {
            "model_a": [JudgeScore("ex_0", "model_a", 0.3, "", "")],
            "model_b": [JudgeScore("ex_0", "model_b", 0.9, "", "")],
        }
        result = aggregate_panel_scores(scores)
        assert abs(result[0].score_spread - 0.6) < 0.001

    def test_invalid_aggregation_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            aggregate_panel_scores({}, aggregation="invalid")

    def test_multiple_examples(self):
        """Multiple examples are each aggregated independently."""
        scores = {
            "model_a": [
                JudgeScore("ex_0", "model_a", 0.8, "", ""),
                JudgeScore("ex_1", "model_a", 0.4, "", ""),
            ],
            "model_b": [
                JudgeScore("ex_0", "model_b", 0.6, "", ""),
                JudgeScore("ex_1", "model_b", 0.2, "", ""),
            ],
        }
        result = aggregate_panel_scores(scores)
        assert len(result) == 2
        assert abs(result[0].aggregated_score - 0.7) < 0.001  # ex_0
        assert abs(result[1].aggregated_score - 0.3) < 0.001  # ex_1


class TestValidatePanelCorrelation:
    def test_perfect_correlation_passes(self):
        poll = [
            PanelScore("ex_0", [], 0.2, 0.0),
            PanelScore("ex_1", [], 0.5, 0.0),
            PanelScore("ex_2", [], 0.8, 0.0),
        ]
        routine = [
            JudgeScore("ex_0", "routine", 0.2, "", ""),
            JudgeScore("ex_1", "routine", 0.5, "", ""),
            JudgeScore("ex_2", "routine", 0.8, "", ""),
        ]
        corr, passed = validate_panel_correlation(poll, routine)
        assert passed is True
        assert corr > 0.99

    def test_no_overlap_fails(self):
        poll = [PanelScore("ex_0", [], 0.5, 0.0)]
        routine = [JudgeScore("ex_999", "routine", 0.5, "", "")]
        corr, passed = validate_panel_correlation(poll, routine)
        assert passed is False

    def test_custom_threshold(self):
        """Lower threshold makes marginal correlation pass."""
        poll = [
            PanelScore("ex_0", [], 0.2, 0.0),
            PanelScore("ex_1", [], 0.5, 0.0),
            PanelScore("ex_2", [], 0.8, 0.0),
        ]
        routine = [
            JudgeScore("ex_0", "routine", 0.3, "", ""),
            JudgeScore("ex_1", "routine", 0.4, "", ""),
            JudgeScore("ex_2", "routine", 0.9, "", ""),
        ]
        corr, passed = validate_panel_correlation(poll, routine, threshold=0.5)
        assert passed is True


class TestIdentifyDisagreements:
    def test_finds_high_spread(self):
        scores = [
            PanelScore("ex_0", [], 0.5, 0.1),  # Low spread
            PanelScore("ex_1", [], 0.5, 0.5),  # High spread
        ]
        result = identify_disagreements(scores, spread_threshold=0.3)
        assert len(result) == 1
        assert result[0].example_id == "ex_1"

    def test_no_disagreements(self):
        scores = [
            PanelScore("ex_0", [], 0.5, 0.1),
            PanelScore("ex_1", [], 0.7, 0.05),
        ]
        result = identify_disagreements(scores, spread_threshold=0.3)
        assert len(result) == 0


class TestBuildPollResult:
    def test_builds_result_without_routine(self):
        scores = {
            "model_a": [JudgeScore("ex_0", "model_a", 0.8, "", "")],
        }
        result = build_poll_result(scores)
        assert len(result.scores) == 1
        assert result.correlation_with_routine is None

    def test_builds_result_with_routine(self):
        scores = {
            "model_a": [
                JudgeScore("ex_0", "model_a", 0.2, "", ""),
                JudgeScore("ex_1", "model_a", 0.8, "", ""),
            ],
        }
        routine = [
            JudgeScore("ex_0", "routine", 0.2, "", ""),
            JudgeScore("ex_1", "routine", 0.8, "", ""),
        ]
        result = build_poll_result(scores, routine_scores=routine)
        assert result.correlation_with_routine is not None

    def test_builds_result_with_config(self):
        config = PollConfig(aggregation="median")
        scores = {
            "model_a": [JudgeScore("ex_0", "model_a", 0.8, "", "")],
            "model_b": [JudgeScore("ex_0", "model_b", 0.6, "", "")],
            "model_c": [JudgeScore("ex_0", "model_c", 0.9, "", "")],
        }
        result = build_poll_result(scores, config=config)
        assert abs(result.scores[0].aggregated_score - 0.8) < 0.001


class TestFormatPollReport:
    def test_report_contains_panel_models(self):
        result = PollResult(
            panel_models=["model_a", "model_b"],
            scores=[],
        )
        report = format_poll_report(result)
        assert "model_a" in report
        assert "model_b" in report

    def test_report_contains_score_summary(self):
        result = PollResult(
            panel_models=["model_a"],
            scores=[
                PanelScore(
                    "ex_0",
                    [JudgeScore("ex_0", "model_a", 0.85, "", "")],
                    0.85,
                    0.0,
                ),
            ],
        )
        report = format_poll_report(result)
        assert "0.85" in report

    def test_report_correlation_section(self):
        result = PollResult(
            panel_models=["model_a"],
            scores=[],
            correlation_with_routine=0.92,
            correlation_passed=True,
        )
        report = format_poll_report(result)
        assert "0.92" in report
        assert "PASSED" in report

    def test_report_disagreements_section(self):
        result = PollResult(
            panel_models=["model_a", "model_b"],
            scores=[
                PanelScore(
                    "ex_0",
                    [
                        JudgeScore("ex_0", "model_a", 0.2, "", ""),
                        JudgeScore("ex_0", "model_b", 0.9, "", ""),
                    ],
                    0.55,
                    0.7,  # High spread
                ),
            ],
        )
        report = format_poll_report(result)
        assert "Disagreements" in report
        assert "ex_0" in report


class TestPollConfig:
    def test_default_config(self):
        config = PollConfig()
        assert len(config.panel_models) == 3
        assert config.aggregation == "mean"
        assert config.correlation_threshold == 0.80

    def test_custom_config(self):
        config = PollConfig(
            panel_models=["model_x", "model_y"],
            aggregation="median",
            correlation_threshold=0.90,
        )
        assert config.panel_models == ["model_x", "model_y"]
        assert config.aggregation == "median"
