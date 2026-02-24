"""Tests for Rich terminal dashboard rendering.

Covers E3-S3: Observatory Terminal Dashboard.
Uses Console(file=StringIO()) to capture rendered output.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.terminal import TerminalDashboard
from agent_evals.observatory.tracker import EventTracker


def _setup(
    tmp_path: Path,
    *,
    total_trials: int = 100,
    budget: float | None = None,
    model_budgets: dict[str, float] | None = None,
) -> tuple[EventTracker, TerminalDashboard]:
    """Create a tracker and dashboard for testing."""
    store = ObservatoryStore(tmp_path / "test.db")
    store.create_run("run-1", "test", {})
    tracker = EventTracker(store=store, model_budgets=model_budgets)
    dashboard = TerminalDashboard(
        tracker=tracker,
        total_trials=total_trials,
        budget=budget,
    )
    return tracker, dashboard


def _record(
    tracker: EventTracker,
    *,
    model: str = "claude",
    cost: float = 0.02,
    score: float = 0.85,
) -> None:
    """Record a trial with defaults."""
    tracker.record_trial(
        run_id="run-1",
        task_id="t1",
        task_type="retrieval",
        variant_name="flat",
        repetition=1,
        score=score,
        prompt_tokens=500,
        completion_tokens=100,
        total_tokens=600,
        cost=cost,
        latency_seconds=1.5,
        model=model,
    )


def _render(dashboard: TerminalDashboard) -> str:
    """Render dashboard to a string."""
    console = Console(file=StringIO(), width=120, force_terminal=True)
    dashboard.render(console)
    return console.file.getvalue()


class TestDashboardRendering:
    """Dashboard renders without errors."""

    def test_renders_without_exceptions(self, tmp_path: Path) -> None:
        tracker, dashboard = _setup(tmp_path)
        _record(tracker)
        output = _render(dashboard)
        assert len(output) > 0

    def test_renders_with_no_events(self, tmp_path: Path) -> None:
        _, dashboard = _setup(tmp_path)
        output = _render(dashboard)
        assert len(output) > 0


class TestProgressDisplay:
    """Progress bar reflects completion."""

    def test_progress_percentage_shown(self, tmp_path: Path) -> None:
        tracker, dashboard = _setup(tmp_path, total_trials=100)
        for _ in range(50):
            _record(tracker)
        output = _render(dashboard)
        assert "50" in output

    def test_progress_shows_trial_counts(self, tmp_path: Path) -> None:
        tracker, dashboard = _setup(tmp_path, total_trials=10)
        for _ in range(3):
            _record(tracker)
        output = _render(dashboard)
        assert "3" in output
        assert "10" in output


class TestModelTable:
    """Per-model table shows all models."""

    def test_model_table_has_all_models(self, tmp_path: Path) -> None:
        tracker, dashboard = _setup(tmp_path)
        for model in ["claude", "gpt", "gemini"]:
            _record(tracker, model=model)
        output = _render(dashboard)
        assert "claude" in output
        assert "gpt" in output
        assert "gemini" in output

    def test_model_table_shows_costs(self, tmp_path: Path) -> None:
        tracker, dashboard = _setup(tmp_path)
        _record(tracker, model="claude", cost=0.05)
        output = _render(dashboard)
        assert "0.05" in output


class TestBudgetDisplay:
    """Budget display shows spend vs cap."""

    def test_budget_shown_when_set(self, tmp_path: Path) -> None:
        tracker, dashboard = _setup(tmp_path, budget=30.0)
        _record(tracker, cost=12.0)
        output = _render(dashboard)
        assert "$12.00" in output
        assert "$30.00" in output

    def test_no_budget_section_when_none(self, tmp_path: Path) -> None:
        tracker, dashboard = _setup(tmp_path, budget=None)
        _record(tracker)
        output = _render(dashboard)
        # Should not crash; budget info simply absent
        assert len(output) > 0


class TestAlertFeed:
    """Alerts appear in feed."""

    def test_alert_text_visible(self, tmp_path: Path) -> None:
        tracker, dashboard = _setup(tmp_path)
        dashboard.add_alert("Budget warning: approaching limit")
        output = _render(dashboard)
        assert "Budget warning" in output
