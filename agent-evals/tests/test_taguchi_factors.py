"""Tests for factor mapping from variant axes to Taguchi factors."""

from collections import Counter

import pytest
from agent_evals.taguchi.analysis import compute_main_effects, run_anova
from agent_evals.taguchi.factors import (
    DUMMY_LEVEL,
    TaguchiExperimentRow,
    build_design,
    build_factors_from_axes,
)


class TestBuildFactorsFromAxes:
    """Convert variant axis definitions to Taguchi factor definitions."""

    def test_single_axis_one_factor(self):
        axes = {1: ["flat", "2tier", "3tier", "4tier", "inline"]}
        factors = build_factors_from_axes(axes)
        assert len(factors) == 1
        assert factors[0].name == "axis_1"
        assert factors[0].n_levels == 5
        assert factors[0].level_names == ["flat", "2tier", "3tier", "4tier", "inline"]

    def test_multiple_axes(self):
        axes = {1: ["flat", "2tier"], 2: ["path", "summary", "tokens"]}
        factors = build_factors_from_axes(axes)
        assert len(factors) == 2
        assert factors[0].n_levels == 2
        assert factors[1].n_levels == 3

    def test_axes_sorted_by_number(self):
        axes = {3: ["a", "b"], 1: ["c", "d"]}
        factors = build_factors_from_axes(axes)
        assert factors[0].name == "axis_1"
        assert factors[1].name == "axis_3"

    def test_models_add_model_factor(self):
        axes = {1: ["flat", "2tier"]}
        factors = build_factors_from_axes(axes, models=["claude", "gpt", "gemini"])
        assert len(factors) == 2
        model_f = factors[-1]
        assert model_f.name == "model"
        assert model_f.n_levels == 3
        assert model_f.axis is None

    def test_model_factor_has_level_names(self):
        axes = {1: ["flat", "2tier"]}
        models = ["claude", "gpt-4o", "gemini"]
        factors = build_factors_from_axes(axes, models=models)
        model_f = [f for f in factors if f.name == "model"][0]
        assert model_f.level_names == ["claude", "gpt-4o", "gemini"]

    def test_single_model_no_factor(self):
        axes = {1: ["flat", "2tier"]}
        factors = build_factors_from_axes(axes, models=["claude"])
        assert len(factors) == 1  # no model factor

    def test_no_models_no_factor(self):
        axes = {1: ["flat", "2tier"]}
        factors = build_factors_from_axes(axes, models=None)
        assert len(factors) == 1

    def test_empty_models_no_factor(self):
        axes = {1: ["flat", "2tier"]}
        factors = build_factors_from_axes(axes, models=[])
        assert len(factors) == 1

    def test_axis_number_stored(self):
        axes = {5: ["a", "b", "c"]}
        factors = build_factors_from_axes(axes)
        assert factors[0].axis == 5

    def test_level_names_are_copies(self):
        original = ["flat", "2tier"]
        axes = {1: original}
        factors = build_factors_from_axes(axes)
        original.append("extra")
        assert factors[0].level_names == ["flat", "2tier"]


class TestBuildDesign:
    """Build a complete Taguchi experimental design from axes."""

    def test_design_has_rows(self):
        axes = {1: ["flat", "2tier", "3tier"], 2: ["path", "summary", "tokens"]}
        design = build_design(axes)
        assert design.n_runs > 0
        assert len(design.rows) == design.n_runs

    def test_rows_have_all_factors(self):
        axes = {1: ["a", "b", "c"], 2: ["x", "y"]}
        design = build_design(axes)
        for row in design.rows:
            assert "axis_1" in row.assignments
            assert "axis_2" in row.assignments

    def test_assignments_use_valid_names(self):
        axes = {1: ["flat", "2tier", "3tier"]}
        design = build_design(axes)
        for row in design.rows:
            assert row.assignments["axis_1"] in ["flat", "2tier", "3tier"]

    def test_design_with_models(self):
        axes = {1: ["flat", "2tier"]}
        design = build_design(axes, models=["claude", "gpt"])
        for row in design.rows:
            assert row.assignments["model"] in ["claude", "gpt"]

    def test_design_records_oa_name(self):
        axes = {1: ["a", "b"]}
        design = build_design(axes)
        assert design.oa_name is not None
        assert design.oa_name.startswith("L")

    def test_oa_override(self):
        axes = {1: ["a", "b", "c"]}
        design = build_design(axes, oa_override="L9")
        assert design.oa_name == "L9"
        assert design.n_runs == 9

    def test_run_ids_are_sequential(self):
        axes = {1: ["a", "b", "c"]}
        design = build_design(axes)
        ids = [r.run_id for r in design.rows]
        assert ids == list(range(1, len(ids) + 1))

    def test_design_stores_factors(self):
        axes = {1: ["a", "b"], 2: ["x", "y", "z"]}
        design = build_design(axes)
        assert len(design.factors) == 2

    def test_design_stores_level_counts(self):
        axes = {1: ["a", "b"], 2: ["x", "y", "z"]}
        design = build_design(axes)
        assert design.level_counts == [2, 3]


class TestDummyLevelExclusion:
    """Dummy-level handling when factor.n_levels < OA column levels."""

    def test_4_level_factor_on_5_level_column_marks_dummy(self):
        """A 4-level factor assigned to a 5-level column should produce
        dummy rows instead of wrapping via modular arithmetic."""
        # L25 has 6 five-level columns; a 4-level factor on a 5-level col
        # means OA values {0,1,2,3} map to real levels, value 4 is dummy.
        axes = {1: ["a", "b", "c", "d"]}
        design = build_design(axes, oa_override="L25")

        dummy_rows = [r for r in design.rows if "axis_1" in r.dummy_factors]
        non_dummy = [r for r in design.rows if "axis_1" not in r.dummy_factors]

        # L25 has 25 runs, 5 values per column, so 5 runs should be dummy
        assert len(dummy_rows) == 5
        assert len(non_dummy) == 20

        # Non-dummy rows should only use real level names
        for row in non_dummy:
            assert row.assignments["axis_1"] in ["a", "b", "c", "d"]

        # Dummy rows should have the DUMMY_LEVEL sentinel
        for row in dummy_rows:
            assert row.assignments["axis_1"] == DUMMY_LEVEL

    def test_3_level_factor_on_5_level_column_marks_2_dummy_levels(self):
        """A 3-level factor on a 5-level column → OA values 3,4 are dummy."""
        axes = {1: ["x", "y", "z"]}
        design = build_design(axes, oa_override="L25")

        dummy_rows = [r for r in design.rows if "axis_1" in r.dummy_factors]
        non_dummy = [r for r in design.rows if "axis_1" not in r.dummy_factors]

        # 2 dummy levels out of 5 → 2/5 of 25 = 10 dummy rows
        assert len(dummy_rows) == 10
        assert len(non_dummy) == 15

        for row in non_dummy:
            assert row.assignments["axis_1"] in ["x", "y", "z"]

    def test_matching_levels_no_dummies(self):
        """When factor.n_levels == column levels, no dummies are produced."""
        axes = {1: ["a", "b", "c", "d", "e"]}
        design = build_design(axes, oa_override="L25")

        dummy_rows = [r for r in design.rows if "axis_1" in r.dummy_factors]
        assert len(dummy_rows) == 0

    def test_non_dummy_rows_have_balanced_level_counts(self):
        """Non-dummy rows should have equal counts per real level (balanced)."""
        axes = {1: ["a", "b", "c", "d"]}
        design = build_design(axes, oa_override="L25")

        non_dummy = [r for r in design.rows if "axis_1" not in r.dummy_factors]
        level_counts = Counter(r.assignments["axis_1"] for r in non_dummy)

        # 20 non-dummy rows / 4 real levels = 5 per level
        assert all(count == 5 for count in level_counts.values())

    def test_mixed_factors_different_dummy_counts(self):
        """Different factors can have different dummy counts on the same design."""
        # 3-level and 4-level factors on L25 (5-level columns)
        axes = {1: ["a", "b", "c"], 2: ["w", "x", "y", "z"]}
        design = build_design(axes, oa_override="L25")

        dummy_axis1 = [r for r in design.rows if "axis_1" in r.dummy_factors]
        dummy_axis2 = [r for r in design.rows if "axis_2" in r.dummy_factors]

        # axis_1: 3 real out of 5 → 2 dummy values → 10 dummy rows
        assert len(dummy_axis1) == 10
        # axis_2: 4 real out of 5 → 1 dummy value → 5 dummy rows
        assert len(dummy_axis2) == 5

    def test_experiment_row_has_dummy_factors_attribute(self):
        """TaguchiExperimentRow must have a dummy_factors set attribute."""
        row = TaguchiExperimentRow(
            run_id=1,
            assignments={"axis_1": "a"},
        )
        assert hasattr(row, "dummy_factors")
        assert isinstance(row.dummy_factors, set)

    def test_main_effects_exclude_dummy_rows(self):
        """compute_main_effects should skip dummy-level rows for each factor."""
        axes = {1: ["a", "b", "c", "d"]}
        design = build_design(axes, oa_override="L25")

        # Give every row a distinct S/N so we can verify which rows are used
        sn_ratios = {row.run_id: float(row.run_id) for row in design.rows}

        effects = compute_main_effects(design, sn_ratios)

        # Only real levels should appear in the result
        assert set(effects["axis_1"].keys()) == {"a", "b", "c", "d"}
        assert DUMMY_LEVEL not in effects["axis_1"]

        # Each level should average exactly 5 rows (balanced)
        # Since we assigned sn=run_id, the average for each level should be
        # computable from the specific rows assigned to it
        for level_name, mean_sn in effects["axis_1"].items():
            matching_rows = [
                r for r in design.rows
                if r.assignments["axis_1"] == level_name
                and "axis_1" not in r.dummy_factors
            ]
            expected = sum(sn_ratios[r.run_id] for r in matching_rows) / len(matching_rows)
            assert mean_sn == pytest.approx(expected)

    def test_anova_excludes_dummy_rows(self):
        """run_anova should exclude dummy-level rows from its computation."""
        axes = {1: ["a", "b", "c", "d"]}
        design = build_design(axes, oa_override="L25")

        sn_ratios = {row.run_id: float(row.run_id) for row in design.rows}

        result = run_anova(design, sn_ratios)

        # ANOVA should have a factor result for axis_1
        assert len(result.factors) == 1
        assert result.factors[0].factor_name == "axis_1"

        # df should be n_levels - 1 = 3 (for the 4 real levels, not 5)
        assert result.factors[0].df == 3
