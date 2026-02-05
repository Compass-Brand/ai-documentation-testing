"""Tests for CLI entry point."""

import sys
from pathlib import Path
from textwrap import dedent
from unittest.mock import patch

import pytest
from agent_index.cli import main, parse_args, run


class TestParseArgs:
    """Tests for argument parsing."""

    def test_local_flag_with_path(self) -> None:
        """--local accepts a path."""
        args = parse_args(["--local", "./docs"])
        assert args.local == "./docs"

    def test_name_flag(self) -> None:
        """--name accepts project name."""
        args = parse_args(["--local", "./docs", "--name", "My Project"])
        assert args.name == "My Project"

    def test_config_flag(self) -> None:
        """--config accepts config file path."""
        args = parse_args(["--config", "config.yaml"])
        assert args.config == "config.yaml"

    def test_output_flag(self) -> None:
        """--output accepts output file path."""
        args = parse_args(["--local", "./docs", "--output", "AGENTS.md"])
        assert args.output == "AGENTS.md"

    def test_inject_flag(self) -> None:
        """--inject accepts target file path."""
        args = parse_args(["--local", "./docs", "--inject", "README.md"])
        assert args.inject == "README.md"

    def test_marker_id_flag(self) -> None:
        """--marker-id accepts marker ID."""
        args = parse_args(["--local", "./docs", "--marker-id", "INDEX"])
        assert args.marker_id == "INDEX"

    def test_default_marker_id(self) -> None:
        """--marker-id defaults to DOCS."""
        args = parse_args(["--local", "./docs"])
        assert args.marker_id == "DOCS"

    def test_help_flag_short(self) -> None:
        """-h shows help."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["-h"])
        assert exc_info.value.code == 0

    def test_help_flag_long(self) -> None:
        """--help shows help."""
        with pytest.raises(SystemExit) as exc_info:
            parse_args(["--help"])
        assert exc_info.value.code == 0

    def test_no_args_allowed(self) -> None:
        """No arguments allowed (relies on auto-detect or fails)."""
        # Should not raise during parsing
        args = parse_args([])
        assert args.local is None
        assert args.config is None


class TestRunFunction:
    """Tests for the run function workflow."""

    def test_local_only_uses_defaults(self, tmp_path: Path) -> None:
        """--local without --config uses default settings."""
        # Create a docs directory with a file
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Test")

        args = parse_args(["--local", str(docs_dir), "--name", "Test Project"])
        result = run(args)

        assert result == 0
        # Verify stdout was written (we'll capture in integration test)

    def test_config_file_loaded(self, tmp_path: Path) -> None:
        """--config loads the specified config file."""
        # Create config file
        config_file = tmp_path / "agent-index.yaml"
        config_file.write_text(
            dedent("""
            index_name: "Config Project"
            root_path: "./docs"
            """).strip()
        )

        # Create docs directory
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Test")

        args = parse_args(["--config", str(config_file)])
        # Patch cwd to tmp_path so root_path resolves correctly
        with patch("agent_index.cli.Path.cwd", return_value=tmp_path):
            result = run(args)

        assert result == 0

    def test_output_writes_to_file(self, tmp_path: Path) -> None:
        """--output writes to specified file."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Test")
        output_file = tmp_path / "AGENTS.md"

        args = parse_args([
            "--local", str(docs_dir),
            "--output", str(output_file),
        ])
        result = run(args)

        assert result == 0
        assert output_file.exists()
        content = output_file.read_text()
        assert "IMPORTANT:" in content
        assert "README.md" in content

    def test_inject_into_existing_file(self, tmp_path: Path) -> None:
        """--inject injects into existing file with markers."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Test")

        target_file = tmp_path / "TARGET.md"
        target_file.write_text(
            dedent("""
            # Project

            <!-- DOCS:START -->
            Old content
            <!-- DOCS:END -->

            ## Footer
            """).strip()
        )

        args = parse_args([
            "--local", str(docs_dir),
            "--inject", str(target_file),
        ])
        result = run(args)

        assert result == 0
        content = target_file.read_text()
        assert "Old content" not in content
        assert "IMPORTANT:" in content
        assert "## Footer" in content

    def test_inject_with_custom_marker(self, tmp_path: Path) -> None:
        """--inject with --marker-id uses custom marker."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Test")

        target_file = tmp_path / "TARGET.md"
        target_file.write_text(
            dedent("""
            # Project

            <!-- INDEX:START -->
            Old content
            <!-- INDEX:END -->
            """).strip()
        )

        args = parse_args([
            "--local", str(docs_dir),
            "--inject", str(target_file),
            "--marker-id", "INDEX",
        ])
        result = run(args)

        assert result == 0
        content = target_file.read_text()
        assert "Old content" not in content
        assert "<!-- INDEX:START -->" in content

    def test_error_no_config_no_local(self, tmp_path: Path) -> None:
        """Error when no --config and no --local and no auto-detected config."""
        args = parse_args([])

        # Mock find_config to return None
        with patch("agent_index.cli.find_config", return_value=None):
            result = run(args)

        assert result == 1

    def test_error_invalid_local_path(self, tmp_path: Path) -> None:
        """Error when --local path doesn't exist."""
        args = parse_args(["--local", str(tmp_path / "nonexistent")])
        result = run(args)

        assert result == 1

    def test_error_config_file_not_found(self, tmp_path: Path) -> None:
        """Error when --config file doesn't exist."""
        args = parse_args(["--config", str(tmp_path / "nonexistent.yaml")])
        result = run(args)

        assert result == 1

    def test_auto_detect_config(self, tmp_path: Path) -> None:
        """Auto-detects config file when no flags provided."""
        # Create config file
        config_file = tmp_path / "agent-index.yaml"
        config_file.write_text(
            dedent("""
            index_name: "Auto Project"
            root_path: "./docs"
            """).strip()
        )

        # Create docs directory
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Test")

        args = parse_args([])

        # Mock find_config to return our config file
        with (
            patch("agent_index.cli.find_config", return_value=config_file),
            patch("agent_index.cli.Path.cwd", return_value=tmp_path),
        ):
            result = run(args)

        assert result == 0


class TestMainFunction:
    """Tests for the main entry point."""

    def test_main_success_returns_zero(self, tmp_path: Path) -> None:
        """main() returns 0 on success."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Test")

        with patch.object(sys, "argv", ["agent-index", "--local", str(docs_dir)]):
            exit_code = main()

        assert exit_code == 0

    def test_main_error_returns_one(self, tmp_path: Path) -> None:
        """main() returns 1 on error."""
        nonexistent = tmp_path / "definitely_nonexistent_dir_12345"
        with patch.object(sys, "argv", ["agent-index", "--local", str(nonexistent)]):
            exit_code = main()

        assert exit_code == 1

    def test_main_writes_to_stdout(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """main() writes index to stdout by default."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Test")

        with patch.object(sys, "argv", ["agent-index", "--local", str(docs_dir)]):
            main()

        captured = capsys.readouterr()
        assert "IMPORTANT:" in captured.out
        assert "README.md" in captured.out

    def test_main_error_message_to_stderr(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """main() writes error messages to stderr."""
        nonexistent = tmp_path / "definitely_nonexistent_dir_12345"
        with patch.object(sys, "argv", ["agent-index", "--local", str(nonexistent)]):
            main()

        captured = capsys.readouterr()
        assert "error" in captured.err.lower()


class TestIntegration:
    """Integration tests for the CLI."""

    def test_full_workflow_local_to_stdout(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Full workflow: scan local docs, output to stdout."""
        # Create docs structure
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Project README")

        guides = docs_dir / "guides"
        guides.mkdir()
        (guides / "setup.md").write_text("# Setup Guide")

        with patch.object(
            sys,
            "argv",
            ["agent-index", "--local", str(docs_dir), "--name", "Test Project"],
        ):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "IMPORTANT:" in captured.out
        # Files should be listed
        assert "README.md" in captured.out
        assert "guides/setup.md" in captured.out

    def test_full_workflow_config_to_file(self, tmp_path: Path) -> None:
        """Full workflow: load config, scan, output to file."""
        # Create config
        config_file = tmp_path / "agent-index.yaml"
        config_file.write_text(
            dedent("""
            index_name: "Configured Project"
            root_path: "./docs"
            instruction: "Custom instruction for testing."
            tiers:
              - name: required
                instruction: "Must read"
                patterns: ["**/README.md"]
              - name: recommended
                instruction: "Should read"
                patterns: ["**/*.md"]
            """).strip()
        )

        # Create docs
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# README")
        (docs_dir / "guide.md").write_text("# Guide")

        # Output file
        output_file = tmp_path / "AGENTS.md"

        with (
            patch.object(
                sys,
                "argv",
                ["agent-index", "--config", str(config_file), "--output", str(output_file)],
            ),
            patch("agent_index.cli.Path.cwd", return_value=tmp_path),
        ):
            exit_code = main()

        assert exit_code == 0
        assert output_file.exists()

        content = output_file.read_text()
        assert "Custom instruction for testing" in content
        assert "## Required [Must read]" in content
        assert "README.md" in content

    def test_output_and_inject_mutually_exclusive_behavior(self, tmp_path: Path) -> None:
        """When both --output and --inject provided, --output takes precedence."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "README.md").write_text("# Test")

        output_file = tmp_path / "output.md"
        inject_file = tmp_path / "inject.md"
        inject_file.write_text("<!-- DOCS:START -->old<!-- DOCS:END -->")

        with patch.object(
            sys,
            "argv",
            [
                "agent-index",
                "--local", str(docs_dir),
                "--output", str(output_file),
                "--inject", str(inject_file),
            ],
        ):
            exit_code = main()

        assert exit_code == 0
        # --output should win
        assert output_file.exists()
        # --inject should not be modified
        assert inject_file.read_text() == "<!-- DOCS:START -->old<!-- DOCS:END -->"
