"""Tests for run checkpointing and resume (Part B: Run Checkpointing)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent_evals.observatory.store import ObservatoryStore
from agent_evals.runner import EvalRunConfig, EvalRunner
from agent_evals.taguchi.factors import (
    TaguchiDesign,
    TaguchiExperimentRow,
    TaguchiFactorDef,
)
from agent_evals.taguchi.runner import TaguchiRunner
from conftest import make_mock_client, make_mock_task, make_mock_variant


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


class TestCheckpointWal:
    """checkpoint_wal() runs without error."""

    def test_checkpoint_wal_succeeds(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.create_run("run-1", "test", {})
        store.record_trial(**_trial_kwargs())
        # Should not raise.
        store.checkpoint_wal()

    def test_checkpoint_wal_on_empty_db(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        # Should not raise even with no data.
        store.checkpoint_wal()


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


# ---------------------------------------------------------------------------
# Helpers for runner-level completed_keys tests
# ---------------------------------------------------------------------------


def _mock_doc_tree() -> MagicMock:
    """Minimal mock DocTree."""
    return MagicMock()


# ---------------------------------------------------------------------------
# Step 9: TaguchiRunner completed_keys filtering
# ---------------------------------------------------------------------------


class TestTaguchiRunnerCompletedKeys:
    """TaguchiRunner.run() skips trials in completed_keys."""

    def _make_design(self) -> tuple[TaguchiDesign, dict[str, MagicMock]]:
        """2-row design with one axis factor."""
        factors = [
            TaguchiFactorDef(
                name="axis_1", n_levels=2, level_names=["A", "B"], axis=1,
            ),
        ]
        rows = [
            TaguchiExperimentRow(run_id=1, assignments={"axis_1": "A"}),
            TaguchiExperimentRow(run_id=2, assignments={"axis_1": "B"}),
        ]
        design = TaguchiDesign(
            oa_name="L2", n_runs=2, factors=factors, rows=rows,
            level_counts=[2],
        )
        lookup = {"A": make_mock_variant("A"), "B": make_mock_variant("B")}
        return design, lookup

    def test_no_completed_keys_runs_all(self) -> None:
        design, lookup = self._make_design()
        tasks = [make_mock_task("t1"), make_mock_task("t2")]
        runner = TaguchiRunner(
            clients={"m": make_mock_client()},
            config=EvalRunConfig(repetitions=1),
            design=design,
            variant_lookup=lookup,
        )

        result = runner.run(tasks, _mock_doc_tree(), completed_keys=None)
        # 2 rows x 2 tasks x 1 rep = 4
        assert len(result.trials) == 4

    def test_completed_keys_skips_matching(self) -> None:
        design, lookup = self._make_design()
        tasks = [make_mock_task("t1"), make_mock_task("t2")]
        runner = TaguchiRunner(
            clients={"m": make_mock_client()},
            config=EvalRunConfig(repetitions=1),
            design=design,
            variant_lookup=lookup,
        )

        # Skip row 1 + task t1 (variant name is "A" for row 1)
        completed = {(1, "t1", "A", 1)}
        result = runner.run(tasks, _mock_doc_tree(), completed_keys=completed)
        # 4 total - 1 skipped = 3
        assert len(result.trials) == 3

    def test_all_completed_returns_empty(self) -> None:
        design, lookup = self._make_design()
        tasks = [make_mock_task("t1")]
        runner = TaguchiRunner(
            clients={"m": make_mock_client()},
            config=EvalRunConfig(repetitions=1),
            design=design,
            variant_lookup=lookup,
        )

        completed = {(1, "t1", "A", 1), (2, "t1", "B", 1)}
        result = runner.run(tasks, _mock_doc_tree(), completed_keys=completed)
        assert len(result.trials) == 0

    def test_completed_keys_matches_despite_variant_name_mismatch(self) -> None:
        """Taguchi resume should match on (oa_row_id, task_id, rep) ignoring variant_name.

        This handles the case where the DB stores a variant name that includes
        axis 0 (e.g. 'no-index+A') but the runner's _build_composite produces
        a name without axis 0 (e.g. 'A').
        """
        design, lookup = self._make_design()
        tasks = [make_mock_task("t1")]
        runner = TaguchiRunner(
            clients={"m": make_mock_client()},
            config=EvalRunConfig(repetitions=1),
            design=design,
            variant_lookup=lookup,
        )

        # DB has variant name with axis 0 prefix that differs from runner's composite
        completed = {(1, "t1", "no-index+A", 1)}
        result = runner.run(tasks, _mock_doc_tree(), completed_keys=completed)
        # Should still skip row 1 + t1 despite variant name mismatch
        # 2 rows x 1 task x 1 rep = 2, minus 1 skipped = 1
        assert len(result.trials) == 1


# ---------------------------------------------------------------------------
# Step 10: EvalRunner completed_keys filtering
# ---------------------------------------------------------------------------


class TestEvalRunnerCompletedKeys:
    """EvalRunner.run() skips trials in completed_keys."""

    def test_no_completed_keys_runs_all(self) -> None:
        tasks = [make_mock_task("t1")]
        variants = [make_mock_variant("v1"), make_mock_variant("v2")]
        runner = EvalRunner(client=make_mock_client(), config=EvalRunConfig(repetitions=1))

        result = runner.run(
            tasks, variants, _mock_doc_tree(), completed_keys=None,
        )
        # 1 task x 2 variants x 1 rep = 2
        assert len(result.trials) == 2

    def test_completed_keys_skips_matching(self) -> None:
        tasks = [make_mock_task("t1")]
        variants = [make_mock_variant("v1"), make_mock_variant("v2")]
        runner = EvalRunner(client=make_mock_client(), config=EvalRunConfig(repetitions=1))

        # Full-sweep uses None for oa_row_id
        completed = {(None, "t1", "v1", 1)}
        result = runner.run(
            tasks, variants, _mock_doc_tree(), completed_keys=completed,
        )
        # 2 total - 1 skipped = 1
        assert len(result.trials) == 1
        assert result.trials[0].variant_name == "v2"

    def test_all_completed_returns_empty(self) -> None:
        tasks = [make_mock_task("t1")]
        variants = [make_mock_variant("v1")]
        runner = EvalRunner(client=make_mock_client(), config=EvalRunConfig(repetitions=1))

        completed = {(None, "t1", "v1", 1)}
        result = runner.run(
            tasks, variants, _mock_doc_tree(), completed_keys=completed,
        )
        assert len(result.trials) == 0


# ---------------------------------------------------------------------------
# Step 11: Orchestrator resume wiring
# ---------------------------------------------------------------------------


class TestOrchestratorResume:
    """Orchestrator fetches completed_keys and forwards to runner on resume."""

    def test_resume_calls_store_resume_and_gets_keys(
        self, tmp_path: Path,
    ) -> None:
        store = _make_store(tmp_path)
        store.create_run("run-resume", "taguchi", {})
        store.record_trial(**_trial_kwargs(
            run_id="run-resume", task_id="t1", variant_name="v1",
            repetition=1, oa_row_id=1,
        ))
        store.fail_run("run-resume", error="crashed")

        from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig

        config = OrchestratorConfig(
            models=["mock"],
            api_key="test",
            store=store,
            resume_run_id="run-resume",
        )
        orch = EvalOrchestrator(config)

        # Patch _run_full to capture completed_keys
        captured: dict = {}

        def fake_run_full(
            tasks, variants, doc_tree, eval_config,
            progress_callback, source, completed_keys=None,
        ):
            captured["completed_keys"] = completed_keys
            from agent_evals.runner import EvalRunResult

            return EvalRunResult(
                config=eval_config,
                trials=[],
                total_cost=0,
                total_tokens=0,
                elapsed_seconds=0,
            )

        orch._run_full = fake_run_full  # type: ignore[assignment]

        orch.run(
            tasks=[make_mock_task()],
            variants=[make_mock_variant("v1")],
            doc_tree=_mock_doc_tree(),
        )

        # Verify keys were fetched and forwarded
        assert captured["completed_keys"] is not None
        assert (1, "t1", "v1", 1) in captured["completed_keys"]

        # Verify run is active (not a new run created)
        summary = store.get_run_summary("run-resume")
        assert summary.status == "completed"  # finished after run

    def test_resume_merges_prior_trials_into_result(
        self, tmp_path: Path,
    ) -> None:
        """Resumed run includes prior + new trials in OrchestratorResult."""
        store = _make_store(tmp_path)
        store.create_run("run-merge", "full", {})
        # Record a prior trial (simulating a previous session).
        store.record_trial(**_trial_kwargs(
            run_id="run-merge", task_id="t1", variant_name="v1",
            repetition=1, score=0.9,
        ))
        store.fail_run("run-merge", error="crashed")

        from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig
        from agent_evals.runner import EvalRunConfig, EvalRunResult, TrialResult

        config = OrchestratorConfig(
            models=["mock"],
            api_key="test",
            store=store,
            resume_run_id="run-merge",
        )
        orch = EvalOrchestrator(config)

        # Fake runner returns one NEW trial (t2).
        new_trial = TrialResult(
            task_id="t2",
            task_type="retrieval",
            variant_name="v1",
            repetition=1,
            score=0.75,
            metrics={},
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.001,
            latency_seconds=1.0,
            response="answer",
            cached=False,
            source="gold_standard",
        )

        def fake_run_full(
            tasks, variants, doc_tree, eval_config,
            progress_callback, source, completed_keys=None,
        ):
            return EvalRunResult(
                config=eval_config,
                trials=[new_trial],
                total_cost=0.001,
                total_tokens=150,
                elapsed_seconds=1.0,
            )

        orch._run_full = fake_run_full  # type: ignore[assignment]

        result = orch.run(
            tasks=[make_mock_task()],
            variants=[make_mock_variant("v1")],
            doc_tree=_mock_doc_tree(),
        )

        # Result should contain BOTH the prior trial (t1) and the new one (t2).
        assert len(result.trials) == 2
        task_ids = {t.task_id for t in result.trials}
        assert task_ids == {"t1", "t2"}
        # Totals should reflect all trials.
        assert result.total_cost == pytest.approx(0.002)
        assert result.total_tokens == 300


# ---------------------------------------------------------------------------
# RunSummary.phase field
# ---------------------------------------------------------------------------


class TestRunSummaryPhase:
    """RunSummary includes phase from the runs table."""

    def test_phase_returned_in_summary(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.create_run(
            "run-1", "taguchi", {}, phase="screening", pipeline_id="pipe-1",
        )
        summary = store.get_run_summary("run-1")
        assert summary.phase == "screening"

    def test_phase_in_pipeline_runs(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.create_run(
            "run-1", "taguchi", {}, phase="screening", pipeline_id="pipe-1",
        )
        store.create_run(
            "run-2", "taguchi", {}, phase="confirmation", pipeline_id="pipe-1",
        )
        runs = store.get_pipeline_runs("pipe-1")
        phases = {r.phase for r in runs}
        assert phases == {"screening", "confirmation"}

    def test_phase_none_when_not_set(self, tmp_path: Path) -> None:
        store = _make_store(tmp_path)
        store.create_run("run-1", "full", {})
        summary = store.get_run_summary("run-1")
        assert summary.phase is None


# ---------------------------------------------------------------------------
# Pipeline resume: incomplete phases
# ---------------------------------------------------------------------------


class TestPipelineResumeIncompletePhases:
    """DOEPipeline.run() should resume active/failed phases."""

    def _make_phase_result(self, phase: str, run_id: str = "r1"):
        """Create a minimal PhaseResult for testing."""
        from agent_evals.pipeline import PhaseResult

        return PhaseResult(
            run_id=run_id,
            phase=phase,
            trials=[],
            significant_factors=["axis_1"],
        )

    def test_pipeline_resumes_active_screening(
        self, tmp_path: Path,
    ) -> None:
        """Pipeline with an 'active' screening run should resume it."""
        from agent_evals.pipeline import DOEPipeline, PipelineConfig

        store = _make_store(tmp_path)
        store.create_run(
            "screen-crash", "taguchi", {},
            phase="screening", pipeline_id="pipe-1",
        )

        orch = MagicMock()
        orch.store = store
        pipeline = DOEPipeline(
            config=PipelineConfig(models=["mock"]),
            orchestrator=orch,
            pipeline_id="pipe-1",
        )

        # Patch phase methods to capture resume_run_id
        captured: dict[str, str | None] = {}
        pipeline.run_screening = MagicMock(
            side_effect=lambda *a, **kw: (
                captured.update(screening=kw.get("resume_run_id")),
                self._make_phase_result("screening", "screen-crash"),
            )[1],
        )
        pipeline.run_confirmation = MagicMock(
            return_value=self._make_phase_result("confirmation"),
        )
        pipeline.run_refinement = MagicMock(
            return_value=self._make_phase_result("refinement"),
        )

        pipeline.run(
            tasks=[make_mock_task()],
            variants=[make_mock_variant("v1")],
            doc_tree=_mock_doc_tree(),
        )

        assert captured.get("screening") == "screen-crash"

    def test_pipeline_resumes_failed_screening(
        self, tmp_path: Path,
    ) -> None:
        """Pipeline with a 'failed' screening run should resume it."""
        from agent_evals.pipeline import DOEPipeline, PipelineConfig

        store = _make_store(tmp_path)
        store.create_run(
            "screen-fail", "taguchi", {},
            phase="screening", pipeline_id="pipe-2",
        )
        store.fail_run("screen-fail", error="crashed")

        orch = MagicMock()
        orch.store = store
        pipeline = DOEPipeline(
            config=PipelineConfig(models=["mock"]),
            orchestrator=orch,
            pipeline_id="pipe-2",
        )

        captured: dict[str, str | None] = {}
        pipeline.run_screening = MagicMock(
            side_effect=lambda *a, **kw: (
                captured.update(screening=kw.get("resume_run_id")),
                self._make_phase_result("screening", "screen-fail"),
            )[1],
        )
        pipeline.run_confirmation = MagicMock(
            return_value=self._make_phase_result("confirmation"),
        )
        pipeline.run_refinement = MagicMock(
            return_value=self._make_phase_result("refinement"),
        )

        pipeline.run(
            tasks=[make_mock_task()],
            variants=[make_mock_variant("v1")],
            doc_tree=_mock_doc_tree(),
        )

        assert captured.get("screening") == "screen-fail"

    def test_pipeline_fresh_when_no_existing_runs(
        self, tmp_path: Path,
    ) -> None:
        """No existing runs → no resume_run_id passed to phase methods."""
        from agent_evals.pipeline import DOEPipeline, PipelineConfig

        store = _make_store(tmp_path)
        orch = MagicMock()
        orch.store = store
        pipeline = DOEPipeline(
            config=PipelineConfig(models=["mock"]),
            orchestrator=orch,
            pipeline_id="pipe-3",
        )

        captured: dict[str, str | None] = {}
        pipeline.run_screening = MagicMock(
            side_effect=lambda *a, **kw: (
                captured.update(screening=kw.get("resume_run_id")),
                self._make_phase_result("screening"),
            )[1],
        )
        pipeline.run_confirmation = MagicMock(
            return_value=self._make_phase_result("confirmation"),
        )
        pipeline.run_refinement = MagicMock(
            return_value=self._make_phase_result("refinement"),
        )

        pipeline.run(
            tasks=[make_mock_task()],
            variants=[make_mock_variant("v1")],
            doc_tree=_mock_doc_tree(),
        )

        assert captured.get("screening") is None
