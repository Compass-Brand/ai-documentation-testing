"""Stability metrics for evaluation consistency analysis."""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_evals.metrics import CostMetrics


@dataclass
class StabilityMetrics:
    """Consistency metrics across repeated runs."""

    mean: float
    std_dev: float
    coefficient_of_variation: float
    min_max_spread: float
    count: int


def compute_stability(
    scores: list[float],
    *,
    exclude_fallbacks: bool = False,
    cost_metrics_list: list[CostMetrics] | None = None,
) -> StabilityMetrics:
    """Compute stability metrics from a list of scores.

    Coefficient of variation = std_dev / mean (0 = perfectly stable).
    Min/max spread = max - min across runs.
    """
    if exclude_fallbacks and cost_metrics_list is not None:
        filtered = [
            (s, cm) for s, cm in zip(scores, cost_metrics_list)
            if cm.provider_fallbacks == 0
        ]
        scores = [s for s, _ in filtered]

    if len(scores) <= 1:
        mean = scores[0] if scores else 0.0
        return StabilityMetrics(
            mean=mean,
            std_dev=0.0,
            coefficient_of_variation=0.0,
            min_max_spread=0.0,
            count=len(scores),
        )

    mean = statistics.mean(scores)
    std_dev = statistics.stdev(scores)
    cv = std_dev / mean if mean != 0 else 0.0

    return StabilityMetrics(
        mean=mean,
        std_dev=std_dev,
        coefficient_of_variation=cv,
        min_max_spread=max(scores) - min(scores),
        count=len(scores),
    )


def compare_strategy_stability(
    trials_by_strategy: dict[str, list[float]],
) -> dict[str, StabilityMetrics]:
    """Compute stability metrics independently for each strategy."""
    return {
        strategy: compute_stability(scores)
        for strategy, scores in trials_by_strategy.items()
    }
