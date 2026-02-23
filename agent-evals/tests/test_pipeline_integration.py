"""End-to-end integration tests for the DOE pipeline.

Verifies that all pipeline components work together:
schema, data models, pipeline phases, CLI flags, API routes.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_evals.pipeline import DOEPipeline, PipelineConfig, PhaseResult, PipelineResult
from agent_evals.observatory.store import ObservatoryStore


class TestPipelineIntegration:
    """Integration tests spanning multiple pipeline components."""

    def test_pipeline_config_defaults(self) -> None:
        """PipelineConfig has sensible defaults for all fields."""
        config = PipelineConfig(models=["model-a"])
        assert config.mode == "auto"
        assert config.quality_type == "larger_is_better"
        assert config.alpha == 0.05
        assert config.top_k == 3
        assert config.screening_reps == 3
        assert config.confirmation_reps == 5

    def test_pipeline_result_aggregates_phases(self) -> None:
        """PipelineResult correctly stores all three phase results."""
        screening = PhaseResult(run_id="r1", phase="screening", trials=[])
        confirmation = PhaseResult(run_id="r2", phase="confirmation", trials=[])
        refinement = PhaseResult(run_id="r3", phase="refinement", trials=[])
        result = PipelineResult(
            pipeline_id="pipe-1",
            screening=screening,
            confirmation=confirmation,
            refinement=refinement,
            final_optimal={"structure": "nested"},
            total_trials=150,
            total_cost=5.0,
            elapsed_seconds=30.0,
        )
        assert result.pipeline_id == "pipe-1"
        assert result.screening.phase == "screening"
        assert result.confirmation.phase == "confirmation"
        assert result.refinement.phase == "refinement"
        assert result.final_optimal == {"structure": "nested"}

    def test_store_phase_results_roundtrip(self, tmp_path: Path) -> None:
        """Phase results survive a save/load roundtrip through the store."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("r1", "taguchi", {"mode": "taguchi"})
        store.save_phase_results(
            run_id="r1",
            main_effects={"structure": {"flat": 10.0, "nested": 12.3}},
            anova={"structure": {"p_value": 0.001, "omega_squared": 0.089}},
            optimal={"structure": "nested"},
            significant_factors=["structure"],
            quality_type="larger_is_better",
        )
        results = store.get_phase_results("r1")
        assert results is not None
        assert results["main_effects"]["structure"]["nested"] == 12.3
        assert results["anova"]["structure"]["p_value"] == 0.001
        assert results["optimal"]["structure"] == "nested"
        assert "structure" in results["significant_factors"]

    def test_store_pipeline_runs_query(self, tmp_path: Path) -> None:
        """Pipeline runs are retrievable by pipeline_id."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run(
            "r1", "taguchi", {"mode": "taguchi"},
            phase="screening", pipeline_id="pipe-1",
        )
        store.create_run(
            "r2", "taguchi", {"mode": "taguchi"},
            phase="confirmation", pipeline_id="pipe-1",
        )
        store.create_run(
            "r3", "taguchi", {"mode": "taguchi"},
            phase="screening", pipeline_id="pipe-2",
        )
        runs = store.get_pipeline_runs("pipe-1")
        assert len(runs) == 2
        run_ids = {r.run_id for r in runs}
        assert run_ids == {"r1", "r2"}

    def test_full_pipeline_auto_mode(self) -> None:
        """Full auto-mode pipeline runs all three phases and aggregates results."""
        config = PipelineConfig(models=["model-a"], mode="auto")
        orch = MagicMock()
        trial = MagicMock()
        trial.score = 0.75
        trial.cost = 0.01
        trial.total_tokens = 100
        trial.metrics = {"oa_row_id": 0}
        result = MagicMock()
        result.run_id = "test-run"
        result.trials = [trial] * 10
        result.total_cost = 0.1
        result.total_tokens = 1000
        result.elapsed_seconds = 5.0
        orch.run.return_value = result

        pipeline = DOEPipeline(config=config, orchestrator=orch)

        with patch("agent_evals.pipeline.build_design"), \
             patch("agent_evals.pipeline.compute_sn_ratios") as mock_sn, \
             patch("agent_evals.pipeline.compute_main_effects") as mock_me, \
             patch("agent_evals.pipeline.run_anova") as mock_anova, \
             patch("agent_evals.pipeline.predict_optimal") as mock_pred, \
             patch("agent_evals.pipeline.validate_confirmation") as mock_val:
            mock_sn.return_value = {0: 10.5}
            mock_me.return_value = {"structure": {"flat": 10.0, "nested": 12.0}}
            mock_anova.return_value = MagicMock()
            mock_anova.return_value.factors = [
                MagicMock(factor_name="structure", p_value=0.001, omega_squared=0.089),
            ]
            mock_pred.return_value = MagicMock()
            mock_pred.return_value.optimal_assignment = {"structure": "nested"}
            mock_val.return_value = MagicMock(
                within_interval=True,
                sigma_deviation=0.3,
                observed_sn=10.2,
                predicted_sn=10.5,
                prediction_interval=(9.0, 12.0),
            )

            # Create mock variants
            v1 = MagicMock()
            v1.metadata.return_value = MagicMock(axis=1, name="flat")
            v2 = MagicMock()
            v2.metadata.return_value = MagicMock(axis=1, name="nested")
            variants = [v1, v2]

            pipeline_result = pipeline.run(
                tasks=[], variants=variants, doc_tree=MagicMock(),
            )

            assert pipeline_result.screening.phase == "screening"
            assert pipeline_result.confirmation.phase == "confirmation"
            assert pipeline_result.refinement.phase == "refinement"
            assert pipeline_result.pipeline_id == pipeline._pipeline_id

    def test_semi_mode_stops_on_rejection(self) -> None:
        """Semi-mode pipeline stops when callback returns False."""
        config = PipelineConfig(models=["model-a"], mode="semi")
        orch = MagicMock()
        trial = MagicMock()
        trial.score = 0.5
        trial.cost = 0.01
        trial.total_tokens = 100
        trial.metrics = {"oa_row_id": 0}
        result = MagicMock()
        result.run_id = "test-run"
        result.trials = [trial] * 10
        result.total_cost = 0.1
        result.total_tokens = 1000
        result.elapsed_seconds = 5.0
        orch.run.return_value = result

        pipeline = DOEPipeline(config=config, orchestrator=orch)

        with patch("agent_evals.pipeline.build_design"), \
             patch("agent_evals.pipeline.compute_sn_ratios") as mock_sn, \
             patch("agent_evals.pipeline.compute_main_effects"), \
             patch("agent_evals.pipeline.run_anova") as mock_anova, \
             patch("agent_evals.pipeline.predict_optimal") as mock_pred:
            mock_sn.return_value = {0: 10.5}
            mock_anova.return_value = MagicMock()
            mock_anova.return_value.factors = []
            mock_pred.return_value = MagicMock()
            mock_pred.return_value.optimal_assignment = {}

            v1 = MagicMock()
            v1.metadata.return_value = MagicMock(axis=1, name="flat")
            variants = [v1]

            # Callback rejects after screening
            pipeline_result = pipeline.run(
                tasks=[], variants=variants, doc_tree=MagicMock(),
                phase_callback=lambda _: False,
            )

            # Should only have screening, no confirmation or refinement
            assert pipeline_result.screening is not None
            assert pipeline_result.confirmation is None
            assert pipeline_result.refinement is None


class TestCLIPipelineFlags:
    """Verify CLI parses pipeline-related flags correctly."""

    def test_pipeline_flag_parsed(self) -> None:
        """--pipeline flag is stored in parsed args."""
        from agent_evals.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["--mode", "taguchi", "--pipeline", "auto"])
        assert args.pipeline == "auto"

    def test_quality_type_flag_parsed(self) -> None:
        """--quality-type flag is stored in parsed args."""
        from agent_evals.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["--quality-type", "smaller_is_better"])
        assert args.quality_type == "smaller_is_better"

    def test_top_k_and_alpha_flags_parsed(self) -> None:
        """--top-k and --alpha flags are parsed with correct types."""
        from agent_evals.cli import build_parser

        parser = build_parser()
        args = parser.parse_args(["--top-k", "5", "--alpha", "0.01"])
        assert args.top_k == 5
        assert args.alpha == pytest.approx(0.01)


class TestWebAPIPipelineRoutes:
    """Verify pipeline API routes respond correctly."""

    @pytest.fixture()
    def client(self, tmp_path: Path):
        from agent_evals.observatory.tracker import EventTracker
        from agent_evals.observatory.web.server import create_app
        from fastapi.testclient import TestClient

        store = ObservatoryStore(tmp_path / "test.db")
        tracker = EventTracker(store=store)
        app = create_app(store=store, tracker=tracker)
        return TestClient(app), store

    def test_list_pipelines_empty(self, client) -> None:
        tc, _ = client
        response = tc.get("/api/pipelines")
        assert response.status_code == 200
        assert response.json() == []

    def test_pipeline_detail_with_runs(self, client) -> None:
        tc, store = client
        store.create_run(
            "r1", "taguchi", {"mode": "taguchi"},
            phase="screening", pipeline_id="pipe-1",
        )
        store.finish_run("r1")
        response = tc.get("/api/pipelines/pipe-1")
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_id"] == "pipe-1"
        assert len(data["runs"]) == 1

    def test_run_analysis_returns_data(self, client) -> None:
        tc, store = client
        store.create_run("r1", "taguchi", {"mode": "taguchi"})
        store.save_phase_results(
            run_id="r1",
            main_effects={"s": {"a": 1.0}},
            anova={"s": {"p": 0.01}},
            optimal={"s": "a"},
            significant_factors=["s"],
            quality_type="larger_is_better",
        )
        response = tc.get("/api/runs/r1/analysis")
        assert response.status_code == 200
        data = response.json()
        assert "main_effects" in data

    def test_run_analysis_404_for_missing(self, client) -> None:
        tc, _ = client
        response = tc.get("/api/runs/nonexistent/analysis")
        assert response.status_code == 404

    def test_approve_pipeline(self, client) -> None:
        tc, store = client
        store.create_run(
            "r1", "taguchi", {"mode": "taguchi"},
            phase="screening", pipeline_id="pipe-1",
        )
        response = tc.post("/api/pipelines/pipe-1/approve")
        assert response.status_code == 200
        assert response.json()["approved"] is True
