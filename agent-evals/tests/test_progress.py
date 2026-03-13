"""Tests for progress display callbacks."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from agent_evals.progress import make_progress_callback
from agent_evals.runner import TrialResult


def _dummy_trial() -> TrialResult:
    return MagicMock(spec=TrialResult, task_id="test_001", variant_name="v1", score=0.85, cost=0.0)


class TestMakeProgressCallback:
    """Tests for make_progress_callback()."""

    def test_none_mode_returns_none(self) -> None:
        cb = make_progress_callback("none")
        assert cb is None

    def test_plain_mode_returns_callable(self) -> None:
        cb = make_progress_callback("plain")
        assert callable(cb)

    def test_rich_mode_returns_callable(self) -> None:
        cb = make_progress_callback("rich")
        assert callable(cb)

    def test_plain_callback_logs_progress(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        cb = make_progress_callback("plain")
        assert cb is not None
        with caplog.at_level(logging.INFO, logger="agent_evals"):
            cb(1, 10, _dummy_trial())
        assert "1/10" in caplog.text

    def test_rich_callback_logs_progress(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        cb = make_progress_callback("rich")
        assert cb is not None
        with caplog.at_level(logging.INFO, logger="agent_evals"):
            cb(5, 20, _dummy_trial())
        assert "5/20" in caplog.text

    def test_rich_callback_shows_percentage(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        cb = make_progress_callback("rich")
        assert cb is not None
        with caplog.at_level(logging.INFO, logger="agent_evals"):
            cb(10, 20, _dummy_trial())
        assert "50%" in caplog.text


class TestCostDisplay:
    """Tests for cost display in progress callbacks."""

    def test_plain_callback_shows_cost(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Plain callback displays accumulated cost."""
        cb = make_progress_callback("plain", budget=None)
        assert cb is not None
        t1 = MagicMock(spec=TrialResult, task_id="t1", variant_name="v1", score=0.8, cost=0.05)
        t2 = MagicMock(spec=TrialResult, task_id="t2", variant_name="v1", score=0.9, cost=0.03)
        with caplog.at_level(logging.INFO, logger="agent_evals"):
            cb(1, 100, t1)
            cb(2, 100, t2)
        assert "$0.08" in caplog.text

    def test_rich_callback_shows_cost_and_budget(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Rich callback displays cost and budget percentage."""
        cb = make_progress_callback("rich", budget=2.0)
        assert cb is not None
        trial = MagicMock(spec=TrialResult, task_id="t1", variant_name="v1", score=0.9, cost=0.42)
        with caplog.at_level(logging.INFO, logger="agent_evals"):
            cb(1, 10, trial)
        assert "$0.42" in caplog.text
        assert "21%" in caplog.text

    def test_rich_callback_no_budget_omits_percentage(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """When no budget set, show cost without budget percentage."""
        cb = make_progress_callback("rich", budget=None)
        assert cb is not None
        trial = MagicMock(spec=TrialResult, task_id="t1", variant_name="v1", score=0.75, cost=1.23)
        with caplog.at_level(logging.INFO, logger="agent_evals"):
            cb(1, 50, trial)
        assert "$1.23" in caplog.text

    def test_none_mode_with_budget_returns_none(self) -> None:
        """Display mode 'none' returns None even with budget."""
        cb = make_progress_callback("none", budget=5.0)
        assert cb is None

    def test_cost_accumulates_across_calls(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Cost accumulates across successive callback invocations."""
        cb = make_progress_callback("plain", budget=None)
        assert cb is not None
        for i in range(1, 6):
            trial = MagicMock(spec=TrialResult, task_id=f"t{i}", variant_name="v1", score=0.5, cost=0.10)
            with caplog.at_level(logging.INFO, logger="agent_evals"):
                cb(i, 10, trial)
        assert "$0.50" in caplog.text

    def test_none_cost_treated_as_zero(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """trial.cost=None should not crash and is treated as $0."""
        cb = make_progress_callback("plain", budget=None)
        assert cb is not None
        trial = MagicMock(spec=TrialResult, task_id="t1", variant_name="v1", score=0.5, cost=None)
        with caplog.at_level(logging.INFO, logger="agent_evals"):
            cb(1, 10, trial)
        assert "$0.00" in caplog.text
