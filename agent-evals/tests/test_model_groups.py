"""Tests for model group management with SQLite persistence."""

from __future__ import annotations

import pytest

from agent_evals.observatory.model_catalog import ModelCatalog
from agent_evals.observatory.model_groups import ModelGroup, ModelGroupManager


@pytest.fixture
def catalog(tmp_path):
    return ModelCatalog(db_path=str(tmp_path / "models.db"))


@pytest.fixture
def manager(catalog):
    return ModelGroupManager(catalog=catalog)


@pytest.fixture
def seeded_catalog(catalog):
    """Catalog pre-populated with test models."""
    catalog.upsert_model(
        id="anthropic/claude-haiku",
        name="Claude Haiku",
        context_length=200000,
        prompt_price=0.25e-06,
        completion_price=1.25e-06,
    )
    catalog.upsert_model(
        id="openai/gpt-4o",
        name="GPT-4o",
        context_length=128000,
        prompt_price=2.5e-06,
        completion_price=10e-06,
    )
    catalog.upsert_model(
        id="google/gemini-flash",
        name="Gemini Flash",
        context_length=1000000,
        prompt_price=0.75e-06,
        completion_price=3e-06,
    )
    return catalog


class TestGroupSchema:
    """Model groups tables are created."""

    def test_creates_model_groups_table(self, manager):
        cursor = manager._catalog._conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='model_groups'"
        )
        assert cursor.fetchone() is not None

    def test_creates_model_group_members_table(self, manager):
        cursor = manager._catalog._conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='model_group_members'"
        )
        assert cursor.fetchone() is not None


class TestCreateGroup:
    """Create model groups."""

    def test_create_group(self, manager):
        group = manager.create_group("frontier", description="Top-tier models")
        assert group.name == "frontier"
        assert group.description == "Top-tier models"
        assert group.id is not None

    def test_create_group_duplicate_name_raises(self, manager):
        manager.create_group("frontier")
        with pytest.raises(ValueError, match="already exists"):
            manager.create_group("frontier")


class TestAddRemoveMembers:
    """Manage group membership."""

    def test_add_model_to_group(self, manager, seeded_catalog):
        group = manager.create_group("test")
        manager.add_to_group(group.id, ["anthropic/claude-haiku"])
        members = manager.get_group_members(group.id)
        assert len(members) == 1
        assert members[0] == "anthropic/claude-haiku"

    def test_add_multiple_models(self, manager, seeded_catalog):
        group = manager.create_group("test")
        manager.add_to_group(group.id, [
            "anthropic/claude-haiku",
            "openai/gpt-4o",
        ])
        members = manager.get_group_members(group.id)
        assert len(members) == 2

    def test_remove_model_from_group(self, manager, seeded_catalog):
        group = manager.create_group("test")
        manager.add_to_group(group.id, [
            "anthropic/claude-haiku",
            "openai/gpt-4o",
        ])
        manager.remove_from_group(group.id, ["openai/gpt-4o"])
        members = manager.get_group_members(group.id)
        assert len(members) == 1
        assert members[0] == "anthropic/claude-haiku"

    def test_add_nonexistent_model_warns(self, manager, seeded_catalog):
        group = manager.create_group("test")
        warnings = manager.add_to_group(group.id, ["nonexistent/model"])
        assert len(warnings) == 1
        assert "not found" in warnings[0].lower()


class TestListGroups:
    """List and show groups."""

    def test_list_groups_empty(self, manager):
        assert manager.list_groups() == []

    def test_list_groups(self, manager):
        manager.create_group("frontier")
        manager.create_group("budget")
        groups = manager.list_groups()
        assert len(groups) == 2

    def test_show_group(self, manager, seeded_catalog):
        group = manager.create_group("frontier", description="Top models")
        manager.add_to_group(group.id, ["anthropic/claude-haiku"])
        shown = manager.show_group(group.id)
        assert shown.name == "frontier"
        assert len(shown.member_ids) == 1


class TestDeleteGroup:
    """Delete groups."""

    def test_delete_group(self, manager):
        group = manager.create_group("temp")
        manager.delete_group(group.id)
        assert len(manager.list_groups()) == 0

    def test_delete_group_removes_memberships(self, manager, seeded_catalog):
        group = manager.create_group("temp")
        manager.add_to_group(group.id, ["anthropic/claude-haiku"])
        manager.delete_group(group.id)
        cursor = manager._catalog._conn.execute(
            "SELECT COUNT(*) FROM model_group_members WHERE group_id = ?",
            (group.id,),
        )
        assert cursor.fetchone()[0] == 0


class TestValidateModelIds:
    """Validate model IDs against catalog."""

    def test_validate_all_exist(self, manager, seeded_catalog):
        result = manager.validate_model_ids([
            "anthropic/claude-haiku",
            "openai/gpt-4o",
        ])
        assert result.valid == ["anthropic/claude-haiku", "openai/gpt-4o"]
        assert result.missing == []

    def test_validate_with_missing(self, manager, seeded_catalog):
        result = manager.validate_model_ids([
            "anthropic/claude-haiku",
            "nonexistent/model",
        ])
        assert len(result.valid) == 1
        assert len(result.missing) == 1
        assert "nonexistent/model" in result.missing
