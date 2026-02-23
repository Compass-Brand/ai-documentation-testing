"""Tests for Taguchi orthogonal array catalog and selection."""

from collections import Counter

import numpy as np
import pytest

from agent_evals.taguchi.catalog import (
    OrthogonalArray,
    get_available_arrays,
    get_oa,
    select_oa,
)


class TestOrthogonalArrayModel:
    """The OrthogonalArray dataclass stores array metadata and matrix."""

    def test_has_name_and_dimensions(self):
        oa = get_oa("L4")
        assert oa.name == "L4"
        assert oa.n_runs == 4
        assert oa.n_columns == 3

    def test_matrix_shape_matches_metadata(self):
        oa = get_oa("L4")
        assert oa.matrix.shape == (oa.n_runs, oa.n_columns)

    def test_matrix_dtype_is_int(self):
        oa = get_oa("L4")
        assert oa.matrix.dtype == np.int32

    def test_values_are_zero_indexed(self):
        oa = get_oa("L4")
        assert oa.matrix.min() == 0

    def test_values_within_level_bounds(self):
        oa = get_oa("L4")
        for col in range(oa.n_columns):
            col_max = oa.matrix[:, col].max()
            assert col_max < oa.column_levels(col)

    def test_column_levels_returns_correct_count(self):
        oa = get_oa("L18")
        assert oa.column_levels(0) == 2  # first column is 2-level
        assert oa.column_levels(1) == 3  # rest are 3-level

    def test_has_required_fields(self):
        oa = get_oa("L4")
        assert isinstance(oa.max_levels, int)
        assert isinstance(oa.matrix, np.ndarray)

    def test_matrix_values_below_max_levels(self):
        oa = get_oa("L4")
        assert oa.matrix.max() < oa.max_levels


class TestGetOA:
    """Retrieve specific OAs by name."""

    def test_l4_has_4_runs_2_levels(self):
        oa = get_oa("L4")
        assert oa.n_runs == 4
        assert oa.max_levels == 2

    def test_l8_has_8_runs_7_columns(self):
        oa = get_oa("L8")
        assert oa.n_runs == 8
        assert oa.n_columns == 7

    def test_l9_has_9_runs_3_levels(self):
        oa = get_oa("L9")
        assert oa.n_runs == 9
        assert oa.max_levels == 3

    def test_l12_has_12_runs_11_columns(self):
        oa = get_oa("L12")
        assert oa.n_runs == 12
        assert oa.n_columns == 11

    def test_l18_has_18_runs_8_columns(self):
        oa = get_oa("L18")
        assert oa.n_runs == 18
        assert oa.n_columns == 8

    def test_l25_has_25_runs_5_levels(self):
        oa = get_oa("L25")
        assert oa.n_runs == 25
        assert oa.max_levels == 5

    def test_l27_has_27_runs_13_columns(self):
        oa = get_oa("L27")
        assert oa.n_runs == 27
        assert oa.n_columns == 13

    def test_l36_has_36_runs_mixed_levels(self):
        oa = get_oa("L36")
        assert oa.n_runs == 36

    def test_l54_has_54_runs(self):
        oa = get_oa("L54")
        assert oa.n_runs == 54

    def test_l64_has_64_runs(self):
        oa = get_oa("L64")
        assert oa.n_runs == 64

    def test_unknown_oa_raises_keyerror(self):
        with pytest.raises(KeyError, match="L999"):
            get_oa("L999")


class TestGetAvailableArrays:
    """List all OAs in the catalog."""

    def test_returns_nonempty(self):
        arrays = get_available_arrays()
        assert len(arrays) >= 10

    def test_sorted_by_run_count(self):
        arrays = get_available_arrays()
        run_counts = [a.n_runs for a in arrays]
        assert run_counts == sorted(run_counts)

    def test_includes_key_arrays(self):
        names = {a.name for a in get_available_arrays()}
        for expected in ["L4", "L9", "L18", "L36", "L54", "L64", "L81"]:
            assert expected in names


class TestSelectOA:
    """Auto-select the smallest suitable OA for a factor-level structure."""

    def test_three_2level_factors_selects_small_oa(self):
        oa = select_oa([2, 2, 2])
        assert oa.n_runs <= 8
        assert oa.n_columns >= 3

    def test_four_3level_factors(self):
        oa = select_oa([3, 3, 3, 3])
        assert oa.n_runs <= 27
        assert oa.n_columns >= 4

    def test_mixed_levels(self):
        oa = select_oa([2, 3, 3, 2, 3])
        assert oa.n_runs <= 36
        assert oa.n_columns >= 5

    def test_real_10_axis_problem(self):
        levels = [5, 4, 5, 4, 5, 5, 4, 4, 3, 4]
        oa = select_oa(levels)
        assert oa.n_columns >= 10
        # Verify each column can hold its factor
        available = sorted(
            [oa.column_levels(i) for i in range(oa.n_columns)],
            reverse=True,
        )
        needed = sorted(levels, reverse=True)
        for a, n in zip(available, needed):
            assert a >= n

    def test_10_axes_plus_3_models(self):
        levels = [5, 4, 5, 4, 5, 5, 4, 4, 3, 4, 3]
        oa = select_oa(levels)
        assert oa.n_columns >= 11

    def test_impossible_request_raises(self):
        with pytest.raises(ValueError, match="No suitable"):
            select_oa([10] * 100)

    def test_oa_selection_reference_mappings(self):
        """Verify expected OA selections for common configurations."""
        # 1 model, 10 axes
        oa = select_oa([5, 4, 5, 4, 5, 5, 4, 4, 3, 4])
        assert oa.name in ("L36", "L50", "L54", "L64", "L81")

        # 3 models, 10 axes
        oa = select_oa([5, 4, 5, 4, 5, 5, 4, 4, 3, 4, 3])
        assert oa.name in ("L50", "L54", "L64", "L81")


class TestOrthogonalityProperty:
    """Verify the fundamental OA property: balanced level combinations."""

    def test_l9_pairwise_balance(self):
        oa = get_oa("L9")
        # For any two columns, every level pair appears equally often
        for c1 in range(oa.n_columns):
            for c2 in range(c1 + 1, oa.n_columns):
                pairs = list(zip(oa.matrix[:, c1], oa.matrix[:, c2]))
                counts = Counter(pairs)
                freq = list(counts.values())
                # All pair frequencies should be equal
                assert len(set(freq)) == 1, (
                    f"Columns ({c1},{c2}) not balanced: {counts}"
                )

    def test_l4_pairwise_balance(self):
        oa = get_oa("L4")
        for c1 in range(oa.n_columns):
            for c2 in range(c1 + 1, oa.n_columns):
                pairs = list(zip(oa.matrix[:, c1], oa.matrix[:, c2]))
                counts = Counter(pairs)
                freq = list(counts.values())
                assert len(set(freq)) == 1


class TestAllArraysValidity:
    """Verify all OAs in the catalog have valid matrix values."""

    def test_all_arrays_have_valid_shape(self):
        for oa in get_available_arrays():
            assert oa.matrix.shape == (oa.n_runs, oa.n_columns), (
                f"{oa.name} shape mismatch"
            )

    def test_all_arrays_have_zero_indexed_values(self):
        for oa in get_available_arrays():
            assert oa.matrix.min() >= 0, f"{oa.name} has negative values"

    def test_all_arrays_values_within_column_levels(self):
        for oa in get_available_arrays():
            for col in range(oa.n_columns):
                col_max = oa.matrix[:, col].max()
                assert col_max < oa.column_levels(col), (
                    f"{oa.name} col {col}: max={col_max} >= levels={oa.column_levels(col)}"
                )
