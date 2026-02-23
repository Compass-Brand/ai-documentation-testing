"""Tests for observatory web dashboard API and HTML endpoints.

Covers E3-S4: Observatory Web Dashboard.
Uses FastAPI TestClient for endpoint testing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker
from agent_evals.observatory.web.server import create_app


@pytest.fixture
def _store(tmp_path: Path) -> ObservatoryStore:
    store = ObservatoryStore(tmp_path / "test.db")
    return store


@pytest.fixture
def _tracker(_store: ObservatoryStore) -> EventTracker:
    return EventTracker(store=_store)


@pytest.fixture
def client(_store: ObservatoryStore, _tracker: EventTracker) -> TestClient:
    app = create_app(store=_store, tracker=_tracker)
    return TestClient(app)


def _record_trial(store: ObservatoryStore, run_id: str, **kwargs) -> None:
    """Helper to record a trial in the store."""
    defaults = {
        "task_id": "t1",
        "task_type": "retrieval",
        "variant_name": "flat",
        "repetition": 1,
        "score": 0.85,
        "prompt_tokens": 500,
        "completion_tokens": 100,
        "total_tokens": 600,
        "cost": 0.02,
        "latency_seconds": 1.5,
        "model": "claude",
    }
    defaults.update(kwargs)
    store.record_trial(run_id=run_id, **defaults)


class TestDashboardHTML:
    """Dashboard serves HTML pages."""

    def test_root_returns_200(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_root_contains_dashboard_elements(self, client: TestClient) -> None:
        response = client.get("/")
        html = response.text
        assert "Dashboard" in html


class TestRunsAPI:
    """API endpoints for run management."""

    def test_list_runs_empty(self, client: TestClient) -> None:
        response = client.get("/api/runs")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_runs_with_data(
        self, client: TestClient, _store: ObservatoryStore
    ) -> None:
        _store.create_run("run-1", "test", {})
        response = client.get("/api/runs")
        data = response.json()
        assert len(data) == 1
        assert data[0]["run_id"] == "run-1"

    def test_get_run_summary(
        self, client: TestClient, _store: ObservatoryStore
    ) -> None:
        _store.create_run("run-1", "test", {})
        _record_trial(_store, "run-1")
        response = client.get("/api/runs/run-1")
        assert response.status_code == 200
        data = response.json()
        assert data["run"]["run_id"] == "run-1"
        assert data["total_trials"] == 1
        assert data["completed_trials"] == 1
        assert data["mean_score"] == pytest.approx(0.85)
        assert "flat" in data["by_variant"]
        assert data["by_variant"]["flat"]["trial_count"] == 1
        assert data["total_tokens"] == 600
        assert data["by_model"]["claude"]["trial_count"] == 1

    def test_finish_run(
        self, client: TestClient, _store: ObservatoryStore
    ) -> None:
        _store.create_run("run-1", "test", {})
        response = client.post("/api/runs/run-1/finish")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        # Verify the run is now completed in the store
        summary = _store.get_run_summary("run-1")
        assert summary.status == "completed"

    def test_finish_run_not_found(self, client: TestClient) -> None:
        response = client.post("/api/runs/nonexistent/finish")
        assert response.status_code == 404

    def test_get_run_not_found(self, client: TestClient) -> None:
        response = client.get("/api/runs/nonexistent")
        assert response.status_code == 404

    def test_get_run_trials(
        self, client: TestClient, _store: ObservatoryStore
    ) -> None:
        _store.create_run("run-1", "test", {})
        _record_trial(_store, "run-1", model="claude")
        _record_trial(_store, "run-1", model="gpt")
        response = client.get("/api/runs/run-1/trials")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


class TestSSE:
    """Server-Sent Events for live streaming."""

    def test_sse_route_registered(self, client: TestClient) -> None:
        """Verify the SSE stream route exists in the app's route table."""
        routes = [r.path for r in client.app.routes]
        assert "/api/runs/{run_id}/stream" in routes


class TestHistoryAPI:
    """Historical analytics endpoints."""

    def test_cost_trend_empty(self, client: TestClient) -> None:
        response = client.get("/api/history/cost-trend")
        assert response.status_code == 200
        assert response.json() == []

    def test_cost_trend_with_runs(
        self, client: TestClient, _store: ObservatoryStore
    ) -> None:
        _store.create_run("run-1", "test", {})
        _record_trial(_store, "run-1", cost=0.05)
        _store.finish_run("run-1")
        response = client.get("/api/history/cost-trend")
        data = response.json()
        assert len(data) == 1
        assert data[0]["total_cost"] == pytest.approx(0.05)


class TestCompareAPI:
    """Run comparison endpoint."""

    def test_compare_two_runs(
        self, client: TestClient, _store: ObservatoryStore
    ) -> None:
        _store.create_run("run-1", "test", {})
        _store.create_run("run-2", "test", {})
        _record_trial(_store, "run-1", score=0.72)
        _record_trial(_store, "run-2", score=0.78)
        response = client.get("/api/compare?ids=run-1,run-2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_compare_missing_params(self, client: TestClient) -> None:
        response = client.get("/api/compare")
        assert response.status_code == 422 or response.status_code == 400


class TestPipelineAPI:
    """Pipeline management endpoints."""

    def test_list_pipelines(
        self, client: TestClient, _store: ObservatoryStore
    ) -> None:
        _store.create_run(
            "r1", "taguchi", {"mode": "taguchi"},
            phase="screening", pipeline_id="pipe-1",
        )
        _store.finish_run("r1")
        response = client.get("/api/pipelines")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["pipeline_id"] == "pipe-1"

    def test_list_pipelines_empty(self, client: TestClient) -> None:
        response = client.get("/api/pipelines")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_pipeline_detail(
        self, client: TestClient, _store: ObservatoryStore
    ) -> None:
        _store.create_run(
            "r1", "taguchi", {"mode": "taguchi"},
            phase="screening", pipeline_id="pipe-1",
        )
        _store.finish_run("r1")
        response = client.get("/api/pipelines/pipe-1")
        assert response.status_code == 200
        data = response.json()
        assert "runs" in data
        assert len(data["runs"]) == 1

    def test_get_pipeline_detail_not_found(
        self, client: TestClient
    ) -> None:
        response = client.get("/api/pipelines/nonexistent")
        assert response.status_code == 404

    def test_get_run_analysis(
        self, client: TestClient, _store: ObservatoryStore
    ) -> None:
        _store.create_run("r1", "taguchi", {"mode": "taguchi"})
        _store.save_phase_results(
            run_id="r1",
            main_effects={"s": {"a": 1.0}},
            anova={"s": {"p": 0.01}},
            optimal={"s": "a"},
            significant_factors=["s"],
            quality_type="larger_is_better",
        )
        response = client.get("/api/runs/r1/analysis")
        assert response.status_code == 200
        data = response.json()
        assert "main_effects" in data
        assert "anova" in data

    def test_get_run_analysis_missing(self, client: TestClient) -> None:
        response = client.get("/api/runs/nonexistent/analysis")
        assert response.status_code == 404

    def test_approve_pipeline(
        self, client: TestClient, _store: ObservatoryStore
    ) -> None:
        _store.create_run(
            "r1", "taguchi", {"mode": "taguchi"},
            phase="screening", pipeline_id="pipe-1",
        )
        response = client.post("/api/pipelines/pipe-1/approve")
        assert response.status_code == 200
        data = response.json()
        assert data["pipeline_id"] == "pipe-1"
        assert data["approved"] is True
