"""Beam search cascade for multi-axis evaluation.

Evaluates index variants across axes sequentially, retaining top
candidates at each stage. Uses statistical parity (Wilcoxon p > 0.10)
to avoid premature elimination.

Design ref: DESIGN.md beam search cascade
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from agent_evals.runner import TrialResult
from agent_evals.scoring import (
    DEFAULT_WEIGHTS,
    BootstrapCI,
    PairwiseResult,
    bootstrap_ci,
    composite_score,
    holm_bonferroni,
    pairwise_wilcoxon,
)

logger = logging.getLogger(__name__)


@dataclass
class BeamCandidate:
    """A variant retained in the beam."""

    variant_name: str
    composite_score: float
    ci: BootstrapCI | None = None
    per_type_scores: dict[str, float] = field(default_factory=dict)
    trial_count: int = 0
    within_parity: bool = True  # True if within statistical parity of best


@dataclass
class BeamAxisResult:
    """Result of beam selection at one axis."""

    axis: int
    candidates_evaluated: list[BeamCandidate]
    beam_retained: list[BeamCandidate]  # Top candidates that survived
    pairwise_tests: list[PairwiseResult] = field(default_factory=list)
    parity_threshold: float = 0.10


@dataclass
class BeamSearchResult:
    """Full result of beam search cascade across all axes."""

    axis_results: list[BeamAxisResult]
    final_beam: list[BeamCandidate]
    axis_order: list[int]
    beam_width: int
    parity_alpha: float


def score_variants(
    trials: list[TrialResult],
    weights: dict[str, float] | None = None,
    n_bootstrap: int = 1000,
) -> list[BeamCandidate]:
    """Score all variants from a set of trial results.

    Groups trials by variant, computes per-type mean scores,
    then composite score. Returns candidates sorted by score descending.
    """
    effective_weights = weights or DEFAULT_WEIGHTS

    # Group trials by variant
    variant_trials: dict[str, list[TrialResult]] = {}
    for trial in trials:
        variant_trials.setdefault(trial.variant_name, []).append(trial)

    candidates: list[BeamCandidate] = []
    for variant_name, vtrials in sorted(variant_trials.items()):
        # Per-type mean scores
        type_scores: dict[str, list[float]] = {}
        for t in vtrials:
            task_type = t.task_type
            type_scores.setdefault(task_type, []).append(t.score)

        per_type_means = {
            tt: sum(scores) / len(scores) for tt, scores in type_scores.items()
        }

        comp = composite_score(per_type_means, effective_weights)

        all_scores = [t.score for t in vtrials]
        ci = (
            bootstrap_ci(all_scores, n_resamples=n_bootstrap)
            if len(all_scores) >= 3
            else None
        )

        candidates.append(
            BeamCandidate(
                variant_name=variant_name,
                composite_score=comp,
                ci=ci,
                per_type_scores=per_type_means,
                trial_count=len(vtrials),
            )
        )

    candidates.sort(key=lambda c: c.composite_score, reverse=True)
    return candidates


def select_beam(
    candidates: list[BeamCandidate],
    trials: list[TrialResult],
    beam_width: int = 3,
    parity_alpha: float = 0.10,
) -> BeamAxisResult:
    """Select top candidates with statistical parity consideration.

    Always retains the top candidate. Additional candidates are retained if:
    1. They are within the beam_width limit, AND
    2. They are NOT statistically significantly worse than the best
       (Wilcoxon p > parity_alpha means we can't distinguish them)

    This prevents premature elimination of good candidates.
    """
    if not candidates:
        return BeamAxisResult(
            axis=0,
            candidates_evaluated=[],
            beam_retained=[],
            parity_threshold=parity_alpha,
        )

    # Get trial scores per variant for pairwise testing
    variant_scores: dict[str, list[float]] = {}
    for trial in trials:
        variant_scores.setdefault(trial.variant_name, []).append(trial.score)

    best = candidates[0]
    best_scores = variant_scores.get(best.variant_name, [])

    retained = [best]
    pairwise_tests: list[PairwiseResult] = []

    for candidate in candidates[1 : beam_width * 2]:  # Consider up to 2x beam width
        if len(retained) >= beam_width:
            # Check if this candidate is within statistical parity
            cand_scores = variant_scores.get(candidate.variant_name, [])
            min_len = min(len(best_scores), len(cand_scores))
            if min_len >= 5:
                pw = pairwise_wilcoxon(
                    best_scores[:min_len],
                    cand_scores[:min_len],
                    alpha=parity_alpha,
                    variant_a=best.variant_name,
                    variant_b=candidate.variant_name,
                )
                pairwise_tests.append(pw)
                if not pw.significant:
                    # Can't distinguish from best -- retain
                    candidate.within_parity = True
                    retained.append(candidate)
                else:
                    candidate.within_parity = False
            else:
                # Not enough data to test -- retain conservatively
                retained.append(candidate)
        else:
            # Within beam width -- always retain
            cand_scores = variant_scores.get(candidate.variant_name, [])
            min_len = min(len(best_scores), len(cand_scores))
            if min_len >= 5:
                pw = pairwise_wilcoxon(
                    best_scores[:min_len],
                    cand_scores[:min_len],
                    alpha=parity_alpha,
                    variant_a=best.variant_name,
                    variant_b=candidate.variant_name,
                )
                pairwise_tests.append(pw)
                candidate.within_parity = not pw.significant
            retained.append(candidate)

    if pairwise_tests:
        pairwise_tests = holm_bonferroni(pairwise_tests)

    return BeamAxisResult(
        axis=0,  # Set by caller
        candidates_evaluated=candidates,
        beam_retained=retained,
        pairwise_tests=pairwise_tests,
        parity_threshold=parity_alpha,
    )


def run_beam_cascade(
    all_trials: dict[int, list[TrialResult]],  # axis -> trials
    axis_order: list[int],
    beam_width: int = 3,
    parity_alpha: float = 0.10,
    weights: dict[str, float] | None = None,
    n_bootstrap: int = 1000,
) -> BeamSearchResult:
    """Run beam search cascade across multiple axes.

    Parameters
    ----------
    all_trials:
        Mapping from axis number to list of trial results for that axis.
    axis_order:
        Order in which to process axes.
    beam_width:
        Number of candidates to retain per axis.
    parity_alpha:
        Significance level for statistical parity test.
    weights:
        Task type weights for composite scoring.
    n_bootstrap:
        Number of bootstrap resamples for CIs.

    Returns
    -------
    BeamSearchResult
        Complete beam search results with per-axis breakdowns.
    """
    axis_results: list[BeamAxisResult] = []

    for axis in axis_order:
        trials = all_trials.get(axis, [])
        if not trials:
            logger.warning("No trials for axis %d, skipping", axis)
            continue

        # Score all candidates for this axis
        candidates = score_variants(trials, weights=weights, n_bootstrap=n_bootstrap)

        if not candidates:
            continue

        # Select beam
        beam_result = select_beam(
            candidates,
            trials,
            beam_width=beam_width,
            parity_alpha=parity_alpha,
        )
        beam_result.axis = axis

        axis_results.append(beam_result)

        retained_names = [c.variant_name for c in beam_result.beam_retained]
        logger.info(
            "Axis %d: %d candidates -> beam %s",
            axis,
            len(candidates),
            retained_names,
        )

    final_beam = axis_results[-1].beam_retained if axis_results else []

    return BeamSearchResult(
        axis_results=axis_results,
        final_beam=final_beam,
        axis_order=axis_order,
        beam_width=beam_width,
        parity_alpha=parity_alpha,
    )


def format_beam_report(result: BeamSearchResult) -> str:
    """Format beam search results as human-readable text."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("BEAM SEARCH CASCADE REPORT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Axis order: {result.axis_order}")
    lines.append(f"Beam width: {result.beam_width}")
    lines.append(f"Parity alpha: {result.parity_alpha}")
    lines.append("")

    for ar in result.axis_results:
        lines.append(f"--- Axis {ar.axis} ---")
        lines.append(f"Candidates evaluated: {len(ar.candidates_evaluated)}")
        lines.append(f"Beam retained: {len(ar.beam_retained)}")
        lines.append("")

        for c in ar.beam_retained:
            parity_marker = " (within parity)" if c.within_parity else ""
            ci_str = ""
            if c.ci:
                ci_str = f" CI[{c.ci.ci_lower:.1f}, {c.ci.ci_upper:.1f}]"
            lines.append(
                f"  {c.variant_name}: {c.composite_score:.2f}"
                f"{ci_str}{parity_marker}"
            )
        lines.append("")

    lines.append("--- Final Beam ---")
    for c in result.final_beam:
        lines.append(f"  {c.variant_name}: {c.composite_score:.2f}")

    lines.append("=" * 60)
    return "\n".join(lines)
