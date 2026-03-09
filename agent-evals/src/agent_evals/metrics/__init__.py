"""Evaluation metrics for agent-evals.

Public API:
    Metric              -- Abstract base class for all metrics.
    MetricContext        -- Shared context passed to every metric computation.
    AbstentionMetric     -- Correct abstention on unanswerable tasks.
    ConsistencyMetric    -- Response consistency across repetitions.
    CostMetrics          -- Aggregated operational metrics for a trial.
    FaithfulnessMetric   -- Keyword-overlap faithfulness approximation.
    FirstAttemptMetric   -- First-attempt success metric.
    NavigationPathMetric -- File navigation efficiency metric.
    ToolCallMetric       -- Tool call efficiency metric.
    TurnMetrics          -- Per-turn metrics for multi-turn strategies.
    aggregate_turn_metrics -- Aggregate TurnMetrics into CostMetrics.
"""

from __future__ import annotations

from agent_evals.metrics.abstention import AbstentionMetric
from agent_evals.metrics.base import Metric, MetricContext
from agent_evals.metrics.consistency import ConsistencyMetric
from agent_evals.metrics.faithfulness import FaithfulnessMetric
from agent_evals.metrics.first_attempt import FirstAttemptMetric
from agent_evals.metrics.navigation import NavigationPathMetric
from agent_evals.metrics.operational import (
    CostMetrics,
    TurnMetrics,
    aggregate_turn_metrics,
)
from agent_evals.metrics.tool_calls import ToolCallMetric

__all__ = [
    "AbstentionMetric",
    "ConsistencyMetric",
    "CostMetrics",
    "FaithfulnessMetric",
    "FirstAttemptMetric",
    "Metric",
    "MetricContext",
    "NavigationPathMetric",
    "ToolCallMetric",
    "TurnMetrics",
    "aggregate_turn_metrics",
]
