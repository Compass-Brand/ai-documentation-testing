"""Tests for auto-detect mode."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from agent_index.autodetect import auto_detect, generate_config_yaml
from agent_index.config import load_config
from agent_index.models import IndexConfig


class TestAutoDetect:
    """Tests for the auto_detect function."""

    def test_getting_started_assigned_to_required(self, tmp_path: Path) -> None:
        """Files with 'getting-started' in the name go to the required tier."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "getting-started.md").write_text("# Getting Started")
        (docs / "other.md").write_text("# Other")

        config = auto_detect(tmp_path)

        required_tier = next(t for t in config.tiers if t.name == "required")
        assert any("getting-started" in p for p in required_tier.patterns)

    def test_setup_assigned_to_required(self, tmp_path: Path) -> None:
        """Files with 'setup' in the name go to the required tier."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "setup.md").write_text("# Setup")

        config = auto_detect(tmp_path)

        required_tier = next(t for t in config.tiers if t.name == "required")
        assert any("setup" in p for p in required_tier.patterns)

    def test_install_assigned_to_required(self, tmp_path: Path) -> None:
        """Files with 'install' in the name go to the required tier."""
        (tmp_path / "install.md").write_text("# Installation")

        config = auto_detect(tmp_path)

        required_tier = next(t for t in config.tiers if t.name == "required")
        assert any("install" in p for p in required_tier.patterns)

    def test_api_reference_assigned_to_reference(self, tmp_path: Path) -> None:
        """Files with 'api' or 'reference' in the path go to the reference tier."""
        api_dir = tmp_path / "api"
        api_dir.mkdir()
        (api_dir / "endpoints.md").write_text("# API Endpoints")

        config = auto_detect(tmp_path)

        reference_tier = next(t for t in config.tiers if t.name == "reference")
        assert any("api" in p for p in reference_tier.patterns)

    def test_everything_else_assigned_to_recommended(self, tmp_path: Path) -> None:
        """Files that don't match required or reference go to recommended."""
        (tmp_path / "contributing.md").write_text("# Contributing")
        (tmp_path / "changelog.md").write_text("# Changelog")

        config = auto_detect(tmp_path)

        recommended_tier = next(t for t in config.tiers if t.name == "recommended")
        assert len(recommended_tier.patterns) == 2

    def test_detects_project_name_from_directory(self, tmp_path: Path) -> None:
        """Project name detected from directory name when no package files exist."""
        (tmp_path / "README.md").write_text("# Readme")

        config = auto_detect(tmp_path)

        # tmp_path has a generated name; just verify it's used
        assert config.index_name == tmp_path.name

    def test_detects_project_name_from_package_json(self, tmp_path: Path) -> None:
        """Project name detected from package.json when available."""
        (tmp_path / "package.json").write_text(
            json.dumps({"name": "my-cool-project"})
        )
        (tmp_path / "README.md").write_text("# Readme")

        config = auto_detect(tmp_path)

        assert config.index_name == "my-cool-project"

    def test_detects_project_name_from_pyproject_toml(self, tmp_path: Path) -> None:
        """Project name detected from pyproject.toml when available."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "my-python-pkg"\n'
        )
        (tmp_path / "README.md").write_text("# Readme")

        config = auto_detect(tmp_path)

        assert config.index_name == "my-python-pkg"

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Auto-detect on an empty directory produces a valid config with empty patterns."""
        config = auto_detect(tmp_path)

        assert isinstance(config, IndexConfig)
        assert len(config.tiers) == 3
        # All tiers should have empty patterns
        for tier in config.tiers:
            assert tier.patterns == []


class TestGenerateConfigYaml:
    """Tests for the generate_config_yaml function."""

    def test_produces_valid_yaml(self, tmp_path: Path) -> None:
        """generate_config_yaml produces parseable YAML."""
        (tmp_path / "setup.md").write_text("# Setup")
        config = auto_detect(tmp_path)

        yaml_str = generate_config_yaml(config)
        parsed = yaml.safe_load(yaml_str)

        assert isinstance(parsed, dict)
        assert "index_name" in parsed

    def test_roundtrips_through_load_config(self, tmp_path: Path) -> None:
        """YAML from generate_config_yaml can be loaded back with load_config."""
        (tmp_path / "setup.md").write_text("# Setup")
        config = auto_detect(tmp_path)

        yaml_str = generate_config_yaml(config)

        # Write to a file and load it back
        config_file = tmp_path / "agent-index.yaml"
        config_file.write_text(yaml_str)

        loaded = load_config(config_file)
        assert loaded.index_name == config.index_name
        assert len(loaded.tiers) == len(config.tiers)

    def test_contains_tier_info(self, tmp_path: Path) -> None:
        """YAML output contains tier configuration."""
        (tmp_path / "api.md").write_text("# API")
        config = auto_detect(tmp_path)

        yaml_str = generate_config_yaml(config)
        parsed = yaml.safe_load(yaml_str)

        assert "tiers" in parsed
        tier_names = [t["name"] for t in parsed["tiers"]]
        assert "required" in tier_names
        assert "recommended" in tier_names
        assert "reference" in tier_names
