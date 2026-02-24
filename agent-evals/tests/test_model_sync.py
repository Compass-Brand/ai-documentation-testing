"""Tests for background model sync with OpenRouter.

Covers E6-S2: Background Model Sync.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agent_evals.observatory.model_catalog import ModelCatalog
from agent_evals.observatory.model_sync import ModelSync, SyncDiff


class TestSyncDiff:
    """Compute differences between local and remote model lists."""

    def test_detect_added_models(self) -> None:
        local = {"a": {}, "b": {}}
        remote = {"a": {}, "b": {}, "c": {"id": "c", "name": "C"}}
        diff = ModelSync.compute_diff(local, remote)
        assert "c" in diff.added

    def test_detect_removed_models(self) -> None:
        local = {"a": {}, "b": {}, "c": {}}
        remote = {"a": {}, "b": {}}
        diff = ModelSync.compute_diff(local, remote)
        assert "c" in diff.removed

    def test_detect_price_changes(self) -> None:
        local = {"a": {"prompt_price": 0.003}}
        remote = {"a": {"id": "a", "prompt_price": 0.005}}
        diff = ModelSync.compute_diff(local, remote)
        assert len(diff.price_changes) == 1
        assert diff.price_changes[0]["old"] == 0.003
        assert diff.price_changes[0]["new"] == 0.005

    def test_no_changes(self) -> None:
        local = {"a": {"prompt_price": 0.003}}
        remote = {"a": {"id": "a", "prompt_price": 0.003}}
        diff = ModelSync.compute_diff(local, remote)
        assert len(diff.added) == 0
        assert len(diff.removed) == 0
        assert len(diff.price_changes) == 0


class TestNormalizeModel:
    """Normalize OpenRouter model response to internal schema."""

    def test_normalize_extracts_created(self) -> None:
        raw = {
            "id": "test/model",
            "name": "Test Model",
            "context_length": 4096,
            "pricing": {"prompt": "0.001", "completion": "0.002"},
            "created": 1700000000,
        }
        result = ModelSync._normalize_model(raw)
        assert result["created"] == 1700000000

    def test_normalize_defaults_created_to_none(self) -> None:
        raw = {
            "id": "test/model",
            "name": "Test Model",
            "context_length": 4096,
            "pricing": {"prompt": "0.001", "completion": "0.002"},
        }
        result = ModelSync._normalize_model(raw)
        assert result["created"] is None


class TestModelSyncExecution:
    """Execute sync against catalog store."""

    def test_sync_adds_new_models(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        sync = ModelSync(catalog=catalog)
        with patch.object(sync, "fetch_remote_models", return_value=[
            {"id": "new", "name": "New", "context_length": 4096,
             "pricing": {"prompt": "0.001", "completion": "0.002"}},
        ]):
            result = sync.run_sync()
        assert result.added_count == 1
        assert catalog.get_model("new") is not None

    def test_sync_marks_removed_models(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="old", name="Old", context_length=4096,
            prompt_price=0.0, completion_price=0.0,
        )
        sync = ModelSync(catalog=catalog)
        with patch.object(sync, "fetch_remote_models", return_value=[]):
            result = sync.run_sync()
        assert result.removed_count == 1
        model = catalog.get_model("old")
        assert model["removed_at"] is not None

    def test_sync_logs_to_catalog(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        sync = ModelSync(catalog=catalog)
        with patch.object(sync, "fetch_remote_models", return_value=[]):
            sync.run_sync()
        history = catalog.get_sync_history()
        assert len(history) == 1

    def test_api_error_handled_gracefully(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        sync = ModelSync(catalog=catalog)
        with patch.object(
            sync, "fetch_remote_models",
            side_effect=Exception("API error"),
        ):
            result = sync.run_sync()
        assert result.error is not None

    def test_sync_stores_created_timestamp(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        sync = ModelSync(catalog=catalog)
        with patch.object(sync, "fetch_remote_models", return_value=[
            {"id": "new", "name": "New", "context_length": 4096,
             "pricing": {"prompt": "0.001", "completion": "0.002"},
             "created": 1700000000},
        ]):
            sync.run_sync()
        model = catalog.get_model("new")
        assert model["created"] == 1700000000

    def test_sync_updates_existing_model_pricing(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="m1", name="M1", context_length=4096,
            prompt_price=0.001, completion_price=0.002,
        )
        sync = ModelSync(catalog=catalog)
        with patch.object(sync, "fetch_remote_models", return_value=[
            {"id": "m1", "name": "M1 Updated", "context_length": 4096,
             "pricing": {"prompt": "0.005", "completion": "0.010"}},
        ]):
            sync.run_sync()
        model = catalog.get_model("m1")
        assert model["prompt_price"] == pytest.approx(0.005)


class TestPeriodicSync:
    """Schedule and cancel periodic sync."""

    def test_start_periodic_creates_task(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        sync = ModelSync(catalog=catalog, interval_hours=6)
        sync.start_periodic()
        assert sync.is_running
        sync.stop_periodic()

    def test_stop_periodic_cancels_task(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        sync = ModelSync(catalog=catalog, interval_hours=6)
        sync.start_periodic()
        sync.stop_periodic()
        assert not sync.is_running

    def test_double_start_is_safe(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        sync = ModelSync(catalog=catalog, interval_hours=6)
        sync.start_periodic()
        sync.start_periodic()  # Should not crash
        assert sync.is_running
        sync.stop_periodic()

    def test_stop_without_start_is_safe(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        sync = ModelSync(catalog=catalog)
        sync.stop_periodic()  # Should not crash
        assert not sync.is_running
