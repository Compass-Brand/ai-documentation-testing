"""Axis ordering sensitivity test for pilot study.

Tests whether the order in which evaluation axes are processed
affects the final winning variants. Uses beam search cascade with
different axis orderings and compares outcomes.

Design ref: DESIGN.md lines 509-513
- Before full eval, run lightweight pilot: 10 tasks, N=3 repetitions
- Test two alternative orderings for sensitivity
- If orderings produce different winners, expand interaction validation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from agent_evals.runner import EvalRunner, TrialResult
from agent_evals.scoring import (
    DEFAULT_WEIGHTS,
    BootstrapCI,
    PairwiseResult,
    bootstrap_ci,
    composite_score,
    holm_bonferroni,
    pairwise_wilcoxon,
)
from agent_evals.variants.registry import get_variants_for_axis

logger = logging.getLogger(__name__)


@dataclass
class BeamCandidate:
    """A variant retained in the beam search."""
    variant_name: str
    axis: int
    mean_score: float
    ci: BootstrapCI | None = None


@dataclass
class AxisResult:
    """Result of evaluating one axis in the cascade."""
    axis: int
    candidates_tested: list[str]
    beam_retained: list[str]  # top 2-3 names
    scores: dict[str, float]  # variant_name -> mean composite score
    pairwise_tests: list[PairwiseResult] = field(default_factory=list)


@dataclass
class OrderingResult:
    """Result of running one complete axis ordering."""
    ordering_name: str
    axis_order: list[int]
    axis_results: list[AxisResult]
    final_winners: list[str]  # Final beam candidates after all axes
    total_cost: float = 0.0


@dataclass
class SensitivityReport:
    """Comparison of multiple axis orderings."""
    ordering_results: list[OrderingResult]
    winners_differ: bool  # True if different orderings produce different winners
    differing_axes: list[int]  # Axes where beam selection differed
    recommendation: str  # "proceed" or "expand_interaction_validation"


def select_beam(
    trial_results: list[TrialResult],
    beam_width: int = 3,
    weights: dict[str, float] | None = None,
) -> list[BeamCandidate]:
    """Select top beam_width candidates from trial results.

    Groups trials by variant, computes mean score per task type,
    then computes weighted composite score to rank variants.
    Returns top beam_width candidates.
    """
    effective_weights = weights or DEFAULT_WEIGHTS

    # Group trials by variant
    variant_trials: dict[str, list[TrialResult]] = {}
    for trial in trial_results:
        variant_trials.setdefault(trial.variant_name, []).append(trial)

    candidates: list[BeamCandidate] = []
    for variant_name, trials in variant_trials.items():
        # Group by task type
        type_scores: dict[str, list[float]] = {}
        for t in trials:
            task_type = t.task_type
            type_scores.setdefault(task_type, []).append(t.score)

        # Mean score per type
        mean_type_scores = {
            tt: sum(scores) / len(scores)
            for tt, scores in type_scores.items()
            if scores
        }

        # Composite score
        comp = composite_score(mean_type_scores, effective_weights)

        # Bootstrap CI on all scores
        all_scores = [t.score for t in trials]
        ci = bootstrap_ci(all_scores, n_resamples=1000) if len(all_scores) >= 3 else None

        candidates.append(BeamCandidate(
            variant_name=variant_name,
            axis=trials[0].repetition,  # Will be overridden
            mean_score=comp,
            ci=ci,
        ))

    # Sort by composite score descending, take top beam_width
    candidates.sort(key=lambda c: c.mean_score, reverse=True)
    return candidates[:beam_width]


def run_axis_ordering(
    runner: EvalRunner,
    tasks: list,  # list[EvalTask]
    doc_tree: Any,  # DocTree
    axis_order: list[int],
    ordering_name: str,
    beam_width: int = 3,
    weights: dict[str, float] | None = None,
) -> OrderingResult:
    """Run beam search cascade with a specific axis ordering.

    For each axis in order:
    1. Get variants for that axis
    2. Combine with current beam (carry-forward variants)
    3. Run evaluation
    4. Select top beam_width as new beam

    Returns the full ordering result with per-axis breakdowns.
    """
    effective_weights = weights or DEFAULT_WEIGHTS
    current_beam: list[str] = []  # variant names retained so far
    axis_results: list[AxisResult] = []
    total_cost = 0.0

    for axis in axis_order:
        axis_variants = get_variants_for_axis(axis)
        if not axis_variants:
            logger.warning("No variants registered for axis %d, skipping", axis)
            continue

        # Combine axis variants with carried-forward beam variants
        # In pilot, we test axis variants directly
        candidates_tested = [v.metadata().name for v in axis_variants]

        # Run evaluation for this axis
        result = runner.run(
            tasks=tasks,
            variants=axis_variants,
            doc_tree=doc_tree,
        )
        total_cost += result.total_cost

        # Select beam
        beam_candidates = select_beam(
            result.trials,
            beam_width=beam_width,
            weights=effective_weights,
        )

        beam_retained = [c.variant_name for c in beam_candidates]
        scores = {c.variant_name: c.mean_score for c in beam_candidates}

        # Pairwise statistical tests between beam candidates
        pairwise_tests: list[PairwiseResult] = []
        variant_scores: dict[str, list[float]] = {}
        for trial in result.trials:
            variant_scores.setdefault(trial.variant_name, []).append(trial.score)

        tested_variants = list(variant_scores.keys())
        for i in range(len(tested_variants)):
            for j in range(i + 1, len(tested_variants)):
                va, vb = tested_variants[i], tested_variants[j]
                sa, sb = variant_scores[va], variant_scores[vb]
                min_len = min(len(sa), len(sb))
                if min_len >= 5:
                    pw = pairwise_wilcoxon(
                        sa[:min_len], sb[:min_len],
                        variant_a=va, variant_b=vb,
                    )
                    pairwise_tests.append(pw)

        if pairwise_tests:
            pairwise_tests = holm_bonferroni(pairwise_tests)

        axis_results.append(AxisResult(
            axis=axis,
            candidates_tested=candidates_tested,
            beam_retained=beam_retained,
            scores=scores,
            pairwise_tests=pairwise_tests,
        ))

        current_beam = beam_retained
        logger.info(
            "Axis %d: tested %d variants, retained %s",
            axis, len(candidates_tested), beam_retained,
        )

    return OrderingResult(
        ordering_name=ordering_name,
        axis_order=axis_order,
        axis_results=axis_results,
        final_winners=current_beam,
        total_cost=total_cost,
    )


def compare_orderings(
    ordering_results: list[OrderingResult],
) -> SensitivityReport:
    """Compare results from different axis orderings.

    Checks whether the final winners differ between orderings.
    If they do, recommends expanding interaction validation.
    """
    if len(ordering_results) < 2:
        return SensitivityReport(
            ordering_results=ordering_results,
            winners_differ=False,
            differing_axes=[],
            recommendation="proceed",
        )

    # Compare final winners
    reference_winners = set(ordering_results[0].final_winners)
    winners_differ = False

    for result in ordering_results[1:]:
        if set(result.final_winners) != reference_winners:
            winners_differ = True
            break

    # Find axes where beam selection differed
    differing_axes: list[int] = []
    for axis_idx in range(min(len(r.axis_results) for r in ordering_results)):
        beams = [
            set(r.axis_results[axis_idx].beam_retained)
            for r in ordering_results
            if axis_idx < len(r.axis_results)
        ]
        if len(beams) >= 2 and any(b != beams[0] for b in beams[1:]):
            differing_axes.append(ordering_results[0].axis_results[axis_idx].axis)

    recommendation = (
        "expand_interaction_validation" if winners_differ else "proceed"
    )

    return SensitivityReport(
        ordering_results=ordering_results,
        winners_differ=winners_differ,
        differing_axes=differing_axes,
        recommendation=recommendation,
    )


def format_sensitivity_report(report: SensitivityReport) -> str:
    """Format sensitivity report as human-readable text."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("AXIS ORDERING SENSITIVITY REPORT")
    lines.append("=" * 60)
    lines.append("")

    for result in report.ordering_results:
        lines.append(f"Ordering: {result.ordering_name}")
        lines.append(f"  Axis order: {result.axis_order}")
        lines.append(f"  Final winners: {result.final_winners}")
        lines.append(f"  Total cost: ${result.total_cost:.4f}")
        lines.append("")

        for ar in result.axis_results:
            lines.append(f"  Axis {ar.axis}:")
            lines.append(f"    Tested: {len(ar.candidates_tested)} variants")
            lines.append(f"    Retained: {ar.beam_retained}")
            for name, score in sorted(ar.scores.items(), key=lambda x: -x[1]):
                lines.append(f"      {name}: {score:.2f}")
            lines.append("")

    lines.append("-" * 60)
    lines.append(f"Winners differ: {report.winners_differ}")
    if report.differing_axes:
        lines.append(f"Differing axes: {report.differing_axes}")
    lines.append(f"Recommendation: {report.recommendation}")
    lines.append("=" * 60)

    return "\n".join(lines)
