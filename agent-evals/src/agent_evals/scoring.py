"""Scoring module: composite scores, statistical tests, and bootstrap CIs.

Provides weighted composite score calculation, pairwise Wilcoxon signed-rank
tests with Holm-Bonferroni correction, and BCa bootstrap confidence intervals.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy import stats  # type: ignore[import-untyped]

# ---------------------------------------------------------------------------
# Default task-type weights (from DESIGN.md, empirically justified)
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS: dict[str, float] = {
    "retrieval": 0.15,
    "fact_extraction": 0.15,
    "code_generation": 0.15,
    "agentic": 0.12,
    "multi_hop": 0.10,
    "negative": 0.08,
    "compositional": 0.07,
    "robustness": 0.06,
    "disambiguation": 0.05,
    "conflicting": 0.04,
    "efficiency": 0.03,
}


def _redistribute_weight(
    base: dict[str, float],
    boost_keys: list[str],
    boost_amount: float,
    reduce_keys: list[str],
) -> dict[str, float]:
    """Create a new weight scheme by boosting some keys and reducing others.

    The total reduction is spread equally across reduce_keys so the scheme
    still sums to 1.0.
    """
    scheme = dict(base)
    total_boost = boost_amount * len(boost_keys)
    per_reduce = total_boost / len(reduce_keys)
    for k in boost_keys:
        scheme[k] = scheme[k] + boost_amount
    for k in reduce_keys:
        scheme[k] = scheme[k] - per_reduce
    return scheme


_edge_cases = ["negative", "disambiguation", "conflicting", "efficiency"]
_non_edge = [k for k in DEFAULT_WEIGHTS if k not in _edge_cases]

WEIGHT_SCHEMES: dict[str, dict[str, float]] = {
    "default": dict(DEFAULT_WEIGHTS),
    "retrieval_heavy": _redistribute_weight(
        DEFAULT_WEIGHTS,
        boost_keys=["retrieval", "fact_extraction"],
        boost_amount=0.05,
        reduce_keys=_edge_cases,
    ),
    "code_heavy": _redistribute_weight(
        DEFAULT_WEIGHTS,
        boost_keys=["code_generation", "compositional"],
        boost_amount=0.05,
        reduce_keys=_edge_cases,
    ),
    "agentic_heavy": (lambda: {
        # agentic at 0.20, others proportionally reduced
        k: (
            0.20 if k == "agentic"
            else DEFAULT_WEIGHTS[k] * (1.0 - 0.20) / (1.0 - DEFAULT_WEIGHTS["agentic"])
        )
        for k in DEFAULT_WEIGHTS
    })(),
    "uniform": {t: 1.0 / len(DEFAULT_WEIGHTS) for t in DEFAULT_WEIGHTS},
}


# ---------------------------------------------------------------------------
# Composite score
# ---------------------------------------------------------------------------


def composite_score(scores: dict[str, float], weights: dict[str, float]) -> float:
    """Calculate weighted composite: sum(weight_i * score_i) on 0-100 scale.

    Args:
        scores: Map of task_type -> mean score (0.0-1.0).
        weights: Map of task_type -> weight (should sum to 1.0).

    Returns:
        Composite score on a 0-100 scale.
    """
    total = sum(weights[k] * scores.get(k, 0.0) for k in weights)
    return total * 100.0


# ---------------------------------------------------------------------------
# Pairwise Wilcoxon signed-rank test
# ---------------------------------------------------------------------------


@dataclass
class PairwiseResult:
    """Result of a pairwise Wilcoxon signed-rank test."""

    variant_a: str
    variant_b: str
    statistic: float
    p_value: float
    corrected_p_value: float
    effect_size: float  # rank-biserial correlation
    significant: bool


def pairwise_wilcoxon(
    scores_a: list[float],
    scores_b: list[float],
    alpha: float = 0.05,
    variant_a: str = "",
    variant_b: str = "",
) -> PairwiseResult:
    """Wilcoxon signed-rank test with rank-biserial effect size.

    Args:
        scores_a: Paired scores for variant A.
        scores_b: Paired scores for variant B.
        alpha: Significance threshold.
        variant_a: Label for variant A.
        variant_b: Label for variant B.

    Returns:
        PairwiseResult with test statistic, p-value, effect size, and
        significance determination.
    """
    a = np.asarray(scores_a, dtype=np.float64)
    b = np.asarray(scores_b, dtype=np.float64)
    differences = a - b

    # If all differences are zero, the test is undefined
    if np.all(differences == 0):
        return PairwiseResult(
            variant_a=variant_a,
            variant_b=variant_b,
            statistic=0.0,
            p_value=1.0,
            corrected_p_value=1.0,
            effect_size=0.0,
            significant=False,
        )

    result = stats.wilcoxon(a, b, alternative="two-sided")
    statistic = float(result.statistic)
    p_value = float(result.pvalue)

    # Rank-biserial effect size: r = 1 - (2*W) / (n*(n+1)/2)
    # where W is the test statistic (smaller rank sum) and n is the
    # number of non-zero differences.
    non_zero = differences[differences != 0]
    n = len(non_zero)
    denominator = n * (n + 1) / 2.0
    # Guard against zero denominator (all pairs tied or no non-zero diffs)
    if denominator == 0.0:
        effect_size = 0.0
    else:
        effect_size = 1.0 - (2.0 * statistic) / denominator

    return PairwiseResult(
        variant_a=variant_a,
        variant_b=variant_b,
        statistic=statistic,
        p_value=p_value,
        corrected_p_value=p_value,  # uncorrected until holm_bonferroni
        effect_size=effect_size,
        significant=p_value < alpha,
    )


# ---------------------------------------------------------------------------
# Holm-Bonferroni correction
# ---------------------------------------------------------------------------


def holm_bonferroni(
    results: list[PairwiseResult],
    alpha: float = 0.05,
) -> list[PairwiseResult]:
    """Apply Holm-Bonferroni correction to multiple pairwise comparisons.

    Args:
        results: List of PairwiseResult from pairwise_wilcoxon.
        alpha: Family-wise significance threshold.

    Returns:
        New list of PairwiseResult with corrected_p_value and significance
        updated according to Holm-Bonferroni.
    """
    if not results:
        return []

    m = len(results)
    # Sort by raw p-value ascending; break ties by original index for
    # deterministic ordering when p-values are identical.
    indexed = sorted(enumerate(results), key=lambda x: (x[1].p_value, x[0]))

    corrected: list[tuple[int, PairwiseResult]] = []
    prev_corrected_p = 0.0
    for rank, (orig_idx, r) in enumerate(indexed):
        multiplier = m - rank  # Holm step-down: (m - rank) for 0-indexed rank
        corrected_p = min(r.p_value * multiplier, 1.0)
        # Enforce monotonicity: each corrected p must be >= previous
        corrected_p = max(corrected_p, prev_corrected_p)
        prev_corrected_p = corrected_p
        corrected.append((
            orig_idx,
            PairwiseResult(
                variant_a=r.variant_a,
                variant_b=r.variant_b,
                statistic=r.statistic,
                p_value=r.p_value,
                corrected_p_value=corrected_p,
                effect_size=r.effect_size,
                significant=corrected_p < alpha,
            ),
        ))

    # Restore original order
    corrected.sort(key=lambda x: x[0])
    return [r for _, r in corrected]


# ---------------------------------------------------------------------------
# Bootstrap confidence intervals (BCa method)
# ---------------------------------------------------------------------------


@dataclass
class BootstrapCI:
    """Result of a bootstrap confidence interval computation."""

    point_estimate: float
    ci_lower: float
    ci_upper: float
    n_resamples: int


_MIN_BOOTSTRAP_RESAMPLES = 100


def bootstrap_ci(
    data: list[float],
    statistic: Callable[[npt.NDArray[np.float64]], Any] = np.mean,
    n_resamples: int = 10000,
    confidence: float = 0.95,
) -> BootstrapCI:
    """Compute BCa bootstrap confidence interval.

    Args:
        data: Observed data points.
        statistic: Function to compute the statistic (default: np.mean).
        n_resamples: Number of bootstrap resamples.
        confidence: Confidence level (e.g. 0.95 for 95%).

    Returns:
        BootstrapCI with point estimate, CI bounds, and resample count.

    Raises:
        ValueError: If n_resamples < 100 (minimum for reliable bootstrap).
    """
    if n_resamples < _MIN_BOOTSTRAP_RESAMPLES:
        msg = (
            f"n_resamples={n_resamples} is below the minimum of "
            f"{_MIN_BOOTSTRAP_RESAMPLES} required for reliable bootstrap CIs"
        )
        raise ValueError(msg)

    arr = np.asarray(data, dtype=np.float64)
    point_est = float(statistic(arr))

    # Zero-variance data: all values are identical, so the CI is degenerate.
    # BCa bootstrap cannot compute acceleration for constant data (division
    # by zero in the jackknife), so we short-circuit here.
    if np.ptp(arr) == 0.0:
        return BootstrapCI(
            point_estimate=point_est,
            ci_lower=point_est,
            ci_upper=point_est,
            n_resamples=n_resamples,
        )

    stat_fn = statistic  # capture for lambda

    # scipy.stats.bootstrap expects a sequence of 1-D sample arrays and
    # a statistic that takes (*samples, axis) as arguments.
    result = stats.bootstrap(
        (arr,),
        statistic=lambda x, axis: np.apply_along_axis(
            lambda a: float(stat_fn(a)), axis, x,
        ),
        n_resamples=n_resamples,
        confidence_level=confidence,
        method="BCa",
        random_state=np.random.default_rng(42),
    )

    return BootstrapCI(
        point_estimate=point_est,
        ci_lower=float(result.confidence_interval.low),
        ci_upper=float(result.confidence_interval.high),
        n_resamples=n_resamples,
    )


# ---------------------------------------------------------------------------
# Weight sensitivity analysis
# ---------------------------------------------------------------------------


def weight_sensitivity_report(
    per_variant_type_scores: dict[str, dict[str, float]],
) -> dict[str, object]:
    """Check if variant rankings change under different weight schemes.

    Computes the composite score for every variant under each scheme in
    :data:`WEIGHT_SCHEMES` and flags cases where the top-ranked variant
    differs from the default ranking.

    Args:
        per_variant_type_scores:
            Mapping of variant_name -> {task_type -> mean_score (0-1)}.

    Returns:
        Dictionary with keys:
            ``rankings``:
                {scheme_name -> [(variant, composite), ...]} sorted desc.
            ``winner_per_scheme``:
                {scheme_name -> variant_name}.
            ``winner_stable``:
                ``True`` if the same variant wins in all schemes.
            ``schemes_where_winner_changes``:
                List of scheme names where the winner differs from default.
    """
    rankings: dict[str, list[tuple[str, float]]] = {}

    for scheme_name, weights in WEIGHT_SCHEMES.items():
        scored: list[tuple[str, float]] = []
        for variant_name, type_scores in per_variant_type_scores.items():
            comp = composite_score(type_scores, weights)
            scored.append((variant_name, comp))
        scored.sort(key=lambda x: x[1], reverse=True)
        rankings[scheme_name] = scored

    winner_per_scheme = {
        name: ranked[0][0] if ranked else ""
        for name, ranked in rankings.items()
    }

    default_winner = winner_per_scheme.get("default", "")
    changes = [
        name
        for name, winner in winner_per_scheme.items()
        if name != "default" and winner != default_winner
    ]

    return {
        "rankings": rankings,
        "winner_per_scheme": winner_per_scheme,
        "winner_stable": len(changes) == 0,
        "schemes_where_winner_changes": changes,
    }
