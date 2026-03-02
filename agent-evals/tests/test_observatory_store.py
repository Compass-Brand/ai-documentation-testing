"""Tests for ObservatoryStore - SQLite-backed telemetry storage."""

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


@pytest.fixture
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


# ---------------------------------------------------------------------------
# TestFailRun (Task 12)
# ---------------------------------------------------------------------------


class TestFailRun:
    """fail_run() marks runs as failed with error and timestamp."""

    def test_fail_run_sets_failed_status_and_finished_at(
        self, tmp_path: Path
    ) -> None:
        store = ObservatoryStore(db_path=tmp_path / "test.db")
        store.create_run("run1", "full", {}, phase="screening")
        store.fail_run("run1", error="Runner crashed")
        summary = store.get_run_summary("run1")
        assert summary.status == "failed"
        assert summary.finished_at is not None


# ---------------------------------------------------------------------------
# TestHeartbeat (Task 15a)
# ---------------------------------------------------------------------------


class TestHeartbeat:
    """Heartbeat and stale run reaping."""

    def test_update_heartbeat_sets_timestamp(self, tmp_path: Path) -> None:
        store = ObservatoryStore(db_path=tmp_path / "test.db")
        store.create_run("run1", "full", {}, phase="screening")
        store.update_heartbeat("run1")
        summary = store.get_run_summary("run1")
        assert summary.heartbeat_at is not None

    def test_reap_stale_runs_marks_stale_active_runs_failed(
        self, tmp_path: Path
    ) -> None:
        store = ObservatoryStore(db_path=tmp_path / "test.db")
        store.create_run("stale", "full", {}, phase="screening")
        store.update_heartbeat("stale")
        reaped = store.reap_stale_runs(max_age_seconds=0)
        assert "stale" in reaped
        summary = store.get_run_summary("stale")
        assert summary.status == "failed"


# ---------------------------------------------------------------------------
# TestTrialRecordFields (Task 20)
# ---------------------------------------------------------------------------


class TestTrialRecordFields:
    """TrialRecord includes oa_row_id and phase fields."""

    def test_trial_record_includes_oa_row_id_and_phase(
        self, tmp_path: Path
    ) -> None:
        store = ObservatoryStore(db_path=tmp_path / "test.db")
        store.create_run("r", "taguchi", {}, phase="screening")
        store.record_trial(
            run_id="r",
            task_id="negative_001",
            task_type="negative",
            variant_name="baseline",
            repetition=1,
            score=0.5,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost=0.001,
            latency_seconds=0.1,
            model="openrouter/anthropic/claude-haiku-4-5-20251001",
            source="gold_standard",
            oa_row_id=3,
            phase="screening",
        )
        trials = store.get_trials("r")
        assert trials[0].oa_row_id == 3
        assert trials[0].phase == "screening"


# ---------------------------------------------------------------------------
# TestPhaseAndPipeline
# ---------------------------------------------------------------------------


class TestPhaseAndPipeline:
    """Phase columns, pipeline queries, and phase results."""

    def test_create_run_with_phase_and_pipeline(
        self, tmp_path: Path
    ) -> None:
        """Runs table accepts phase and pipeline_id columns."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run(
            "run-1", "taguchi", {"mode": "taguchi"},
            phase="screening", pipeline_id="pipe-1",
        )
        runs = store.list_runs()
        assert len(runs) == 1
        assert runs[0].run_id == "run-1"

    def test_create_run_with_parent(self, tmp_path: Path) -> None:
        """Confirmation run links to parent screening run."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run(
            "run-1", "taguchi", {},
            phase="screening", pipeline_id="pipe-1",
        )
        store.create_run(
            "run-2", "taguchi", {},
            phase="confirmation", pipeline_id="pipe-1",
            parent_run_id="run-1",
        )
        runs = store.list_runs()
        assert len(runs) == 2

    def test_record_trial_with_oa_row_and_phase(
        self, tmp_path: Path
    ) -> None:
        """Trial records store oa_row_id and phase."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("run-1", "taguchi", {})
        store.record_trial(
            run_id="run-1", task_id="t1", task_type="retrieval",
            variant_name="v1", repetition=1, score=0.8,
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=0.01, latency_seconds=1.0, model="test-model",
            oa_row_id=3, phase="screening",
        )
        trials = store.get_trials("run-1")
        assert len(trials) == 1

    def test_save_and_get_phase_results(self, tmp_path: Path) -> None:
        """Phase results round-trip through SQLite."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("run-1", "taguchi", {})
        store.save_phase_results(
            run_id="run-1",
            main_effects={"structure": {"flat": 10.5, "nested": 12.3}},
            anova={"structure": {"p_value": 0.001, "omega_squared": 0.089}},
            optimal={"structure": "nested"},
            significant_factors=["structure", "transform"],
            quality_type="larger_is_better",
        )
        result = store.get_phase_results("run-1")
        assert result is not None
        assert result["main_effects"]["structure"]["nested"] == 12.3
        assert result["quality_type"] == "larger_is_better"

    def test_get_phase_results_missing(self, tmp_path: Path) -> None:
        """Returns None for runs without phase results."""
        store = ObservatoryStore(tmp_path / "test.db")
        result = store.get_phase_results("nonexistent")
        assert result is None

    def test_get_pipeline_runs(self, tmp_path: Path) -> None:
        """Lists all runs in a pipeline ordered by creation."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run(
            "r1", "taguchi", {}, phase="screening", pipeline_id="p1",
        )
        store.create_run(
            "r2", "taguchi", {},
            phase="confirmation", pipeline_id="p1",
        )
        store.create_run(
            "r3", "taguchi", {}, phase="refinement", pipeline_id="p1",
        )
        runs = store.get_pipeline_runs("p1")
        assert len(runs) == 3
        assert runs[0].run_id == "r1"

    def test_get_run_aggregates_returns_correct_statistics(
        self, tmp_path: Path
    ) -> None:
        """SQL aggregation returns correct trial statistics (Task 18)."""
        store = ObservatoryStore(db_path=tmp_path / "test.db")
        store.create_run("r", "full", {}, phase="screening")
        for i in range(100):
            store.record_trial(
                run_id="r",
                task_id=f"compositional_{i:03d}",
                task_type="compositional",
                variant_name="v1",
                repetition=1,
                score=i / 100.0,
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
                cost=0.001,
                latency_seconds=0.5,
                model="openrouter/anthropic/claude-haiku-4-5-20251001",
                source="gold_standard",
            )
        aggs = store.get_run_aggregates("r")
        assert aggs["trial_count"] == 100
        assert abs(aggs["mean_score"] - 0.495) < 0.01
        assert len(aggs["by_variant"]) == 1
        assert aggs["by_variant"][0]["variant"] == "v1"

    def test_list_runs_pagination(self, tmp_path: Path) -> None:
        """SQL LIMIT/OFFSET pagination works correctly (Task 19)."""
        store = ObservatoryStore(db_path=tmp_path / "test.db")
        for i in range(20):
            store.create_run(f"run{i}", "full", {})
        page2 = store.list_runs(limit=5, offset=5)
        page1 = store.list_runs(limit=5, offset=0)
        assert len(page2) == 5
        assert page2[0].run_id != page1[0].run_id

    def test_list_pipelines(self, tmp_path: Path) -> None:
        """list_pipelines returns aggregated pipeline stats (Task 19)."""
        store = ObservatoryStore(db_path=tmp_path / "test.db")
        for i in range(3):
            store.create_run(f"run{i}", "full", {}, pipeline_id="pipe1")
        pipelines = store.list_pipelines()
        assert len(pipelines) == 1
        assert pipelines[0]["pipeline_id"] == "pipe1"
        assert pipelines[0]["run_count"] == 3

    def test_schema_migration_preserves_existing_data(
        self, tmp_path: Path
    ) -> None:
        """Adding new columns does not break existing data."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("old-run", "sweep", {"mode": "full"})
        store.record_trial(
            run_id="old-run", task_id="t1", task_type="retrieval",
            variant_name="v1", repetition=1, score=0.5,
            prompt_tokens=10, completion_tokens=5, total_tokens=15,
            cost=0.001, latency_seconds=0.5, model="m1",
        )
        store2 = ObservatoryStore(tmp_path / "test.db")
        trials = store2.get_trials("old-run")
        assert len(trials) == 1
