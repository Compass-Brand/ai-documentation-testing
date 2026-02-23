"""Tests for EvalOrchestrator -- mode routing, telemetry, and dashboard.

Covers E5-S1: Orchestrator with run() method, telemetry wiring, mode
routing, report generation, and dashboard lifecycle.
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_evals.observatory.tracker import TrackerEvent
from agent_evals.orchestrator import (
    EvalOrchestrator,
    OrchestratorConfig,
    OrchestratorResult,
)
from agent_evals.runner import EvalRunConfig, EvalRunResult, TrialResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_trial(
    task_id: str = "retrieval_001",
    score: float = 0.8,
    cost: float = 0.001,
) -> TrialResult:
    return TrialResult(
        task_id=task_id,
        task_type="retrieval",
        variant_name="flat",
        repetition=1,
        score=score,
        metrics={},
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        cost=cost,
        latency_seconds=0.5,
        response="test response",
        cached=False,
        source="gold_standard",
    )


def _make_eval_run_result(
    trials: list[TrialResult] | None = None,
) -> EvalRunResult:
    if trials is None:
        trials = [_make_trial()]
    return EvalRunResult(
        config=EvalRunConfig(),
        trials=trials,
        total_cost=sum(t.cost for t in trials if t.cost is not None),
        total_tokens=sum(t.total_tokens for t in trials),
        elapsed_seconds=1.0,
    )


def _make_taguchi_run_result(
    trials: list[TrialResult] | None = None,
) -> MagicMock:
    """Create a mock TaguchiRunResult with the same shape."""
    if trials is None:
        trials = [_make_trial()]
    result = MagicMock()
    result.trials = trials
    result.total_cost = sum(t.cost for t in trials if t.cost is not None)
    result.total_tokens = sum(t.total_tokens for t in trials)
    result.elapsed_seconds = 1.0
    result.config = EvalRunConfig()
    result.design = MagicMock()
    return result


def _make_mock_client(model_name: str = "mock-model") -> MagicMock:
    client = MagicMock()
    client.model = model_name
    gen = MagicMock()
    gen.content = f"response from {model_name}"
    gen.prompt_tokens = 10
    gen.completion_tokens = 5
    gen.total_tokens = 15
    gen.cost = 0.001
    gen.model = model_name
    gen.generation_id = None
    client.complete.return_value = gen
    return client


def _make_mock_task(task_id: str = "retrieval_001") -> MagicMock:
    task = MagicMock()
    task.definition.task_id = task_id
    task.definition.type = "retrieval"
    task.build_prompt.return_value = [
        {"role": "user", "content": "test question"},
    ]
    task.score_response.return_value = 0.8
    return task


def _make_mock_variant(name: str = "flat") -> MagicMock:
    variant = MagicMock()
    meta = MagicMock()
    meta.name = name
    meta.token_estimate = 100
    variant.metadata.return_value = meta
    variant.render.return_value = f"rendered {name}"
    return variant


def _make_orchestrator(
    tmp_path: Path,
    mode: str = "full",
    dashboard: bool = False,
    report_format: str | None = None,
    models: list[str] | None = None,
) -> EvalOrchestrator:
    """Create an EvalOrchestrator with a temp db path."""
    config = OrchestratorConfig(
        mode=mode,
        models=models or ["mock-model"],
        api_key="test-key",
        db_path=tmp_path / "test_observatory.db",
        dashboard=dashboard,
        report_format=report_format,
        temperature=0.3,
    )
    return EvalOrchestrator(config)


# ---------------------------------------------------------------------------
# TestModeRouting
# ---------------------------------------------------------------------------


class TestModeRouting:
    """run() routes to the correct runner based on mode."""

    def test_full_mode_routes_to_eval_runner(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path, mode="full")
        trials = [_make_trial(), _make_trial(task_id="retrieval_002")]
        eval_result = _make_eval_run_result(trials)

        with (
            patch.object(orch, "_run_full", return_value=eval_result) as mock_full,
            patch.object(orch, "_run_taguchi") as mock_taguchi,
        ):
            result = orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
            )

        mock_full.assert_called_once()
        mock_taguchi.assert_not_called()
        assert result.mode == "full"
        assert len(result.trials) == 2

    def test_taguchi_mode_routes_to_taguchi_runner(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(tmp_path, mode="taguchi")
        trials = [_make_trial()]
        taguchi_result = _make_taguchi_run_result(trials)

        mock_design = MagicMock()
        mock_lookup = {"flat": _make_mock_variant()}

        with (
            patch.object(
                orch, "_run_taguchi", return_value=taguchi_result
            ) as mock_tag,
            patch.object(orch, "_run_full") as mock_full,
        ):
            result = orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
                design=mock_design,
                variant_lookup=mock_lookup,
            )

        mock_tag.assert_called_once()
        mock_full.assert_not_called()
        assert result.mode == "taguchi"

    def test_runner_type_property_full(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path, mode="full")
        assert orch.runner_type == "eval"

    def test_runner_type_property_taguchi(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path, mode="taguchi")
        assert orch.runner_type == "taguchi"

    def test_default_mode_is_full(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            models=["m"],
            api_key="key",
            db_path=tmp_path / "obs.db",
        )
        assert config.mode == "full"
        orch = EvalOrchestrator(config)
        assert orch.runner_type == "eval"


# ---------------------------------------------------------------------------
# TestTelemetryWiring
# ---------------------------------------------------------------------------


class TestTelemetryWiring:
    """EventTracker receives events during a run."""

    def test_tracker_receives_trial_events(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path, mode="full")

        received_events: list[TrackerEvent] = []
        orch.tracker.add_listener(lambda e: received_events.append(e))

        trials = [_make_trial(), _make_trial(task_id="retrieval_002")]
        eval_result = _make_eval_run_result(trials)

        def fake_run_full(
            tasks, variants, doc_tree, eval_config, progress_callback, source
        ):
            for i, trial in enumerate(trials):
                progress_callback(i + 1, len(trials), trial)
            return eval_result

        with patch.object(orch, "_run_full", side_effect=fake_run_full):
            orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
            )

        completed_events = [
            e for e in received_events if e.event_type == "trial_completed"
        ]
        assert len(completed_events) == 2

    def test_tracker_stats_updated_after_run(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path, mode="full")

        trials = [
            _make_trial(cost=0.01),
            _make_trial(task_id="t2", cost=0.02),
        ]
        eval_result = _make_eval_run_result(trials)

        def fake_run_full(
            tasks, variants, doc_tree, eval_config, progress_callback, source
        ):
            for i, trial in enumerate(trials):
                progress_callback(i + 1, len(trials), trial)
            return eval_result

        with patch.object(orch, "_run_full", side_effect=fake_run_full):
            orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
            )

        stats = orch.tracker.stats
        assert stats["total_trials"] == 2
        assert stats["total_cost"] == pytest.approx(0.03)

    def test_tracker_event_data_has_trial_info(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(tmp_path, mode="full")

        received_events: list[TrackerEvent] = []
        orch.tracker.add_listener(lambda e: received_events.append(e))

        trials = [_make_trial(task_id="task_A", score=0.95, cost=0.005)]
        eval_result = _make_eval_run_result(trials)

        def fake_run_full(
            tasks, variants, doc_tree, eval_config, progress_callback, source
        ):
            for i, trial in enumerate(trials):
                progress_callback(i + 1, len(trials), trial)
            return eval_result

        with patch.object(orch, "_run_full", side_effect=fake_run_full):
            orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
            )

        completed = [
            e for e in received_events if e.event_type == "trial_completed"
        ]
        assert len(completed) == 1
        data = completed[0].data
        assert data["task_id"] == "task_A"
        assert data["score"] == 0.95
        assert data["cost"] == pytest.approx(0.005)


# ---------------------------------------------------------------------------
# TestReportGeneration
# ---------------------------------------------------------------------------


class TestReportGeneration:
    """Report generation when report_format is configured."""

    def test_report_generated_when_format_configured(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(tmp_path, report_format="html")
        trials = [_make_trial()]
        eval_result = _make_eval_run_result(trials)

        with patch.object(orch, "_run_full", return_value=eval_result):
            result = orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
            )

        assert result.report is not None
        assert result.report.total_trials == 1

    def test_no_report_when_format_is_none(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path, report_format=None)
        trials = [_make_trial()]
        eval_result = _make_eval_run_result(trials)

        with patch.object(orch, "_run_full", return_value=eval_result):
            result = orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
            )

        assert result.report is None

    def test_report_has_correct_breakdowns(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path, report_format="both")
        trials = [
            _make_trial(task_id="r1", score=0.8),
            _make_trial(task_id="r2", score=0.9),
        ]
        eval_result = _make_eval_run_result(trials)

        with patch.object(orch, "_run_full", return_value=eval_result):
            result = orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
            )

        assert result.report is not None
        assert "flat" in result.report.by_variant
        assert "retrieval" in result.report.by_task_type


# ---------------------------------------------------------------------------
# TestOrchestratorResult
# ---------------------------------------------------------------------------


class TestOrchestratorResult:
    """OrchestratorResult captures run metadata."""

    def test_result_has_run_id(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path)
        eval_result = _make_eval_run_result()

        with patch.object(orch, "_run_full", return_value=eval_result):
            result = orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
            )

        assert isinstance(result.run_id, str)
        assert len(result.run_id) == 12

    def test_result_has_cost_and_tokens(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path)
        trials = [_make_trial(cost=0.005)]
        eval_result = _make_eval_run_result(trials)

        with patch.object(orch, "_run_full", return_value=eval_result):
            result = orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
            )

        assert result.total_cost == pytest.approx(0.005)
        assert result.total_tokens == 15
        assert result.elapsed_seconds >= 0

    def test_result_preserves_raw_result(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path)
        eval_result = _make_eval_run_result()

        with patch.object(orch, "_run_full", return_value=eval_result):
            result = orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
            )

        assert result.raw_result is eval_result


# ---------------------------------------------------------------------------
# TestObservatoryStore
# ---------------------------------------------------------------------------


class TestObservatoryStoreIntegration:
    """Observatory store is populated during runs."""

    def test_run_created_in_store(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path)
        eval_result = _make_eval_run_result()

        with patch.object(orch, "_run_full", return_value=eval_result):
            result = orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
            )

        runs = orch.store.list_runs()
        assert len(runs) == 1
        assert runs[0].run_id == result.run_id
        assert runs[0].status == "completed"

    def test_run_type_matches_mode(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path, mode="full")
        eval_result = _make_eval_run_result()

        with patch.object(orch, "_run_full", return_value=eval_result):
            orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
            )

        runs = orch.store.list_runs()
        assert runs[0].run_type == "full"

    def test_store_created(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path)
        assert orch.store is not None

    def test_tracker_created(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path)
        assert orch.tracker is not None


# ---------------------------------------------------------------------------
# TestTaguchiValidation
# ---------------------------------------------------------------------------


class TestTaguchiValidation:
    """Taguchi mode validates required parameters."""

    def test_taguchi_requires_design(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path, mode="taguchi")

        with pytest.raises(ValueError, match="TaguchiDesign is required"):
            orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
                design=None,
                variant_lookup={"flat": _make_mock_variant()},
            )

    def test_taguchi_requires_variant_lookup(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path, mode="taguchi")

        with pytest.raises(ValueError, match="variant_lookup is required"):
            orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
                design=MagicMock(),
                variant_lookup=None,
            )


# ---------------------------------------------------------------------------
# TestDashboard
# ---------------------------------------------------------------------------


class TestDashboard:
    """Dashboard starts in background thread when configured."""

    def test_dashboard_disabled_returns_none(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path, dashboard=False)
        result = orch.start_dashboard()
        assert result is None

    def test_dashboard_enabled_starts_thread(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path, dashboard=True)

        with (
            patch(
                "agent_evals.observatory.web.server.create_app"
            ) as mock_create_app,
            patch("uvicorn.Config") as mock_config_cls,
            patch("uvicorn.Server") as mock_server_cls,
        ):
            mock_app = MagicMock()
            mock_create_app.return_value = mock_app
            mock_server = MagicMock()
            mock_server_cls.return_value = mock_server

            thread = orch.start_dashboard()

            if thread is not None:
                thread.join(timeout=2.0)

        assert thread is not None
        assert thread.name == "observatory-dashboard"
        assert thread.daemon is True

    def test_stop_dashboard_signals_shutdown(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path, dashboard=True)
        mock_thread = MagicMock(spec=threading.Thread)
        mock_server = MagicMock()
        orch._dashboard_thread = mock_thread
        orch._uvicorn_server = mock_server

        orch.stop_dashboard()

        assert orch._dashboard_shutdown.is_set()
        assert mock_server.should_exit is True
        mock_thread.join.assert_called_once_with(timeout=5.0)

    def test_dashboard_default_false(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            models=["m"],
            api_key="key",
            db_path=tmp_path / "obs.db",
        )
        assert config.dashboard is False


# ---------------------------------------------------------------------------
# TestClientPool
# ---------------------------------------------------------------------------


class TestClientPool:
    """Client pool created from model list."""

    def test_client_pool_has_all_models(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(
            tmp_path, models=["model-a", "model-b"]
        )
        assert orch.client_pool.models == ["model-a", "model-b"]

    def test_client_pool_budget(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            models=["m"],
            api_key="key",
            db_path=tmp_path / "obs.db",
            global_budget=10.0,
        )
        orch = EvalOrchestrator(config)
        state = orch.client_pool.get_budget_state()
        assert state["global_budget"] == 10.0


# ---------------------------------------------------------------------------
# TestRunFullIntegration
# ---------------------------------------------------------------------------


class TestRunFullIntegration:
    """Integration test for _run_full using mocked LLM client."""

    def test_run_full_creates_eval_runner(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(tmp_path, mode="full")
        mock_client = _make_mock_client()

        with patch.object(
            orch.client_pool, "get_client", return_value=mock_client
        ), patch("agent_evals.orchestrator.EvalRunner") as mock_runner_cls:
            mock_runner = MagicMock()
            mock_runner.run.return_value = _make_eval_run_result()
            mock_runner_cls.return_value = mock_runner

            orch._run_full(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
                eval_config=EvalRunConfig(),
                progress_callback=None,
                source="gold_standard",
            )

            mock_runner_cls.assert_called_once()
            mock_runner.run.assert_called_once()

    def test_run_taguchi_creates_taguchi_runner(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(
            tmp_path, mode="taguchi", models=["model-a", "model-b"]
        )
        mock_client_a = _make_mock_client("model-a")
        mock_client_b = _make_mock_client("model-b")

        def fake_get_client(name: str) -> MagicMock:
            return {"model-a": mock_client_a, "model-b": mock_client_b}[name]

        taguchi_result = _make_taguchi_run_result()

        with patch.object(
            orch.client_pool, "get_client", side_effect=fake_get_client
        ), patch(
            "agent_evals.taguchi.runner.TaguchiRunner"
        ) as mock_runner_cls:
            mock_runner = MagicMock()
            mock_runner.run.return_value = taguchi_result
            mock_runner_cls.return_value = mock_runner

            orch._run_taguchi(
                tasks=[_make_mock_task()],
                doc_tree=MagicMock(),
                eval_config=EvalRunConfig(),
                design=MagicMock(),
                variant_lookup={"flat": _make_mock_variant()},
                progress_callback=None,
                source="gold_standard",
            )

            mock_runner_cls.assert_called_once()
            mock_runner.run.assert_called_once()


# ---------------------------------------------------------------------------
# TestMultiModel
# ---------------------------------------------------------------------------


class TestPhaseRouting:
    """Phase and pipeline_id flow through orchestrator to store and runner."""

    def test_run_passes_phase_and_pipeline_id_to_store_create_run(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(tmp_path, mode="full")
        eval_result = _make_eval_run_result()

        with patch.object(orch, "_run_full", return_value=eval_result), \
             patch.object(orch.store, "create_run", wraps=orch.store.create_run) as mock_create:
            orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
                phase="screening",
                pipeline_id="pipe_001",
            )

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs.get("phase") == "screening"
        assert call_kwargs.kwargs.get("pipeline_id") == "pipe_001"

    def test_run_passes_phase_to_taguchi_runner(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(tmp_path, mode="taguchi")
        taguchi_result = _make_taguchi_run_result()

        with patch.object(
            orch, "_run_taguchi", return_value=taguchi_result
        ) as mock_tag:
            orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
                design=MagicMock(),
                variant_lookup={"flat": _make_mock_variant()},
                phase="confirmation",
            )

        mock_tag.assert_called_once()
        call_kwargs = mock_tag.call_args
        assert call_kwargs.kwargs.get("phase") == "confirmation"

    def test_run_defaults_phase_and_pipeline_id_to_none(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(tmp_path, mode="full")
        eval_result = _make_eval_run_result()

        with patch.object(orch, "_run_full", return_value=eval_result), \
             patch.object(orch.store, "create_run", wraps=orch.store.create_run) as mock_create:
            orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
            )

        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs.get("phase") is None
        assert call_kwargs.kwargs.get("pipeline_id") is None

    def test_trial_oa_row_id_and_phase_passed_to_tracker(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(tmp_path, mode="full")

        trial = _make_trial()
        trial.metrics["oa_row_id"] = 3
        trial.metrics["phase"] = "screening"
        trials = [trial]
        eval_result = _make_eval_run_result(trials)

        with patch.object(
            orch.tracker, "record_trial", wraps=orch.tracker.record_trial
        ) as mock_record, \
             patch.object(orch, "_run_full") as mock_full:

            def fake_run_full(
                tasks, variants, doc_tree, eval_config, progress_callback, source
            ):
                for i, t in enumerate(trials):
                    progress_callback(i + 1, len(trials), t)
                return eval_result

            mock_full.side_effect = fake_run_full
            orch.run(
                tasks=[_make_mock_task()],
                variants=[_make_mock_variant()],
                doc_tree=MagicMock(),
            )

        mock_record.assert_called_once()
        call_kwargs = mock_record.call_args
        assert call_kwargs.kwargs.get("oa_row_id") == 3
        assert call_kwargs.kwargs.get("phase") == "screening"

    def test_taguchi_run_passes_phase_through_to_runner(
        self, tmp_path: Path
    ) -> None:
        orch = _make_orchestrator(
            tmp_path, mode="taguchi", models=["model-a"]
        )
        mock_client = _make_mock_client("model-a")
        taguchi_result = _make_taguchi_run_result()

        with patch.object(
            orch.client_pool, "get_client", return_value=mock_client
        ), patch(
            "agent_evals.taguchi.runner.TaguchiRunner"
        ) as mock_runner_cls:
            mock_runner = MagicMock()
            mock_runner.run.return_value = taguchi_result
            mock_runner_cls.return_value = mock_runner

            orch._run_taguchi(
                tasks=[_make_mock_task()],
                doc_tree=MagicMock(),
                eval_config=EvalRunConfig(),
                design=MagicMock(),
                variant_lookup={"flat": _make_mock_variant()},
                progress_callback=None,
                source="gold_standard",
                phase="screening",
            )

            run_kwargs = mock_runner.run.call_args
            assert run_kwargs.kwargs.get("phase") == "screening"


class TestMultiModel:
    """Orchestrator manages multiple models."""

    def test_models_list_preserved(self, tmp_path: Path) -> None:
        orch = _make_orchestrator(
            tmp_path, models=["a", "b", "c"]
        )
        assert orch.config.models == ["a", "b", "c"]

    def test_report_format_stored(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            models=["m"],
            api_key="key",
            db_path=tmp_path / "obs.db",
            report_format="both",
        )
        assert config.report_format == "both"

    def test_report_format_default_none(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            models=["m"],
            api_key="key",
            db_path=tmp_path / "obs.db",
        )
        assert config.report_format is None
