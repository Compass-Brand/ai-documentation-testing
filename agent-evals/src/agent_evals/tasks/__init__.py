"""Task definitions, base classes, and YAML loading for agent-evals.

Public API:
    - ``TaskDefinition`` -- Pydantic model for YAML task schema validation.
    - ``EvalTask`` -- ABC that all task types must subclass.
    - ``GenericTask`` -- Concrete fallback task for unimplemented types.
    - ``TASK_TYPES`` -- Registry mapping type names to EvalTask subclasses.
    - ``register_task_type`` -- Register a new task type implementation.
    - ``load_task`` -- Load a single YAML file into an EvalTask.
    - ``load_tasks`` -- Load all YAML files from a directory into EvalTask instances.
"""

from agent_evals.tasks.base import (
    TASK_TYPES,
    EvalTask,
    GenericTask,
    TaskDefinition,
    register_task_type,
)
from agent_evals.tasks.loader import load_task, load_tasks

__all__ = [
    "TASK_TYPES",
    "EvalTask",
    "GenericTask",
    "TaskDefinition",
    "load_task",
    "load_tasks",
    "register_task_type",
]
