"""Tests for model catalog store with filtering and sync logging.

Covers E6-S1: Model Catalog Store.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_evals.observatory.model_catalog import ModelCatalog


class TestModelStorage:
    """Store and retrieve model metadata."""

    def test_store_and_retrieve_by_id(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="anthropic/claude-sonnet-4.5",
            name="Claude Sonnet 4.5",
            context_length=200000,
            prompt_price=0.003,
            completion_price=0.015,
            modality="text+image",
            tokenizer="claude",
        )
        model = catalog.get_model("anthropic/claude-sonnet-4.5")
        assert model is not None
        assert model["name"] == "Claude Sonnet 4.5"
        assert model["context_length"] == 200000

    def test_get_model_not_found_returns_none(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        assert catalog.get_model("nonexistent") is None

    def test_upsert_preserves_first_seen(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="m1", name="M1", context_length=4096,
            prompt_price=0.001, completion_price=0.002,
        )
        first = catalog.get_model("m1")["first_seen"]
        catalog.upsert_model(
            id="m1", name="M1 Updated", context_length=8192,
            prompt_price=0.002, completion_price=0.004,
        )
        updated = catalog.get_model("m1")
        assert updated["first_seen"] == first
        assert updated["name"] == "M1 Updated"
        assert updated["context_length"] == 8192

    def test_upsert_updates_last_seen(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="m1", name="M1", context_length=4096,
            prompt_price=0.001, completion_price=0.002,
        )
        first_last_seen = catalog.get_model("m1")["last_seen"]
        catalog.upsert_model(
            id="m1", name="M1", context_length=4096,
            prompt_price=0.001, completion_price=0.002,
        )
        updated_last_seen = catalog.get_model("m1")["last_seen"]
        assert updated_last_seen >= first_last_seen

    def test_mark_removed_sets_timestamp(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="old", name="Old", context_length=4096,
            prompt_price=0.0, completion_price=0.0,
        )
        catalog.mark_removed("old")
        model = catalog.get_model("old")
        assert model["removed_at"] is not None

    def test_get_active_excludes_removed(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        for i in range(5):
            catalog.upsert_model(
                id=f"m{i}", name=f"M{i}", context_length=4096,
                prompt_price=0.0, completion_price=0.0,
            )
        catalog.mark_removed("m0")
        active = catalog.get_active_models()
        assert len(active) == 4
        assert all(m["id"] != "m0" for m in active)

    def test_stored_model_has_required_fields(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="m1", name="M1", context_length=4096,
            prompt_price=0.001, completion_price=0.002,
            modality="text", tokenizer="gpt",
            supported_params=["tools"],
        )
        model = catalog.get_model("m1")
        required_fields = [
            "id", "name", "context_length", "prompt_price",
            "completion_price", "modality", "tokenizer",
            "supported_params", "first_seen", "last_seen", "removed_at",
            "created",
        ]
        for field_name in required_fields:
            assert field_name in model, f"Missing field: {field_name}"

    def test_upsert_stores_created_timestamp(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="m1", name="M1", context_length=4096,
            prompt_price=0.001, completion_price=0.002,
            created=1700000000,
        )
        model = catalog.get_model("m1")
        assert model["created"] == 1700000000

    def test_created_defaults_to_none(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="m1", name="M1", context_length=4096,
            prompt_price=0.001, completion_price=0.002,
        )
        model = catalog.get_model("m1")
        assert model["created"] is None

    def test_upsert_preserves_created_on_update(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="m1", name="M1", context_length=4096,
            prompt_price=0.001, completion_price=0.002,
            created=1700000000,
        )
        catalog.upsert_model(
            id="m1", name="M1 Updated", context_length=8192,
            prompt_price=0.002, completion_price=0.004,
            created=1700000000,
        )
        model = catalog.get_model("m1")
        assert model["created"] == 1700000000


class TestModelFiltering:
    """Filter models by various criteria."""

    def test_filter_free_models(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="free", name="Free", context_length=4096,
            prompt_price=0.0, completion_price=0.0,
        )
        catalog.upsert_model(
            id="paid", name="Paid", context_length=4096,
            prompt_price=0.003, completion_price=0.015,
        )
        results = catalog.filter_models(free=True)
        assert len(results) == 1
        assert results[0]["id"] == "free"

    def test_filter_max_price(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        for price in [0.001, 0.005, 0.010]:
            catalog.upsert_model(
                id=f"m{price}", name="M", context_length=4096,
                prompt_price=price, completion_price=price,
            )
        results = catalog.filter_models(max_price=0.005)
        assert len(results) == 2

    def test_filter_min_context(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        for ctx in [4096, 32768, 200000]:
            catalog.upsert_model(
                id=f"m{ctx}", name="M", context_length=ctx,
                prompt_price=0.0, completion_price=0.0,
            )
        results = catalog.filter_models(min_context=32768)
        assert len(results) == 2

    def test_filter_modality(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="text", name="T", context_length=4096,
            prompt_price=0.0, completion_price=0.0, modality="text",
        )
        catalog.upsert_model(
            id="multi", name="M", context_length=4096,
            prompt_price=0.0, completion_price=0.0, modality="text+image",
        )
        results = catalog.filter_models(modality="text+image")
        assert len(results) == 1
        assert results[0]["id"] == "multi"

    def test_filter_capabilities_and_logic(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="full", name="Full", context_length=4096,
            prompt_price=0.0, completion_price=0.0,
            supported_params=["tools", "json_mode", "streaming"],
        )
        catalog.upsert_model(
            id="partial", name="Partial", context_length=4096,
            prompt_price=0.0, completion_price=0.0,
            supported_params=["tools"],
        )
        results = catalog.filter_models(capabilities=["tools", "json_mode"])
        assert len(results) == 1
        assert results[0]["id"] == "full"

    def test_filter_tokenizer(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="c1", name="C1", context_length=4096,
            prompt_price=0.0, completion_price=0.0, tokenizer="claude",
        )
        catalog.upsert_model(
            id="g1", name="G1", context_length=4096,
            prompt_price=0.0, completion_price=0.0, tokenizer="gpt",
        )
        results = catalog.filter_models(tokenizer="claude")
        assert len(results) == 1
        assert results[0]["id"] == "c1"

    def test_combine_multiple_filters(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="match", name="Match", context_length=100000,
            prompt_price=0.0, completion_price=0.0,
        )
        catalog.upsert_model(
            id="no_ctx", name="No", context_length=4096,
            prompt_price=0.0, completion_price=0.0,
        )
        catalog.upsert_model(
            id="no_price", name="No", context_length=100000,
            prompt_price=0.005, completion_price=0.005,
        )
        results = catalog.filter_models(free=True, min_context=32768)
        assert len(results) == 1
        assert results[0]["id"] == "match"

    def test_filter_excludes_removed_models(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="active", name="Active", context_length=4096,
            prompt_price=0.0, completion_price=0.0,
        )
        catalog.upsert_model(
            id="removed", name="Removed", context_length=4096,
            prompt_price=0.0, completion_price=0.0,
        )
        catalog.mark_removed("removed")
        results = catalog.filter_models(free=True)
        assert len(results) == 1
        assert results[0]["id"] == "active"

    def test_filter_no_criteria_returns_all_active(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="a", name="A", context_length=4096,
            prompt_price=0.0, completion_price=0.0,
        )
        catalog.upsert_model(
            id="b", name="B", context_length=8192,
            prompt_price=0.01, completion_price=0.02,
        )
        results = catalog.filter_models()
        assert len(results) == 2


class TestSyncLogging:
    """Log and retrieve sync run history."""

    def test_log_sync_run(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.log_sync(added=5, removed=2, total=150)
        history = catalog.get_sync_history()
        assert len(history) == 1
        assert history[0]["models_added"] == 5
        assert history[0]["models_removed"] == 2
        assert history[0]["total_count"] == 150

    def test_sync_history_ordered_descending(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.log_sync(added=1, removed=0, total=10)
        catalog.log_sync(added=2, removed=1, total=11)
        catalog.log_sync(added=0, removed=3, total=8)
        history = catalog.get_sync_history()
        assert len(history) == 3
        # Most recent first
        assert history[0]["models_added"] == 0
        assert history[1]["models_added"] == 2
        assert history[2]["models_added"] == 1

    def test_sync_history_has_timestamp(self, tmp_path: Path) -> None:
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.log_sync(added=1, removed=0, total=10)
        history = catalog.get_sync_history()
        assert "timestamp" in history[0]
        assert history[0]["timestamp"] is not None
