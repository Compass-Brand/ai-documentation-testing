"""Tests for run checkpointing and resume (Part B: Run Checkpointing)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_evals.observatory.store import ObservatoryStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_store(tmp_path: Path) -> ObservatoryStore:
    """Create a fresh store."""
    return ObservatoryStore(tmp_path / "test.db")


def _trial_kwargs(
    run_id: str = "run-1",
    *,
    task_id: str = "t1",
    variant_name: str = "flat",
    repetition: int = 1,
    score: float = 0.85,
    oa_row_id: int | None = None,
    error: str | None = None,
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
        "oa_row_id": oa_row_id,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Step 8: resume_run and get_completed_trial_keys
# ---------------------------------------------------------------------------


class TestResumeRun:
    """resume_run() reactivates a failed/completed run."""

    def test_resume_sets_status_active(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.create_run("run-1", "taguchi", {})
        store.fail_run("run-1", error="crashed")

        summary = store.get_run_summary("run-1")
        assert summary.status == "failed"

        store.resume_run("run-1")

        summary = store.get_run_summary("run-1")
        assert summary.status == "active"

    def test_resume_updates_heartbeat(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.create_run("run-1", "taguchi", {})
        store.fail_run("run-1")
        store.resume_run("run-1")

        summary = store.get_run_summary("run-1")
        assert summary.heartbeat_at is not None

    def test_resume_nonexistent_run_raises(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        with pytest.raises(ValueError, match="not found"):
            store.resume_run("nonexistent")


class TestGetCompletedTrialKeys:
    """get_completed_trial_keys() returns completed trial identifiers."""

    def test_returns_set_of_tuples(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.create_run("run-1", "taguchi", {})
        store.record_trial(**_trial_kwargs(
            task_id="t1", variant_name="v1", repetition=1, oa_row_id=1,
        ))
        store.record_trial(**_trial_kwargs(
            task_id="t2", variant_name="v1", repetition=1, oa_row_id=1,
        ))

        keys = store.get_completed_trial_keys("run-1")
        assert isinstance(keys, set)
        assert len(keys) == 2
        # Each key is (oa_row_id, task_id, variant_name, repetition)
        assert (1, "t1", "v1", 1) in keys
        assert (1, "t2", "v1", 1) in keys

    def test_excludes_error_trials(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.create_run("run-1", "taguchi", {})
        store.record_trial(**_trial_kwargs(
            task_id="t1", variant_name="v1", repetition=1, oa_row_id=1,
        ))
        store.record_trial(**_trial_kwargs(
            task_id="t2", variant_name="v1", repetition=1, oa_row_id=1,
            error="API timeout",
        ))

        keys = store.get_completed_trial_keys("run-1")
        assert len(keys) == 1
        assert (1, "t1", "v1", 1) in keys

    def test_returns_empty_for_nonexistent_run(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        keys = store.get_completed_trial_keys("nonexistent")
        assert keys == set()

    def test_handles_null_oa_row_id(self, tmp_path: Path) -> None:
        """Full-sweep trials have None oa_row_id."""
        store = _make_store(tmp_path)
        store.create_run("run-1", "full", {})
        store.record_trial(**_trial_kwargs(
            task_id="t1", variant_name="v1", repetition=1, oa_row_id=None,
        ))

        keys = store.get_completed_trial_keys("run-1")
        assert (None, "t1", "v1", 1) in keys
