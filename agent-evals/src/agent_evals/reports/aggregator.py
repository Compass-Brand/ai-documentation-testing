"""Aggregate raw trial results into report-ready summaries.

Provides by-variant, by-task-type, and by-source breakdowns of trial
scores, plus reproducibility metadata (config, model versions).
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from agent_evals.runner import EvalRunConfig, TrialResult


@dataclass
class VariantSummary:
    """Aggregated statistics for a group of trials."""

    count: int
    mean_score: float
    total_cost: float
    std_dev: float = 0.0
    median: float = 0.0
    ci_lower: float | None = None
    ci_upper: float | None = None


@dataclass
class ReportData:
    """Complete aggregated report data.

    Attributes:
        config: The evaluation run configuration.
        total_trials: Total number of trials aggregated.
        total_cost: Sum of all trial costs.
        by_variant: Per-variant score summaries.
        by_task_type: Per-task-type score summaries.
        by_source: Per-source score summaries.
        model_versions: Mapping of requested model to actual API version.
    """

    config: EvalRunConfig
    total_trials: int
    total_cost: float
    by_variant: dict[str, VariantSummary]
    by_task_type: dict[str, VariantSummary]
    by_source: dict[str, VariantSummary]
    model_versions: dict[str, str] = field(default_factory=dict)
    phase_results: dict[str, Any] | None = None
    context_strategy: str = "full_context"
    strategy_comparison: dict | None = None


def _summarize(trials: list[TrialResult]) -> VariantSummary:
    """Compute summary statistics for a group of trials."""
    count = len(trials)
    mean_score = sum(t.score for t in trials) / count if count else 0.0
    total_cost = sum(t.cost for t in trials if t.cost is not None)

    scores = [t.score for t in trials]
    std_dev = statistics.stdev(scores) if count >= 2 else 0.0
    median = statistics.median(scores) if count >= 1 else 0.0

    if count >= 2:
        se = std_dev / (count ** 0.5)
        ci_lower = mean_score - 1.96 * se
        ci_upper = mean_score + 1.96 * se
    else:
        ci_lower = None
        ci_upper = None

    return VariantSummary(
        count=count,
        mean_score=mean_score,
        total_cost=total_cost,
        std_dev=std_dev,
        median=median,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
    )


def _group_and_summarize(
    trials: list[TrialResult],
    key_fn: Callable[[TrialResult], str],
) -> dict[str, VariantSummary]:
    """Group trials by key function and summarize each group."""
    groups: dict[str, list[TrialResult]] = defaultdict(list)
    for trial in trials:
        groups[key_fn(trial)].append(trial)
    return {k: _summarize(v) for k, v in groups.items()}


def aggregate(
    trials: list[TrialResult],
    *,
    config: EvalRunConfig,
    model_versions: dict[str, str] | None = None,
    phase_results: dict[str, Any] | None = None,
) -> ReportData:
    """Aggregate trial results into report data.

    Args:
        trials: List of completed trial results.
        config: The evaluation run configuration.
        model_versions: Optional mapping of requested model names
            to actual API model versions.
        phase_results: Optional DOE pipeline phase results
            (screening, confirmation, refinement data).

    Returns:
        ReportData with all breakdowns computed.
    """
    total_cost = sum(t.cost for t in trials if t.cost is not None)

    return ReportData(
        config=config,
        total_trials=len(trials),
        total_cost=total_cost,
        by_variant=_group_and_summarize(trials, lambda t: t.variant_name),
        by_task_type=_group_and_summarize(trials, lambda t: t.task_type),
        by_source=_group_and_summarize(trials, lambda t: t.source),
        model_versions=model_versions or {},
        phase_results=phase_results,
    )
