"""Task definitions, base classes, and YAML loading for agent-evals.

Public API:
    - ``TaskDefinition`` -- Pydantic model for YAML task schema validation.
    - ``EvalTask`` -- ABC that all task types must subclass.
    - ``GenericTask`` -- Concrete fallback task for unimplemented types.
    - ``TASK_TYPES`` -- Registry mapping type names to EvalTask subclasses.
    - ``register_task_type`` -- Register a new task type implementation.
    - ``load_task`` -- Load a single YAML file into an EvalTask.
    - ``load_tasks`` -- Load all YAML files from a directory into EvalTask instances.
    - ``AgenticTask`` -- Task type for agentic coding evaluation.
    - ``CodeGenerationTask`` -- Task type for code generation evaluation.
    - ``FactExtractionTask`` -- Task type for fact extraction evaluation.
    - ``RetrievalTask`` -- Task type for file retrieval evaluation.
"""

# Import concrete task types to trigger registration via register_task_type().
# Each module calls register_task_type() at module level, overriding the
# GenericTask default for its type name.
from agent_evals.tasks.agentic import AgenticTask
from agent_evals.tasks.base import (
    TASK_TYPES,
    EvalTask,
    GenericTask,
    TaskDefinition,
    register_task_type,
)
from agent_evals.tasks.code_generation import CodeGenerationTask
from agent_evals.tasks.fact_extraction import FactExtractionTask
from agent_evals.tasks.loader import load_task, load_tasks
from agent_evals.tasks.retrieval import RetrievalTask

__all__ = [
    "TASK_TYPES",
    "AgenticTask",
    "CodeGenerationTask",
    "EvalTask",
    "FactExtractionTask",
    "GenericTask",
    "RetrievalTask",
    "TaskDefinition",
    "load_task",
    "load_tasks",
    "register_task_type",
]
