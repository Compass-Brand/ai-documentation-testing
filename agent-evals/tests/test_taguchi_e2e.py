"""E2E Taguchi verification tests.

Covers E13: End-to-end smoke tests for the Taguchi DOE pipeline,
source routing through the orchestrator, and dashboard integration.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_evals.cli import _run_evaluation
from agent_evals.observatory.run_manager import RunManager, StartRunRequest
from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _ensure_variants_loaded() -> None:
    """Ensure the variant registry is clean and fully populated.

    Other test files use ``clear_registry()`` with ``autouse=True``, which
    can leave stale entries.  We clear first, then reload canonical variants.
    """
    from agent_evals.variants.registry import clear_registry, load_all

    clear_registry()
    load_all()


@pytest.fixture
def store(tmp_path: Path) -> ObservatoryStore:
    return ObservatoryStore(tmp_path / "test.db")


@pytest.fixture
def tracker(store: ObservatoryStore) -> EventTracker:
    return EventTracker(store=store)


@pytest.fixture
def run_manager(store: ObservatoryStore, tracker: EventTracker) -> RunManager:
    return RunManager(store=store, tracker=tracker)


# ---------------------------------------------------------------------------
# TestSourceRouting: CLI source routing E2E
# ---------------------------------------------------------------------------


class TestSourceRouting:
    """Verify that --source routes correctly through _run_evaluation."""

    def test_gold_standard_source_loads_builtin_tasks(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Default source=gold_standard uses built-in fixture tasks."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
        resolved: dict[str, object] = {
            "model": "openrouter/test/model",
            "mode": "taguchi",
            "dry_run": True,
        }
        result = _run_evaluation(resolved)
        assert result == 0

    def test_dataset_source_requires_preparation(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Non-gold_standard source fails if dataset is not prepared."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")

        monkeypatch.setattr(
            "agent_evals.datasets.cache.DatasetCache.__init__",
            lambda self, **kw: None,
        )
        monkeypatch.setattr(
            "agent_evals.datasets.cache.DatasetCache.is_prepared",
            lambda self, name: False,
        )
        monkeypatch.setattr(
            "agent_evals.datasets.load_all",
            lambda: None,
        )

        resolved: dict[str, object] = {
            "model": "openrouter/test/model",
            "mode": "taguchi",
            "source": "custom-dataset",
        }
        result = _run_evaluation(resolved)
        assert result == 1

    def test_taguchi_dry_run_shows_oa_design(
        self, monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Taguchi dry-run shows OA design info regardless of source."""
        import logging

        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
        resolved: dict[str, object] = {
            "model": "openrouter/test/model",
            "mode": "taguchi",
            "dry_run": True,
        }
        with caplog.at_level(logging.INFO, logger="agent_evals"):
            result = _run_evaluation(resolved)
        assert result == 0
        assert "Taguchi design" in caplog.text


# ---------------------------------------------------------------------------
# TestTaguchiPipelineSmoke: Orchestrator integration
# ---------------------------------------------------------------------------


class TestTaguchiPipelineSmoke:
    """Smoke tests for the Taguchi orchestrator path."""

    def test_taguchi_orchestrator_receives_design(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """EvalOrchestrator.run receives a valid TaguchiDesign."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")

        captured: dict = {}

        def fake_run(self, **kwargs):
            captured.update(kwargs)
            from agent_evals.orchestrator import OrchestratorResult

            return OrchestratorResult(
                run_id="smoke-test",
                mode="taguchi",
                trials=[],
                total_cost=0.0,
                total_tokens=0,
                elapsed_seconds=0.0,
                report=None,
                raw_result=None,
            )

        monkeypatch.setattr(
            "agent_evals.orchestrator.EvalOrchestrator.run",
            fake_run,
        )

        resolved: dict[str, object] = {
            "model": "openrouter/test/model",
            "mode": "taguchi",
        }
        result = _run_evaluation(resolved)
        assert result == 0
        assert "design" in captured
        assert captured["design"].n_runs > 0
        assert "variant_lookup" in captured
        assert len(captured["variant_lookup"]) > 0

    def test_taguchi_with_multiple_models(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Multi-model Taguchi adds model as a factor to the design."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")

        captured: dict = {}

        def fake_run(self, **kwargs):
            captured.update(kwargs)
            from agent_evals.orchestrator import OrchestratorResult

            return OrchestratorResult(
                run_id="multi-model",
                mode="taguchi",
                trials=[],
                total_cost=0.0,
                total_tokens=0,
                elapsed_seconds=0.0,
                report=None,
                raw_result=None,
            )

        monkeypatch.setattr(
            "agent_evals.orchestrator.EvalOrchestrator.run",
            fake_run,
        )

        resolved: dict[str, object] = {
            "model": "openrouter/test/model",
            "mode": "taguchi",
            "models": "model-a,model-b",
        }
        result = _run_evaluation(resolved)
        assert result == 0
        # With 2 models, model becomes a factor
        factor_names = [f.name for f in captured["design"].factors]
        assert "model" in factor_names

    def test_pipeline_mode_routes_to_doe_pipeline(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--pipeline auto routes through DOEPipeline."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")

        pipeline_called = False

        def fake_pipeline_run(self, tasks, variants, doc_tree, **kwargs):
            nonlocal pipeline_called
            pipeline_called = True
            from agent_evals.pipeline import PhaseResult, PipelineResult

            screening = PhaseResult(
                run_id="screen", phase="screening", trials=[],
            )
            return PipelineResult(
                pipeline_id="smoke",
                screening=screening,
                total_cost=0.0,
                elapsed_seconds=0.0,
            )

        monkeypatch.setattr(
            "agent_evals.pipeline.DOEPipeline.run",
            fake_pipeline_run,
        )

        resolved: dict[str, object] = {
            "model": "openrouter/test/model",
            "mode": "taguchi",
            "pipeline": "auto",
        }
        result = _run_evaluation(resolved)
        assert result == 0
        assert pipeline_called is True


# ---------------------------------------------------------------------------
# TestDashboardSourceIntegration: RunManager + source field
# ---------------------------------------------------------------------------


class TestDashboardSourceIntegration:
    """Verify RunManager respects the source field from StartRunRequest."""

    def test_request_with_source_passes_to_execute(
        self,
        store: ObservatoryStore,
        tracker: EventTracker,
        run_manager: RunManager,
    ) -> None:
        """StartRunRequest.source is passed to _execute_run."""
        request = StartRunRequest(model="m", source="repliqa")
        captured: list[StartRunRequest] = []

        def spy_execute(run_id, req):
            captured.append(req)

        with patch.object(run_manager, "_execute_run", side_effect=spy_execute):
            run_manager.start_run(request)

        # Give thread time to start
        import time
        time.sleep(0.1)

        assert len(captured) == 1
        assert captured[0].source == "repliqa"

    def test_request_default_source_is_gold_standard(
        self,
        store: ObservatoryStore,
        tracker: EventTracker,
        run_manager: RunManager,
    ) -> None:
        """Default StartRunRequest has source=gold_standard."""
        request = StartRunRequest(model="m")
        captured: list[StartRunRequest] = []

        def spy_execute(run_id, req):
            captured.append(req)

        with patch.object(run_manager, "_execute_run", side_effect=spy_execute):
            run_manager.start_run(request)

        import time
        time.sleep(0.1)

        assert len(captured) == 1
        assert captured[0].source == "gold_standard"
