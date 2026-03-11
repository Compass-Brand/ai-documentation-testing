"""Tests for pipeline confirmation/refinement design (bugs #233, #234, #235).

Bug #233: Confirmation should test ONE combined optimal variant, not individual
          factor variants.
Bug #234: Refinement should use full factorial design, not one-factor-at-a-time.
Bug #235: Refinement should select factors by main effect S/N range, not by
          ANOVA significance.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agent_evals.pipeline import DOEPipeline, PhaseResult, PipelineConfig
from agent_evals.variants.composite import CompositeVariant


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_variant(axis: int, name: str) -> MagicMock:
    """Create a mock variant with given axis and name.

    Note: MagicMock(name=...) uses ``name`` as the mock's internal label,
    so we must set ``.name`` as a separate attribute after construction.
    """
    v = MagicMock()
    meta = MagicMock()
    meta.name = name
    meta.axis = axis
    meta.token_estimate = 100
    v.metadata.return_value = meta
    return v


def _make_orchestrator_result(
    n_trials: int = 5, score: float = 0.75,
) -> MagicMock:
    """Create a mock orchestrator result."""
    trial = MagicMock()
    trial.score = score
    trial.error = None
    trial.cost = 0.01
    trial.total_tokens = 100
    trial.variant_name = "composite"
    trial.metrics = {}
    result = MagicMock()
    result.run_id = "test-run"
    result.trials = [trial] * n_trials
    result.total_cost = 0.01 * n_trials
    result.total_tokens = 100 * n_trials
    result.elapsed_seconds = 1.0
    return result


def _make_pipeline(
    top_k: int = 2,
    confirmation_reps: int = 10,
) -> tuple[DOEPipeline, MagicMock]:
    """Build a DOEPipeline with a mock orchestrator."""
    config = PipelineConfig(
        models=["model-a"],
        top_k=top_k,
        confirmation_reps=confirmation_reps,
    )
    orch = MagicMock()
    orch.config = MagicMock()
    orch.config.eval_config = MagicMock()
    orch.store = None
    orch.run.return_value = _make_orchestrator_result()
    return DOEPipeline(config=config, orchestrator=orch), orch


# ===================================================================
# Bug #235 — Factor selection by main effect S/N range
# ===================================================================


class TestRankFactorsByEffectRange:
    """Refinement must select factors by main effect S/N range."""

    def test_returns_sorted_by_range_descending(self) -> None:
        """Factors are ordered by (max - min) of their level S/N means."""
        from agent_evals.taguchi.analysis import rank_factors_by_effect_range

        main_effects = {
            "axis_1": {"a": 10.0, "b": 12.0},       # range = 2
            "axis_2": {"x": 8.0, "y": 15.0},         # range = 7
            "axis_3": {"p": 9.0, "q": 10.0},         # range = 1
        }
        result = rank_factors_by_effect_range(main_effects)
        assert result == ["axis_2", "axis_1", "axis_3"]

    def test_excludes_specified_factors(self) -> None:
        """The model factor (or any named factor) can be excluded."""
        from agent_evals.taguchi.analysis import rank_factors_by_effect_range

        main_effects = {
            "axis_1": {"a": 10.0, "b": 12.0},
            "model": {"m1": 1.0, "m2": 20.0},  # biggest range but excluded
        }
        result = rank_factors_by_effect_range(
            main_effects, exclude_factors={"model"},
        )
        assert result == ["axis_1"]
        assert "model" not in result

    def test_skips_nan_levels(self) -> None:
        """NaN levels (unobserved) are excluded from range computation."""
        from agent_evals.taguchi.analysis import rank_factors_by_effect_range

        main_effects = {
            "axis_1": {"a": 10.0, "b": float("nan"), "c": 12.0},  # range = 2
            "axis_2": {"x": 5.0, "y": 15.0},                       # range = 10
        }
        result = rank_factors_by_effect_range(main_effects)
        assert result == ["axis_2", "axis_1"]

    def test_skips_single_level_factors(self) -> None:
        """Factors with only one observed level have no range and are skipped."""
        from agent_evals.taguchi.analysis import rank_factors_by_effect_range

        main_effects = {
            "axis_1": {"a": 10.0},            # 1 level, no range
            "axis_2": {"x": 5.0, "y": 15.0},  # range = 10
        }
        result = rank_factors_by_effect_range(main_effects)
        assert result == ["axis_2"]


class TestRefinementSelectsFactorsByRange:
    """Bug #235: run_refinement must use main effect range, not significance."""

    def test_selects_top_k_by_range_not_significance(self) -> None:
        """With top_k=2, pick the 2 factors with largest S/N range."""
        pipeline, orch = _make_pipeline(top_k=2)

        screening = PhaseResult(
            run_id="s1",
            phase="screening",
            trials=[],
            optimal={
                "axis_1": "a1_lv1",
                "axis_2": "a2_lv1",
                "axis_3": "a3_lv1",
            },
            main_effects={
                # axis_3 has the biggest range (10) — should be picked first
                "axis_3": {"a3_lv1": 5.0, "a3_lv2": 15.0},
                # axis_1 has the second biggest range (4) — picked second
                "axis_1": {"a1_lv1": 10.0, "a1_lv2": 14.0},
                # axis_2 has the smallest range (1) — NOT picked
                "axis_2": {"a2_lv1": 10.0, "a2_lv2": 11.0},
            },
            # significant_factors lists axis_2 first — old code would pick it
            significant_factors=["axis_2", "axis_1"],
        )

        variants = [
            _make_variant(1, "a1_lv1"),
            _make_variant(1, "a1_lv2"),
            _make_variant(2, "a2_lv1"),
            _make_variant(2, "a2_lv2"),
            _make_variant(3, "a3_lv1"),
            _make_variant(3, "a3_lv2"),
        ]

        with patch.object(pipeline, "_analyse_refinement") as mock_analyse:
            mock_analyse.return_value = {
                "main_effects": {},
                "anova": MagicMock(),
                "optimal": {},
                "predicted_sn": 10.0,
                "significant_factors": [],
                "interaction_effects": [],
            }
            pipeline.run_refinement(
                screening,
                tasks=[],
                variants=variants,
                doc_tree=MagicMock(),
            )

        # The orchestrator must receive variants involving axis_3 and axis_1
        # (the two factors with the largest ranges), NOT axis_2
        passed_variants = orch.run.call_args[0][1]
        passed_names = {v.metadata().name for v in passed_variants}
        # axis_2 variants must NOT appear as top-level varying factors
        assert "a2_lv2" not in passed_names or all(
            isinstance(v, CompositeVariant) for v in passed_variants
        )


# ===================================================================
# Bug #233 — Confirmation tests ONE combined optimal composite
# ===================================================================


class TestConfirmationComposite:
    """Confirmation must run a single CompositeVariant, not N individual ones."""

    def test_passes_single_composite_to_orchestrator(self) -> None:
        """run_confirmation creates one CompositeVariant with all optimal
        levels and passes it (not individual variants) to the orchestrator."""
        pipeline, orch = _make_pipeline()

        screening = PhaseResult(
            run_id="s1",
            phase="screening",
            trials=[],
            optimal={
                "axis_1": "nested",
                "axis_2": "verbose",
                "model": "model-a",
            },
            predicted_sn=10.0,
            prediction_interval=(8.0, 12.0),
            se_prediction=1.0,
        )

        variants = [
            _make_variant(1, "nested"),
            _make_variant(1, "flat"),
            _make_variant(2, "verbose"),
            _make_variant(2, "brief"),
        ]

        with patch("agent_evals.pipeline.validate_confirmation") as mock_val:
            mock_val.return_value = MagicMock(
                within_interval=True,
                sigma_deviation=0.5,
                observed_sn=10.2,
                predicted_sn=10.0,
                prediction_interval=(8.0, 12.0),
            )
            pipeline.run_confirmation(
                screening,
                tasks=[],
                variants=variants,
                doc_tree=MagicMock(),
            )

        # Orchestrator should receive exactly ONE variant
        passed_variants = orch.run.call_args[0][1]
        assert len(passed_variants) == 1, (
            f"Expected 1 composite variant, got {len(passed_variants)}"
        )

    def test_composite_is_correct_type(self) -> None:
        """The single variant passed is a CompositeVariant instance."""
        pipeline, orch = _make_pipeline()

        screening = PhaseResult(
            run_id="s1",
            phase="screening",
            trials=[],
            optimal={"axis_1": "nested", "axis_2": "verbose"},
            predicted_sn=10.0,
            prediction_interval=(8.0, 12.0),
            se_prediction=1.0,
        )

        variants = [
            _make_variant(1, "nested"),
            _make_variant(1, "flat"),
            _make_variant(2, "verbose"),
            _make_variant(2, "brief"),
        ]

        with patch("agent_evals.pipeline.validate_confirmation") as mock_val:
            mock_val.return_value = MagicMock(
                within_interval=True,
                sigma_deviation=0.5,
                observed_sn=10.2,
                predicted_sn=10.0,
                prediction_interval=(8.0, 12.0),
            )
            pipeline.run_confirmation(
                screening,
                tasks=[],
                variants=variants,
                doc_tree=MagicMock(),
            )

        passed_variants = orch.run.call_args[0][1]
        assert isinstance(passed_variants[0], CompositeVariant)

    def test_composite_contains_all_optimal_axes(self) -> None:
        """The composite has components for each optimal axis (not model)."""
        pipeline, orch = _make_pipeline()

        screening = PhaseResult(
            run_id="s1",
            phase="screening",
            trials=[],
            optimal={
                "axis_1": "nested",
                "axis_3": "tagged",
                "model": "model-a",
            },
            predicted_sn=10.0,
            prediction_interval=(8.0, 12.0),
            se_prediction=1.0,
        )

        v1 = _make_variant(1, "nested")
        v3 = _make_variant(3, "tagged")
        variants = [
            v1,
            _make_variant(1, "flat"),
            v3,
            _make_variant(3, "untagged"),
        ]

        with patch("agent_evals.pipeline.validate_confirmation") as mock_val:
            mock_val.return_value = MagicMock(
                within_interval=True,
                sigma_deviation=0.5,
                observed_sn=10.2,
                predicted_sn=10.0,
                prediction_interval=(8.0, 12.0),
            )
            pipeline.run_confirmation(
                screening,
                tasks=[],
                variants=variants,
                doc_tree=MagicMock(),
            )

        composite = orch.run.call_args[0][1][0]
        assert isinstance(composite, CompositeVariant)
        # Should have axis 1 and 3, NOT model
        assert 1 in composite._components
        assert 3 in composite._components


# ===================================================================
# Bug #234 — Refinement uses full factorial design
# ===================================================================


class TestRefinementFactorial:
    """Refinement must generate all factorial combinations, not OFAT."""

    def test_generates_full_factorial_grid(self) -> None:
        """2 factors × 3 levels each = 9 composite variants."""
        pipeline, orch = _make_pipeline(top_k=2)

        screening = PhaseResult(
            run_id="s1",
            phase="screening",
            trials=[],
            optimal={
                "axis_1": "a1_lv1",
                "axis_2": "a2_lv1",
            },
            main_effects={
                "axis_1": {"a1_lv1": 12.0, "a1_lv2": 10.0, "a1_lv3": 8.0},
                "axis_2": {"a2_lv1": 15.0, "a2_lv2": 10.0, "a2_lv3": 5.0},
            },
            significant_factors=["axis_1", "axis_2"],
        )

        variants = [
            _make_variant(1, "a1_lv1"),
            _make_variant(1, "a1_lv2"),
            _make_variant(1, "a1_lv3"),
            _make_variant(2, "a2_lv1"),
            _make_variant(2, "a2_lv2"),
            _make_variant(2, "a2_lv3"),
        ]

        with patch.object(pipeline, "_analyse_refinement") as mock_analyse:
            mock_analyse.return_value = {
                "main_effects": {},
                "anova": MagicMock(),
                "optimal": {},
                "predicted_sn": 10.0,
                "significant_factors": [],
                "interaction_effects": [],
            }
            pipeline.run_refinement(
                screening,
                tasks=[],
                variants=variants,
                doc_tree=MagicMock(),
            )

        passed_variants = orch.run.call_args[0][1]
        assert len(passed_variants) == 9, (
            f"Expected 3×3=9 factorial combos, got {len(passed_variants)}"
        )

    def test_all_factorial_variants_are_composites(self) -> None:
        """Every variant passed to orchestrator is a CompositeVariant."""
        pipeline, orch = _make_pipeline(top_k=2)

        screening = PhaseResult(
            run_id="s1",
            phase="screening",
            trials=[],
            optimal={"axis_1": "a1_lv1", "axis_2": "a2_lv1"},
            main_effects={
                "axis_1": {"a1_lv1": 12.0, "a1_lv2": 10.0},
                "axis_2": {"a2_lv1": 15.0, "a2_lv2": 10.0},
            },
            significant_factors=["axis_1", "axis_2"],
        )

        variants = [
            _make_variant(1, "a1_lv1"),
            _make_variant(1, "a1_lv2"),
            _make_variant(2, "a2_lv1"),
            _make_variant(2, "a2_lv2"),
        ]

        with patch.object(pipeline, "_analyse_refinement") as mock_analyse:
            mock_analyse.return_value = {
                "main_effects": {},
                "anova": MagicMock(),
                "optimal": {},
                "predicted_sn": 10.0,
                "significant_factors": [],
                "interaction_effects": [],
            }
            pipeline.run_refinement(
                screening,
                tasks=[],
                variants=variants,
                doc_tree=MagicMock(),
            )

        passed_variants = orch.run.call_args[0][1]
        for v in passed_variants:
            assert isinstance(v, CompositeVariant), (
                f"Expected CompositeVariant, got {type(v).__name__}"
            )

    def test_factorial_includes_fixed_axes_at_optimal(self) -> None:
        """Non-top-k axes are fixed at their screening optimal level."""
        pipeline, orch = _make_pipeline(top_k=1)

        screening = PhaseResult(
            run_id="s1",
            phase="screening",
            trials=[],
            optimal={
                "axis_1": "a1_lv1",
                "axis_2": "a2_lv1",  # axis_2 is fixed (not top-k)
            },
            main_effects={
                "axis_1": {"a1_lv1": 12.0, "a1_lv2": 8.0},  # range=4 (top)
                "axis_2": {"a2_lv1": 11.0, "a2_lv2": 10.0},  # range=1
            },
            significant_factors=["axis_1"],
        )

        v_a2_opt = _make_variant(2, "a2_lv1")  # the optimal/fixed variant
        variants = [
            _make_variant(1, "a1_lv1"),
            _make_variant(1, "a1_lv2"),
            v_a2_opt,
            _make_variant(2, "a2_lv2"),
        ]

        with patch.object(pipeline, "_analyse_refinement") as mock_analyse:
            mock_analyse.return_value = {
                "main_effects": {},
                "anova": MagicMock(),
                "optimal": {},
                "predicted_sn": 10.0,
                "significant_factors": [],
                "interaction_effects": [],
            }
            pipeline.run_refinement(
                screening,
                tasks=[],
                variants=variants,
                doc_tree=MagicMock(),
            )

        passed_variants = orch.run.call_args[0][1]
        # top_k=1 with axis_1 having 2 levels → 2 composites
        assert len(passed_variants) == 2
        # Each composite must include axis_2 at optimal level
        for composite in passed_variants:
            assert isinstance(composite, CompositeVariant)
            assert 2 in composite._components
            fixed_name = composite._components[2].metadata().name
            assert fixed_name == "a2_lv1", (
                f"axis_2 should be fixed at 'a2_lv1', got '{fixed_name}'"
            )

    def test_factorial_variant_names_are_unique(self) -> None:
        """Each factorial composite has a distinct metadata name."""
        pipeline, orch = _make_pipeline(top_k=2)

        screening = PhaseResult(
            run_id="s1",
            phase="screening",
            trials=[],
            optimal={"axis_1": "a1_lv1", "axis_2": "a2_lv1"},
            main_effects={
                "axis_1": {"a1_lv1": 12.0, "a1_lv2": 10.0},
                "axis_2": {"a2_lv1": 15.0, "a2_lv2": 10.0},
            },
            significant_factors=["axis_1", "axis_2"],
        )

        variants = [
            _make_variant(1, "a1_lv1"),
            _make_variant(1, "a1_lv2"),
            _make_variant(2, "a2_lv1"),
            _make_variant(2, "a2_lv2"),
        ]

        with patch.object(pipeline, "_analyse_refinement") as mock_analyse:
            mock_analyse.return_value = {
                "main_effects": {},
                "anova": MagicMock(),
                "optimal": {},
                "predicted_sn": 10.0,
                "significant_factors": [],
                "interaction_effects": [],
            }
            pipeline.run_refinement(
                screening,
                tasks=[],
                variants=variants,
                doc_tree=MagicMock(),
            )

        passed_variants = orch.run.call_args[0][1]
        names = [v.metadata().name for v in passed_variants]
        assert len(names) == len(set(names)), (
            f"Duplicate variant names: {names}"
        )


# ===================================================================
# Full factorial design builder
# ===================================================================


class TestBuildFactorialDesign:
    """Unit tests for the factorial design builder utility."""

    def test_two_factors_three_levels(self) -> None:
        """2 factors × 3 levels = 9 rows."""
        from agent_evals.taguchi.factors import build_factorial_design

        axes = {
            1: ["a", "b", "c"],
            2: ["x", "y", "z"],
        }
        design = build_factorial_design(axes)
        assert design.n_runs == 9
        assert len(design.rows) == 9
        assert len(design.factors) == 2

    def test_rows_cover_all_combinations(self) -> None:
        """Every level combination appears exactly once."""
        from agent_evals.taguchi.factors import build_factorial_design

        axes = {1: ["a", "b"], 2: ["x", "y"]}
        design = build_factorial_design(axes)

        combos = {
            (r.assignments["axis_1"], r.assignments["axis_2"])
            for r in design.rows
        }
        expected = {("a", "x"), ("a", "y"), ("b", "x"), ("b", "y")}
        assert combos == expected

    def test_no_dummy_factors(self) -> None:
        """Full factorial rows never have dummy factors."""
        from agent_evals.taguchi.factors import build_factorial_design

        axes = {1: ["a", "b", "c"], 2: ["x", "y"]}
        design = build_factorial_design(axes)
        for row in design.rows:
            assert not row.dummy_factors

    def test_oa_name_is_full_factorial(self) -> None:
        """Design is labelled as full_factorial, not an OA."""
        from agent_evals.taguchi.factors import build_factorial_design

        design = build_factorial_design({1: ["a", "b"]})
        assert design.oa_name == "full_factorial"
