"""Saturation analysis for pilot study.

Determines whether the task corpus is large enough for stable evaluation
results. Incrementally adds tasks and monitors ranking stability.

Design ref: DESIGN.md lines 769-774
- Track cumulative composite score as tasks accumulate
- Plot learning curve: score stability vs task count
- If the last 10% of tasks changes no rankings, the eval is saturated
- Target: rankings stable within 1 point of composite score over last 20%
- Report saturation point per axis
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from agent_evals.runner import TrialResult
from agent_evals.scoring import (
    DEFAULT_WEIGHTS,
    BootstrapCI,
    bootstrap_ci,
    composite_score,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class LearningCurvePoint:
    """A single point on the learning curve."""

    task_count: int
    variant_name: str
    composite_score: float
    ci: BootstrapCI | None = None
    ranking: int = 0  # 1-based ranking at this point


@dataclass
class SaturationResult:
    """Result of saturation analysis for one variant."""

    variant_name: str
    saturation_point: int | None  # Task count where scores stabilized (None if not reached)
    is_saturated: bool
    final_score: float
    score_range_last_20pct: float  # Range of scores in last 20% of curve
    learning_curve: list[LearningCurvePoint] = field(default_factory=list)


@dataclass
class RankingStabilityPoint:
    """Rankings of all variants at a given task count."""

    task_count: int
    rankings: dict[str, int]  # variant_name -> ranking (1-based)
    ranking_changed: bool  # True if rankings changed from previous point


@dataclass
class SaturationReport:
    """Overall saturation analysis report."""

    variant_results: list[SaturationResult]
    ranking_history: list[RankingStabilityPoint]
    overall_saturated: bool
    saturation_point: int | None  # Task count where ALL variants stabilized
    sufficient_tasks: bool  # True if corpus is large enough
    stability_threshold: float
    total_tasks_analyzed: int


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------


def compute_learning_curve(
    trials: list[TrialResult],
    variant_name: str,
    step_size: int = 10,
    min_tasks: int = 20,
    weights: dict[str, float] | None = None,
    n_bootstrap: int = 1000,
) -> list[LearningCurvePoint]:
    """Compute learning curve for a single variant.

    Incrementally includes more tasks and computes the composite
    score at each step. Returns a list of (task_count, score) points.
    """
    effective_weights = weights or DEFAULT_WEIGHTS

    # Filter trials for this variant
    variant_trials = [t for t in trials if t.variant_name == variant_name]
    if not variant_trials:
        return []

    # Get unique task IDs in order
    seen: set[str] = set()
    task_order: list[str] = []
    for t in variant_trials:
        if t.task_id not in seen:
            seen.add(t.task_id)
            task_order.append(t.task_id)

    # Group trials by task_id
    task_trials: dict[str, list[TrialResult]] = {}
    for t in variant_trials:
        task_trials.setdefault(t.task_id, []).append(t)

    curve: list[LearningCurvePoint] = []

    for n in range(min_tasks, len(task_order) + 1, step_size):
        included_tasks = task_order[:n]

        # Compute per-type mean scores using included tasks only
        type_scores: dict[str, list[float]] = {}
        for tid in included_tasks:
            for t in task_trials.get(tid, []):
                type_scores.setdefault(t.task_type, []).append(t.score)

        per_type_means = {
            tt: sum(scores) / len(scores)
            for tt, scores in type_scores.items()
        }

        comp = composite_score(per_type_means, effective_weights)

        # Bootstrap CI on all included scores
        all_scores = []
        for tid in included_tasks:
            all_scores.extend(t.score for t in task_trials.get(tid, []))

        ci = bootstrap_ci(all_scores, n_resamples=n_bootstrap) if len(all_scores) >= 3 else None

        curve.append(LearningCurvePoint(
            task_count=n,
            variant_name=variant_name,
            composite_score=comp,
            ci=ci,
        ))

    # Add final point if not already included
    if task_order and (not curve or curve[-1].task_count != len(task_order)):
        included_tasks = task_order
        type_scores_final: dict[str, list[float]] = {}
        for tid in included_tasks:
            for t in task_trials.get(tid, []):
                type_scores_final.setdefault(t.task_type, []).append(t.score)

        per_type_means_final = {
            tt: sum(scores) / len(scores)
            for tt, scores in type_scores_final.items()
        }
        comp_final = composite_score(per_type_means_final, effective_weights)
        all_final = [t.score for tid in included_tasks for t in task_trials.get(tid, [])]
        ci_final = bootstrap_ci(all_final, n_resamples=n_bootstrap) if len(all_final) >= 3 else None

        curve.append(LearningCurvePoint(
            task_count=len(task_order),
            variant_name=variant_name,
            composite_score=comp_final,
            ci=ci_final,
        ))

    return curve


def find_saturation_point(
    curve: list[LearningCurvePoint],
    stability_threshold: float = 1.0,
    tail_fraction: float = 0.20,
) -> tuple[int | None, bool, float]:
    """Find the saturation point in a learning curve.

    Saturation is reached when the score variation in the tail
    (last tail_fraction of points) is within stability_threshold.

    Returns:
        (saturation_point, is_saturated, score_range_in_tail)
    """
    if len(curve) < 3:
        return None, False, float("inf")

    # Check the tail
    tail_start = max(1, int(len(curve) * (1 - tail_fraction)))
    tail_scores = [p.composite_score for p in curve[tail_start:]]

    if not tail_scores:
        return None, False, float("inf")

    score_range = max(tail_scores) - min(tail_scores)
    is_saturated = score_range <= stability_threshold

    # Find first point where remaining curve is stable
    saturation_point = None
    if is_saturated:
        for i in range(len(curve)):
            remaining = [p.composite_score for p in curve[i:]]
            if max(remaining) - min(remaining) <= stability_threshold:
                saturation_point = curve[i].task_count
                break

    return saturation_point, is_saturated, score_range


def compute_ranking_stability(
    all_curves: dict[str, list[LearningCurvePoint]],
) -> list[RankingStabilityPoint]:
    """Track how variant rankings change as tasks accumulate.

    At each task count step, ranks all variants by their composite
    score and records whether rankings changed from the previous step.
    """
    # Collect all unique task counts across all variants
    all_counts: set[int] = set()
    for curve in all_curves.values():
        for point in curve:
            all_counts.add(point.task_count)

    sorted_counts = sorted(all_counts)
    if not sorted_counts:
        return []

    # Build lookup: variant -> {task_count -> score}
    score_lookup: dict[str, dict[int, float]] = {}
    for variant_name, curve in all_curves.items():
        score_lookup[variant_name] = {p.task_count: p.composite_score for p in curve}

    history: list[RankingStabilityPoint] = []
    prev_rankings: dict[str, int] | None = None

    for count in sorted_counts:
        # Get scores at this count (use most recent available if exact not found)
        current_scores: dict[str, float] = {}
        for variant_name, lookup in score_lookup.items():
            # Find closest count <= current count
            available = [c for c in lookup if c <= count]
            if available:
                current_scores[variant_name] = lookup[max(available)]

        if not current_scores:
            continue

        # Rank by score (descending)
        sorted_variants = sorted(
            current_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        rankings = {name: rank + 1 for rank, (name, _) in enumerate(sorted_variants)}

        changed = prev_rankings is not None and rankings != prev_rankings

        history.append(RankingStabilityPoint(
            task_count=count,
            rankings=rankings,
            ranking_changed=changed,
        ))

        prev_rankings = rankings

    return history


def analyze_saturation(
    trials: list[TrialResult],
    step_size: int = 10,
    min_tasks: int = 20,
    stability_threshold: float = 1.0,
    tail_fraction: float = 0.20,
    weights: dict[str, float] | None = None,
    n_bootstrap: int = 1000,
) -> SaturationReport:
    """Run full saturation analysis on trial results.

    Computes learning curves for all variants, finds saturation
    points, and checks ranking stability.
    """
    # Get unique variant names
    variant_names = sorted({t.variant_name for t in trials})

    # Compute learning curves
    all_curves: dict[str, list[LearningCurvePoint]] = {}
    variant_results: list[SaturationResult] = []

    for variant_name in variant_names:
        curve = compute_learning_curve(
            trials, variant_name,
            step_size=step_size,
            min_tasks=min_tasks,
            weights=weights,
            n_bootstrap=n_bootstrap,
        )
        all_curves[variant_name] = curve

        sat_point, is_sat, score_range = find_saturation_point(
            curve,
            stability_threshold=stability_threshold,
            tail_fraction=tail_fraction,
        )

        final_score = curve[-1].composite_score if curve else 0.0

        variant_results.append(SaturationResult(
            variant_name=variant_name,
            saturation_point=sat_point,
            is_saturated=is_sat,
            final_score=final_score,
            score_range_last_20pct=score_range,
            learning_curve=curve,
        ))

    # Ranking stability
    ranking_history = compute_ranking_stability(all_curves)

    # Overall saturation: all variants must be saturated
    overall_saturated = all(vr.is_saturated for vr in variant_results) if variant_results else False

    # Overall saturation point: max of individual saturation points
    sat_points = [
        vr.saturation_point for vr in variant_results
        if vr.saturation_point is not None
    ]
    overall_sat_point = max(sat_points) if sat_points else None

    # Check if rankings are stable in the tail
    if ranking_history:
        tail_start = max(0, int(len(ranking_history) * (1 - tail_fraction)))
        tail_changes = sum(1 for rsp in ranking_history[tail_start:] if rsp.ranking_changed)
        sufficient = overall_saturated and tail_changes == 0
    else:
        sufficient = False

    total_tasks = max(
        (p.task_count for vr in variant_results for p in vr.learning_curve),
        default=0,
    )

    return SaturationReport(
        variant_results=variant_results,
        ranking_history=ranking_history,
        overall_saturated=overall_saturated,
        saturation_point=overall_sat_point,
        sufficient_tasks=sufficient,
        stability_threshold=stability_threshold,
        total_tasks_analyzed=total_tasks,
    )


def format_saturation_report(report: SaturationReport) -> str:
    """Format saturation report as human-readable text."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("SATURATION ANALYSIS REPORT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Total tasks analyzed: {report.total_tasks_analyzed}")
    lines.append(f"Stability threshold: {report.stability_threshold} composite points")
    lines.append(f"Overall saturated: {report.overall_saturated}")
    lines.append(f"Saturation point: {report.saturation_point}")
    lines.append(f"Sufficient tasks: {report.sufficient_tasks}")
    lines.append("")

    lines.append("Per-variant results:")
    for vr in report.variant_results:
        status = "SATURATED" if vr.is_saturated else "NOT SATURATED"
        lines.append(f"  {vr.variant_name}: [{status}]")
        lines.append(f"    Final score: {vr.final_score:.2f}")
        lines.append(f"    Saturation point: {vr.saturation_point}")
        lines.append(f"    Score range (last 20%): {vr.score_range_last_20pct:.2f}")
        lines.append(f"    Curve points: {len(vr.learning_curve)}")
        lines.append("")

    # Ranking stability summary
    if report.ranking_history:
        changes = sum(1 for rsp in report.ranking_history if rsp.ranking_changed)
        lines.append(f"Ranking changes: {changes} across {len(report.ranking_history)} checkpoints")
        if report.ranking_history:
            final_rankings = report.ranking_history[-1].rankings
            lines.append("Final rankings:")
            for name, rank in sorted(final_rankings.items(), key=lambda x: x[1]):
                lines.append(f"  #{rank}: {name}")
    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)
