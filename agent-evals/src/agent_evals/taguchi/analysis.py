"""S/N ratio, ANOVA decomposition, and optimal prediction for Taguchi designs.

Implements the statistical analysis pipeline for Taguchi DOE results:
1. Signal-to-noise ratio computation (larger/smaller/nominal-is-best)
2. Main effects per factor level
3. One-way ANOVA decomposition with F-ratios, p-values, eta-squared, omega-squared
4. Optimal configuration prediction with prediction intervals
5. Confirmation run validation
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from scipy import stats as sp_stats

if TYPE_CHECKING:
    from agent_evals.taguchi.factors import TaguchiDesign


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ANOVAFactorResult:
    """ANOVA result for a single factor."""

    factor_name: str
    ss: float  # sum of squares
    df: int  # degrees of freedom
    ms: float  # mean square
    f_ratio: float
    p_value: float
    eta_squared: float
    omega_squared: float


@dataclass
class ANOVAResult:
    """Complete ANOVA decomposition results."""

    factors: list[ANOVAFactorResult]
    ss_total: float
    ss_error: float
    df_error: int
    ms_error: float
    error_eta_squared: float
    grand_mean: float


@dataclass
class OptimalPrediction:
    """Optimal configuration prediction from main effects."""

    optimal_assignment: dict[str, str]
    predicted_sn: float
    prediction_interval: tuple[float, float] | None = None
    se_prediction: float | None = None


@dataclass
class ConfirmationResult:
    """Result of validating confirmation runs against prediction."""

    observed_sn: float
    predicted_sn: float
    prediction_interval: tuple[float, float]
    within_interval: bool
    sigma_deviation: float


# ---------------------------------------------------------------------------
# S/N Ratio
# ---------------------------------------------------------------------------


def compute_sn_ratios(
    row_scores: dict[int, list[float]],
    quality_type: str = "larger_is_better",
) -> dict[int, float]:
    """Compute signal-to-noise ratio for each OA row.

    Args:
        row_scores: Mapping of row_id to list of observed scores.
        quality_type: One of "larger_is_better", "smaller_is_better",
            or "nominal_is_best".

    Returns:
        Dict mapping row_id to S/N ratio (in dB).
    """
    result: dict[int, float] = {}
    eps = 1e-10  # guard against division by zero and log(0)

    for row_id, scores in row_scores.items():
        n = len(scores)
        if n == 0:
            raise ValueError(
                f"Row {row_id} has no scores; cannot compute S/N ratio."
            )
        if quality_type == "larger_is_better":
            # S/N = -10 * log10(mean(1/y^2))
            mean_inv_sq = sum(1.0 / (y * y + eps) for y in scores) / n
            result[row_id] = -10.0 * math.log10(mean_inv_sq)

        elif quality_type == "smaller_is_better":
            # S/N = -10 * log10(mean(y^2))
            mean_sq = sum(y * y for y in scores) / n
            result[row_id] = -10.0 * math.log10(max(mean_sq, eps))

        elif quality_type == "nominal_is_best":
            # S/N = 10 * log10(mean^2 / variance)
            mean_val = sum(scores) / n
            variance = sum((y - mean_val) ** 2 for y in scores) / n
            if variance < 1e-30:
                # Near-zero variance -> very high S/N
                result[row_id] = 100.0
            else:
                result[row_id] = 10.0 * math.log10(
                    (mean_val * mean_val) / variance
                )
        else:
            msg = (
                f"Invalid quality_type: '{quality_type}'. "
                "Must be 'larger_is_better', 'smaller_is_better', "
                "or 'nominal_is_best'."
            )
            raise ValueError(msg)

    return result


# ---------------------------------------------------------------------------
# Main Effects
# ---------------------------------------------------------------------------


def compute_main_effects(
    design: TaguchiDesign,
    sn_ratios: dict[int, float],
) -> dict[str, dict[str, float]]:
    """Compute the mean S/N ratio for each level of each factor.

    Args:
        design: The Taguchi experimental design.
        sn_ratios: Mapping of row_id (1-based) to S/N ratio.

    Returns:
        Nested dict: {factor_name: {level_name: mean_sn_ratio}}.
    """
    effects: dict[str, dict[str, list[float]]] = {}

    for factor in design.factors:
        effects[factor.name] = {
            level: [] for level in factor.level_names
        }

    for row in design.rows:
        sn_val = sn_ratios[row.run_id]
        for factor in design.factors:
            level_name = row.assignments[factor.name]
            effects[factor.name][level_name].append(sn_val)

    result: dict[str, dict[str, float]] = {}
    for factor_name, level_data in effects.items():
        result[factor_name] = {}
        for level_name, values in level_data.items():
            result[factor_name][level_name] = (
                sum(values) / len(values) if values else 0.0
            )

    return result


# ---------------------------------------------------------------------------
# ANOVA
# ---------------------------------------------------------------------------


def run_anova(
    design: TaguchiDesign,
    sn_ratios: dict[int, float],
) -> ANOVAResult:
    """One-way ANOVA decomposition with F-ratios, p-values, and effect sizes.

    Args:
        design: The Taguchi experimental design.
        sn_ratios: Mapping of row_id (1-based) to S/N ratio.

    Returns:
        ANOVAResult with per-factor statistics and error terms.
    """
    all_sn = [sn_ratios[row.run_id] for row in design.rows]
    n = len(all_sn)
    grand_mean = sum(all_sn) / n

    # Total sum of squares
    ss_total = sum((y - grand_mean) ** 2 for y in all_sn)

    # Compute SS for each factor
    factor_results: list[ANOVAFactorResult] = []
    ss_factors_sum = 0.0
    df_factors_sum = 0

    for factor in design.factors:
        # Group S/N ratios by level
        level_groups: dict[str, list[float]] = {
            level: [] for level in factor.level_names
        }
        for row in design.rows:
            level_name = row.assignments[factor.name]
            level_groups[level_name].append(sn_ratios[row.run_id])

        # SS_factor = sum(n_i * (mean_i - grand_mean)^2)
        ss_factor = 0.0
        for level_name, values in level_groups.items():
            if values:
                level_mean = sum(values) / len(values)
                ss_factor += len(values) * (level_mean - grand_mean) ** 2

        df = factor.n_levels - 1
        ms = ss_factor / df if df > 0 else 0.0

        ss_factors_sum += ss_factor
        df_factors_sum += df

        factor_results.append(ANOVAFactorResult(
            factor_name=factor.name,
            ss=ss_factor,
            df=df,
            ms=ms,
            f_ratio=0.0,  # computed after error term
            p_value=1.0,
            eta_squared=0.0,
            omega_squared=0.0,
        ))

    # Error term
    ss_error = ss_total - ss_factors_sum
    ss_error = max(ss_error, 0.0)  # guard against floating point
    df_error = n - 1 - df_factors_sum
    df_error = max(df_error, 1)  # guard against zero
    ms_error = ss_error / df_error

    # Compute F-ratios, p-values, and effect sizes
    for fr in factor_results:
        if ms_error > 1e-30:
            fr.f_ratio = fr.ms / ms_error
            fr.p_value = 1.0 - sp_stats.f.cdf(fr.f_ratio, fr.df, df_error)
        else:
            fr.f_ratio = float("inf") if fr.ms > 1e-30 else 0.0
            fr.p_value = 0.0 if fr.ms > 1e-30 else 1.0

        # Eta-squared: proportion of total variance
        if ss_total > 1e-30:
            fr.eta_squared = fr.ss / ss_total
        else:
            fr.eta_squared = 0.0

        # Omega-squared: less biased effect size
        # omega^2 = (SS_factor - df_factor * MS_error) / (SS_total + MS_error)
        numerator = fr.ss - fr.df * ms_error
        denominator = ss_total + ms_error
        if denominator > 1e-30:
            fr.omega_squared = max(0.0, numerator / denominator)
        else:
            fr.omega_squared = 0.0

    error_eta = ss_error / ss_total if ss_total > 1e-30 else 0.0

    return ANOVAResult(
        factors=factor_results,
        ss_total=ss_total,
        ss_error=ss_error,
        df_error=df_error,
        ms_error=ms_error,
        error_eta_squared=error_eta,
        grand_mean=grand_mean,
    )


# ---------------------------------------------------------------------------
# Optimal Prediction
# ---------------------------------------------------------------------------


def predict_optimal(
    main_effects: dict[str, dict[str, float]],
    sn_ratios: dict[int, float] | None = None,
) -> OptimalPrediction:
    """Predict the optimal configuration from main effects.

    Selects the level with the highest mean S/N for each factor and
    computes the predicted S/N using the additive model.

    Args:
        main_effects: {factor_name: {level_name: mean_sn}}.
        sn_ratios: Optional S/N ratios for prediction interval computation.

    Returns:
        OptimalPrediction with assignment, predicted S/N, and optional interval.
    """
    # 1. Select best level per factor
    optimal: dict[str, str] = {}
    for factor_name, levels in main_effects.items():
        best_level = max(levels, key=levels.get)  # type: ignore[arg-type]
        optimal[factor_name] = best_level

    # 2. Compute predicted S/N (additive model)
    all_values = [v for d in main_effects.values() for v in d.values()]
    if not all_values:
        raise ValueError("main_effects is empty; cannot compute prediction.")
    grand_mean = sum(all_values) / len(all_values)

    predicted = grand_mean
    for factor_name, levels in main_effects.items():
        factor_mean = sum(levels.values()) / len(levels)
        best_val = levels[optimal[factor_name]]
        predicted += best_val - factor_mean

    # 3. Prediction interval (if S/N ratios provided)
    interval: tuple[float, float] | None = None
    se: float | None = None

    if sn_ratios is not None and len(sn_ratios) > 2:
        sn_values = list(sn_ratios.values())
        n = len(sn_values)
        sn_mean = sum(sn_values) / n
        residual_var = sum((y - sn_mean) ** 2 for y in sn_values) / (n - 1)
        se = math.sqrt(residual_var / n)

        if se > 0:
            df = n - 1
            t_val = sp_stats.t.ppf(0.975, df)
            margin = t_val * se
            interval = (predicted - margin, predicted + margin)

    return OptimalPrediction(
        optimal_assignment=optimal,
        predicted_sn=predicted,
        prediction_interval=interval,
        se_prediction=se,
    )


# ---------------------------------------------------------------------------
# Confirmation Validation
# ---------------------------------------------------------------------------


def validate_confirmation(
    prediction: OptimalPrediction,
    confirmation_scores: list[float],
    quality_type: str = "larger_is_better",
) -> ConfirmationResult:
    """Validate confirmation run results against predicted S/N.

    Args:
        prediction: The optimal prediction from predict_optimal().
        confirmation_scores: Observed scores from confirmation runs.
        quality_type: Quality type for S/N computation.

    Returns:
        ConfirmationResult with observed S/N, interval check, and deviation.
    """
    # Compute observed S/N from confirmation scores
    sn = compute_sn_ratios({0: confirmation_scores}, quality_type)
    observed_sn = sn[0]

    # Check against prediction interval
    low, high = prediction.prediction_interval or (
        prediction.predicted_sn - 1.0,
        prediction.predicted_sn + 1.0,
    )
    within = low <= observed_sn <= high

    # Sigma deviation
    se = prediction.se_prediction or 1.0
    sigma_dev = (observed_sn - prediction.predicted_sn) / se if se > 0 else 0.0

    return ConfirmationResult(
        observed_sn=observed_sn,
        predicted_sn=prediction.predicted_sn,
        prediction_interval=(low, high),
        within_interval=within,
        sigma_deviation=sigma_dev,
    )
