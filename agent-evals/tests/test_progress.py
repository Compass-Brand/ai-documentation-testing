"""Tests for progress display callbacks."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from agent_evals.progress import make_progress_callback
from agent_evals.runner import TrialResult


def _dummy_trial() -> TrialResult:
    return MagicMock(spec=TrialResult, task_id="test_001", variant_name="v1", score=0.85)


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
