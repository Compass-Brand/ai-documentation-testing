"""Tests for the PoLL (Panel of LLM Evaluators) module."""

from __future__ import annotations

import pytest
from agent_evals.judge.calibrator import JudgeScore
from agent_evals.judge.poll import (
    DEFAULT_PANEL,
    ROUTINE_MODEL,
    PanelScore,
    PollConfig,
    PollResult,
    aggregate_panel_scores,
    build_poll_result,
    format_poll_report,
    identify_disagreements,
    validate_panel_correlation,
)

# ===================================================================
# Helpers
# ===================================================================


def _make_judge(
    example_id: str,
    score: float = 0.8,
    model: str = "openrouter/openai/gpt-4o-mini",
) -> JudgeScore:
    return JudgeScore(
        example_id=example_id,
        judge_model=model,
        score=score,
        rationale="Looks correct.",
        raw_response=f"RATIONALE: Looks correct.\nSCORE: {score}",
    )


def _make_panel_scores(
    example_ids: list[str],
    scores_by_model: dict[str, list[float]],
) -> dict[str, list[JudgeScore]]:
    """Build a judge_scores_by_model dict from model->scores mapping."""
    result: dict[str, list[JudgeScore]] = {}
    for model, scores in scores_by_model.items():
        result[model] = [
            _make_judge(eid, score, model)
            for eid, score in zip(example_ids, scores, strict=True)
        ]
    return result


# ===================================================================
# aggregate_panel_scores - mean
# ===================================================================


class TestAggregatePanelScoresMean:
    """Test aggregate_panel_scores with mean aggregation."""

    def test_three_models_mean(self) -> None:
        example_ids = ["ex_0", "ex_1", "ex_2"]
        by_model = _make_panel_scores(
            example_ids,
            {
                "model_a": [0.8, 0.6, 0.4],
                "model_b": [0.7, 0.5, 0.3],
                "model_c": [0.9, 0.7, 0.5],
            },
        )
        results = aggregate_panel_scores(by_model, aggregation="mean")

        assert len(results) == 3
        # ex_0: mean(0.8, 0.7, 0.9) = 0.8
        assert results[0].example_id == "ex_0"
        assert results[0].aggregated_score == pytest.approx(0.8)
        assert results[0].aggregation_method == "mean"
        # ex_1: mean(0.6, 0.5, 0.7) = 0.6
        assert results[1].aggregated_score == pytest.approx(0.6)
        # ex_2: mean(0.4, 0.3, 0.5) = 0.4
        assert results[2].aggregated_score == pytest.approx(0.4)

    def test_each_panel_score_has_three_judge_scores(self) -> None:
        example_ids = ["ex_0"]
        by_model = _make_panel_scores(
            example_ids,
            {
                "model_a": [0.8],
                "model_b": [0.7],
                "model_c": [0.9],
            },
        )
        results = aggregate_panel_scores(by_model)
        assert len(results[0].panel_scores) == 3

    def test_results_sorted_by_example_id(self) -> None:
        by_model = _make_panel_scores(
            ["z_ex", "a_ex", "m_ex"],
            {"model_a": [0.5, 0.6, 0.7]},
        )
        results = aggregate_panel_scores(by_model)
        ids = [ps.example_id for ps in results]
        assert ids == ["a_ex", "m_ex", "z_ex"]


# ===================================================================
# aggregate_panel_scores - median
# ===================================================================


class TestAggregatePanelScoresMedian:
    """Test aggregate_panel_scores with median aggregation."""

    def test_three_models_median(self) -> None:
        example_ids = ["ex_0", "ex_1"]
        by_model = _make_panel_scores(
            example_ids,
            {
                "model_a": [0.2, 0.9],
                "model_b": [0.5, 0.5],
                "model_c": [0.8, 0.1],
            },
        )
        results = aggregate_panel_scores(by_model, aggregation="median")

        # ex_0: median(0.2, 0.5, 0.8) = 0.5
        assert results[0].aggregated_score == pytest.approx(0.5)
        assert results[0].aggregation_method == "median"
        # ex_1: median(0.9, 0.5, 0.1) = 0.5
        assert results[1].aggregated_score == pytest.approx(0.5)

    def test_invalid_aggregation_raises(self) -> None:
        by_model = _make_panel_scores(["ex_0"], {"m": [0.5]})
        with pytest.raises(ValueError, match="Unsupported aggregation"):
            aggregate_panel_scores(by_model, aggregation="max")


# ===================================================================
# score_spread
# ===================================================================


class TestScoreSpread:
    """Test that score_spread is correctly computed (max - min)."""

    def test_spread_computed_correctly(self) -> None:
        by_model = _make_panel_scores(
            ["ex_0"],
            {
                "model_a": [0.3],
                "model_b": [0.7],
                "model_c": [0.5],
            },
        )
        results = aggregate_panel_scores(by_model)
        # spread = 0.7 - 0.3 = 0.4
        assert results[0].score_spread == pytest.approx(0.4)

    def test_zero_spread_when_unanimous(self) -> None:
        by_model = _make_panel_scores(
            ["ex_0"],
            {
                "model_a": [0.5],
                "model_b": [0.5],
                "model_c": [0.5],
            },
        )
        results = aggregate_panel_scores(by_model)
        assert results[0].score_spread == pytest.approx(0.0)

    def test_large_spread(self) -> None:
        by_model = _make_panel_scores(
            ["ex_0"],
            {
                "model_a": [0.0],
                "model_b": [1.0],
            },
        )
        results = aggregate_panel_scores(by_model)
        assert results[0].score_spread == pytest.approx(1.0)


# ===================================================================
# aggregate handles missing examples
# ===================================================================


class TestAggregatePartialCoverage:
    """Test aggregate when not all models scored every example."""

    def test_missing_examples_still_aggregated(self) -> None:
        """Models that don't score an example are simply absent."""
        by_model: dict[str, list[JudgeScore]] = {
            "model_a": [
                _make_judge("ex_0", 0.8, "model_a"),
                _make_judge("ex_1", 0.6, "model_a"),
            ],
            "model_b": [
                _make_judge("ex_0", 0.7, "model_b"),
                # model_b did NOT score ex_1
            ],
            "model_c": [
                _make_judge("ex_0", 0.9, "model_c"),
                _make_judge("ex_1", 0.5, "model_c"),
            ],
        }
        results = aggregate_panel_scores(by_model)

        assert len(results) == 2

        # ex_0: scored by all 3 models
        ex0 = results[0]
        assert ex0.example_id == "ex_0"
        assert len(ex0.panel_scores) == 3
        assert ex0.aggregated_score == pytest.approx(0.8)

        # ex_1: scored by only 2 models
        ex1 = results[1]
        assert ex1.example_id == "ex_1"
        assert len(ex1.panel_scores) == 2
        assert ex1.aggregated_score == pytest.approx(0.55)  # mean(0.6, 0.5)


# ===================================================================
# validate_panel_correlation
# ===================================================================


class TestValidatePanelCorrelation:
    """Tests for validate_panel_correlation."""

    def test_correlated_scores_pass(self) -> None:
        """Perfectly correlated panel and routine scores should pass."""
        example_ids = [f"ex_{i}" for i in range(10)]
        poll_values = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        routine_values = [0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95, 1.0]

        panel_scores = [
            PanelScore(
                example_id=eid,
                panel_scores=[],
                aggregated_score=val,
                score_spread=0.0,
            )
            for eid, val in zip(example_ids, poll_values, strict=True)
        ]
        routine_scores = [
            _make_judge(eid, val, ROUTINE_MODEL)
            for eid, val in zip(example_ids, routine_values, strict=True)
        ]

        correlation, passed = validate_panel_correlation(panel_scores, routine_scores)
        assert correlation >= 0.80
        assert passed is True

    def test_uncorrelated_scores_fail(self) -> None:
        """Reversed scores should fail correlation check."""
        example_ids = [f"ex_{i}" for i in range(10)]
        poll_values = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        routine_values = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]

        panel_scores = [
            PanelScore(
                example_id=eid,
                panel_scores=[],
                aggregated_score=val,
                score_spread=0.0,
            )
            for eid, val in zip(example_ids, poll_values, strict=True)
        ]
        routine_scores = [
            _make_judge(eid, val, ROUTINE_MODEL)
            for eid, val in zip(example_ids, routine_values, strict=True)
        ]

        correlation, passed = validate_panel_correlation(panel_scores, routine_scores)
        assert correlation < 0.80
        assert passed is False

    def test_no_overlapping_examples_returns_zero(self) -> None:
        panel_scores = [
            PanelScore(
                example_id="poll_0",
                panel_scores=[],
                aggregated_score=0.5,
                score_spread=0.0,
            )
        ]
        routine_scores = [_make_judge("routine_0", 0.5)]

        correlation, passed = validate_panel_correlation(panel_scores, routine_scores)
        assert correlation == 0.0
        assert passed is False

    def test_custom_threshold(self) -> None:
        """With a low threshold, moderate correlation passes."""
        example_ids = [f"ex_{i}" for i in range(5)]
        poll_values = [0.1, 0.3, 0.5, 0.7, 0.9]
        # Somewhat noisy but still monotonic
        routine_values = [0.2, 0.25, 0.6, 0.55, 0.85]

        panel_scores = [
            PanelScore(
                example_id=eid,
                panel_scores=[],
                aggregated_score=val,
                score_spread=0.0,
            )
            for eid, val in zip(example_ids, poll_values, strict=True)
        ]
        routine_scores = [
            _make_judge(eid, val, ROUTINE_MODEL)
            for eid, val in zip(example_ids, routine_values, strict=True)
        ]

        correlation, passed = validate_panel_correlation(
            panel_scores, routine_scores, threshold=0.50
        )
        assert passed is True


# ===================================================================
# build_poll_result
# ===================================================================


class TestBuildPollResult:
    """Tests for build_poll_result."""

    def test_full_pipeline(self) -> None:
        """End-to-end: panel scores + routine correlation."""
        example_ids = [f"ex_{i}" for i in range(5)]
        by_model = _make_panel_scores(
            example_ids,
            {
                "model_a": [0.1, 0.3, 0.5, 0.7, 0.9],
                "model_b": [0.15, 0.35, 0.55, 0.75, 0.95],
                "model_c": [0.12, 0.32, 0.48, 0.72, 0.88],
            },
        )
        routine_scores = [
            _make_judge(eid, val, ROUTINE_MODEL)
            for eid, val in zip(
                example_ids,
                [0.1, 0.3, 0.5, 0.7, 0.9],
                strict=True,
            )
        ]

        result = build_poll_result(by_model, routine_scores=routine_scores)

        assert isinstance(result, PollResult)
        assert len(result.scores) == 5
        assert result.correlation_with_routine is not None
        assert result.correlation_with_routine >= 0.80
        assert result.correlation_passed is True

    def test_without_routine_scores(self) -> None:
        """When no routine scores, correlation is None."""
        example_ids = ["ex_0", "ex_1"]
        by_model = _make_panel_scores(
            example_ids,
            {
                "model_a": [0.5, 0.6],
                "model_b": [0.4, 0.7],
            },
        )

        result = build_poll_result(by_model)

        assert isinstance(result, PollResult)
        assert len(result.scores) == 2
        assert result.correlation_with_routine is None
        assert result.correlation_passed is False

    def test_uses_config_aggregation(self) -> None:
        example_ids = ["ex_0"]
        by_model = _make_panel_scores(
            example_ids,
            {
                "model_a": [0.2],
                "model_b": [0.5],
                "model_c": [0.8],
            },
        )
        config = PollConfig(aggregation="median")
        result = build_poll_result(by_model, config=config)
        # median(0.2, 0.5, 0.8) = 0.5
        assert result.scores[0].aggregated_score == pytest.approx(0.5)
        assert result.scores[0].aggregation_method == "median"

    def test_panel_models_from_config(self) -> None:
        by_model = _make_panel_scores(["ex_0"], {"m": [0.5]})
        custom_models = ["model_x", "model_y"]
        config = PollConfig(panel_models=custom_models)
        result = build_poll_result(by_model, config=config)
        assert result.panel_models == custom_models


# ===================================================================
# identify_disagreements
# ===================================================================


class TestIdentifyDisagreements:
    """Tests for identify_disagreements."""

    def test_finds_high_spread_examples(self) -> None:
        scores = [
            PanelScore(
                example_id="ex_0",
                panel_scores=[],
                aggregated_score=0.5,
                score_spread=0.5,  # high spread
            ),
            PanelScore(
                example_id="ex_1",
                panel_scores=[],
                aggregated_score=0.7,
                score_spread=0.1,  # low spread
            ),
            PanelScore(
                example_id="ex_2",
                panel_scores=[],
                aggregated_score=0.6,
                score_spread=0.4,  # high spread
            ),
        ]
        disagreements = identify_disagreements(scores, spread_threshold=0.3)
        assert len(disagreements) == 2
        ids = [d.example_id for d in disagreements]
        assert "ex_0" in ids
        assert "ex_2" in ids

    def test_low_spread_returns_empty(self) -> None:
        scores = [
            PanelScore(
                example_id="ex_0",
                panel_scores=[],
                aggregated_score=0.5,
                score_spread=0.05,
            ),
            PanelScore(
                example_id="ex_1",
                panel_scores=[],
                aggregated_score=0.7,
                score_spread=0.1,
            ),
        ]
        disagreements = identify_disagreements(scores, spread_threshold=0.3)
        assert disagreements == []

    def test_exact_threshold_not_included(self) -> None:
        """Spread exactly at threshold should NOT be flagged (> not >=)."""
        scores = [
            PanelScore(
                example_id="ex_0",
                panel_scores=[],
                aggregated_score=0.5,
                score_spread=0.3,  # exactly at threshold
            ),
        ]
        disagreements = identify_disagreements(scores, spread_threshold=0.3)
        assert disagreements == []

    def test_empty_input(self) -> None:
        disagreements = identify_disagreements([])
        assert disagreements == []


# ===================================================================
# format_poll_report
# ===================================================================


class TestFormatPollReport:
    """Tests for format_poll_report."""

    def test_contains_key_sections(self) -> None:
        example_ids = ["ex_0", "ex_1"]
        by_model = _make_panel_scores(
            example_ids,
            {
                "model_a": [0.8, 0.6],
                "model_b": [0.7, 0.5],
                "model_c": [0.9, 0.7],
            },
        )
        routine_scores = [
            _make_judge("ex_0", 0.8, ROUTINE_MODEL),
            _make_judge("ex_1", 0.6, ROUTINE_MODEL),
        ]
        result = build_poll_result(by_model, routine_scores=routine_scores)
        report = format_poll_report(result)

        assert "PoLL" in report
        assert "Panel Models" in report
        assert "Total Examples: 2" in report
        assert "Per-Model Statistics" in report
        assert "Aggregated Score" in report
        assert "Correlation with Routine Model" in report
        assert "Spearman" in report
        assert "Disagreements" in report

    def test_report_without_correlation(self) -> None:
        by_model = _make_panel_scores(["ex_0"], {"model_a": [0.5]})
        result = build_poll_result(by_model)
        report = format_poll_report(result)

        assert "Not computed" in report

    def test_report_is_string(self) -> None:
        result = PollResult(panel_models=["m"], scores=[], correlation_passed=False)
        report = format_poll_report(result)
        assert isinstance(report, str)


# ===================================================================
# DEFAULT_PANEL constant
# ===================================================================


class TestDefaultPanel:
    """Tests for DEFAULT_PANEL constant."""

    def test_has_exactly_three_models(self) -> None:
        assert len(DEFAULT_PANEL) == 3

    def test_contains_expected_providers(self) -> None:
        providers = [m.split("/")[1] for m in DEFAULT_PANEL]
        assert "openai" in providers
        assert "anthropic" in providers
        assert "google" in providers

    def test_all_use_openrouter(self) -> None:
        for model in DEFAULT_PANEL:
            assert model.startswith("openrouter/")


# ===================================================================
# PollConfig defaults
# ===================================================================


class TestPollConfigDefaults:
    """Tests for PollConfig default values."""

    def test_default_panel_models(self) -> None:
        config = PollConfig()
        assert config.panel_models == DEFAULT_PANEL

    def test_default_routine_model(self) -> None:
        config = PollConfig()
        assert config.routine_model == ROUTINE_MODEL

    def test_default_aggregation(self) -> None:
        config = PollConfig()
        assert config.aggregation == "mean"

    def test_default_correlation_threshold(self) -> None:
        config = PollConfig()
        assert config.correlation_threshold == pytest.approx(0.80)

    def test_panel_models_is_independent_copy(self) -> None:
        """Mutating config.panel_models should not affect DEFAULT_PANEL."""
        config = PollConfig()
        config.panel_models.append("extra_model")
        assert len(DEFAULT_PANEL) == 3


# ===================================================================
# Single-model panel (edge case)
# ===================================================================


class TestSingleModelPanel:
    """Edge case: panel with a single model."""

    def test_single_model_aggregation(self) -> None:
        by_model = _make_panel_scores(
            ["ex_0", "ex_1"],
            {"solo_model": [0.6, 0.8]},
        )
        results = aggregate_panel_scores(by_model)

        assert len(results) == 2
        assert results[0].aggregated_score == pytest.approx(0.6)
        assert results[1].aggregated_score == pytest.approx(0.8)
        # With one model, spread is always 0
        assert results[0].score_spread == pytest.approx(0.0)
        assert results[1].score_spread == pytest.approx(0.0)

    def test_single_model_poll_result(self) -> None:
        by_model = _make_panel_scores(
            ["ex_0"],
            {"solo_model": [0.5]},
        )
        config = PollConfig(panel_models=["solo_model"])
        result = build_poll_result(by_model, config=config)
        assert len(result.scores) == 1
        assert result.panel_models == ["solo_model"]
