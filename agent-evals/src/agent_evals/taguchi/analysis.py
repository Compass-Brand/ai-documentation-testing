"""S/N ratio, ANOVA decomposition, and optimal prediction for Taguchi designs.

Implements the statistical analysis pipeline for Taguchi DOE results:
1. Signal-to-noise ratio computation (larger/smaller/nominal-is-best)
2. Main effects per factor level
3. One-way ANOVA decomposition with F-ratios, p-values, eta-squared, omega-squared
4. Optimal configuration prediction with prediction intervals
5. Confirmation run validation
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from typing import TYPE_CHECKING

from scipy import stats as sp_stats

if TYPE_CHECKING:
    from agent_evals.taguchi.factors import TaguchiDesign

logger = logging.getLogger(__name__)

# Additive model R² threshold: below this, interactions are likely significant.
_ADDITIVITY_R_SQUARED_THRESHOLD = 0.8


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
    corrected_p_value: float = 1.0  # BH-corrected p-value


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
    additivity_r_squared: float | None = None
    additivity_warning: str | None = None


@dataclass
class ConfirmationResult:
    """Result of validating confirmation runs against prediction."""

    observed_sn: float
    predicted_sn: float
    prediction_interval: tuple[float, float]
    within_interval: bool
    sigma_deviation: float


@dataclass
class InteractionEffect:
    """Two-factor interaction effect from full factorial analysis."""

    factor1: str  # alphabetically first
    factor2: str
    ss: float  # interaction sum of squares
    df: int  # degrees of freedom: (levels_f1 - 1) * (levels_f2 - 1)
    ms: float  # mean square: ss / df
    f_ratio: float
    p_value: float


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
    # Floor for scores in the 1/y^2 term.  Using 0.01 bounds zero-scores
    # to S/N ≈ -40 dB instead of the degenerate -100 dB from eps=1e-10.
    # This is appropriate for bounded [0,1] LLM evaluation scores where
    # y=0 means total failure, not an infinitesimally small signal.
    score_floor = 0.01
    eps = 1e-10  # guard for log(0) in smaller_is_better

    for row_id, scores in row_scores.items():
        n = len(scores)
        if n == 0:
            raise ValueError(
                f"Row {row_id} has no scores; cannot compute S/N ratio."
            )
        if quality_type == "larger_is_better":
            # S/N = -10 * log10(mean(1/y^2))
            # Clamp y to score_floor to prevent degenerate values from y≈0
            mean_inv_sq = (
                sum(1.0 / (max(y, score_floor) ** 2) for y in scores) / n
            )
            result[row_id] = -10.0 * math.log10(mean_inv_sq)

        elif quality_type == "smaller_is_better":
            # S/N = -10 * log10(mean(y^2))
            mean_sq = sum(y * y for y in scores) / n
            result[row_id] = -10.0 * math.log10(max(mean_sq, eps))

        elif quality_type == "nominal_is_best":
            # S/N = 10 * log10(mean^2 / variance)
            # Use sample variance (n-1) per Taguchi's standard formula.
            mean_val = sum(scores) / n
            if n < 2:
                result[row_id] = 100.0
                continue
            variance = sum((y - mean_val) ** 2 for y in scores) / (n - 1)
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
            if factor.name in row.dummy_factors:
                continue
            level_name = row.assignments[factor.name]
            effects[factor.name][level_name].append(sn_val)

    result: dict[str, dict[str, float]] = {}
    for factor_name, level_data in effects.items():
        result[factor_name] = {}
        for level_name, values in level_data.items():
            result[factor_name][level_name] = (
                sum(values) / len(values) if values else float("nan")
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
    # Exclude rows that have ANY dummy factor from the global S/N pool.
    # This keeps the grand mean unbiased by incomplete experimental conditions.
    non_dummy_rows = [
        row for row in design.rows
        if not row.dummy_factors
    ]
    all_sn = [sn_ratios[row.run_id] for row in non_dummy_rows]
    n = len(all_sn)
    grand_mean = sum(all_sn) / n

    # Total sum of squares
    ss_total = sum((y - grand_mean) ** 2 for y in all_sn)

    # Compute SS for each factor
    factor_results: list[ANOVAFactorResult] = []
    ss_factors_sum = 0.0
    df_factors_sum = 0

    for factor in design.factors:
        # Group S/N ratios by level, using only non-dummy rows
        # (same row set as grand_mean) for consistent ANOVA identity.
        level_groups: dict[str, list[float]] = {
            level: [] for level in factor.level_names
        }
        for row in non_dummy_rows:
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

    # Benjamini-Hochberg FDR correction for multiple comparisons
    _apply_bh_correction(factor_results)

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


def _apply_bh_correction(factors: list[ANOVAFactorResult]) -> None:
    """Apply Benjamini-Hochberg FDR correction to factor p-values in-place.

    Sets ``corrected_p_value`` on each factor. With m factors, the corrected
    p-value for rank i (1-based, sorted ascending by raw p) is::

        p_corrected[i] = min(p_raw[i] * m / i, 1.0)

    A backward sweep ensures monotonicity.
    """
    m = len(factors)
    if m == 0:
        return

    # Sort indices by raw p-value ascending
    ranked = sorted(range(m), key=lambda i: factors[i].p_value)

    # Forward pass: compute corrected values
    corrected = [0.0] * m
    for rank_pos, idx in enumerate(ranked):
        rank = rank_pos + 1  # 1-based rank
        corrected[idx] = min(factors[idx].p_value * m / rank, 1.0)

    # Backward sweep for monotonicity: corrected[i] = min(corrected[i], corrected[i+1])
    for rank_pos in range(m - 2, -1, -1):
        idx = ranked[rank_pos]
        next_idx = ranked[rank_pos + 1]
        corrected[idx] = min(corrected[idx], corrected[next_idx])

    for i in range(m):
        factors[i].corrected_p_value = corrected[i]


# ---------------------------------------------------------------------------
# Interaction Effects
# ---------------------------------------------------------------------------


def compute_interactions(
    design_rows: list[dict[str, str]],
    sn_ratios: list[float],
) -> list[InteractionEffect]:
    """Compute 2-way interaction effects from full factorial data.

    For each pair of factors (A, B), the interaction SS is:
        SS_AB = SS_cells(A,B) - SS_A - SS_B
    where SS_cells is the between-cells sum of squares for the A*B table.

    Args:
        design_rows: List of dicts mapping factor_name -> level_name.
        sn_ratios: List of S/N ratios (same length as design_rows).

    Returns:
        Sorted list of InteractionEffect (sorted by factor pair name).
    """
    if not design_rows:
        return []

    factor_names = sorted(design_rows[0].keys())
    if len(factor_names) < 2:
        return []

    n = len(sn_ratios)
    grand_mean = sum(sn_ratios) / n

    # Pre-compute main-effect SS for each factor
    main_ss: dict[str, float] = {}
    for fname in factor_names:
        groups: dict[str, list[float]] = defaultdict(list)
        for row, sn in zip(design_rows, sn_ratios):
            groups[row[fname]].append(sn)
        ss = 0.0
        for vals in groups.values():
            level_mean = sum(vals) / len(vals)
            ss += len(vals) * (level_mean - grand_mean) ** 2
        main_ss[fname] = ss

    # Compute interaction effects for each factor pair
    results: list[InteractionEffect] = []

    for f1, f2 in combinations(factor_names, 2):
        # Group S/N ratios by (f1_level, f2_level) cells
        cells: dict[tuple[str, str], list[float]] = defaultdict(list)
        for row, sn in zip(design_rows, sn_ratios):
            key = (row[f1], row[f2])
            cells[key].append(sn)

        # Between-cell SS
        ss_cells = 0.0
        for vals in cells.values():
            cell_mean = sum(vals) / len(vals)
            ss_cells += len(vals) * (cell_mean - grand_mean) ** 2

        # Interaction SS = SS_cells - SS_f1 - SS_f2
        ss_interaction = max(0.0, ss_cells - main_ss[f1] - main_ss[f2])

        # Degrees of freedom
        levels_f1 = len({row[f1] for row in design_rows})
        levels_f2 = len({row[f2] for row in design_rows})
        df = (levels_f1 - 1) * (levels_f2 - 1)
        ms = ss_interaction / df if df > 0 else 0.0

        # Within-cell SS for F-ratio denominator
        ss_within = 0.0
        df_within = 0
        for vals in cells.values():
            if len(vals) > 1:
                cell_mean = sum(vals) / len(vals)
                ss_within += sum((v - cell_mean) ** 2 for v in vals)
                df_within += len(vals) - 1

        ms_within = ss_within / df_within if df_within > 0 else 0.0

        # F-ratio and p-value
        if ms_within > 1e-30 and df > 0 and df_within > 0:
            f_ratio = ms / ms_within
            p_value = 1.0 - sp_stats.f.cdf(f_ratio, df, df_within)
        elif ms > 1e-30 and df > 0:
            f_ratio = float("inf")
            p_value = 0.0
        else:
            f_ratio = 0.0
            p_value = 1.0

        results.append(InteractionEffect(
            factor1=f1,
            factor2=f2,
            ss=ss_interaction,
            df=df,
            ms=ms,
            f_ratio=f_ratio,
            p_value=p_value,
        ))

    return sorted(results, key=lambda ie: (ie.factor1, ie.factor2))


# ---------------------------------------------------------------------------
# Optimal Prediction
# ---------------------------------------------------------------------------


def predict_optimal(
    main_effects: dict[str, dict[str, float]],
    sn_ratios: dict[int, float] | None = None,
    design: TaguchiDesign | None = None,
    anova_result: ANOVAResult | None = None,
) -> OptimalPrediction:
    """Predict the optimal configuration from main effects.

    Selects the level with the highest mean S/N for each factor and
    computes the predicted S/N using the additive model.

    When *anova_result* is provided, the prediction interval uses the
    ANOVA residual error (ms_error) and proper degrees of freedom
    (df_error) instead of total variance.

    When *design* is provided alongside *sn_ratios*, an additivity check
    is performed.  The R-squared of the additive model is computed by
    comparing predicted vs observed S/N for every OA row.  If R-squared
    falls below the threshold, ``additivity_warning`` is set.

    Args:
        main_effects: {factor_name: {level_name: mean_sn}}.
        sn_ratios: Optional S/N ratios for prediction interval computation.
        design: Optional TaguchiDesign for additivity validation.
        anova_result: Optional ANOVA result for proper prediction intervals.

    Returns:
        OptimalPrediction with assignment, predicted S/N, and optional interval.
    """
    # 1. Select best level per factor (skip NaN — unobserved levels)
    optimal: dict[str, str] = {}
    for factor_name, levels in main_effects.items():
        observed = {k: v for k, v in levels.items() if not math.isnan(v)}
        if not observed:
            # All levels unobserved — pick first arbitrarily
            best_level = next(iter(levels))
        else:
            best_level = max(observed, key=observed.get)  # type: ignore[arg-type]
        optimal[factor_name] = best_level

    # 2. Compute predicted S/N (additive model)
    if not main_effects:
        raise ValueError("main_effects is empty; cannot compute prediction.")
    # Use mean-of-factor-means to avoid bias in mixed-level designs
    # where factors have different numbers of levels.
    # Skip NaN values (unobserved levels) in the mean calculation.
    factor_means: dict[str, float] = {}
    for name, levels in main_effects.items():
        observed_vals = [v for v in levels.values() if not math.isnan(v)]
        factor_means[name] = (
            sum(observed_vals) / len(observed_vals) if observed_vals else 0.0
        )
    grand_mean = sum(factor_means.values()) / len(factor_means)

    predicted = grand_mean
    for factor_name, levels in main_effects.items():
        best_val = levels[optimal[factor_name]]
        predicted += best_val - factor_means[factor_name]

    # 3. Prediction interval (if S/N ratios provided)
    interval: tuple[float, float] | None = None
    se: float | None = None

    if sn_ratios is not None and len(sn_ratios) > 2:
        n = len(sn_ratios)

        if anova_result is not None:
            # Use ANOVA residual error with n_eff (effective replications).
            # For the additive model the prediction uses 1 + sum(df_i)
            # estimated parameters, so n_eff = n / (1 + sum(df_i)).
            sum_dof = sum(f.df for f in anova_result.factors)
            n_eff = n / (1 + sum_dof)
            se = math.sqrt(anova_result.ms_error / n_eff)
            df = anova_result.df_error
        else:
            # Fallback: total variance (no ANOVA available)
            sn_values = list(sn_ratios.values())
            sn_mean = sum(sn_values) / n
            residual_var = (
                sum((y - sn_mean) ** 2 for y in sn_values) / (n - 1)
            )
            se = math.sqrt(residual_var / n)
            df = n - 1

        if se > 0:
            t_val = sp_stats.t.ppf(0.975, df)
            margin = t_val * se
            interval = (predicted - margin, predicted + margin)

    # 4. Additivity check (if design provided)
    r_squared: float | None = None
    warning: str | None = None

    if design is not None and sn_ratios is not None:
        r_squared = _compute_additivity_r_squared(
            design, main_effects, sn_ratios,
        )
        if r_squared < _ADDITIVITY_R_SQUARED_THRESHOLD:
            warning = (
                f"Additive model R²={r_squared:.3f} is below "
                f"{_ADDITIVITY_R_SQUARED_THRESHOLD}. Factor interaction "
                f"effects may be significant; predicted S/N may be "
                f"inaccurate by 5-20%."
            )
            logger.warning(
                "Additivity check: R²=%.3f < %.1f threshold. "
                "Factor interactions likely present.",
                r_squared,
                _ADDITIVITY_R_SQUARED_THRESHOLD,
            )

    return OptimalPrediction(
        optimal_assignment=optimal,
        predicted_sn=predicted,
        prediction_interval=interval,
        se_prediction=se,
        additivity_r_squared=r_squared,
        additivity_warning=warning,
    )


def _compute_additivity_r_squared(
    design: TaguchiDesign,
    main_effects: dict[str, dict[str, float]],
    sn_ratios: dict[int, float],
) -> float:
    """Compute R-squared of the additive model against observed S/N ratios.

    For each OA row, the additive prediction is:
        predicted_row = grand_mean + sum(level_effect_i - factor_mean_i)

    R-squared = 1 - SS_residual / SS_total.
    """
    # Use mean-of-factor-means (consistent with predict_optimal) to avoid
    # bias in mixed-level designs.  Skip NaN (unobserved) levels.
    factor_means: dict[str, float] = {}
    for name, levels in main_effects.items():
        obs_vals = [v for v in levels.values() if not math.isnan(v)]
        factor_means[name] = (
            sum(obs_vals) / len(obs_vals) if obs_vals else 0.0
        )
    grand_mean = sum(factor_means.values()) / len(factor_means)

    observed: list[float] = []
    predicted_vals: list[float] = []

    for row in design.rows:
        if row.run_id not in sn_ratios:
            continue
        # Skip rows with dummy factors (level not in main_effects)
        if row.dummy_factors:
            continue
        obs = sn_ratios[row.run_id]
        pred = grand_mean
        for factor_name, levels in main_effects.items():
            level_name = row.assignments[factor_name]
            pred += levels[level_name] - factor_means[factor_name]
        observed.append(obs)
        predicted_vals.append(pred)

    if len(observed) < 2:
        return 1.0  # Not enough data to assess

    obs_mean = sum(observed) / len(observed)
    ss_total = sum((y - obs_mean) ** 2 for y in observed)
    ss_residual = sum(
        (y - yhat) ** 2 for y, yhat in zip(observed, predicted_vals)
    )

    if ss_total == 0:
        return 1.0  # No variance in data
    return 1.0 - ss_residual / ss_total


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
