"""YAML task loader for eval task definitions.

This module provides:
- load_task: Load a single YAML file into a validated EvalTask
- load_tasks: Load all YAML files from a directory into EvalTask instances
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from agent_evals.tasks.base import TASK_TYPES, EvalTask, TaskDefinition


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


def load_tasks(directory: Path) -> list[EvalTask]:
    """Load all YAML task definitions from a directory.

    Recursively scans the directory for files with .yaml or .yml extensions,
    loads each one, and returns the resulting tasks sorted by task_id.

    Args:
        directory: Path to a directory containing YAML task files.

    Returns:
        List of EvalTask instances sorted by task_id.

    Raises:
        FileNotFoundError: If the directory does not exist.
    """
    directory = Path(directory)

    if not directory.exists():
        msg = f"Task directory not found: {directory}"
        raise FileNotFoundError(msg)

    tasks: list[EvalTask] = []

    yaml_paths = sorted(
        [*directory.rglob("*.yaml"), *directory.rglob("*.yml")]
    )
    for yaml_path in yaml_paths:
        task = load_task(yaml_path)
        tasks.append(task)

    # Check for duplicate task_ids
    seen_ids: dict[str, Path] = {}
    for task, yaml_path in zip(tasks, yaml_paths):
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
