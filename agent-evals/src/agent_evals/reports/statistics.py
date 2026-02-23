"""Statistical analysis engine for evaluation reports.

Provides power analysis, assumption testing, effect sizes, post-hoc
comparisons, and multiple comparison corrections.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import sqrt

import numpy as np
from numpy import typing as npt
from scipy import stats


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class PowerResult:
    """Result of a power analysis computation."""

    power: float
    n_required: int
    effect_size: float
    alpha: float


@dataclass
class AssumptionsResult:
    """Result of assumption tests (normality + homogeneity)."""

    normality_stat: float
    normality_p: float
    homogeneity_stat: float
    homogeneity_p: float


@dataclass
class EffectSizeResult:
    """Pairwise effect size between two groups."""

    group1: str
    group2: str
    cohens_d: float
    rank_biserial_r: float | None
    interpretation: str


@dataclass
class TukeyResult:
    """Single pairwise comparison from Tukey HSD."""

    group1: str
    group2: str
    mean_diff: float
    p_value: float
    significant: bool


@dataclass
class BHResult:
    """Single result from Benjamini-Hochberg FDR correction."""

    original_p: float
    adjusted_p: float
    rank: int
    significant: bool


# ---------------------------------------------------------------------------
# Power analysis
# ---------------------------------------------------------------------------


def power_analysis(
    n_groups: int,
    n_obs_per_group: int,
    effect_size: float = 0.25,
    alpha: float = 0.05,
) -> PowerResult:
    """Compute statistical power for a one-way ANOVA design.

    Uses the non-central F distribution to compute power, then searches
    for the minimum sample size to achieve 80% power.

    Args:
        n_groups: Number of groups (factor levels).
        n_obs_per_group: Observations per group in the current design.
        effect_size: Cohen's f effect size (default 0.25 = medium).
        alpha: Significance level.

    Returns:
        PowerResult with computed power and required sample size.
    """
    power = _compute_power(n_groups, n_obs_per_group, effect_size, alpha)

    # Search for minimum n_per_group to reach 80% power
    n_req = n_obs_per_group
    if power < 0.80:
        for n in range(n_obs_per_group, 10001):
            if _compute_power(n_groups, n, effect_size, alpha) >= 0.80:
                n_req = n
                break
        else:
            n_req = 10000
    else:
        # Already above 80%, find minimum
        for n in range(2, n_obs_per_group + 1):
            if _compute_power(n_groups, n, effect_size, alpha) >= 0.80:
                n_req = n
                break

    return PowerResult(
        power=power,
        n_required=n_req,
        effect_size=effect_size,
        alpha=alpha,
    )


def _compute_power(
    n_groups: int,
    n_per_group: int,
    effect_size: float,
    alpha: float,
) -> float:
    """Compute power using non-central F distribution."""
    df1 = n_groups - 1
    df2 = n_groups * (n_per_group - 1)
    if df2 <= 0:
        return 0.0
    # Non-centrality parameter: lambda = n * k * f^2
    nc = n_per_group * n_groups * effect_size**2
    f_crit = stats.f.ppf(1 - alpha, df1, df2)
    return float(1 - stats.ncf.cdf(f_crit, df1, df2, nc))


# ---------------------------------------------------------------------------
# Assumptions testing
# ---------------------------------------------------------------------------


def check_assumptions(
    residuals: npt.NDArray,
    groups: list[npt.NDArray],
) -> AssumptionsResult:
    """Run Shapiro-Wilk normality and Levene's homogeneity tests.

    Args:
        residuals: Array of model residuals for normality test.
        groups: List of group arrays for homogeneity test (need >= 2).

    Returns:
        AssumptionsResult with test statistics and p-values.
    """
    shap_stat, shap_p = stats.shapiro(residuals)

    if len(groups) >= 2:
        lev_stat, lev_p = stats.levene(*groups)
    else:
        lev_stat, lev_p = 0.0, 1.0

    return AssumptionsResult(
        normality_stat=float(shap_stat),
        normality_p=float(shap_p),
        homogeneity_stat=float(lev_stat),
        homogeneity_p=float(lev_p),
    )


# Alias for backward compatibility
test_assumptions = check_assumptions


# ---------------------------------------------------------------------------
# Effect sizes
# ---------------------------------------------------------------------------


def cohens_d(a: npt.NDArray, b: npt.NDArray) -> float:
    """Compute Cohen's d for two groups.

    Uses pooled standard deviation.

    Args:
        a: First group array.
        b: Second group array.

    Returns:
        Cohen's d (positive when mean(a) > mean(b)).
    """
    na, nb = len(a), len(b)
    denom = na + nb - 2
    if denom <= 0:
        return 0.0
    var_a = float(np.var(a, ddof=1)) if na > 1 else 0.0
    var_b = float(np.var(b, ddof=1)) if nb > 1 else 0.0
    pooled_sd = sqrt(((na - 1) * var_a + (nb - 1) * var_b) / denom)
    mean_diff = float(np.mean(a) - np.mean(b))
    if pooled_sd == 0:
        return mean_diff  # Degenerate: constant groups
    return mean_diff / pooled_sd


def rank_biserial_r(a: npt.NDArray, b: npt.NDArray) -> float:
    """Compute rank-biserial r from Mann-Whitney U.

    Formula: r = 1 - (2U) / (n1 * n2)

    Args:
        a: First group array.
        b: Second group array.

    Returns:
        Rank-biserial r in range [-1, 1].
    """
    u_stat, _ = stats.mannwhitneyu(a, b, alternative="two-sided")
    n1, n2 = len(a), len(b)
    return float(1.0 - (2.0 * u_stat) / (n1 * n2))


def interpret_cohens_d(d: float) -> str:
    """Interpret absolute Cohen's d magnitude.

    Args:
        d: Cohen's d value (uses absolute value).

    Returns:
        One of "negligible", "small", "medium", "large".
    """
    return interpret_effect_size(d)


def interpret_effect_size(d: float) -> str:
    """Interpret absolute effect size magnitude.

    Args:
        d: Effect size value (uses absolute value).

    Returns:
        One of "negligible", "small", "medium", "large".
    """
    d = abs(d)
    if d < 0.1:
        return "negligible"
    if d < 0.5:
        return "small"
    if d < 0.8:
        return "medium"
    return "large"


def compute_effect_sizes(
    groups: dict[str, list[float]],
) -> list[EffectSizeResult]:
    """Compute pairwise effect sizes for all group combinations.

    Returns Cohen's d and rank-biserial r for each pair.

    Args:
        groups: Mapping of group name to score list.

    Returns:
        List of EffectSizeResult for each pair.
    """
    results: list[EffectSizeResult] = []
    names = sorted(groups.keys())
    for name_a, name_b in combinations(names, 2):
        a = np.array(groups[name_a], dtype=float)
        b = np.array(groups[name_b], dtype=float)
        d = abs(cohens_d(a, b))
        r: float | None = None
        if len(a) >= 2 and len(b) >= 2:
            try:
                r = rank_biserial_r(a, b)
            except ValueError:
                pass
        results.append(
            EffectSizeResult(
                group1=name_a,
                group2=name_b,
                cohens_d=d,
                rank_biserial_r=r,
                interpretation=interpret_effect_size(d),
            )
        )
    return results


# ---------------------------------------------------------------------------
# Omega-squared
# ---------------------------------------------------------------------------


def omega_squared(
    ss_factor: float,
    df_factor: int,
    ms_error: float,
    ss_total: float,
) -> float:
    """Compute omega-squared, a less-biased ANOVA effect size.

    Formula: w2 = (SS_f - df_f * MS_e) / (SS_total + MS_e)

    Args:
        ss_factor: Sum of squares for the factor.
        df_factor: Degrees of freedom for the factor.
        ms_error: Mean square error.
        ss_total: Total sum of squares.

    Returns:
        Omega-squared value (clamped to >= 0).
    """
    numerator = ss_factor - df_factor * ms_error
    denominator = ss_total + ms_error
    if denominator == 0:
        return 0.0
    return max(0.0, numerator / denominator)


# ---------------------------------------------------------------------------
# Tukey HSD
# ---------------------------------------------------------------------------


def tukey_hsd(
    groups: dict[str, list[float]],
    alpha: float = 0.05,
) -> list[TukeyResult]:
    """Run Tukey's HSD post-hoc test for all pairwise comparisons.

    Args:
        groups: Mapping of group name to score list.
        alpha: Significance level.

    Returns:
        List of TukeyResult for each pair (k choose 2).
    """
    names = sorted(groups.keys())
    arrays = [np.array(groups[n], dtype=float) for n in names]

    hsd = stats.tukey_hsd(*arrays)

    results: list[TukeyResult] = []
    for i, j in combinations(range(len(names)), 2):
        p_val = float(hsd.pvalue[i][j])
        mean_diff = float(np.mean(arrays[i]) - np.mean(arrays[j]))
        results.append(
            TukeyResult(
                group1=names[i],
                group2=names[j],
                mean_diff=mean_diff,
                p_value=p_val,
                significant=p_val < alpha,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Benjamini-Hochberg FDR
# ---------------------------------------------------------------------------


def benjamini_hochberg(
    p_values: list[float],
    alpha: float = 0.05,
) -> list[BHResult]:
    """Apply Benjamini-Hochberg FDR correction.

    Args:
        p_values: Original p-values to correct.
        alpha: FDR significance level.

    Returns:
        List of BHResult with adjusted p-values and significance.
    """
    m = len(p_values)
    if m == 0:
        return []

    # Sort by p-value
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])

    # Compute adjusted p-values (step-up)
    adjusted = [0.0] * m
    for rank_idx, (orig_idx, p) in enumerate(indexed):
        rank = rank_idx + 1
        adjusted_p = p * m / rank
        adjusted[orig_idx] = adjusted_p

    # Enforce monotonicity (from largest rank down)
    sorted_indices = [idx for idx, _ in indexed]
    for k in range(m - 2, -1, -1):
        idx_curr = sorted_indices[k]
        idx_next = sorted_indices[k + 1]
        adjusted[idx_curr] = min(adjusted[idx_curr], adjusted[idx_next])

    # Cap at 1.0
    adjusted = [min(p, 1.0) for p in adjusted]

    results: list[BHResult] = []
    for orig_idx, (_, orig_p) in enumerate(
        sorted(enumerate(p_values), key=lambda x: x[0])
    ):
        rank = next(
            r + 1
            for r, (i, _) in enumerate(indexed)
            if i == orig_idx
        )
        results.append(
            BHResult(
                original_p=orig_p,
                adjusted_p=adjusted[orig_idx],
                rank=rank,
                significant=adjusted[orig_idx] <= alpha,
            )
        )

    return results
