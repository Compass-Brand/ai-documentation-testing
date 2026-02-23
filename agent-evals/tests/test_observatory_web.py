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
        assert data["run_id"] == "run-1"
        assert data["total_trials"] == 1

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
