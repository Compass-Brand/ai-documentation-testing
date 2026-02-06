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
    - ``CompositionalTask`` -- Task type for compositional reasoning evaluation.
    - ``FactExtractionTask`` -- Task type for fact extraction evaluation.
    - ``MultiHopTask`` -- Task type for multi-hop reasoning evaluation.
    - ``NegativeTask`` -- Task type for unanswerable question evaluation.
    - ``RetrievalTask`` -- Task type for file retrieval evaluation.
    - ``RobustnessTask`` -- Task type for perturbation robustness evaluation.
    - ``ConflictingTask`` -- Task type for conflicting information evaluation.
    - ``DisambiguationTask`` -- Task type for disambiguation evaluation.
    - ``EfficiencyTask`` -- Task type for efficiency evaluation.
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
from agent_evals.tasks.compositional import CompositionalTask
from agent_evals.tasks.conflicting import ConflictingTask
from agent_evals.tasks.disambiguation import DisambiguationTask
from agent_evals.tasks.efficiency import EfficiencyTask
from agent_evals.tasks.fact_extraction import FactExtractionTask
from agent_evals.tasks.loader import load_task, load_tasks
from agent_evals.tasks.multi_hop import MultiHopTask
from agent_evals.tasks.negative import NegativeTask
from agent_evals.tasks.retrieval import RetrievalTask
from agent_evals.tasks.robustness import RobustnessTask

__all__ = [
    "TASK_TYPES",
    "AgenticTask",
    "CodeGenerationTask",
    "CompositionalTask",
    "ConflictingTask",
    "DisambiguationTask",
    "EfficiencyTask",
    "EvalTask",
    "FactExtractionTask",
    "GenericTask",
    "MultiHopTask",
    "NegativeTask",
    "RetrievalTask",
    "RobustnessTask",
    "TaskDefinition",
    "load_task",
    "load_tasks",
    "register_task_type",
]
