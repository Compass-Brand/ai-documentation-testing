"""CLI entry point for agent-evals: run evaluation axes, tasks, and variants."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from agent_evals.runner import EvalRunConfig
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _add_run_args(parser: argparse.ArgumentParser) -> None:
    """Add all evaluation run arguments to *parser*."""
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
        choices=["json", "csv", "both"],
        default=None,
        help="Output format (default: both)",
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

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        default=False,
        help="Skip failed trials and report partial results",
    )

    # Dataset sources
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help=(
            "Task source: gold_standard (default), dataset name, "
            "or comma-separated list"
        ),
    )
    parser.add_argument(
        "--dataset-limit",
        type=int,
        default=None,
        help="Max tasks per dataset (for cost control)",
    )
    parser.add_argument(
        "--dataset-cache-dir",
        type=str,
        default=None,
        help="Override cache directory (default: ~/.agent-evals/datasets/)",
    )
    parser.add_argument(
        "--prepare-datasets",
        type=str,
        default=None,
        help="Download + convert without running evals (name, comma-list, or 'all')",
    )
    parser.add_argument(
        "--list-datasets",
        action="store_true",
        default=False,
        help="Show available datasets with contamination risk",
    )

    # Taguchi / multi-model configuration
    parser.add_argument(
        "--mode",
        choices=["full", "taguchi"],
        default=None,
        help="Evaluation mode (default: full)",
    )
    parser.add_argument(
        "--models",
        type=str,
        default=None,
        help="Comma-separated list of models for multi-model evaluation",
    )
    parser.add_argument(
        "--oa-type",
        type=str,
        default=None,
        help="Force specific Taguchi OA (e.g. L54). Default: auto-select",
    )
    parser.add_argument(
        "--pipeline",
        choices=["auto", "semi"],
        default=None,
        help="Run full three-phase DOE pipeline (auto or semi-automatic)",
    )
    parser.add_argument(
        "--quality-type",
        choices=["larger_is_better", "smaller_is_better", "nominal_is_best"],
        default="larger_is_better",
        help="S/N ratio quality type",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
        help="Number of top factors for Phase 3 factorial refinement",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="Significance threshold for ANOVA",
    )
    parser.add_argument(
        "--report",
        choices=["html", "markdown", "both", "none"],
        default=None,
        help="Research report format (in addition to JSON/CSV)",
    )
    parser.add_argument(
        "--budget",
        type=float,
        default=None,
        help="Budget cap in dollars",
    )
    parser.add_argument(
        "--model-budgets",
        type=str,
        default=None,
        help='Per-model budget caps, e.g. "claude=20.00,gpt-4o=30.00"',
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        default=False,
        help="Start web dashboard on localhost:8080",
    )
    parser.add_argument(
        "--model-group",
        type=str,
        default=None,
        help="Model group name to use (combinable with --models, union)",
    )
    parser.add_argument(
        "--sync-interval",
        type=float,
        default=None,
        help="Model sync interval in hours (default: 6)",
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


def _add_dashboard_args(parser: argparse.ArgumentParser) -> None:
    """Add dashboard-specific arguments to *parser*."""
    parser.add_argument(
        "--db-dir",
        type=str,
        default=None,
        help="Base directory for database files (default: ~/.observatory/)",
    )
    parser.add_argument(
        "--observatory-db",
        type=str,
        default=None,
        help="Path to observatory database file",
    )
    parser.add_argument(
        "--models-db",
        type=str,
        default=None,
        help="Path to models database file",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to listen on (default: 8080)",
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        default=False,
        help="Disable automatic model catalog sync",
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


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser with subcommands.

    Supports:
      agent-evals [run] [--model ...] -- evaluation run (backward compat)
      agent-evals dashboard [--port ...] -- standalone dashboard
    """
    parser = argparse.ArgumentParser(
        prog="agent-evals",
        description="Run evaluation axes to test documentation index formats.",
    )
    parser.set_defaults(command=None)

    # Add all run args to the top-level parser for backward compat
    _add_run_args(parser)

    subparsers = parser.add_subparsers(dest="command")

    # 'run' subcommand (explicit)
    run_parser = subparsers.add_parser(
        "run", help="Run evaluation axes (default behavior)",
    )
    _add_run_args(run_parser)

    # 'dashboard' subcommand
    dash_parser = subparsers.add_parser(
        "dashboard", help="Start the observatory web dashboard",
    )
    _add_dashboard_args(dash_parser)

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
    except (yaml.YAMLError, OSError) as exc:
        logger.warning("Failed to parse config file %s: %s", config_path, exc)
        return {}

    if not isinstance(data, dict):
        logger.warning(
            "Config file %s does not contain a YAML mapping (got %s)",
            config_path,
            type(data).__name__,
        )
        return {}

    return dict(data)


# Mapping from config/env key names to their expected Python types.
_CONFIG_KEYS: dict[str, type] = {
    "axis": int,
    "tasks": str,
    "task_id": str,
    "variant": str,
    "model": str,
    "limit": int,
    "repetitions": int,
    "temperature": float,
    "max_connections": int,
    "max_tasks": int,
    "dry_run": bool,
    "no_cache": bool,
    "output_dir": str,
    "output_format": str,
    "display": str,
    "continue_on_error": bool,
    "source": str,
    "dataset_limit": int,
    "dataset_cache_dir": str,
    "prepare_datasets": str,
    "list_datasets": bool,
    "mode": str,
    "models": str,
    "oa_type": str,
    "pipeline": str,
    "quality_type": str,
    "top_k": int,
    "alpha": float,
    "report": str,
    "budget": float,
    "model_budgets": str,
    "dashboard": bool,
    "model_group": str,
    "sync_interval": float,
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
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "Could not parse env var %s=%r as %s: %s",
                    env_name, env_value, target_type.__name__, exc,
                )
            else:
                continue

        # 3. Config file
        if key in config:
            resolved[key] = config[key]

    return resolved


def build_eval_run_config(resolved: dict[str, Any]) -> EvalRunConfig:
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
        output_format=resolved.get("output_format", "both"),
        display_mode=resolved.get("display", "rich"),
        continue_on_error=resolved.get("continue_on_error", False),
    )


def _run_evaluation(resolved: dict[str, Any]) -> int:
    """Execute an evaluation run from resolved configuration.

    Returns 0 on success, 1 on error.
    """
    from agent_evals.runner import EvalRunner

    # --list-datasets: show available datasets and exit (no model needed)
    if resolved.get("list_datasets"):
        from agent_evals.datasets import list_available, load_all as load_all_datasets

        load_all_datasets()
        available = list_available()
        if not available:
            logger.info("Available datasets: none registered")
        else:
            logger.info("Available datasets:")
            for ds in available:
                logger.info(
                    "  %-20s  %-15s  contamination=%s  license=%s",
                    ds["name"],
                    ds["task_type"],
                    ds["contamination_risk"],
                    ds["license"],
                )
        return 0

    # --prepare-datasets: download + convert without running evals (no model needed)
    prepare = resolved.get("prepare_datasets")
    if prepare is not None:
        from agent_evals.datasets import get_adapter, load_all as load_all_datasets
        from agent_evals.datasets.cache import DatasetCache

        load_all_datasets()

        cache_dir = resolved.get("dataset_cache_dir")
        cache = DatasetCache(
            cache_dir=Path(cache_dir) if cache_dir else None,
        )
        limit = resolved.get("dataset_limit")

        names = [n.strip() for n in prepare.split(",")]
        for name in names:
            try:
                adapter = get_adapter(name)
            except KeyError:
                logger.error("Unknown dataset: '%s'", name)
                return 1
            task_dir = cache.task_dir(name)
            logger.info("Preparing dataset '%s' -> %s", name, task_dir)
            count = adapter.convert_tasks(task_dir, limit=limit)
            doc_tree = adapter.build_doc_tree(limit=limit)
            dt_path = cache.doc_tree_path(name)
            dt_path.write_text(
                doc_tree.model_dump_json(indent=2), encoding="utf-8",
            )
            cache.mark_prepared(name, count)
            logger.info("Prepared %d tasks for '%s'", count, name)
        return 0

    model = resolved.get("model")
    if not model:
        logger.error("--model is required (or set in config/env)")
        return 1

    run_config = build_eval_run_config(resolved)

    # Check API key format early so warnings are visible even in dry-run mode.
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if api_key and not api_key.startswith("sk-or-"):
        logger.warning(
            "OPENROUTER_API_KEY does not start with 'sk-or-'. "
            "Verify your key format at https://openrouter.ai/keys"
        )

    # Dry-run mode: log config and exit (no API key needed)
    if resolved.get("dry_run", False):
        logger.info("Dry-run mode: resolved configuration:")
        for key, value in sorted(resolved.items()):
            logger.info("  %s: %r", key, value)

        # For taguchi mode, also show the OA design
        mode = resolved.get("mode", "full")
        if mode == "taguchi":
            from agent_evals.variants.registry import (
                get_all_variants,
                get_variants_for_axis,
                load_all,
            )

            load_all()
            axis = resolved.get("axis")
            if axis is not None:
                all_variants = get_variants_for_axis(axis)
            else:
                all_variants = get_all_variants()

            axes: dict[int, list[str]] = {}
            for v in all_variants:
                m = v.metadata()
                if m.axis == 0:
                    continue  # Baselines are not Taguchi factors
                if m.axis not in axes:
                    axes[m.axis] = []
                if m.name not in axes[m.axis]:
                    axes[m.axis].append(m.name)

            models_str = resolved.get("models")
            models_list: list[str] | None = None
            if models_str:
                models_list = [m.strip() for m in str(models_str).split(",")]

            from agent_evals.taguchi.factors import build_design

            oa_override = resolved.get("oa_type")
            design = build_design(
                axes,
                models=models_list,
                oa_override=str(oa_override) if oa_override else None,
            )
            logger.info(
                "Taguchi design: OA=%s, %d runs, %d factors",
                design.oa_name, design.n_runs, len(design.factors),
            )
            for factor in design.factors:
                logger.info(
                    "  Factor %s: %d levels %s",
                    factor.name, factor.n_levels, factor.level_names,
                )
            reps = resolved.get("repetitions", 10)
            logger.info(
                "  Estimated trials per task: %d (OA runs) x %d (reps) = %d",
                design.n_runs, reps, design.n_runs * int(reps),
            )
        return 0

    # Validate API key upfront (only needed for actual runs)
    if not api_key:
        logger.error(
            "OPENROUTER_API_KEY is not set. "
            "Get your key at https://openrouter.ai/keys and set it:\n"
            "  export OPENROUTER_API_KEY=sk-or-v1-..."
        )
        return 1

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

    # Load tasks and doc_tree based on --source
    from agent_evals.source import (
        SourceNotPreparedError,
        load_doc_tree_for_source,
        load_tasks_for_source,
    )

    source = resolved.get("source") or "gold_standard"

    try:
        tasks = load_tasks_for_source(source)
    except FileNotFoundError:
        logger.error("Gold standard directory not found.")
        return 1
    except SourceNotPreparedError:
        logger.error(
            "Dataset '%s' has not been prepared. Run first:\n"
            "  agent-evals --prepare-datasets %s",
            source,
            source,
        )
        return 1

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
    doc_tree = load_doc_tree_for_source(source)

    # Route to the correct runner based on --mode
    mode = resolved.get("mode", "full")

    if mode == "taguchi":
        pipeline_mode = resolved.get("pipeline")
        if pipeline_mode:
            return _run_pipeline(
                resolved, tasks, variants, doc_tree, api_key, run_config,
            )
        return _run_taguchi(
            resolved, tasks, variants, doc_tree, api_key, run_config,
        )

    # Default: full mode via EvalRunner
    from agent_evals.progress import make_progress_callback

    display = run_config.display_mode or "rich"
    callback = make_progress_callback(display)

    runner = EvalRunner(client=client, config=run_config)
    result = runner.run(
        tasks=tasks, variants=variants, doc_tree=doc_tree,
        progress_callback=callback,
    )

    logger.info(
        "Evaluation complete: %d trials, $%.4f cost, %.1fs elapsed",
        len(result.trials),
        result.total_cost,
        result.elapsed_seconds,
    )
    return 0


def _run_taguchi(
    resolved: dict[str, Any],
    tasks: list,
    variants: list,
    doc_tree: Any,
    api_key: str,
    run_config: EvalRunConfig,
) -> int:
    """Execute a Taguchi DOE evaluation via EvalOrchestrator.

    Builds a TaguchiDesign from variant axes, creates the orchestrator,
    and runs the evaluation.

    Returns 0 on success, 1 on error.
    """
    from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig
    from agent_evals.taguchi.factors import build_design

    # Build axes dict from loaded variants (exclude axis 0 baselines -
    # they are control conditions, not experimental factors).
    axes: dict[int, list[str]] = {}
    for v in variants:
        m = v.metadata()
        if m.axis == 0:
            continue  # Baselines are not Taguchi factors
        if m.axis not in axes:
            axes[m.axis] = []
        if m.name not in axes[m.axis]:
            axes[m.axis].append(m.name)

    # Parse models list
    models_str = resolved.get("models")
    model = str(resolved["model"])
    if models_str:
        models_list = [m.strip() for m in str(models_str).split(",")]
    else:
        models_list = [model]

    # Build Taguchi design
    oa_override = resolved.get("oa_type")
    design = build_design(
        axes,
        models=models_list if len(models_list) > 1 else None,
        oa_override=str(oa_override) if oa_override else None,
    )
    logger.info(
        "Taguchi design: OA=%s, %d runs, %d factors",
        design.oa_name, design.n_runs, len(design.factors),
    )

    # Build variant lookup
    variant_lookup = {v.metadata().name: v for v in variants}

    # Parse model budgets
    model_budgets: dict[str, float] | None = None
    raw_budgets = resolved.get("model_budgets")
    if raw_budgets and isinstance(raw_budgets, str):
        model_budgets = {}
        for pair in raw_budgets.split(","):
            key, _, val = pair.partition("=")
            model_budgets[key.strip()] = float(val.strip())

    # Create orchestrator
    orch_config = OrchestratorConfig(
        mode="taguchi",
        models=models_list,
        api_key=api_key,
        report_format=resolved.get("report"),
        global_budget=resolved.get("budget"),
        model_budgets=model_budgets,
        temperature=run_config.temperature,
        eval_config=run_config,
        dashboard=resolved.get("dashboard", False),
        dashboard_port=int(resolved.get("dashboard_port", 8501)),
    )
    orchestrator = EvalOrchestrator(orch_config)

    orchestrator.start_dashboard()
    try:
        result = orchestrator.run(
            tasks=tasks,
            variants=variants,
            doc_tree=doc_tree,
            design=design,
            variant_lookup=variant_lookup,
        )
    finally:
        orchestrator.stop_dashboard()

    logger.info(
        "Taguchi evaluation complete: %d trials, $%.4f cost, %.1fs elapsed",
        len(result.trials),
        result.total_cost,
        result.elapsed_seconds,
    )
    return 0


def _run_pipeline(
    resolved: dict[str, Any],
    tasks: list,
    variants: list,
    doc_tree: Any,
    api_key: str,
    run_config: EvalRunConfig,
) -> int:
    """Execute a multi-phase DOE pipeline via DOEPipeline.

    Builds a PipelineConfig from resolved params and runs the full
    screening -> confirmation -> refinement flow.

    Returns 0 on success, 1 on error.
    """
    from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig
    from agent_evals.pipeline import DOEPipeline, PipelineConfig

    # Parse models list
    models_str = resolved.get("models")
    model = str(resolved["model"])
    if models_str:
        models_list = [m.strip() for m in str(models_str).split(",")]
    else:
        models_list = [model]

    # Parse model budgets
    model_budgets: dict[str, float] | None = None
    raw_budgets = resolved.get("model_budgets")
    if raw_budgets and isinstance(raw_budgets, str):
        model_budgets = {}
        for pair in raw_budgets.split(","):
            key, _, val = pair.partition("=")
            model_budgets[key.strip()] = float(val.strip())

    # Build orchestrator
    orch_config = OrchestratorConfig(
        mode="taguchi",
        models=models_list,
        api_key=api_key,
        report_format=resolved.get("report"),
        global_budget=resolved.get("budget"),
        model_budgets=model_budgets,
        temperature=run_config.temperature,
        eval_config=run_config,
        dashboard=resolved.get("dashboard", False),
        dashboard_port=int(resolved.get("dashboard_port", 8501)),
    )
    orchestrator = EvalOrchestrator(orch_config)

    # Build pipeline config
    pipeline_config = PipelineConfig(
        models=models_list,
        mode=str(resolved.get("pipeline", "auto")),
        quality_type=str(resolved.get("quality_type", "larger_is_better")),
        alpha=float(resolved.get("alpha", 0.05)),
        top_k=int(resolved.get("top_k", 3)),
        oa_override=resolved.get("oa_type"),
        report_format=resolved.get("report"),
        api_key=api_key,
        dashboard=resolved.get("dashboard", False),
        temperature=run_config.temperature,
        global_budget=resolved.get("budget"),
        model_budgets=model_budgets,
    )

    pipeline = DOEPipeline(config=pipeline_config, orchestrator=orchestrator)

    orchestrator.start_dashboard()
    try:
        result = pipeline.run(tasks=tasks, variants=variants, doc_tree=doc_tree)
    finally:
        orchestrator.stop_dashboard()

    logger.info(
        "DOE pipeline complete: %d trials, $%.4f cost, %.1fs elapsed",
        result.total_trials,
        result.total_cost,
        result.elapsed_seconds,
    )
    return 0


def _run_dashboard(args: argparse.Namespace) -> int:
    """Launch the observatory dashboard from CLI args.

    Returns 0 on success, 1 on error.
    """
    from agent_evals.observatory.web.server import DashboardConfig, launch_dashboard

    # Resolve database paths
    db_dir = Path(args.db_dir) if args.db_dir else Path.home() / ".observatory"
    observatory_db = Path(args.observatory_db) if args.observatory_db else db_dir / "observatory.db"
    models_db = Path(args.models_db) if args.models_db else db_dir / "models.db"

    log_level = "debug" if args.verbose else ("warning" if args.quiet else "info")

    config = DashboardConfig(
        observatory_db=observatory_db,
        models_db=models_db,
        host=args.host,
        port=args.port,
        log_level=log_level,
        auto_sync=not args.no_sync,
    )

    try:
        launch_dashboard(config, background=False)
    except KeyboardInterrupt:
        logger.info("Dashboard stopped.")

    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``agent-evals`` CLI.

    Returns 0 on success, 1 on error.
    """
    from agent_evals.logging_config import configure_logging

    parser = build_parser()
    args = parser.parse_args(argv)

    # Route dashboard subcommand
    if args.command == "dashboard":
        verbosity = 1 if args.verbose else (-1 if args.quiet else 0)
        configure_logging(verbosity)
        return _run_dashboard(args)

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


def dashboard_main(argv: list[str] | None = None) -> int:
    """Entry point for the ``observatory`` CLI command.

    Prepends 'dashboard' to argv and delegates to main().
    """
    if argv is None:
        argv = []
    return main(["dashboard", *argv])


if __name__ == "__main__":
    sys.exit(main())
