"""Tests for Report Data Aggregator."""

from __future__ import annotations

import pytest
from agent_evals.reports.aggregator import (
    ReportData,
    VariantSummary,
    aggregate,
)
from agent_evals.runner import EvalRunConfig, TrialResult


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


class TestEmptyInput:
    """Edge cases with no trials."""

    def test_empty_trials_produces_empty_report(self) -> None:
        report = aggregate([], config=_config())
        assert report.total_trials == 0
        assert report.by_variant == {}
        assert report.by_task_type == {}
        assert report.by_source == {}
