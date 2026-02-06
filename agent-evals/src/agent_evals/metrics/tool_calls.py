"""Tool call efficiency metric.

Scores the agent on how few tool calls it needed.  Lower is better at
equal quality, normalized to the ``[0.0, 1.0]`` range.
"""

from __future__ import annotations

from agent_evals.metrics.base import Metric, MetricContext


class ToolCallMetric(Metric):
    """Tool call efficiency metric.

    Score semantics:
        1.0 = zero tool calls (perfect efficiency).
        0.0 = ``max_expected`` or more calls.

    Formula: ``1.0 - min(actual / max_expected, 1.0)``

    Args:
        max_expected: The number of calls at which the score bottoms out
            to 0.0.  Defaults to 10.
    """

    def __init__(self, max_expected: int = 10) -> None:
        self.max_expected = max_expected

    @property
    def name(self) -> str:  # noqa: D102
        return "tool_calls"

    def compute(self, response: str, context: MetricContext) -> float:
        """Compute tool-call efficiency score.

        Args:
            response: Unused for this metric (kept for interface conformance).
            context: Must contain ``tool_calls``.

        Returns:
            Float in ``[0.0, 1.0]``.
        """
        actual = len(context.tool_calls)
        ratio = actual / self.max_expected if self.max_expected > 0 else 1.0
        return 1.0 - min(ratio, 1.0)
