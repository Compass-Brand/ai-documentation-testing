"""Tests for trial trace storage and retrieval (Part A: Trace Storage)."""

from __future__ import annotations

from pathlib import Path

from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker
from agent_evals.observatory.web.routes import create_router
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store(tmp_path: Path) -> ObservatoryStore:
    """Create a store with a pre-created run."""
    store = ObservatoryStore(tmp_path / "test.db")
    store.create_run("run-1", "test", {})
    return store


def _trial_kwargs(
    run_id: str = "run-1",
    *,
    task_id: str = "t1",
    variant_name: str = "flat",
    repetition: int = 1,
    score: float = 0.85,
) -> dict:
    """Minimal kwargs for record_trial."""
    return {
        "run_id": run_id,
        "task_id": task_id,
        "task_type": "retrieval",
        "variant_name": variant_name,
        "repetition": repetition,
        "score": score,
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "cost": 0.001,
        "latency_seconds": 1.5,
        "model": "claude",
    }


# ---------------------------------------------------------------------------
# Step 1: record_trial returns trial_id
# ---------------------------------------------------------------------------


class TestRecordTrialReturnsId:
    """record_trial() should return a positive integer trial_id."""

    def test_returns_positive_int(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        trial_id = store.record_trial(**_trial_kwargs())
        assert isinstance(trial_id, int)
        assert trial_id > 0

    def test_sequential_calls_return_distinct_ids(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        id1 = store.record_trial(**_trial_kwargs(repetition=1))
        id2 = store.record_trial(**_trial_kwargs(repetition=2))
        assert id1 != id2
        assert id2 > id1


# ---------------------------------------------------------------------------
# Step 2: trial_traces table and methods
# ---------------------------------------------------------------------------


class TestTrialTraces:
    """trial_traces table with record_trace() and get_trace()."""

    def test_trial_traces_table_exists(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tables = store._get_tables()
        assert "trial_traces" in tables

    def test_record_and_get_trace(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        trial_id = store.record_trial(**_trial_kwargs())

        prompt = [{"role": "user", "content": "Hello"}]
        response = "Hi there!"

        store.record_trace(trial_id=trial_id, prompt_json=prompt, response_text=response)
        trace = store.get_trace(trial_id)

        assert trace is not None
        assert trace["prompt_json"] == prompt
        assert trace["response_text"] == response
        assert "created_at" in trace

    def test_get_trace_returns_none_for_missing(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        assert store.get_trace(99999) is None

    def test_record_trace_idempotent_on_duplicate(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        trial_id = store.record_trial(**_trial_kwargs())

        prompt = [{"role": "user", "content": "Hello"}]
        store.record_trace(trial_id=trial_id, prompt_json=prompt, response_text="v1")
        # Second call should not raise
        store.record_trace(trial_id=trial_id, prompt_json=prompt, response_text="v2")

        # Should keep the first insertion (INSERT OR IGNORE)
        trace = store.get_trace(trial_id)
        assert trace["response_text"] == "v1"


# ---------------------------------------------------------------------------
# Step 5: EventTracker trace forwarding
# ---------------------------------------------------------------------------


class TestTrackerTraceForwarding:
    """EventTracker conditionally stores traces based on store_traces flag."""

    def test_store_traces_false_no_trace_stored(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tracker = EventTracker(store=store, store_traces=False)

        prompt = [{"role": "user", "content": "Hello"}]
        trial_id = tracker.record_trial(
            **_trial_kwargs(),
            prompt_messages=prompt,
            response_text="response",
        )

        assert store.get_trace(trial_id) is None

    def test_store_traces_true_with_messages_stores_trace(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tracker = EventTracker(store=store, store_traces=True)

        prompt = [{"role": "user", "content": "Hello"}]
        trial_id = tracker.record_trial(
            **_trial_kwargs(),
            prompt_messages=prompt,
            response_text="response",
        )

        trace = store.get_trace(trial_id)
        assert trace is not None
        assert trace["prompt_json"] == prompt
        assert trace["response_text"] == "response"

    def test_store_traces_true_without_messages_no_trace(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        tracker = EventTracker(store=store, store_traces=True)

        trial_id = tracker.record_trial(**_trial_kwargs())

        assert store.get_trace(trial_id) is None


# ---------------------------------------------------------------------------
# Step 7: API endpoint for traces
# ---------------------------------------------------------------------------


class TestTraceAPIEndpoint:
    """GET /api/trials/{trial_id}/trace endpoint."""

    def _make_client(self, tmp_path: Path) -> tuple[TestClient, ObservatoryStore]:
        from fastapi import FastAPI

        store = _make_store(tmp_path)
        tracker = EventTracker(store=store)
        router = create_router(store=store, tracker=tracker)
        app = FastAPI()
        app.include_router(router)
        return TestClient(app), store

    def test_returns_404_when_no_trace(self, tmp_path: Path) -> None:
        client, _ = self._make_client(tmp_path)
        resp = client.get("/api/trials/99999/trace")
        assert resp.status_code == 404

    def test_returns_trace_data(self, tmp_path: Path) -> None:
        client, store = self._make_client(tmp_path)

        trial_id = store.record_trial(**_trial_kwargs())
        prompt = [{"role": "user", "content": "Test"}]
        store.record_trace(trial_id=trial_id, prompt_json=prompt, response_text="OK")

        resp = client.get(f"/api/trials/{trial_id}/trace")
        assert resp.status_code == 200
        data = resp.json()
        assert data["prompt_json"] == prompt
        assert data["response_text"] == "OK"
