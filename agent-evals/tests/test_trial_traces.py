"""Tests for trial trace storage and retrieval (Part A: Trace Storage)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_evals.observatory.store import ObservatoryStore


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
