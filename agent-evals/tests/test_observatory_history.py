"""Tests for observatory historical analytics: cross-run comparison and trends."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_evals.observatory.history import (
    VariantTrend,
    compare_runs,
    cost_trend,
    detect_regressions,
    get_cross_run_trials,
    model_ranking,
    variant_performance_trend,
)
from agent_evals.observatory.store import ObservatoryStore


@pytest.fixture
def store(tmp_path: Path) -> ObservatoryStore:
    return ObservatoryStore(db_path=tmp_path / "obs.db")


@pytest.fixture
def seeded_store(store: ObservatoryStore) -> ObservatoryStore:
    """Store with two completed runs, each with multiple trials."""
    # Run 1: older run
    store.create_run("run-1", "taguchi", {"tag": "baseline"})
    for i, (variant, score, cost, model) in enumerate([
        ("v-A", 0.80, 0.01, "openai/gpt-4o"),
        ("v-A", 0.85, 0.012, "openai/gpt-4o"),
        ("v-B", 0.70, 0.008, "anthropic/claude-haiku"),
        ("v-B", 0.65, 0.009, "anthropic/claude-haiku"),
    ]):
        store.record_trial(
            run_id="run-1", task_id=f"t{i}", task_type="qa",
            variant_name=variant, repetition=1, score=score,
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=cost, latency_seconds=1.0, model=model,
        )
    store.finish_run("run-1")

    # Run 2: newer run
    store.create_run("run-2", "taguchi", {"tag": "improved"})
    for i, (variant, score, cost, model) in enumerate([
        ("v-A", 0.90, 0.011, "openai/gpt-4o"),
        ("v-A", 0.88, 0.013, "openai/gpt-4o"),
        ("v-B", 0.60, 0.007, "anthropic/claude-haiku"),
        ("v-B", 0.55, 0.0065, "anthropic/claude-haiku"),
    ]):
        store.record_trial(
            run_id="run-2", task_id=f"t{i}", task_type="qa",
            variant_name=variant, repetition=1, score=score,
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=cost, latency_seconds=0.9, model=model,
        )
    store.finish_run("run-2")

    return store


class TestGetCrossRunTrials:
    """Query trials across multiple runs."""

    def test_returns_trials_from_all_runs(self, seeded_store):
        trials = get_cross_run_trials(seeded_store, ["run-1", "run-2"])
        assert len(trials) == 8

    def test_filters_by_variant(self, seeded_store):
        trials = get_cross_run_trials(
            seeded_store, ["run-1", "run-2"], variant_name="v-A"
        )
        assert all(t.variant_name == "v-A" for t in trials)
        assert len(trials) == 4

    def test_filters_by_model(self, seeded_store):
        trials = get_cross_run_trials(
            seeded_store, ["run-1", "run-2"], model="anthropic/claude-haiku"
        )
        assert all(t.model == "anthropic/claude-haiku" for t in trials)
        assert len(trials) == 4

    def test_empty_for_nonexistent_run(self, seeded_store):
        trials = get_cross_run_trials(seeded_store, ["run-999"])
        assert len(trials) == 0


class TestCompareRuns:
    """Compare aggregate statistics between runs."""

    def test_returns_entry_per_run(self, seeded_store):
        result = compare_runs(seeded_store, ["run-1", "run-2"])
        assert len(result) == 2
        assert result[0]["run_id"] == "run-1"
        assert result[1]["run_id"] == "run-2"

    def test_aggregates_correct(self, seeded_store):
        result = compare_runs(seeded_store, ["run-1", "run-2"])
        r1 = result[0]
        assert r1["total_trials"] == 4
        assert r1["avg_score"] == pytest.approx(0.75, abs=0.01)
        assert r1["total_cost"] == pytest.approx(0.039, abs=0.001)

    def test_includes_delta_from_previous(self, seeded_store):
        result = compare_runs(seeded_store, ["run-1", "run-2"])
        r2 = result[1]
        # v-A improved but v-B regressed more, so overall delta is negative
        assert "score_delta" in r2
        assert r2["score_delta"] != 0.0  # some change detected


class TestVariantPerformanceTrend:
    """Track variant performance across runs over time."""

    def test_returns_trend_per_run(self, seeded_store):
        trend = variant_performance_trend(
            seeded_store, "v-A", ["run-1", "run-2"]
        )
        assert len(trend) == 2

    def test_trend_type(self, seeded_store):
        trend = variant_performance_trend(
            seeded_store, "v-A", ["run-1", "run-2"]
        )
        assert isinstance(trend[0], VariantTrend)

    def test_trend_shows_improvement(self, seeded_store):
        trend = variant_performance_trend(
            seeded_store, "v-A", ["run-1", "run-2"]
        )
        assert trend[1].avg_score > trend[0].avg_score

    def test_trend_for_unknown_variant_empty(self, seeded_store):
        trend = variant_performance_trend(
            seeded_store, "nonexistent", ["run-1", "run-2"]
        )
        assert len(trend) == 0


class TestDetectRegressions:
    """Detect performance regressions between runs."""

    def test_detects_regression(self, seeded_store):
        regressions = detect_regressions(
            seeded_store, "run-1", "run-2", threshold=0.05
        )
        # v-B regressed from 0.675 to 0.575
        regressed = [r for r in regressions if r["variant"] == "v-B"]
        assert len(regressed) == 1

    def test_no_false_positive_for_improvement(self, seeded_store):
        regressions = detect_regressions(
            seeded_store, "run-1", "run-2", threshold=0.05
        )
        improved = [r for r in regressions if r["variant"] == "v-A"]
        assert len(improved) == 0

    def test_threshold_controls_sensitivity(self, seeded_store):
        # With high threshold, nothing is a regression
        regressions = detect_regressions(
            seeded_store, "run-1", "run-2", threshold=0.20
        )
        assert len(regressions) == 0


class TestCostTrend:
    """Track cost trends across runs."""

    def test_returns_cost_per_run(self, seeded_store):
        trend = cost_trend(seeded_store, ["run-1", "run-2"])
        assert len(trend) == 2
        assert "run_id" in trend[0]
        assert "total_cost" in trend[0]
        assert "avg_cost_per_trial" in trend[0]

    def test_cost_values_correct(self, seeded_store):
        trend = cost_trend(seeded_store, ["run-1", "run-2"])
        assert trend[0]["total_cost"] == pytest.approx(0.039, abs=0.001)


class TestModelRanking:
    """Rank models by performance across runs."""

    def test_returns_ranking_per_model(self, seeded_store):
        ranking = model_ranking(seeded_store, ["run-1", "run-2"])
        assert len(ranking) == 2

    def test_ranking_sorted_by_score(self, seeded_store):
        ranking = model_ranking(seeded_store, ["run-1", "run-2"])
        scores = [r["avg_score"] for r in ranking]
        assert scores == sorted(scores, reverse=True)

    def test_ranking_includes_model_name(self, seeded_store):
        ranking = model_ranking(seeded_store, ["run-1", "run-2"])
        models = {r["model"] for r in ranking}
        assert "openai/gpt-4o" in models
        assert "anthropic/claude-haiku" in models
