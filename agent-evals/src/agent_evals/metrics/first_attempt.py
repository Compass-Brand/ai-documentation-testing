"""First-attempt success metric.

Binary metric: was the task solved correctly on the very first attempt?
"""

from __future__ import annotations

from agent_evals.metrics.base import Metric, MetricContext


class FirstAttemptMetric(Metric):
    """First-attempt success metric.

    Score semantics:
        1.0 = first attempt **and** ``task_score >= success_threshold``.
        0.0 = otherwise (not first attempt, score below threshold, or no
              score available).

    Args:
        success_threshold: Minimum ``task_score`` to count as a success.
            Defaults to 0.5.
    """

    def __init__(self, success_threshold: float = 0.5) -> None:
        self.success_threshold = success_threshold

    @property
    def name(self) -> str:  # noqa: D102
        return "first_attempt"

    def compute(self, response: str, context: MetricContext) -> float:
        """Compute first-attempt success.

        Args:
            response: Unused for this metric (kept for interface conformance).
            context: Must contain ``attempt_number`` and ``task_score``.

        Returns:
            ``1.0`` or ``0.0``.
        """
        if context.attempt_number != 1:
            return 0.0
        if context.task_score is None:
            return 0.0
        if context.task_score >= self.success_threshold:
            return 1.0
        return 0.0
