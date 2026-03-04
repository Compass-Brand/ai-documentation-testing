"""Tests for the DiagnosticTracker module.

Covers thread-safe recording, heartbeat logging, stall detection,
and final summary output.
"""

from __future__ import annotations

import logging
import threading
import time
from unittest.mock import patch

import pytest

from agent_evals.diagnostics import DiagnosticTracker


# ---------------------------------------------------------------------------
# Thread-safe recording
# ---------------------------------------------------------------------------


class TestDiagnosticTrackerRecording:
    """Tests for thread-safe trial recording and stats accumulation."""

    def test_record_single_trial(self) -> None:
        tracker = DiagnosticTracker(total_trials=10)
        tracker.record_trial(
            tokens=100,
            cost=0.001,
            retries=0,
            api_ms=500.0,
            trial_ms=600.0,
            error=False,
            rate_limited=False,
        )
        snapshot = tracker.snapshot()
        assert snapshot["completed"] == 1
        assert snapshot["total_tokens"] == 100
        assert snapshot["total_cost"] == pytest.approx(0.001)
        assert snapshot["total_retries"] == 0
        assert snapshot["total_rate_limits"] == 0
        assert snapshot["total_errors"] == 0
        assert snapshot["total_api_ms"] == pytest.approx(500.0)
        assert snapshot["total_trial_ms"] == pytest.approx(600.0)

    def test_record_multiple_trials_accumulates(self) -> None:
        tracker = DiagnosticTracker(total_trials=10)
        tracker.record_trial(
            tokens=100, cost=0.001, retries=1, api_ms=500.0,
            trial_ms=600.0, error=False, rate_limited=False,
        )
        tracker.record_trial(
            tokens=200, cost=0.002, retries=0, api_ms=400.0,
            trial_ms=500.0, error=True, rate_limited=True,
        )
        snapshot = tracker.snapshot()
        assert snapshot["completed"] == 2
        assert snapshot["total_tokens"] == 300
        assert snapshot["total_cost"] == pytest.approx(0.003)
        assert snapshot["total_retries"] == 1
        assert snapshot["total_rate_limits"] == 1
        assert snapshot["total_errors"] == 1
        assert snapshot["total_api_ms"] == pytest.approx(900.0)
        assert snapshot["total_trial_ms"] == pytest.approx(1100.0)

    def test_thread_safety(self) -> None:
        """Multiple threads recording concurrently should not lose data."""
        tracker = DiagnosticTracker(total_trials=1000)
        num_threads = 10
        trials_per_thread = 100

        def record_batch() -> None:
            for _ in range(trials_per_thread):
                tracker.record_trial(
                    tokens=1, cost=0.0001, retries=0, api_ms=1.0,
                    trial_ms=2.0, error=False, rate_limited=False,
                )

        threads = [threading.Thread(target=record_batch) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        snapshot = tracker.snapshot()
        assert snapshot["completed"] == num_threads * trials_per_thread
        assert snapshot["total_tokens"] == num_threads * trials_per_thread

    def test_snapshot_returns_averages(self) -> None:
        tracker = DiagnosticTracker(total_trials=10)
        tracker.record_trial(
            tokens=100, cost=0.001, retries=0, api_ms=200.0,
            trial_ms=300.0, error=False, rate_limited=False,
        )
        tracker.record_trial(
            tokens=200, cost=0.002, retries=0, api_ms=400.0,
            trial_ms=500.0, error=False, rate_limited=False,
        )
        snapshot = tracker.snapshot()
        assert snapshot["avg_api_ms"] == pytest.approx(300.0)
        assert snapshot["avg_trial_ms"] == pytest.approx(400.0)

    def test_snapshot_averages_zero_when_no_trials(self) -> None:
        tracker = DiagnosticTracker(total_trials=10)
        snapshot = tracker.snapshot()
        assert snapshot["completed"] == 0
        assert snapshot["avg_api_ms"] == 0.0
        assert snapshot["avg_trial_ms"] == 0.0

    def test_none_cost_treated_as_zero(self) -> None:
        tracker = DiagnosticTracker(total_trials=10)
        tracker.record_trial(
            tokens=100, cost=None, retries=0, api_ms=100.0,
            trial_ms=200.0, error=False, rate_limited=False,
        )
        snapshot = tracker.snapshot()
        assert snapshot["total_cost"] == 0.0


# ---------------------------------------------------------------------------
# Heartbeat logging
# ---------------------------------------------------------------------------


class TestDiagnosticTrackerHeartbeat:
    """Tests for periodic heartbeat log output."""

    def test_heartbeat_logs_at_info_level(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Heartbeat should produce INFO-level log with key stats."""
        tracker = DiagnosticTracker(total_trials=100, heartbeat_interval=0.1)
        tracker.record_trial(
            tokens=500, cost=0.01, retries=2, api_ms=2000.0,
            trial_ms=2500.0, error=False, rate_limited=True,
        )

        with caplog.at_level(logging.INFO, logger="agent_evals.diagnostics"):
            tracker.start()
            # Wait for at least one heartbeat
            time.sleep(0.3)
            tracker.stop()

        assert "HEARTBEAT" in caplog.text

    def test_heartbeat_includes_progress(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        tracker = DiagnosticTracker(total_trials=1000, heartbeat_interval=0.1)
        tracker.record_trial(
            tokens=100, cost=0.001, retries=0, api_ms=100.0,
            trial_ms=200.0, error=False, rate_limited=False,
        )

        with caplog.at_level(logging.INFO, logger="agent_evals.diagnostics"):
            tracker.start()
            time.sleep(0.3)
            tracker.stop()

        # Should show completed/total
        assert "1/1000" in caplog.text

    def test_heartbeat_thread_is_daemon(self) -> None:
        tracker = DiagnosticTracker(total_trials=10, heartbeat_interval=60)
        tracker.start()
        # The thread should be a daemon so it doesn't block process exit
        assert tracker._heartbeat_thread.daemon is True
        tracker.stop()

    def test_stop_is_idempotent(self) -> None:
        tracker = DiagnosticTracker(total_trials=10, heartbeat_interval=60)
        tracker.start()
        tracker.stop()
        tracker.stop()  # Should not raise


# ---------------------------------------------------------------------------
# Stall detection
# ---------------------------------------------------------------------------


class TestDiagnosticTrackerStallDetection:
    """Tests for stall detection warning when no trials complete."""

    def test_stall_warning_when_no_recent_trial(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Should log WARNING if no trial completed within stall_threshold."""
        tracker = DiagnosticTracker(
            total_trials=100,
            heartbeat_interval=0.1,
            stall_threshold=0.2,
        )
        # Don't record any trials — simulate a stall

        with caplog.at_level(logging.WARNING, logger="agent_evals.diagnostics"):
            tracker.start()
            time.sleep(0.5)
            tracker.stop()

        # Should have stall warning
        stall_messages = [r for r in caplog.records if "stall" in r.message.lower()]
        assert len(stall_messages) > 0

    def test_no_stall_warning_when_trials_flowing(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Should NOT log stall warning when trials are completing regularly."""
        tracker = DiagnosticTracker(
            total_trials=100,
            heartbeat_interval=0.1,
            stall_threshold=5.0,  # Very generous threshold
        )
        tracker.record_trial(
            tokens=100, cost=0.001, retries=0, api_ms=100.0,
            trial_ms=200.0, error=False, rate_limited=False,
        )

        with caplog.at_level(logging.WARNING, logger="agent_evals.diagnostics"):
            tracker.start()
            time.sleep(0.3)
            tracker.stop()

        stall_messages = [r for r in caplog.records if "stall" in r.message.lower()]
        assert len(stall_messages) == 0


# ---------------------------------------------------------------------------
# Final summary
# ---------------------------------------------------------------------------


class TestDiagnosticTrackerFinalSummary:
    """Tests for the final summary log at run end."""

    def test_final_summary_logged_on_stop(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        tracker = DiagnosticTracker(total_trials=10, heartbeat_interval=60)
        tracker.record_trial(
            tokens=500, cost=0.01, retries=1, api_ms=1000.0,
            trial_ms=1200.0, error=False, rate_limited=False,
        )
        tracker.record_trial(
            tokens=300, cost=0.005, retries=0, api_ms=800.0,
            trial_ms=1000.0, error=True, rate_limited=False,
        )

        with caplog.at_level(logging.INFO, logger="agent_evals.diagnostics"):
            tracker.start()
            tracker.stop()

        assert "RUN COMPLETE" in caplog.text

    def test_final_summary_includes_key_stats(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        tracker = DiagnosticTracker(total_trials=10, heartbeat_interval=60)
        tracker.record_trial(
            tokens=500, cost=0.01, retries=1, api_ms=1000.0,
            trial_ms=1200.0, error=False, rate_limited=False,
        )

        with caplog.at_level(logging.INFO, logger="agent_evals.diagnostics"):
            tracker.start()
            tracker.stop()

        # Summary should mention completed count and tokens
        assert "1/10" in caplog.text or "1 / 10" in caplog.text

    def test_start_stop_without_recording(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Starting and stopping with zero trials should still produce summary."""
        tracker = DiagnosticTracker(total_trials=10, heartbeat_interval=60)

        with caplog.at_level(logging.INFO, logger="agent_evals.diagnostics"):
            tracker.start()
            tracker.stop()

        assert "RUN COMPLETE" in caplog.text


# ---------------------------------------------------------------------------
# Completed offset (resume support)
# ---------------------------------------------------------------------------


class TestDiagnosticTrackerCompletedOffset:
    """Tests for completed_offset parameter used during resume."""

    def test_completed_offset_sets_initial_completed(self) -> None:
        """Tracker with offset should start with completed = offset."""
        tracker = DiagnosticTracker(total_trials=500, completed_offset=100)
        snapshot = tracker.snapshot()
        assert snapshot["completed"] == 100
        assert snapshot["total_trials"] == 500

    def test_completed_offset_accumulates_with_new_trials(self) -> None:
        """Recording trials should add to the offset."""
        tracker = DiagnosticTracker(total_trials=500, completed_offset=100)
        tracker.record_trial(
            tokens=50, cost=0.001, retries=0, api_ms=100.0,
            trial_ms=200.0, error=False, rate_limited=False,
        )
        snapshot = tracker.snapshot()
        assert snapshot["completed"] == 101

    def test_completed_offset_progress_percentage(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Heartbeat should show correct % including offset."""
        tracker = DiagnosticTracker(
            total_trials=100, completed_offset=99, heartbeat_interval=0.1,
        )
        tracker.record_trial(
            tokens=50, cost=0.001, retries=0, api_ms=100.0,
            trial_ms=200.0, error=False, rate_limited=False,
        )

        with caplog.at_level(logging.INFO, logger="agent_evals.diagnostics"):
            tracker.start()
            time.sleep(0.3)
            tracker.stop()

        # Should show 100/100 (100.0%)
        assert "100/100" in caplog.text

    def test_completed_offset_default_zero(self) -> None:
        """Default offset is 0 — backward compatible."""
        tracker = DiagnosticTracker(total_trials=10)
        snapshot = tracker.snapshot()
        assert snapshot["completed"] == 0

    def test_completed_offset_in_summary(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Final summary should reflect offset in completed count."""
        tracker = DiagnosticTracker(
            total_trials=200, completed_offset=150, heartbeat_interval=60,
        )
        tracker.record_trial(
            tokens=50, cost=0.001, retries=0, api_ms=100.0,
            trial_ms=200.0, error=False, rate_limited=False,
        )

        with caplog.at_level(logging.INFO, logger="agent_evals.diagnostics"):
            tracker.start()
            tracker.stop()

        assert "RUN COMPLETE" in caplog.text
        assert "151/200" in caplog.text
