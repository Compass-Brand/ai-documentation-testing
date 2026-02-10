"""Tests for scoring module: composite scores, statistical tests, and bootstrap CIs."""

from __future__ import annotations

import numpy as np
import pytest
from agent_evals.scoring import (
    DEFAULT_WEIGHTS,
    WEIGHT_SCHEMES,
    BootstrapCI,
    PairwiseResult,
    bootstrap_ci,
    composite_score,
    holm_bonferroni,
    pairwise_wilcoxon,
)

# ---------------------------------------------------------------------------
# Composite score tests
# ---------------------------------------------------------------------------


class TestCompositeScore:
    """Tests for composite_score calculation."""

    def test_known_weights_and_scores(self) -> None:
        """Composite score with known values gives expected result."""
        scores = {
            "retrieval": 0.8,
            "fact_extraction": 0.6,
            "code_generation": 0.9,
            "agentic": 0.7,
            "multi_hop": 0.5,
            "negative": 0.4,
            "compositional": 0.3,
            "robustness": 0.6,
            "disambiguation": 0.5,
            "conflicting": 0.2,
            "efficiency": 0.1,
        }
        weights = DEFAULT_WEIGHTS

        # Manual calculation: sum(w_i * s_i) * 100
        expected = sum(
            weights[k] * scores[k] for k in weights
        ) * 100

        result = composite_score(scores, weights)
        assert result == pytest.approx(expected, abs=1e-10)

    def test_all_perfect_scores(self) -> None:
        """All scores of 1.0 should yield exactly 100.0."""
        scores = {k: 1.0 for k in DEFAULT_WEIGHTS}
        result = composite_score(scores, DEFAULT_WEIGHTS)
        assert result == pytest.approx(100.0, abs=1e-10)

    def test_all_zero_scores(self) -> None:
        """All scores of 0.0 should yield exactly 0.0."""
        scores = {k: 0.0 for k in DEFAULT_WEIGHTS}
        result = composite_score(scores, DEFAULT_WEIGHTS)
        assert result == pytest.approx(0.0, abs=1e-10)

    def test_subset_weights(self) -> None:
        """Composite score works when weights cover a subset of task types."""
        scores = {"retrieval": 0.8, "agentic": 0.6}
        weights = {"retrieval": 0.5, "agentic": 0.5}
        # (0.5 * 0.8 + 0.5 * 0.6) * 100 = 70.0
        result = composite_score(scores, weights)
        assert result == pytest.approx(70.0, abs=1e-10)

    def test_single_task_type(self) -> None:
        """Composite with one task type reduces to weight * score * 100."""
        scores = {"retrieval": 0.75}
        weights = {"retrieval": 1.0}
        result = composite_score(scores, weights)
        assert result == pytest.approx(75.0, abs=1e-10)

    def test_missing_scores_default_to_zero(self) -> None:
        """Scores missing from the scores dict are treated as 0.0."""
        scores = {"retrieval": 0.8}
        weights = {"retrieval": 0.5, "agentic": 0.5}
        # agentic is missing from scores -> 0.0
        # (0.5 * 0.8 + 0.5 * 0.0) * 100 = 40.0
        result = composite_score(scores, weights)
        assert result == pytest.approx(40.0, abs=1e-10)


# ---------------------------------------------------------------------------
# Wilcoxon signed-rank tests
# ---------------------------------------------------------------------------


class TestPairwiseWilcoxon:
    """Tests for pairwise_wilcoxon."""

    def test_identical_samples_not_significant(self) -> None:
        """Identical samples should not produce a significant result."""
        rng = np.random.default_rng(42)
        data = rng.uniform(0, 1, size=30).tolist()
        result = pairwise_wilcoxon(data, data, alpha=0.05)
        assert isinstance(result, PairwiseResult)
        assert result.significant is False

    def test_very_different_samples_significant(self) -> None:
        """Clearly different paired samples should be significant."""
        rng = np.random.default_rng(42)
        scores_a = rng.uniform(0.0, 0.3, size=30).tolist()
        scores_b = rng.uniform(0.7, 1.0, size=30).tolist()
        result = pairwise_wilcoxon(scores_a, scores_b, alpha=0.05)
        assert result.significant is True
        assert result.p_value < 0.05

    def test_effect_size_in_range(self) -> None:
        """Rank-biserial effect size must be in [-1, 1]."""
        rng = np.random.default_rng(99)
        scores_a = rng.uniform(0, 1, size=20).tolist()
        scores_b = rng.uniform(0, 1, size=20).tolist()
        result = pairwise_wilcoxon(scores_a, scores_b)
        assert -1.0 <= result.effect_size <= 1.0

    def test_effect_size_direction(self) -> None:
        """Rank-biserial should be large negative when b >> a."""
        scores_a = [0.1] * 20
        scores_b = [0.9] * 20
        result = pairwise_wilcoxon(scores_a, scores_b)
        # b is much larger than a, so differences are negative,
        # effect size should reflect that
        assert result.effect_size != 0.0

    def test_rank_biserial_handles_all_tied(self) -> None:
        """When all paired observations are equal (all differences zero),
        rank-biserial effect size should be 0.0 without division-by-zero."""
        # Exact same scores: all differences are zero
        scores = [0.5, 0.6, 0.7, 0.8, 0.9]
        result = pairwise_wilcoxon(scores, scores, alpha=0.05)
        assert result.effect_size == 0.0
        assert result.p_value == 1.0
        assert result.significant is False

    def test_rank_biserial_near_tied(self) -> None:
        """When almost all pairs are tied, effect size should still be valid."""
        # All but one pair identical
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        b = [1.0, 2.0, 3.0, 4.0, 4.0]  # Only last differs
        result = pairwise_wilcoxon(a, b, alpha=0.05)
        assert -1.0 <= result.effect_size <= 1.0
        assert isinstance(result.effect_size, float)

    def test_result_fields_populated(self) -> None:
        """All PairwiseResult fields should be populated."""
        rng = np.random.default_rng(7)
        a = rng.uniform(0, 1, size=15).tolist()
        b = rng.uniform(0, 1, size=15).tolist()
        result = pairwise_wilcoxon(a, b)
        assert isinstance(result.statistic, float)
        assert isinstance(result.p_value, float)
        assert isinstance(result.corrected_p_value, float)
        assert isinstance(result.effect_size, float)
        assert isinstance(result.significant, bool)
        # Before Holm-Bonferroni, corrected_p == raw p
        assert result.corrected_p_value == result.p_value


# ---------------------------------------------------------------------------
# Holm-Bonferroni correction tests
# ---------------------------------------------------------------------------


class TestHolmBonferroni:
    """Tests for holm_bonferroni correction."""

    def test_corrects_p_values(self) -> None:
        """Holm-Bonferroni should increase p-values appropriately."""
        # Create results with known p-values
        results = [
            PairwiseResult(
                variant_a="A", variant_b="B",
                statistic=10.0, p_value=0.01,
                corrected_p_value=0.01, effect_size=0.5,
                significant=True,
            ),
            PairwiseResult(
                variant_a="A", variant_b="C",
                statistic=8.0, p_value=0.04,
                corrected_p_value=0.04, effect_size=0.3,
                significant=True,
            ),
            PairwiseResult(
                variant_a="B", variant_b="C",
                statistic=5.0, p_value=0.06,
                corrected_p_value=0.06, effect_size=0.2,
                significant=False,
            ),
        ]
        corrected = holm_bonferroni(results, alpha=0.05)
        assert len(corrected) == 3

        # Holm-Bonferroni: sort by p-value ascending, multiply by (m - rank)
        # p=0.01 * 3 = 0.03 < 0.05 -> significant
        # p=0.04 * 2 = 0.08 > 0.05 -> not significant
        # p=0.06 * 1 = 0.06, but monotonicity -> max(0.06, 0.08) = 0.08
        corrected_sorted = sorted(corrected, key=lambda r: r.p_value)
        assert corrected_sorted[0].corrected_p_value == pytest.approx(0.03)
        assert corrected_sorted[0].significant is True
        assert corrected_sorted[1].corrected_p_value == pytest.approx(0.08)
        assert corrected_sorted[1].significant is False
        assert corrected_sorted[2].corrected_p_value == pytest.approx(0.08)
        assert corrected_sorted[2].significant is False

    def test_single_comparison_unchanged(self) -> None:
        """A single comparison needs no correction (multiplied by 1)."""
        result = PairwiseResult(
            variant_a="A", variant_b="B",
            statistic=10.0, p_value=0.03,
            corrected_p_value=0.03, effect_size=0.5,
            significant=True,
        )
        corrected = holm_bonferroni([result], alpha=0.05)
        assert corrected[0].corrected_p_value == pytest.approx(0.03)
        assert corrected[0].significant is True

    def test_corrected_p_capped_at_one(self) -> None:
        """Corrected p-values should be capped at 1.0."""
        results = [
            PairwiseResult(
                variant_a="A", variant_b="B",
                statistic=1.0, p_value=0.9,
                corrected_p_value=0.9, effect_size=0.0,
                significant=False,
            ),
            PairwiseResult(
                variant_a="A", variant_b="C",
                statistic=1.0, p_value=0.8,
                corrected_p_value=0.8, effect_size=0.0,
                significant=False,
            ),
        ]
        corrected = holm_bonferroni(results, alpha=0.05)
        for r in corrected:
            assert r.corrected_p_value <= 1.0

    def test_empty_list(self) -> None:
        """Empty input returns empty output."""
        assert holm_bonferroni([], alpha=0.05) == []

    def test_tied_p_values_deterministic(self) -> None:
        """Tied p-values should produce deterministic, consistent corrections.

        When all raw p-values are identical, Holm-Bonferroni should assign
        the same corrected p-value to all (via monotonicity enforcement),
        and the result should be deterministic regardless of input order.
        """
        results = [
            PairwiseResult(
                variant_a="A", variant_b="B",
                statistic=10.0, p_value=0.03,
                corrected_p_value=0.03, effect_size=0.5,
                significant=True,
            ),
            PairwiseResult(
                variant_a="A", variant_b="C",
                statistic=8.0, p_value=0.03,
                corrected_p_value=0.03, effect_size=0.3,
                significant=True,
            ),
            PairwiseResult(
                variant_a="B", variant_b="C",
                statistic=5.0, p_value=0.03,
                corrected_p_value=0.03, effect_size=0.2,
                significant=True,
            ),
        ]
        corrected = holm_bonferroni(results, alpha=0.05)

        # All tied: first gets 0.03*3=0.09, others enforced to >= 0.09
        for r in corrected:
            assert r.corrected_p_value == pytest.approx(0.09)

        # Verify determinism: reverse input order, same result
        reversed_results = list(reversed(results))
        corrected_rev = holm_bonferroni(reversed_results, alpha=0.05)
        for r in corrected_rev:
            assert r.corrected_p_value == pytest.approx(0.09)

        # Verify original order preserved
        assert corrected[0].variant_a == "A"
        assert corrected[0].variant_b == "B"
        assert corrected[2].variant_a == "B"
        assert corrected[2].variant_b == "C"

    def test_tied_p_values_partial(self) -> None:
        """When some p-values are tied, corrections should be consistent."""
        results = [
            PairwiseResult(
                variant_a="A", variant_b="B",
                statistic=10.0, p_value=0.01,
                corrected_p_value=0.01, effect_size=0.5,
                significant=True,
            ),
            PairwiseResult(
                variant_a="A", variant_b="C",
                statistic=8.0, p_value=0.04,
                corrected_p_value=0.04, effect_size=0.3,
                significant=True,
            ),
            PairwiseResult(
                variant_a="B", variant_b="C",
                statistic=5.0, p_value=0.04,
                corrected_p_value=0.04, effect_size=0.2,
                significant=True,
            ),
        ]
        corrected = holm_bonferroni(results, alpha=0.05)

        # p=0.01 * 3 = 0.03 (significant at 0.05)
        # p=0.04 * 2 = 0.08 (not significant)
        # p=0.04 * 1 = 0.04, but monotonicity -> max(0.04, 0.08) = 0.08
        sorted_corrected = sorted(corrected, key=lambda r: r.p_value)
        assert sorted_corrected[0].corrected_p_value == pytest.approx(0.03)
        assert sorted_corrected[0].significant is True
        # Both tied p=0.04 results should get the same corrected p-value
        assert sorted_corrected[1].corrected_p_value == pytest.approx(0.08)
        assert sorted_corrected[2].corrected_p_value == pytest.approx(0.08)

    def test_monotonicity_enforced(self) -> None:
        """Corrected p-values must be monotonically non-decreasing."""
        results = [
            PairwiseResult(
                variant_a="A", variant_b="B",
                statistic=10.0, p_value=0.001,
                corrected_p_value=0.001, effect_size=0.5,
                significant=True,
            ),
            PairwiseResult(
                variant_a="A", variant_b="C",
                statistic=8.0, p_value=0.04,
                corrected_p_value=0.04, effect_size=0.3,
                significant=True,
            ),
            PairwiseResult(
                variant_a="B", variant_b="C",
                statistic=5.0, p_value=0.03,
                corrected_p_value=0.03, effect_size=0.2,
                significant=True,
            ),
        ]
        corrected = holm_bonferroni(results, alpha=0.05)
        sorted_by_raw = sorted(corrected, key=lambda r: r.p_value)
        for i in range(1, len(sorted_by_raw)):
            assert sorted_by_raw[i].corrected_p_value >= sorted_by_raw[i - 1].corrected_p_value


# ---------------------------------------------------------------------------
# Bootstrap confidence interval tests
# ---------------------------------------------------------------------------


class TestBootstrapCI:
    """Tests for bootstrap_ci."""

    def test_ci_contains_point_estimate(self) -> None:
        """The point estimate should lie within the CI."""
        rng = np.random.default_rng(42)
        data = rng.normal(0.5, 0.1, size=100).tolist()
        result = bootstrap_ci(data, n_resamples=5000, confidence=0.95)
        assert isinstance(result, BootstrapCI)
        assert result.ci_lower <= result.point_estimate <= result.ci_upper

    def test_ci_narrows_with_more_data(self) -> None:
        """CI should be narrower with more data points."""
        rng = np.random.default_rng(42)
        small_data = rng.normal(0.5, 0.1, size=20).tolist()
        large_data = rng.normal(0.5, 0.1, size=200).tolist()

        ci_small = bootstrap_ci(small_data, n_resamples=5000, confidence=0.95)
        ci_large = bootstrap_ci(large_data, n_resamples=5000, confidence=0.95)

        width_small = ci_small.ci_upper - ci_small.ci_lower
        width_large = ci_large.ci_upper - ci_large.ci_lower
        assert width_large < width_small

    def test_ci_with_custom_statistic(self) -> None:
        """Bootstrap CI should work with a custom statistic (e.g., median)."""
        rng = np.random.default_rng(42)
        data = rng.normal(0.5, 0.1, size=50).tolist()
        result = bootstrap_ci(data, statistic=np.median, n_resamples=5000)
        assert result.ci_lower <= result.point_estimate <= result.ci_upper

    def test_n_resamples_recorded(self) -> None:
        """The number of resamples should be stored in the result."""
        data = [0.5, 0.6, 0.7, 0.8, 0.9]
        result = bootstrap_ci(data, n_resamples=2000)
        assert result.n_resamples == 2000

    def test_high_confidence_wider(self) -> None:
        """99% CI should be wider than 90% CI for the same data."""
        rng = np.random.default_rng(42)
        data = rng.normal(0.5, 0.1, size=100).tolist()
        ci_90 = bootstrap_ci(data, n_resamples=5000, confidence=0.90)
        ci_99 = bootstrap_ci(data, n_resamples=5000, confidence=0.99)
        width_90 = ci_90.ci_upper - ci_90.ci_lower
        width_99 = ci_99.ci_upper - ci_99.ci_lower
        assert width_99 > width_90

    def test_zero_variance_returns_degenerate_ci(self) -> None:
        """When all data points are identical (zero variance), CI should be
        degenerate: (value, value) with zero width."""
        data = [0.75, 0.75, 0.75, 0.75, 0.75]
        result = bootstrap_ci(data, n_resamples=1000, confidence=0.95)
        assert result.point_estimate == pytest.approx(0.75)
        assert result.ci_lower == pytest.approx(0.75)
        assert result.ci_upper == pytest.approx(0.75)

    def test_zero_variance_single_value(self) -> None:
        """Zero-variance with many identical values should not crash."""
        data = [42.0] * 50
        result = bootstrap_ci(data, n_resamples=500, confidence=0.95)
        assert result.point_estimate == pytest.approx(42.0)
        assert result.ci_lower == pytest.approx(42.0)
        assert result.ci_upper == pytest.approx(42.0)
        assert result.n_resamples == 500

    def test_insufficient_bootstrap_samples_raises(self) -> None:
        """Should raise ValueError when n_resamples is too small."""
        data = [0.5, 0.6, 0.7, 0.8, 0.9]
        with pytest.raises(ValueError, match="n_resamples"):
            bootstrap_ci(data, n_resamples=0)

    def test_minimum_bootstrap_samples(self) -> None:
        """Should raise ValueError when n_resamples < 100."""
        data = [0.5, 0.6, 0.7, 0.8, 0.9]
        with pytest.raises(ValueError, match="n_resamples"):
            bootstrap_ci(data, n_resamples=50)


# ---------------------------------------------------------------------------
# Weight scheme tests
# ---------------------------------------------------------------------------


class TestWeightSchemes:
    """Tests for weight schemes and sensitivity analysis."""

    def test_default_weights_sum_to_one(self) -> None:
        """DEFAULT_WEIGHTS should sum to 1.0."""
        assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0, abs=1e-10)

    def test_all_weight_schemes_sum_to_one(self) -> None:
        """Every weight scheme should sum to approximately 1.0."""
        for name, scheme in WEIGHT_SCHEMES.items():
            total = sum(scheme.values())
            assert total == pytest.approx(1.0, abs=1e-6), (
                f"Weight scheme '{name}' sums to {total}, not 1.0"
            )

    def test_all_schemes_have_same_keys(self) -> None:
        """All weight schemes should cover the same task types."""
        expected_keys = set(DEFAULT_WEIGHTS.keys())
        for name, scheme in WEIGHT_SCHEMES.items():
            assert set(scheme.keys()) == expected_keys, (
                f"Weight scheme '{name}' has different keys than default"
            )

    def test_all_weights_non_negative(self) -> None:
        """All weights should be non-negative."""
        for name, scheme in WEIGHT_SCHEMES.items():
            for task, weight in scheme.items():
                assert weight >= 0.0, (
                    f"Weight scheme '{name}' has negative weight for '{task}': {weight}"
                )

    def test_retrieval_heavy_boosts_retrieval(self) -> None:
        """retrieval_heavy scheme should have higher retrieval weight than default."""
        assert WEIGHT_SCHEMES["retrieval_heavy"]["retrieval"] > DEFAULT_WEIGHTS["retrieval"]

    def test_code_heavy_boosts_code_generation(self) -> None:
        """code_heavy scheme should have higher code_generation weight than default."""
        assert WEIGHT_SCHEMES["code_heavy"]["code_generation"] > DEFAULT_WEIGHTS["code_generation"]

    def test_agentic_heavy_boosts_agentic(self) -> None:
        """agentic_heavy scheme should have agentic at 0.20."""
        assert WEIGHT_SCHEMES["agentic_heavy"]["agentic"] == pytest.approx(0.20)

    def test_uniform_all_equal(self) -> None:
        """uniform scheme should have equal weights for all task types."""
        uniform = WEIGHT_SCHEMES["uniform"]
        expected = 1.0 / len(DEFAULT_WEIGHTS)
        for weight in uniform.values():
            assert weight == pytest.approx(expected, abs=1e-10)

    def test_sensitivity_analysis_across_schemes(self) -> None:
        """Different weight schemes should produce different composite scores
        for the same non-uniform scores."""
        scores = {
            "retrieval": 0.9,
            "fact_extraction": 0.8,
            "code_generation": 0.95,
            "agentic": 0.85,
            "multi_hop": 0.6,
            "negative": 0.5,
            "compositional": 0.7,
            "robustness": 0.65,
            "disambiguation": 0.55,
            "conflicting": 0.4,
            "efficiency": 0.3,
        }
        results = {}
        for name, scheme in WEIGHT_SCHEMES.items():
            results[name] = composite_score(scores, scheme)

        # All scores should be different (with non-uniform input scores)
        values = list(results.values())
        # At least some should differ
        assert len(set(round(v, 6) for v in values)) > 1, (
            "Expected different composite scores across weight schemes"
        )
        # All scores should be in valid range
        for name, score in results.items():
            assert 0.0 <= score <= 100.0, (
                f"Weight scheme '{name}' produced score {score} outside [0, 100]"
            )
