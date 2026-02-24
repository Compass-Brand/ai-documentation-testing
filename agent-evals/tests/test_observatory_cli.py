"""Tests for observatory CLI subcommand functions."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_evals.observatory.cli import (
    cli_compare_runs,
    cli_cost_trend,
    cli_list_runs,
    cli_model_ranking,
    cli_regressions,
)
from agent_evals.observatory.store import ObservatoryStore


@pytest.fixture
def store(tmp_path: Path) -> ObservatoryStore:
    return ObservatoryStore(db_path=tmp_path / "obs.db")


@pytest.fixture
def populated_store(store: ObservatoryStore) -> ObservatoryStore:
    """Store with two completed runs for CLI testing."""
    store.create_run("run-alpha", "taguchi", {"tag": "alpha"})
    for variant, score, cost, model in [
        ("v-X", 0.85, 0.01, "openai/gpt-4o"),
        ("v-X", 0.90, 0.012, "openai/gpt-4o"),
        ("v-Y", 0.60, 0.005, "anthropic/claude-haiku"),
        ("v-Y", 0.65, 0.006, "anthropic/claude-haiku"),
    ]:
        store.record_trial(
            run_id="run-alpha", task_id="t1", task_type="qa",
            variant_name=variant, repetition=1, score=score,
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=cost, latency_seconds=1.0, model=model,
        )
    store.finish_run("run-alpha")

    store.create_run("run-beta", "sweep", {"tag": "beta"})
    for variant, score, cost, model in [
        ("v-X", 0.92, 0.011, "openai/gpt-4o"),
        ("v-X", 0.88, 0.013, "openai/gpt-4o"),
        ("v-Y", 0.50, 0.004, "anthropic/claude-haiku"),
    ]:
        store.record_trial(
            run_id="run-beta", task_id="t1", task_type="qa",
            variant_name=variant, repetition=1, score=score,
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=cost, latency_seconds=0.8, model=model,
        )
    store.finish_run("run-beta")
    return store


class TestCliListRuns:
    """List all runs with summary statistics."""

    def test_returns_formatted_string(self, populated_store):
        output = cli_list_runs(populated_store)
        assert isinstance(output, str)
        assert len(output) > 0

    def test_includes_run_ids(self, populated_store):
        output = cli_list_runs(populated_store)
        assert "run-alpha" in output
        assert "run-beta" in output

    def test_includes_run_type(self, populated_store):
        output = cli_list_runs(populated_store)
        assert "taguchi" in output
        assert "sweep" in output

    def test_empty_store_returns_message(self, store):
        output = cli_list_runs(store)
        assert "no runs" in output.lower()


class TestCliCompareRuns:
    """Compare runs side by side."""

    def test_returns_formatted_string(self, populated_store):
        output = cli_compare_runs(
            populated_store, ["run-alpha", "run-beta"]
        )
        assert isinstance(output, str)
        assert len(output) > 0

    def test_includes_score_info(self, populated_store):
        output = cli_compare_runs(
            populated_store, ["run-alpha", "run-beta"]
        )
        # Should show avg scores
        assert "score" in output.lower() or "0." in output


class TestCliRegressions:
    """Detect regressions between runs."""

    def test_detects_regression(self, populated_store):
        output = cli_regressions(
            populated_store, "run-alpha", "run-beta", threshold=0.05
        )
        assert isinstance(output, str)
        # v-Y regressed from 0.625 to 0.50
        assert "v-Y" in output

    def test_no_regressions_message(self, populated_store):
        output = cli_regressions(
            populated_store, "run-alpha", "run-beta", threshold=0.50
        )
        assert "no regression" in output.lower()


class TestCliCostTrend:
    """Show cost trends across runs."""

    def test_returns_formatted_string(self, populated_store):
        output = cli_cost_trend(
            populated_store, ["run-alpha", "run-beta"]
        )
        assert isinstance(output, str)
        assert len(output) > 0

    def test_includes_cost_data(self, populated_store):
        output = cli_cost_trend(
            populated_store, ["run-alpha", "run-beta"]
        )
        assert "$" in output or "cost" in output.lower()


class TestCliModelRanking:
    """Rank models by performance."""

    def test_returns_formatted_string(self, populated_store):
        output = cli_model_ranking(
            populated_store, ["run-alpha", "run-beta"]
        )
        assert isinstance(output, str)
        assert len(output) > 0

    def test_includes_model_names(self, populated_store):
        output = cli_model_ranking(
            populated_store, ["run-alpha", "run-beta"]
        )
        assert "gpt-4o" in output
        assert "claude-haiku" in output
