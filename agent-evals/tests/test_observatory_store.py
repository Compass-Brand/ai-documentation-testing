"""Tests for ObservatoryStore - SQLite-backed telemetry storage."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
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
        store.record_trial(**_make_trial_kwargs("run_001"))
        store.finish_run("run_001")
        runs = store.list_runs()
        assert runs[0].status == "completed"

    def test_finish_zero_trials_sets_empty(
        self, store: ObservatoryStore
    ) -> None:
        store.create_run("run_001", run_type="taguchi", config={})
        store.finish_run("run_001")
        runs = store.list_runs()
        assert runs[0].status == "empty"

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

    def test_get_phase_results_corrupted_json(self, tmp_path: Path) -> None:
        """Corrupted JSON columns return None with a warning instead of crashing."""
        db_path = tmp_path / "test.db"
        store = ObservatoryStore(db_path)
        store.create_run("run-1", "taguchi", {})
        # Save valid data first
        store.save_phase_results(
            run_id="run-1",
            main_effects={"a": 1},
            anova={"a": {"p": 0.05}},
            optimal={"a": "b"},
            significant_factors=["a"],
            quality_type="larger_is_better",
        )
        # Corrupt the main_effects column directly
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "UPDATE phase_results SET main_effects = '{invalid json' "
            "WHERE run_id = 'run-1'"
        )
        conn.commit()
        conn.close()

        result = store.get_phase_results("run-1")
        assert result is not None
        # Corrupted field should be None, valid fields should still parse
        assert result["main_effects"] is None
        assert result["anova"] == {"a": {"p": 0.05}}
        assert result["optimal"] == {"a": "b"}
        assert result["significant_factors"] == ["a"]
        assert result["quality_type"] == "larger_is_better"

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


# ---------------------------------------------------------------------------
# TestDatabaseIndexes
# ---------------------------------------------------------------------------


class TestDatabaseIndexes:
    """Verify performance indexes exist on trials table."""

    def _get_index_names(self, store: ObservatoryStore) -> set[str]:
        """Return set of index names in the database."""
        with store._connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        return {r["name"] for r in rows}

    def test_should_have_run_id_composite_index(
        self, store: ObservatoryStore
    ) -> None:
        """Composite index on (run_id, task_type, variant_name) for filtered queries."""
        indexes = self._get_index_names(store)
        assert "idx_trials_run_type_variant" in indexes

    def test_should_have_source_task_type_index(
        self, store: ObservatoryStore
    ) -> None:
        """Index on (source, task_type) for dashboard source filtering."""
        indexes = self._get_index_names(store)
        assert "idx_trials_source_type" in indexes

    def test_should_have_variant_repetition_index(
        self, store: ObservatoryStore
    ) -> None:
        """Index on (variant_name, repetition) for variant analysis queries."""
        indexes = self._get_index_names(store)
        assert "idx_trials_variant_rep" in indexes

    def test_indexes_created_idempotently(self, tmp_path: Path) -> None:
        """Re-creating store on same DB does not fail on existing indexes."""
        db_path = tmp_path / "test.db"
        ObservatoryStore(db_path=db_path)
        store2 = ObservatoryStore(db_path=db_path)
        indexes = self._get_index_names(store2)
        assert "idx_trials_run_type_variant" in indexes

    def test_should_have_strategy_index(
        self, store: ObservatoryStore
    ) -> None:
        """Index on context_strategy for strategy-filtered queries."""
        indexes = self._get_index_names(store)
        assert "idx_trials_strategy" in indexes


# ---------------------------------------------------------------------------
# TestStrategySchema (Phase 6)
# ---------------------------------------------------------------------------


class TestStrategySchema:
    """Schema migration adds context_strategy, llm_calls, strategy_metadata columns."""

    def test_schema_migration_adds_context_strategy_column(
        self, tmp_path: Path
    ) -> None:
        """Migration adds context_strategy TEXT DEFAULT 'full_context'."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("r", "full", {})
        store.record_trial(
            run_id="r", task_id="t1", task_type="retrieval",
            variant_name="v1", repetition=1, score=0.8,
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=0.01, latency_seconds=1.0, model="test",
        )
        trials = store.get_trials("r")
        assert trials[0].context_strategy == "full_context"

    def test_schema_migration_adds_llm_calls_column(
        self, tmp_path: Path
    ) -> None:
        """Migration adds llm_calls INTEGER DEFAULT 1."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("r", "full", {})
        store.record_trial(
            run_id="r", task_id="t1", task_type="retrieval",
            variant_name="v1", repetition=1, score=0.8,
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=0.01, latency_seconds=1.0, model="test",
        )
        trials = store.get_trials("r")
        assert trials[0].llm_calls == 1

    def test_schema_migration_adds_strategy_metadata_column(
        self, tmp_path: Path
    ) -> None:
        """Migration adds strategy_metadata TEXT (JSON blob)."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("r", "full", {})
        store.record_trial(
            run_id="r", task_id="t1", task_type="retrieval",
            variant_name="v1", repetition=1, score=0.8,
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=0.01, latency_seconds=1.0, model="test",
        )
        trials = store.get_trials("r")
        assert trials[0].strategy_metadata is None

    def test_record_trial_with_strategy_fields(
        self, tmp_path: Path
    ) -> None:
        """record_trial accepts and persists context_strategy, llm_calls, strategy_metadata."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("r", "full", {})
        store.record_trial(
            run_id="r", task_id="t1", task_type="retrieval",
            variant_name="v1", repetition=1, score=0.8,
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=0.01, latency_seconds=1.0, model="test",
            context_strategy="rag",
            llm_calls=3,
            strategy_metadata={"chunk_method": "heading", "top_k": 5},
        )
        trials = store.get_trials("r")
        assert trials[0].context_strategy == "rag"
        assert trials[0].llm_calls == 3
        assert trials[0].strategy_metadata == {"chunk_method": "heading", "top_k": 5}

    def test_get_trials_filters_by_context_strategy(
        self, tmp_path: Path
    ) -> None:
        """get_trials accepts optional context_strategy filter."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("r", "full", {})
        store.record_trial(
            run_id="r", task_id="t1", task_type="retrieval",
            variant_name="v1", repetition=1, score=0.8,
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=0.01, latency_seconds=1.0, model="test",
            context_strategy="full_context",
        )
        store.record_trial(
            run_id="r", task_id="t2", task_type="retrieval",
            variant_name="v1", repetition=1, score=0.7,
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=0.01, latency_seconds=1.0, model="test",
            context_strategy="rag",
        )
        rag_trials = store.get_trials("r", context_strategy="rag")
        assert len(rag_trials) == 1
        assert rag_trials[0].context_strategy == "rag"

    def test_get_run_aggregates_includes_by_strategy(
        self, tmp_path: Path
    ) -> None:
        """get_run_aggregates includes by_strategy grouping."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("r", "full", {})
        store.record_trial(
            run_id="r", task_id="t1", task_type="retrieval",
            variant_name="v1", repetition=1, score=0.9,
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=0.01, latency_seconds=1.0, model="test",
            context_strategy="full_context",
        )
        store.record_trial(
            run_id="r", task_id="t2", task_type="retrieval",
            variant_name="v1", repetition=1, score=0.7,
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=0.01, latency_seconds=1.0, model="test",
            context_strategy="rag",
        )
        aggs = store.get_run_aggregates("r")
        assert "by_strategy" in aggs
        strategies = {s["strategy"] for s in aggs["by_strategy"]}
        assert "full_context" in strategies
        assert "rag" in strategies

    def test_schema_migration_backward_compatible(
        self, tmp_path: Path
    ) -> None:
        """Existing data without strategy fields gets correct defaults."""
        import sqlite3

        db_path = tmp_path / "test.db"
        # Create a minimal DB without strategy columns
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                run_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                config TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                finished_at TEXT,
                parent_run_id TEXT,
                phase TEXT,
                pipeline_id TEXT,
                heartbeat_at TEXT
            );
            CREATE TABLE IF NOT EXISTS trials (
                trial_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                task_type TEXT NOT NULL,
                variant_name TEXT NOT NULL,
                repetition INTEGER NOT NULL,
                score REAL NOT NULL,
                prompt_tokens INTEGER NOT NULL,
                completion_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                cost REAL,
                latency_seconds REAL NOT NULL,
                model TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'gold_standard',
                error TEXT,
                created_at TEXT NOT NULL,
                oa_row_id INTEGER,
                phase TEXT
            );
            CREATE TABLE IF NOT EXISTS phase_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                main_effects TEXT NOT NULL,
                anova TEXT NOT NULL,
                optimal TEXT NOT NULL,
                significant_factors TEXT NOT NULL,
                quality_type TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS trial_traces (
                trial_id INTEGER PRIMARY KEY,
                prompt_json TEXT NOT NULL,
                response_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        conn.execute(
            "INSERT INTO runs VALUES ('old', 'full', 'completed', '{}', "
            "'2025-01-01', '2025-01-01', NULL, NULL, NULL, NULL)"
        )
        conn.execute(
            "INSERT INTO trials (run_id, task_id, task_type, variant_name, "
            "repetition, score, prompt_tokens, completion_tokens, "
            "total_tokens, cost, latency_seconds, model, source, error, "
            "created_at, oa_row_id, phase) VALUES "
            "('old', 't1', 'qa', 'v1', 1, 0.8, 100, 50, 150, 0.01, "
            "1.0, 'test', 'gold_standard', NULL, '2025-01-01', NULL, NULL)"
        )
        conn.commit()
        conn.close()

        # Now open with ObservatoryStore which runs migration
        store = ObservatoryStore(db_path)
        trials = store.get_trials("old")
        assert len(trials) == 1
        assert trials[0].context_strategy == "full_context"
        assert trials[0].llm_calls == 1
        assert trials[0].strategy_metadata is None


# ---------------------------------------------------------------------------
# TestFactorDefinitions (Task 1)
# ---------------------------------------------------------------------------


class TestFactorDefinitions:
    """Factor definition persistence for axis/level metadata."""

    def test_save_and_get_factor_definitions(
        self, store: ObservatoryStore
    ) -> None:
        """Save 3 definitions across 2 factors, retrieve, verify count and values."""
        store.create_run("run_001", run_type="taguchi", config={})
        definitions = [
            {
                "factor_name": "structure",
                "axis_id": 1,
                "level_index": 0,
                "level_name": "flat",
                "description": "Flat directory layout",
            },
            {
                "factor_name": "structure",
                "axis_id": 1,
                "level_index": 1,
                "level_name": "nested",
                "description": "Nested directory layout",
            },
            {
                "factor_name": "verbosity",
                "axis_id": 3,
                "level_index": 0,
                "level_name": "terse",
                "description": "Minimal prose",
            },
        ]
        store.save_factor_definitions("run_001", definitions)
        result = store.get_factor_definitions("run_001")
        assert len(result) == 3
        # Ordered by axis_id then level_index
        assert result[0]["factor_name"] == "structure"
        assert result[0]["axis_id"] == 1
        assert result[0]["level_index"] == 0
        assert result[0]["level_name"] == "flat"
        assert result[0]["description"] == "Flat directory layout"
        assert result[1]["factor_name"] == "structure"
        assert result[1]["level_index"] == 1
        assert result[2]["factor_name"] == "verbosity"
        assert result[2]["axis_id"] == 3

    def test_get_factor_definitions_empty(
        self, store: ObservatoryStore
    ) -> None:
        """Create run, get definitions with no saves, verify empty list."""
        store.create_run("run_001", run_type="taguchi", config={})
        result = store.get_factor_definitions("run_001")
        assert result == []

    def test_factor_definitions_replaced_on_rewrite(
        self, store: ObservatoryStore
    ) -> None:
        """Save once, save again with different data, verify only new data exists."""
        store.create_run("run_001", run_type="taguchi", config={})
        original = [
            {
                "factor_name": "structure",
                "axis_id": 1,
                "level_index": 0,
                "level_name": "flat",
                "description": "Original",
            },
        ]
        store.save_factor_definitions("run_001", original)
        assert len(store.get_factor_definitions("run_001")) == 1

        replacement = [
            {
                "factor_name": "verbosity",
                "axis_id": 3,
                "level_index": 0,
                "level_name": "terse",
                "description": "Replaced",
            },
            {
                "factor_name": "verbosity",
                "axis_id": 3,
                "level_index": 1,
                "level_name": "verbose",
                "description": "Also replaced",
            },
        ]
        store.save_factor_definitions("run_001", replacement)
        result = store.get_factor_definitions("run_001")
        assert len(result) == 2
        assert result[0]["factor_name"] == "verbosity"
        assert result[0]["level_name"] == "terse"
        assert result[1]["level_name"] == "verbose"


# ---------------------------------------------------------------------------
# TestTaskMetadata (Task 2)
# ---------------------------------------------------------------------------


class TestTaskMetadata:
    """Task metadata persistence for slicing trials by task attributes."""

    def test_save_and_get_task_metadata(
        self, store: ObservatoryStore
    ) -> None:
        """Save 2 tasks, retrieve, verify count and values (ordered by task_id)."""
        metadata = [
            {
                "task_id": "retrieval_002",
                "task_type": "retrieval",
                "domain": "api_docs",
                "difficulty": "hard",
                "word_count": 250,
                "tag_count": 5,
            },
            {
                "task_id": "negative_001",
                "task_type": "negative",
                "domain": "security",
                "difficulty": "easy",
                "word_count": 80,
                "tag_count": 2,
            },
        ]
        store.save_task_metadata(metadata)
        result = store.get_task_metadata()
        assert len(result) == 2
        # Ordered by task_id: negative_001 < retrieval_002
        assert result[0]["task_id"] == "negative_001"
        assert result[0]["task_type"] == "negative"
        assert result[0]["domain"] == "security"
        assert result[0]["difficulty"] == "easy"
        assert result[0]["word_count"] == 80
        assert result[0]["tag_count"] == 2
        assert result[1]["task_id"] == "retrieval_002"
        assert result[1]["task_type"] == "retrieval"
        assert result[1]["domain"] == "api_docs"
        assert result[1]["difficulty"] == "hard"
        assert result[1]["word_count"] == 250
        assert result[1]["tag_count"] == 5

    def test_task_metadata_upsert(
        self, store: ObservatoryStore
    ) -> None:
        """Save same task_id twice with different values, verify only 1 row with updated values."""
        original = [
            {
                "task_id": "retrieval_001",
                "task_type": "retrieval",
                "domain": "api_docs",
                "difficulty": "easy",
                "word_count": 100,
                "tag_count": 3,
            },
        ]
        store.save_task_metadata(original)

        updated = [
            {
                "task_id": "retrieval_001",
                "task_type": "retrieval",
                "domain": "tutorials",
                "difficulty": "hard",
                "word_count": 500,
                "tag_count": 8,
            },
        ]
        store.save_task_metadata(updated)

        result = store.get_task_metadata()
        assert len(result) == 1
        assert result[0]["domain"] == "tutorials"
        assert result[0]["difficulty"] == "hard"
        assert result[0]["word_count"] == 500
        assert result[0]["tag_count"] == 8

    def test_get_task_metadata_by_type(
        self, store: ObservatoryStore
    ) -> None:
        """Save 2 tasks of different types, filter by one type, verify only matching returned."""
        metadata = [
            {
                "task_id": "retrieval_001",
                "task_type": "retrieval",
                "domain": "api_docs",
                "difficulty": "easy",
                "word_count": 100,
                "tag_count": 3,
            },
            {
                "task_id": "negative_001",
                "task_type": "negative",
                "domain": "security",
                "difficulty": "hard",
                "word_count": 200,
                "tag_count": 4,
            },
        ]
        store.save_task_metadata(metadata)

        result = store.get_task_metadata(task_type="negative")
        assert len(result) == 1
        assert result[0]["task_id"] == "negative_001"
        assert result[0]["task_type"] == "negative"


# ---------------------------------------------------------------------------
# TestPhaseResultsCost (Task 3)
# ---------------------------------------------------------------------------


class TestPhaseResultsCost:
    """Phase results persist total_cost, total_tokens, and elapsed_seconds."""

    def test_save_phase_results_with_cost(self, tmp_path: Path) -> None:
        """Save with all 3 cost fields, retrieve, verify values match."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("run-cost", "taguchi", {})
        store.save_phase_results(
            run_id="run-cost",
            main_effects={"axis_1": {"flat": 10.0}},
            anova={"axis_1": {"p_value": 0.01}},
            optimal={"axis_1": "flat"},
            significant_factors=["axis_1"],
            quality_type="larger_is_better",
            total_cost=1.234,
            total_tokens=56789,
            elapsed_seconds=42.5,
        )
        result = store.get_phase_results("run-cost")
        assert result is not None
        assert result["total_cost"] == pytest.approx(1.234)
        assert result["total_tokens"] == 56789
        assert result["elapsed_seconds"] == pytest.approx(42.5)

    def test_phase_results_cost_defaults_to_zero(
        self, tmp_path: Path
    ) -> None:
        """Save without cost fields (using defaults), retrieve, verify 0.0/0/0.0."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("run-default", "taguchi", {})
        store.save_phase_results(
            run_id="run-default",
            main_effects={"axis_2": {"v1": 8.0}},
            anova={"axis_2": {"p_value": 0.05}},
            optimal={"axis_2": "v1"},
            significant_factors=["axis_2"],
            quality_type="smaller_is_better",
        )
        result = store.get_phase_results("run-default")
        assert result is not None
        assert result["total_cost"] == pytest.approx(0.0)
        assert result["total_tokens"] == 0
        assert result["elapsed_seconds"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TestPhaseResultsInteractions (Task 5)
# ---------------------------------------------------------------------------


class TestPhaseResultsInteractions:
    """Phase results persist interaction_effects as JSON."""

    def test_save_phase_results_with_interactions(
        self, tmp_path: Path
    ) -> None:
        """Save with interaction_effects list, retrieve, verify round-trip."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("run-interactions", "taguchi", {})
        interactions = [
            {
                "factor1": "A",
                "factor2": "B",
                "ss": 12.5,
                "df": 1,
                "ms": 12.5,
                "f_ratio": 4.2,
                "p_value": 0.05,
            },
            {
                "factor1": "A",
                "factor2": "C",
                "ss": 3.1,
                "df": 2,
                "ms": 1.55,
                "f_ratio": 0.8,
                "p_value": 0.45,
            },
        ]
        store.save_phase_results(
            run_id="run-interactions",
            main_effects={"axis_1": {"flat": 10.0}},
            anova={"axis_1": {"p_value": 0.01}},
            optimal={"axis_1": "flat"},
            significant_factors=["axis_1"],
            quality_type="larger_is_better",
            interaction_effects=interactions,
        )
        result = store.get_phase_results("run-interactions")
        assert result is not None
        assert result["interaction_effects"] == interactions

    def test_phase_results_interactions_defaults_to_empty(
        self, tmp_path: Path
    ) -> None:
        """Save without interaction_effects (default), retrieve, verify []."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("run-no-interactions", "taguchi", {})
        store.save_phase_results(
            run_id="run-no-interactions",
            main_effects={"axis_2": {"v1": 8.0}},
            anova={"axis_2": {"p_value": 0.05}},
            optimal={"axis_2": "v1"},
            significant_factors=["axis_2"],
            quality_type="smaller_is_better",
        )
        result = store.get_phase_results("run-no-interactions")
        assert result is not None
        assert result["interaction_effects"] == []


# ---------------------------------------------------------------------------
# Bug #205: predicted_sn persistence in phase_results
# Bug #189: prediction_interval and se_prediction persistence
# ---------------------------------------------------------------------------


class TestPhaseResultsPredictionPersistence:
    """Phase results must persist predicted_sn, prediction_interval, and se_prediction."""

    def test_save_and_get_predicted_sn(self, tmp_path: Path) -> None:
        """predicted_sn round-trips through SQLite (bug #205)."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("run-sn", "taguchi", {})
        store.save_phase_results(
            run_id="run-sn",
            main_effects={"axis_1": {"flat": 10.0}},
            anova={"axis_1": {"p_value": 0.01}},
            optimal={"axis_1": "flat"},
            significant_factors=["axis_1"],
            quality_type="larger_is_better",
            predicted_sn=7.42,
        )
        result = store.get_phase_results("run-sn")
        assert result is not None
        assert result["predicted_sn"] == pytest.approx(7.42)

    def test_predicted_sn_defaults_to_none(self, tmp_path: Path) -> None:
        """predicted_sn defaults to None when not provided."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("run-no-sn", "taguchi", {})
        store.save_phase_results(
            run_id="run-no-sn",
            main_effects={"axis_1": {"flat": 10.0}},
            anova={},
            optimal={},
            significant_factors=[],
            quality_type="larger_is_better",
        )
        result = store.get_phase_results("run-no-sn")
        assert result is not None
        assert result["predicted_sn"] is None

    def test_save_and_get_prediction_interval(self, tmp_path: Path) -> None:
        """prediction_interval round-trips through SQLite (bug #189)."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("run-pi", "taguchi", {})
        store.save_phase_results(
            run_id="run-pi",
            main_effects={"axis_1": {"flat": 10.0}},
            anova={},
            optimal={},
            significant_factors=[],
            quality_type="larger_is_better",
            predicted_sn=7.42,
            prediction_interval=(5.1, 9.7),
            se_prediction=1.15,
        )
        result = store.get_phase_results("run-pi")
        assert result is not None
        assert result["prediction_interval"] == pytest.approx([5.1, 9.7])
        assert result["se_prediction"] == pytest.approx(1.15)

    def test_prediction_interval_defaults_to_none(self, tmp_path: Path) -> None:
        """prediction_interval and se_prediction default to None."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("run-no-pi", "taguchi", {})
        store.save_phase_results(
            run_id="run-no-pi",
            main_effects={},
            anova={},
            optimal={},
            significant_factors=[],
            quality_type="larger_is_better",
        )
        result = store.get_phase_results("run-no-pi")
        assert result is not None
        assert result["prediction_interval"] is None
        assert result["se_prediction"] is None


# ---------------------------------------------------------------------------
# TestReportArtifacts (Task 4)
# ---------------------------------------------------------------------------


class TestReportArtifacts:
    """Report artifact persistence for computed report outputs."""

    def test_save_and_get_report_artifact(
        self, store: ObservatoryStore
    ) -> None:
        """Save artifact, retrieve by type, verify data matches."""
        store.create_run("run_001", run_type="taguchi", config={})
        data = {
            "kv_cache": {"hit_rate": 0.85, "miss_rate": 0.15},
            "model": "claude-sonnet",
        }
        store.save_report_artifact("run_001", "kv_cache_analysis", data)
        result = store.get_report_artifact("run_001", "kv_cache_analysis")
        assert result is not None
        assert result["data"] == data
        assert "created_at" in result

    def test_get_nonexistent_artifact(
        self, store: ObservatoryStore
    ) -> None:
        """Verify returns None for missing artifact."""
        store.create_run("run_001", run_type="taguchi", config={})
        result = store.get_report_artifact("run_001", "nonexistent_type")
        assert result is None

    def test_list_report_artifacts(
        self, store: ObservatoryStore
    ) -> None:
        """Save 2 artifacts, list them, verify types."""
        store.create_run("run_001", run_type="taguchi", config={})
        store.save_report_artifact(
            "run_001", "hallucination_summary", {"rate": 0.05}
        )
        store.save_report_artifact(
            "run_001", "kv_cache_analysis", {"hit_rate": 0.9}
        )
        artifacts = store.list_report_artifacts("run_001")
        assert len(artifacts) == 2
        types = [a["artifact_type"] for a in artifacts]
        # Ordered by artifact_type alphabetically
        assert types == ["hallucination_summary", "kv_cache_analysis"]
        for a in artifacts:
            assert "created_at" in a

    def test_artifact_upsert(
        self, store: ObservatoryStore
    ) -> None:
        """Save same (run_id, artifact_type) twice, verify second value wins."""
        store.create_run("run_001", run_type="taguchi", config={})
        store.save_report_artifact(
            "run_001", "synthesis", {"version": 1, "concordance": 0.7}
        )
        store.save_report_artifact(
            "run_001", "synthesis", {"version": 2, "concordance": 0.85}
        )
        result = store.get_report_artifact("run_001", "synthesis")
        assert result is not None
        assert result["data"]["version"] == 2
        assert result["data"]["concordance"] == 0.85
        # Only one row should exist
        artifacts = store.list_report_artifacts("run_001")
        assert len(artifacts) == 1


# ---------------------------------------------------------------------------
# TestLLMCallDetails (Task 6)
# ---------------------------------------------------------------------------


class TestLLMCallDetails:
    """Per-call LLM metrics for multi-call trials."""

    def test_save_and_get_llm_calls(
        self, store: ObservatoryStore
    ) -> None:
        """Create run, record trial, save 2 call details, retrieve, verify."""
        store.create_run("run_001", run_type="taguchi", config={})
        trial_id = store.record_trial(**_make_trial_kwargs("run_001"))
        calls = [
            {
                "call_index": 0,
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "cost": 0.001,
                "api_call_ms": 350.5,
                "cached_tokens": 20,
                "model": "claude-sonnet",
                "provider": "openrouter",
            },
            {
                "call_index": 1,
                "prompt_tokens": 200,
                "completion_tokens": 80,
                "cost": 0.002,
                "api_call_ms": 420.0,
                "cached_tokens": 0,
                "model": "claude-sonnet",
                "provider": "openrouter",
            },
        ]
        store.save_llm_call_details(trial_id, calls)
        result = store.get_llm_call_details(trial_id)
        assert len(result) == 2
        # Ordered by call_index
        assert result[0]["call_index"] == 0
        assert result[0]["prompt_tokens"] == 100
        assert result[0]["completion_tokens"] == 50
        assert result[0]["cost"] == pytest.approx(0.001)
        assert result[0]["api_call_ms"] == pytest.approx(350.5)
        assert result[0]["cached_tokens"] == 20
        assert result[0]["model"] == "claude-sonnet"
        assert result[0]["provider"] == "openrouter"
        assert result[1]["call_index"] == 1
        assert result[1]["prompt_tokens"] == 200
        assert result[1]["completion_tokens"] == 80
        assert result[1]["cost"] == pytest.approx(0.002)
        assert result[1]["api_call_ms"] == pytest.approx(420.0)
        assert result[1]["cached_tokens"] == 0
        assert result[1]["model"] == "claude-sonnet"
        assert result[1]["provider"] == "openrouter"

    def test_get_empty_calls(
        self, store: ObservatoryStore
    ) -> None:
        """Create run, record trial without saving call details, verify empty list."""
        store.create_run("run_001", run_type="taguchi", config={})
        trial_id = store.record_trial(**_make_trial_kwargs("run_001"))
        result = store.get_llm_call_details(trial_id)
        assert result == []

    def test_multiple_trials_independent(
        self, store: ObservatoryStore
    ) -> None:
        """Save call details for 2 trials, verify each trial's calls are independent."""
        store.create_run("run_001", run_type="taguchi", config={})
        trial_id_1 = store.record_trial(
            **_make_trial_kwargs("run_001", task_id="task_1", repetition=1)
        )
        trial_id_2 = store.record_trial(
            **_make_trial_kwargs("run_001", task_id="task_2", repetition=1)
        )
        calls_1 = [
            {
                "call_index": 0,
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "cost": 0.001,
                "api_call_ms": 300.0,
                "cached_tokens": 10,
                "model": "claude-sonnet",
                "provider": "openrouter",
            },
        ]
        calls_2 = [
            {
                "call_index": 0,
                "prompt_tokens": 200,
                "completion_tokens": 80,
                "cost": 0.002,
                "api_call_ms": 400.0,
                "cached_tokens": 0,
                "model": "claude-haiku",
                "provider": "anthropic",
            },
            {
                "call_index": 1,
                "prompt_tokens": 150,
                "completion_tokens": 60,
                "cost": 0.0015,
                "api_call_ms": 250.0,
                "cached_tokens": 50,
                "model": "claude-haiku",
                "provider": "anthropic",
            },
        ]
        store.save_llm_call_details(trial_id_1, calls_1)
        store.save_llm_call_details(trial_id_2, calls_2)

        result_1 = store.get_llm_call_details(trial_id_1)
        result_2 = store.get_llm_call_details(trial_id_2)

        assert len(result_1) == 1
        assert result_1[0]["prompt_tokens"] == 100
        assert result_1[0]["model"] == "claude-sonnet"

        assert len(result_2) == 2
        assert result_2[0]["prompt_tokens"] == 200
        assert result_2[0]["model"] == "claude-haiku"
        assert result_2[1]["prompt_tokens"] == 150


# ---------------------------------------------------------------------------
# Bug #244: extract_provider utility
# ---------------------------------------------------------------------------


class TestExtractProvider:
    """extract_provider extracts the provider prefix from model strings."""

    def test_openrouter_prefix(self) -> None:
        from agent_evals.observatory.store import extract_provider

        assert extract_provider("openrouter/arcee-ai/trinity:free") == "openrouter"

    def test_nested_provider(self) -> None:
        from agent_evals.observatory.store import extract_provider

        assert extract_provider("openrouter/anthropic/claude-sonnet-4.5") == "openrouter"

    def test_no_slash_returns_none(self) -> None:
        from agent_evals.observatory.store import extract_provider

        assert extract_provider("claude-sonnet") is None

    def test_empty_string_returns_none(self) -> None:
        from agent_evals.observatory.store import extract_provider

        assert extract_provider("") is None

    def test_none_returns_none(self) -> None:
        from agent_evals.observatory.store import extract_provider

        assert extract_provider(None) is None


class TestProviderAutoExtraction:
    """Bug #244: save_llm_call_details auto-extracts provider from model."""

    def test_provider_none_extracted_from_model(
        self, store: ObservatoryStore
    ) -> None:
        """When provider is None, extract it from the model string."""
        store.create_run("run_001", run_type="taguchi", config={})
        trial_id = store.record_trial(**_make_trial_kwargs("run_001"))
        calls = [
            {
                "call_index": 0,
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "cost": 0.001,
                "api_call_ms": 300.0,
                "cached_tokens": 0,
                "model": "openrouter/anthropic/claude-sonnet-4.5",
                "provider": None,
            },
        ]
        store.save_llm_call_details(trial_id, calls)
        result = store.get_llm_call_details(trial_id)
        assert result[0]["provider"] == "openrouter"

    def test_provider_string_none_extracted_from_model(
        self, store: ObservatoryStore
    ) -> None:
        """When provider is literal string 'None', extract from model."""
        store.create_run("run_001", run_type="taguchi", config={})
        trial_id = store.record_trial(**_make_trial_kwargs("run_001"))
        calls = [
            {
                "call_index": 0,
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "cost": 0.001,
                "api_call_ms": 300.0,
                "cached_tokens": 0,
                "model": "openrouter/arcee-ai/trinity:free",
                "provider": "None",
            },
        ]
        store.save_llm_call_details(trial_id, calls)
        result = store.get_llm_call_details(trial_id)
        assert result[0]["provider"] == "openrouter"

    def test_provider_missing_key_extracted_from_model(
        self, store: ObservatoryStore
    ) -> None:
        """When provider key is absent, extract from model string."""
        store.create_run("run_001", run_type="taguchi", config={})
        trial_id = store.record_trial(**_make_trial_kwargs("run_001"))
        calls = [
            {
                "call_index": 0,
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "cost": 0.001,
                "api_call_ms": 300.0,
                "cached_tokens": 0,
                "model": "openrouter/anthropic/claude-sonnet-4.5",
            },
        ]
        store.save_llm_call_details(trial_id, calls)
        result = store.get_llm_call_details(trial_id)
        assert result[0]["provider"] == "openrouter"

    def test_provider_explicit_not_overridden(
        self, store: ObservatoryStore
    ) -> None:
        """When provider is explicitly set, do not override it."""
        store.create_run("run_001", run_type="taguchi", config={})
        trial_id = store.record_trial(**_make_trial_kwargs("run_001"))
        calls = [
            {
                "call_index": 0,
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "cost": 0.001,
                "api_call_ms": 300.0,
                "cached_tokens": 0,
                "model": "openrouter/anthropic/claude-sonnet-4.5",
                "provider": "anthropic",
            },
        ]
        store.save_llm_call_details(trial_id, calls)
        result = store.get_llm_call_details(trial_id)
        assert result[0]["provider"] == "anthropic"

    def test_provider_none_no_slash_in_model(
        self, store: ObservatoryStore
    ) -> None:
        """When provider is None and model has no slash, provider stays None."""
        store.create_run("run_001", run_type="taguchi", config={})
        trial_id = store.record_trial(**_make_trial_kwargs("run_001"))
        calls = [
            {
                "call_index": 0,
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "cost": 0.001,
                "api_call_ms": 300.0,
                "cached_tokens": 0,
                "model": "claude-sonnet",
                "provider": None,
            },
        ]
        store.save_llm_call_details(trial_id, calls)
        result = store.get_llm_call_details(trial_id)
        assert result[0]["provider"] is None


# ---------------------------------------------------------------------------
# Bug #245: Ghost completed runs with zero trials
# ---------------------------------------------------------------------------


class TestFinishRunEmptyGuard:
    """finish_run marks runs with zero trials as 'empty' not 'completed'."""

    def test_finish_run_with_trials_is_completed(
        self, store: ObservatoryStore
    ) -> None:
        """A run with trials finishes as 'completed'."""
        store.create_run("run_001", run_type="taguchi", config={})
        store.record_trial(**_make_trial_kwargs("run_001"))
        store.finish_run("run_001")
        summary = store.get_run_summary("run_001")
        assert summary.status == "completed"

    def test_finish_run_with_zero_trials_is_empty(
        self, store: ObservatoryStore
    ) -> None:
        """A run with zero trials finishes as 'empty'."""
        store.create_run("run_001", run_type="taguchi", config={})
        store.finish_run("run_001")
        summary = store.get_run_summary("run_001")
        assert summary.status == "empty"

    def test_purge_empty_runs_deletes_empties(
        self, store: ObservatoryStore
    ) -> None:
        """purge_empty_runs removes runs with status 'empty'."""
        store.create_run("run_empty", run_type="taguchi", config={})
        store.finish_run("run_empty")
        store.create_run("run_good", run_type="taguchi", config={})
        store.record_trial(**_make_trial_kwargs("run_good"))
        store.finish_run("run_good")

        purged = store.purge_empty_runs()
        assert purged == ["run_empty"]

        runs = store.list_runs()
        run_ids = [r.run_id for r in runs]
        assert "run_empty" not in run_ids
        assert "run_good" in run_ids

    def test_purge_empty_runs_returns_empty_when_none(
        self, store: ObservatoryStore
    ) -> None:
        """purge_empty_runs returns empty list when no empty runs exist."""
        store.create_run("run_001", run_type="taguchi", config={})
        store.record_trial(**_make_trial_kwargs("run_001"))
        store.finish_run("run_001")
        purged = store.purge_empty_runs()
        assert purged == []


# ---------------------------------------------------------------------------
# Bug #246: Zombie active runs never finalized
# ---------------------------------------------------------------------------


class TestReapZombieRuns:
    """reap_stale_runs also catches runs with NULL heartbeat based on created_at."""

    def test_reap_null_heartbeat_old_run(
        self, store: ObservatoryStore
    ) -> None:
        """Active runs with NULL heartbeat and old created_at are reaped."""
        store.create_run("run_zombie", run_type="taguchi", config={})
        # Backdate created_at to simulate a stale run
        with store._connect() as conn:
            old_time = (
                datetime.now(timezone.utc) - timedelta(hours=2)
            ).isoformat()
            conn.execute(
                "UPDATE runs SET created_at = ? WHERE run_id = ?",
                (old_time, "run_zombie"),
            )
        reaped = store.reap_stale_runs(max_age_seconds=3600)
        assert "run_zombie" in reaped
        summary = store.get_run_summary("run_zombie")
        assert summary.status == "failed"

    def test_reap_null_heartbeat_fresh_run_not_reaped(
        self, store: ObservatoryStore
    ) -> None:
        """Active runs with NULL heartbeat but recent created_at are NOT reaped."""
        store.create_run("run_fresh", run_type="taguchi", config={})
        reaped = store.reap_stale_runs(max_age_seconds=3600)
        assert "run_fresh" not in reaped
        summary = store.get_run_summary("run_fresh")
        assert summary.status == "active"

    def test_reap_completed_run_not_reaped(
        self, store: ObservatoryStore
    ) -> None:
        """Completed runs are never reaped, even if old."""
        store.create_run("run_done", run_type="taguchi", config={})
        store.record_trial(**_make_trial_kwargs("run_done"))
        store.finish_run("run_done")
        with store._connect() as conn:
            old_time = (
                datetime.now(timezone.utc) - timedelta(hours=2)
            ).isoformat()
            conn.execute(
                "UPDATE runs SET created_at = ? WHERE run_id = ?",
                (old_time, "run_done"),
            )
        reaped = store.reap_stale_runs(max_age_seconds=3600)
        assert "run_done" not in reaped


# ---------------------------------------------------------------------------
# Bug #239: FK enforcement — PRAGMA foreign_keys must be ON
# ---------------------------------------------------------------------------


class TestForeignKeyEnforcement:
    """Bug #239: FK enforcement disabled — PRAGMA foreign_keys never ON."""

    def test_pragma_foreign_keys_is_on(
        self, store: ObservatoryStore
    ) -> None:
        """Verify PRAGMA foreign_keys returns 1 (ON) for new connections."""
        with store._connect() as conn:
            row = conn.execute("PRAGMA foreign_keys").fetchone()
        assert row[0] == 1

    def test_trial_insert_with_invalid_run_id_raises(
        self, store: ObservatoryStore
    ) -> None:
        """Inserting a trial referencing a non-existent run_id must fail."""
        import sqlite3

        with pytest.raises(sqlite3.IntegrityError):
            store.record_trial(**_make_trial_kwargs("nonexistent_run"))

    def test_trace_insert_with_invalid_trial_id_raises(
        self, store: ObservatoryStore
    ) -> None:
        """Inserting a trace referencing a non-existent trial_id must fail."""
        import sqlite3

        with pytest.raises(sqlite3.IntegrityError):
            store.record_trace(
                trial_id=999999,
                prompt_json=[{"role": "user", "content": "test"}],
                response_text="test response",
            )

    def test_phase_results_with_invalid_run_id_raises(
        self, store: ObservatoryStore
    ) -> None:
        """Inserting phase_results referencing a non-existent run_id must fail."""
        import sqlite3

        with pytest.raises(sqlite3.IntegrityError):
            store.save_phase_results(
                run_id="nonexistent_run",
                main_effects={},
                anova={},
                optimal={},
                significant_factors=[],
                quality_type="larger_is_better",
            )
