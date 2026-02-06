"""Tests for scaffold mode."""

from __future__ import annotations

from pathlib import Path

import yaml
from agent_index.models import IndexConfig, TierConfig
from agent_index.scaffold import scaffold_project


class TestScaffoldProject:
    """Tests for the scaffold_project function."""

    def test_creates_directory_structure(self, tmp_path: Path) -> None:
        """scaffold_project creates the expected directory structure."""
        root = tmp_path / "my-project"
        config = IndexConfig(index_name="Test Project")

        scaffold_project(root, config)

        assert root.exists()
        assert (root / ".docs").exists()
        assert (root / ".docs" / "required").exists()
        assert (root / ".docs" / "recommended").exists()
        assert (root / ".docs" / "reference").exists()

    def test_creates_placeholder_llms_md_files(self, tmp_path: Path) -> None:
        """scaffold_project creates placeholder .llms.md files in each tier dir."""
        root = tmp_path / "my-project"
        config = IndexConfig(index_name="Test Project")

        scaffold_project(root, config)

        required_file = root / ".docs" / "required" / "required.llms.md"
        assert required_file.exists()
        content = required_file.read_text()
        assert "Required" in content

        recommended_file = root / ".docs" / "recommended" / "recommended.llms.md"
        assert recommended_file.exists()

        reference_file = root / ".docs" / "reference" / "reference.llms.md"
        assert reference_file.exists()

    def test_creates_config_file(self, tmp_path: Path) -> None:
        """scaffold_project creates an agent-index.yaml config file."""
        root = tmp_path / "my-project"
        config = IndexConfig(index_name="Test Project")

        scaffold_project(root, config)

        config_file = root / "agent-index.yaml"
        assert config_file.exists()

        parsed = yaml.safe_load(config_file.read_text())
        assert parsed["index_name"] == "Test Project"

    def test_returns_list_of_created_paths(self, tmp_path: Path) -> None:
        """scaffold_project returns a list of all created paths."""
        root = tmp_path / "my-project"
        config = IndexConfig(index_name="Test Project")

        created = scaffold_project(root, config)

        assert isinstance(created, list)
        assert len(created) > 0
        # Should include root, .docs, tier dirs, placeholder files, config
        assert root in created
        assert (root / ".docs") in created
        assert (root / "agent-index.yaml") in created

    def test_with_custom_config(self, tmp_path: Path) -> None:
        """scaffold_project respects custom tier names in config."""
        root = tmp_path / "custom-project"
        config = IndexConfig(
            index_name="Custom Project",
            tiers=[
                TierConfig(name="critical", instruction="Must read these."),
                TierConfig(name="optional", instruction="Read if needed."),
            ],
        )

        scaffold_project(root, config)

        assert (root / ".docs" / "critical").exists()
        assert (root / ".docs" / "optional").exists()
        assert not (root / ".docs" / "required").exists()

        critical_file = root / ".docs" / "critical" / "critical.llms.md"
        assert critical_file.exists()
        content = critical_file.read_text()
        assert "Critical" in content

    def test_does_not_overwrite_existing_files(self, tmp_path: Path) -> None:
        """scaffold_project does not overwrite files that already exist."""
        root = tmp_path / "existing-project"
        root.mkdir()
        docs = root / ".docs"
        docs.mkdir()
        required_dir = docs / "required"
        required_dir.mkdir()

        # Create a file that already exists
        existing_file = required_dir / "required.llms.md"
        existing_file.write_text("# My existing content")

        # Also create a config file
        config_file = root / "agent-index.yaml"
        config_file.write_text("index_name: Existing\n")

        config = IndexConfig(index_name="New Project")
        created = scaffold_project(root, config)

        # Existing file should NOT be overwritten
        assert existing_file.read_text() == "# My existing content"
        assert config_file.read_text() == "index_name: Existing\n"

        # Existing items should not be in the created list
        assert existing_file not in created
        assert config_file not in created

    def test_creates_with_empty_tiers(self, tmp_path: Path) -> None:
        """scaffold_project works with an empty tiers list."""
        root = tmp_path / "no-tiers"
        config = IndexConfig(index_name="No Tiers", tiers=[])

        created = scaffold_project(root, config)

        assert root.exists()
        assert (root / ".docs").exists()
        assert (root / "agent-index.yaml").exists()
        assert len(created) > 0
