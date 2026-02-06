"""Tests for factorial design generator (Story 7.1)."""

from __future__ import annotations

import pytest
from agent_evals.factorial import (
    Factor,
    FactorialRun,
    PruningRule,
    apply_pruning,
    generate_fractional_factorial,
    generate_full_factorial,
    get_active_runs,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_five_factors() -> list[Factor]:
    """Create 5 factors representing top-2 candidates from axes 1-5."""
    return [
        Factor(name="A_structure", levels=("flat", "nested"), axis=1),
        Factor(name="B_format", levels=("json", "yaml"), axis=2),
        Factor(name="C_chunking", levels=("small", "large"), axis=3),
        Factor(name="D_metadata", levels=("minimal", "rich"), axis=4),
        Factor(name="E_ordering", levels=("alpha", "semantic"), axis=5),
    ]


def _make_three_factors() -> list[Factor]:
    return [
        Factor(name="X", levels=("lo", "hi"), axis=1),
        Factor(name="Y", levels=("lo", "hi"), axis=2),
        Factor(name="Z", levels=("lo", "hi"), axis=3),
    ]


# ---------------------------------------------------------------------------
# Fractional factorial
# ---------------------------------------------------------------------------

class TestFractionalFactorial:
    def test_generates_16_runs(self) -> None:
        factors = _make_five_factors()
        design = generate_fractional_factorial(factors)
        assert len(design.runs) == 16

    def test_n_runs_matches(self) -> None:
        design = generate_fractional_factorial(_make_five_factors())
        assert design.n_runs == 16

    def test_resolution_v(self) -> None:
        design = generate_fractional_factorial(_make_five_factors())
        assert design.resolution == "V"

    def test_generator_stored(self) -> None:
        design = generate_fractional_factorial(_make_five_factors())
        assert design.generator == "E=ABCD"

    def test_generator_e_equals_abcd(self) -> None:
        """E should equal the product of A, B, C, D in coded space.

        When an even number of the first 4 factors are at their low level
        (-1), the product is +1, otherwise -1.  We verify by mapping levels
        back to codes and checking the relation.
        """
        factors = _make_five_factors()
        design = generate_fractional_factorial(factors)

        # Build level-to-code lookup per factor
        level_to_code: dict[str, dict[str, int]] = {}
        for f in factors:
            level_to_code[f.name] = {f.levels[0]: -1, f.levels[1]: 1}

        for run in design.runs:
            codes = [
                level_to_code[f.name][run.factor_assignments[f.name]]
                for f in factors
            ]
            a, b, c, d, e = codes
            assert e == a * b * c * d, (
                f"Run {run.run_id}: E ({e}) != A*B*C*D ({a * b * c * d})"
            )

    def test_unique_factor_combinations(self) -> None:
        design = generate_fractional_factorial(_make_five_factors())
        combos = [
            tuple(sorted(run.factor_assignments.items())) for run in design.runs
        ]
        assert len(set(combos)) == 16

    def test_factor_assignments_use_level_names(self) -> None:
        factors = _make_five_factors()
        design = generate_fractional_factorial(factors)
        valid_levels = {f.name: set(f.levels) for f in factors}
        for run in design.runs:
            for fname, chosen in run.factor_assignments.items():
                assert chosen in valid_levels[fname], (
                    f"Run {run.run_id}: {fname}={chosen} not in {valid_levels[fname]}"
                )

    def test_run_ids_sequential(self) -> None:
        design = generate_fractional_factorial(_make_five_factors())
        ids = [run.run_id for run in design.runs]
        assert ids == list(range(1, 17))

    def test_requires_exactly_five_factors(self) -> None:
        with pytest.raises(ValueError, match="exactly 5"):
            generate_fractional_factorial(_make_three_factors())

    def test_rejects_six_factors(self) -> None:
        factors = _make_five_factors() + [
            Factor(name="F_extra", levels=("a", "b"), axis=6),
        ]
        with pytest.raises(ValueError, match="exactly 5"):
            generate_fractional_factorial(factors)

    def test_factors_preserved(self) -> None:
        factors = _make_five_factors()
        design = generate_fractional_factorial(factors)
        assert design.factors == factors


# ---------------------------------------------------------------------------
# Full factorial
# ---------------------------------------------------------------------------

class TestFullFactorial:
    def test_three_factors_gives_8_runs(self) -> None:
        design = generate_full_factorial(_make_three_factors())
        assert len(design.runs) == 8
        assert design.n_runs == 8

    def test_five_factors_gives_32_runs(self) -> None:
        design = generate_full_factorial(_make_five_factors())
        assert len(design.runs) == 32
        assert design.n_runs == 32

    def test_single_factor_gives_2_runs(self) -> None:
        factors = [Factor(name="A", levels=("lo", "hi"), axis=1)]
        design = generate_full_factorial(factors)
        assert len(design.runs) == 2

    def test_unique_combinations(self) -> None:
        factors = _make_three_factors()
        design = generate_full_factorial(factors)
        combos = [
            tuple(sorted(run.factor_assignments.items())) for run in design.runs
        ]
        assert len(set(combos)) == 8

    def test_resolution_is_full(self) -> None:
        design = generate_full_factorial(_make_three_factors())
        assert design.resolution == "full"

    def test_rejects_empty_factors(self) -> None:
        with pytest.raises(ValueError, match="At least one"):
            generate_full_factorial([])

    def test_level_names_correct(self) -> None:
        factors = _make_three_factors()
        design = generate_full_factorial(factors)
        valid = {f.name: set(f.levels) for f in factors}
        for run in design.runs:
            for fname, chosen in run.factor_assignments.items():
                assert chosen in valid[fname]


# ---------------------------------------------------------------------------
# Pruning
# ---------------------------------------------------------------------------

class TestPruning:
    def test_pruning_marks_runs_not_removes(self) -> None:
        design = generate_fractional_factorial(_make_five_factors())
        rule = PruningRule(
            description="YAML + flat excluded",
            check=lambda a: a["B_format"] == "yaml" and a["A_structure"] == "flat",
            reason="YAML requires hierarchy",
        )
        pruned = apply_pruning(design, [rule])
        # Total runs unchanged
        assert len(pruned.runs) == 16
        # At least one run is excluded
        assert any(r.excluded for r in pruned.runs)

    def test_excluded_runs_have_reason(self) -> None:
        design = generate_fractional_factorial(_make_five_factors())
        rule = PruningRule(
            description="test rule",
            check=lambda a: a["B_format"] == "yaml" and a["A_structure"] == "flat",
            reason="YAML requires hierarchy",
        )
        pruned = apply_pruning(design, [rule])
        for run in pruned.runs:
            if run.excluded:
                assert run.exclusion_reason == "YAML requires hierarchy"

    def test_non_matching_runs_not_excluded(self) -> None:
        design = generate_fractional_factorial(_make_five_factors())
        # Rule that matches nothing
        rule = PruningRule(
            description="impossible",
            check=lambda _a: False,
            reason="never",
        )
        pruned = apply_pruning(design, [rule])
        assert all(not r.excluded for r in pruned.runs)

    def test_multiple_rules(self) -> None:
        design = generate_fractional_factorial(_make_five_factors())
        r1 = PruningRule(
            description="rule 1",
            check=lambda a: a["A_structure"] == "flat" and a["B_format"] == "yaml",
            reason="reason 1",
        )
        r2 = PruningRule(
            description="rule 2",
            check=lambda a: a["C_chunking"] == "large" and a["D_metadata"] == "minimal",
            reason="reason 2",
        )
        pruned = apply_pruning(design, [r1, r2])
        excluded = [r for r in pruned.runs if r.excluded]
        assert len(excluded) >= 2  # Both rules should fire on some runs

    def test_pruning_preserves_run_ids(self) -> None:
        design = generate_fractional_factorial(_make_five_factors())
        rule = PruningRule(
            description="any yaml",
            check=lambda a: a["B_format"] == "yaml",
            reason="no yaml",
        )
        pruned = apply_pruning(design, [rule])
        original_ids = {r.run_id for r in design.runs}
        pruned_ids = {r.run_id for r in pruned.runs}
        assert original_ids == pruned_ids

    def test_already_excluded_stays_excluded(self) -> None:
        """Applying pruning to an already-pruned design keeps prior exclusions."""
        design = generate_fractional_factorial(_make_five_factors())
        r1 = PruningRule(
            description="rule 1",
            check=lambda a: a["A_structure"] == "flat" and a["B_format"] == "yaml",
            reason="first pass",
        )
        first_pass = apply_pruning(design, [r1])
        # Rule that matches nothing new
        r2 = PruningRule(
            description="noop",
            check=lambda _a: False,
            reason="noop",
        )
        second_pass = apply_pruning(first_pass, [r2])
        for run in second_pass.runs:
            orig = next(r for r in first_pass.runs if r.run_id == run.run_id)
            if orig.excluded:
                assert run.excluded
                assert run.exclusion_reason == "first pass"


# ---------------------------------------------------------------------------
# Active runs
# ---------------------------------------------------------------------------

class TestGetActiveRuns:
    def test_all_active_when_no_pruning(self) -> None:
        design = generate_fractional_factorial(_make_five_factors())
        active = get_active_runs(design)
        assert len(active) == 16

    def test_excludes_pruned_runs(self) -> None:
        design = generate_fractional_factorial(_make_five_factors())
        rule = PruningRule(
            description="prune yaml",
            check=lambda a: a["B_format"] == "yaml",
            reason="no yaml",
        )
        pruned = apply_pruning(design, [rule])
        active = get_active_runs(pruned)
        total_excluded = sum(1 for r in pruned.runs if r.excluded)
        assert len(active) == 16 - total_excluded
        assert all(not r.excluded for r in active)

    def test_returns_empty_when_all_pruned(self) -> None:
        design = generate_fractional_factorial(_make_five_factors())
        rule = PruningRule(
            description="exclude everything",
            check=lambda _a: True,
            reason="all gone",
        )
        pruned = apply_pruning(design, [rule])
        active = get_active_runs(pruned)
        assert active == []


# ---------------------------------------------------------------------------
# Data model basics
# ---------------------------------------------------------------------------

class TestDataModels:
    def test_factor_fields(self) -> None:
        f = Factor(name="A", levels=("lo", "hi"), axis=1)
        assert f.name == "A"
        assert f.levels == ("lo", "hi")
        assert f.axis == 1

    def test_factorial_run_defaults(self) -> None:
        run = FactorialRun(run_id=1, factor_assignments={"A": "lo"})
        assert run.excluded is False
        assert run.exclusion_reason == ""

    def test_pruning_rule_callable(self) -> None:
        rule = PruningRule(
            description="test",
            check=lambda a: a.get("x") == "bad",
            reason="bad x",
        )
        assert rule.check({"x": "bad"}) is True
        assert rule.check({"x": "good"}) is False
