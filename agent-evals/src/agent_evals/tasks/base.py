"""Base task classes and Pydantic models for eval task definitions.

This module provides:
- TaskDefinition: Pydantic model for YAML task schema validation
- EvalTask: Abstract base class for all eval task types
- GenericTask: Concrete fallback task for types without custom implementations
- TASK_TYPES: Registry mapping type names to EvalTask subclasses
- register_task_type: Function to register new task type implementations
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_TASK_TYPES: set[str] = {
    "retrieval",
    "fact_extraction",
    "code_generation",
    "agentic",
    "multi_hop",
    "negative",
    "compositional",
    "robustness",
    "disambiguation",
    "conflicting",
    "efficiency",
}

VALID_DOMAINS: set[str] = {
    "framework_api",
    "project_repo",
    "skills_workflows",
}

VALID_DIFFICULTIES: set[str] = {
    "easy",
    "medium",
    "hard",
    "edge",
}

# Pattern: one or more lowercase word segments separated by underscores,
# ending with underscore + one or more digits.
# Matches: retrieval_001, multi_hop_042, code_generation_python_001
TASK_ID_PATTERN: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*_\d+$")


# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------


class TaskDefinition(BaseModel):
    """Pydantic v2 model for a single eval task definition.

    Validates all fields from the YAML task schema, including pattern-based
    validation on task_id and literal validation on type, domain, and
    difficulty.
    """

    task_id: str
    type: str
    question: str
    domain: str
    difficulty: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("task_id")
    @classmethod
    def validate_task_id(cls, v: str) -> str:
        """Validate task_id matches pattern: {type}_{digits} or {type}_{subtype}_{digits}."""
        if not TASK_ID_PATTERN.match(v):
            msg = (
                f"task_id '{v}' does not match required pattern. "
                "Expected format: {{type}}_{{number}} (e.g., retrieval_001) "
                "or {{type}}_{{subtype}}_{{number}} (e.g., code_generation_python_001)"
            )
            raise ValueError(msg)
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Validate type is one of the 11 defined task types."""
        if v not in VALID_TASK_TYPES:
            msg = f"type '{v}' is not valid. Must be one of: {sorted(VALID_TASK_TYPES)}"
            raise ValueError(msg)
        return v

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        """Validate domain is one of the 3 defined domains."""
        if v not in VALID_DOMAINS:
            msg = f"domain '{v}' is not valid. Must be one of: {sorted(VALID_DOMAINS)}"
            raise ValueError(msg)
        return v

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: str) -> str:
        """Validate difficulty is one of: easy, medium, hard, edge."""
        if v not in VALID_DIFFICULTIES:
            msg = f"difficulty '{v}' is not valid. Must be one of: {sorted(VALID_DIFFICULTIES)}"
            raise ValueError(msg)
        return v


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class EvalTask(ABC):
    """Abstract base class for all eval task types.

    Subclasses must implement build_prompt() and score_response().
    Each task wraps a validated TaskDefinition with the YAML-sourced
    configuration.
    """

    def __init__(self, definition: TaskDefinition) -> None:
        self.definition = definition

    @abstractmethod
    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build messages for an LLM call.

        Args:
            index_content: The documentation index content to include
                in the prompt context.

        Returns:
            List of message dicts with 'role' and 'content' keys,
            suitable for passing to an LLM API.
        """
        ...

    @abstractmethod
    def score_response(self, response: str, **kwargs: object) -> float:
        """Score an LLM response for this task.

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (e.g., reference answers).

        Returns:
            Score between 0.0 (worst) and 1.0 (best).
        """
        ...


# ---------------------------------------------------------------------------
# Generic fallback task
# ---------------------------------------------------------------------------


class GenericTask(EvalTask):
    """Generic task implementation for types without custom logic.

    Provides baseline build_prompt and score_response implementations.
    Specific task type subclasses (retrieval, code_generation, etc.)
    will override these in Stories 2.4-2.6.
    """

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build a simple prompt with index content and the question.

        Returns a two-message conversation: a system message providing
        the index content as context, and a user message with the question.
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant. Use the following documentation "
                    "index to answer the question.\n\n"
                    f"{index_content}"
                ),
            },
            {
                "role": "user",
                "content": self.definition.question,
            },
        ]

    def score_response(self, response: str, **kwargs: object) -> float:
        """Return a placeholder score.

        GenericTask always returns 0.0 since it has no task-specific
        scoring logic. Real scoring will be implemented in concrete
        task type subclasses.
        """
        return 0.0


# ---------------------------------------------------------------------------
# Task type registry
# ---------------------------------------------------------------------------

TASK_TYPES: dict[str, type[EvalTask]] = {}


def register_task_type(type_name: str, cls: type[EvalTask]) -> None:
    """Register an EvalTask subclass for a given task type name.

    Args:
        type_name: The type string (e.g., 'retrieval', 'code_generation').
        cls: The EvalTask subclass to use for that type.
    """
    TASK_TYPES[type_name] = cls


# Register GenericTask as default for all standard types
for _type_name in VALID_TASK_TYPES:
    register_task_type(_type_name, GenericTask)
