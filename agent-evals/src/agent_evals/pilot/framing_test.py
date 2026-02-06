"""Prompt framing comparison for pilot study.

Tests whether how we frame the system prompt matters for evaluation results.
Two strategies compared:

1. Constant framing: Same system prompt regardless of variant.
   Only the index content changes. This isolates the index effect.

2. Adapted framing: System prompt includes variant-specific guidance.
   E.g., "The index uses YAML format..." This tests whether explanation
   improves comprehension.

Design ref: DESIGN.md lines 682-687
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
    pairwise_wilcoxon,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Framing strategies
# ---------------------------------------------------------------------------

CONSTANT_SYSTEM_PROMPT = (
    "You are an AI coding assistant. Use the provided documentation index "
    "to answer the question. If the information is not available in the "
    "index, say so clearly."
)

ADAPTED_TEMPLATE = (
    "You are an AI coding assistant. The documentation index below uses "
    "{format_description}. Use it to answer the question. If the information "
    "is not available in the index, say so clearly."
)


def build_constant_prompt(question: str, index_content: str) -> list[dict[str, str]]:
    """Build prompt with constant framing (same system prompt for all)."""
    return [
        {"role": "system", "content": CONSTANT_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"## Documentation Index\n{index_content}\n\n"
                f"## Question\n{question}"
            ),
        },
    ]


def build_adapted_prompt(
    question: str,
    index_content: str,
    format_description: str,
) -> list[dict[str, str]]:
    """Build prompt with adapted framing (variant-specific guidance)."""
    system = ADAPTED_TEMPLATE.format(format_description=format_description)
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                f"## Documentation Index\n{index_content}\n\n"
                f"## Question\n{question}"
            ),
        },
    ]


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass
class FramingVariantResult:
    """Result for one variant under one framing strategy."""

    variant_name: str
    framing: str  # "constant" or "adapted"
    mean_score: float
    ci: BootstrapCI | None = None
    per_type_scores: dict[str, float] = field(default_factory=dict)
    composite: float = 0.0
    trial_count: int = 0


@dataclass
class FramingComparison:
    """Comparison of a single variant under both framings."""

    variant_name: str
    constant_result: FramingVariantResult
    adapted_result: FramingVariantResult
    score_difference: float  # adapted - constant
    pairwise_test: PairwiseResult | None = None
    better_framing: str = ""  # "constant", "adapted", or "no_difference"


@dataclass
class FramingReport:
    """Overall framing comparison report."""

    comparisons: list[FramingComparison]
    overall_better_framing: str  # "constant", "adapted", or "mixed"
    mean_difference: float  # mean(adapted - constant) across variants
    variants_favoring_constant: int = 0
    variants_favoring_adapted: int = 0
    variants_no_difference: int = 0


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def aggregate_trials(
    trials: list[TrialResult],
    framing: str,
    weights: dict[str, float] | None = None,
) -> dict[str, FramingVariantResult]:
    """Aggregate trial results into per-variant summaries.

    Groups trials by variant, computes per-type mean scores,
    and calculates composite score.
    """
    effective_weights = weights or DEFAULT_WEIGHTS

    # Group by variant
    variant_trials: dict[str, list[TrialResult]] = {}
    for trial in trials:
        variant_trials.setdefault(trial.variant_name, []).append(trial)

    results: dict[str, FramingVariantResult] = {}
    for variant_name, vtrials in variant_trials.items():
        # Per-type scores
        type_scores: dict[str, list[float]] = {}
        for t in vtrials:
            task_type = "_".join(t.task_id.split("_")[:-1])
            type_scores.setdefault(task_type, []).append(t.score)

        per_type_means = {
            tt: sum(scores) / len(scores)
            for tt, scores in type_scores.items()
        }

        comp = composite_score(per_type_means, effective_weights)

        all_scores = [t.score for t in vtrials]
        ci = bootstrap_ci(all_scores, n_resamples=1000) if len(all_scores) >= 3 else None

        results[variant_name] = FramingVariantResult(
            variant_name=variant_name,
            framing=framing,
            mean_score=sum(all_scores) / len(all_scores) if all_scores else 0.0,
            ci=ci,
            per_type_scores=per_type_means,
            composite=comp,
            trial_count=len(vtrials),
        )

    return results


def compare_framings(
    constant_trials: list[TrialResult],
    adapted_trials: list[TrialResult],
    weights: dict[str, float] | None = None,
    alpha: float = 0.05,
    min_effect_size: float = 0.1,
) -> FramingReport:
    """Compare constant vs adapted framing across all variants.

    For each variant present in both trial sets, computes the
    score difference and runs a Wilcoxon signed-rank test.
    """
    constant_results = aggregate_trials(constant_trials, "constant", weights)
    adapted_results = aggregate_trials(adapted_trials, "adapted", weights)

    # Find common variants
    common_variants = sorted(
        set(constant_results.keys()) & set(adapted_results.keys())
    )

    comparisons: list[FramingComparison] = []
    for variant_name in common_variants:
        cr = constant_results[variant_name]
        ar = adapted_results[variant_name]
        diff = ar.composite - cr.composite

        # Pairwise test
        constant_scores = [
            t.score for t in constant_trials if t.variant_name == variant_name
        ]
        adapted_scores = [
            t.score for t in adapted_trials if t.variant_name == variant_name
        ]
        min_len = min(len(constant_scores), len(adapted_scores))

        pw = None
        if min_len >= 5:
            pw = pairwise_wilcoxon(
                constant_scores[:min_len],
                adapted_scores[:min_len],
                alpha=alpha,
                variant_a=f"{variant_name}_constant",
                variant_b=f"{variant_name}_adapted",
            )

        # Determine better framing
        if pw and pw.significant and abs(diff) >= min_effect_size:
            better = "adapted" if diff > 0 else "constant"
        else:
            better = "no_difference"

        comparisons.append(FramingComparison(
            variant_name=variant_name,
            constant_result=cr,
            adapted_result=ar,
            score_difference=diff,
            pairwise_test=pw,
            better_framing=better,
        ))

    # Overall assessment
    favoring_constant = sum(1 for c in comparisons if c.better_framing == "constant")
    favoring_adapted = sum(1 for c in comparisons if c.better_framing == "adapted")
    no_diff = sum(1 for c in comparisons if c.better_framing == "no_difference")

    if favoring_adapted > favoring_constant:
        overall = "adapted"
    elif favoring_constant > favoring_adapted:
        overall = "constant"
    else:
        overall = "mixed"

    mean_diff = (
        sum(c.score_difference for c in comparisons) / len(comparisons)
        if comparisons
        else 0.0
    )

    return FramingReport(
        comparisons=comparisons,
        overall_better_framing=overall,
        mean_difference=mean_diff,
        variants_favoring_constant=favoring_constant,
        variants_favoring_adapted=favoring_adapted,
        variants_no_difference=no_diff,
    )


def format_framing_report(report: FramingReport) -> str:
    """Format framing comparison report as human-readable text."""
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("PROMPT FRAMING COMPARISON REPORT")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Overall better framing: {report.overall_better_framing}")
    lines.append(f"Mean score difference (adapted - constant): {report.mean_difference:+.2f}")
    lines.append(f"Variants favoring constant: {report.variants_favoring_constant}")
    lines.append(f"Variants favoring adapted: {report.variants_favoring_adapted}")
    lines.append(f"No significant difference: {report.variants_no_difference}")
    lines.append("")

    for comp in report.comparisons:
        lines.append(f"Variant: {comp.variant_name}")
        lines.append(f"  Constant composite: {comp.constant_result.composite:.2f}")
        lines.append(f"  Adapted composite:  {comp.adapted_result.composite:.2f}")
        lines.append(f"  Difference: {comp.score_difference:+.2f}")
        lines.append(f"  Better: {comp.better_framing}")
        if comp.pairwise_test:
            lines.append(f"  p-value: {comp.pairwise_test.p_value:.4f}")
            lines.append(f"  Significant: {comp.pairwise_test.significant}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)
