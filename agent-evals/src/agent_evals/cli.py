"""CLI entry point for agent-evals: run evaluation axes, tasks, and variants."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import yaml


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser with all CLI flags."""
    parser = argparse.ArgumentParser(
        prog="agent-evals",
        description="Run evaluation axes to test documentation index formats.",
    )

    # Evaluation scope
    parser.add_argument(
        "--axis",
        type=int,
        default=None,
        help="Run all variants for eval axis N (1-10)",
    )
    parser.add_argument(
        "--tasks",
        type=str,
        default=None,
        help="Filter to specific task types (comma-separated)",
    )
    parser.add_argument(
        "--task-id",
        type=str,
        default=None,
        help="Run a single task by ID (for debugging)",
    )
    parser.add_argument(
        "--variant",
        type=str,
        default=None,
        help="Run a single variant by name (for debugging)",
    )

    # Model configuration
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM model in provider/name format (default: from config)",
    )
    parser.add_argument(
        "--model-config",
        type=str,
        default=None,
        help="Path to model-specific args YAML file",
    )
    parser.add_argument(
        "--judge-model",
        type=str,
        default=None,
        help="Override judge model (default: GPT-4o)",
    )

    # Execution parameters
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max tasks per type (for quick iteration)",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=None,
        help="Override repetition count (default: 10)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Override temperature (default: 0.3)",
    )
    parser.add_argument(
        "--max-connections",
        type=int,
        default=None,
        help="Concurrent API connections (default: 10)",
    )
    parser.add_argument(
        "--max-tasks",
        type=int,
        default=None,
        help="Parallel task evaluation (default: 1)",
    )

    # Cost control
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Estimate tokens and cost without API calls",
    )
    parser.add_argument(
        "--max-cost",
        type=float,
        default=None,
        help="Budget cap in dollars; pause if projected cost exceeds 2x",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        default=False,
        help="Force fresh LLM calls (ignore cache)",
    )

    # Output configuration
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Results directory (default: reports/)",
    )
    parser.add_argument(
        "--output-format",
        type=str,
        choices=["json", "csv"],
        default=None,
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--display",
        type=str,
        choices=["rich", "plain", "none"],
        default=None,
        help="Progress display mode",
    )

    # Config file
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to eval-config.yaml (default: ./eval-config.yaml)",
    )

    return parser


def load_config(config_path: Path | None) -> dict[str, Any]:
    """Load YAML config file if it exists.

    Returns an empty dict when the file does not exist or cannot be parsed.
    """
    if config_path is None:
        return {}

    if not config_path.is_file():
        return {}

    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError):
        return {}

    if not isinstance(data, dict):
        return {}

    return dict(data)


# Mapping from config/env key names to their expected Python types.
_CONFIG_KEYS: dict[str, type] = {
    "axis": int,
    "tasks": str,
    "task_id": str,
    "variant": str,
    "model": str,
    "model_config": str,
    "judge_model": str,
    "limit": int,
    "repetitions": int,
    "temperature": float,
    "max_connections": int,
    "max_tasks": int,
    "dry_run": bool,
    "max_cost": float,
    "no_cache": bool,
    "output_dir": str,
    "output_format": str,
    "display": str,
}


def _env_key(name: str) -> str:
    """Return the environment variable name for a config key."""
    return f"AGENT_EVALS_{name.upper()}"


def _coerce_env(value: str, target_type: type) -> Any:
    """Coerce a string environment variable value to the target type."""
    if target_type is bool:
        return value.lower() in ("1", "true", "yes")
    if target_type is int:
        return int(value)
    if target_type is float:
        return float(value)
    return value


def resolve_config(
    args: argparse.Namespace,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Merge CLI args > env vars > config file into a single resolved dict.

    Precedence (highest to lowest):
    1. CLI arguments with non-None values
    2. Environment variables (``AGENT_EVALS_`` prefix)
    3. Config file values
    """
    resolved: dict[str, Any] = {}

    for key, target_type in _CONFIG_KEYS.items():
        # CLI args use hyphens in flag names, argparse stores with underscores
        cli_value = getattr(args, key, None)

        # For store_true flags, argparse sets False as the default rather than
        # None, so we treat False as "not explicitly provided".
        if target_type is bool and cli_value is False:
            cli_value = None

        # 1. CLI wins if explicitly provided
        if cli_value is not None:
            resolved[key] = cli_value
            continue

        # 2. Environment variable
        env_name = _env_key(key)
        env_value = os.environ.get(env_name)
        if env_value is not None:
            try:
                resolved[key] = _coerce_env(env_value, target_type)
            except (ValueError, TypeError):
                # Ignore malformed env values; fall through to config
                pass
            else:
                continue

        # 3. Config file
        if key in config:
            resolved[key] = config[key]

    return resolved


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``agent-evals`` CLI.

    Returns 0 on success, 1 on error.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    # Determine config file path
    config_path: Path | None = None
    if args.config is not None:
        config_path = Path(args.config)
    else:
        default_config = Path("eval-config.yaml")
        if default_config.is_file():
            config_path = default_config

    config = load_config(config_path)
    resolved = resolve_config(args, config)

    # Placeholder: print resolved config until the runner module is ready
    print("Resolved configuration:")  # noqa: T201
    for key, value in sorted(resolved.items()):
        print(f"  {key}: {value!r}")  # noqa: T201

    return 0


if __name__ == "__main__":
    sys.exit(main())
