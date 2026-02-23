"""Tests for OpenRouter cost reconciliation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agent_evals.observatory.openrouter import (
    CostDiscrepancy,
    ReconciliationReport,
    build_reconciliation_report,
    fetch_generation_stats,
    find_discrepancies,
    reconcile_trial_cost,
    token_accuracy_check,
)
from agent_evals.observatory.store import ObservatoryStore, TrialRecord


@pytest.fixture
def store(tmp_path: Path) -> ObservatoryStore:
    return ObservatoryStore(db_path=tmp_path / "obs.db")


@pytest.fixture
def seeded_store(store: ObservatoryStore) -> ObservatoryStore:
    """Store with a run containing trials with known costs."""
    store.create_run("run-1", "taguchi", {})
    store.record_trial(
        run_id="run-1", task_id="t1", task_type="qa",
        variant_name="v-A", repetition=1, score=0.9,
        prompt_tokens=500, completion_tokens=200, total_tokens=700,
        cost=0.005, latency_seconds=1.2, model="openai/gpt-4o",
    )
    store.record_trial(
        run_id="run-1", task_id="t2", task_type="qa",
        variant_name="v-A", repetition=1, score=0.8,
        prompt_tokens=600, completion_tokens=250, total_tokens=850,
        cost=0.007, latency_seconds=1.5, model="openai/gpt-4o",
    )
    store.record_trial(
        run_id="run-1", task_id="t3", task_type="code",
        variant_name="v-B", repetition=1, score=0.75,
        prompt_tokens=800, completion_tokens=400, total_tokens=1200,
        cost=0.010, latency_seconds=2.0,
        model="anthropic/claude-haiku",
    )
    store.finish_run("run-1")
    return store


def _make_trial(
    *,
    trial_id: int = 1,
    cost: float = 0.005,
    prompt_tokens: int = 500,
    completion_tokens: int = 200,
    model: str = "openai/gpt-4o",
) -> TrialRecord:
    """Helper to create a TrialRecord."""
    return TrialRecord(
        trial_id=trial_id, run_id="run-1", task_id="t1",
        task_type="qa", variant_name="v-A", repetition=1,
        score=0.9, prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        cost=cost, latency_seconds=1.0, model=model,
        source="gold_standard", error=None,
    )


class TestReconcileTrialCost:
    """Compare a single trial's cost against OpenRouter reported cost."""

    def test_matching_cost_returns_no_discrepancy(self):
        trial = _make_trial(cost=0.005)
        result = reconcile_trial_cost(trial, openrouter_cost=0.005)
        assert result is None  # No discrepancy

    def test_small_discrepancy_below_threshold_ignored(self):
        trial = _make_trial(cost=0.005)
        # 0.1% difference - below 1% threshold
        result = reconcile_trial_cost(trial, openrouter_cost=0.005005)
        assert result is None

    def test_large_discrepancy_flagged(self):
        trial = _make_trial(cost=0.050)
        result = reconcile_trial_cost(trial, openrouter_cost=0.080)
        assert result is not None
        assert isinstance(result, CostDiscrepancy)
        assert result.trial_id == 1
        assert result.recorded_cost == 0.050
        assert result.openrouter_cost == 0.080

    def test_absolute_threshold_applied(self):
        trial = _make_trial(cost=0.001)
        # 50% diff but only $0.005 absolute - below $0.01 threshold
        result = reconcile_trial_cost(trial, openrouter_cost=0.0005)
        assert result is None


class TestTokenAccuracyCheck:
    """Validate token counts against OpenRouter reported tokens."""

    def test_matching_tokens_pass(self):
        trial = _make_trial(prompt_tokens=500, completion_tokens=200)
        ok = token_accuracy_check(
            trial, or_prompt_tokens=500, or_completion_tokens=200
        )
        assert ok is True

    def test_small_variance_passes(self):
        trial = _make_trial(prompt_tokens=500, completion_tokens=200)
        # 3% variance - below 5%
        ok = token_accuracy_check(
            trial, or_prompt_tokens=515, or_completion_tokens=200
        )
        assert ok is True

    def test_large_variance_fails(self):
        trial = _make_trial(prompt_tokens=500, completion_tokens=200)
        # 20% variance - above 5%
        ok = token_accuracy_check(
            trial, or_prompt_tokens=600, or_completion_tokens=200
        )
        assert ok is False


class TestFindDiscrepancies:
    """Find cost discrepancies across a list of trials."""

    def test_no_discrepancies_when_costs_match(self):
        trials = [_make_trial(trial_id=i, cost=0.005) for i in range(3)]
        or_costs = {i: 0.005 for i in range(3)}
        discs = find_discrepancies(trials, or_costs)
        assert len(discs) == 0

    def test_flags_mismatched_costs(self):
        trials = [
            _make_trial(trial_id=1, cost=0.005),
            _make_trial(trial_id=2, cost=0.010),
        ]
        or_costs = {1: 0.005, 2: 0.020}  # trial 2 mismatch
        discs = find_discrepancies(trials, or_costs)
        assert len(discs) == 1
        assert discs[0].trial_id == 2

    def test_missing_openrouter_cost_flagged(self):
        trials = [_make_trial(trial_id=1, cost=0.005)]
        or_costs: dict[int, float] = {}  # no matching OR cost
        discs = find_discrepancies(trials, or_costs)
        assert len(discs) == 1
        assert discs[0].openrouter_cost is None


class TestBuildReconciliationReport:
    """Build a reconciliation report from trials and OpenRouter data."""

    def test_report_type(self):
        trials = [_make_trial(trial_id=1, cost=0.005)]
        or_costs = {1: 0.005}
        report = build_reconciliation_report(trials, or_costs)
        assert isinstance(report, ReconciliationReport)

    def test_report_totals(self):
        trials = [
            _make_trial(trial_id=1, cost=0.005),
            _make_trial(trial_id=2, cost=0.010),
        ]
        or_costs = {1: 0.005, 2: 0.010}
        report = build_reconciliation_report(trials, or_costs)
        assert report.total_recorded == pytest.approx(0.015)
        assert report.total_openrouter == pytest.approx(0.015)
        assert report.discrepancy_count == 0

    def test_report_with_discrepancies(self):
        trials = [
            _make_trial(trial_id=1, cost=0.005),
            _make_trial(trial_id=2, cost=0.010),
        ]
        or_costs = {1: 0.005, 2: 0.025}
        report = build_reconciliation_report(trials, or_costs)
        assert report.discrepancy_count == 1
        assert len(report.discrepancies) == 1


class TestFetchGenerationStats:
    """Fetch generation stats from OpenRouter API (mocked)."""

    def test_returns_none_on_api_failure(self):
        with patch("agent_evals.observatory.openrouter.httpx") as mock_httpx:
            mock_httpx.get.side_effect = Exception("Network error")
            result = fetch_generation_stats("gen-123")
            assert result is None

    def test_returns_dict_on_success(self):
        with patch("agent_evals.observatory.openrouter.httpx") as mock_httpx:
            mock_resp = mock_httpx.get.return_value
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "id": "gen-123",
                "total_cost": 0.005,
                "tokens_prompt": 500,
                "tokens_completion": 200,
            }
            result = fetch_generation_stats("gen-123")
            assert result is not None
            assert result["total_cost"] == 0.005
