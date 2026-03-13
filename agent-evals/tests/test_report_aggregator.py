"""Tests for Report Data Aggregator."""

from __future__ import annotations

import statistics

import pytest
from agent_evals.reports.aggregator import (
    ReportData,
    aggregate,
)
from agent_evals.runner import EvalRunConfig, TrialResult
from scipy.stats import t as t_dist

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _trial(
    *,
    task_id: str = "task_1",
    task_type: str = "retrieval",
    variant_name: str = "flat",
    repetition: int = 1,
    score: float = 0.85,
    cost: float | None = 0.01,
    latency_seconds: float = 1.5,
    source: str = "gold_standard",
) -> TrialResult:
    return TrialResult(
        task_id=task_id,
        task_type=task_type,
        variant_name=variant_name,
        repetition=repetition,
        score=score,
        metrics={},
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost=cost,
        latency_seconds=latency_seconds,
        response="",
        cached=False,
        source=source,
    )


def _config() -> EvalRunConfig:
    return EvalRunConfig()


# ---------------------------------------------------------------------------
# TestByVariant
# ---------------------------------------------------------------------------


class TestByVariant:
    """Aggregates per-variant scores."""

    def test_groups_by_variant_name(self) -> None:
        trials = [
            _trial(variant_name="flat", score=0.8),
            _trial(variant_name="flat", score=0.9),
            _trial(variant_name="3tier", score=0.7),
        ]
        report = aggregate(trials, config=_config())
        assert len(report.by_variant) == 2
        assert "flat" in report.by_variant
        assert "3tier" in report.by_variant

    def test_computes_mean_score(self) -> None:
        trials = [
            _trial(variant_name="flat", score=0.8),
            _trial(variant_name="flat", score=0.9),
        ]
        report = aggregate(trials, config=_config())
        assert report.by_variant["flat"].mean_score == pytest.approx(0.85)

    def test_computes_trial_count(self) -> None:
        trials = [
            _trial(variant_name="flat", score=0.8),
            _trial(variant_name="flat", score=0.9),
            _trial(variant_name="flat", score=0.7),
        ]
        report = aggregate(trials, config=_config())
        assert report.by_variant["flat"].count == 3


# ---------------------------------------------------------------------------
# TestByTaskType
# ---------------------------------------------------------------------------


class TestByTaskType:
    """Aggregates per-task-type scores."""

    def test_groups_by_task_type(self) -> None:
        trials = [
            _trial(task_type="retrieval", score=0.8),
            _trial(task_type="code_gen", score=0.7),
            _trial(task_type="retrieval", score=0.9),
        ]
        report = aggregate(trials, config=_config())
        assert len(report.by_task_type) == 2
        assert "retrieval" in report.by_task_type
        assert "code_gen" in report.by_task_type

    def test_computes_mean_per_type(self) -> None:
        trials = [
            _trial(task_type="retrieval", score=0.8),
            _trial(task_type="retrieval", score=0.9),
        ]
        report = aggregate(trials, config=_config())
        assert report.by_task_type["retrieval"].mean_score == pytest.approx(
            0.85
        )


# ---------------------------------------------------------------------------
# TestBySource
# ---------------------------------------------------------------------------


class TestBySource:
    """Aggregates per-source scores."""

    def test_groups_by_source(self) -> None:
        trials = [
            _trial(source="gold_standard", score=0.8),
            _trial(source="repliqa", score=0.7),
        ]
        report = aggregate(trials, config=_config())
        assert len(report.by_source) == 2
        assert "gold_standard" in report.by_source
        assert "repliqa" in report.by_source

    def test_computes_mean_per_source(self) -> None:
        trials = [
            _trial(source="repliqa", score=0.6),
            _trial(source="repliqa", score=0.8),
        ]
        report = aggregate(trials, config=_config())
        assert report.by_source["repliqa"].mean_score == pytest.approx(0.7)

    def test_single_source_produces_one_entry(self) -> None:
        trials = [_trial(), _trial(), _trial()]
        report = aggregate(trials, config=_config())
        assert len(report.by_source) == 1


# ---------------------------------------------------------------------------
# TestModelVersions
# ---------------------------------------------------------------------------


class TestModelVersions:
    """Captures model version mapping."""

    def test_stores_model_versions(self) -> None:
        versions = {"claude-sonnet-4.5": "claude-3-5-sonnet-20241022"}
        report = aggregate(
            [_trial()], config=_config(), model_versions=versions
        )
        assert report.model_versions == versions

    def test_empty_model_versions_default(self) -> None:
        report = aggregate([_trial()], config=_config())
        assert report.model_versions == {}


# ---------------------------------------------------------------------------
# TestReproducibility
# ---------------------------------------------------------------------------


class TestReproducibility:
    """Captures reproducibility metadata."""

    def test_config_dump_preserved(self) -> None:
        cfg = _config()
        report = aggregate([_trial()], config=cfg)
        assert report.config is cfg

    def test_total_trials_count(self) -> None:
        trials = [_trial() for _ in range(10)]
        report = aggregate(trials, config=_config())
        assert report.total_trials == 10

    def test_total_cost(self) -> None:
        trials = [_trial(cost=0.01) for _ in range(5)]
        report = aggregate(trials, config=_config())
        assert report.total_cost == pytest.approx(0.05)

    def test_total_cost_handles_none(self) -> None:
        trials = [_trial(cost=0.01), _trial(cost=None)]
        report = aggregate(trials, config=_config())
        assert report.total_cost == pytest.approx(0.01)


# ---------------------------------------------------------------------------
# TestEmptyInput
# ---------------------------------------------------------------------------


class TestPhaseResults:
    """Phase results from DOE pipeline phases."""

    def test_phase_results_default_none(self) -> None:
        report = aggregate([_trial()], config=_config())
        assert report.phase_results is None

    def test_phase_results_passed_through(self) -> None:
        phase_data = {
            "screening": {
                "significant_factors": ["structure", "transform"],
                "main_effects": {"structure": {"flat": 0.7, "nested": 0.9}},
            },
        }
        report = aggregate(
            [_trial()], config=_config(), phase_results=phase_data
        )
        assert report.phase_results is not None
        assert "screening" in report.phase_results
        assert report.phase_results["screening"]["significant_factors"] == [
            "structure",
            "transform",
        ]

    def test_phase_results_with_confirmation(self) -> None:
        phase_data = {
            "screening": {"significant_factors": ["structure"]},
            "confirmation": {
                "within_interval": True,
                "sigma_deviation": 0.3,
            },
        }
        report = aggregate(
            [_trial()], config=_config(), phase_results=phase_data
        )
        assert report.phase_results["confirmation"]["within_interval"] is True


# ---------------------------------------------------------------------------
# TestEmptyInput
# ---------------------------------------------------------------------------


class TestEmptyInput:
    """Edge cases with no trials."""

    def test_empty_trials_produces_empty_report(self) -> None:
        report = aggregate([], config=_config())
        assert report.total_trials == 0
        assert report.by_variant == {}
        assert report.by_task_type == {}
        assert report.by_source == {}

    def test_empty_trials_phase_results_none(self) -> None:
        report = aggregate([], config=_config())
        assert report.phase_results is None


# ---------------------------------------------------------------------------
# TestVariabilityEstimates
# ---------------------------------------------------------------------------


class TestVariabilityEstimates:
    """VariantSummary includes SD, median, and CI."""

    def test_should_compute_std_dev_when_multiple_trials(self) -> None:
        trials = [
            _trial(variant_name="flat", score=0.8),
            _trial(variant_name="flat", score=0.9),
            _trial(variant_name="flat", score=0.7),
        ]
        report = aggregate(trials, config=_config())
        summary = report.by_variant["flat"]
        assert summary.std_dev is not None
        assert summary.std_dev == pytest.approx(0.1, abs=0.01)

    def test_should_compute_median(self) -> None:
        trials = [
            _trial(variant_name="flat", score=0.7),
            _trial(variant_name="flat", score=0.9),
            _trial(variant_name="flat", score=0.8),
        ]
        report = aggregate(trials, config=_config())
        assert report.by_variant["flat"].median == pytest.approx(0.8)

    def test_should_compute_ci_bounds(self) -> None:
        trials = [
            _trial(variant_name="flat", score=s)
            for s in [0.7, 0.8, 0.9, 0.75, 0.85]
        ]
        report = aggregate(trials, config=_config())
        summary = report.by_variant["flat"]
        assert summary.ci_lower is not None
        assert summary.ci_upper is not None
        assert summary.ci_lower <= summary.mean_score <= summary.ci_upper

    def test_should_return_none_ci_when_single_trial(self) -> None:
        trials = [_trial(variant_name="flat", score=0.8)]
        report = aggregate(trials, config=_config())
        summary = report.by_variant["flat"]
        assert summary.ci_lower is None
        assert summary.ci_upper is None

    def test_should_return_zero_std_dev_when_single_trial(self) -> None:
        trials = [_trial(variant_name="flat", score=0.8)]
        report = aggregate(trials, config=_config())
        assert report.by_variant["flat"].std_dev == 0.0

    def test_should_compute_median_when_even_count(self) -> None:
        trials = [
            _trial(variant_name="flat", score=0.7),
            _trial(variant_name="flat", score=0.9),
        ]
        report = aggregate(trials, config=_config())
        assert report.by_variant["flat"].median == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# Bug #101: CI must use t-distribution for small samples
# ---------------------------------------------------------------------------


class TestCIUsesStudentT:
    """Bug #101: CI calculation must use t-distribution, not z=1.96.

    For small sample sizes, z=1.96 understates the CI width.  The correct
    critical value is scipy.stats.t.ppf(0.975, df=n-1), which for n=3 is
    ~4.303 (much wider than 1.96).
    """

    def test_ci_width_matches_t_distribution_for_small_n(self) -> None:
        """With n=3, CI should use t(0.975, 2) ~ 4.303, not z=1.96.

        We compute the expected CI manually with the t-distribution and
        verify the aggregator matches it.
        """
        scores = [0.6, 0.8, 1.0]
        trials = [_trial(variant_name="flat", score=s) for s in scores]
        report = aggregate(trials, config=_config())
        summary = report.by_variant["flat"]

        mean = statistics.mean(scores)
        sd = statistics.stdev(scores)
        se = sd / (len(scores) ** 0.5)
        t_crit = t_dist.ppf(0.975, df=len(scores) - 1)
        expected_lower = mean - t_crit * se
        expected_upper = mean + t_crit * se

        assert summary.ci_lower == pytest.approx(expected_lower, abs=1e-6)
        assert summary.ci_upper == pytest.approx(expected_upper, abs=1e-6)

    def test_ci_wider_than_z_based_for_small_n(self) -> None:
        """For n=3, the t-based CI must be wider than a z=1.96 CI."""
        scores = [0.6, 0.8, 1.0]
        trials = [_trial(variant_name="flat", score=s) for s in scores]
        report = aggregate(trials, config=_config())
        summary = report.by_variant["flat"]

        mean = statistics.mean(scores)
        sd = statistics.stdev(scores)
        se = sd / (len(scores) ** 0.5)
        z_lower = mean - 1.96 * se
        z_upper = mean + 1.96 * se

        # t-based CI should be strictly wider than z-based CI
        assert summary.ci_lower is not None
        assert summary.ci_upper is not None
        assert summary.ci_lower < z_lower
        assert summary.ci_upper > z_upper

    def test_ci_converges_to_z_for_large_n(self) -> None:
        """With large n, the t-based CI should be close to z=1.96 CI."""
        scores = [0.7 + 0.01 * i for i in range(100)]
        trials = [_trial(variant_name="flat", score=s) for s in scores]
        report = aggregate(trials, config=_config())
        summary = report.by_variant["flat"]

        mean = statistics.mean(scores)
        sd = statistics.stdev(scores)
        se = sd / (len(scores) ** 0.5)
        z_lower = mean - 1.96 * se
        z_upper = mean + 1.96 * se

        # With n=100, t(0.975, 99) ~ 1.984, close to 1.96
        assert summary.ci_lower == pytest.approx(z_lower, abs=0.01)
        assert summary.ci_upper == pytest.approx(z_upper, abs=0.01)


# ---------------------------------------------------------------------------
# TestReportDataStrategyFields (Phase 6)
# ---------------------------------------------------------------------------


class TestReportDataStrategyFields:
    """ReportData includes context_strategy and strategy_comparison fields."""

    def test_context_strategy_default(self) -> None:
        report = aggregate([_trial()], config=_config())
        assert report.context_strategy == "full_context"

    def test_context_strategy_set(self) -> None:
        report = ReportData(
            config=_config(),
            total_trials=1,
            total_cost=0.01,
            by_variant={},
            by_task_type={},
            by_source={},
            context_strategy="rag",
        )
        assert report.context_strategy == "rag"

    def test_strategy_comparison_default_none(self) -> None:
        report = aggregate([_trial()], config=_config())
        assert report.strategy_comparison is None

    def test_strategy_comparison_set(self) -> None:
        comparison = {
            "strategies": ["full_context", "rag"],
            "concordance": {"structure": 0.82},
        }
        report = ReportData(
            config=_config(),
            total_trials=1,
            total_cost=0.01,
            by_variant={},
            by_task_type={},
            by_source={},
            strategy_comparison=comparison,
        )
        assert report.strategy_comparison is not None
        assert report.strategy_comparison["concordance"]["structure"] == 0.82
