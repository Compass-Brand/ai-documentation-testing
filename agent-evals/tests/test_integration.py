"""End-to-end integration tests for the evaluation pipeline.

Covers E5-S2: Integration Tests.
Tests the complete pipeline: config -> orchestrator -> observatory -> API.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_evals.llm.client_pool import LLMClientPool
from agent_evals.observatory.model_catalog import ModelCatalog
from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker
from agent_evals.observatory.web.server import create_app
from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig


class TestOrchestratorIntegration:
    """Orchestrator initializes all subsystems correctly."""

    def test_full_pipeline_init(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            mode="full",
            models=["mock-a", "mock-b"],
            api_key="test-key",
            db_path=tmp_path / "obs.db",
        )
        orch = EvalOrchestrator(config)

        # Verify all subsystems initialized.
        assert orch.store is not None
        assert orch.tracker is not None
        assert orch.client_pool is not None
        assert len(orch.client_pool.models) == 2

    def test_taguchi_mode_init(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            mode="taguchi",
            models=["mock-a"],
            api_key="test-key",
            db_path=tmp_path / "obs.db",
        )
        orch = EvalOrchestrator(config)
        assert orch.runner_type == "taguchi"


class TestObservatoryIntegration:
    """Observatory store and tracker work end-to-end."""

    def test_store_and_tracker_pipeline(self, tmp_path: Path) -> None:
        """Trials recorded via tracker appear in the store."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("integration-run", "test", {"models": ["a"]})
        tracker = EventTracker(store=store)

        tracker.record_trial(
            run_id="integration-run",
            task_id="t1",
            task_type="retrieval",
            variant_name="flat",
            repetition=1,
            score=0.85,
            prompt_tokens=500,
            completion_tokens=100,
            total_tokens=600,
            cost=0.02,
            latency_seconds=1.5,
            model="mock-a",
        )

        trials = store.get_trials("integration-run")
        assert len(trials) == 1
        assert trials[0].model == "mock-a"

        stats = tracker.stats
        assert stats["total_trials"] == 1
        assert stats["total_cost"] == pytest.approx(0.02)

    def test_multi_model_stats(self, tmp_path: Path) -> None:
        """Per-model breakdowns tracked correctly."""
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("run-1", "test", {})
        tracker = EventTracker(store=store)

        for model, cost in [("mock-a", 0.01), ("mock-b", 0.02), ("mock-a", 0.015)]:
            tracker.record_trial(
                run_id="run-1",
                task_id="t1",
                task_type="retrieval",
                variant_name="flat",
                repetition=1,
                score=0.80,
                prompt_tokens=400,
                completion_tokens=80,
                total_tokens=480,
                cost=cost,
                latency_seconds=1.0,
                model=model,
            )

        stats = tracker.stats
        assert stats["per_model"]["mock-a"]["count"] == 2
        assert stats["per_model"]["mock-b"]["count"] == 1


class TestWebAPIIntegration:
    """Web API responds with data from the observatory."""

    def test_completed_run_in_api(self, tmp_path: Path) -> None:
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("run-1", "test", {})
        store.record_trial(
            run_id="run-1",
            task_id="t1",
            task_type="retrieval",
            variant_name="flat",
            repetition=1,
            score=0.85,
            prompt_tokens=500,
            completion_tokens=100,
            total_tokens=600,
            cost=0.02,
            latency_seconds=1.5,
            model="mock-a",
        )
        store.finish_run("run-1")

        tracker = EventTracker(store=store)
        app = create_app(store=store, tracker=tracker)
        client = TestClient(app)

        response = client.get("/api/runs")
        data = response.json()
        assert len(data) == 1
        assert data[0]["run_id"] == "run-1"
        assert data[0]["status"] == "completed"

    def test_trials_available_via_api(self, tmp_path: Path) -> None:
        store = ObservatoryStore(tmp_path / "test.db")
        store.create_run("run-1", "test", {})
        store.record_trial(
            run_id="run-1",
            task_id="t1",
            task_type="retrieval",
            variant_name="flat",
            repetition=1,
            score=0.85,
            prompt_tokens=500,
            completion_tokens=100,
            total_tokens=600,
            cost=0.02,
            latency_seconds=1.5,
            model="mock-a",
        )

        tracker = EventTracker(store=store)
        app = create_app(store=store, tracker=tracker)
        client = TestClient(app)

        response = client.get("/api/runs/run-1/trials")
        data = response.json()
        assert len(data) == 1
        assert data[0]["model"] == "mock-a"


class TestClientPoolIntegration:
    """Client pool integrates with budget tracking."""

    def test_pool_budget_tracks_across_models(self, tmp_path: Path) -> None:
        pool = LLMClientPool(
            models=["a", "b"],
            api_key="test-key",
            global_budget=1.00,
            model_budgets={"a": 0.50},
        )
        pool.record_cost("a", 0.30)
        pool.record_cost("b", 0.20)

        state = pool.get_budget_state()
        assert state["global_spent"] == pytest.approx(0.50)
        assert not pool.is_global_budget_exceeded()
        assert not pool.is_budget_exceeded("a")

        pool.record_cost("a", 0.25)
        assert pool.is_budget_exceeded("a")


class TestModelCatalogIntegration:
    """Model catalog integrates with sync and filtering."""

    def test_catalog_filter_and_sync(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="free-model", name="Free", context_length=32768,
            prompt_price=0.0, completion_price=0.0,
        )
        catalog.upsert_model(
            id="paid-model", name="Paid", context_length=128000,
            prompt_price=0.005, completion_price=0.010,
        )

        free = catalog.filter_models(free=True)
        assert len(free) == 1

        big_ctx = catalog.filter_models(min_context=100000)
        assert len(big_ctx) == 1
        assert big_ctx[0]["id"] == "paid-model"

        catalog.log_sync(added=2, removed=0, total=2)
        history = catalog.get_sync_history()
        assert len(history) == 1
