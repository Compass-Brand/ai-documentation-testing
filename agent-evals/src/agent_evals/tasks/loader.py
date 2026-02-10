"""YAML task loader for eval task definitions.

This module provides:
- load_task: Load a single YAML file into a validated EvalTask
- load_tasks: Load all YAML files from a directory into EvalTask instances

Imports ``agent_evals.tasks`` to ensure concrete task type registrations
are loaded before any TASK_TYPES lookups.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

logger = logging.getLogger(__name__)

from agent_evals.tasks.base import TASK_TYPES, EvalTask, TaskDefinition

_registered = False


def _ensure_registered() -> None:
    """Ensure all concrete task types have been registered.

    When this module is imported directly (e.g. ``from
    agent_evals.tasks.loader import load_task``) the package
    ``__init__.py`` may not have run yet, leaving TASK_TYPES with only
    GenericTask defaults.  This guard triggers the concrete imports
    exactly once.
    """
    global _registered  # noqa: PLW0603
    if _registered:
        return
    from agent_evals.tasks.base import load_all_task_types

    load_all_task_types()
    _registered = True


def load_task(path: Path) -> EvalTask:
    """Load a single YAML task definition and return an EvalTask instance.

    The YAML file is parsed, validated against TaskDefinition, and then
    the appropriate EvalTask subclass is looked up from the TASK_TYPES
    registry based on the task's ``type`` field.

    Args:
        path: Path to a YAML file (.yaml or .yml).

    Returns:
        An EvalTask instance (or subclass) wrapping the validated definition.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the YAML is malformed, fails schema validation,
            or the task type is not registered.
    """
    _ensure_registered()

    path = Path(path)

    if not path.exists():
        msg = f"Task file not found: {path}"
        raise FileNotFoundError(msg)

    raw_text = path.read_text(encoding="utf-8")

    try:
        data = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        msg = f"Invalid YAML in {path}: {exc}"
        raise ValueError(msg) from exc

    if not isinstance(data, dict):
        msg = f"Invalid YAML in {path}: expected a mapping, got {type(data).__name__}"
        raise ValueError(msg)

    # Validate against Pydantic model
    try:
        definition = TaskDefinition(**data)
    except ValidationError as exc:
        msg = f"Task validation failed for {path}: {exc}"
        raise ValueError(msg) from exc

    # Look up the registered task class for this type
    task_cls = TASK_TYPES.get(definition.type)
    if task_cls is None:
        msg = (
            f"No registered task class for type '{definition.type}'. "
            f"Registered types: {sorted(TASK_TYPES.keys())}"
        )
        raise ValueError(msg)

    return task_cls(definition)


def load_tasks(directory: Path, *, strict: bool = True) -> list[EvalTask]:
    """Load all YAML task definitions from a directory.

    Recursively scans the directory for files with .yaml or .yml extensions,
    loads each one, and returns the resulting tasks sorted by task_id.

    Args:
        directory: Path to a directory containing YAML task files.
        strict: When True (default), raise on the first invalid file.
            When False, log warnings and skip invalid files.

    Returns:
        List of EvalTask instances sorted by task_id.

    Raises:
        FileNotFoundError: If the directory does not exist.
        ValueError: If strict=True and a file fails validation.
    """
    directory = Path(directory)

    if not directory.exists():
        msg = f"Task directory not found: {directory}"
        raise FileNotFoundError(msg)

    tasks: list[EvalTask] = []
    errors: list[tuple[Path, Exception]] = []

    yaml_paths = sorted(
        [*directory.rglob("*.yaml"), *directory.rglob("*.yml")]
    )
    for yaml_path in yaml_paths:
        try:
            task = load_task(yaml_path)
            tasks.append(task)
        except (ValueError, FileNotFoundError) as exc:
            if strict:
                raise
            errors.append((yaml_path, exc))
            logger.warning("Skipping %s: %s", yaml_path, exc)

    if errors:
        logger.warning(
            "Loaded %d tasks, skipped %d invalid files",
            len(tasks), len(errors),
        )

    # Check for duplicate task_ids
    seen_ids: dict[str, Path] = {}
    loaded_paths = [p for p in yaml_paths if p not in {e[0] for e in errors}]
    for task, yaml_path in zip(tasks, loaded_paths):
        tid = task.definition.task_id
        if tid in seen_ids:
            msg = (
                f"Duplicate task_id '{tid}' found in {yaml_path} "
                f"(first seen in {seen_ids[tid]})"
            )
            raise ValueError(msg)
        seen_ids[tid] = yaml_path

    # Sort by task_id for deterministic ordering
    tasks.sort(key=lambda t: t.definition.task_id)

    return tasks
