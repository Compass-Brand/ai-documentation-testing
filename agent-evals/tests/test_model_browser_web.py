"""Tests for web model browser API endpoints and HTML elements.

Covers E6-S5: Model Browser Web UI.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from agent_evals.observatory.model_catalog import ModelCatalog
from agent_evals.observatory.model_groups import ModelGroupManager
from agent_evals.observatory.model_sync import ModelSync
from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker
from agent_evals.observatory.web.server import create_app


@pytest.fixture()
def catalog(tmp_path: Path) -> ModelCatalog:
    cat = ModelCatalog(tmp_path / "models.db")
    # Seed with test models.
    cat.upsert_model(
        id="test-model", name="Test Model", context_length=200000,
        prompt_price=0.003, completion_price=0.015,
        modality="text+image", tokenizer="claude",
        supported_params=["tools", "json_mode"],
    )
    cat.upsert_model(
        id="cheap-model", name="Cheap Model", context_length=4096,
        prompt_price=0.0, completion_price=0.0,
        modality="text", tokenizer="gpt",
        supported_params=["streaming"],
    )
    cat.upsert_model(
        id="big-ctx", name="Big Context", context_length=128000,
        prompt_price=0.001, completion_price=0.002,
        modality="text", tokenizer="claude",
    )
    return cat


@pytest.fixture()
def client(tmp_path: Path, catalog: ModelCatalog) -> TestClient:
    store = ObservatoryStore(tmp_path / "obs.db")
    tracker = EventTracker(store=store)
    group_mgr = ModelGroupManager(catalog)
    sync = ModelSync(catalog=catalog)
    app = create_app(
        store=store, tracker=tracker,
        catalog=catalog, group_manager=group_mgr, model_sync=sync,
    )
    return TestClient(app)


class TestModelAPIEndpoints:
    """REST API endpoints for model browsing."""

    def test_get_models_returns_list(self, client: TestClient) -> None:
        response = client.get("/api/models")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_models_returns_seeded_data(self, client: TestClient) -> None:
        response = client.get("/api/models")
        ids = [m["id"] for m in response.json()]
        assert "test-model" in ids
        assert "cheap-model" in ids

    def test_get_model_by_id(self, client: TestClient) -> None:
        response = client.get("/api/models/test-model")
        assert response.status_code == 200
        assert response.json()["id"] == "test-model"

    def test_get_model_not_found(self, client: TestClient) -> None:
        response = client.get("/api/models/nonexistent")
        assert response.status_code == 404

    def test_get_groups(self, client: TestClient) -> None:
        response = client.get("/api/models/groups")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_group(self, client: TestClient) -> None:
        response = client.post("/api/models/groups", json={
            "name": "test-group", "models": ["test-model"],
        })
        assert response.status_code == 201

    def test_trigger_sync(self, client: TestClient) -> None:
        with patch.object(ModelSync, "fetch_remote_models", return_value=[]):
            response = client.post("/api/models/sync")
        assert response.status_code == 200


class TestModelFilterAPI:
    """Filter models via query parameters."""

    def test_filter_free_models(self, client: TestClient) -> None:
        response = client.get("/api/models?free=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "cheap-model"

    def test_filter_by_max_price(self, client: TestClient) -> None:
        response = client.get("/api/models?max_price=0.001")
        assert response.status_code == 200
        for m in response.json():
            assert m["prompt_price"] <= 0.001

    def test_filter_by_min_context(self, client: TestClient) -> None:
        response = client.get("/api/models?min_context=100000")
        assert response.status_code == 200
        data = response.json()
        for m in data:
            assert m["context_length"] >= 100000

    def test_filter_by_modality(self, client: TestClient) -> None:
        response = client.get("/api/models?modality=text%2Bimage")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "test-model"

    def test_filter_by_capabilities(self, client: TestClient) -> None:
        response = client.get("/api/models?capabilities=tools,json_mode")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "test-model"

    def test_filter_by_tokenizer(self, client: TestClient) -> None:
        response = client.get("/api/models?tokenizer=claude")
        assert response.status_code == 200
        data = response.json()
        assert all(m["tokenizer"] == "claude" for m in data)

    def test_combined_filters(self, client: TestClient) -> None:
        response = client.get("/api/models?max_price=0.005&min_context=32768")
        assert response.status_code == 200

    def test_search_query(self, client: TestClient) -> None:
        response = client.get("/api/models?search=cheap")
        assert response.status_code == 200
        data = response.json()
        assert any("cheap" in m["name"].lower() for m in data)


class TestModelBrowserHTML:
    """Dashboard HTML includes model browser elements."""

    def test_navigation_includes_models_link(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert "Models" in response.text

    def test_models_page_has_filter_panel(self, client: TestClient) -> None:
        response = client.get("/")
        assert "filter-panel" in response.text

    def test_models_page_has_search_bar(self, client: TestClient) -> None:
        response = client.get("/")
        assert "model-search" in response.text

    def test_models_page_has_table_view(self, client: TestClient) -> None:
        response = client.get("/")
        assert "model-table" in response.text

    def test_models_page_has_select_all(self, client: TestClient) -> None:
        response = client.get("/")
        assert "Select All" in response.text

    def test_models_page_has_run_selected(self, client: TestClient) -> None:
        response = client.get("/")
        assert "Run Selected" in response.text

    def test_models_page_has_save_group(self, client: TestClient) -> None:
        response = client.get("/")
        assert "Save as Group" in response.text

    def test_models_page_has_detail_panel(self, client: TestClient) -> None:
        response = client.get("/")
        assert "detail-panel" in response.text

    def test_models_page_has_view_toggle(self, client: TestClient) -> None:
        response = client.get("/")
        assert "view-toggle" in response.text
