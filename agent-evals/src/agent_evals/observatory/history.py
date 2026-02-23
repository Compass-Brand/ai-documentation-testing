"""Observatory historical analytics: cross-run comparison and trends.

Provides functions for querying trials across multiple runs,
comparing run-level aggregates, tracking variant performance trends,
detecting regressions, and ranking models.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_evals.observatory.store import ObservatoryStore, TrialRecord


@dataclass
class VariantTrend:
    """Performance trend for a variant in a single run."""

    run_id: str
    avg_score: float
    avg_cost: float
    trial_count: int


def get_cross_run_trials(
    store: ObservatoryStore,
    run_ids: list[str],
    *,
    variant_name: str | None = None,
    model: str | None = None,
) -> list[TrialRecord]:
    """Query trials across multiple runs with optional filters.

    Args:
        store: The observatory store.
        run_ids: Run IDs to query.
        variant_name: If set, filter by variant.
        model: If set, filter by model.

    Returns:
        Combined list of TrialRecord from all specified runs.
    """
    all_trials: list[TrialRecord] = []
    for run_id in run_ids:
        trials = store.get_trials(run_id, model=model)
        if variant_name is not None:
            trials = [t for t in trials if t.variant_name == variant_name]
        all_trials.extend(trials)
    return all_trials


def _aggregate_trials(
    trials: list[TrialRecord],
) -> dict[str, Any]:
    """Compute aggregate stats for a list of trials."""
    if not trials:
        return {
            "total_trials": 0,
            "avg_score": 0.0,
            "total_cost": 0.0,
            "avg_latency": 0.0,
        }
    n = len(trials)
    total_cost = sum(t.cost or 0.0 for t in trials)
    return {
        "total_trials": n,
        "avg_score": sum(t.score for t in trials) / n,
        "total_cost": total_cost,
        "avg_latency": sum(t.latency_seconds for t in trials) / n,
    }


def compare_runs(
    store: ObservatoryStore,
    run_ids: list[str],
) -> list[dict[str, Any]]:
    """Compare aggregate statistics between runs.

    Args:
        store: The observatory store.
        run_ids: Run IDs to compare (in chronological order).

    Returns:
        List of dicts with run_id, total_trials, avg_score, total_cost,
        avg_latency, and score_delta (relative to previous run).
    """
    results: list[dict[str, Any]] = []
    prev_avg: float | None = None

    for run_id in run_ids:
        trials = store.get_trials(run_id)
        agg = _aggregate_trials(trials)
        entry: dict[str, Any] = {"run_id": run_id, **agg}

        if prev_avg is not None:
            entry["score_delta"] = agg["avg_score"] - prev_avg
        else:
            entry["score_delta"] = 0.0

        prev_avg = agg["avg_score"]
        results.append(entry)

    return results


def variant_performance_trend(
    store: ObservatoryStore,
    variant_name: str,
    run_ids: list[str],
) -> list[VariantTrend]:
    """Track a variant's performance across runs.

    Args:
        store: The observatory store.
        variant_name: The variant to track.
        run_ids: Run IDs in chronological order.

    Returns:
        List of VariantTrend, one per run that has data for this variant.
    """
    trends: list[VariantTrend] = []

    for run_id in run_ids:
        trials = store.get_trials(run_id)
        variant_trials = [
            t for t in trials if t.variant_name == variant_name
        ]
        if not variant_trials:
            continue

        n = len(variant_trials)
        trends.append(VariantTrend(
            run_id=run_id,
            avg_score=sum(t.score for t in variant_trials) / n,
            avg_cost=sum(t.cost or 0.0 for t in variant_trials) / n,
            trial_count=n,
        ))

    return trends


def detect_regressions(
    store: ObservatoryStore,
    baseline_run_id: str,
    comparison_run_id: str,
    *,
    threshold: float = 0.05,
) -> list[dict[str, Any]]:
    """Detect variants that regressed between two runs.

    A regression is when a variant's average score drops by more than
    the threshold.

    Args:
        store: The observatory store.
        baseline_run_id: The earlier run.
        comparison_run_id: The later run.
        threshold: Minimum score drop to flag as regression.

    Returns:
        List of dicts with variant, baseline_score, comparison_score, delta.
    """
    baseline_trials = store.get_trials(baseline_run_id)
    comparison_trials = store.get_trials(comparison_run_id)

    # Group by variant
    baseline_by_variant: dict[str, list[float]] = {}
    for t in baseline_trials:
        baseline_by_variant.setdefault(t.variant_name, []).append(t.score)

    comparison_by_variant: dict[str, list[float]] = {}
    for t in comparison_trials:
        comparison_by_variant.setdefault(t.variant_name, []).append(t.score)

    regressions: list[dict[str, Any]] = []
    for variant, base_scores in baseline_by_variant.items():
        comp_scores = comparison_by_variant.get(variant)
        if comp_scores is None:
            continue

        base_avg = sum(base_scores) / len(base_scores)
        comp_avg = sum(comp_scores) / len(comp_scores)
        delta = comp_avg - base_avg

        if delta < -threshold:
            regressions.append({
                "variant": variant,
                "baseline_score": base_avg,
                "comparison_score": comp_avg,
                "delta": delta,
            })

    return regressions


def cost_trend(
    store: ObservatoryStore,
    run_ids: list[str],
) -> list[dict[str, Any]]:
    """Track cost trends across runs.

    Args:
        store: The observatory store.
        run_ids: Run IDs in chronological order.

    Returns:
        List of dicts with run_id, total_cost, avg_cost_per_trial.
    """
    results: list[dict[str, Any]] = []
    for run_id in run_ids:
        trials = store.get_trials(run_id)
        total = sum(t.cost or 0.0 for t in trials)
        avg = total / len(trials) if trials else 0.0
        results.append({
            "run_id": run_id,
            "total_cost": total,
            "avg_cost_per_trial": avg,
        })
    return results


def model_ranking(
    store: ObservatoryStore,
    run_ids: list[str],
) -> list[dict[str, Any]]:
    """Rank models by average score across all specified runs.

    Args:
        store: The observatory store.
        run_ids: Run IDs to include.

    Returns:
        List of dicts with model, avg_score, total_trials, avg_cost,
        sorted by avg_score descending.
    """
    all_trials = get_cross_run_trials(store, run_ids)

    by_model: dict[str, list[TrialRecord]] = {}
    for t in all_trials:
        by_model.setdefault(t.model, []).append(t)

    rankings: list[dict[str, Any]] = []
    for model_name, trials in by_model.items():
        n = len(trials)
        rankings.append({
            "model": model_name,
            "avg_score": sum(t.score for t in trials) / n,
            "total_trials": n,
            "avg_cost": sum(t.cost or 0.0 for t in trials) / n,
        })

    rankings.sort(key=lambda r: r["avg_score"], reverse=True)
    return rankings
