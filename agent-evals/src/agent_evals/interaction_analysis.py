"""Interaction effect analysis: Lenth method, half-normal plots, override detection.

Identifies significant main effects and interactions from factorial experiment
designs. Uses the Lenth method for unreplicated factorials and provides
half-normal plot data for visual diagnostics. Supports override detection
when a factorial combination outperforms the sequential beam-search winner.

Design ref: DESIGN.md Story 7.2 — Interaction Effect Analysis
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats as sp_stats  # type: ignore[import-untyped]

from agent_evals.scoring import pairwise_wilcoxon

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class EffectEstimate:
    """A single estimated effect from a factorial design."""

    name: str
    estimate: float
    is_main_effect: bool
    significant: bool = False


@dataclass
class LenthResult:
    """Result of the Lenth method for effect significance testing."""

    effects: list[EffectEstimate]
    pse: float  # Pseudo standard error
    me: float  # Margin of error
    sme: float  # Simultaneous margin of error
    alpha: float


@dataclass
class HalfNormalPoint:
    """A single point for a half-normal probability plot."""

    label: str
    absolute_effect: float
    expected_quantile: float


@dataclass
class InteractionResult:
    """Full result of interaction effect analysis with override detection."""

    lenth: LenthResult
    half_normal_points: list[HalfNormalPoint]
    override_detected: bool
    override_combination: dict[str, str] | None
    override_p_value: float | None
    sequential_winner_score: float
    best_factorial_score: float


# ---------------------------------------------------------------------------
# Effect computation
# ---------------------------------------------------------------------------


def compute_effects(
    response_values: list[float],
    design_matrix: list[list[int]],
    factor_names: list[str],
) -> list[EffectEstimate]:
    """Compute main effects and two-way interaction effects from a factorial design.

    Parameters
    ----------
    response_values:
        Observed response for each run (length n).
    design_matrix:
        n x k matrix of coded factor levels (-1 / +1) for each run.
    factor_names:
        Names for the k factors.

    Returns
    -------
    list[EffectEstimate]
        All main effects and two-way interactions, sorted by absolute
        effect size descending.
    """
    y = np.asarray(response_values, dtype=np.float64)
    X = np.asarray(design_matrix, dtype=np.float64)
    n = len(y)
    k = len(factor_names)

    if X.shape != (n, k):
        msg = (
            f"Design matrix shape {X.shape} does not match "
            f"n={n} runs x k={k} factors"
        )
        raise ValueError(msg)

    effects: list[EffectEstimate] = []

    # Main effects: effect_j = (2/n) * sum(x_ij * y_i)
    for j in range(k):
        estimate = float((2.0 / n) * np.dot(X[:, j], y))
        effects.append(
            EffectEstimate(
                name=factor_names[j],
                estimate=estimate,
                is_main_effect=True,
            )
        )

    # Two-way interaction effects: effect_jk = (2/n) * sum(x_ij * x_ik * y_i)
    for j in range(k):
        for m in range(j + 1, k):
            interaction_col = X[:, j] * X[:, m]
            estimate = float((2.0 / n) * np.dot(interaction_col, y))
            effects.append(
                EffectEstimate(
                    name=f"{factor_names[j]}:{factor_names[m]}",
                    estimate=estimate,
                    is_main_effect=False,
                )
            )

    # Sort by absolute effect descending
    effects.sort(key=lambda e: abs(e.estimate), reverse=True)
    return effects


# ---------------------------------------------------------------------------
# Lenth method
# ---------------------------------------------------------------------------


def lenth_method(
    effects: list[EffectEstimate],
    alpha: float = 0.05,
) -> LenthResult:
    """Apply the Lenth method to identify significant effects.

    The Lenth method is designed for unreplicated factorial designs where
    there is no independent estimate of error variance. It uses a pseudo
    standard error derived from the median absolute effect.

    Parameters
    ----------
    effects:
        List of EffectEstimate objects (from compute_effects).
    alpha:
        Significance level for the margin of error.

    Returns
    -------
    LenthResult
        Contains PSE, ME, SME, and updated effect significance flags.
    """
    if not effects:
        return LenthResult(effects=[], pse=0.0, me=0.0, sme=0.0, alpha=alpha)

    estimates = np.array([e.estimate for e in effects], dtype=np.float64)
    abs_estimates = np.abs(estimates)
    n_effects = len(effects)

    # All-zero effects: nothing is significant
    if np.all(abs_estimates == 0):
        return LenthResult(
            effects=list(effects),
            pse=0.0,
            me=0.0,
            sme=0.0,
            alpha=alpha,
        )

    # Iterative PSE computation
    # Start: PSE = 1.5 * median(|effects|)
    # Remove effects > 2.5 * PSE, recompute until stable
    remaining = abs_estimates.copy()
    max_iterations = 50
    for _ in range(max_iterations):
        pse = 1.5 * float(np.median(remaining))
        if pse == 0.0:
            # All remaining effects are zero; break
            break
        mask = remaining <= 2.5 * pse
        new_remaining = remaining[mask]
        if len(new_remaining) == len(remaining):
            # Converged: no effects removed
            break
        if len(new_remaining) == 0:
            break
        remaining = new_remaining

    # Degrees of freedom for t-distribution
    d = max(n_effects / 3.0, 1.0)

    # Margin of Error: ME = t_{alpha/2, d} * PSE
    me = float(sp_stats.t.ppf(1.0 - alpha / 2.0, df=d)) * pse

    # Simultaneous Margin of Error: SME = t_{gamma, d} * PSE
    # gamma = (1 + 0.95^(1/n_effects)) / 2
    gamma = (1.0 + 0.95 ** (1.0 / n_effects)) / 2.0
    sme = float(sp_stats.t.ppf(gamma, df=d)) * pse

    # Mark significant effects
    updated_effects: list[EffectEstimate] = []
    for e in effects:
        updated_effects.append(
            EffectEstimate(
                name=e.name,
                estimate=e.estimate,
                is_main_effect=e.is_main_effect,
                significant=abs(e.estimate) > me,
            )
        )

    return LenthResult(
        effects=updated_effects,
        pse=pse,
        me=me,
        sme=sme,
        alpha=alpha,
    )


# ---------------------------------------------------------------------------
# Half-normal plot data
# ---------------------------------------------------------------------------


def compute_half_normal_points(
    effects: list[EffectEstimate],
) -> list[HalfNormalPoint]:
    """Generate half-normal probability plot data for visual diagnostics.

    Points that deviate upward from the reference line (y = x) indicate
    significant effects.

    Parameters
    ----------
    effects:
        List of EffectEstimate objects.

    Returns
    -------
    list[HalfNormalPoint]
        Sorted by absolute effect ascending, with expected half-normal
        quantiles for probability plotting.
    """
    if not effects:
        return []

    n = len(effects)

    # Sort by absolute effect ascending
    sorted_effects = sorted(effects, key=lambda e: abs(e.estimate))

    points: list[HalfNormalPoint] = []
    for i, eff in enumerate(sorted_effects, start=1):
        # Expected quantile: Phi^{-1}((i - 0.5 + n) / (2n))
        p = (i - 0.5 + n) / (2.0 * n)
        expected_quantile = float(sp_stats.norm.ppf(p))
        points.append(
            HalfNormalPoint(
                label=eff.name,
                absolute_effect=abs(eff.estimate),
                expected_quantile=expected_quantile,
            )
        )

    return points


# ---------------------------------------------------------------------------
# Override detection
# ---------------------------------------------------------------------------


def detect_override(
    factorial_scores: dict[str, float],
    sequential_winner_score: float,
    sequential_winner_name: str,
    all_scores: dict[str, list[float]] | None = None,
    alpha: float = 0.05,
) -> InteractionResult:
    """Detect whether a factorial combination overrides the sequential winner.

    Compares each factorial combination's score against the sequential
    winner. If any combination scores significantly higher, it overrides
    the sequential result.

    Parameters
    ----------
    factorial_scores:
        Mapping of combination_name -> composite score for each
        factorial combination.
    sequential_winner_score:
        Composite score of the sequential beam-search winner.
    sequential_winner_name:
        Name of the sequential winner (used to look up replicated scores).
    all_scores:
        Optional mapping of combination_name -> list of replicated scores.
        When provided, uses Wilcoxon signed-rank test for significance.
        When absent, uses simple score comparison (>).
    alpha:
        Significance threshold for override detection.

    Returns
    -------
    InteractionResult
        Full analysis result including Lenth analysis (empty placeholder
        if not computed externally), half-normal points, and override
        detection outcome.
    """
    best_combo_name: str | None = None
    best_combo_score: float = sequential_winner_score
    override_p: float | None = None
    override_detected = False

    for combo_name, combo_score in factorial_scores.items():
        if combo_score <= sequential_winner_score:
            continue

        # This combination scores higher; test significance
        if all_scores is not None:
            combo_replicated = all_scores.get(combo_name)
            winner_replicated = all_scores.get(sequential_winner_name)

            if (
                combo_replicated is not None
                and winner_replicated is not None
                and len(combo_replicated) >= 2
                and len(winner_replicated) >= 2
            ):
                min_len = min(len(combo_replicated), len(winner_replicated))
                pw = pairwise_wilcoxon(
                    combo_replicated[:min_len],
                    winner_replicated[:min_len],
                    alpha=alpha,
                    variant_a=combo_name,
                    variant_b=sequential_winner_name,
                )
                if pw.significant and combo_score > best_combo_score:
                    best_combo_name = combo_name
                    best_combo_score = combo_score
                    override_p = pw.p_value
                    override_detected = True
            else:
                # Not enough replicates for Wilcoxon; fall back to simple comparison
                if combo_score > best_combo_score:
                    best_combo_name = combo_name
                    best_combo_score = combo_score
                    override_detected = True
        else:
            # No replicated scores; use simple comparison
            if combo_score > best_combo_score:
                best_combo_name = combo_name
                best_combo_score = combo_score
                override_detected = True

    # Parse combination name into factor dict if override found
    override_combination: dict[str, str] | None = None
    if best_combo_name is not None and override_detected:
        # Convention: combination names are "factorA=levelA+factorB=levelB"
        # or just the raw name if no convention
        override_combination = _parse_combination_name(best_combo_name)

    # Create a placeholder LenthResult (caller should replace with real analysis)
    placeholder_lenth = LenthResult(
        effects=[], pse=0.0, me=0.0, sme=0.0, alpha=alpha
    )

    return InteractionResult(
        lenth=placeholder_lenth,
        half_normal_points=[],
        override_detected=override_detected,
        override_combination=override_combination,
        override_p_value=override_p,
        sequential_winner_score=sequential_winner_score,
        best_factorial_score=best_combo_score,
    )


def _parse_combination_name(name: str) -> dict[str, str]:
    """Parse a factorial combination name into a factor-level mapping.

    Supports format ``"factorA=levelA+factorB=levelB"`` or returns
    ``{"combination": name}`` if not parseable.
    """
    parts = name.split("+")
    result: dict[str, str] = {}
    for part in parts:
        if "=" in part:
            key, _, value = part.partition("=")
            result[key.strip()] = value.strip()
        else:
            return {"combination": name}
    return result if result else {"combination": name}
