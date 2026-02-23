"""Tests for observatory event tracker with listeners and budget guards.

Covers E3-S2: Observatory Event Tracker.
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker, TrackerEvent


def _make_store(tmp_path: Path) -> ObservatoryStore:
    """Create a store and a run for testing."""
    store = ObservatoryStore(tmp_path / "test.db")
    store.create_run("run-1", "test", {})
    return store


def _trial_kwargs(
    *,
    model: str = "claude",
    cost: float = 0.02,
    score: float = 0.85,
) -> dict:
    """Return minimal kwargs for record_trial."""
    return {
        "run_id": "run-1",
        "task_id": "t1",
        "task_type": "retrieval",
        "variant_name": "flat",
        "repetition": 1,
        "score": score,
        "prompt_tokens": 500,
        "completion_tokens": 100,
        "total_tokens": 600,
        "cost": cost,
        "latency_seconds": 1.5,
        "model": model,
    }


class TestEventRecording:
    """Thread-safe event recording and persistence."""

    def test_record_event_persists_to_store(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tracker = EventTracker(store=store)
        tracker.record_trial(**_trial_kwargs())
        trials = store.get_trials("run-1")
        assert len(trials) == 1
        assert trials[0].model == "claude"

    def test_concurrent_recording_no_data_loss(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tracker = EventTracker(store=store)
        barrier = threading.Barrier(10)

        def _record(i: int) -> None:
            barrier.wait()
            tracker.record_trial(
                **_trial_kwargs(cost=0.01, score=0.5 + i * 0.01)
            )

        threads = [threading.Thread(target=_record, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        trials = store.get_trials("run-1")
        assert len(trials) == 10


class TestListeners:
    """Listener registration and notification."""

    def test_listener_receives_event(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tracker = EventTracker(store=store)
        listener = MagicMock()
        tracker.add_listener(listener)
        tracker.record_trial(**_trial_kwargs())
        listener.assert_called_once()
        event = listener.call_args[0][0]
        assert isinstance(event, TrackerEvent)
        assert event.event_type == "trial_completed"

    def test_multiple_listeners_all_notified(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tracker = EventTracker(store=store)
        listeners = [MagicMock() for _ in range(3)]
        for listener in listeners:
            tracker.add_listener(listener)
        tracker.record_trial(**_trial_kwargs())
        for listener in listeners:
            listener.assert_called_once()

    def test_remove_listener_stops_notification(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tracker = EventTracker(store=store)
        listener = MagicMock()
        tracker.add_listener(listener)
        tracker.remove_listener(listener)
        tracker.record_trial(**_trial_kwargs())
        listener.assert_not_called()


class TestStats:
    """Stats aggregation across recorded events."""

    def test_stats_total_trials(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tracker = EventTracker(store=store)
        for _ in range(5):
            tracker.record_trial(**_trial_kwargs())
        stats = tracker.stats
        assert stats["total_trials"] == 5

    def test_stats_total_cost(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tracker = EventTracker(store=store)
        tracker.record_trial(**_trial_kwargs(cost=0.10))
        tracker.record_trial(**_trial_kwargs(cost=0.05))
        stats = tracker.stats
        assert stats["total_cost"] == pytest.approx(0.15)

    def test_stats_per_model_breakdown(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tracker = EventTracker(store=store)
        tracker.record_trial(**_trial_kwargs(model="claude", cost=0.03))
        tracker.record_trial(**_trial_kwargs(model="claude", cost=0.02))
        tracker.record_trial(**_trial_kwargs(model="gpt", cost=0.01))
        stats = tracker.stats
        assert stats["per_model"]["claude"]["count"] == 2
        assert stats["per_model"]["claude"]["total_cost"] == pytest.approx(0.05)
        assert stats["per_model"]["gpt"]["count"] == 1


class TestAnomalyDetection:
    """Anomaly detection for expensive calls (>3x average)."""

    def test_anomaly_alert_emitted(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tracker = EventTracker(store=store)
        listener = MagicMock()
        tracker.add_listener(listener)

        # Record baseline calls to establish average
        for _ in range(5):
            tracker.record_trial(**_trial_kwargs(model="claude", cost=0.02))

        # Reset mock to only check the anomaly event
        listener.reset_mock()

        # Record an anomalous call (>3x average of 0.02)
        tracker.record_trial(**_trial_kwargs(model="claude", cost=0.08))

        # Should have emitted trial_completed + anomaly_alert
        events = [call[0][0] for call in listener.call_args_list]
        anomaly_events = [e for e in events if e.event_type == "anomaly_alert"]
        assert len(anomaly_events) == 1
        assert anomaly_events[0].data["model"] == "claude"

    def test_no_anomaly_when_cost_is_normal(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tracker = EventTracker(store=store)
        listener = MagicMock()
        tracker.add_listener(listener)

        for _ in range(5):
            tracker.record_trial(**_trial_kwargs(model="claude", cost=0.02))

        events = [call[0][0] for call in listener.call_args_list]
        anomaly_events = [e for e in events if e.event_type == "anomaly_alert"]
        assert len(anomaly_events) == 0


class TestBudgetEnforcement:
    """Per-model budget enforcement."""

    def test_model_budget_exceeded_event(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tracker = EventTracker(
            store=store,
            model_budgets={"claude": 0.05},
        )
        listener = MagicMock()
        tracker.add_listener(listener)

        tracker.record_trial(**_trial_kwargs(model="claude", cost=0.04))
        tracker.record_trial(**_trial_kwargs(model="claude", cost=0.02))

        events = [call[0][0] for call in listener.call_args_list]
        budget_events = [
            e for e in events if e.event_type == "model_budget_exceeded"
        ]
        assert len(budget_events) == 1
        assert budget_events[0].data["model"] == "claude"

    def test_is_model_over_budget(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tracker = EventTracker(
            store=store,
            model_budgets={"claude": 0.05, "gpt": 10.0},
        )
        tracker.record_trial(**_trial_kwargs(model="claude", cost=0.06))
        assert tracker.is_model_over_budget("claude") is True
        assert tracker.is_model_over_budget("gpt") is False

    def test_model_without_budget_never_over(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tracker = EventTracker(store=store)
        tracker.record_trial(**_trial_kwargs(model="claude", cost=100.0))
        assert tracker.is_model_over_budget("claude") is False
