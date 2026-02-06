"""Evaluation metrics for agent-evals.

Public API:
    Metric              -- Abstract base class for all metrics.
    MetricContext        -- Shared context passed to every metric computation.
    AbstentionMetric     -- Correct abstention on unanswerable tasks.
    ConsistencyMetric    -- Response consistency across repetitions.
    FaithfulnessMetric   -- Keyword-overlap faithfulness approximation.
    FirstAttemptMetric   -- First-attempt success metric.
    NavigationPathMetric -- File navigation efficiency metric.
    ToolCallMetric       -- Tool call efficiency metric.
"""

from __future__ import annotations

from agent_evals.metrics.abstention import AbstentionMetric
from agent_evals.metrics.base import Metric, MetricContext
from agent_evals.metrics.consistency import ConsistencyMetric
from agent_evals.metrics.faithfulness import FaithfulnessMetric
from agent_evals.metrics.first_attempt import FirstAttemptMetric
from agent_evals.metrics.navigation import NavigationPathMetric
from agent_evals.metrics.tool_calls import ToolCallMetric

__all__ = [
    "AbstentionMetric",
    "ConsistencyMetric",
    "FaithfulnessMetric",
    "FirstAttemptMetric",
    "Metric",
    "MetricContext",
    "NavigationPathMetric",
    "ToolCallMetric",
]
