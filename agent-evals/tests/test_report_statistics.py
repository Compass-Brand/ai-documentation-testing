"""Tests for the report statistical engine."""

from __future__ import annotations

import numpy as np
import pytest

from agent_evals.reports.statistics import (
    AssumptionsResult,
    BHResult,
    EffectSizeResult,
    PowerResult,
    TukeyResult,
    benjamini_hochberg,
    check_assumptions,
    compute_effect_sizes,
    interpret_cohens_d,
    power_analysis,
    tukey_hsd,
)


class TestPowerAnalysis:
    """Power analysis for the experimental design."""

    def test_returns_power_result(self):
        result = power_analysis(n_groups=5, n_obs_per_group=30)
        assert isinstance(result, PowerResult)

    def test_power_between_0_and_1(self):
        result = power_analysis(n_groups=5, n_obs_per_group=30, effect_size=0.25)
        assert 0 < result.power <= 1.0

    def test_n_required_is_positive(self):
        result = power_analysis(n_groups=5, n_obs_per_group=30, effect_size=0.25)
        assert result.n_required > 0

    def test_more_observations_increases_power(self):
        low = power_analysis(n_groups=3, n_obs_per_group=10, effect_size=0.5)
        high = power_analysis(n_groups=3, n_obs_per_group=100, effect_size=0.5)
        assert high.power > low.power

    def test_larger_effect_needs_fewer_samples(self):
        small = power_analysis(n_groups=3, n_obs_per_group=30, effect_size=0.1)
        large = power_analysis(n_groups=3, n_obs_per_group=30, effect_size=0.8)
        assert large.n_required <= small.n_required


class TestAssumptionsTesting:
    """Shapiro-Wilk normality and Levene's homogeneity tests."""

    def test_normal_residuals_pass_shapiro(self):
        rng = np.random.default_rng(42)
        residuals = rng.normal(0, 1, 100)
        result = check_assumptions(residuals, [residuals[:50], residuals[50:]])
        assert result.normality_p > 0.05

    def test_uniform_residuals_fail_shapiro(self):
        rng = np.random.default_rng(42)
        residuals = rng.uniform(0, 1, 100)
        result = check_assumptions(residuals, [residuals[:50], residuals[50:]])
        assert result.normality_p < 0.05

    def test_equal_variance_passes_levene(self):
        rng = np.random.default_rng(42)
        g1 = rng.normal(0, 1, 50)
        g2 = rng.normal(0, 1, 50)
        result = check_assumptions(
            np.concatenate([g1, g2]), [g1, g2]
        )
        assert result.homogeneity_p > 0.05

    def test_unequal_variance_fails_levene(self):
        rng = np.random.default_rng(42)
        g1 = rng.normal(0, 1, 50)
        g2 = rng.normal(0, 10, 50)
        result = check_assumptions(
            np.concatenate([g1, g2]), [g1, g2]
        )
        assert result.homogeneity_p < 0.05

    def test_returns_assumptions_result(self):
        rng = np.random.default_rng(42)
        residuals = rng.normal(0, 1, 50)
        result = check_assumptions(residuals, [residuals])
        assert isinstance(result, AssumptionsResult)


class TestEffectSizes:
    """Cohen's d, rank-biserial r, and interpretation labels."""

    def test_cohens_d_known_values(self):
        # Two groups: mean=0,sd=1 vs mean=1,sd=1 -> d ~= 1.0
        g1 = [0.0] * 20
        g2 = [1.0] * 20
        results = compute_effect_sizes({"A": g1, "B": g2})
        assert len(results) == 1
        assert abs(abs(results[0].cohens_d) - 1.0) < 0.1

    def test_rank_biserial_r_computed(self):
        g1 = list(range(10))
        g2 = list(range(5, 15))
        results = compute_effect_sizes({"A": g1, "B": g2})
        assert results[0].rank_biserial_r is not None

    def test_interpretation_small(self):
        assert interpret_cohens_d(0.15) == "small"

    def test_interpretation_medium(self):
        assert interpret_cohens_d(0.55) == "medium"

    def test_interpretation_large(self):
        assert interpret_cohens_d(0.95) == "large"

    def test_interpretation_negligible(self):
        assert interpret_cohens_d(0.05) == "negligible"

    def test_multiple_groups_pairwise(self):
        groups = {
            "A": [1.0, 2.0, 3.0],
            "B": [2.0, 3.0, 4.0],
            "C": [3.0, 4.0, 5.0],
        }
        results = compute_effect_sizes(groups)
        # 3 choose 2 = 3 pairs
        assert len(results) == 3


class TestTukeyHSD:
    """Tukey's HSD post-hoc test."""

    def test_returns_all_pairwise(self):
        groups = {
            "A": [1.0, 2.0, 3.0, 4.0],
            "B": [2.0, 3.0, 4.0, 5.0],
            "C": [3.0, 4.0, 5.0, 6.0],
            "D": [4.0, 5.0, 6.0, 7.0],
        }
        results = tukey_hsd(groups)
        # 4 choose 2 = 6
        assert len(results) == 6

    def test_result_has_p_value(self):
        groups = {
            "A": [1.0, 2.0, 3.0],
            "B": [10.0, 11.0, 12.0],
        }
        results = tukey_hsd(groups)
        assert results[0].p_value >= 0
        assert results[0].p_value <= 1

    def test_significant_difference_detected(self):
        groups = {
            "A": [1.0, 1.1, 1.2, 1.3, 1.4],
            "B": [10.0, 10.1, 10.2, 10.3, 10.4],
        }
        results = tukey_hsd(groups)
        assert results[0].p_value < 0.05


class TestBenjaminiHochberg:
    """Benjamini-Hochberg FDR correction."""

    def test_corrected_p_values_returned(self):
        p_values = [0.001, 0.01, 0.03, 0.05, 0.1, 0.2, 0.5, 0.8]
        results = benjamini_hochberg(p_values)
        assert len(results) == len(p_values)

    def test_significant_results_subset(self):
        p_values = [0.001, 0.01, 0.03, 0.5, 0.8]
        results = benjamini_hochberg(p_values, alpha=0.05)
        significant = [r for r in results if r.significant]
        assert len(significant) >= 1

    def test_all_significant_for_tiny_p_values(self):
        p_values = [0.001, 0.002, 0.003]
        results = benjamini_hochberg(p_values, alpha=0.05)
        assert all(r.significant for r in results)

    def test_none_significant_for_large_p_values(self):
        p_values = [0.5, 0.6, 0.7, 0.8, 0.9]
        results = benjamini_hochberg(p_values, alpha=0.05)
        assert not any(r.significant for r in results)

    def test_adjusted_p_values_monotone(self):
        p_values = [0.001, 0.01, 0.03, 0.05, 0.1]
        results = benjamini_hochberg(p_values, alpha=0.05)
        # Sort by original p-value, adjusted should be non-decreasing
        sorted_results = sorted(results, key=lambda r: r.original_p)
        adjusted = [r.adjusted_p for r in sorted_results]
        for i in range(1, len(adjusted)):
            assert adjusted[i] >= adjusted[i - 1] - 1e-10
