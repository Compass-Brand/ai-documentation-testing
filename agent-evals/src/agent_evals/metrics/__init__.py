"""Evaluation metrics for agent-evals.

Public API:
    Metric            -- Abstract base class for all metrics.
    MetricContext      -- Shared context passed to every metric computation.
    FaithfulnessMetric -- Keyword-overlap faithfulness approximation.
    ToolCallMetric     -- Tool call efficiency metric.
    FirstAttemptMetric -- First-attempt success metric.
"""

from __future__ import annotations

from agent_evals.metrics.base import Metric, MetricContext
from agent_evals.metrics.faithfulness import FaithfulnessMetric
from agent_evals.metrics.first_attempt import FirstAttemptMetric
from agent_evals.metrics.tool_calls import ToolCallMetric

__all__ = [
    "FaithfulnessMetric",
    "FirstAttemptMetric",
    "Metric",
    "MetricContext",
    "ToolCallMetric",
]
