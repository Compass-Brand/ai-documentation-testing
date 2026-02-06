"""Tests for interaction effect analysis module (Story 7.2)."""

from __future__ import annotations

import numpy as np
import pytest
from agent_evals.interaction_analysis import (
    EffectEstimate,
    LenthResult,
    compute_effects,
    compute_half_normal_points,
    detect_override,
    lenth_method,
)
from scipy import stats as sp_stats

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_2x2_design() -> tuple[list[float], list[list[int]], list[str]]:
    """Create a standard 2^2 factorial design with known effects.

    Design matrix (A, B):
        Run 1: -1, -1  -> y = 20
        Run 2: +1, -1  -> y = 40
        Run 3: -1, +1  -> y = 30
        Run 4: +1, +1  -> y = 52

    Main effect A = (2/4)*[(-1)(20) + (1)(40) + (-1)(30) + (1)(52)]
                   = 0.5 * (-20 + 40 - 30 + 52) = 0.5 * 42 = 21
    Main effect B = (2/4)*[(-1)(20) + (-1)(40) + (1)(30) + (1)(52)]
                   = 0.5 * (-20 - 40 + 30 + 52) = 0.5 * 22 = 11
    Interaction AB = (2/4)*[(1)(20) + (-1)(40) + (-1)(30) + (1)(52)]
                    = 0.5 * (20 - 40 - 30 + 52) = 0.5 * 2 = 1
    """
    response_values = [20.0, 40.0, 30.0, 52.0]
    design_matrix = [
        [-1, -1],
        [+1, -1],
        [-1, +1],
        [+1, +1],
    ]
    factor_names = ["A", "B"]
    return response_values, design_matrix, factor_names


def _make_2x2x2_design() -> tuple[list[float], list[list[int]], list[str]]:
    """Create a 2^3 factorial design with known effects.

    Factors: A, B, C (all at -1/+1).
    8 runs in standard order.
    """
    design_matrix = [
        [-1, -1, -1],
        [+1, -1, -1],
        [-1, +1, -1],
        [+1, +1, -1],
        [-1, -1, +1],
        [+1, -1, +1],
        [-1, +1, +1],
        [+1, +1, +1],
    ]
    # Responses chosen so that:
    # - A has a large main effect
    # - B has a moderate main effect
    # - C has a small main effect
    # - A:B has a noticeable interaction
    response_values = [10.0, 30.0, 15.0, 45.0, 12.0, 32.0, 17.0, 49.0]
    factor_names = ["A", "B", "C"]
    return response_values, design_matrix, factor_names


# ---------------------------------------------------------------------------
# Tests: compute_effects
# ---------------------------------------------------------------------------


class TestComputeEffects:
    def test_2x2_main_effects(self) -> None:
        """Test compute_effects with a 2^2 design with known exact effects."""
        y, X, names = _make_2x2_design()
        effects = compute_effects(y, X, names)

        # Build a lookup by name
        by_name = {e.name: e for e in effects}

        assert by_name["A"].estimate == pytest.approx(21.0)
        assert by_name["B"].estimate == pytest.approx(11.0)
        assert by_name["A:B"].estimate == pytest.approx(1.0)

    def test_2x2_effect_labels(self) -> None:
        """Main effects should have is_main_effect=True, interactions False."""
        y, X, names = _make_2x2_design()
        effects = compute_effects(y, X, names)
        by_name = {e.name: e for e in effects}

        assert by_name["A"].is_main_effect is True
        assert by_name["B"].is_main_effect is True
        assert by_name["A:B"].is_main_effect is False

    def test_2x2_sorted_by_absolute_effect(self) -> None:
        """Effects should be sorted descending by |estimate|."""
        y, X, names = _make_2x2_design()
        effects = compute_effects(y, X, names)

        abs_values = [abs(e.estimate) for e in effects]
        assert abs_values == sorted(abs_values, reverse=True)

    def test_2x2_correct_count(self) -> None:
        """2^2 design: 2 main effects + 1 interaction = 3 effects total."""
        y, X, names = _make_2x2_design()
        effects = compute_effects(y, X, names)
        assert len(effects) == 3

    def test_2x3_design(self) -> None:
        """Test compute_effects with a 2^3 design."""
        y, X, names = _make_2x2x2_design()
        effects = compute_effects(y, X, names)

        # 3 main effects + 3 two-way interactions = 6 total
        assert len(effects) == 6

        by_name = {e.name: e for e in effects}
        assert "A" in by_name
        assert "B" in by_name
        assert "C" in by_name
        assert "A:B" in by_name
        assert "A:C" in by_name
        assert "B:C" in by_name

    def test_2x3_main_vs_interaction_labels(self) -> None:
        """Verify main effects and interactions are correctly labelled in 2^3."""
        y, X, names = _make_2x2x2_design()
        effects = compute_effects(y, X, names)
        by_name = {e.name: e for e in effects}

        for name in ["A", "B", "C"]:
            assert by_name[name].is_main_effect is True
        for name in ["A:B", "A:C", "B:C"]:
            assert by_name[name].is_main_effect is False

    def test_2x3_known_main_effects(self) -> None:
        """Verify numerical accuracy of main effects in 2^3 design."""
        y, X, names = _make_2x2x2_design()
        effects = compute_effects(y, X, names)
        by_name = {e.name: e for e in effects}

        # Manual calculation for A:
        # (2/8) * sum(x_Ai * y_i)
        # = 0.25 * [(-1)(10) + (1)(30) + (-1)(15) + (1)(45) +
        #           (-1)(12) + (1)(32) + (-1)(17) + (1)(49)]
        # = 0.25 * (-10+30-15+45-12+32-17+49)
        # = 0.25 * 102 = 25.5
        assert by_name["A"].estimate == pytest.approx(25.5)

    def test_shape_mismatch_raises(self) -> None:
        """Mismatched dimensions should raise ValueError."""
        with pytest.raises(ValueError, match="does not match"):
            compute_effects([1.0, 2.0], [[1, 1], [1, -1]], ["A", "B", "C"])

    def test_all_equal_responses(self) -> None:
        """When all responses are equal, all effects should be zero."""
        y = [5.0, 5.0, 5.0, 5.0]
        X = [[-1, -1], [1, -1], [-1, 1], [1, 1]]
        effects = compute_effects(y, X, ["A", "B"])
        for e in effects:
            assert e.estimate == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Tests: lenth_method
# ---------------------------------------------------------------------------


class TestLenthMethod:
    def test_pse_calculation(self) -> None:
        """PSE should be 1.5 * median(|effects|) for simple cases."""
        # Create effects with known absolute values: [1, 2, 3, 4, 5]
        effects = [
            EffectEstimate(f"e{i}", est, True)
            for i, est in enumerate([1.0, -2.0, 3.0, -4.0, 5.0])
        ]
        result = lenth_method(effects, alpha=0.05)

        # median(|1, 2, 3, 4, 5|) = 3.0
        # Initial PSE = 1.5 * 3.0 = 4.5
        # 2.5 * 4.5 = 11.25 -- no effects exceed this, so PSE = 4.5
        assert result.pse == pytest.approx(4.5)

    def test_significant_effect_detected(self) -> None:
        """A clearly large effect should be marked significant."""
        # One huge effect among small ones
        effects = [
            EffectEstimate("small1", 0.1, True),
            EffectEstimate("small2", -0.2, True),
            EffectEstimate("small3", 0.15, True),
            EffectEstimate("small4", -0.1, True),
            EffectEstimate("big", 10.0, True),
        ]
        result = lenth_method(effects, alpha=0.05)

        by_name = {e.name: e for e in result.effects}
        assert by_name["big"].significant is True
        # Small effects should not be significant
        assert by_name["small1"].significant is False

    def test_all_zero_effects(self) -> None:
        """All-zero effects should yield PSE=0 and nothing significant."""
        effects = [
            EffectEstimate(f"e{i}", 0.0, True) for i in range(5)
        ]
        result = lenth_method(effects, alpha=0.05)

        assert result.pse == 0.0
        assert result.me == 0.0
        assert result.sme == 0.0
        for e in result.effects:
            assert e.significant is False

    def test_empty_effects(self) -> None:
        """Empty effects list should return zero PSE/ME/SME."""
        result = lenth_method([], alpha=0.05)
        assert result.pse == 0.0
        assert result.me == 0.0
        assert result.sme == 0.0
        assert result.effects == []

    def test_me_less_than_sme(self) -> None:
        """ME should always be less than or equal to SME (SME is more conservative)."""
        effects = [
            EffectEstimate(f"e{i}", float(i + 1), True) for i in range(7)
        ]
        result = lenth_method(effects, alpha=0.05)
        assert result.me <= result.sme

    def test_alpha_stored(self) -> None:
        """The alpha parameter should be stored in the result."""
        effects = [EffectEstimate("e0", 1.0, True)]
        result = lenth_method(effects, alpha=0.01)
        assert result.alpha == 0.01

    def test_iterative_pse_convergence(self) -> None:
        """PSE should converge when outlier effects are removed iteratively."""
        # Mix of small effects and one extreme outlier
        effects = [
            EffectEstimate("a", 1.0, True),
            EffectEstimate("b", 1.2, True),
            EffectEstimate("c", 0.8, True),
            EffectEstimate("d", 1.1, True),
            EffectEstimate("e", 0.9, True),
            EffectEstimate("outlier", 100.0, True),
        ]
        result = lenth_method(effects)

        # After removing the outlier (100 > 2.5 * PSE), PSE should be based
        # on the remaining small effects
        assert result.pse < 5.0  # Much smaller than if outlier were included
        by_name = {e.name: e for e in result.effects}
        assert by_name["outlier"].significant is True

    def test_original_effects_not_mutated(self) -> None:
        """lenth_method should not mutate the input effects."""
        effects = [EffectEstimate("x", 5.0, True, significant=False)]
        lenth_method(effects)
        assert effects[0].significant is False  # Unchanged


# ---------------------------------------------------------------------------
# Tests: compute_half_normal_points
# ---------------------------------------------------------------------------


class TestComputeHalfNormalPoints:
    def test_sorted_by_absolute_effect(self) -> None:
        """Points should be sorted ascending by absolute effect."""
        effects = [
            EffectEstimate("big", 10.0, True),
            EffectEstimate("small", 1.0, True),
            EffectEstimate("medium", -5.0, False),
        ]
        points = compute_half_normal_points(effects)

        abs_values = [p.absolute_effect for p in points]
        assert abs_values == sorted(abs_values)

    def test_correct_number_of_points(self) -> None:
        """Should return one point per effect."""
        effects = [EffectEstimate(f"e{i}", float(i), True) for i in range(7)]
        points = compute_half_normal_points(effects)
        assert len(points) == 7

    def test_quantiles_are_positive(self) -> None:
        """All half-normal quantiles should be positive."""
        effects = [
            EffectEstimate("a", 1.0, True),
            EffectEstimate("b", -2.0, True),
            EffectEstimate("c", 3.0, False),
        ]
        points = compute_half_normal_points(effects)
        for p in points:
            assert p.expected_quantile > 0

    def test_quantiles_increase(self) -> None:
        """Expected quantiles should increase along sorted effects."""
        effects = [EffectEstimate(f"e{i}", float(i + 1), True) for i in range(5)]
        points = compute_half_normal_points(effects)

        quantiles = [p.expected_quantile for p in points]
        for i in range(len(quantiles) - 1):
            assert quantiles[i] < quantiles[i + 1]

    def test_labels_preserved(self) -> None:
        """Point labels should match effect names."""
        effects = [
            EffectEstimate("alpha", 3.0, True),
            EffectEstimate("beta", 1.0, True),
        ]
        points = compute_half_normal_points(effects)
        labels = {p.label for p in points}
        assert labels == {"alpha", "beta"}

    def test_absolute_values_used(self) -> None:
        """Negative effects should use absolute values."""
        effects = [EffectEstimate("neg", -5.0, True)]
        points = compute_half_normal_points(effects)
        assert points[0].absolute_effect == 5.0

    def test_empty_effects(self) -> None:
        """Empty effects should return empty list."""
        points = compute_half_normal_points([])
        assert points == []

    def test_quantile_formula(self) -> None:
        """Verify the quantile formula: Phi^{-1}((i - 0.5 + n) / (2*n))."""
        effects = [
            EffectEstimate("a", 1.0, True),
            EffectEstimate("b", 2.0, True),
            EffectEstimate("c", 3.0, True),
        ]
        points = compute_half_normal_points(effects)
        n = 3
        for i, p in enumerate(points, start=1):
            expected_p = (i - 0.5 + n) / (2.0 * n)
            expected_q = float(sp_stats.norm.ppf(expected_p))
            assert p.expected_quantile == pytest.approx(expected_q)


# ---------------------------------------------------------------------------
# Tests: detect_override
# ---------------------------------------------------------------------------


class TestDetectOverride:
    def test_override_when_factorial_clearly_better(self) -> None:
        """Should detect override when a factorial combo scores higher."""
        result = detect_override(
            factorial_scores={"A=high+B=high": 85.0, "A=low+B=low": 60.0},
            sequential_winner_score=70.0,
            sequential_winner_name="seq_best",
        )
        assert result.override_detected is True
        assert result.best_factorial_score == 85.0
        assert result.override_combination is not None
        assert result.override_combination == {"A": "high", "B": "high"}

    def test_no_override_when_sequential_is_best(self) -> None:
        """Should not detect override when sequential winner is best."""
        result = detect_override(
            factorial_scores={"combo1": 60.0, "combo2": 65.0},
            sequential_winner_score=80.0,
            sequential_winner_name="seq_best",
        )
        assert result.override_detected is False
        assert result.override_combination is None
        assert result.override_p_value is None
        assert result.best_factorial_score == 80.0  # Sequential stays best

    def test_override_with_replicated_scores_significant(self) -> None:
        """Override should use Wilcoxon test when replicated scores are provided."""
        # Create clearly different distributions
        np.random.seed(42)
        combo_scores = list(np.random.normal(85, 2, 20))
        winner_scores = list(np.random.normal(70, 2, 20))

        result = detect_override(
            factorial_scores={"combo_best": 85.0},
            sequential_winner_score=70.0,
            sequential_winner_name="seq_winner",
            all_scores={
                "combo_best": combo_scores,
                "seq_winner": winner_scores,
            },
            alpha=0.05,
        )
        assert result.override_detected is True
        assert result.override_p_value is not None
        assert result.override_p_value < 0.05

    def test_no_override_with_replicated_scores_not_significant(self) -> None:
        """No override when replicated scores are not significantly different."""
        np.random.seed(123)
        # Nearly identical distributions
        combo_scores = list(np.random.normal(75, 5, 20))
        winner_scores = list(np.random.normal(75, 5, 20))

        result = detect_override(
            factorial_scores={"combo": 75.5},
            sequential_winner_score=75.0,
            sequential_winner_name="seq_winner",
            all_scores={
                "combo": combo_scores,
                "seq_winner": winner_scores,
            },
            alpha=0.05,
        )
        # Even though combo_score > sequential_winner_score, the Wilcoxon
        # test should not find significance with these nearly identical distributions
        assert result.override_detected is False

    def test_sequential_winner_score_preserved(self) -> None:
        """The sequential winner score should be stored in the result."""
        result = detect_override(
            factorial_scores={"a": 50.0},
            sequential_winner_score=60.0,
            sequential_winner_name="winner",
        )
        assert result.sequential_winner_score == 60.0

    def test_combination_name_parsing(self) -> None:
        """Combination names with factor=level+factor=level should be parsed."""
        result = detect_override(
            factorial_scores={"structure=flat+metadata=rich": 90.0},
            sequential_winner_score=70.0,
            sequential_winner_name="seq",
        )
        assert result.override_detected is True
        assert result.override_combination == {"structure": "flat", "metadata": "rich"}

    def test_simple_combination_name(self) -> None:
        """Combination names without = should be wrapped in dict."""
        result = detect_override(
            factorial_scores={"combo_abc": 90.0},
            sequential_winner_score=70.0,
            sequential_winner_name="seq",
        )
        assert result.override_detected is True
        assert result.override_combination == {"combination": "combo_abc"}

    def test_placeholder_lenth_result(self) -> None:
        """InteractionResult should contain a placeholder LenthResult."""
        result = detect_override(
            factorial_scores={"a": 50.0},
            sequential_winner_score=60.0,
            sequential_winner_name="winner",
        )
        assert isinstance(result.lenth, LenthResult)
        assert result.lenth.effects == []

    def test_best_of_multiple_factorial_combos(self) -> None:
        """When multiple combos beat the sequential winner, pick the best."""
        result = detect_override(
            factorial_scores={
                "A=1+B=1": 80.0,
                "A=2+B=2": 95.0,
                "A=1+B=2": 75.0,
            },
            sequential_winner_score=70.0,
            sequential_winner_name="seq",
        )
        assert result.override_detected is True
        assert result.best_factorial_score == 95.0
        assert result.override_combination == {"A": "2", "B": "2"}


# ---------------------------------------------------------------------------
# Tests: full pipeline
# ---------------------------------------------------------------------------


class TestFullPipeline:
    def test_effects_through_lenth_through_halfnormal_through_override(self) -> None:
        """End-to-end: compute_effects -> lenth -> half_normal -> detect_override."""
        # 2^2 design with one strong main effect
        response_values = [10.0, 50.0, 12.0, 48.0]
        design_matrix = [[-1, -1], [1, -1], [-1, 1], [1, 1]]
        factor_names = ["chunk_size", "overlap"]

        # Step 1: Compute effects
        effects = compute_effects(response_values, design_matrix, factor_names)
        assert len(effects) == 3

        by_name = {e.name: e for e in effects}
        # chunk_size effect should be dominant
        # (2/4)*[(-1)(10)+(1)(50)+(-1)(12)+(1)(48)] = 0.5*(76) = 38
        assert by_name["chunk_size"].estimate == pytest.approx(38.0)
        # overlap: (2/4)*[(-1)(10)+(-1)(50)+(1)(12)+(1)(48)] = 0.5*0 = 0
        assert by_name["overlap"].estimate == pytest.approx(0.0)

        # Step 2: Lenth method
        lenth_result = lenth_method(effects, alpha=0.05)
        assert lenth_result.pse >= 0
        # chunk_size should be significant, overlap should not
        lenth_by_name = {e.name: e for e in lenth_result.effects}
        assert lenth_by_name["chunk_size"].significant is True

        # Step 3: Half-normal points
        hn_points = compute_half_normal_points(effects)
        assert len(hn_points) == 3
        # Last point (largest absolute effect) should be chunk_size
        assert hn_points[-1].label == "chunk_size"

        # Step 4: Override detection
        # Simulate factorial scores where a combination beats the sequential winner
        factorial_scores = {
            "chunk_size=large+overlap=small": 90.0,
            "chunk_size=small+overlap=large": 55.0,
        }
        override_result = detect_override(
            factorial_scores=factorial_scores,
            sequential_winner_score=80.0,
            sequential_winner_name="seq_best",
        )
        assert override_result.override_detected is True
        assert override_result.best_factorial_score == 90.0

    def test_no_override_in_pipeline(self) -> None:
        """Pipeline where the sequential winner is the best."""
        response_values = [50.0, 52.0, 51.0, 53.0]
        design_matrix = [[-1, -1], [1, -1], [-1, 1], [1, 1]]
        factor_names = ["A", "B"]

        effects = compute_effects(response_values, design_matrix, factor_names)
        lenth_method(effects)  # Verify it runs without error
        compute_half_normal_points(effects)  # Verify it runs without error

        override_result = detect_override(
            factorial_scores={"combo1": 45.0, "combo2": 48.0},
            sequential_winner_score=55.0,
            sequential_winner_name="seq",
        )
        assert override_result.override_detected is False
        assert override_result.best_factorial_score == 55.0
