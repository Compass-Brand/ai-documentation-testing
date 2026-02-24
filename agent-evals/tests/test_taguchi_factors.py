"""Tests for factor mapping from variant axes to Taguchi factors."""

import pytest

from agent_evals.taguchi.factors import (
    TaguchiDesign,
    TaguchiExperimentRow,
    TaguchiFactorDef,
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
