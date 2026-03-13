"""Tests for multi-objective Taguchi analysis."""

from __future__ import annotations

from agent_evals.taguchi.analysis import compute_sn_ratios
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
        TaguchiFactorDef(
            name="axis_1", n_levels=3,
            level_names=["flat", "2tier", "3tier"], axis=1,
        ),
        TaguchiFactorDef(
            name="axis_2", n_levels=3,
            level_names=["path", "summary", "tokens"], axis=2,
        ),
    ]
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
# S/N Ratio Quality Type Tests
# ---------------------------------------------------------------------------


class TestMultiObjectiveSNRatios:
    """Verify compute_sn_ratios supports smaller_is_better and nominal_is_best."""

    def test_smaller_is_better_for_cost(self):
        """Lower cost = better, so smaller_is_better quality type."""
        row_costs = {
            0: [0.005, 0.006, 0.004],
            1: [0.020, 0.025, 0.018],
        }
        sn = compute_sn_ratios(row_costs, quality_type="smaller_is_better")
        assert sn[0] > sn[1]

    def test_smaller_is_better_for_latency(self):
        """Lower latency = better."""
        row_latencies = {
            0: [200.0, 220.0, 180.0],
            1: [800.0, 900.0, 750.0],
        }
        sn = compute_sn_ratios(
            row_latencies, quality_type="smaller_is_better",
        )
        assert sn[0] > sn[1]

    def test_nominal_is_best_for_stability(self):
        """Consistency = good, so nominal_is_best quality type."""
        row_scores = {
            0: [0.80, 0.80, 0.80],
            1: [0.90, 0.50, 0.70],
        }
        sn = compute_sn_ratios(
            row_scores, quality_type="nominal_is_best",
        )
        assert sn[0] > sn[1]


# ---------------------------------------------------------------------------
# Multi-Objective Wrapper Tests
# ---------------------------------------------------------------------------


class TestMultiObjectiveWrapper:
    """Verify run_multi_objective_analysis returns per-objective results."""

    def test_runs_all_three_objectives(self):
        """Wrapper returns results for accuracy, cost, and latency."""
        from agent_evals.taguchi.multi_objective import (
            run_multi_objective_analysis,
        )

        design = _make_design_2factor()
        # Build per-row data (9 rows, run_ids 1..9)
        row_scores = {i: [0.7 + i * 0.02] for i in range(1, 10)}
        row_costs = {i: [0.01 * i] for i in range(1, 10)}
        row_latencies = {i: [100.0 + 50.0 * i] for i in range(1, 10)}

        results = run_multi_objective_analysis(
            design, row_scores, row_costs, row_latencies,
        )

        assert "accuracy" in results
        assert "cost" in results
        assert "latency" in results

    def test_each_objective_has_sn_effects_anova(self):
        """Each objective result contains sn_ratios, main_effects, anova."""
        from agent_evals.taguchi.multi_objective import (
            run_multi_objective_analysis,
        )

        design = _make_design_2factor()
        row_scores = {i: [0.7 + i * 0.02] for i in range(1, 10)}
        row_costs = {i: [0.01 * i] for i in range(1, 10)}
        row_latencies = {i: [100.0 + 50.0 * i] for i in range(1, 10)}

        results = run_multi_objective_analysis(
            design, row_scores, row_costs, row_latencies,
        )

        for name in ("accuracy", "cost", "latency"):
            obj = results[name]
            assert "sn_ratios" in obj, f"{name} missing sn_ratios"
            assert "main_effects" in obj, f"{name} missing main_effects"
            assert "anova" in obj, f"{name} missing anova"

    def test_accuracy_uses_larger_is_better(self):
        """Accuracy S/N should be higher for rows with higher scores."""
        from agent_evals.taguchi.multi_objective import (
            run_multi_objective_analysis,
        )

        design = _make_design_2factor()
        # Row 1 has high scores, row 9 has low scores
        row_scores = {i: [1.0 - i * 0.08] for i in range(1, 10)}
        row_costs = {i: [0.01] for i in range(1, 10)}
        row_latencies = {i: [100.0] for i in range(1, 10)}

        results = run_multi_objective_analysis(
            design, row_scores, row_costs, row_latencies,
        )

        sn = results["accuracy"]["sn_ratios"]
        # Row 1 (score ~0.92) should have higher S/N than row 9 (score ~0.28)
        assert sn[1] > sn[9]

    def test_cost_uses_smaller_is_better(self):
        """Cost S/N should be higher for rows with lower costs."""
        from agent_evals.taguchi.multi_objective import (
            run_multi_objective_analysis,
        )

        design = _make_design_2factor()
        row_scores = {i: [0.8] for i in range(1, 10)}
        # Row 1 has lowest cost, row 9 has highest
        row_costs = {i: [0.001 * i] for i in range(1, 10)}
        row_latencies = {i: [100.0] for i in range(1, 10)}

        results = run_multi_objective_analysis(
            design, row_scores, row_costs, row_latencies,
        )

        sn = results["cost"]["sn_ratios"]
        assert sn[1] > sn[9]

    def test_skips_empty_objective(self):
        """Empty row_data dict should be skipped."""
        from agent_evals.taguchi.multi_objective import (
            run_multi_objective_analysis,
        )

        design = _make_design_2factor()
        row_scores = {i: [0.8] for i in range(1, 10)}
        row_costs: dict[int, list[float]] = {}
        row_latencies = {i: [100.0] for i in range(1, 10)}

        results = run_multi_objective_analysis(
            design, row_scores, row_costs, row_latencies,
        )

        assert "accuracy" in results
        assert "cost" not in results
        assert "latency" in results

    def test_anova_results_have_factor_names(self):
        """ANOVA results should reference the design's factor names."""
        from agent_evals.taguchi.multi_objective import (
            run_multi_objective_analysis,
        )

        design = _make_design_2factor()
        row_scores = {i: [0.5 + i * 0.05] for i in range(1, 10)}
        row_costs = {i: [0.01 * i] for i in range(1, 10)}
        row_latencies = {i: [100.0 + 20.0 * i] for i in range(1, 10)}

        results = run_multi_objective_analysis(
            design, row_scores, row_costs, row_latencies,
        )

        for name in ("accuracy", "cost", "latency"):
            anova = results[name]["anova"]
            factor_names = {fr.factor_name for fr in anova.factors}
            assert "axis_1" in factor_names
            assert "axis_2" in factor_names
