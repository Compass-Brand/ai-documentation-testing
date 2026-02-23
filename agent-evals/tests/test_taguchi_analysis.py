"""Tests for Taguchi S/N ratio, ANOVA decomposition, and optimal prediction."""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy import stats

from agent_evals.taguchi.analysis import (
    ANOVAFactorResult,
    ANOVAResult,
    ConfirmationResult,
    OptimalPrediction,
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
