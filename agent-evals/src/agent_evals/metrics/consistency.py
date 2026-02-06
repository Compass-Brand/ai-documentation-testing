"""Consistency metric: Jaccard token overlap across repetitions.

Measures how consistently an agent responds to the same task across
multiple runs, using Jaccard similarity on word-level tokens.
"""

from __future__ import annotations

import re
from typing import Any

from agent_evals.metrics.base import Metric, MetricContext

_TOKEN_RE: re.Pattern[str] = re.compile(r"\b\w+\b")


def _tokenize(text: str) -> set[str]:
    """Tokenize *text* into a set of lowercase word tokens."""
    return set(_TOKEN_RE.findall(text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    """Compute Jaccard similarity between two sets.

    Returns 1.0 when both sets are empty (degenerate case).
    """
    if not a and not b:
        return 1.0
    union = a | b
    if not union:  # pragma: no cover — unreachable after the above guard
        return 1.0
    return len(a & b) / len(union)


class ConsistencyMetric(Metric):
    """Response consistency metric via Jaccard token overlap.

    Compares the current response against prior responses for the same
    task.  Returns the mean pairwise Jaccard similarity.

    Score semantics:
        1.0 = identical token sets across all repetitions (or first run).
        0.0 = zero overlap with prior responses.
    """

    @property
    def name(self) -> str:  # noqa: D102
        return "consistency"

    def compute(self, response: str, context: MetricContext) -> float:
        """Compute consistency score.

        Args:
            response: The agent's textual response.
            context: ``task_definition`` may contain ``prior_responses``.

        Returns:
            Float in ``[0.0, 1.0]``.
        """
        prior_responses: Any = context.task_definition.get("prior_responses", [])
        if not isinstance(prior_responses, list):
            prior_responses = []

        if len(prior_responses) == 0:
            return 1.0

        current_tokens = _tokenize(response)
        similarities: list[float] = []

        for prior in prior_responses:
            prior_tokens = _tokenize(str(prior))
            similarities.append(_jaccard(current_tokens, prior_tokens))

        return sum(similarities) / len(similarities)
