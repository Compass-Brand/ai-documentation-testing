"""Tests for ObservatoryStore – SQLite-backed telemetry storage."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest
from agent_evals.observatory.store import (
    ObservatoryStore,
    RunSummary,
    TrialRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trial_kwargs(
    run_id: str = "run_001",
    *,
    task_id: str = "task_1",
    task_type: str = "retrieval",
    variant_name: str = "flat",
    repetition: int = 1,
    score: float = 0.85,
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
    total_tokens: int = 150,
    cost: float | None = 0.001,
    latency_seconds: float = 1.5,
    model: str = "claude",
    source: str = "gold_standard",
    error: str | None = None,
) -> dict:
    """Build keyword args for record_trial."""
    return {
        "run_id": run_id,
        "task_id": task_id,
        "task_type": task_type,
        "variant_name": variant_name,
        "repetition": repetition,
        "score": score,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost": cost,
        "latency_seconds": latency_seconds,
        "model": model,
        "source": source,
        "error": error,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path: Path) -> ObservatoryStore:
    """Create a fresh ObservatoryStore in a temp directory."""
    return ObservatoryStore(db_path=tmp_path / "observatory.db")


# ---------------------------------------------------------------------------
# TestDatabaseCreation
# ---------------------------------------------------------------------------


class TestDatabaseCreation:
    """Database auto-creates on first use."""

    def test_db_file_created_on_init(self, tmp_path: Path) -> None:
        db_path = tmp_path / "observatory.db"
        assert not db_path.exists()
        ObservatoryStore(db_path=db_path)
        assert db_path.exists()

    def test_schema_has_runs_table(self, store: ObservatoryStore) -> None:
        tables = store._get_tables()
        assert "runs" in tables

    def test_schema_has_trials_table(self, store: ObservatoryStore) -> None:
        tables = store._get_tables()
        assert "trials" in tables


# ---------------------------------------------------------------------------
# TestCreateRun
# ---------------------------------------------------------------------------


class TestCreateRun:
    """Run creation and persistence."""

    def test_creates_run_record(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", run_type="taguchi", config={"k": 10})
        runs = store.list_runs()
        assert len(runs) == 1
        assert runs[0].run_id == "run_001"

    def test_run_has_correct_type(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", run_type="taguchi", config={})
        runs = store.list_runs()
        assert runs[0].run_type == "taguchi"

    def test_run_status_is_active(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", run_type="taguchi", config={})
        runs = store.list_runs()
        assert runs[0].status == "active"

    def test_duplicate_run_id_raises(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", run_type="taguchi", config={})
        with pytest.raises(ValueError, match="already exists"):
            store.create_run("run_001", run_type="taguchi", config={})


# ---------------------------------------------------------------------------
# TestRecordTrial
# ---------------------------------------------------------------------------


class TestRecordTrial:
    """Trial event recording."""

    def test_records_single_trial(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", run_type="taguchi", config={})
        store.record_trial(**_make_trial_kwargs())
        trials = store.get_trials("run_001")
        assert len(trials) == 1

    def test_records_multiple_trials(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", run_type="taguchi", config={})
        for i in range(3):
            store.record_trial(**_make_trial_kwargs(task_id=f"task_{i}"))
        trials = store.get_trials("run_001")
        assert len(trials) == 3

    def test_trial_preserves_fields(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", run_type="taguchi", config={})
        store.record_trial(**_make_trial_kwargs(
            score=0.92, model="gpt-4", source="repliqa",
        ))
        trials = store.get_trials("run_001")
        t = trials[0]
        assert t.score == pytest.approx(0.92)
        assert t.model == "gpt-4"
        assert t.source == "repliqa"

    def test_trial_preserves_source_column(
        self, store: ObservatoryStore
    ) -> None:
        store.create_run("run_001", run_type="taguchi", config={})
        store.record_trial(**_make_trial_kwargs(source="swe-bench"))
        trials = store.get_trials("run_001")
        assert trials[0].source == "swe-bench"


# ---------------------------------------------------------------------------
# TestFinishRun
# ---------------------------------------------------------------------------


class TestFinishRun:
    """Run completion."""

    def test_finish_sets_completed_status(
        self, store: ObservatoryStore
    ) -> None:
        store.create_run("run_001", run_type="taguchi", config={})
        store.finish_run("run_001")
        runs = store.list_runs()
        assert runs[0].status == "completed"

    def test_finish_sets_timestamp(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", run_type="taguchi", config={})
        store.finish_run("run_001")
        runs = store.list_runs()
        assert runs[0].finished_at is not None


# ---------------------------------------------------------------------------
# TestListRuns
# ---------------------------------------------------------------------------


class TestListRuns:
    """Run listing and summaries."""

    def test_list_runs_returns_all(self, store: ObservatoryStore) -> None:
        for i in range(3):
            store.create_run(f"run_{i}", run_type="taguchi", config={})
        runs = store.list_runs()
        assert len(runs) == 3

    def test_list_runs_empty_db(self, store: ObservatoryStore) -> None:
        runs = store.list_runs()
        assert runs == []


# ---------------------------------------------------------------------------
# TestGetRunSummary
# ---------------------------------------------------------------------------


class TestGetRunSummary:
    """Run summary with aggregates."""

    def test_summary_has_total_trials(
        self, store: ObservatoryStore
    ) -> None:
        store.create_run("run_001", run_type="taguchi", config={})
        for i in range(5):
            store.record_trial(**_make_trial_kwargs(task_id=f"task_{i}"))
        summary = store.get_run_summary("run_001")
        assert summary.total_trials == 5

    def test_summary_has_total_cost(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", run_type="taguchi", config={})
        for i in range(3):
            store.record_trial(**_make_trial_kwargs(
                task_id=f"task_{i}", cost=0.01,
            ))
        summary = store.get_run_summary("run_001")
        assert summary.total_cost == pytest.approx(0.03)

    def test_summary_has_avg_latency(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", run_type="taguchi", config={})
        store.record_trial(**_make_trial_kwargs(
            task_id="t1", latency_seconds=1.0,
        ))
        store.record_trial(**_make_trial_kwargs(
            task_id="t2", latency_seconds=3.0,
        ))
        summary = store.get_run_summary("run_001")
        assert summary.avg_latency == pytest.approx(2.0)

    def test_summary_unknown_run_raises(
        self, store: ObservatoryStore
    ) -> None:
        with pytest.raises(ValueError, match="not found"):
            store.get_run_summary("nonexistent")


# ---------------------------------------------------------------------------
# TestFilterTrials
# ---------------------------------------------------------------------------


class TestFilterTrials:
    """Trial filtering by model and source."""

    def test_filter_by_model(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", run_type="taguchi", config={})
        store.record_trial(**_make_trial_kwargs(
            task_id="t1", model="claude",
        ))
        store.record_trial(**_make_trial_kwargs(
            task_id="t2", model="gpt",
        ))
        trials = store.get_trials("run_001", model="claude")
        assert len(trials) == 1
        assert trials[0].model == "claude"

    def test_filter_by_source(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", run_type="taguchi", config={})
        store.record_trial(**_make_trial_kwargs(
            task_id="t1", source="gold_standard",
        ))
        store.record_trial(**_make_trial_kwargs(
            task_id="t2", source="repliqa",
        ))
        trials = store.get_trials("run_001", source="repliqa")
        assert len(trials) == 1
        assert trials[0].source == "repliqa"


# ---------------------------------------------------------------------------
# TestConcurrency
# ---------------------------------------------------------------------------


class TestConcurrency:
    """Thread safety for concurrent writes."""

    def test_concurrent_writes_succeed(
        self, store: ObservatoryStore
    ) -> None:
        store.create_run("run_001", run_type="taguchi", config={})

        def write_trial(i: int) -> None:
            store.record_trial(**_make_trial_kwargs(task_id=f"task_{i}"))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(write_trial, i) for i in range(10)]
            for future in as_completed(futures):
                future.result()  # Raises if any thread failed

        trials = store.get_trials("run_001")
        assert len(trials) == 10
