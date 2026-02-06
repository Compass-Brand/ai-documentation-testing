"""Abstract base class for metrics and the shared MetricContext."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricContext:
    """Context provided to every metric computation.

    Attributes:
        task_definition: The task YAML parsed as a dict.
        index_content: The documentation index that was provided to the agent.
        source_documents: Actual document contents (for faithfulness checking).
        tool_calls: Tool calls made during the task.
        attempt_number: Which attempt this is (1-based).
        task_score: Overall task correctness score, if available.
    """

    task_definition: dict[str, Any]
    index_content: str
    source_documents: list[str]
    tool_calls: list[dict[str, Any]]
    attempt_number: int
    task_score: float | None = field(default=None)


class Metric(ABC):
    """Abstract base class for all evaluation metrics.

    Subclasses must implement ``name`` and ``compute``.  The ``compute``
    method should always return a value in the ``[0.0, 1.0]`` range.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Metric identifier."""
        ...

    @abstractmethod
    def compute(self, response: str, context: MetricContext) -> float:
        """Compute metric value.

        Args:
            response: The agent's textual response.
            context: Shared evaluation context.

        Returns:
            A float in the range ``[0.0, 1.0]``.
        """
        ...
