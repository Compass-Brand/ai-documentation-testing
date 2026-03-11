"""Tests for observatory schema/persistence bugs #239-#243.

Bug #239: FK enforcement disabled
Bug #240: No screening report file generated in pipeline mode
Bug #241: Report JSONs lack DOE fields
Bug #242: factor_definitions, task_metadata, report_artifacts never populated
Bug #243: parent_run_id is None for confirmation/refinement runs
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_evals.observatory.store import ObservatoryStore
from agent_evals.pipeline import (
    DOEPipeline,
    PhaseResult,
    PipelineConfig,
    _to_dict,
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
) -> dict:
    """Build keyword args for record_trial."""
    return {
        "run_id": run_id,
        "task_id": task_id,
        "task_type": task_type,
        "variant_name": variant_name,
        "repetition": repetition,
        "score": score,
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "cost": 0.001,
        "latency_seconds": 1.5,
        "model": "claude",
        "source": "gold_standard",
    }


def _make_mock_orchestrator(score: float = 0.5) -> MagicMock:
    """Create a mock orchestrator that returns predictable results."""
    orch = MagicMock()
    trial = MagicMock()
    trial.score = score
    trial.cost = 0.01
    trial.total_tokens = 100
    trial.error = None
    trial.metrics = {"oa_row_id": 0}
    result = MagicMock()
    result.run_id = "test-run"
    result.trials = [trial] * 50
    result.total_cost = 0.5
    result.total_tokens = 5000
    result.elapsed_seconds = 10.0
    orch.run.return_value = result
    orch.store = None
    orch.clear_cache.return_value = 0
    orch.config = MagicMock()
    orch.config.eval_config = MagicMock()
    return orch


def _make_variants() -> list[MagicMock]:
    """Create mock variants with metadata for 5 axes, 3 levels each."""
    variants = []
    for axis in range(1, 6):
        for level in ["a", "b", "c"]:
            v = MagicMock()
            m = MagicMock()
            m.axis = axis
            m.name = f"axis{axis}_{level}"
            v.metadata.return_value = m
            variants.append(v)
    return variants


@pytest.fixture
def store(tmp_path: Path) -> ObservatoryStore:
    """Create a fresh ObservatoryStore in a temp directory."""
    return ObservatoryStore(db_path=tmp_path / "observatory.db")


# ---------------------------------------------------------------------------
# Bug #239: FK enforcement disabled
# ---------------------------------------------------------------------------


class TestFKEnforcement:
    """SQLite foreign keys must be enforced by the store."""

    def test_pragma_foreign_keys_enabled(self, store: ObservatoryStore) -> None:
        """PRAGMA foreign_keys should be ON for every connection."""
        conn = store._connect()
        try:
            row = conn.execute("PRAGMA foreign_keys").fetchone()
            assert row[0] == 1, "PRAGMA foreign_keys should be enabled (1)"
        finally:
            conn.close()

    def test_trial_insert_rejects_orphan_run_id(
        self, store: ObservatoryStore
    ) -> None:
        """Inserting a trial with a non-existent run_id must raise IntegrityError."""
        with pytest.raises(sqlite3.IntegrityError):
            store.record_trial(**_make_trial_kwargs(run_id="nonexistent_run"))

    def test_trace_insert_rejects_orphan_trial_id(
        self, store: ObservatoryStore
    ) -> None:
        """Inserting a trace with a non-existent trial_id must raise IntegrityError."""
        with pytest.raises(sqlite3.IntegrityError):
            store.record_trace(
                trial_id=99999,
                prompt_json=[{"role": "user", "content": "hi"}],
                response_text="hello",
            )

    def test_phase_results_reject_orphan_run_id(
        self, store: ObservatoryStore
    ) -> None:
        """Inserting phase_results for non-existent run must raise IntegrityError."""
        with pytest.raises(sqlite3.IntegrityError):
            store.save_phase_results(
                run_id="ghost_run",
                main_effects={},
                anova={},
                optimal={},
                significant_factors=[],
                quality_type="larger_is_better",
            )


# ---------------------------------------------------------------------------
# Bug #240: No screening report file generated in pipeline mode
# ---------------------------------------------------------------------------


class TestScreeningReportFile:
    """Pipeline should generate a screening report artifact after phase 1."""

    def test_save_phase_report_writes_artifact(
        self, tmp_path: Path
    ) -> None:
        """_save_phase_report must write a report_artifacts row to the store."""
        store = ObservatoryStore(db_path=tmp_path / "obs.db")
        store.create_run(
            "screen-001", "taguchi", {},
            phase="screening", pipeline_id="pipe-1",
        )

        orch = _make_mock_orchestrator()
        orch.store = store
        config = PipelineConfig(models=["model-a"])
        pipeline = DOEPipeline(config=config, orchestrator=orch, pipeline_id="pipe-1")
        pipeline._store = store

        # Build a PhaseResult with realistic screening data
        phase_result = PhaseResult(
            run_id="screen-001",
            phase="screening",
            trials=[MagicMock()] * 5,
            total_cost=0.5,
            total_tokens=5000,
            elapsed_seconds=10.0,
            main_effects={"axis_1": {"a": 10.0, "b": 8.0}},
            anova={"axis_1": {"p_value": 0.03, "f_ratio": 5.2}},
            optimal={"axis_1": "a"},
            significant_factors=["axis_1"],
            predicted_sn=10.0,
        )

        pipeline._save_phase_report(phase_result)

        artifact = store.get_report_artifact("screen-001", "phase_report")
        assert artifact is not None, "No phase_report artifact was saved"
        data = artifact["data"]
        assert "main_effects" in data
        assert "anova" in data
        assert "optimal" in data
        assert "significant_factors" in data

    @patch("agent_evals.pipeline.predict_optimal")
    @patch("agent_evals.pipeline.run_anova")
    @patch("agent_evals.pipeline.compute_main_effects")
    @patch("agent_evals.pipeline.compute_sn_ratios")
    @patch("agent_evals.pipeline.build_design")
    def test_run_screening_calls_save_phase_report(
        self,
        mock_build,
        mock_sn,
        mock_me,
        mock_anova,
        mock_pred,
        tmp_path: Path,
    ) -> None:
        """run_screening must call _save_phase_report when store is present."""
        mock_design = MagicMock()
        mock_design.factors = []
        mock_build.return_value = mock_design
        mock_sn.return_value = {0: 10.0}
        mock_me.return_value = {"axis_1": {"a": 10.0, "b": 8.0}}
        mock_anova.return_value = MagicMock(factors=[])
        mock_pred.return_value = MagicMock(
            optimal_assignment={"axis_1": "a"},
            predicted_sn=10.0,
            prediction_interval=(8.0, 12.0),
            se_prediction=1.0,
        )

        store = ObservatoryStore(db_path=tmp_path / "obs.db")
        orch = _make_mock_orchestrator()
        orch.store = store
        orch.run.return_value.run_id = "screen-002"

        store.create_run(
            "screen-002", "taguchi", {},
            phase="screening", pipeline_id="pipe-2",
        )

        config = PipelineConfig(models=["model-a"])
        pipeline = DOEPipeline(config=config, orchestrator=orch, pipeline_id="pipe-2")
        pipeline._store = store

        # Patch both _save_phase_report AND save_phase_results (the latter
        # calls json.dumps on _to_dict output which fails on MagicMock objects)
        with patch.object(pipeline, "_save_phase_report") as mock_save, \
             patch.object(store, "save_phase_results"):
            pipeline.run_screening(
                tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
            )
            mock_save.assert_called_once()
            call_arg = mock_save.call_args[0][0]
            assert call_arg.phase == "screening"


# ---------------------------------------------------------------------------
# Bug #241: Report JSONs lack DOE fields
# ---------------------------------------------------------------------------


class TestReportDOEFields:
    """Report artifacts must include DOE-specific fields."""

    def test_phase_report_includes_phase_and_pipeline(
        self, tmp_path: Path
    ) -> None:
        """Phase report artifact must include phase, pipeline_id, and optimal config."""
        store = ObservatoryStore(db_path=tmp_path / "obs.db")
        store.create_run(
            "screen-003", "taguchi", {},
            phase="screening", pipeline_id="pipe-3",
        )

        orch = _make_mock_orchestrator()
        orch.store = store
        config = PipelineConfig(models=["model-a"])
        pipeline = DOEPipeline(config=config, orchestrator=orch, pipeline_id="pipe-3")
        pipeline._store = store

        phase_result = PhaseResult(
            run_id="screen-003",
            phase="screening",
            trials=[],
            total_cost=0.5,
            total_tokens=5000,
            elapsed_seconds=10.0,
            main_effects={"axis_1": {"a": 10.0, "b": 8.0}},
            anova={"axis_1": {"p_value": 0.03}},
            optimal={"axis_1": "a"},
            significant_factors=["axis_1"],
            predicted_sn=10.0,
        )

        pipeline._save_phase_report(phase_result)

        artifact = store.get_report_artifact("screen-003", "phase_report")
        assert artifact is not None
        data = artifact["data"]
        assert data["phase"] == "screening"
        assert data["pipeline_id"] == "pipe-3"
        assert data["optimal"] == {"axis_1": "a"}
        assert data["significant_factors"] == ["axis_1"]
        assert data["predicted_sn"] == 10.0
        assert data["main_effects"] == {"axis_1": {"a": 10.0, "b": 8.0}}

    def test_confirmation_report_includes_confirmation_data(
        self, tmp_path: Path
    ) -> None:
        """Confirmation phase report must include confirmation validation data."""
        store = ObservatoryStore(db_path=tmp_path / "obs.db")
        store.create_run(
            "conf-001", "taguchi", {},
            phase="confirmation", pipeline_id="pipe-4",
        )

        orch = _make_mock_orchestrator()
        orch.store = store
        config = PipelineConfig(models=["model-a"])
        pipeline = DOEPipeline(config=config, orchestrator=orch, pipeline_id="pipe-4")
        pipeline._store = store

        phase_result = PhaseResult(
            run_id="conf-001",
            phase="confirmation",
            trials=[],
            confirmation={
                "within_interval": True,
                "sigma_deviation": 0.3,
                "observed_sn": 11.5,
            },
        )

        pipeline._save_phase_report(phase_result)

        artifact = store.get_report_artifact("conf-001", "phase_report")
        assert artifact is not None
        data = artifact["data"]
        assert data["phase"] == "confirmation"
        assert data["confirmation"]["within_interval"] is True


# ---------------------------------------------------------------------------
# Bug #242: factor_definitions, task_metadata, report_artifacts never populated
# ---------------------------------------------------------------------------


class TestMetadataTablePopulation:
    """factor_definitions and task_metadata must be populated during pipeline runs."""

    def test_save_factor_definitions_from_variants(
        self, tmp_path: Path
    ) -> None:
        """_save_factor_definitions must write variant axes to factor_definitions table."""
        store = ObservatoryStore(db_path=tmp_path / "obs.db")
        store.create_run(
            "screen-005", "taguchi", {},
            phase="screening", pipeline_id="pipe-5",
        )

        orch = _make_mock_orchestrator()
        orch.store = store
        config = PipelineConfig(models=["model-a"])
        pipeline = DOEPipeline(config=config, orchestrator=orch, pipeline_id="pipe-5")
        pipeline._store = store

        variants = _make_variants()  # 5 axes, 3 levels each
        pipeline._save_factor_definitions("screen-005", variants)

        defs = store.get_factor_definitions("screen-005")
        assert len(defs) > 0, "factor_definitions table should be populated"
        factor_names = {d["factor_name"] for d in defs}
        # All 5 axes should be present
        for axis in range(1, 6):
            assert f"axis_{axis}" in factor_names
        # Each axis should have 3 levels
        axis_1_levels = [d for d in defs if d["factor_name"] == "axis_1"]
        assert len(axis_1_levels) == 3

    def test_save_factor_definitions_excludes_axis_0(
        self, tmp_path: Path
    ) -> None:
        """_save_factor_definitions must skip axis 0 (baselines)."""
        store = ObservatoryStore(db_path=tmp_path / "obs.db")
        store.create_run("screen-006", "taguchi", {})

        orch = _make_mock_orchestrator()
        orch.store = store
        config = PipelineConfig(models=["model-a"])
        pipeline = DOEPipeline(config=config, orchestrator=orch)
        pipeline._store = store

        # Mix of axis 0 baselines and real axes
        variants = []
        for name in ["baseline_a", "baseline_b"]:
            v = MagicMock()
            m = MagicMock()
            m.axis = 0
            m.name = name
            v.metadata.return_value = m
            variants.append(v)
        for axis in [1, 2]:
            for level in ["x", "y"]:
                v = MagicMock()
                m = MagicMock()
                m.axis = axis
                m.name = f"axis{axis}_{level}"
                v.metadata.return_value = m
                variants.append(v)

        pipeline._save_factor_definitions("screen-006", variants)

        defs = store.get_factor_definitions("screen-006")
        factor_names = {d["factor_name"] for d in defs}
        assert "axis_0" not in factor_names
        assert "axis_1" in factor_names
        assert "axis_2" in factor_names

    def test_save_task_metadata_from_tasks(
        self, tmp_path: Path
    ) -> None:
        """_save_task_metadata must write task definitions to task_metadata table."""
        store = ObservatoryStore(db_path=tmp_path / "obs.db")

        orch = _make_mock_orchestrator()
        orch.store = store
        config = PipelineConfig(models=["model-a"])
        pipeline = DOEPipeline(config=config, orchestrator=orch)
        pipeline._store = store

        # Build tasks that match the expected structure (task.definition.task_id)
        task1 = MagicMock()
        task1.definition.task_id = "t1"
        task1.definition.type = "retrieval"
        task1.definition.metadata = {
            "domain": "api",
            "difficulty": "hard",
            "word_count": 500,
            "tag_count": 3,
        }

        task2 = MagicMock()
        task2.definition.task_id = "t2"
        task2.definition.type = "disambiguation"
        task2.definition.metadata = {
            "domain": "general",
            "difficulty": "easy",
            "word_count": 200,
            "tag_count": 1,
        }

        pipeline._save_task_metadata([task1, task2])

        metadata = store.get_task_metadata()
        assert len(metadata) >= 2, "task_metadata table should be populated"
        task_ids = {m["task_id"] for m in metadata}
        assert "t1" in task_ids
        assert "t2" in task_ids

        # Verify field values for task t1
        t1_meta = next(m for m in metadata if m["task_id"] == "t1")
        assert t1_meta["task_type"] == "retrieval"
        assert t1_meta["domain"] == "api"
        assert t1_meta["difficulty"] == "hard"

    def test_pipeline_run_populates_factor_definitions(
        self, tmp_path: Path
    ) -> None:
        """DOEPipeline.run() must call _save_factor_definitions after screening."""
        store = ObservatoryStore(db_path=tmp_path / "obs.db")

        orch = _make_mock_orchestrator()
        orch.store = store

        config = PipelineConfig(models=["model-a"])
        pipeline = DOEPipeline(config=config, orchestrator=orch, pipeline_id="pipe-6")
        pipeline._store = store

        with patch.object(pipeline, "_save_factor_definitions") as mock_fd, \
             patch.object(pipeline, "_save_task_metadata"), \
             patch.object(pipeline, "run_screening") as mock_screen, \
             patch.object(pipeline, "run_confirmation") as mock_conf, \
             patch.object(pipeline, "run_refinement") as mock_ref:
            mock_screen.return_value = PhaseResult(
                run_id="s1", phase="screening", trials=[],
                significant_factors=["axis_1"],
                optimal={"axis_1": "a"},
            )
            mock_conf.return_value = PhaseResult(
                run_id="c1", phase="confirmation", trials=[],
            )
            mock_ref.return_value = PhaseResult(
                run_id="r1", phase="refinement", trials=[],
            )

            pipeline.run(
                tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
            )

            mock_fd.assert_called_once()

    def test_pipeline_run_populates_task_metadata(
        self, tmp_path: Path
    ) -> None:
        """DOEPipeline.run() must call _save_task_metadata with tasks."""
        store = ObservatoryStore(db_path=tmp_path / "obs.db")

        orch = _make_mock_orchestrator()
        orch.store = store

        config = PipelineConfig(models=["model-a"])
        pipeline = DOEPipeline(config=config, orchestrator=orch, pipeline_id="pipe-7")
        pipeline._store = store

        tasks = [MagicMock(), MagicMock()]

        with patch.object(pipeline, "_save_task_metadata") as mock_tm, \
             patch.object(pipeline, "_save_factor_definitions"), \
             patch.object(pipeline, "run_screening") as mock_screen, \
             patch.object(pipeline, "run_confirmation") as mock_conf, \
             patch.object(pipeline, "run_refinement") as mock_ref:
            mock_screen.return_value = PhaseResult(
                run_id="s1", phase="screening", trials=[],
                significant_factors=["axis_1"],
                optimal={"axis_1": "a"},
            )
            mock_conf.return_value = PhaseResult(
                run_id="c1", phase="confirmation", trials=[],
            )
            mock_ref.return_value = PhaseResult(
                run_id="r1", phase="refinement", trials=[],
            )

            pipeline.run(
                tasks=tasks, variants=_make_variants(), doc_tree=MagicMock(),
            )

            mock_tm.assert_called_once_with(tasks)


# ---------------------------------------------------------------------------
# Bug #243: parent_run_id is None for confirmation/refinement runs
# ---------------------------------------------------------------------------


class TestParentRunId:
    """Confirmation and refinement runs must set parent_run_id to screening run_id."""

    def test_confirmation_passes_parent_run_id_to_orchestrator(self) -> None:
        """run_confirmation must pass screening run_id as parent_run_id."""
        config = PipelineConfig(models=["model-a"], confirmation_reps=5)
        orch = _make_mock_orchestrator(score=0.7)
        pipeline = DOEPipeline(config=config, orchestrator=orch)

        screening = PhaseResult(
            run_id="screening-run-001",
            phase="screening",
            trials=[],
            optimal={"axis_1": "a", "axis_2": "b"},
            significant_factors=["axis_1", "axis_2"],
        )

        with patch("agent_evals.pipeline.validate_confirmation") as mock_val:
            mock_val.return_value = MagicMock(
                within_interval=True,
                sigma_deviation=0.3,
                observed_sn=11.5,
                predicted_sn=12.0,
                prediction_interval=(10.0, 14.0),
            )
            pipeline.run_confirmation(
                screening_result=screening,
                tasks=[],
                variants=_make_variants(),
                doc_tree=MagicMock(),
            )

        orch.run.assert_called_once()
        call_kwargs = orch.run.call_args.kwargs
        assert "parent_run_id" in call_kwargs, (
            "orchestrator.run() must receive parent_run_id kwarg"
        )
        assert call_kwargs["parent_run_id"] == "screening-run-001"

    @patch("agent_evals.pipeline.compute_interactions")
    @patch("agent_evals.pipeline.predict_optimal")
    @patch("agent_evals.pipeline.run_anova")
    @patch("agent_evals.pipeline.compute_main_effects")
    @patch("agent_evals.pipeline.compute_sn_ratios")
    @patch("agent_evals.pipeline.build_design")
    def test_refinement_passes_parent_run_id_to_orchestrator(
        self,
        mock_build,
        mock_sn,
        mock_me,
        mock_anova,
        mock_pred,
        mock_interactions,
    ) -> None:
        """run_refinement must pass screening run_id as parent_run_id."""
        mock_build.return_value = MagicMock()
        mock_sn.return_value = {0: 10.0}
        mock_me.return_value = {}
        mock_anova.return_value = MagicMock(factors=[])
        mock_pred.return_value = MagicMock(
            optimal_assignment={}, predicted_sn=0.0,
        )
        mock_interactions.return_value = []

        config = PipelineConfig(models=["model-a"], top_k=2)
        orch = _make_mock_orchestrator()
        pipeline = DOEPipeline(config=config, orchestrator=orch)

        screening = PhaseResult(
            run_id="screening-run-002",
            phase="screening",
            trials=[],
            optimal={"axis_1": "a"},
            significant_factors=["axis_1", "axis_2"],
            main_effects={"axis_1": {"a": 12.0, "b": 10.0}, "axis_2": {"x": 9.0, "y": 7.0}},
        )

        pipeline.run_refinement(
            screening_result=screening,
            tasks=[],
            variants=_make_variants(),
            doc_tree=MagicMock(),
        )

        orch.run.assert_called_once()
        call_kwargs = orch.run.call_args.kwargs
        assert "parent_run_id" in call_kwargs, (
            "orchestrator.run() must receive parent_run_id kwarg"
        )
        assert call_kwargs["parent_run_id"] == "screening-run-002"

    def test_orchestrator_threads_parent_run_id_to_store(
        self, tmp_path: Path
    ) -> None:
        """parent_run_id must be persisted to the runs table in the store."""
        store = ObservatoryStore(db_path=tmp_path / "obs.db")
        store.create_run("parent-run", "taguchi", {}, phase="screening")
        store.create_run(
            "child-run", "taguchi", {},
            phase="confirmation",
            parent_run_id="parent-run",
        )

        with store._connect() as conn:
            row = conn.execute(
                "SELECT parent_run_id FROM runs WHERE run_id = ?",
                ("child-run",),
            ).fetchone()
        assert row is not None
        assert row["parent_run_id"] == "parent-run"

    def test_orchestrator_run_accepts_parent_run_id(self) -> None:
        """EvalOrchestrator.run() must accept and forward parent_run_id."""
        from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig

        config = OrchestratorConfig(
            models=["test-model"],
            api_key="fake",
            mode="full",
        )

        # Build orchestrator with a mock store
        orch = EvalOrchestrator(config)
        mock_store = MagicMock()
        orch.store = mock_store
        orch.tracker = MagicMock()

        # Patch the runner to avoid actual LLM calls
        with patch.object(orch, "_run_full") as mock_run:
            mock_result = MagicMock()
            mock_result.trials = []
            mock_result.total_cost = 0.0
            mock_result.total_tokens = 0
            mock_result.elapsed_seconds = 0.0
            mock_result.graceful_shutdown = False
            mock_run.return_value = mock_result

            orch.run(
                tasks=[],
                variants=[],
                doc_tree=MagicMock(),
                phase="confirmation",
                pipeline_id="pipe-x",
                parent_run_id="parent-screening",
                mode="full",
            )

        # Verify create_run was called with parent_run_id
        mock_store.create_run.assert_called_once()
        call_kwargs = mock_store.create_run.call_args.kwargs
        assert call_kwargs.get("parent_run_id") == "parent-screening"
