"""Abstention metric: correct refusal on unanswerable tasks.

Tracks whether the agent correctly abstains from answering when a task
is unanswerable, and correctly provides an answer when it is answerable.
"""

from __future__ import annotations

from agent_evals.metrics.base import Metric, MetricContext

# Phrases that indicate the agent is abstaining from answering.
_ABSTENTION_PHRASES: list[str] = [
    "not available",
    "cannot be determined",
    "no information",
    "not found in",
    "don't have",
    "unable to find",
    "not in the documentation",
    "unanswerable",
    "i don't know",
    "cannot answer",
]


def _has_abstention(response: str) -> bool:
    """Return True if *response* contains any abstention phrase."""
    lower = response.lower()
    return any(phrase in lower for phrase in _ABSTENTION_PHRASES)


class AbstentionMetric(Metric):
    """Abstention correctness metric.

    Score semantics:
        For **unanswerable** tasks (``answerable is False``):
            1.0 = response contains an abstention phrase (correct refusal).
            0.0 = response does not contain an abstention phrase.

        For **answerable** tasks (``answerable is True`` or not present):
            1.0 = response does NOT contain an abstention phrase.
            0.0 = response contains an abstention phrase (incorrect refusal).
    """

    @property
    def name(self) -> str:  # noqa: D102
        return "abstention"

    def compute(self, response: str, context: MetricContext) -> float:
        """Compute abstention correctness score.

        Args:
            response: The agent's textual response.
            context: ``task_definition`` may contain ``answerable`` (bool).

        Returns:
            ``1.0`` or ``0.0``.
        """
        answerable = context.task_definition.get("answerable")
        abstained = _has_abstention(response)

        if answerable is False:
            # Unanswerable task: abstention is correct.
            return 1.0 if abstained else 0.0

        # Answerable (or unspecified): abstention is incorrect.
        return 0.0 if abstained else 1.0
