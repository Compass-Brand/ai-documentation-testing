"""Tests for the agent-evals CLI module."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from agent_evals.cli import (
    _run_evaluation,
    build_parser,
    load_config,
    main,
    resolve_config,
)

# ---------------------------------------------------------------------------
# build_parser tests
# ---------------------------------------------------------------------------


class TestBuildParserDefaults:
    """Default values for all flags."""

    def test_returns_argument_parser(self) -> None:
        parser = build_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_default_axis_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.axis is None

    def test_default_tasks_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.tasks is None

    def test_default_task_id_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.task_id is None

    def test_default_variant_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.variant is None

    def test_default_model_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.model is None

    def test_default_model_config_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.model_config is None

    def test_default_judge_model_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.judge_model is None

    def test_default_limit_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.limit is None

    def test_default_repetitions_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.repetitions is None

    def test_default_temperature_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.temperature is None

    def test_default_max_connections_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.max_connections is None

    def test_default_max_tasks_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.max_tasks is None

    def test_default_dry_run_is_false(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.dry_run is False

    def test_default_max_cost_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.max_cost is None

    def test_default_no_cache_is_false(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.no_cache is False

    def test_default_output_dir_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.output_dir is None

    def test_default_output_format_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.output_format is None

    def test_default_display_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.display is None


class TestBuildParserFlags:
    """Each flag can be set individually and parsed correctly."""

    def test_axis_accepts_int(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--axis", "5"])
        assert args.axis == 5

    def test_tasks_accepts_comma_separated(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--tasks", "retrieval,code_generation"])
        assert args.tasks == "retrieval,code_generation"

    def test_task_id_accepts_string(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--task-id", "task-123"])
        assert args.task_id == "task-123"

    def test_variant_accepts_string(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--variant", "baseline-v1"])
        assert args.variant == "baseline-v1"

    def test_model_accepts_provider_name(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--model", "openrouter/anthropic/claude-sonnet-4.5"])
        assert args.model == "openrouter/anthropic/claude-sonnet-4.5"

    def test_model_config_accepts_path(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--model-config", "model.yaml"])
        assert args.model_config == "model.yaml"

    def test_judge_model_accepts_provider_name(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--judge-model", "openrouter/openai/gpt-4o"])
        assert args.judge_model == "openrouter/openai/gpt-4o"

    def test_limit_accepts_int(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--limit", "50"])
        assert args.limit == 50

    def test_repetitions_accepts_int(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--repetitions", "20"])
        assert args.repetitions == 20

    def test_temperature_accepts_float(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--temperature", "0.7"])
        assert args.temperature == pytest.approx(0.7)

    def test_max_connections_accepts_int(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--max-connections", "5"])
        assert args.max_connections == 5

    def test_max_tasks_accepts_int(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--max-tasks", "4"])
        assert args.max_tasks == 4

    def test_dry_run_is_boolean_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_max_cost_accepts_float(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--max-cost", "25.50"])
        assert args.max_cost == pytest.approx(25.50)

    def test_no_cache_is_boolean_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--no-cache"])
        assert args.no_cache is True

    def test_output_dir_accepts_string(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--output-dir", "./my-reports"])
        assert args.output_dir == "./my-reports"

    def test_output_format_accepts_json(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--output-format", "json"])
        assert args.output_format == "json"

    def test_output_format_accepts_csv(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--output-format", "csv"])
        assert args.output_format == "csv"

    def test_output_format_rejects_invalid(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--output-format", "xml"])

    def test_display_accepts_rich(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--display", "rich"])
        assert args.display == "rich"

    def test_display_accepts_plain(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--display", "plain"])
        assert args.display == "plain"

    def test_display_accepts_none_value(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--display", "none"])
        assert args.display == "none"

    def test_display_rejects_invalid(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--display", "fancy"])


class TestBuildParserCombinations:
    """Multiple flags can be combined."""

    def test_multiple_flags_together(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "--axis", "3",
            "--model", "openrouter/openai/gpt-4o",
            "--repetitions", "5",
            "--dry-run",
            "--output-format", "csv",
        ])
        assert args.axis == 3
        assert args.model == "openrouter/openai/gpt-4o"
        assert args.repetitions == 5
        assert args.dry_run is True
        assert args.output_format == "csv"


# ---------------------------------------------------------------------------
# load_config tests
# ---------------------------------------------------------------------------


class TestLoadConfig:
    """Tests for YAML config file loading."""

    def test_returns_empty_dict_when_no_file(self, tmp_path: Path) -> None:
        result = load_config(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_returns_empty_dict_when_path_is_none(self) -> None:
        result = load_config(None)
        assert result == {}

    def test_parses_valid_yaml(self, tmp_path: Path) -> None:
        config_file = tmp_path / "eval-config.yaml"
        config_file.write_text(
            "model: openrouter/anthropic/claude-sonnet-4.5\n"
            "repetitions: 10\n"
            "temperature: 0.3\n",
            encoding="utf-8",
        )
        result = load_config(config_file)
        assert result == {
            "model": "openrouter/anthropic/claude-sonnet-4.5",
            "repetitions": 10,
            "temperature": pytest.approx(0.3),
        }

    def test_parses_full_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "eval-config.yaml"
        config_file.write_text(
            "model: openrouter/anthropic/claude-sonnet-4.5\n"
            "judge_model: openrouter/openai/gpt-4o\n"
            "repetitions: 10\n"
            "temperature: 0.3\n"
            "max_connections: 10\n"
            "output_dir: ./reports\n",
            encoding="utf-8",
        )
        result = load_config(config_file)
        assert result["model"] == "openrouter/anthropic/claude-sonnet-4.5"
        assert result["judge_model"] == "openrouter/openai/gpt-4o"
        assert result["repetitions"] == 10
        assert result["temperature"] == pytest.approx(0.3)
        assert result["max_connections"] == 10
        assert result["output_dir"] == "./reports"

    def test_handles_invalid_yaml_gracefully(self, tmp_path: Path) -> None:
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("{{invalid: yaml: [", encoding="utf-8")
        result = load_config(config_file)
        assert result == {}

    def test_handles_non_dict_yaml(self, tmp_path: Path) -> None:
        config_file = tmp_path / "list.yaml"
        config_file.write_text("- item1\n- item2\n", encoding="utf-8")
        result = load_config(config_file)
        assert result == {}

    def test_handles_empty_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("", encoding="utf-8")
        result = load_config(config_file)
        assert result == {}


# ---------------------------------------------------------------------------
# resolve_config tests
# ---------------------------------------------------------------------------


class TestResolveConfigCLIOverrides:
    """CLI args with non-None values override everything."""

    def test_cli_overrides_config_file(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--model", "my-model", "--repetitions", "5"])
        config = {"model": "config-model", "repetitions": 20}
        resolved = resolve_config(args, config)
        assert resolved["model"] == "my-model"
        assert resolved["repetitions"] == 5

    def test_cli_overrides_env_var(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--temperature", "0.9"])
        with patch.dict("os.environ", {"AGENT_EVALS_TEMPERATURE": "0.1"}):
            resolved = resolve_config(args, {})
        assert resolved["temperature"] == pytest.approx(0.9)

    def test_cli_overrides_both_env_and_config(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--repetitions", "3"])
        config = {"repetitions": 10}
        with patch.dict("os.environ", {"AGENT_EVALS_REPETITIONS": "7"}):
            resolved = resolve_config(args, config)
        assert resolved["repetitions"] == 3

    def test_dry_run_cli_flag_overrides(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--dry-run"])
        resolved = resolve_config(args, {})
        assert resolved["dry_run"] is True

    def test_no_cache_cli_flag_overrides(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--no-cache"])
        resolved = resolve_config(args, {})
        assert resolved["no_cache"] is True


class TestResolveConfigEnvVars:
    """Environment variables override config file values."""

    def test_env_var_overrides_config(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        config = {"model": "config-model"}
        with patch.dict("os.environ", {"AGENT_EVALS_MODEL": "env-model"}):
            resolved = resolve_config(args, config)
        assert resolved["model"] == "env-model"

    def test_env_var_temperature_coerced_to_float(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        with patch.dict("os.environ", {"AGENT_EVALS_TEMPERATURE": "0.5"}):
            resolved = resolve_config(args, {})
        assert resolved["temperature"] == pytest.approx(0.5)

    def test_env_var_repetitions_coerced_to_int(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        with patch.dict("os.environ", {"AGENT_EVALS_REPETITIONS": "15"}):
            resolved = resolve_config(args, {})
        assert resolved["repetitions"] == 15

    def test_env_var_dry_run_bool_true(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        with patch.dict("os.environ", {"AGENT_EVALS_DRY_RUN": "true"}):
            resolved = resolve_config(args, {})
        assert resolved["dry_run"] is True

    def test_env_var_dry_run_bool_one(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        with patch.dict("os.environ", {"AGENT_EVALS_DRY_RUN": "1"}):
            resolved = resolve_config(args, {})
        assert resolved["dry_run"] is True

    def test_env_var_dry_run_bool_false(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        with patch.dict("os.environ", {"AGENT_EVALS_DRY_RUN": "false"}):
            resolved = resolve_config(args, {})
        # "false" should coerce to False, so it IS set but to False
        assert resolved["dry_run"] is False

    def test_env_var_malformed_int_ignored(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        config = {"repetitions": 10}
        with patch.dict("os.environ", {"AGENT_EVALS_REPETITIONS": "not_a_number"}):
            resolved = resolve_config(args, config)
        # Malformed env var falls through to config
        assert resolved["repetitions"] == 10

    def test_env_var_without_config_fallback(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        with patch.dict("os.environ", {"AGENT_EVALS_OUTPUT_DIR": "/tmp/results"}):
            resolved = resolve_config(args, {})
        assert resolved["output_dir"] == "/tmp/results"


class TestResolveConfigFileDefaults:
    """Config file provides default values."""

    def test_config_file_provides_defaults(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        config = {
            "model": "openrouter/anthropic/claude-sonnet-4.5",
            "judge_model": "openrouter/openai/gpt-4o",
            "repetitions": 10,
            "temperature": 0.3,
        }
        resolved = resolve_config(args, config)
        assert resolved["model"] == "openrouter/anthropic/claude-sonnet-4.5"
        assert resolved["judge_model"] == "openrouter/openai/gpt-4o"
        assert resolved["repetitions"] == 10
        assert resolved["temperature"] == pytest.approx(0.3)

    def test_empty_config_yields_no_extras(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        resolved = resolve_config(args, {})
        # No CLI, no env, no config => empty resolved
        assert resolved == {}

    def test_unknown_config_keys_ignored(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        config = {"unknown_key": "value", "model": "m"}
        resolved = resolve_config(args, config)
        assert "unknown_key" not in resolved
        assert resolved["model"] == "m"


class TestResolveConfigMerge:
    """Full three-way merge: CLI > env vars > config file."""

    def test_three_way_merge(self) -> None:
        parser = build_parser()
        # CLI sets model
        args = parser.parse_args(["--model", "cli-model"])
        # Config sets model, temperature, and output_dir
        config = {
            "model": "config-model",
            "temperature": 0.3,
            "output_dir": "./config-reports",
        }
        # Env sets temperature and output_dir
        env = {
            "AGENT_EVALS_TEMPERATURE": "0.8",
            "AGENT_EVALS_OUTPUT_DIR": "/env/reports",
        }
        with patch.dict("os.environ", env):
            resolved = resolve_config(args, config)

        # model: CLI wins
        assert resolved["model"] == "cli-model"
        # temperature: env wins over config
        assert resolved["temperature"] == pytest.approx(0.8)
        # output_dir: env wins over config
        assert resolved["output_dir"] == "/env/reports"

    def test_non_none_cli_values_win(self) -> None:
        parser = build_parser()
        args = parser.parse_args([
            "--axis", "7",
            "--output-format", "csv",
        ])
        config = {"axis": 1, "output_format": "json", "repetitions": 10}
        resolved = resolve_config(args, config)
        assert resolved["axis"] == 7
        assert resolved["output_format"] == "csv"
        # repetitions not set via CLI, falls to config
        assert resolved["repetitions"] == 10


# ---------------------------------------------------------------------------
# main() tests
# ---------------------------------------------------------------------------


class TestMain:
    """Tests for the main() entry point."""

    def test_returns_one_without_model(self) -> None:
        result = main([])
        assert result == 1

    def test_help_raises_system_exit(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_resolves_config_from_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        config_file = tmp_path / "eval-config.yaml"
        config_file.write_text(
            "model: file-model\nrepetitions: 15\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
        result = main(["--config", str(config_file), "--dry-run"])
        assert result == 0

    def test_returns_zero_with_flags(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
        result = main([
            "--axis", "2",
            "--model", "test/model",
            "--dry-run",
            "--output-format", "json",
        ])
        assert result == 0

    def test_invalid_flag_exits_nonzero(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--nonexistent-flag"])
        assert exc_info.value.code != 0

    def test_default_config_file_loaded_when_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no --config is passed but eval-config.yaml exists in cwd, load it."""
        config_file = tmp_path / "eval-config.yaml"
        config_file.write_text("model: auto-loaded\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
        result = main(["--dry-run"])
        assert result == 0

    def test_no_default_config_file_returns_one_without_model(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no config file exists and no model, returns 1."""
        monkeypatch.chdir(tmp_path)
        result = main([])
        assert result == 1

    def test_main_with_env_vars(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "AGENT_EVALS_MODEL": "env/model",
                "AGENT_EVALS_REPETITIONS": "8",
                "OPENROUTER_API_KEY": "sk-or-v1-test",
            },
        ):
            result = main(["--dry-run"])
        assert result == 0


# ---------------------------------------------------------------------------
# Verbosity flags tests
# ---------------------------------------------------------------------------


class TestVerbosityFlags:
    """Tests for --verbose and --quiet mutually exclusive flags."""

    def test_verbose_flag_parsed(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--verbose"])
        assert args.verbose is True

    def test_verbose_short_flag_parsed(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["-v"])
        assert args.verbose is True

    def test_quiet_flag_parsed(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--quiet"])
        assert args.quiet is True

    def test_quiet_short_flag_parsed(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["-q"])
        assert args.quiet is True

    def test_verbose_and_quiet_mutually_exclusive(self) -> None:
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--verbose", "--quiet"])

    def test_default_verbose_is_false(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.verbose is False

    def test_default_quiet_is_false(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.quiet is False


# ---------------------------------------------------------------------------
# API key validation tests
# ---------------------------------------------------------------------------


class TestApiKeyValidation:
    """Tests for upfront OPENROUTER_API_KEY validation."""

    def test_missing_api_key_returns_error(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        resolved: dict[str, object] = {"model": "openrouter/anthropic/claude-sonnet-4.5"}
        result = _run_evaluation(resolved)
        assert result == 1

    def test_invalid_prefix_logs_warning(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "bad-prefix-key")
        resolved: dict[str, object] = {
            "model": "openrouter/anthropic/claude-sonnet-4.5",
            "dry_run": True,
        }
        with caplog.at_level(logging.WARNING, logger="agent_evals"):
            _run_evaluation(resolved)
        assert "does not start with" in caplog.text

    def test_dry_run_does_not_require_api_key(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        resolved: dict[str, object] = {
            "model": "openrouter/anthropic/claude-sonnet-4.5",
            "dry_run": True,
        }
        result = _run_evaluation(resolved)
        assert result == 0


# ---------------------------------------------------------------------------
# Task 2.1: Config file warning tests
# ---------------------------------------------------------------------------


class TestLoadConfigWarnings:
    def test_warns_on_yaml_parse_error(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture,
    ) -> None:
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text(": : : invalid", encoding="utf-8")
        with caplog.at_level(logging.WARNING, logger="agent_evals"):
            result = load_config(bad_yaml)
        assert result == {}
        assert "Failed to parse" in caplog.text

    def test_warns_on_non_dict_yaml(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture,
    ) -> None:
        list_yaml = tmp_path / "list.yaml"
        list_yaml.write_text("- item1\n- item2", encoding="utf-8")
        with caplog.at_level(logging.WARNING, logger="agent_evals"):
            result = load_config(list_yaml)
        assert result == {}
        assert "does not contain a YAML mapping" in caplog.text


# ---------------------------------------------------------------------------
# Task 2.2: Env var warning tests
# ---------------------------------------------------------------------------


class TestEnvVarWarnings:
    def test_warns_on_malformed_env_var(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
    ) -> None:
        monkeypatch.setenv("AGENT_EVALS_MAX_CONNECTIONS", "not_a_number")
        args = build_parser().parse_args([])
        with caplog.at_level(logging.WARNING, logger="agent_evals"):
            resolve_config(args, {})
        assert "Could not parse" in caplog.text


# ---------------------------------------------------------------------------
# Task 2.3: --continue-on-error flag tests
# ---------------------------------------------------------------------------


class TestContinueOnErrorFlag:
    def test_continue_on_error_flag_parsed(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--continue-on-error"])
        assert args.continue_on_error is True

    def test_default_continue_on_error_is_false(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.continue_on_error is False


# ---------------------------------------------------------------------------
# Dataset CLI flags -- parser defaults
# ---------------------------------------------------------------------------


class TestDatasetFlagDefaults:
    """Default values for dataset-related CLI flags."""

    def test_default_source_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.source is None

    def test_default_dataset_limit_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.dataset_limit is None

    def test_default_dataset_cache_dir_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.dataset_cache_dir is None

    def test_default_prepare_datasets_is_none(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.prepare_datasets is None

    def test_default_list_datasets_is_false(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        assert args.list_datasets is False


# ---------------------------------------------------------------------------
# Dataset CLI flags -- parsing
# ---------------------------------------------------------------------------


class TestDatasetFlagParsing:
    """Each dataset flag can be set and parsed correctly."""

    def test_source_accepts_single_name(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--source", "repliqa"])
        assert args.source == "repliqa"

    def test_source_accepts_comma_separated_list(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--source", "gold_standard,repliqa,code-rag-bench"])
        assert args.source == "gold_standard,repliqa,code-rag-bench"

    def test_dataset_limit_accepts_int(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--dataset-limit", "50"])
        assert args.dataset_limit == 50

    def test_dataset_cache_dir_accepts_path(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--dataset-cache-dir", "/tmp/my-cache"])
        assert args.dataset_cache_dir == "/tmp/my-cache"

    def test_prepare_datasets_accepts_single_name(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--prepare-datasets", "repliqa"])
        assert args.prepare_datasets == "repliqa"

    def test_prepare_datasets_accepts_all(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--prepare-datasets", "all"])
        assert args.prepare_datasets == "all"

    def test_prepare_datasets_accepts_comma_separated(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--prepare-datasets", "repliqa,ibm-techqa"])
        assert args.prepare_datasets == "repliqa,ibm-techqa"

    def test_list_datasets_is_boolean_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--list-datasets"])
        assert args.list_datasets is True


# ---------------------------------------------------------------------------
# Dataset CLI flags -- resolve_config integration
# ---------------------------------------------------------------------------


class TestDatasetResolveConfig:
    """Dataset flags participate in the config resolution pipeline."""

    def test_source_resolved_from_cli(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--source", "repliqa"])
        resolved = resolve_config(args, {})
        assert resolved["source"] == "repliqa"

    def test_source_resolved_from_config_file(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        config = {"source": "code-rag-bench"}
        resolved = resolve_config(args, config)
        assert resolved["source"] == "code-rag-bench"

    def test_source_resolved_from_env(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        with patch.dict("os.environ", {"AGENT_EVALS_SOURCE": "ibm-techqa"}):
            resolved = resolve_config(args, {})
        assert resolved["source"] == "ibm-techqa"

    def test_dataset_limit_resolved_from_cli(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--dataset-limit", "25"])
        resolved = resolve_config(args, {})
        assert resolved["dataset_limit"] == 25

    def test_dataset_limit_resolved_from_env(self) -> None:
        parser = build_parser()
        args = parser.parse_args([])
        with patch.dict("os.environ", {"AGENT_EVALS_DATASET_LIMIT": "100"}):
            resolved = resolve_config(args, {})
        assert resolved["dataset_limit"] == 100

    def test_dataset_cache_dir_resolved_from_cli(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--dataset-cache-dir", "/tmp/cache"])
        resolved = resolve_config(args, {})
        assert resolved["dataset_cache_dir"] == "/tmp/cache"

    def test_list_datasets_resolved_from_cli(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--list-datasets"])
        resolved = resolve_config(args, {})
        assert resolved["list_datasets"] is True

    def test_prepare_datasets_resolved_from_cli(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--prepare-datasets", "repliqa"])
        resolved = resolve_config(args, {})
        assert resolved["prepare_datasets"] == "repliqa"


# ---------------------------------------------------------------------------
# Dataset CLI flags -- _run_evaluation behavior
# ---------------------------------------------------------------------------


class TestListDatasetsCommand:
    """--list-datasets prints available datasets and exits."""

    def test_list_datasets_returns_zero(self) -> None:
        """--list-datasets should exit successfully without needing a model."""
        resolved: dict[str, object] = {"list_datasets": True}
        result = _run_evaluation(resolved)
        assert result == 0

    def test_list_datasets_logs_output(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """--list-datasets should log dataset information."""
        resolved: dict[str, object] = {"list_datasets": True}
        with caplog.at_level(logging.INFO, logger="agent_evals"):
            _run_evaluation(resolved)
        assert "Available datasets" in caplog.text


class TestPrepareDatasetsCommand:
    """--prepare-datasets downloads and converts without running evals."""

    def test_prepare_unknown_dataset_returns_error(self) -> None:
        """Preparing a non-existent dataset should fail."""
        resolved: dict[str, object] = {"prepare_datasets": "nonexistent_dataset"}
        result = _run_evaluation(resolved)
        assert result == 1

    def test_prepare_datasets_does_not_require_model(self) -> None:
        """--prepare-datasets should not require --model flag."""
        resolved: dict[str, object] = {"prepare_datasets": "nonexistent_dataset"}
        # Should fail with dataset error, not model error
        result = _run_evaluation(resolved)
        assert result == 1  # Fails because dataset unknown, not because model missing


class TestSourceFlag:
    """--source controls which task source is used."""

    def test_dry_run_with_source_flag(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Dry run with --source should succeed and log source info."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
        result = main([
            "--model", "test/model",
            "--dry-run",
            "--source", "gold_standard",
        ])
        assert result == 0

    def test_dry_run_with_dataset_limit(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Dry run with --dataset-limit should succeed."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
        result = main([
            "--model", "test/model",
            "--dry-run",
            "--dataset-limit", "10",
        ])
        assert result == 0

    def test_dry_run_with_multi_source(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Dry run with comma-separated --source should succeed."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-test")
        result = main([
            "--model", "test/model",
            "--dry-run",
            "--source", "gold_standard,repliqa",
        ])
        assert result == 0
