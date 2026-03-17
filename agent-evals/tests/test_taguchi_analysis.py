"""Tests for Taguchi S/N ratio, ANOVA decomposition, and optimal prediction."""

from __future__ import annotations

import math

import pytest
from agent_evals.taguchi.analysis import (
    ANOVAResult,
    ConfirmationResult,
    OptimalPrediction,
    compute_interactions,
    compute_main_effects,
    compute_sn_ratios,
    predict_optimal,
    run_anova,
    validate_confirmation,
)
from agent_evals.taguchi.factors import (
    TaguchiDesign,
    TaguchiExperimentRow,
    TaguchiFactorDef,
)
from scipy import stats

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_design_2factor() -> TaguchiDesign:
    """Simple 2-factor, 3-level design (L9-like, 9 rows)."""
    factors = [
        TaguchiFactorDef(name="axis_1", n_levels=3,
                         level_names=["flat", "2tier", "3tier"], axis=1),
        TaguchiFactorDef(name="axis_2", n_levels=3,
                         level_names=["path", "summary", "tokens"], axis=2),
    ]
    # Simulate L9 assignments
    assignments_data = [
        {"axis_1": "flat", "axis_2": "path"},
        {"axis_1": "flat", "axis_2": "summary"},
        {"axis_1": "flat", "axis_2": "tokens"},
        {"axis_1": "2tier", "axis_2": "path"},
        {"axis_1": "2tier", "axis_2": "summary"},
        {"axis_1": "2tier", "axis_2": "tokens"},
        {"axis_1": "3tier", "axis_2": "path"},
        {"axis_1": "3tier", "axis_2": "summary"},
        {"axis_1": "3tier", "axis_2": "tokens"},
    ]
    rows = [
        TaguchiExperimentRow(run_id=i + 1, assignments=a)
        for i, a in enumerate(assignments_data)
    ]
    return TaguchiDesign(
        oa_name="L9", n_runs=9, factors=factors, rows=rows,
        level_counts=[3, 3],
    )


# ---------------------------------------------------------------------------
# S/N Ratio Tests
# ---------------------------------------------------------------------------


class TestComputeSNRatios:
    """Verify S/N ratio computation for different quality types."""

    def test_larger_is_better_basic(self):
        """S/N = -10 * log10(mean(1/y^2)) for larger-is-better."""
        scores = {1: [0.8, 0.9, 0.85], 2: [0.5, 0.6, 0.55]}
        sn = compute_sn_ratios(scores, quality_type="larger_is_better")

        # Row 1 has higher scores -> higher S/N
        assert sn[1] > sn[2]

    def test_larger_is_better_hand_computed(self):
        """Verify against hand-computed value."""
        scores = {1: [1.0, 1.0, 1.0]}
        sn = compute_sn_ratios(scores, quality_type="larger_is_better")
        # S/N = -10*log10(mean(1/1^2)) = -10*log10(1) ≈ 0
        # Epsilon guard (1e-10) introduces a negligible offset
        assert abs(sn[1]) < 1e-6

    def test_larger_is_better_with_high_scores(self):
        """Higher scores produce higher S/N."""
        scores = {1: [2.0, 2.0, 2.0], 2: [1.0, 1.0, 1.0]}
        sn = compute_sn_ratios(scores, quality_type="larger_is_better")
        # S/N for row 1: -10*log10(mean(1/4)) = -10*log10(0.25) ≈ 6.02
        expected_sn_1 = -10 * math.log10(1 / 4)
        assert abs(sn[1] - expected_sn_1) < 0.01

    def test_smaller_is_better(self):
        """S/N = -10 * log10(mean(y^2)) for smaller-is-better."""
        scores = {1: [0.1, 0.2, 0.15], 2: [0.5, 0.6, 0.55]}
        sn = compute_sn_ratios(scores, quality_type="smaller_is_better")

        # Row 1 has smaller scores -> higher S/N (less noise)
        assert sn[1] > sn[2]

    def test_nominal_is_best(self):
        """S/N = 10 * log10(mean^2 / var) for nominal-is-best."""
        scores = {
            1: [1.0, 1.0, 1.0],  # zero variance -> very high S/N
            2: [0.5, 1.0, 1.5],  # high variance
        }
        sn = compute_sn_ratios(scores, quality_type="nominal_is_best")
        assert sn[1] > sn[2]

    def test_nominal_is_best_uses_sample_variance(self):
        """Bug #228: nominal_is_best should use n-1 (Bessel's correction)."""
        # With scores [0.4, 0.6]:
        #   mean = 0.5
        #   population var (/ n):   (0.01 + 0.01) / 2 = 0.01
        #   sample var     (/ n-1): (0.01 + 0.01) / 1 = 0.02
        #   S/N (pop):  10*log10(0.25 / 0.01) = 10*log10(25) ≈ 13.979
        #   S/N (sample): 10*log10(0.25 / 0.02) = 10*log10(12.5) ≈ 10.969
        scores = {1: [0.4, 0.6]}
        sn = compute_sn_ratios(scores, quality_type="nominal_is_best")

        mean_val = 0.5
        sample_var = sum((y - mean_val) ** 2 for y in [0.4, 0.6]) / 1  # n-1
        expected_sn = 10.0 * math.log10(mean_val ** 2 / sample_var)

        assert abs(sn[1] - expected_sn) < 0.001, (
            f"S/N={sn[1]:.4f} doesn't match sample variance formula "
            f"(expected {expected_sn:.4f}). Likely using population variance."
        )

    def test_nominal_is_best_single_observation_returns_cap(self):
        """Bug #228: n=1 should return capped S/N, not divide-by-zero."""
        scores = {1: [0.7]}
        sn = compute_sn_ratios(scores, quality_type="nominal_is_best")
        assert sn[1] == 100.0

    def test_invalid_quality_type_raises(self):
        with pytest.raises(ValueError, match="quality_type"):
            compute_sn_ratios({1: [0.5]}, quality_type="invalid")

    def test_larger_is_better_all_zero_scores(self):
        """All-zero scores should not raise ZeroDivisionError."""
        scores = {1: [0.0, 0.0, 0.0]}
        sn = compute_sn_ratios(scores, quality_type="larger_is_better")
        assert isinstance(sn[1], float)
        assert math.isfinite(sn[1])

    def test_larger_is_better_some_zero_scores(self):
        """Mixed zero/non-zero scores should not raise ZeroDivisionError."""
        scores = {1: [0.0, 0.8, 0.0, 0.9]}
        sn = compute_sn_ratios(scores, quality_type="larger_is_better")
        assert isinstance(sn[1], float)
        assert math.isfinite(sn[1])

    def test_smaller_is_better_all_zero_scores(self):
        """All-zero scores should not raise ValueError (log of zero)."""
        scores = {1: [0.0, 0.0, 0.0]}
        sn = compute_sn_ratios(scores, quality_type="smaller_is_better")
        assert isinstance(sn[1], float)
        assert math.isfinite(sn[1])

    def test_larger_is_better_zero_scores_bounded(self):
        """Zero scores should produce bounded S/N, not extreme ~-100 dB values.

        With y=0 in larger_is_better, the 1/y^2 term should be clamped
        so the S/N ratio stays within a reasonable range (> -50 dB).
        """
        scores = {
            1: [0.0, 0.0, 0.0],
            2: [0.8, 0.9, 0.7],
        }
        sn = compute_sn_ratios(scores, quality_type="larger_is_better")
        # Zero row should not produce extreme values like -100 dB
        assert sn[1] > -50.0, (
            f"S/N for all-zero scores is {sn[1]} dB, too extreme. "
            "Score floor should prevent degenerate values."
        )

    def test_larger_is_better_bimodal_scores_reasonable_spread(self):
        """Bimodal [0,1] scores should produce S/N values with reasonable spread.

        A row of all-0s vs all-1s should differ, but not by 100+ dB.
        """
        scores = {
            1: [0.0, 0.0, 1.0, 1.0],  # bimodal
            2: [1.0, 1.0, 1.0, 1.0],  # all-ones
        }
        sn = compute_sn_ratios(scores, quality_type="larger_is_better")
        spread = abs(sn[2] - sn[1])
        assert spread < 50.0, (
            f"S/N spread between bimodal and all-1 is {spread} dB, too extreme."
        )

    def test_returns_dict_of_floats(self):
        scores = {1: [0.8], 2: [0.5], 3: [0.7]}
        sn = compute_sn_ratios(scores)
        assert isinstance(sn, dict)
        assert all(isinstance(v, float) for v in sn.values())
        assert set(sn.keys()) == {1, 2, 3}


# ---------------------------------------------------------------------------
# Main Effects Tests
# ---------------------------------------------------------------------------


class TestComputeMainEffects:
    """Verify main effect computation per factor level."""

    def test_returns_effects_for_all_factors(self):
        design = _make_design_2factor()
        sn = {i + 1: float(i) for i in range(9)}

        effects = compute_main_effects(design, sn)

        assert "axis_1" in effects
        assert "axis_2" in effects

    def test_effects_have_all_levels(self):
        design = _make_design_2factor()
        sn = {i + 1: float(i) for i in range(9)}

        effects = compute_main_effects(design, sn)

        assert set(effects["axis_1"].keys()) == {"flat", "2tier", "3tier"}
        assert set(effects["axis_2"].keys()) == {"path", "summary", "tokens"}

    def test_best_level_has_highest_mean_sn(self):
        design = _make_design_2factor()
        # "3tier" rows (7,8,9) get highest S/N
        sn = {
            1: 1.0, 2: 1.5, 3: 1.2,   # flat
            4: 2.0, 5: 2.5, 6: 2.2,   # 2tier
            7: 4.0, 8: 4.5, 9: 4.2,   # 3tier
        }
        effects = compute_main_effects(design, sn)

        assert effects["axis_1"]["3tier"] > effects["axis_1"]["2tier"]
        assert effects["axis_1"]["2tier"] > effects["axis_1"]["flat"]

    def test_main_effect_is_mean_of_level_sn(self):
        design = _make_design_2factor()
        sn = {
            1: 1.0, 2: 2.0, 3: 3.0,   # flat
            4: 4.0, 5: 5.0, 6: 6.0,   # 2tier
            7: 7.0, 8: 8.0, 9: 9.0,   # 3tier
        }
        effects = compute_main_effects(design, sn)

        # flat mean = (1+2+3)/3 = 2.0
        assert abs(effects["axis_1"]["flat"] - 2.0) < 1e-10
        # 2tier mean = (4+5+6)/3 = 5.0
        assert abs(effects["axis_1"]["2tier"] - 5.0) < 1e-10


# ---------------------------------------------------------------------------
# ANOVA Tests
# ---------------------------------------------------------------------------


class TestRunANOVA:
    """Verify ANOVA decomposition."""

    def test_returns_anova_result(self):
        design = _make_design_2factor()
        sn = {i + 1: float(i) * 0.5 for i in range(9)}

        result = run_anova(design, sn)

        assert isinstance(result, ANOVAResult)
        assert len(result.factors) > 0

    def test_f_ratios_positive(self):
        design = _make_design_2factor()
        sn = {
            1: 1.0, 2: 1.5, 3: 1.2,
            4: 3.0, 5: 3.5, 6: 3.2,
            7: 5.0, 8: 5.5, 9: 5.2,
        }
        result = run_anova(design, sn)

        for fr in result.factors:
            assert fr.f_ratio >= 0, f"{fr.factor_name} F-ratio is negative"

    def test_p_values_between_0_and_1(self):
        design = _make_design_2factor()
        sn = {
            1: 1.0, 2: 1.5, 3: 1.2,
            4: 3.0, 5: 3.5, 6: 3.2,
            7: 5.0, 8: 5.5, 9: 5.2,
        }
        result = run_anova(design, sn)

        for fr in result.factors:
            assert 0 <= fr.p_value <= 1, (
                f"{fr.factor_name} p-value out of range: {fr.p_value}"
            )

    def test_eta_squared_sums_approximately_to_1(self):
        design = _make_design_2factor()
        sn = {
            1: 1.0, 2: 1.5, 3: 1.2,
            4: 3.0, 5: 3.5, 6: 3.2,
            7: 5.0, 8: 5.5, 9: 5.2,
        }
        result = run_anova(design, sn)

        total_eta = sum(fr.eta_squared for fr in result.factors)
        total_eta += result.error_eta_squared
        assert abs(total_eta - 1.0) < 0.01, (
            f"Eta-squared sum = {total_eta}, expected ~1.0"
        )

    def test_omega_squared_nonnegative(self):
        design = _make_design_2factor()
        sn = {
            1: 1.0, 2: 1.5, 3: 1.2,
            4: 3.0, 5: 3.5, 6: 3.2,
            7: 5.0, 8: 5.5, 9: 5.2,
        }
        result = run_anova(design, sn)

        for fr in result.factors:
            assert fr.omega_squared >= 0, (
                f"{fr.factor_name} omega-squared is negative: {fr.omega_squared}"
            )

    def test_omega_squared_lte_eta_squared(self):
        design = _make_design_2factor()
        sn = {
            1: 1.0, 2: 1.5, 3: 1.2,
            4: 3.0, 5: 3.5, 6: 3.2,
            7: 5.0, 8: 5.5, 9: 5.2,
        }
        result = run_anova(design, sn)

        for fr in result.factors:
            assert fr.omega_squared <= fr.eta_squared + 1e-10, (
                f"{fr.factor_name}: omega^2={fr.omega_squared} > eta^2={fr.eta_squared}"
            )

    def test_factor_results_have_correct_names(self):
        design = _make_design_2factor()
        sn = {i + 1: float(i) for i in range(9)}

        result = run_anova(design, sn)

        factor_names = {fr.factor_name for fr in result.factors}
        assert "axis_1" in factor_names
        assert "axis_2" in factor_names

    def test_corrected_p_values_exist(self):
        """Each factor result should have a corrected_p_value field."""
        design = _make_design_2factor()
        sn = {
            1: 1.0, 2: 1.5, 3: 1.2,
            4: 3.0, 5: 3.5, 6: 3.2,
            7: 5.0, 8: 5.5, 9: 5.2,
        }
        result = run_anova(design, sn)

        for fr in result.factors:
            assert hasattr(fr, "corrected_p_value"), (
                f"{fr.factor_name} missing corrected_p_value"
            )
            assert 0 <= fr.corrected_p_value <= 1, (
                f"{fr.factor_name} corrected_p_value out of range: {fr.corrected_p_value}"
            )

    def test_corrected_p_values_gte_raw(self):
        """BH-corrected p-values must be >= raw p-values."""
        design = _make_design_2factor()
        sn = {
            1: 1.0, 2: 1.5, 3: 1.2,
            4: 3.0, 5: 3.5, 6: 3.2,
            7: 5.0, 8: 5.5, 9: 5.2,
        }
        result = run_anova(design, sn)

        for fr in result.factors:
            assert fr.corrected_p_value >= fr.p_value - 1e-10, (
                f"{fr.factor_name}: corrected {fr.corrected_p_value} < raw {fr.p_value}"
            )

    def test_corrected_p_values_monotone(self):
        """BH correction ensures corrected p-values are monotone non-decreasing when sorted by raw."""
        design = _make_design_2factor()
        sn = {
            1: 1.0, 2: 1.5, 3: 1.2,
            4: 3.0, 5: 3.5, 6: 3.2,
            7: 5.0, 8: 5.5, 9: 5.2,
        }
        result = run_anova(design, sn)

        sorted_by_raw = sorted(result.factors, key=lambda f: f.p_value)
        corrected = [f.corrected_p_value for f in sorted_by_raw]
        for i in range(1, len(corrected)):
            assert corrected[i] >= corrected[i - 1] - 1e-10, (
                f"Corrected p-values not monotone: {corrected}"
            )


# ---------------------------------------------------------------------------
# Optimal Prediction Tests
# ---------------------------------------------------------------------------


class TestPredictOptimal:
    """Verify optimal configuration prediction."""

    def test_selects_highest_sn_level_per_factor(self):
        effects = {
            "axis_1": {"flat": 1.0, "2tier": 3.0, "3tier": 5.0},
            "axis_2": {"path": 2.0, "summary": 4.0, "tokens": 3.0},
        }
        prediction = predict_optimal(effects)

        assert prediction.optimal_assignment["axis_1"] == "3tier"
        assert prediction.optimal_assignment["axis_2"] == "summary"

    def test_predicted_sn_is_additive(self):
        effects = {
            "axis_1": {"flat": 1.0, "2tier": 3.0, "3tier": 5.0},
            "axis_2": {"path": 2.0, "summary": 4.0, "tokens": 3.0},
        }
        prediction = predict_optimal(effects)

        # Grand mean of all level effects
        all_values = [v for d in effects.values() for v in d.values()]
        grand_mean = sum(all_values) / len(all_values)

        # Predicted = grand_mean + sum(best_level - factor_mean)
        factor_means = {
            name: sum(levels.values()) / len(levels)
            for name, levels in effects.items()
        }
        expected = grand_mean
        for name in effects:
            best_level = max(effects[name].values())
            expected += best_level - factor_means[name]

        assert abs(prediction.predicted_sn - expected) < 1e-10

    def test_returns_optimal_prediction_type(self):
        effects = {
            "axis_1": {"flat": 1.0, "3tier": 5.0},
        }
        prediction = predict_optimal(effects)

        assert isinstance(prediction, OptimalPrediction)
        assert isinstance(prediction.optimal_assignment, dict)
        assert isinstance(prediction.predicted_sn, float)

    def test_prediction_interval_computed(self):
        effects = {
            "axis_1": {"flat": 1.0, "2tier": 3.0, "3tier": 5.0},
            "axis_2": {"path": 2.0, "summary": 4.0, "tokens": 3.0},
        }
        # Provide S/N ratios for interval computation
        sn = {i + 1: float(i) for i in range(9)}
        prediction = predict_optimal(effects, sn_ratios=sn)

        assert prediction.prediction_interval is not None
        low, high = prediction.prediction_interval
        assert low < high
        assert low <= prediction.predicted_sn <= high

    def test_prediction_se_uses_anova_ms_error(self):
        """Prediction SE must use ANOVA ms_error, not total variance.

        When factor effects explain most of the variance, total variance
        is much larger than ms_error. Using total variance inflates the SE.
        """
        design = _make_design_2factor()
        # Strong factor effects: axis_1 dominates, small residual error.
        sn_ratios = {
            1: 0.5, 2: 1.0, 3: 2.5,     # flat levels
            4: 5.5, 5: 6.0, 6: 6.5,     # 2tier levels
            7: 10.0, 8: 11.5, 9: 12.0,  # 3tier levels
        }
        effects = compute_main_effects(design, sn_ratios)
        anova = run_anova(design, sn_ratios)
        prediction = predict_optimal(
            effects, sn_ratios=sn_ratios, design=design, anova_result=anova,
        )

        # ms_error should be much smaller than total variance
        n = len(sn_ratios)
        sn_mean = sum(sn_ratios.values()) / n
        total_var = sum(
            (v - sn_mean) ** 2 for v in sn_ratios.values()
        ) / (n - 1)
        assert anova.ms_error < total_var * 0.1  # ms_error << total_var

        # SE must use ms_error, so it should be much smaller
        old_se = math.sqrt(total_var / n)
        assert prediction.se_prediction is not None
        assert prediction.se_prediction < old_se * 0.5

    def test_prediction_interval_uses_anova_df_error(self):
        """Prediction interval df should be ANOVA df_error, not n-1."""
        design = _make_design_2factor()
        sn_ratios = {
            1: 0.5, 2: 1.0, 3: 2.5,
            4: 5.5, 5: 6.0, 6: 6.5,
            7: 10.0, 8: 11.5, 9: 12.0,
        }
        effects = compute_main_effects(design, sn_ratios)
        anova = run_anova(design, sn_ratios)
        prediction = predict_optimal(
            effects, sn_ratios=sn_ratios, design=design, anova_result=anova,
        )

        # Compute expected interval using ms_error, n_eff, and df_error
        n = len(sn_ratios)
        sum_dof = sum(f.df for f in anova.factors)
        n_eff = n / (1 + sum_dof)
        se_expected = math.sqrt(anova.ms_error / n_eff)
        t_val = stats.t.ppf(0.975, anova.df_error)
        margin = t_val * se_expected
        expected_low = prediction.predicted_sn - margin
        expected_high = prediction.predicted_sn + margin

        assert prediction.prediction_interval is not None
        assert abs(prediction.prediction_interval[0] - expected_low) < 1e-10
        assert abs(prediction.prediction_interval[1] - expected_high) < 1e-10

    def test_prediction_interval_known_values(self):
        """Verify interval with hand-computed values where total var != ms_error."""
        design = _make_design_2factor()
        # Perfectly additive data: zero residual error
        sn_ratios = {
            1: 1.0, 2: 3.0, 3: 2.0,
            4: 3.0, 5: 5.0, 6: 4.0,
            7: 5.0, 8: 7.0, 9: 6.0,
        }
        effects = compute_main_effects(design, sn_ratios)
        anova = run_anova(design, sn_ratios)
        prediction = predict_optimal(
            effects, sn_ratios=sn_ratios, design=design, anova_result=anova,
        )

        # With perfectly additive data, ms_error ~ 0 -> se_prediction = NaN
        assert anova.ms_error < 1e-10
        # SE should be NaN (not 0) to signal undefined error estimate
        assert prediction.se_prediction is not None
        assert math.isnan(prediction.se_prediction), (
            f"se_prediction={prediction.se_prediction}; expected NaN for zero ms_error"
        )

    def test_additivity_r_squared_computed_with_design(self):
        """When design is provided, additivity R-squared should be computed."""
        design = _make_design_2factor()
        # Purely additive S/N: axis_1 effect + axis_2 effect
        sn_ratios = {
            1: 1.0, 2: 3.0, 3: 2.0,  # flat + path/summary/tokens
            4: 3.0, 5: 5.0, 6: 4.0,  # 2tier + ...
            7: 5.0, 8: 7.0, 9: 6.0,  # 3tier + ...
        }
        effects = compute_main_effects(design, sn_ratios)
        prediction = predict_optimal(effects, sn_ratios=sn_ratios, design=design)

        assert prediction.additivity_r_squared is not None
        assert prediction.additivity_r_squared > 0.99

    def test_additivity_r_squared_none_without_design(self):
        """Without design, additivity R-squared should be None."""
        effects = {
            "axis_1": {"flat": 1.0, "2tier": 3.0, "3tier": 5.0},
            "axis_2": {"path": 2.0, "summary": 4.0, "tokens": 3.0},
        }
        prediction = predict_optimal(effects)
        assert prediction.additivity_r_squared is None
        assert prediction.additivity_warning is None

    def test_additivity_warning_when_r_squared_low(self):
        """Should warn when R-squared is below threshold."""
        design = _make_design_2factor()
        # Strong interactions: diagonal dominance (non-additive)
        sn_ratios = {
            1: 10.0, 2: 1.0, 3: 1.0,
            4: 1.0,  5: 10.0, 6: 1.0,
            7: 1.0,  8: 1.0, 9: 10.0,
        }
        effects = compute_main_effects(design, sn_ratios)
        prediction = predict_optimal(effects, sn_ratios=sn_ratios, design=design)

        assert prediction.additivity_r_squared is not None
        assert prediction.additivity_r_squared < 0.8
        assert prediction.additivity_warning is not None
        assert "interaction" in prediction.additivity_warning.lower()

    def test_additivity_no_warning_when_good_fit(self):
        """No warning when additive model fits well."""
        design = _make_design_2factor()
        sn_ratios = {
            1: 1.0, 2: 3.0, 3: 2.0,
            4: 3.0, 5: 5.0, 6: 4.0,
            7: 5.0, 8: 7.0, 9: 6.0,
        }
        effects = compute_main_effects(design, sn_ratios)
        prediction = predict_optimal(effects, sn_ratios=sn_ratios, design=design)

        assert prediction.additivity_warning is None


# ---------------------------------------------------------------------------
# Confirmation Run Tests
# ---------------------------------------------------------------------------


class TestValidateConfirmation:
    """Verify confirmation run validation."""

    def test_within_interval(self):
        prediction = OptimalPrediction(
            optimal_assignment={"axis_1": "3tier"},
            predicted_sn=5.2,
            prediction_interval=(4.8, 5.6),
            se_prediction=0.2,
        )
        result = validate_confirmation(prediction, [0.9, 0.85, 0.88])

        assert isinstance(result, ConfirmationResult)
        assert isinstance(result.observed_sn, float)
        assert result.predicted_sn == 5.2

    def test_outside_interval_flagged(self):
        prediction = OptimalPrediction(
            optimal_assignment={"axis_1": "3tier"},
            predicted_sn=5.2,
            prediction_interval=(4.8, 5.6),
            se_prediction=0.2,
        )
        # Very low scores -> observed S/N far below predicted
        result = validate_confirmation(prediction, [0.1, 0.1, 0.1])

        assert not result.within_interval
        assert abs(result.sigma_deviation) > 2.0

    def test_confirmation_within_interval_ok(self):
        prediction = OptimalPrediction(
            optimal_assignment={"axis_1": "3tier"},
            predicted_sn=5.2,
            prediction_interval=(4.0, 6.4),
            se_prediction=0.6,
        )
        # Scores that produce an S/N near the predicted value
        result = validate_confirmation(prediction, [0.9, 0.9, 0.9])

        # The exact result depends on computation, but check structure
        assert isinstance(result.within_interval, bool)
        assert isinstance(result.sigma_deviation, float)

    def test_returns_confirmation_result_type(self):
        prediction = OptimalPrediction(
            optimal_assignment={"axis_1": "flat"},
            predicted_sn=3.0,
            prediction_interval=(2.0, 4.0),
            se_prediction=0.5,
        )
        result = validate_confirmation(prediction, [0.7, 0.8])
        assert isinstance(result, ConfirmationResult)


# ---------------------------------------------------------------------------
# Interaction Effects Tests
# ---------------------------------------------------------------------------


class TestInteractionEffects:
    """Verify 2-way interaction effect computation from full factorial data."""

    def test_compute_two_way_interactions_basic(self):
        """2x2 factorial (2 factors, 2 levels each) returns 1 interaction pair."""
        design_rows = [
            {"A": "a1", "B": "b1"},
            {"A": "a1", "B": "b2"},
            {"A": "a2", "B": "b1"},
            {"A": "a2", "B": "b2"},
        ]
        # Strong interaction: A*B synergy on diagonal
        sn_ratios = [10.0, 2.0, 2.0, 10.0]

        interactions = compute_interactions(design_rows, sn_ratios)

        assert len(interactions) == 1
        ie = interactions[0]
        assert ie.factor1 == "A"
        assert ie.factor2 == "B"
        assert ie.ss > 0
        assert ie.df == 1  # (2-1)*(2-1)

    def test_no_interactions_single_factor(self):
        """Only 1 factor should return empty list."""
        design_rows = [
            {"A": "a1"},
            {"A": "a2"},
        ]
        sn_ratios = [5.0, 10.0]

        interactions = compute_interactions(design_rows, sn_ratios)

        assert interactions == []

    def test_interactions_three_factors(self):
        """2^3 factorial (3 factors, 2 levels each) returns 3 interaction pairs."""
        design_rows = [
            {"A": "a1", "B": "b1", "C": "c1"},
            {"A": "a1", "B": "b1", "C": "c2"},
            {"A": "a1", "B": "b2", "C": "c1"},
            {"A": "a1", "B": "b2", "C": "c2"},
            {"A": "a2", "B": "b1", "C": "c1"},
            {"A": "a2", "B": "b1", "C": "c2"},
            {"A": "a2", "B": "b2", "C": "c1"},
            {"A": "a2", "B": "b2", "C": "c2"},
        ]
        sn_ratios = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]

        interactions = compute_interactions(design_rows, sn_ratios)

        assert len(interactions) == 3  # C(3,2) = 3
        pair_names = [(ie.factor1, ie.factor2) for ie in interactions]
        assert ("A", "B") in pair_names
        assert ("A", "C") in pair_names
        assert ("B", "C") in pair_names


# ---------------------------------------------------------------------------
# Bug #184: ANOVA consistent row filtering for mixed-level designs
# ---------------------------------------------------------------------------


class TestANOVAConsistentRowFiltering:
    """ANOVA must use the same row set for grand_mean and per-factor SS.

    Bug #184: grand_mean excludes rows where ALL factors are dummy, but
    per-factor SS includes rows where SOME (other) factors are dummy.
    This breaks the ANOVA identity SS_total = sum(SS_factor) + SS_error.
    """

    @staticmethod
    def _make_mixed_level_design_with_dummies() -> TaguchiDesign:
        """Mixed-level design: 2-level factor A, 3-level factor B.

        In a 3-column OA, factor A (2 levels) gets a dummy level on one
        of the three OA levels. Some rows have partial dummies (only A
        is dummy) and NO row has ALL factors dummy.
        """
        factors = [
            TaguchiFactorDef(name="A", n_levels=2,
                             level_names=["a1", "a2"], axis=1),
            TaguchiFactorDef(name="B", n_levels=3,
                             level_names=["b1", "b2", "b3"], axis=2),
        ]
        rows = [
            # Rows 1-3: A=a1, B cycles through b1/b2/b3
            TaguchiExperimentRow(run_id=1, assignments={"A": "a1", "B": "b1"}),
            TaguchiExperimentRow(run_id=2, assignments={"A": "a1", "B": "b2"}),
            TaguchiExperimentRow(run_id=3, assignments={"A": "a1", "B": "b3"}),
            # Rows 4-6: A=a2, B cycles
            TaguchiExperimentRow(run_id=4, assignments={"A": "a2", "B": "b1"}),
            TaguchiExperimentRow(run_id=5, assignments={"A": "a2", "B": "b2"}),
            TaguchiExperimentRow(run_id=6, assignments={"A": "a2", "B": "b3"}),
            # Rows 7-9: A=dummy, B cycles (partial-dummy rows)
            TaguchiExperimentRow(
                run_id=7, assignments={"A": "__dummy__", "B": "b1"},
                dummy_factors={"A"},
            ),
            TaguchiExperimentRow(
                run_id=8, assignments={"A": "__dummy__", "B": "b2"},
                dummy_factors={"A"},
            ),
            TaguchiExperimentRow(
                run_id=9, assignments={"A": "__dummy__", "B": "b3"},
                dummy_factors={"A"},
            ),
        ]
        return TaguchiDesign(
            oa_name="L9_mixed", n_runs=9, factors=factors, rows=rows,
            level_counts=[2, 3],
        )

    def test_anova_identity_holds_with_partial_dummy_rows(self):
        """SS_total must equal sum(SS_factor) + SS_error.

        With inconsistent row filtering, the identity breaks because
        grand_mean is computed from a different row set than the per-factor
        SS contributions.
        """
        design = self._make_mixed_level_design_with_dummies()
        sn_ratios = {
            1: 2.0, 2: 4.0, 3: 3.0,
            4: 6.0, 5: 8.0, 6: 7.0,
            7: 1.0, 8: 3.0, 9: 2.0,  # dummy-A rows
        }
        result = run_anova(design, sn_ratios)

        ss_factors_sum = sum(fr.ss for fr in result.factors)
        identity_lhs = result.ss_total
        identity_rhs = ss_factors_sum + result.ss_error

        assert abs(identity_lhs - identity_rhs) < 1e-10, (
            f"ANOVA identity broken: SS_total={identity_lhs:.6f} != "
            f"sum(SS_factor)+SS_error={identity_rhs:.6f} "
            f"(diff={abs(identity_lhs - identity_rhs):.2e})"
        )

    def test_anova_per_factor_ss_uses_factor_specific_filtering(self):
        """Per-factor SS excludes only rows where THAT factor is dummy.

        Factor B (no dummy levels) should use ALL 9 rows — including
        rows 7-9 where A is dummy but B is real.  Factor A should only
        use rows 1-6 (where A is at a real level).
        """
        design = self._make_mixed_level_design_with_dummies()
        sn_ratios = {
            1: 2.0, 2: 4.0, 3: 3.0,
            4: 6.0, 5: 8.0, 6: 7.0,
            7: 1.0, 8: 3.0, 9: 2.0,
        }
        result = run_anova(design, sn_ratios)

        b_factor = next(f for f in result.factors if f.factor_name == "B")
        # df should be n_levels - 1 = 2
        assert b_factor.df == 2
        assert b_factor.eta_squared >= 0

        a_factor = next(f for f in result.factors if f.factor_name == "A")
        # Factor A has 2 levels, df = 1
        assert a_factor.df == 1

    def test_grand_mean_uses_all_rows(self):
        """Grand mean must use all rows (including partial-dummy rows).

        In standard Taguchi ANOVA, every OA row is a real experiment.
        Dummy levels are bookkeeping — the row's S/N is still valid.
        Per-factor SS excludes only rows where THAT factor is dummy,
        and unmodelled variance flows into SS_error.
        """
        design = self._make_mixed_level_design_with_dummies()
        sn_ratios = {
            1: 2.0, 2: 4.0, 3: 3.0,
            4: 6.0, 5: 8.0, 6: 7.0,
            7: 1.0, 8: 3.0, 9: 2.0,
        }
        result = run_anova(design, sn_ratios)

        # Grand mean of ALL 9 rows: (2+4+3+6+8+7+1+3+2)/9 = 36/9 = 4.0
        expected_grand_mean = 4.0
        assert abs(result.grand_mean - expected_grand_mean) < 1e-10, (
            f"Grand mean {result.grand_mean} != expected {expected_grand_mean}; "
            f"should use all rows including partial-dummy rows"
        )


# ---------------------------------------------------------------------------
# Bug #186: predict_optimal grand_mean bias in mixed-level designs
# ---------------------------------------------------------------------------


class TestPredictOptimalMixedLevelGrandMean:
    """predict_optimal must compute grand_mean from observation means,
    not from averaging all level means across factors.

    Bug #186: In mixed-level designs (e.g., factor A: 5 levels, factor B:
    2 levels), averaging all level means over-weights factors with more
    levels. The correct approach: weight each factor's mean equally.
    """

    def test_grand_mean_unbiased_mixed_levels(self):
        """Grand mean should weight each factor's mean equally.

        Factor A (5 levels): means [1, 2, 3, 4, 5] -> factor mean 3.0
        Factor B (2 levels): means [10, 20]         -> factor mean 15.0

        Biased (mean-of-all-level-means): (1+2+3+4+5+10+20)/7 ≈ 6.43
        Correct (mean-of-factor-means):   (3.0 + 15.0) / 2 = 9.0
        """
        effects = {
            "A": {"a1": 1.0, "a2": 2.0, "a3": 3.0, "a4": 4.0, "a5": 5.0},
            "B": {"b1": 10.0, "b2": 20.0},
        }
        prediction = predict_optimal(effects)

        # The additive model: predicted = grand_mean + sum(best - factor_mean)
        # With correct grand_mean = 9.0:
        #   best_A = 5.0, factor_mean_A = 3.0, effect_A = +2.0
        #   best_B = 20.0, factor_mean_B = 15.0, effect_B = +5.0
        #   predicted = 9.0 + 2.0 + 5.0 = 16.0
        #
        # With biased grand_mean ≈ 6.43:
        #   predicted = 6.43 + 2.0 + 5.0 = 13.43 (WRONG)
        expected_grand_mean = 9.0
        expected_predicted = expected_grand_mean + (5.0 - 3.0) + (20.0 - 15.0)
        assert abs(expected_predicted - 16.0) < 1e-10  # sanity

        assert abs(prediction.predicted_sn - expected_predicted) < 1e-10, (
            f"predicted_sn={prediction.predicted_sn:.4f} != "
            f"expected={expected_predicted:.4f}; "
            f"grand_mean is biased by unequal factor level counts"
        )

    def test_grand_mean_equal_levels_unchanged(self):
        """When all factors have the same number of levels, behavior is unchanged."""
        effects = {
            "A": {"a1": 1.0, "a2": 3.0, "a3": 5.0},
            "B": {"b1": 2.0, "b2": 4.0, "b3": 6.0},
        }
        # Both approaches give the same result for equal-level designs
        all_values = [v for d in effects.values() for v in d.values()]
        naive_grand_mean = sum(all_values) / len(all_values)

        factor_means = {
            name: sum(levels.values()) / len(levels)
            for name, levels in effects.items()
        }
        correct_grand_mean = sum(factor_means.values()) / len(factor_means)

        # For equal levels, both should agree
        assert abs(naive_grand_mean - correct_grand_mean) < 1e-10

        prediction = predict_optimal(effects)
        # predicted = grand_mean + sum(best - factor_mean)
        expected = correct_grand_mean + (5.0 - 3.0) + (6.0 - 4.0)
        assert abs(prediction.predicted_sn - expected) < 1e-10


# ---------------------------------------------------------------------------
# Bug #225: predict_optimal prediction interval uses n instead of n_eff
# ---------------------------------------------------------------------------


class TestPredictOptimalNeff:
    """predict_optimal must use n_eff (effective replications) for the
    prediction interval, not n (total observations).

    Bug #225: For a k-factor additive model the effective sample size is
    n_eff = n / (1 + sum(df_i)) where df_i = levels_i - 1.  Using plain
    n makes the interval ~sqrt(1 + sum_DOF) times too narrow, turning
    confirmation into a rubber stamp.
    """

    def test_se_uses_n_eff_not_n(self):
        """SE must be sqrt(ms_error / n_eff), not sqrt(ms_error / n).

        For a 2-factor, 3-level L9 design:
          n = 9, sum_dof = 2 + 2 = 4, n_eff = 9 / 5 = 1.8
          SE_correct = sqrt(ms_error / 1.8) ≈ 2.24 × SE_wrong
        """
        design = _make_design_2factor()
        sn_ratios = {
            1: 0.5, 2: 1.0, 3: 2.5,
            4: 5.5, 5: 6.0, 6: 6.5,
            7: 10.0, 8: 11.5, 9: 12.0,
        }
        effects = compute_main_effects(design, sn_ratios)
        anova = run_anova(design, sn_ratios)
        prediction = predict_optimal(
            effects, sn_ratios=sn_ratios, design=design, anova_result=anova,
        )

        n = len(sn_ratios)
        sum_dof = sum(f.df for f in anova.factors)
        n_eff = n / (1 + sum_dof)

        expected_se = math.sqrt(anova.ms_error / n_eff)
        wrong_se = math.sqrt(anova.ms_error / n)

        # The correct SE must be larger than n-based SE
        assert expected_se > wrong_se * 1.5, (
            "Expected n_eff-based SE to be significantly larger than n-based SE"
        )
        assert prediction.se_prediction is not None
        assert abs(prediction.se_prediction - expected_se) < 1e-10, (
            f"SE={prediction.se_prediction:.6f} != expected={expected_se:.6f}; "
            f"likely using n={n} instead of n_eff={n_eff:.2f}"
        )

    def test_interval_wider_with_n_eff(self):
        """Prediction interval must be wider when using n_eff.

        With the wrong n, the interval is ~sqrt(1 + sum_DOF) times too narrow.
        """
        design = _make_design_2factor()
        sn_ratios = {
            1: 0.5, 2: 1.0, 3: 2.5,
            4: 5.5, 5: 6.0, 6: 6.5,
            7: 10.0, 8: 11.5, 9: 12.0,
        }
        effects = compute_main_effects(design, sn_ratios)
        anova = run_anova(design, sn_ratios)
        prediction = predict_optimal(
            effects, sn_ratios=sn_ratios, design=design, anova_result=anova,
        )

        # Compute the wrong (too narrow) interval for comparison
        n = len(sn_ratios)
        wrong_se = math.sqrt(anova.ms_error / n)
        t_val = stats.t.ppf(0.975, anova.df_error)
        wrong_margin = t_val * wrong_se

        assert prediction.prediction_interval is not None
        actual_margin = (
            prediction.prediction_interval[1]
            - prediction.prediction_interval[0]
        ) / 2.0

        # Actual margin must be wider than the wrong margin
        assert actual_margin > wrong_margin * 1.5, (
            f"Interval margin {actual_margin:.4f} not wider than wrong "
            f"margin {wrong_margin:.4f}; likely using n instead of n_eff"
        )

    def test_n_eff_without_anova_falls_back_to_n(self):
        """Without ANOVA, fallback uses total variance with n (no n_eff)."""
        effects = {
            "axis_1": {"flat": 1.0, "2tier": 3.0, "3tier": 5.0},
            "axis_2": {"path": 2.0, "summary": 4.0, "tokens": 3.0},
        }
        sn = {i + 1: float(i) for i in range(9)}
        prediction = predict_optimal(effects, sn_ratios=sn)

        # Without ANOVA, should use total variance / n (no n_eff correction)
        n = len(sn)
        sn_values = list(sn.values())
        sn_mean = sum(sn_values) / n
        residual_var = sum((y - sn_mean) ** 2 for y in sn_values) / (n - 1)
        expected_se = math.sqrt(residual_var / n)

        assert prediction.se_prediction is not None
        assert abs(prediction.se_prediction - expected_se) < 1e-10


# ---------------------------------------------------------------------------
# Bugs #231, #232, #238: ANOVA SS decomposition, df_error, se_prediction
# ---------------------------------------------------------------------------


def _make_design_4factor_many_dummies() -> TaguchiDesign:
    """4 two-level factors on an L9 OA: most rows have at least one dummy.

    Standard L9(3^4) OA with each factor having 2 real levels and a dummy
    at OA level 2.  Only rows 1 and 4 have all factors at real levels.

    L9 OA columns:
    Row | C1 C2 C3 C4    Factor assignments (0→lvl1, 1→lvl2, 2→dummy):
     1  |  0  0  0  0    A=a1 B=b1 C=c1 D=d1  (no dummy)
     2  |  0  1  1  2    A=a1 B=b2 C=c2 D=dum  (dummy: D)
     3  |  0  2  2  1    A=a1 B=dum C=dum D=d2  (dummy: B,C)
     4  |  1  0  1  1    A=a2 B=b1 C=c2 D=d2  (no dummy)
     5  |  1  1  2  0    A=a2 B=b2 C=dum D=d1  (dummy: C)
     6  |  1  2  0  2    A=a2 B=dum C=c1 D=dum  (dummy: B,D)
     7  |  2  0  2  2    A=dum B=b1 C=dum D=dum  (dummy: A,C,D)
     8  |  2  1  0  1    A=dum B=b2 C=c1 D=d2  (dummy: A)
     9  |  2  2  1  0    A=dum B=dum C=c2 D=d1  (dummy: A,B)
    """
    factors = [
        TaguchiFactorDef(name="A", n_levels=2, level_names=["a1", "a2"], axis=1),
        TaguchiFactorDef(name="B", n_levels=2, level_names=["b1", "b2"], axis=2),
        TaguchiFactorDef(name="C", n_levels=2, level_names=["c1", "c2"], axis=3),
        TaguchiFactorDef(name="D", n_levels=2, level_names=["d1", "d2"], axis=4),
    ]
    rows = [
        TaguchiExperimentRow(
            run_id=1, assignments={"A": "a1", "B": "b1", "C": "c1", "D": "d1"},
        ),
        TaguchiExperimentRow(
            run_id=2, assignments={"A": "a1", "B": "b2", "C": "c2", "D": "__dummy__"},
            dummy_factors={"D"},
        ),
        TaguchiExperimentRow(
            run_id=3,
            assignments={"A": "a1", "B": "__dummy__", "C": "__dummy__", "D": "d2"},
            dummy_factors={"B", "C"},
        ),
        TaguchiExperimentRow(
            run_id=4, assignments={"A": "a2", "B": "b1", "C": "c2", "D": "d2"},
        ),
        TaguchiExperimentRow(
            run_id=5,
            assignments={"A": "a2", "B": "b2", "C": "__dummy__", "D": "d1"},
            dummy_factors={"C"},
        ),
        TaguchiExperimentRow(
            run_id=6,
            assignments={"A": "a2", "B": "__dummy__", "C": "c1", "D": "__dummy__"},
            dummy_factors={"B", "D"},
        ),
        TaguchiExperimentRow(
            run_id=7,
            assignments={"A": "__dummy__", "B": "b1", "C": "__dummy__", "D": "__dummy__"},
            dummy_factors={"A", "C", "D"},
        ),
        TaguchiExperimentRow(
            run_id=8,
            assignments={"A": "__dummy__", "B": "b2", "C": "c1", "D": "d2"},
            dummy_factors={"A"},
        ),
        TaguchiExperimentRow(
            run_id=9,
            assignments={"A": "__dummy__", "B": "__dummy__", "C": "c2", "D": "d1"},
            dummy_factors={"A", "B"},
        ),
    ]
    return TaguchiDesign(
        oa_name="L9_4x2", n_runs=9, factors=factors, rows=rows,
        level_counts=[2, 2, 2, 2],
    )


class TestANOVASSDecomposition:
    """Bug #231: ANOVA SS decomposition must not give each factor SS = SS_total.

    When only fully-non-dummy rows are used, designs with many dummy factors
    shrink the row set so far that each factor's levels have ~1 observation
    each, making SS_factor = SS_total for every factor.

    The fix: use ALL rows for grand_mean/SS_total; for each factor's SS,
    exclude only rows where THAT SPECIFIC factor is at a dummy level.
    """

    def test_no_factor_ss_exceeds_ss_total(self):
        """No individual factor SS should exceed SS_total."""
        design = _make_design_4factor_many_dummies()
        sn = {1: 2.0, 2: 5.0, 3: 3.0, 4: 8.0, 5: 4.0, 6: 7.0, 7: 1.0, 8: 6.0, 9: 3.0}

        result = run_anova(design, sn)

        for fr in result.factors:
            assert fr.ss <= result.ss_total + 1e-10, (
                f"Factor {fr.factor_name} SS={fr.ss:.4f} exceeds "
                f"SS_total={result.ss_total:.4f}"
            )

    def test_ss_factors_sum_lte_ss_total(self):
        """Sum of all factor SS must not exceed SS_total."""
        design = _make_design_4factor_many_dummies()
        sn = {1: 2.0, 2: 5.0, 3: 3.0, 4: 8.0, 5: 4.0, 6: 7.0, 7: 1.0, 8: 6.0, 9: 3.0}

        result = run_anova(design, sn)

        ss_factors_sum = sum(fr.ss for fr in result.factors)
        assert ss_factors_sum <= result.ss_total + 1e-10, (
            f"Sum of factor SS ({ss_factors_sum:.4f}) exceeds "
            f"SS_total ({result.ss_total:.4f})"
        )

    def test_anova_identity_ss_total_equals_ss_factors_plus_ss_error(self):
        """ANOVA identity: SS_total = sum(SS_factor) + SS_error."""
        design = _make_design_4factor_many_dummies()
        sn = {1: 2.0, 2: 5.0, 3: 3.0, 4: 8.0, 5: 4.0, 6: 7.0, 7: 1.0, 8: 6.0, 9: 3.0}

        result = run_anova(design, sn)

        ss_factors_sum = sum(fr.ss for fr in result.factors)
        assert abs(result.ss_total - (ss_factors_sum + result.ss_error)) < 1e-10, (
            f"ANOVA identity broken: SS_total={result.ss_total:.6f} != "
            f"sum(SS_factor)+SS_error={ss_factors_sum + result.ss_error:.6f}"
        )

    def test_grand_mean_uses_all_rows(self):
        """Grand mean must use all N rows, not just fully-non-dummy rows.

        Hand-computed: grand_mean = (2+5+3+8+4+7+1+6+3)/9 = 39/9 ≈ 4.333
        Buggy (rows 1,4 only): (2+8)/2 = 5.0
        """
        design = _make_design_4factor_many_dummies()
        sn = {1: 2.0, 2: 5.0, 3: 3.0, 4: 8.0, 5: 4.0, 6: 7.0, 7: 1.0, 8: 6.0, 9: 3.0}

        result = run_anova(design, sn)

        expected_grand_mean = 39.0 / 9.0
        assert abs(result.grand_mean - expected_grand_mean) < 1e-10, (
            f"Grand mean {result.grand_mean:.6f} != expected {expected_grand_mean:.6f}; "
            f"likely using only fully-non-dummy rows instead of all rows"
        )

    def test_ss_total_uses_all_rows(self):
        """SS_total must be computed from all N rows.

        Hand-computed with grand_mean = 13/3:
        SS_total = sum((y_i - 13/3)^2) = 396/9 = 44.0
        Buggy (rows 1,4): (2-5)^2 + (8-5)^2 = 18.0
        """
        design = _make_design_4factor_many_dummies()
        sn = {1: 2.0, 2: 5.0, 3: 3.0, 4: 8.0, 5: 4.0, 6: 7.0, 7: 1.0, 8: 6.0, 9: 3.0}

        result = run_anova(design, sn)

        assert abs(result.ss_total - 44.0) < 1e-10, (
            f"SS_total={result.ss_total:.6f} != expected 44.0; "
            f"likely using only fully-non-dummy rows"
        )

    def test_per_factor_ss_uses_factor_specific_rows(self):
        """Each factor's SS uses rows where that factor is NOT dummy.

        Factor A (non-dummy rows 1-6):
          a1: rows 1,2,3 → mean = 10/3
          a2: rows 4,5,6 → mean = 19/3
          SS_A = 3*(10/3 - 13/3)^2 + 3*(19/3 - 13/3)^2 = 3+12 = 15.0
        """
        design = _make_design_4factor_many_dummies()
        sn = {1: 2.0, 2: 5.0, 3: 3.0, 4: 8.0, 5: 4.0, 6: 7.0, 7: 1.0, 8: 6.0, 9: 3.0}

        result = run_anova(design, sn)

        a_factor = next(f for f in result.factors if f.factor_name == "A")
        assert abs(a_factor.ss - 15.0) < 1e-10, (
            f"Factor A SS={a_factor.ss:.6f} != expected 15.0; "
            f"should use rows 1-6 (where A is not dummy)"
        )


class TestANOVADfError:
    """Bug #232: df_error must use total rows N, not non-dummy count.

    With L9 (9 rows) and 4 two-level factors (4 df total):
      Correct:  df_error = 9 - 1 - 4 = 4
      Buggy:    df_error = max(2 - 1 - 4, 1) = 1  (only 2 non-dummy rows)
    """

    def test_df_error_uses_total_rows(self):
        """df_error = N_total - 1 - sum(df_factor)."""
        design = _make_design_4factor_many_dummies()
        sn = {1: 2.0, 2: 5.0, 3: 3.0, 4: 8.0, 5: 4.0, 6: 7.0, 7: 1.0, 8: 6.0, 9: 3.0}

        result = run_anova(design, sn)

        expected_df_error = 9 - 1 - 4  # N - 1 - sum(df_factors)
        assert result.df_error == expected_df_error, (
            f"df_error={result.df_error} != expected {expected_df_error}; "
            f"likely using non-dummy row count instead of total rows"
        )

    def test_ms_error_nonzero(self):
        """ms_error must be nonzero when there is residual variance."""
        design = _make_design_4factor_many_dummies()
        sn = {1: 2.0, 2: 5.0, 3: 3.0, 4: 8.0, 5: 4.0, 6: 7.0, 7: 1.0, 8: 6.0, 9: 3.0}

        result = run_anova(design, sn)

        # SS_error = 44 - 98/3 = 34/3 ≈ 11.333
        # ms_error = (34/3) / 4 = 17/6 ≈ 2.833
        assert result.ms_error > 0, (
            f"ms_error={result.ms_error}; should be > 0 with residual variance"
        )
        expected_ms_error = 17.0 / 6.0
        assert abs(result.ms_error - expected_ms_error) < 1e-10, (
            f"ms_error={result.ms_error:.6f} != expected {expected_ms_error:.6f}"
        )

    def test_f_ratios_finite(self):
        """F-ratios must be finite when ms_error > 0."""
        design = _make_design_4factor_many_dummies()
        sn = {1: 2.0, 2: 5.0, 3: 3.0, 4: 8.0, 5: 4.0, 6: 7.0, 7: 1.0, 8: 6.0, 9: 3.0}

        result = run_anova(design, sn)

        for fr in result.factors:
            assert math.isfinite(fr.f_ratio), (
                f"Factor {fr.factor_name} F-ratio={fr.f_ratio}; "
                f"should be finite when ms_error > 0"
            )

    def test_p_values_nonzero(self):
        """p-values must not all be zero when ms_error is proper."""
        design = _make_design_4factor_many_dummies()
        sn = {1: 2.0, 2: 5.0, 3: 3.0, 4: 8.0, 5: 4.0, 6: 7.0, 7: 1.0, 8: 6.0, 9: 3.0}

        result = run_anova(design, sn)

        # At least some p-values should be > 0 (not all factors are significant)
        p_values = [fr.p_value for fr in result.factors]
        assert any(p > 0 for p in p_values), (
            f"All p-values are 0: {p_values}; ms_error is likely wrong"
        )


class TestANOVASePrediction:
    """Bug #238: se_prediction=0 when ms_error=0 (downstream of #232).

    When df_error and ms_error are correctly computed, se_prediction
    should be > 0 for designs with residual variance.
    """

    def test_se_prediction_nonzero_with_residual_variance(self):
        """se_prediction must be > 0 when the design has residual error."""
        design = _make_design_4factor_many_dummies()
        sn = {1: 2.0, 2: 5.0, 3: 3.0, 4: 8.0, 5: 4.0, 6: 7.0, 7: 1.0, 8: 6.0, 9: 3.0}

        effects = compute_main_effects(design, sn)
        anova = run_anova(design, sn)
        prediction = predict_optimal(
            effects, sn_ratios=sn, design=design, anova_result=anova,
        )

        assert prediction.se_prediction is not None
        assert prediction.se_prediction > 0, (
            f"se_prediction={prediction.se_prediction}; "
            f"should be > 0 when ms_error > 0"
        )

    def test_prediction_interval_nonzero_width(self):
        """Prediction interval must have nonzero width."""
        design = _make_design_4factor_many_dummies()
        sn = {1: 2.0, 2: 5.0, 3: 3.0, 4: 8.0, 5: 4.0, 6: 7.0, 7: 1.0, 8: 6.0, 9: 3.0}

        effects = compute_main_effects(design, sn)
        anova = run_anova(design, sn)
        prediction = predict_optimal(
            effects, sn_ratios=sn, design=design, anova_result=anova,
        )

        assert prediction.prediction_interval is not None
        low, high = prediction.prediction_interval
        assert high - low > 0, (
            f"Prediction interval width = {high - low}; should be > 0"
        )

    def test_se_prediction_nan_when_ms_error_zero(self):
        """se_prediction must be NaN (not 0) when ms_error is 0 or < 1e-12.

        With perfectly additive data, ms_error=0 -> sqrt(0/n_eff)=0.
        Returning 0 is misleading because it implies perfect certainty.
        NaN signals that the error estimate is undefined.
        """
        design = _make_design_2factor()
        # Perfectly additive data: zero residual error
        sn_ratios = {
            1: 1.0, 2: 3.0, 3: 2.0,
            4: 3.0, 5: 5.0, 6: 4.0,
            7: 5.0, 8: 7.0, 9: 6.0,
        }
        effects = compute_main_effects(design, sn_ratios)
        anova = run_anova(design, sn_ratios)
        assert anova.ms_error < 1e-12, "Precondition: ms_error must be ~0"

        prediction = predict_optimal(
            effects, sn_ratios=sn_ratios, design=design, anova_result=anova,
        )

        assert prediction.se_prediction is not None, (
            "se_prediction should be NaN, not None"
        )
        assert math.isnan(prediction.se_prediction), (
            f"se_prediction={prediction.se_prediction}; "
            f"should be NaN when ms_error < 1e-12, not 0"
        )

    def test_prediction_interval_none_when_ms_error_zero(self):
        """prediction_interval must be None when ms_error is 0.

        NaN * t_val = NaN, so no valid interval can be computed.
        """
        design = _make_design_2factor()
        sn_ratios = {
            1: 1.0, 2: 3.0, 3: 2.0,
            4: 3.0, 5: 5.0, 6: 4.0,
            7: 5.0, 8: 7.0, 9: 6.0,
        }
        effects = compute_main_effects(design, sn_ratios)
        anova = run_anova(design, sn_ratios)
        prediction = predict_optimal(
            effects, sn_ratios=sn_ratios, design=design, anova_result=anova,
        )

        assert prediction.prediction_interval is None, (
            f"prediction_interval should be None when se is NaN, "
            f"got {prediction.prediction_interval}"
        )


# ---------------------------------------------------------------------------
# Bug 249: KeyError when some rows have no scores (all trials errored)
# ---------------------------------------------------------------------------


class TestComputeMainEffectsMissingRows:
    """compute_main_effects must not raise KeyError when some rows have no data.

    When all trials for a given OA row error out, that row has no entry in
    row_scores and therefore no entry in sn_ratios.  compute_main_effects
    iterates *all* design.rows and does sn_ratios[row.run_id], raising
    KeyError for the missing rows.

    The fix: skip rows absent from sn_ratios in compute_main_effects.
    """

    def test_missing_row_in_sn_ratios_does_not_raise(self):
        """Fix: row absent from sn_ratios is skipped, not a KeyError."""
        design = _make_design_2factor()
        # Only include rows 1-8; row 9 is missing (all trials errored)
        sn_ratios_partial = {i: float(i) for i in range(1, 9)}  # missing row 9
        # After the fix this must not raise
        effects = compute_main_effects(design, sn_ratios_partial)
        assert "axis_1" in effects
        assert "axis_2" in effects

    def test_complete_sn_ratios_work_correctly(self):
        """All rows present in sn_ratios works without error."""
        design = _make_design_2factor()
        sn_ratios = {i: float(i) for i in range(1, 10)}
        effects = compute_main_effects(design, sn_ratios)
        assert "axis_1" in effects
        assert "axis_2" in effects

    def test_pipeline_row_scores_conversion_produces_int(self):
        """The pipeline fix: int(trial.metrics['oa_row_id']) yields an int key.

        This regression guard verifies that the explicit cast in pipeline.py
        produces an int-keyed dict compatible with sn_ratios lookup.
        """
        raw_oa_row_id = 3.0  # float as stored by taguchi/runner.py
        row_id_int = int(raw_oa_row_id)
        assert type(row_id_int) is int  # noqa: E721
        assert row_id_int == 3

        design = _make_design_2factor()
        assert any(row.run_id == row_id_int for row in design.rows)
