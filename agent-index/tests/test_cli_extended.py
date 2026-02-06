"""Tests for CLI extensions (--auto-detect, --init, --scaffold, --validate)."""

from __future__ import annotations

import sys
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest
from agent_index.cli import main, parse_args, run


class TestParseArgsExtended:
    """Tests for new CLI argument parsing."""

    def test_auto_detect_flag_recognized(self) -> None:
        """--auto-detect accepts a path."""
        args = parse_args(["--auto-detect", "./my-project"])
        assert args.auto_detect == "./my-project"

    def test_validate_flag_recognized(self) -> None:
        """--validate is a boolean flag."""
        args = parse_args(["--validate"])
        assert args.validate is True

    def test_scaffold_flag_recognized(self) -> None:
        """--scaffold accepts a path."""
        args = parse_args(["--scaffold", "./new-project"])
        assert args.scaffold == "./new-project"

    def test_init_flag_recognized(self) -> None:
        """--init is a boolean flag."""
        args = parse_args(["--init"])
        assert args.init is True

    def test_existing_flags_still_work(self) -> None:
        """Existing CLI flags are not broken by new additions."""
        args = parse_args(["--local", "./docs", "--name", "Test"])
        assert args.local == "./docs"
        assert args.name == "Test"

    def test_defaults_for_new_flags(self) -> None:
        """New flags default to None/False when not provided."""
        args = parse_args(["--local", "./docs"])
        assert args.auto_detect is None
        assert args.validate is False
        assert args.scaffold is None
        assert args.init is False


class TestAutoDetectCLI:
    """Tests for --auto-detect CLI workflow."""

    def test_auto_detect_outputs_yaml(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--auto-detect outputs YAML config to stdout."""
        (tmp_path / "setup.md").write_text("# Setup")

        args = parse_args(["--auto-detect", str(tmp_path)])
        result = run(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "index_name" in captured.out
        assert "tiers" in captured.out

    def test_auto_detect_nonexistent_dir(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--auto-detect with nonexistent directory returns error."""
        args = parse_args(["--auto-detect", str(tmp_path / "nonexistent")])
        result = run(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "error" in captured.err.lower()


class TestInitCLI:
    """Tests for --init CLI workflow."""

    def test_init_outputs_template(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--init outputs a template YAML config."""
        args = parse_args(["--init"])
        result = run(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "index_name" in captured.out
        assert "My Project" in captured.out


class TestScaffoldCLI:
    """Tests for --scaffold CLI workflow."""

    def test_scaffold_creates_structure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--scaffold creates directory structure and reports created paths."""
        root = tmp_path / "new-project"

        args = parse_args(["--scaffold", str(root)])
        result = run(args)

        assert result == 0
        assert root.exists()
        assert (root / ".docs").exists()
        assert (root / "agent-index.yaml").exists()

        captured = capsys.readouterr()
        assert "Created:" in captured.out


class TestValidateCLI:
    """Tests for --validate CLI workflow."""

    def test_validate_passes_with_matching_index(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--validate passes when index matches docs on disk."""
        # Create config and docs
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "readme.md").write_text("# Hello")

        config_file = tmp_path / "agent-index.yaml"
        config_file.write_text(
            dedent("""
            index_name: "Test"
            root_path: "./docs"
            """).strip()
        )

        args = parse_args(["--validate", "--config", str(config_file)])
        with patch("agent_index.cli.Path.cwd", return_value=tmp_path):
            result = run(args)

        assert result == 0
        captured = capsys.readouterr()
        assert "passed" in captured.out.lower()

    def test_validate_no_config_found(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--validate without config returns error."""
        args = parse_args(["--validate"])
        with patch("agent_index.cli.find_config", return_value=None):
            result = run(args)

        assert result == 1
        captured = capsys.readouterr()
        assert "error" in captured.err.lower()


class TestExistingBehaviorPreserved:
    """Ensure existing CLI behavior is not broken by new features."""

    def test_local_scan_still_works(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--local still works as before."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Test")

        with patch.object(sys, "argv", ["agent-index", "--local", str(docs_dir)]):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "IMPORTANT:" in captured.out

    def test_config_loading_still_works(self, tmp_path: Path) -> None:
        """--config still loads config files correctly."""
        config_file = tmp_path / "agent-index.yaml"
        config_file.write_text(
            dedent("""
            index_name: "Config Project"
            root_path: "./docs"
            """).strip()
        )
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Test")

        args = parse_args(["--config", str(config_file)])
        with patch("agent_index.cli.Path.cwd", return_value=tmp_path):
            result = run(args)

        assert result == 0

    def test_output_writes_to_file(self, tmp_path: Path) -> None:
        """--output still writes to file correctly."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Test")
        output_file = tmp_path / "AGENTS.md"

        args = parse_args(["--local", str(docs_dir), "--output", str(output_file)])
        result = run(args)

        assert result == 0
        assert output_file.exists()
        assert "README.md" in output_file.read_text()
