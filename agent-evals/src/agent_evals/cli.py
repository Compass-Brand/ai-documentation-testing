"""CLI entry point for agent-evals: run evaluation axes, tasks, and variants."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


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

    # Verbosity (mutually exclusive)
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Enable debug-level logging output",
    )
    verbosity.add_argument(
        "--quiet", "-q",
        action="store_true",
        default=False,
        help="Suppress info-level output (warnings and errors only)",
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


def build_eval_run_config(resolved: dict[str, Any]) -> "EvalRunConfig":
    """Build an EvalRunConfig from a resolved config dict.

    Maps CLI/config/env keys to EvalRunConfig fields with appropriate defaults.
    """
    from agent_evals.runner import EvalRunConfig

    return EvalRunConfig(
        repetitions=resolved.get("repetitions", 10),
        max_connections=resolved.get("max_connections", 10),
        max_tasks=resolved.get("max_tasks", 1),
        temperature=resolved.get("temperature", 0.3),
        max_tokens=resolved.get("max_tokens", 2048),
        use_cache=not resolved.get("no_cache", False),
        cache_dir=resolved.get("cache_dir", ".agent-evals-cache"),
        output_dir=resolved.get("output_dir", "reports"),
        display_mode=resolved.get("display", "rich"),
    )


def _run_evaluation(resolved: dict[str, Any]) -> int:
    """Execute an evaluation run from resolved configuration.

    Returns 0 on success, 1 on error.
    """
    from agent_evals.runner import EvalRunConfig, EvalRunner

    model = resolved.get("model")
    if not model:
        logger.error("--model is required (or set in config/env)")
        return 1

    # Validate API key upfront
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.error(
            "OPENROUTER_API_KEY is not set. "
            "Get your key at https://openrouter.ai/keys and set it:\n"
            "  export OPENROUTER_API_KEY=sk-or-v1-..."
        )
        return 1

    if not api_key.startswith("sk-or-"):
        logger.warning(
            "OPENROUTER_API_KEY does not start with 'sk-or-'. "
            "Verify your key format at https://openrouter.ai/keys"
        )

    run_config = build_eval_run_config(resolved)

    # Dry-run mode: log config and exit
    if resolved.get("dry_run", False):
        logger.info("Dry-run mode: resolved configuration:")
        for key, value in sorted(resolved.items()):
            logger.info("  %s: %r", key, value)
        return 0

    # Import heavy dependencies only when actually running
    from agent_evals.llm.client import LLMClient
    from agent_evals.tasks.loader import load_tasks
    from agent_evals.variants.registry import get_variants_for_axis

    # Build LLM client (api_key already validated above)
    client = LLMClient(
        model=model,
        api_key=api_key,
        temperature=run_config.temperature,
    )

    # Load tasks
    gold_standard_dir = Path(__file__).resolve().parent.parent.parent / "gold_standard"
    if not gold_standard_dir.is_dir():
        logger.error("Gold standard directory not found: %s", gold_standard_dir)
        return 1

    tasks = load_tasks(gold_standard_dir)

    # Filter tasks by type if specified
    task_filter = resolved.get("tasks")
    if task_filter:
        allowed_types = {t.strip() for t in task_filter.split(",")}
        tasks = [t for t in tasks if t.definition.type in allowed_types]

    # Filter by task_id if specified
    task_id_filter = resolved.get("task_id")
    if task_id_filter:
        tasks = [t for t in tasks if t.definition.task_id == task_id_filter]

    # Apply limit
    limit = resolved.get("limit")
    if limit is not None:
        tasks = tasks[:limit]

    if not tasks:
        logger.warning("No tasks matched the filter criteria.")
        return 1

    # Load variants
    from agent_evals.variants.registry import get_all_variants, load_all

    load_all()  # Auto-discover all variant modules

    axis = resolved.get("axis")
    variant_name = resolved.get("variant")
    if axis is not None:
        variants = get_variants_for_axis(axis)
    else:
        variants = get_all_variants()

    if variant_name:
        variants = [v for v in variants if v.metadata().name == variant_name]

    if not variants:
        logger.warning("No variants matched the filter criteria.")
        return 1

    # Load doc_tree
    from agent_evals.fixtures import load_sample_doc_tree

    doc_tree = load_sample_doc_tree()

    # Run evaluation
    runner = EvalRunner(client=client, config=run_config)
    result = runner.run(tasks=tasks, variants=variants, doc_tree=doc_tree)

    logger.info(
        "Evaluation complete: %d trials, $%.4f cost, %.1fs elapsed",
        len(result.trials),
        result.total_cost,
        result.elapsed_seconds,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``agent-evals`` CLI.

    Returns 0 on success, 1 on error.
    """
    from agent_evals.logging_config import configure_logging

    parser = build_parser()
    args = parser.parse_args(argv)

    # Initialize logging before anything else
    verbosity = 1 if args.verbose else (-1 if args.quiet else 0)
    configure_logging(verbosity)

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

    return _run_evaluation(resolved)


if __name__ == "__main__":
    sys.exit(main())
