"""Tests for config loading functionality."""

from pathlib import Path
from textwrap import dedent

import pytest
from agent_index.config import ConfigError, find_config, load_config
from agent_index.models import IndexConfig


class TestLoadConfigYAML:
    """Tests for loading YAML configuration files."""

    def test_loads_minimal_yaml_config(self, tmp_path: Path) -> None:
        """load_config loads a minimal YAML config file."""
        config_file = tmp_path / "agent-index.yaml"
        config_file.write_text(
            dedent("""
            index_name: "Test Project"
            """).strip()
        )

        config = load_config(config_file)

        assert isinstance(config, IndexConfig)
        assert config.index_name == "Test Project"

    def test_loads_full_yaml_config(self, tmp_path: Path) -> None:
        """load_config loads a complete YAML config with all fields."""
        config_file = tmp_path / "agent-index.yaml"
        config_file.write_text(
            dedent("""
            index_name: "My Project"
            marker_id: "DOCS"
            root_path: "./.docs"
            instruction: "Custom instruction."

            tiers:
              - name: required
                instruction: "Read these files at the start of every session."
                patterns: ["**/README.md", "**/ARCHITECTURE.md"]
              - name: recommended
                instruction: "Read these files when working on related tasks."
                patterns: ["docs/guides/**"]

            sources:
              - type: local
                path: ./docs
              - type: github
                repo: owner/repo
                path: docs/

            file_extensions: [".md", ".mdx", ".rst"]
            ignore_patterns: ["node_modules", "__pycache__"]

            transform_steps:
              - type: passthrough

            output_targets:
              - agents.md
              - claude.md
            """).strip()
        )

        config = load_config(config_file)

        assert config.index_name == "My Project"
        assert config.marker_id == "DOCS"
        assert config.root_path == "./.docs"
        assert len(config.tiers) == 2
        assert config.tiers[0].name == "required"
        assert config.tiers[0].patterns == ["**/README.md", "**/ARCHITECTURE.md"]
        assert len(config.sources) == 2
        assert config.sources[0]["type"] == "local"
        assert config.file_extensions == {".md", ".mdx", ".rst"}
        assert config.output_targets == ["agents.md", "claude.md"]

    def test_loads_yml_extension(self, tmp_path: Path) -> None:
        """load_config handles .yml extension."""
        config_file = tmp_path / "agent-index.yml"
        config_file.write_text('index_name: "YML Test"')

        config = load_config(config_file)

        assert config.index_name == "YML Test"

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """load_config accepts string path."""
        config_file = tmp_path / "agent-index.yaml"
        config_file.write_text('index_name: "String Path"')

        config = load_config(str(config_file))

        assert config.index_name == "String Path"


class TestLoadConfigTOML:
    """Tests for loading TOML configuration files."""

    def test_loads_minimal_toml_config(self, tmp_path: Path) -> None:
        """load_config loads a minimal TOML config file."""
        config_file = tmp_path / "agent-index.toml"
        config_file.write_text('index_name = "TOML Project"')

        config = load_config(config_file)

        assert isinstance(config, IndexConfig)
        assert config.index_name == "TOML Project"

    def test_loads_full_toml_config(self, tmp_path: Path) -> None:
        """load_config loads a complete TOML config with all fields."""
        config_file = tmp_path / "agent-index.toml"
        config_file.write_text(
            dedent("""
            index_name = "My TOML Project"
            marker_id = "DOCS"
            root_path = "./.docs"
            instruction = "Custom instruction."

            file_extensions = [".md", ".mdx"]
            ignore_patterns = ["node_modules"]
            output_targets = ["agents.md"]

            [[tiers]]
            name = "required"
            instruction = "Read these files first."
            patterns = ["**/README.md"]

            [[tiers]]
            name = "recommended"
            instruction = "Read when relevant."
            patterns = ["docs/**"]

            [[sources]]
            type = "local"
            path = "./docs"

            [[transform_steps]]
            type = "passthrough"
            """).strip()
        )

        config = load_config(config_file)

        assert config.index_name == "My TOML Project"
        assert len(config.tiers) == 2
        assert config.tiers[0].name == "required"
        assert len(config.sources) == 1
        assert config.sources[0]["type"] == "local"


class TestLoadConfigErrors:
    """Tests for config loading error handling."""

    def test_file_not_found_error(self, tmp_path: Path) -> None:
        """load_config raises ConfigError for missing file."""
        missing_file = tmp_path / "nonexistent.yaml"

        with pytest.raises(ConfigError) as exc_info:
            load_config(missing_file)

        assert "not found" in str(exc_info.value).lower()
        assert "nonexistent.yaml" in str(exc_info.value)

    def test_unsupported_extension_error(self, tmp_path: Path) -> None:
        """load_config raises ConfigError for unsupported file extension."""
        config_file = tmp_path / "agent-index.json"
        config_file.write_text('{"index_name": "Test"}')

        with pytest.raises(ConfigError) as exc_info:
            load_config(config_file)

        assert "unsupported" in str(exc_info.value).lower()
        assert ".json" in str(exc_info.value)

    def test_yaml_parse_error_includes_line(self, tmp_path: Path) -> None:
        """load_config includes line number for YAML parse errors."""
        config_file = tmp_path / "agent-index.yaml"
        config_file.write_text(
            dedent("""
            index_name: "Test"
            tiers:
              - name: required
                instruction: "Read these"
                patterns:
                  - bad indent
               wrong: "indentation"
            """).strip()
        )

        with pytest.raises(ConfigError) as exc_info:
            load_config(config_file)

        error_msg = str(exc_info.value)
        assert "agent-index.yaml" in error_msg
        # YAML parse errors should mention line number
        assert "line" in error_msg.lower()

    def test_toml_parse_error_includes_line(self, tmp_path: Path) -> None:
        """load_config includes line number for TOML parse errors."""
        config_file = tmp_path / "agent-index.toml"
        config_file.write_text(
            dedent("""
            index_name = "Test"
            invalid toml here
            """).strip()
        )

        with pytest.raises(ConfigError) as exc_info:
            load_config(config_file)

        error_msg = str(exc_info.value)
        assert "agent-index.toml" in error_msg

    def test_validation_error_includes_field(self, tmp_path: Path) -> None:
        """load_config includes field name for validation errors."""
        config_file = tmp_path / "agent-index.yaml"
        config_file.write_text(
            dedent("""
            index_name: "Test"
            max_workers: "not a number"
            """).strip()
        )

        with pytest.raises(ConfigError) as exc_info:
            load_config(config_file)

        error_msg = str(exc_info.value)
        assert "agent-index.yaml" in error_msg
        assert "max_workers" in error_msg

    def test_validation_error_nested_field(self, tmp_path: Path) -> None:
        """load_config shows path for nested validation errors."""
        config_file = tmp_path / "agent-index.yaml"
        config_file.write_text(
            dedent("""
            index_name: "Test"
            tiers:
              - name: 123
                instruction: "Read"
            """).strip()
        )

        with pytest.raises(ConfigError) as exc_info:
            load_config(config_file)

        error_msg = str(exc_info.value)
        assert "agent-index.yaml" in error_msg
        # Should indicate it's a tier issue
        assert "tiers" in error_msg or "name" in error_msg


class TestFindConfig:
    """Tests for find_config function."""

    def test_finds_yaml_in_current_dir(self, tmp_path: Path) -> None:
        """find_config finds agent-index.yaml in specified directory."""
        config_file = tmp_path / "agent-index.yaml"
        config_file.write_text('index_name: "Test"')

        result = find_config(tmp_path)

        assert result == config_file

    def test_finds_yml_in_current_dir(self, tmp_path: Path) -> None:
        """find_config finds agent-index.yml in specified directory."""
        config_file = tmp_path / "agent-index.yml"
        config_file.write_text('index_name: "Test"')

        result = find_config(tmp_path)

        assert result == config_file

    def test_finds_toml_in_current_dir(self, tmp_path: Path) -> None:
        """find_config finds agent-index.toml in specified directory."""
        config_file = tmp_path / "agent-index.toml"
        config_file.write_text('index_name = "Test"')

        result = find_config(tmp_path)

        assert result == config_file

    def test_yaml_takes_priority_over_yml(self, tmp_path: Path) -> None:
        """find_config prefers .yaml over .yml."""
        (tmp_path / "agent-index.yaml").write_text('index_name: "YAML"')
        (tmp_path / "agent-index.yml").write_text('index_name: "YML"')

        result = find_config(tmp_path)

        assert result is not None
        assert result.suffix == ".yaml"

    def test_yaml_takes_priority_over_toml(self, tmp_path: Path) -> None:
        """find_config prefers .yaml over .toml."""
        (tmp_path / "agent-index.yaml").write_text('index_name: "YAML"')
        (tmp_path / "agent-index.toml").write_text('index_name = "TOML"')

        result = find_config(tmp_path)

        assert result is not None
        assert result.suffix == ".yaml"

    def test_yml_takes_priority_over_toml(self, tmp_path: Path) -> None:
        """find_config prefers .yml over .toml."""
        (tmp_path / "agent-index.yml").write_text('index_name: "YML"')
        (tmp_path / "agent-index.toml").write_text('index_name = "TOML"')

        result = find_config(tmp_path)

        assert result is not None
        assert result.suffix == ".yml"

    def test_searches_parent_directories(self, tmp_path: Path) -> None:
        """find_config searches parent directories."""
        config_file = tmp_path / "agent-index.yaml"
        config_file.write_text('index_name: "Parent"')
        subdir = tmp_path / "subdir" / "nested"
        subdir.mkdir(parents=True)

        result = find_config(subdir)

        assert result == config_file

    def test_returns_none_when_not_found(self, tmp_path: Path) -> None:
        """find_config returns None when no config file exists."""
        result = find_config(tmp_path)

        assert result is None

    def test_stops_at_filesystem_root(self, tmp_path: Path) -> None:
        """find_config doesn't search beyond filesystem root."""
        # This test ensures we don't infinite loop
        result = find_config(tmp_path)

        # Should complete without error
        assert result is None

    def test_uses_cwd_when_no_start_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """find_config uses current working directory when start_dir is None."""
        config_file = tmp_path / "agent-index.yaml"
        config_file.write_text('index_name: "CWD"')
        monkeypatch.chdir(tmp_path)

        result = find_config()

        assert result == config_file


class TestConfigErrorMessage:
    """Tests for ConfigError message formatting."""

    def test_config_error_is_exception(self) -> None:
        """ConfigError is an Exception subclass."""
        error = ConfigError("Test error")
        assert isinstance(error, Exception)

    def test_config_error_stores_message(self) -> None:
        """ConfigError stores the error message."""
        error = ConfigError("Test error message")
        assert str(error) == "Test error message"

    def test_config_error_stores_path(self) -> None:
        """ConfigError can store the config file path."""
        error = ConfigError("Test error", path=Path("/config.yaml"))
        assert error.path == Path("/config.yaml")

    def test_config_error_stores_cause(self) -> None:
        """ConfigError can store the underlying cause."""
        cause = ValueError("Original error")
        error = ConfigError("Wrapped error", cause=cause)
        assert error.cause is cause
