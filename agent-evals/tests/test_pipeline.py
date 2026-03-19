"""Tests for DOE pipeline data models and DOEPipeline orchestration."""

from unittest.mock import MagicMock, patch

import pytest
from agent_evals.pipeline import DOEPipeline, PhaseResult, PipelineConfig, PipelineResult


def test_pipeline_config_defaults():
    """PipelineConfig provides sensible defaults."""
    config = PipelineConfig(models=["model-a"])
    assert config.mode == "auto"
    assert config.quality_type == "larger_is_better"
    assert config.alpha == 0.05
    assert config.top_k == 3
    assert config.screening_reps == 3
    assert config.confirmation_reps == 5
    assert config.refinement_reps == 3


def test_pipeline_config_semi_mode():
    """PipelineConfig accepts semi mode."""
    config = PipelineConfig(models=["m"], mode="semi")
    assert config.mode == "semi"


def test_phase_result_stores_analysis():
    """PhaseResult holds run_id, phase, trials, and analysis data."""
    result = PhaseResult(
        run_id="r1",
        phase="screening",
        trials=[],
        total_cost=1.23,
        total_tokens=5000,
        elapsed_seconds=60.0,
        main_effects={"structure": {"flat": 10.0}},
        anova={"structure": {"p_value": 0.01}},
        optimal={"structure": "nested"},
        significant_factors=["structure"],
    )
    assert result.phase == "screening"
    assert result.main_effects["structure"]["flat"] == 10.0


def test_phase_result_confirmation_field():
    """PhaseResult can store confirmation data for Phase 2."""
    result = PhaseResult(
        run_id="r2",
        phase="confirmation",
        trials=[],
        total_cost=0.5,
        total_tokens=1000,
        elapsed_seconds=30.0,
        confirmation={"within_interval": True, "sigma_deviation": 0.3},
    )
    assert result.confirmation["within_interval"] is True


def test_pipeline_result_aggregates_phases():
    """PipelineResult holds all phases and the final optimal."""
    screening = PhaseResult(
        run_id="r1",
        phase="screening",
        trials=[],
        total_cost=10.0,
        total_tokens=50000,
        elapsed_seconds=300.0,
        significant_factors=["structure", "transform"],
    )
    pr = PipelineResult(
        pipeline_id="pipe-1",
        screening=screening,
        confirmation=None,
        refinement=None,
        final_optimal={"structure": "nested", "transform": "summary"},
        total_trials=150,
        total_cost=10.0,
        elapsed_seconds=300.0,
    )
    assert pr.pipeline_id == "pipe-1"
    assert pr.final_optimal["structure"] == "nested"


# ---------------------------------------------------------------------------
# Helpers for DOEPipeline tests
# ---------------------------------------------------------------------------


def _make_mock_orchestrator(score=0.5):
    """Create a mock orchestrator that returns predictable results."""
    orch = MagicMock()
    trial = MagicMock()
    trial.score = score
    trial.cost = 0.01
    trial.total_tokens = 100
    trial.metrics = {"oa_row_id": 0}
    result = MagicMock()
    result.run_id = "test-run"
    result.trials = [trial] * 50
    result.total_cost = 0.5
    result.total_tokens = 5000
    result.elapsed_seconds = 10.0
    result.raw_result = MagicMock()
    result.raw_result.design = MagicMock()
    orch.run.return_value = result
    return orch


def _make_variants():
    """Create mock variants with metadata for 5 axes, 3 levels each."""
    variants = []
    for axis in range(1, 6):
        for level in ["a", "b", "c"]:
            v = MagicMock()
            m = MagicMock()
            m.axis = axis
            m.name = f"axis{axis}_{level}"
            v.metadata.return_value = m
            variants.append(v)
    return variants


# ---------------------------------------------------------------------------
# DOEPipeline.run_screening tests
# ---------------------------------------------------------------------------


@patch("agent_evals.pipeline.predict_optimal")
@patch("agent_evals.pipeline.run_anova")
@patch("agent_evals.pipeline.compute_main_effects")
@patch("agent_evals.pipeline.compute_sn_ratios")
@patch("agent_evals.pipeline.build_design")
def test_pipeline_screening_builds_design(
    mock_build, mock_sn, mock_me, mock_anova, mock_pred
):
    """Phase 1 builds a TaguchiDesign from variant axes."""
    mock_build.return_value = MagicMock()
    mock_sn.return_value = {0: 10.0}
    mock_me.return_value = {}
    mock_anova.return_value = MagicMock(factors=[])
    mock_pred.return_value = MagicMock(optimal_assignment={})

    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)
    pipeline.run_screening(tasks=[], variants=_make_variants(), doc_tree=MagicMock())

    mock_build.assert_called_once()
    call_args = mock_build.call_args
    axes_arg = call_args[0][0] if call_args[0] else call_args[1]["axes"]
    # Should have 5 axes, each with 3 levels
    assert len(axes_arg) == 5
    for axis_num in range(1, 6):
        assert len(axes_arg[axis_num]) == 3


@patch("agent_evals.pipeline.predict_optimal")
@patch("agent_evals.pipeline.run_anova")
@patch("agent_evals.pipeline.compute_main_effects")
@patch("agent_evals.pipeline.compute_sn_ratios")
@patch("agent_evals.pipeline.build_design")
def test_pipeline_screening_returns_phase_result(
    mock_build, mock_sn, mock_me, mock_anova, mock_pred
):
    """Screening returns a PhaseResult with analysis data."""
    mock_build.return_value = MagicMock()
    mock_sn.return_value = {0: 10.0}
    mock_me.return_value = {"axis_1": {"a": 10.0, "b": 8.0}}
    mock_anova.return_value = MagicMock(factors=[])
    mock_pred.return_value = MagicMock(optimal_assignment={"axis_1": "a"})

    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)
    result = pipeline.run_screening(
        tasks=[], variants=_make_variants(), doc_tree=MagicMock()
    )

    assert isinstance(result, PhaseResult)
    assert result.phase == "screening"
    assert result.run_id == "test-run"
    assert result.total_cost == 0.5
    assert result.total_tokens == 5000
    assert result.elapsed_seconds == 10.0
    assert result.main_effects == {"axis_1": {"a": 10.0, "b": 8.0}}
    assert result.optimal == {"axis_1": "a"}


@patch("agent_evals.pipeline.predict_optimal")
@patch("agent_evals.pipeline.run_anova")
@patch("agent_evals.pipeline.compute_main_effects")
@patch("agent_evals.pipeline.compute_sn_ratios")
@patch("agent_evals.pipeline.build_design")
def test_pipeline_screening_identifies_significant_factors(
    mock_build, mock_sn, mock_me, mock_anova, mock_pred
):
    """Screening extracts factors with p < alpha, sorted by omega_squared."""
    mock_build.return_value = MagicMock()
    mock_sn.return_value = {0: 10.0}
    mock_me.return_value = {}
    mock_pred.return_value = MagicMock(optimal_assignment={})

    # Create ANOVA factors: two significant, one not
    sig_factor_1 = MagicMock()
    sig_factor_1.factor_name = "axis_1"
    sig_factor_1.p_value = 0.001
    sig_factor_1.corrected_p_value = 0.003
    sig_factor_1.omega_squared = 0.4

    sig_factor_2 = MagicMock()
    sig_factor_2.factor_name = "axis_3"
    sig_factor_2.p_value = 0.02
    sig_factor_2.corrected_p_value = 0.03
    sig_factor_2.omega_squared = 0.2

    nonsig_factor = MagicMock()
    nonsig_factor.factor_name = "axis_2"
    nonsig_factor.p_value = 0.15
    nonsig_factor.corrected_p_value = 0.15
    nonsig_factor.omega_squared = 0.05

    mock_anova.return_value = MagicMock(
        factors=[sig_factor_2, nonsig_factor, sig_factor_1]
    )

    config = PipelineConfig(models=["model-a"], alpha=0.05)
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)
    result = pipeline.run_screening(
        tasks=[], variants=_make_variants(), doc_tree=MagicMock()
    )

    # Should include only significant factors, sorted by omega_squared desc
    assert result.significant_factors == ["axis_1", "axis_3"]


# ---------------------------------------------------------------------------
# DOEPipeline.run_screening validation tests
# ---------------------------------------------------------------------------


def test_pipeline_screening_rejects_empty_variants():
    """run_screening raises ValueError when no variants are provided."""
    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    with pytest.raises(ValueError, match="axes"):
        pipeline.run_screening(tasks=[], variants=[], doc_tree=MagicMock())


def test_pipeline_screening_rejects_only_baseline_variants():
    """run_screening raises ValueError when all variants are axis 0 (baseline)."""
    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    # Create variants that are all axis 0
    baseline_variants = []
    for name in ["baseline_a", "baseline_b"]:
        v = MagicMock()
        m = MagicMock()
        m.axis = 0
        m.name = name
        v.metadata.return_value = m
        baseline_variants.append(v)

    with pytest.raises(ValueError, match="axes"):
        pipeline.run_screening(tasks=[], variants=baseline_variants, doc_tree=MagicMock())


@patch("agent_evals.pipeline.predict_optimal")
@patch("agent_evals.pipeline.run_anova")
@patch("agent_evals.pipeline.compute_main_effects")
@patch("agent_evals.pipeline.compute_sn_ratios")
@patch("agent_evals.pipeline.build_design")
def test_pipeline_screening_excludes_axis_0_from_design(
    mock_build, mock_sn, mock_me, mock_anova, mock_pred
):
    """run_screening must exclude axis 0 baselines from build_design call."""
    mock_build.return_value = MagicMock()
    mock_sn.return_value = {0: 10.0}
    mock_me.return_value = {}
    mock_anova.return_value = MagicMock(factors=[])
    mock_pred.return_value = MagicMock(optimal_assignment={})

    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    # Create variants with axis 0 baselines AND real axes
    variants = []
    for name in ["baseline_a", "baseline_b"]:
        v = MagicMock()
        m = MagicMock()
        m.axis = 0
        m.name = name
        v.metadata.return_value = m
        variants.append(v)
    # Add real axes (1 and 2, 2 levels each)
    for axis in [1, 2]:
        for level in ["x", "y"]:
            v = MagicMock()
            m = MagicMock()
            m.axis = axis
            m.name = f"axis{axis}_{level}"
            v.metadata.return_value = m
            variants.append(v)

    pipeline.run_screening(tasks=[], variants=variants, doc_tree=MagicMock())

    # build_design must NOT receive axis 0
    call_args = mock_build.call_args
    axes_arg = call_args[0][0]
    assert 0 not in axes_arg, (
        f"Axis 0 baselines should be excluded from build_design, got axes: {list(axes_arg.keys())}"
    )
    assert 1 in axes_arg
    assert 2 in axes_arg


def test_pipeline_screening_rejects_single_axis_single_level():
    """run_screening raises ValueError when only 1 axis has a single level."""
    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    v = MagicMock()
    m = MagicMock()
    m.axis = 1
    m.name = "axis1_a"
    v.metadata.return_value = m

    with pytest.raises(ValueError, match="axes"):
        pipeline.run_screening(tasks=[], variants=[v], doc_tree=MagicMock())


# ---------------------------------------------------------------------------
# DOEPipeline.run_confirmation tests
# ---------------------------------------------------------------------------


def test_pipeline_confirmation_returns_phase_result():
    """Phase 2 returns a PhaseResult with confirmation data."""
    config = PipelineConfig(models=["model-a"], confirmation_reps=5)
    orch = _make_mock_orchestrator(score=0.7)
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    screening = PhaseResult(
        run_id="r1",
        phase="screening",
        trials=[],
        optimal={"axis_1": "a", "axis_2": "b"},
        significant_factors=["axis_1", "axis_2"],
    )

    with patch("agent_evals.pipeline.validate_confirmation") as mock_val:
        mock_val.return_value = MagicMock(
            within_interval=True,
            sigma_deviation=0.3,
            observed_sn=11.5,
            predicted_sn=12.0,
            prediction_interval=(10.0, 14.0),
        )
        result = pipeline.run_confirmation(
            screening_result=screening,
            tasks=[],
            variants=_make_variants(),
            doc_tree=MagicMock(),
        )

    assert isinstance(result, PhaseResult)
    assert result.phase == "confirmation"
    assert result.confirmation is not None
    assert result.confirmation["within_interval"] is True


def test_pipeline_confirmation_filters_to_optimal_variants():
    """Bug #96/#233: Confirmation must pass a single CompositeVariant
    composed of all optimal levels, not individual variants.
    """
    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator(score=0.7)
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    # Screening says axis_1="axis1_a" and axis_2="axis2_b" are optimal
    screening = PhaseResult(
        run_id="r1",
        phase="screening",
        trials=[],
        optimal={"axis_1": "axis1_a", "axis_2": "axis2_b"},
        significant_factors=["axis_1", "axis_2"],
    )

    all_variants = _make_variants()  # 5 axes * 3 levels = 15 variants

    with patch("agent_evals.pipeline.validate_confirmation") as mock_val:
        mock_val.return_value = MagicMock(
            within_interval=True,
            sigma_deviation=0.3,
            observed_sn=11.5,
            predicted_sn=12.0,
            prediction_interval=(10.0, 14.0),
        )
        pipeline.run_confirmation(
            screening_result=screening,
            tasks=[],
            variants=all_variants,
            doc_tree=MagicMock(),
        )

    # Orchestrator should receive exactly 1 CompositeVariant (the combined optimal)
    call_kwargs = orch.run.call_args
    passed_variants = call_kwargs[1].get("variants") or call_kwargs[0][1]
    assert len(passed_variants) == 1, (
        f"Expected 1 CompositeVariant, got {len(passed_variants)} variants"
    )
    # The composite's name should contain both optimal level names
    composite_name = passed_variants[0].metadata().name
    assert "axis1_a" in composite_name, (
        f"Composite name should include axis1_a, got {composite_name}"
    )
    assert "axis2_b" in composite_name, (
        f"Composite name should include axis2_b, got {composite_name}"
    )


def test_pipeline_confirmation_passes_mode_full():
    """Phase 2 passes mode='full' to orchestrator to avoid Taguchi design requirement."""
    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator(score=0.7)
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    screening = PhaseResult(
        run_id="r1",
        phase="screening",
        trials=[],
        optimal={"axis_1": "a"},
        significant_factors=["axis_1"],
    )

    with patch("agent_evals.pipeline.validate_confirmation") as mock_val:
        mock_val.return_value = MagicMock(
            within_interval=True,
            sigma_deviation=0.3,
            observed_sn=11.5,
            predicted_sn=12.0,
            prediction_interval=(10.0, 14.0),
        )
        pipeline.run_confirmation(
            screening_result=screening,
            tasks=[],
            variants=_make_variants(),
            doc_tree=MagicMock(),
        )

    # Verify orchestrator.run() was called with mode="full"
    orch.run.assert_called_once()
    call_kwargs = orch.run.call_args
    assert call_kwargs.kwargs.get("mode") == "full"


def test_pipeline_refinement_passes_composites_in_full_mode():
    """Phase 3 passes CompositeVariants in mode='full' (full factorial)."""
    from agent_evals.variants.composite import CompositeVariant

    config = PipelineConfig(models=["model-a"], top_k=2)
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    screening = PhaseResult(
        run_id="r1",
        phase="screening",
        trials=[],
        optimal={"axis_1": "axis1_a", "axis_2": "axis2_a"},
        significant_factors=["axis_1", "axis_2"],
        main_effects={
            "axis_1": {"axis1_a": 12.0, "axis1_b": 10.0},
            "axis_2": {"axis2_a": 15.0, "axis2_b": 8.0},
        },
    )

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
            screening_result=screening,
            tasks=[],
            variants=_make_variants(),
            doc_tree=MagicMock(),
        )

    orch.run.assert_called_once()
    call_kwargs = orch.run.call_args
    assert call_kwargs.kwargs.get("mode") == "full", (
        "Refinement uses mode='full' with CompositeVariants"
    )
    passed_variants = call_kwargs.args[1]
    assert all(isinstance(v, CompositeVariant) for v in passed_variants), (
        "All variants must be CompositeVariant instances"
    )


def test_pipeline_confirmation_calls_validate():
    """Phase 2 calls validate_confirmation with optimal scores."""
    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator(score=0.8)
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    screening = PhaseResult(
        run_id="r1",
        phase="screening",
        trials=[],
        optimal={"axis_1": "a"},
        significant_factors=["axis_1"],
    )

    with patch("agent_evals.pipeline.validate_confirmation") as mock_val:
        mock_val.return_value = MagicMock(
            within_interval=False,
            sigma_deviation=2.1,
            observed_sn=8.0,
            predicted_sn=12.0,
            prediction_interval=(10.0, 14.0),
        )
        result = pipeline.run_confirmation(
            screening_result=screening,
            tasks=[],
            variants=_make_variants(),
            doc_tree=MagicMock(),
        )
        mock_val.assert_called_once()

    assert result.confirmation["within_interval"] is False


def test_pipeline_confirmation_uses_screening_predicted_sn():
    """Phase 2 must use the actual predicted_sn from screening, not 0.0."""
    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator(score=0.7)
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    screening = PhaseResult(
        run_id="r1",
        phase="screening",
        trials=[],
        optimal={"axis_1": "a"},
        significant_factors=["axis_1"],
        predicted_sn=15.3,
    )

    with patch("agent_evals.pipeline.validate_confirmation") as mock_val:
        mock_val.return_value = MagicMock(
            within_interval=True,
            sigma_deviation=0.5,
            observed_sn=14.8,
            predicted_sn=15.3,
            prediction_interval=(13.0, 17.6),
        )
        pipeline.run_confirmation(
            screening_result=screening,
            tasks=[],
            variants=_make_variants(),
            doc_tree=MagicMock(),
        )

        # The OptimalPrediction passed to validate_confirmation must have
        # predicted_sn=15.3 from screening, NOT 0.0
        prediction_arg = mock_val.call_args[0][0]
        assert prediction_arg.predicted_sn == 15.3, (
            f"Expected predicted_sn=15.3 from screening, got {prediction_arg.predicted_sn}"
        )


# ---------------------------------------------------------------------------
# DOEPipeline.run_refinement tests
# ---------------------------------------------------------------------------


def test_pipeline_refinement_filters_to_top_k_factor_variants():
    """Bug #96: Refinement must only use top-K factor axes (full factorial)."""
    from agent_evals.variants.composite import CompositeVariant

    config = PipelineConfig(models=["model-a"], top_k=2)
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    # axis_1 (range=4) and axis_3 (range=3) are top-2 by main effect range
    screening = PhaseResult(
        run_id="r1",
        phase="screening",
        trials=[],
        optimal={"axis_1": "axis1_a", "axis_2": "axis2_b", "axis_3": "axis3_c"},
        significant_factors=["axis_1", "axis_3", "axis_2"],
        main_effects={
            "axis_1": {"axis1_a": 12.0, "axis1_b": 10.0, "axis1_c": 8.0},
            "axis_2": {"axis2_a": 9.0, "axis2_b": 11.0, "axis2_c": 10.0},
            "axis_3": {"axis3_a": 8.5, "axis3_b": 10.5, "axis3_c": 11.5},
        },
    )

    all_variants = _make_variants()  # 5 axes * 3 levels = 15 variants

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
            screening_result=screening,
            tasks=[],
            variants=all_variants,
            doc_tree=MagicMock(),
        )

    call_kwargs = orch.run.call_args
    passed_variants = call_kwargs[1].get("variants") or call_kwargs[0][1]

    # All should be CompositeVariants (full factorial, not OFAT)
    assert all(isinstance(v, CompositeVariant) for v in passed_variants)

    # 3 levels × 3 levels = 9 full factorial combos (not 6 OFAT)
    assert len(passed_variants) == 9, (
        f"Expected 3×3=9 factorial combos for 2 top-K factors, "
        f"got {len(passed_variants)}"
    )


def test_pipeline_refinement_populates_analysis_fields():
    """Bug #140: Refinement must compute and return analysis like screening."""
    config = PipelineConfig(models=["model-a"], top_k=2)
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    screening = PhaseResult(
        run_id="r1",
        phase="screening",
        trials=[],
        optimal={"axis_1": "a", "axis_2": "b", "axis_3": "c"},
        significant_factors=["axis_1", "axis_3", "axis_2"],
        main_effects={
            "axis_1": {"a": 12.0, "b": 10.0, "c": 8.0},
            "axis_2": {"a": 9.0, "b": 11.0, "c": 10.0},
            "axis_3": {"a": 8.5, "b": 10.5, "c": 11.5},
        },
    )

    mock_main_fx = {"axis_1": {"a": 12.5, "b": 9.5, "c": 7.5}}
    mock_optimal_assignment = {"axis_1": "a"}

    with patch("agent_evals.pipeline.compute_sn_ratios") as mock_sn, \
         patch("agent_evals.pipeline.compute_main_effects") as mock_me, \
         patch("agent_evals.pipeline.run_anova") as mock_anova, \
         patch("agent_evals.pipeline.predict_optimal") as mock_pred:
        mock_sn.return_value = {0: 12.0}
        mock_me.return_value = mock_main_fx
        mock_anova.return_value = MagicMock(factors=[])
        mock_pred.return_value = MagicMock(
            optimal_assignment=mock_optimal_assignment,
            predicted_sn=12.5,
        )
        result = pipeline.run_refinement(
            screening_result=screening,
            tasks=[],
            variants=_make_variants(),
            doc_tree=MagicMock(),
        )

    assert result.main_effects == mock_main_fx, (
        f"Expected main_effects={mock_main_fx}, got {result.main_effects}"
    )
    assert result.anova is not None, "Refinement must populate anova"
    assert result.optimal == mock_optimal_assignment, (
        f"Expected optimal={mock_optimal_assignment}, got {result.optimal}"
    )
    assert result.predicted_sn == 12.5, (
        f"Expected predicted_sn=12.5, got {result.predicted_sn}"
    )


def test_pipeline_refinement_calls_analysis_functions():
    """Bug #140: Refinement must call compute_sn_ratios, main_effects, ANOVA."""
    config = PipelineConfig(models=["model-a"], top_k=2)
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    screening = PhaseResult(
        run_id="r1",
        phase="screening",
        trials=[],
        optimal={"axis_1": "a", "axis_3": "c"},
        significant_factors=["axis_1", "axis_3"],
    )

    with patch("agent_evals.pipeline.compute_sn_ratios") as mock_sn, \
         patch("agent_evals.pipeline.compute_main_effects") as mock_me, \
         patch("agent_evals.pipeline.run_anova") as mock_anova, \
         patch("agent_evals.pipeline.predict_optimal") as mock_pred:
        mock_sn.return_value = {0: 10.0}
        mock_me.return_value = {}
        mock_anova.return_value = MagicMock(factors=[])
        mock_pred.return_value = MagicMock(
            optimal_assignment={}, predicted_sn=0.0,
        )
        pipeline.run_refinement(
            screening_result=screening,
            tasks=[],
            variants=_make_variants(),
            doc_tree=MagicMock(),
        )

        mock_sn.assert_called_once()
        mock_me.assert_called_once()
        mock_anova.assert_called_once()
        mock_pred.assert_called_once()


def test_pipeline_refinement_returns_phase_result():
    """Phase 3 runs full factorial on top K factors."""
    config = PipelineConfig(models=["model-a"], top_k=2)
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    screening = PhaseResult(
        run_id="r1",
        phase="screening",
        trials=[],
        optimal={"axis_1": "a", "axis_2": "b", "axis_3": "c"},
        significant_factors=["axis_1", "axis_3", "axis_2"],
        main_effects={
            "axis_1": {"a": 12.0, "b": 10.0, "c": 8.0},
            "axis_2": {"a": 9.0, "b": 11.0, "c": 10.0},
            "axis_3": {"a": 8.5, "b": 10.5, "c": 11.5},
        },
    )

    with patch("agent_evals.pipeline.compute_sn_ratios"), \
         patch("agent_evals.pipeline.compute_main_effects") as mock_me, \
         patch("agent_evals.pipeline.run_anova") as mock_anova, \
         patch("agent_evals.pipeline.predict_optimal") as mock_pred:
        mock_me.return_value = {}
        mock_anova.return_value = MagicMock(factors=[])
        mock_pred.return_value = MagicMock(optimal_assignment={})
        result = pipeline.run_refinement(
            screening_result=screening,
            tasks=[],
            variants=_make_variants(),
            doc_tree=MagicMock(),
        )

    assert isinstance(result, PhaseResult)
    assert result.phase == "refinement"


# ---------------------------------------------------------------------------
# DOEPipeline.run() full pipeline tests
# ---------------------------------------------------------------------------


def test_pipeline_full_run_auto_mode():
    """Full pipeline in auto mode runs all three phases."""
    config = PipelineConfig(models=["model-a"], mode="auto")
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    with patch.object(pipeline, "run_screening") as mock_s, \
         patch.object(pipeline, "run_confirmation") as mock_c, \
         patch.object(pipeline, "run_refinement") as mock_r:
        mock_s.return_value = PhaseResult(
            run_id="r1", phase="screening", trials=[],
            significant_factors=["axis_1"], optimal={"axis_1": "a"},
            total_cost=1.0, elapsed_seconds=10.0,
        )
        mock_c.return_value = PhaseResult(
            run_id="r2", phase="confirmation", trials=[],
            confirmation={"within_interval": True},
            total_cost=0.5, elapsed_seconds=5.0,
        )
        mock_r.return_value = PhaseResult(
            run_id="r3", phase="refinement", trials=[],
            optimal={"axis_1": "a"},
            total_cost=2.0, elapsed_seconds=20.0,
        )
        result = pipeline.run(
            tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
        )
        mock_s.assert_called_once()
        mock_c.assert_called_once()
        mock_r.assert_called_once()
        assert isinstance(result, PipelineResult)
        assert result.pipeline_id == pipeline._pipeline_id


def test_pipeline_semi_mode_with_callback():
    """Semi mode calls phase_callback between phases."""
    approvals = []

    def approve_callback(phase_result):
        approvals.append(phase_result.phase)
        return True

    config = PipelineConfig(models=["model-a"], mode="semi")
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    with patch.object(pipeline, "run_screening") as mock_s, \
         patch.object(pipeline, "run_confirmation") as mock_c, \
         patch.object(pipeline, "run_refinement") as mock_r:
        mock_s.return_value = PhaseResult(
            run_id="r1", phase="screening", trials=[],
            significant_factors=["axis_1"], optimal={"axis_1": "a"},
        )
        mock_c.return_value = PhaseResult(
            run_id="r2", phase="confirmation", trials=[],
            confirmation={"within_interval": True},
        )
        mock_r.return_value = PhaseResult(
            run_id="r3", phase="refinement", trials=[],
        )
        pipeline.run(
            tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
            phase_callback=approve_callback,
        )
        assert "screening" in approvals
        assert "confirmation" in approvals


def test_pipeline_semi_mode_stops_on_rejection():
    """Semi mode stops when callback returns False."""
    config = PipelineConfig(models=["model-a"], mode="semi")
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    with patch.object(pipeline, "run_screening") as mock_s, \
         patch.object(pipeline, "run_confirmation") as mock_c, \
         patch.object(pipeline, "run_refinement") as mock_r:
        mock_s.return_value = PhaseResult(
            run_id="r1", phase="screening", trials=[],
            significant_factors=["axis_1"], optimal={"axis_1": "a"},
        )
        result = pipeline.run(
            tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
            phase_callback=lambda pr: False,  # reject after screening
        )
        mock_s.assert_called_once()
        mock_c.assert_not_called()
        mock_r.assert_not_called()
        assert result.confirmation is None
        assert result.refinement is None


# ---------------------------------------------------------------------------
# Per-phase repetition count tests (bead #99)
# ---------------------------------------------------------------------------


@patch("agent_evals.pipeline.predict_optimal")
@patch("agent_evals.pipeline.run_anova")
@patch("agent_evals.pipeline.compute_main_effects")
@patch("agent_evals.pipeline.compute_sn_ratios")
@patch("agent_evals.pipeline.build_design")
def test_pipeline_screening_applies_screening_reps(
    mock_build, mock_sn, mock_me, mock_anova, mock_pred
):
    """run_screening sets eval_config.repetitions to screening_reps."""
    from agent_evals.runner import EvalRunConfig

    mock_build.return_value = MagicMock()
    mock_sn.return_value = {0: 10.0}
    mock_me.return_value = {}
    mock_anova.return_value = MagicMock(factors=[])
    mock_pred.return_value = MagicMock(optimal_assignment={})

    config = PipelineConfig(models=["model-a"], screening_reps=5)
    orch = _make_mock_orchestrator()

    # Give orchestrator a real EvalRunConfig to verify rep override
    eval_cfg = EvalRunConfig(repetitions=1)
    orch.config = MagicMock()
    orch.config.eval_config = eval_cfg

    pipeline = DOEPipeline(config=config, orchestrator=orch)
    pipeline.run_screening(tasks=[], variants=_make_variants(), doc_tree=MagicMock())

    assert eval_cfg.repetitions == 5


def test_pipeline_confirmation_applies_confirmation_reps():
    """run_confirmation sets eval_config.repetitions to confirmation_reps."""
    from agent_evals.runner import EvalRunConfig

    config = PipelineConfig(models=["model-a"], confirmation_reps=7)
    orch = _make_mock_orchestrator(score=0.7)

    eval_cfg = EvalRunConfig(repetitions=1)
    orch.config = MagicMock()
    orch.config.eval_config = eval_cfg

    pipeline = DOEPipeline(config=config, orchestrator=orch)

    screening = PhaseResult(
        run_id="r1", phase="screening", trials=[],
        optimal={"axis_1": "a"}, significant_factors=["axis_1"],
        predicted_sn=12.0,
    )

    with patch("agent_evals.pipeline.validate_confirmation") as mock_val:
        mock_val.return_value = MagicMock(
            within_interval=True, sigma_deviation=0.3,
            observed_sn=11.5, predicted_sn=12.0,
            prediction_interval=(10.0, 14.0),
        )
        pipeline.run_confirmation(
            screening_result=screening, tasks=[],
            variants=_make_variants(), doc_tree=MagicMock(),
        )

    assert eval_cfg.repetitions == 7


def test_pipeline_refinement_applies_refinement_reps():
    """run_refinement sets eval_config.repetitions to refinement_reps."""
    from agent_evals.runner import EvalRunConfig

    config = PipelineConfig(models=["model-a"], refinement_reps=9)
    orch = _make_mock_orchestrator()

    eval_cfg = EvalRunConfig(repetitions=1)
    orch.config = MagicMock()
    orch.config.eval_config = eval_cfg

    pipeline = DOEPipeline(config=config, orchestrator=orch)

    screening = PhaseResult(
        run_id="r1", phase="screening", trials=[],
        optimal={"axis_1": "a"}, significant_factors=["axis_1"],
    )

    with patch("agent_evals.pipeline.compute_sn_ratios") as mock_sn, \
         patch("agent_evals.pipeline.compute_main_effects") as mock_me, \
         patch("agent_evals.pipeline.run_anova") as mock_anova, \
         patch("agent_evals.pipeline.predict_optimal") as mock_pred:
        mock_sn.return_value = {0: 10.0}
        mock_me.return_value = {}
        mock_anova.return_value = MagicMock(factors=[])
        mock_pred.return_value = MagicMock(
            optimal_assignment={}, predicted_sn=0.0,
        )
        pipeline.run_refinement(
            screening_result=screening, tasks=[],
            variants=_make_variants(), doc_tree=MagicMock(),
        )

    assert eval_cfg.repetitions == 9


# ---------------------------------------------------------------------------
# Bug #122: Refinement computes 2-way interaction effects
# ---------------------------------------------------------------------------


def test_pipeline_refinement_calls_compute_interactions():
    """Bug #122: Refinement must call compute_interactions for 2-way effects."""
    config = PipelineConfig(models=["model-a"], top_k=2)
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    screening = PhaseResult(
        run_id="r1",
        phase="screening",
        trials=[],
        optimal={"axis_1": "a", "axis_3": "c"},
        significant_factors=["axis_1", "axis_3"],
    )

    with patch("agent_evals.pipeline.build_design") as mock_build, \
         patch("agent_evals.pipeline.compute_sn_ratios") as mock_sn, \
         patch("agent_evals.pipeline.compute_main_effects") as mock_me, \
         patch("agent_evals.pipeline.run_anova") as mock_anova, \
         patch("agent_evals.pipeline.predict_optimal") as mock_pred, \
         patch("agent_evals.pipeline.compute_interactions") as mock_interactions:

        mock_row = MagicMock()
        mock_row.run_id = 1
        mock_row.assignments = {"axis_1": "a", "axis_3": "c"}
        mock_row.dummy_factors = set()
        mock_design = MagicMock()
        mock_design.rows = [mock_row]
        mock_design.factors = []
        mock_build.return_value = mock_design

        mock_sn.return_value = {1: 10.0}
        mock_me.return_value = {}
        mock_anova.return_value = MagicMock(factors=[])
        mock_pred.return_value = MagicMock(
            optimal_assignment={}, predicted_sn=0.0,
        )
        mock_interactions.return_value = []

        pipeline.run_refinement(
            screening_result=screening,
            tasks=[],
            variants=_make_variants(),
            doc_tree=MagicMock(),
        )

        mock_interactions.assert_called_once()


def test_pipeline_refinement_populates_interaction_effects():
    """Bug #122: Refinement PhaseResult must contain interaction_effects."""
    from agent_evals.taguchi.analysis import InteractionEffect

    config = PipelineConfig(models=["model-a"], top_k=2)
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    screening = PhaseResult(
        run_id="r1",
        phase="screening",
        trials=[],
        optimal={"axis_1": "a", "axis_3": "c"},
        significant_factors=["axis_1", "axis_3"],
    )

    fake_interaction = InteractionEffect(
        factor1="axis_1", factor2="axis_3",
        ss=2.5, df=4, ms=0.625, f_ratio=3.1, p_value=0.04,
    )

    with patch("agent_evals.pipeline.build_design") as mock_build, \
         patch("agent_evals.pipeline.compute_sn_ratios") as mock_sn, \
         patch("agent_evals.pipeline.compute_main_effects") as mock_me, \
         patch("agent_evals.pipeline.run_anova") as mock_anova, \
         patch("agent_evals.pipeline.predict_optimal") as mock_pred, \
         patch("agent_evals.pipeline.compute_interactions") as mock_interactions:

        mock_row = MagicMock()
        mock_row.run_id = 1
        mock_row.assignments = {"axis_1": "a", "axis_3": "c"}
        mock_row.dummy_factors = set()
        mock_design = MagicMock()
        mock_design.rows = [mock_row]
        mock_design.factors = []
        mock_build.return_value = mock_design

        mock_sn.return_value = {1: 10.0}
        mock_me.return_value = {}
        mock_anova.return_value = MagicMock(factors=[])
        mock_pred.return_value = MagicMock(
            optimal_assignment={}, predicted_sn=0.0,
        )
        mock_interactions.return_value = [fake_interaction]

        result = pipeline.run_refinement(
            screening_result=screening,
            tasks=[],
            variants=_make_variants(),
            doc_tree=MagicMock(),
        )

    assert len(result.interaction_effects) == 1
    assert result.interaction_effects[0]["factor1"] == "axis_1"
    assert result.interaction_effects[0]["factor2"] == "axis_3"
    assert result.interaction_effects[0]["p_value"] == 0.04


def test_pipeline_refinement_stores_interactions_to_observatory():
    """Bug #122: Refinement must persist interaction_effects to the store."""
    config = PipelineConfig(models=["model-a"], top_k=2)
    orch = _make_mock_orchestrator()
    mock_store = MagicMock()
    pipeline = DOEPipeline(config=config, orchestrator=orch)
    pipeline._store = mock_store

    screening = PhaseResult(
        run_id="r1",
        phase="screening",
        trials=[],
        optimal={"axis_1": "a", "axis_3": "c"},
        significant_factors=["axis_1", "axis_3"],
    )

    with patch("agent_evals.pipeline.build_design") as mock_build, \
         patch("agent_evals.pipeline.compute_sn_ratios") as mock_sn, \
         patch("agent_evals.pipeline.compute_main_effects") as mock_me, \
         patch("agent_evals.pipeline.run_anova") as mock_anova, \
         patch("agent_evals.pipeline.predict_optimal") as mock_pred, \
         patch("agent_evals.pipeline.compute_interactions") as mock_interactions:

        mock_row = MagicMock()
        mock_row.run_id = 1
        mock_row.assignments = {"axis_1": "a", "axis_3": "c"}
        mock_row.dummy_factors = set()
        mock_design = MagicMock()
        mock_design.rows = [mock_row]
        mock_design.factors = []
        mock_build.return_value = mock_design

        mock_sn.return_value = {1: 10.0}
        mock_me.return_value = {}
        mock_anova.return_value = MagicMock(factors=[])
        mock_pred.return_value = MagicMock(
            optimal_assignment={}, predicted_sn=0.0,
        )
        mock_interactions.return_value = []

        pipeline.run_refinement(
            screening_result=screening,
            tasks=[],
            variants=_make_variants(),
            doc_tree=MagicMock(),
        )

    mock_store.save_phase_results.assert_called_once()
    call_kwargs = mock_store.save_phase_results.call_args[1]
    assert "interaction_effects" in call_kwargs


# ---------------------------------------------------------------------------
# Bug #111: Resume loads trial aggregates from store
# ---------------------------------------------------------------------------


def _make_mock_store_for_resume():
    """Create a mock store with completed pipeline runs and phase results."""
    store = MagicMock()

    # Three completed runs for the pipeline
    screening_run = MagicMock()
    screening_run.run_id = "screen-run-1"
    screening_run.status = "completed"
    screening_run.phase = "screening"
    screening_run.total_trials = 50
    screening_run.total_cost = 1.25

    confirmation_run = MagicMock()
    confirmation_run.run_id = "conf-run-1"
    confirmation_run.status = "completed"
    confirmation_run.phase = "confirmation"
    confirmation_run.total_trials = 20
    confirmation_run.total_cost = 0.50

    refinement_run = MagicMock()
    refinement_run.run_id = "ref-run-1"
    refinement_run.status = "completed"
    refinement_run.phase = "refinement"
    refinement_run.total_trials = 30
    refinement_run.total_cost = 0.75

    store.get_pipeline_runs.return_value = [
        screening_run, confirmation_run, refinement_run,
    ]

    # Phase results with cost/token data
    def _get_phase_results(run_id):
        data = {
            "screen-run-1": {
                "main_effects": {"axis_1": {"a": 12.0}},
                "anova": {},
                "optimal": {"axis_1": "a"},
                "significant_factors": ["axis_1"],
                "total_cost": 1.25,
                "total_tokens": 50000,
                "elapsed_seconds": 120.0,
                "interaction_effects": [],
            },
            "conf-run-1": {
                "main_effects": None,
                "anova": None,
                "optimal": None,
                "significant_factors": [],
                "total_cost": 0.50,
                "total_tokens": 20000,
                "elapsed_seconds": 45.0,
                "interaction_effects": [],
            },
            "ref-run-1": {
                "main_effects": {"axis_1": {"a": 13.0}},
                "anova": {},
                "optimal": {"axis_1": "a"},
                "significant_factors": ["axis_1"],
                "total_cost": 0.75,
                "total_tokens": 30000,
                "elapsed_seconds": 90.0,
                "interaction_effects": [],
            },
        }
        return data.get(run_id)

    store.get_phase_results.side_effect = _get_phase_results

    # Run summaries for trial counts
    def _get_run_summary(run_id):
        summaries = {
            "screen-run-1": screening_run,
            "conf-run-1": confirmation_run,
            "ref-run-1": refinement_run,
        }
        return summaries.get(run_id)

    store.get_run_summary.side_effect = _get_run_summary

    return store


def test_pipeline_resume_loads_screening_cost_data():
    """Bug #111: Resumed screening phase must load cost/token data from store."""
    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    store = _make_mock_store_for_resume()
    orch.store = store

    pipeline = DOEPipeline(
        config=config, orchestrator=orch, pipeline_id="test-pipe",
    )
    pipeline._store = store

    result = pipeline.run(
        tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
    )

    # Screening was completed - its cost data should come from the store
    assert result.screening.total_cost == 1.25, (
        f"Expected screening total_cost=1.25, got {result.screening.total_cost}"
    )
    assert result.screening.total_tokens == 50000, (
        f"Expected screening total_tokens=50000, got {result.screening.total_tokens}"
    )
    assert result.screening.elapsed_seconds == 120.0, (
        f"Expected screening elapsed_seconds=120.0, got {result.screening.elapsed_seconds}"
    )


def test_pipeline_resume_loads_confirmation_cost_data():
    """Bug #111: Resumed confirmation phase must load cost/token data from store."""
    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    store = _make_mock_store_for_resume()
    orch.store = store

    pipeline = DOEPipeline(
        config=config, orchestrator=orch, pipeline_id="test-pipe",
    )
    pipeline._store = store

    result = pipeline.run(
        tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
    )

    assert result.confirmation is not None
    assert result.confirmation.total_cost == 0.50, (
        f"Expected confirmation total_cost=0.50, got {result.confirmation.total_cost}"
    )
    assert result.confirmation.total_tokens == 20000, (
        f"Expected confirmation total_tokens=20000, got {result.confirmation.total_tokens}"
    )
    assert result.confirmation.elapsed_seconds == 45.0, (
        f"Expected confirmation elapsed_seconds=45.0, got {result.confirmation.elapsed_seconds}"
    )


def test_pipeline_resume_loads_refinement_cost_data():
    """Bug #111: Resumed refinement phase must load cost/token data from store."""
    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    store = _make_mock_store_for_resume()
    orch.store = store

    pipeline = DOEPipeline(
        config=config, orchestrator=orch, pipeline_id="test-pipe",
    )
    pipeline._store = store

    result = pipeline.run(
        tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
    )

    assert result.refinement is not None
    assert result.refinement.total_cost == 0.75, (
        f"Expected refinement total_cost=0.75, got {result.refinement.total_cost}"
    )
    assert result.refinement.total_tokens == 30000, (
        f"Expected refinement total_tokens=30000, got {result.refinement.total_tokens}"
    )
    assert result.refinement.elapsed_seconds == 90.0, (
        f"Expected refinement elapsed_seconds=90.0, got {result.refinement.elapsed_seconds}"
    )


def test_pipeline_resume_aggregates_total_cost():
    """Bug #111: PipelineResult totals must reflect all resumed phase costs."""
    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    store = _make_mock_store_for_resume()
    orch.store = store

    pipeline = DOEPipeline(
        config=config, orchestrator=orch, pipeline_id="test-pipe",
    )
    pipeline._store = store

    result = pipeline.run(
        tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
    )

    # Total cost should be sum of all three phases: 1.25 + 0.50 + 0.75 = 2.50
    assert result.total_cost == pytest.approx(2.50), (
        f"Expected total_cost=2.50, got {result.total_cost}"
    )
    assert result.elapsed_seconds == pytest.approx(255.0), (
        f"Expected elapsed_seconds=255.0, got {result.elapsed_seconds}"
    )


# ---------------------------------------------------------------------------
# Bug #205: Pipeline resume must restore predicted_sn from store
# Bug #189: Pipeline resume must restore prediction_interval and se_prediction
# ---------------------------------------------------------------------------


def _make_mock_store_for_resume_with_predictions():
    """Create a mock store with predicted_sn, prediction_interval, se_prediction."""
    store = MagicMock()

    screening_run = MagicMock()
    screening_run.run_id = "screen-run-1"
    screening_run.status = "completed"
    screening_run.phase = "screening"

    confirmation_run = MagicMock()
    confirmation_run.run_id = "conf-run-1"
    confirmation_run.status = "completed"
    confirmation_run.phase = "confirmation"

    refinement_run = MagicMock()
    refinement_run.run_id = "ref-run-1"
    refinement_run.status = "completed"
    refinement_run.phase = "refinement"

    store.get_pipeline_runs.return_value = [
        screening_run, confirmation_run, refinement_run,
    ]

    def _get_phase_results(run_id):
        data = {
            "screen-run-1": {
                "main_effects": {"axis_1": {"a": 12.0}},
                "anova": {},
                "optimal": {"axis_1": "a"},
                "significant_factors": ["axis_1"],
                "total_cost": 1.25,
                "total_tokens": 50000,
                "elapsed_seconds": 120.0,
                "interaction_effects": [],
                "predicted_sn": 7.42,
                "prediction_interval": [5.1, 9.7],
                "se_prediction": 1.15,
            },
            "conf-run-1": {
                "main_effects": None,
                "anova": None,
                "optimal": None,
                "significant_factors": [],
                "total_cost": 0.50,
                "total_tokens": 20000,
                "elapsed_seconds": 45.0,
                "interaction_effects": [],
                "predicted_sn": None,
                "prediction_interval": None,
                "se_prediction": None,
            },
            "ref-run-1": {
                "main_effects": {"axis_1": {"a": 13.0}},
                "anova": {},
                "optimal": {"axis_1": "a"},
                "significant_factors": ["axis_1"],
                "total_cost": 0.75,
                "total_tokens": 30000,
                "elapsed_seconds": 90.0,
                "interaction_effects": [],
                "predicted_sn": 8.1,
                "prediction_interval": None,
                "se_prediction": None,
            },
        }
        return data.get(run_id)

    store.get_phase_results.side_effect = _get_phase_results
    store.get_run_summary.side_effect = lambda rid: {
        "screen-run-1": screening_run,
        "conf-run-1": confirmation_run,
        "ref-run-1": refinement_run,
    }.get(rid)

    return store


def test_pipeline_resume_restores_predicted_sn():
    """Bug #205: predicted_sn must be restored from DB on pipeline resume."""
    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    store = _make_mock_store_for_resume_with_predictions()
    orch.store = store

    pipeline = DOEPipeline(
        config=config, orchestrator=orch, pipeline_id="test-pipe",
    )
    pipeline._store = store

    result = pipeline.run(
        tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
    )

    assert result.screening.predicted_sn == pytest.approx(7.42), (
        f"Expected predicted_sn=7.42, got {result.screening.predicted_sn}"
    )


def test_pipeline_resume_restores_prediction_interval():
    """Bug #189: prediction_interval and se_prediction must be restored on resume."""
    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    store = _make_mock_store_for_resume_with_predictions()
    orch.store = store

    pipeline = DOEPipeline(
        config=config, orchestrator=orch, pipeline_id="test-pipe",
    )
    pipeline._store = store

    result = pipeline.run(
        tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
    )

    assert result.screening.prediction_interval == pytest.approx([5.1, 9.7]), (
        f"Expected prediction_interval=[5.1, 9.7], got {result.screening.prediction_interval}"
    )
    assert result.screening.se_prediction == pytest.approx(1.15), (
        f"Expected se_prediction=1.15, got {result.screening.se_prediction}"
    )


# ---------------------------------------------------------------------------
# Resume trial count and confirmation persistence
# ---------------------------------------------------------------------------


def test_pipeline_resume_aggregates_total_trials():
    """Resumed pipeline must report correct total_trials from DB, not len([])."""
    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    store = _make_mock_store_for_resume()
    orch.store = store

    pipeline = DOEPipeline(
        config=config, orchestrator=orch, pipeline_id="test-pipe",
    )
    pipeline._store = store

    result = pipeline.run(
        tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
    )

    # Mock store has screening=50, confirmation=20, refinement=30 total_trials
    assert result.total_trials == 100, (
        f"Expected total_trials=100, got {result.total_trials}"
    )


def test_pipeline_resume_populates_trial_count_field():
    """Bug #227: Resumed PhaseResult must have trial_count set from DB."""
    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    store = _make_mock_store_for_resume()
    orch.store = store

    pipeline = DOEPipeline(
        config=config, orchestrator=orch, pipeline_id="test-pipe",
    )
    pipeline._store = store

    result = pipeline.run(
        tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
    )

    # Resumed phases have trials=[] but trial_count should be populated
    assert result.screening.trials == []
    assert result.screening.trial_count == 50, (
        f"Expected trial_count=50, got {result.screening.trial_count}"
    )
    assert result.confirmation.trial_count == 20
    assert result.refinement.trial_count == 30


def test_phase_result_trial_count_defaults_to_none():
    """PhaseResult.trial_count defaults to None for fresh phases."""
    result = PhaseResult(
        run_id="r1",
        phase="screening",
        trials=["t1", "t2", "t3"],
    )
    assert result.trial_count is None


def test_confirmation_phase_persists_confirmation_dict():
    """Confirmation dict (within_interval, sigma_deviation) must be persisted."""
    import tempfile
    from pathlib import Path

    from agent_evals.observatory.store import ObservatoryStore

    with tempfile.TemporaryDirectory() as td:
        store = ObservatoryStore(db_path=Path(td) / "test.db")
        store.create_run("run_001", "taguchi", {})

        confirmation = {
            "within_interval": True,
            "sigma_deviation": 0.3,
            "observed_sn": 7.5,
            "predicted_sn": 7.42,
            "prediction_interval": [5.1, 9.7],
        }

        store.save_phase_results(
            run_id="run_001",
            main_effects={},
            anova={},
            optimal={},
            significant_factors=[],
            quality_type="larger_is_better",
            confirmation=confirmation,
        )

        result = store.get_phase_results("run_001")
        assert result is not None
        assert result["confirmation"] is not None
        assert result["confirmation"]["within_interval"] is True
        assert result["confirmation"]["sigma_deviation"] == pytest.approx(0.3)
        assert result["confirmation"]["observed_sn"] == pytest.approx(7.5)


# ---------------------------------------------------------------------------
# Bug #226: _group_refinement_scores maps to ALL matching OA rows
# ---------------------------------------------------------------------------


class TestGroupRefinementScoresBug226:
    """_group_refinement_scores must map each trial to only the exact
    OA row matching the trial's full factor combination.

    Bug #226: The current code maps a trial's score to ALL rows that
    contain the trial's variant_name in any factor position.  When
    two factors share a level name (or a composite name partially
    matches), scores are attributed to the wrong rows.
    """

    @staticmethod
    def _make_trial(variant_name: str, score: float):
        """Create a minimal trial mock."""
        trial = MagicMock()
        trial.variant_name = variant_name
        trial.score = score
        trial.error = None
        trial.metrics = {}
        return trial

    @staticmethod
    def _make_design_with_shared_level_names():
        """Design where two factors share the level name 'verbose'.

        Row 1: {axis_1: verbose,  axis_2: short}
        Row 2: {axis_1: verbose,  axis_2: verbose}
        Row 3: {axis_1: concise,  axis_2: short}
        Row 4: {axis_1: concise,  axis_2: verbose}
        """
        from agent_evals.taguchi.factors import (
            TaguchiDesign,
            TaguchiExperimentRow,
            TaguchiFactorDef,
        )

        factors = [
            TaguchiFactorDef(
                name="axis_1", n_levels=2,
                level_names=["verbose", "concise"], axis=1,
            ),
            TaguchiFactorDef(
                name="axis_2", n_levels=2,
                level_names=["short", "verbose"], axis=2,
            ),
        ]
        rows = [
            TaguchiExperimentRow(
                run_id=1,
                assignments={"axis_1": "verbose", "axis_2": "short"},
            ),
            TaguchiExperimentRow(
                run_id=2,
                assignments={"axis_1": "verbose", "axis_2": "verbose"},
            ),
            TaguchiExperimentRow(
                run_id=3,
                assignments={"axis_1": "concise", "axis_2": "short"},
            ),
            TaguchiExperimentRow(
                run_id=4,
                assignments={"axis_1": "concise", "axis_2": "verbose"},
            ),
        ]
        return TaguchiDesign(
            oa_name="L4", n_runs=4, factors=factors, rows=rows,
            level_counts=[2, 2],
        )

    def test_composite_trial_maps_to_exact_row(self):
        """A composite trial 'verbose+short' must map ONLY to row 1.

        Bug: old code can't handle composite names at all (maps to empty).
        """
        design = self._make_design_with_shared_level_names()
        trial = self._make_trial("verbose+short", score=0.9)

        scores = DOEPipeline._group_refinement_scores([trial], design)

        # Must map to ONLY row 1 (exact match for verbose+short)
        assert 1 in scores, "Composite 'verbose+short' should match row 1"
        assert scores[1] == [0.9]
        # Must NOT map to other rows
        assert 2 not in scores, "Score leaked to row 2 (verbose+verbose)"
        assert 3 not in scores, "Score leaked to row 3 (concise+short)"
        assert 4 not in scores, "Score leaked to row 4 (concise+verbose)"

    def test_shared_level_name_no_cross_factor_contamination(self):
        """'verbose' appears in both axis_1 and axis_2.

        Old code maps 'verbose' to ALL rows containing it (rows 1,2,4).
        Correct: a single variant matches no exact row when ambiguous.
        """
        design = self._make_design_with_shared_level_names()
        trial = self._make_trial("verbose", score=0.7)

        scores = DOEPipeline._group_refinement_scores([trial], design)

        mapped_rows = set(scores.keys())
        # Must NOT map to 3+ rows (cross-factor contamination)
        assert len(mapped_rows) <= 2, (
            f"Single-variant 'verbose' mapped to {len(mapped_rows)} rows "
            f"instead of ≤2; cross-factor contamination"
        )

    @staticmethod
    def _make_unique_level_design():
        """Design with unique level names across factors.

        Row 1: {axis_1: flat,   axis_2: path}
        Row 2: {axis_1: flat,   axis_2: summary}
        Row 3: {axis_1: nested, axis_2: path}
        Row 4: {axis_1: nested, axis_2: summary}
        """
        from agent_evals.taguchi.factors import (
            TaguchiDesign,
            TaguchiExperimentRow,
            TaguchiFactorDef,
        )

        factors = [
            TaguchiFactorDef(
                name="axis_1", n_levels=2,
                level_names=["flat", "nested"], axis=1,
            ),
            TaguchiFactorDef(
                name="axis_2", n_levels=2,
                level_names=["path", "summary"], axis=2,
            ),
        ]
        rows = [
            TaguchiExperimentRow(
                run_id=1,
                assignments={"axis_1": "flat", "axis_2": "path"},
            ),
            TaguchiExperimentRow(
                run_id=2,
                assignments={"axis_1": "flat", "axis_2": "summary"},
            ),
            TaguchiExperimentRow(
                run_id=3,
                assignments={"axis_1": "nested", "axis_2": "path"},
            ),
            TaguchiExperimentRow(
                run_id=4,
                assignments={"axis_1": "nested", "axis_2": "summary"},
            ),
        ]
        return TaguchiDesign(
            oa_name="L4", n_runs=4, factors=factors, rows=rows,
            level_counts=[2, 2],
        )

    def test_composite_name_exact_match_unique_levels(self):
        """Composite trial 'flat+path' maps to exactly row 1."""
        design = self._make_unique_level_design()
        trials = [
            self._make_trial("flat+path", score=0.8),
            self._make_trial("nested+summary", score=0.6),
        ]

        scores = DOEPipeline._group_refinement_scores(trials, design)

        assert scores.get(1) == [0.8], "flat+path -> row 1"
        assert scores.get(4) == [0.6], "nested+summary -> row 4"
        assert 2 not in scores
        assert 3 not in scores


# ---------------------------------------------------------------------------
# Bug #233: Confirmation must test COMBINED optimal, not individual variants
# ---------------------------------------------------------------------------


class TestConfirmationCombinedOptimal:
    """Bug #233: Confirmation phase must compose a single CompositeVariant
    from all optimal levels and test that combined configuration, rather than
    testing each factor's optimal level individually.
    """

    def test_confirmation_builds_composite_variant(self):
        """Confirmation must create a CompositeVariant from all optimal levels.

        When screening identifies optimal={axis_1: 'axis1_a', axis_2: 'axis2_b'},
        confirmation should build a single CompositeVariant({1: var_a, 2: var_b})
        and pass that single composite to the orchestrator, not pass two separate
        variants.
        """
        config = PipelineConfig(models=["model-a"])
        orch = _make_mock_orchestrator(score=0.7)
        pipeline = DOEPipeline(config=config, orchestrator=orch)

        screening = PhaseResult(
            run_id="r1",
            phase="screening",
            trials=[],
            optimal={"axis_1": "axis1_a", "axis_2": "axis2_b"},
            significant_factors=["axis_1", "axis_2"],
            predicted_sn=12.0,
            prediction_interval=(10.0, 14.0),
            se_prediction=1.0,
        )

        all_variants = _make_variants()  # 5 axes * 3 levels = 15 variants

        with patch("agent_evals.pipeline.validate_confirmation") as mock_val:
            mock_val.return_value = MagicMock(
                within_interval=True,
                sigma_deviation=0.3,
                observed_sn=11.5,
                predicted_sn=12.0,
                prediction_interval=(10.0, 14.0),
            )
            pipeline.run_confirmation(
                screening_result=screening,
                tasks=[],
                variants=all_variants,
                doc_tree=MagicMock(),
            )

        # Orchestrator.run should receive exactly ONE variant (the composite)
        call_kwargs = orch.run.call_args
        passed_variants = call_kwargs[1].get("variants") or call_kwargs[0][1]
        assert len(passed_variants) == 1, (
            f"Confirmation should pass 1 CompositeVariant, got {len(passed_variants)} "
            f"individual variants. The combined optimal must be tested as a single "
            f"configuration, not as separate factor levels."
        )

    def test_confirmation_composite_contains_all_optimal_axes(self):
        """The composite variant must include one component per optimal factor.

        E.g., optimal={axis_1: 'axis1_a', axis_3: 'axis3_c'} -> composite has
        components from axis 1 and axis 3.
        """

        config = PipelineConfig(models=["model-a"])
        orch = _make_mock_orchestrator(score=0.7)
        pipeline = DOEPipeline(config=config, orchestrator=orch)

        screening = PhaseResult(
            run_id="r1",
            phase="screening",
            trials=[],
            optimal={"axis_1": "axis1_a", "axis_3": "axis3_c"},
            significant_factors=["axis_1", "axis_3"],
            predicted_sn=12.0,
            prediction_interval=(10.0, 14.0),
            se_prediction=1.0,
        )

        all_variants = _make_variants()

        with patch("agent_evals.pipeline.validate_confirmation") as mock_val:
            mock_val.return_value = MagicMock(
                within_interval=True,
                sigma_deviation=0.3,
                observed_sn=11.5,
                predicted_sn=12.0,
                prediction_interval=(10.0, 14.0),
            )
            pipeline.run_confirmation(
                screening_result=screening,
                tasks=[],
                variants=all_variants,
                doc_tree=MagicMock(),
            )

        call_kwargs = orch.run.call_args
        passed_variants = call_kwargs[1].get("variants") or call_kwargs[0][1]
        composite = passed_variants[0]

        # The composite's metadata name should combine the optimal level names
        composite_name = composite.metadata().name
        assert "axis1_a" in composite_name, (
            f"Composite should include axis1_a, got name: {composite_name}"
        )
        assert "axis3_c" in composite_name, (
            f"Composite should include axis3_c, got name: {composite_name}"
        )


# ---------------------------------------------------------------------------
# Bug #234: Refinement must use factorial design, not OFAT
# ---------------------------------------------------------------------------


class TestRefinementFactorialDesign:
    """Bug #234: Refinement phase must run a factorial (or fractional factorial)
    design on the top-k factors, not one-factor-at-a-time experiments.
    """

    def test_refinement_generates_factorial_composites(self):
        """Refinement must generate CompositeVariants covering all factor
        combinations, not pass individual variants (OFAT).

        With 2 top-k factors, each having 3 levels, refinement should
        produce 3*3 = 9 CompositeVariant objects.
        """
        from agent_evals.variants.composite import CompositeVariant

        config = PipelineConfig(models=["model-a"], top_k=2)
        orch = _make_mock_orchestrator()
        pipeline = DOEPipeline(config=config, orchestrator=orch)

        screening = PhaseResult(
            run_id="r1",
            phase="screening",
            trials=[],
            optimal={"axis_1": "axis1_a", "axis_3": "axis3_c"},
            significant_factors=["axis_1", "axis_3"],
            main_effects={
                "axis_1": {"axis1_a": 12.0, "axis1_b": 10.0, "axis1_c": 8.0},
                "axis_3": {"axis3_a": 8.5, "axis3_b": 10.5, "axis3_c": 11.5},
            },
        )

        with patch("agent_evals.pipeline.build_design") as mock_build, \
             patch("agent_evals.pipeline.compute_sn_ratios") as mock_sn, \
             patch("agent_evals.pipeline.compute_main_effects") as mock_me, \
             patch("agent_evals.pipeline.run_anova") as mock_anova, \
             patch("agent_evals.pipeline.predict_optimal") as mock_pred, \
             patch("agent_evals.pipeline.compute_interactions") as mock_ix:
            mock_row = MagicMock()
            mock_row.run_id = 1
            mock_row.assignments = {"axis_1": "axis1_a", "axis_3": "axis3_c"}
            mock_row.dummy_factors = set()
            mock_design = MagicMock()
            mock_design.rows = [mock_row]
            mock_design.factors = []
            mock_build.return_value = mock_design

            mock_sn.return_value = {1: 10.0}
            mock_me.return_value = {}
            mock_anova.return_value = MagicMock(factors=[])
            mock_pred.return_value = MagicMock(
                optimal_assignment={}, predicted_sn=0.0,
            )
            mock_ix.return_value = []

            pipeline.run_refinement(
                screening_result=screening,
                tasks=[],
                variants=_make_variants(),
                doc_tree=MagicMock(),
            )

        call_kwargs = orch.run.call_args
        passed_variants = call_kwargs[1].get("variants") or call_kwargs[0][1]

        # With 2 factors (axis_1: 3 levels, axis_3: 3 levels),
        # full factorial = 3 * 3 = 9 combinations
        assert len(passed_variants) == 9, (
            f"Expected 9 factorial CompositeVariants (3x3), "
            f"got {len(passed_variants)}"
        )
        # Each should be a CompositeVariant (not a bare mock variant)
        for v in passed_variants:
            assert isinstance(v, CompositeVariant), (
                f"Expected CompositeVariant, got {type(v).__name__}"
            )

    def test_refinement_composites_cover_all_combinations(self):
        """Each factorial CompositeVariant's name must be a unique combination."""
        config = PipelineConfig(models=["model-a"], top_k=2)
        orch = _make_mock_orchestrator()
        pipeline = DOEPipeline(config=config, orchestrator=orch)

        screening = PhaseResult(
            run_id="r1",
            phase="screening",
            trials=[],
            optimal={"axis_1": "axis1_a", "axis_3": "axis3_c"},
            significant_factors=["axis_1", "axis_3"],
            main_effects={
                "axis_1": {"axis1_a": 12.0, "axis1_b": 10.0, "axis1_c": 8.0},
                "axis_2": {"axis2_a": 9.0, "axis2_b": 11.0, "axis2_c": 10.0},
                "axis_3": {"axis3_a": 8.5, "axis3_b": 10.5, "axis3_c": 11.5},
            },
        )

        with patch("agent_evals.pipeline.build_design") as mock_build, \
             patch("agent_evals.pipeline.compute_sn_ratios") as mock_sn, \
             patch("agent_evals.pipeline.compute_main_effects") as mock_me, \
             patch("agent_evals.pipeline.run_anova") as mock_anova, \
             patch("agent_evals.pipeline.predict_optimal") as mock_pred, \
             patch("agent_evals.pipeline.compute_interactions") as mock_ix:
            mock_row = MagicMock()
            mock_row.run_id = 1
            mock_row.assignments = {"axis_1": "axis1_a", "axis_3": "axis3_c"}
            mock_row.dummy_factors = set()
            mock_design = MagicMock()
            mock_design.rows = [mock_row]
            mock_design.factors = []
            mock_build.return_value = mock_design

            mock_sn.return_value = {1: 10.0}
            mock_me.return_value = {}
            mock_anova.return_value = MagicMock(factors=[])
            mock_pred.return_value = MagicMock(
                optimal_assignment={}, predicted_sn=0.0,
            )
            mock_ix.return_value = []

            pipeline.run_refinement(
                screening_result=screening,
                tasks=[],
                variants=_make_variants(),
                doc_tree=MagicMock(),
            )

        call_kwargs = orch.run.call_args
        passed_variants = call_kwargs[1].get("variants") or call_kwargs[0][1]

        # All variant names should be unique (each is a distinct combination)
        names = [v.metadata().name for v in passed_variants]
        assert len(set(names)) == len(names), (
            f"Duplicate factorial combinations found: {names}"
        )


# ---------------------------------------------------------------------------
# Bug #235: Refinement uses main-effect ranking, not just significant_factors
# ---------------------------------------------------------------------------


class TestRefinementFactorRanking:
    """Bug #235: When selecting top-k factors for refinement, the code must
    use main-effect ranking (by delta = max - min of S/N ratios across levels)
    from the screening analysis. The significant_factors list may be empty
    (when no factors reach p < alpha), so the code must fall back to
    main-effect delta ranking.
    """

    def test_refinement_selects_factors_by_main_effect_delta(self):
        """When screening has no significant factors (all p > alpha), refinement
        must still select top-k factors using main-effect delta ranking.
        """
        config = PipelineConfig(models=["model-a"], top_k=2)
        orch = _make_mock_orchestrator()
        pipeline = DOEPipeline(config=config, orchestrator=orch)

        # No significant factors (common with noisy/free models)
        screening = PhaseResult(
            run_id="r1",
            phase="screening",
            trials=[],
            optimal={"axis_1": "axis1_a", "axis_2": "axis2_b", "axis_3": "axis3_c"},
            significant_factors=[],  # EMPTY - no factors reached p < alpha
            main_effects={
                "axis_1": {"axis1_a": 12.0, "axis1_b": 10.0, "axis1_c": 8.0},  # delta=4.0
                "axis_2": {"axis2_a": 9.0, "axis2_b": 9.5, "axis2_c": 9.2},    # delta=0.5
                "axis_3": {"axis3_a": 8.5, "axis3_b": 10.5, "axis3_c": 11.5},   # delta=3.0
            },
        )

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
                screening_result=screening,
                tasks=[],
                variants=_make_variants(),
                doc_tree=MagicMock(),
            )

        # Despite empty significant_factors, refinement should use
        # main_effects delta to pick top-2: axis_1 (delta=4.0) and axis_3 (delta=3.0)
        call_kwargs = orch.run.call_args
        passed_variants = call_kwargs[1].get("variants") or call_kwargs[0][1]

        # CompositeVariant names encode their component levels with "+"
        all_names = " ".join(v.metadata().name for v in passed_variants)
        assert "axis1_" in all_names, (
            "axis_1 (delta=4.0) levels should be in composites"
        )
        assert "axis3_" in all_names, (
            "axis_3 (delta=3.0) levels should be in composites"
        )
        # axis_2 non-optimal levels should NOT appear (it's fixed at optimal)
        for vname in (v.metadata().name for v in passed_variants):
            assert "axis2_a" not in vname, (
                "axis_2 non-optimal 'axis2_a' should not be varied"
            )
            assert "axis2_c" not in vname, (
                "axis_2 non-optimal 'axis2_c' should not be varied"
            )

    def test_refinement_prefers_main_effect_delta_over_significance_order(self):
        """Even with some significant factors, the ranking should follow
        main-effect delta, not the order from ANOVA significance.

        Example: significant_factors=['axis_2', 'axis_1'] by omega_squared,
        but main_effects show axis_3 has larger delta than axis_2.
        When top_k=2, we want axis_1 and axis_3 (by delta), not axis_2 and axis_1.
        """
        config = PipelineConfig(models=["model-a"], top_k=2)
        orch = _make_mock_orchestrator()
        pipeline = DOEPipeline(config=config, orchestrator=orch)

        screening = PhaseResult(
            run_id="r1",
            phase="screening",
            trials=[],
            optimal={"axis_1": "axis1_a", "axis_2": "axis2_b", "axis_3": "axis3_c"},
            significant_factors=["axis_2", "axis_1"],  # by omega_squared
            main_effects={
                "axis_1": {"axis1_a": 12.0, "axis1_b": 10.0, "axis1_c": 8.0},  # delta=4.0
                "axis_2": {"axis2_a": 9.0, "axis2_b": 10.0, "axis2_c": 9.5},    # delta=1.0
                "axis_3": {"axis3_a": 8.5, "axis3_b": 10.5, "axis3_c": 11.5},   # delta=3.0
            },
        )

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
                screening_result=screening,
                tasks=[],
                variants=_make_variants(),
                doc_tree=MagicMock(),
            )

        call_kwargs = orch.run.call_args
        passed_variants = call_kwargs[1].get("variants") or call_kwargs[0][1]

        # By main-effect delta: axis_1 (4.0) and axis_3 (3.0) are top-2
        all_names = " ".join(v.metadata().name for v in passed_variants)
        assert "axis1_" in all_names, "axis_1 (delta=4.0) should be selected"
        assert "axis3_" in all_names, "axis_3 (delta=3.0) should be selected"
        # axis_2 non-optimal levels should NOT be varied
        for vname in (v.metadata().name for v in passed_variants):
            assert "axis2_a" not in vname, (
                "axis_2 (delta=1.0) non-optimal should NOT be varied"
            )
            assert "axis2_c" not in vname, (
                "axis_2 (delta=1.0) non-optimal should NOT be varied"
            )


# ---------------------------------------------------------------------------
# Bug #240: No screening report file generated in pipeline mode
# ---------------------------------------------------------------------------


class TestScreeningReportFile:
    """Bug #240: screening phase should generate a JSON report file."""

    def test_screening_generates_report_file(self, tmp_path):
        """Pipeline screening phase must produce a report JSON file."""
        from agent_evals.observatory.store import ObservatoryStore
        from agent_evals.pipeline import DOEPipeline, PipelineConfig

        store = ObservatoryStore(db_path=tmp_path / "obs.db")

        # Create a mock orchestrator that returns minimal results
        mock_orch = MagicMock()
        mock_orch.store = store
        mock_orch.config = MagicMock()
        mock_orch.config.eval_config = MagicMock()
        mock_orch.config.eval_config.repetitions = 3
        mock_orch.config.eval_config.output_dir = str(tmp_path / "reports")

        # Build a mock run result
        mock_trial = MagicMock()
        mock_trial.score = 0.8
        mock_trial.error = None
        mock_trial.metrics = {"oa_row_id": 1}
        mock_trial.cost = 0.001
        mock_trial.total_tokens = 100

        mock_result = MagicMock()
        mock_result.run_id = "test_screening_run"
        mock_result.trials = [mock_trial]
        mock_result.total_cost = 0.001
        mock_result.total_tokens = 100
        mock_result.elapsed_seconds = 1.0
        mock_orch.run.return_value = mock_result

        config = PipelineConfig(models=["m"])

        pipeline = DOEPipeline(
            config=config, orchestrator=mock_orch, pipeline_id="test_pipe",
        )

        # Run screening with mocked internals
        with patch.object(
            pipeline, "run_screening",
        ) as mock_screening:
            phase_result = PhaseResult(
                run_id="scr_run",
                phase="screening",
                trials=[mock_trial],
                total_cost=0.001,
                total_tokens=100,
                elapsed_seconds=1.0,
                main_effects={"axis_1": {"flat": 10.0}},
                anova={"factors": []},
                optimal={"axis_1": "flat"},
                significant_factors=["axis_1"],
            )
            mock_screening.return_value = phase_result

            # After pipeline runs, check for screening report artifact in DB
            store.create_run(
                "scr_run", run_type="taguchi", config={},
                phase="screening", pipeline_id="test_pipe",
            )
            pipeline._save_phase_report(phase_result)

            artifacts = store.list_report_artifacts("scr_run")
            artifact_types = [a["artifact_type"] for a in artifacts]
            assert "phase_report" in artifact_types


# ---------------------------------------------------------------------------
# Bug #241: Report JSONs lack DOE-specific fields
# ---------------------------------------------------------------------------


class TestReportDOEFields:
    """Bug #241: Report artifacts must include DOE-specific fields."""

    def test_phase_report_includes_doe_fields(self, tmp_path):
        """Phase report artifact must include DOE analysis fields."""
        from agent_evals.observatory.store import ObservatoryStore
        from agent_evals.pipeline import DOEPipeline, PipelineConfig

        store = ObservatoryStore(db_path=tmp_path / "obs.db")
        mock_orch = MagicMock()
        mock_orch.store = store

        config = PipelineConfig(models=["m"])
        pipeline = DOEPipeline(
            config=config, orchestrator=mock_orch, pipeline_id="pipe_241",
        )

        store.create_run(
            "run_241", run_type="taguchi", config={},
            phase="screening", pipeline_id="pipe_241",
        )

        phase_result = PhaseResult(
            run_id="run_241",
            phase="screening",
            trials=[],
            main_effects={"axis_1": {"flat": 10.0}},
            anova={"factors": []},
            optimal={"axis_1": "flat"},
            significant_factors=["axis_1"],
            predicted_sn=12.5,
        )

        pipeline._save_phase_report(phase_result)

        artifact = store.get_report_artifact("run_241", "phase_report")
        assert artifact is not None
        data = artifact["data"]

        # Must include DOE-specific fields
        assert "phase" in data
        assert data["phase"] == "screening"
        assert "pipeline_id" in data
        assert data["pipeline_id"] == "pipe_241"
        assert "run_id" in data
        assert "main_effects" in data
        assert "anova" in data
        assert "optimal" in data
        assert "significant_factors" in data


# ---------------------------------------------------------------------------
# Bug #242: factor_definitions, task_metadata, report_artifacts never populated
# ---------------------------------------------------------------------------


class TestPipelinePopulatesTables:
    """Bug #242: Pipeline must populate factor_definitions and task_metadata."""

    def test_screening_saves_factor_definitions(self, tmp_path):
        """After screening, factor_definitions table must have entries."""
        from agent_evals.observatory.store import ObservatoryStore
        from agent_evals.pipeline import DOEPipeline, PipelineConfig

        store = ObservatoryStore(db_path=tmp_path / "obs.db")
        mock_orch = MagicMock()
        mock_orch.store = store
        mock_orch.config = MagicMock()
        mock_orch.config.eval_config = MagicMock()
        mock_orch.config.eval_config.repetitions = 3

        config = PipelineConfig(models=["m"])
        pipeline = DOEPipeline(
            config=config, orchestrator=mock_orch, pipeline_id="pipe_242",
        )

        store.create_run(
            "run_242", run_type="taguchi", config={},
            phase="screening", pipeline_id="pipe_242",
        )

        # Simulate variant metadata (MagicMock 'name' is special —
        # set it as an attribute after construction)
        meta1 = MagicMock(axis=1)
        meta1.name = "flat"
        mock_variant1 = MagicMock()
        mock_variant1.metadata.return_value = meta1

        meta2 = MagicMock(axis=1)
        meta2.name = "nested"
        mock_variant2 = MagicMock()
        mock_variant2.metadata.return_value = meta2

        variants = [mock_variant1, mock_variant2]
        pipeline._save_factor_definitions("run_242", variants)

        defs = store.get_factor_definitions("run_242")
        assert len(defs) > 0
        factor_names = {d["factor_name"] for d in defs}
        assert "axis_1" in factor_names

    def test_pipeline_saves_task_metadata(self, tmp_path):
        """Pipeline must save task metadata to the task_metadata table."""
        from agent_evals.observatory.store import ObservatoryStore
        from agent_evals.pipeline import DOEPipeline, PipelineConfig

        store = ObservatoryStore(db_path=tmp_path / "obs.db")
        mock_orch = MagicMock()
        mock_orch.store = store

        config = PipelineConfig(models=["m"])
        pipeline = DOEPipeline(
            config=config, orchestrator=mock_orch, pipeline_id="pipe_tm",
        )

        # Simulate task list
        mock_task = MagicMock()
        mock_task.definition.task_id = "task_1"
        mock_task.definition.type = "retrieval"
        mock_task.definition.metadata = {"domain": "api", "difficulty": "easy"}

        pipeline._save_task_metadata([mock_task])

        metadata = store.get_task_metadata()
        assert len(metadata) > 0
        assert metadata[0]["task_id"] == "task_1"
        assert metadata[0]["task_type"] == "retrieval"


# ---------------------------------------------------------------------------
# Bug #243: parent_run_id is None for confirmation/refinement runs
# ---------------------------------------------------------------------------


class TestParentRunId:
    """Bug #243: confirmation/refinement runs must reference screening run."""

    def test_confirmation_passes_parent_run_id(self):
        """Orchestrator.run must receive parent_run_id for confirmation."""
        from agent_evals.pipeline import DOEPipeline, PipelineConfig

        # Use fully mocked store to avoid FK constraints
        mock_store = MagicMock()
        mock_orch = MagicMock()
        mock_orch.store = mock_store
        mock_orch.config = MagicMock()
        mock_orch.config.eval_config = MagicMock()
        mock_orch.config.eval_config.repetitions = 5

        mock_trial = MagicMock()
        mock_trial.score = 0.8
        mock_trial.error = None
        mock_trial.cost = 0.001
        mock_trial.total_tokens = 100
        mock_trial.metrics = {}

        mock_result = MagicMock()
        mock_result.run_id = "confirm_run"
        mock_result.trials = [mock_trial]
        mock_result.total_cost = 0.001
        mock_result.total_tokens = 100
        mock_result.elapsed_seconds = 1.0
        mock_orch.run.return_value = mock_result

        config = PipelineConfig(models=["m"])
        pipeline = DOEPipeline(
            config=config, orchestrator=mock_orch, pipeline_id="pipe_243",
        )

        screening_result = PhaseResult(
            run_id="screening_run",
            phase="screening",
            trials=[],
            optimal={"axis_1": "flat"},
            significant_factors=["axis_1"],
            predicted_sn=10.0,
            prediction_interval=(8.0, 12.0),
            se_prediction=1.0,
        )

        meta = MagicMock(axis=1)
        meta.name = "flat"
        mock_variant = MagicMock()
        mock_variant.metadata.return_value = meta

        with patch(
            "agent_evals.pipeline.validate_confirmation",
            return_value=MagicMock(
                within_interval=True,
                sigma_deviation=0.5,
                observed_sn=10.5,
                predicted_sn=10.0,
                prediction_interval=(8.0, 12.0),
            ),
        ):
            pipeline.run_confirmation(
                screening_result, [], [mock_variant], MagicMock(),
            )

        # Verify orchestrator.run was called with parent_run_id
        call_kwargs = mock_orch.run.call_args
        assert call_kwargs is not None
        assert call_kwargs.kwargs.get("parent_run_id") == "screening_run", \
            "orchestrator.run must be called with parent_run_id=screening_run"

    def test_refinement_passes_parent_run_id(self):
        """Orchestrator.run must receive parent_run_id for refinement."""
        from agent_evals.pipeline import DOEPipeline, PipelineConfig

        mock_store = MagicMock()
        mock_orch = MagicMock()
        mock_orch.store = mock_store
        mock_orch.config = MagicMock()
        mock_orch.config.eval_config = MagicMock()
        mock_orch.config.eval_config.repetitions = 3

        mock_trial = MagicMock()
        mock_trial.score = 0.8
        mock_trial.error = None
        mock_trial.cost = 0.001
        mock_trial.total_tokens = 100
        mock_trial.metrics = {}
        mock_trial.variant_name = "flat"

        mock_result = MagicMock()
        mock_result.run_id = "refine_run"
        mock_result.trials = [mock_trial]
        mock_result.total_cost = 0.001
        mock_result.total_tokens = 100
        mock_result.elapsed_seconds = 1.0
        mock_orch.run.return_value = mock_result

        config = PipelineConfig(models=["m"])
        pipeline = DOEPipeline(
            config=config, orchestrator=mock_orch, pipeline_id="pipe_243r",
        )

        screening_result = PhaseResult(
            run_id="screening_run_ref",
            phase="screening",
            trials=[],
            significant_factors=["axis_1"],
            main_effects={"axis_1": {"flat": 10.0, "nested": 8.0}},
        )

        meta = MagicMock(axis=1)
        meta.name = "flat"
        mock_variant = MagicMock()
        mock_variant.metadata.return_value = meta

        with patch(
            "agent_evals.pipeline.build_design",
        ), patch(
            "agent_evals.pipeline.compute_sn_ratios",
            return_value={},
        ), patch(
            "agent_evals.pipeline.compute_main_effects",
            return_value={},
        ), patch(
            "agent_evals.pipeline.run_anova",
            return_value=MagicMock(factors=[]),
        ), patch(
            "agent_evals.pipeline.predict_optimal",
            return_value=MagicMock(
                optimal_assignment={},
                predicted_sn=10.0,
                prediction_interval=(8.0, 12.0),
                se_prediction=1.0,
            ),
        ), patch(
            "agent_evals.pipeline.compute_interactions",
            return_value=[],
        ):
            pipeline.run_refinement(
                screening_result, [], [mock_variant], MagicMock(),
            )

        call_kwargs = mock_orch.run.call_args
        assert call_kwargs is not None
        assert call_kwargs.kwargs.get("parent_run_id") == "screening_run_ref", \
            "orchestrator.run must be called with parent_run_id=screening_run_ref"


class TestEffectiveScore:
    """Tests for _effective_score helper in pipeline module."""

    def test_returns_judge_score_for_primary_type(self):
        from agent_evals.pipeline import _effective_score

        trial = MagicMock()
        trial.task_type = "code_generation"
        trial.score = 0.5
        trial.metrics = {"judge_score": 0.9}

        result = _effective_score(trial, frozenset({"code_generation"}))
        assert result == 0.9

    def test_returns_trial_score_for_non_primary_type(self):
        from agent_evals.pipeline import _effective_score

        trial = MagicMock()
        trial.task_type = "retrieval"
        trial.score = 0.7
        trial.metrics = {"judge_score": 0.9}

        result = _effective_score(trial, frozenset({"code_generation"}))
        assert result == 0.7

    def test_returns_trial_score_when_no_judge_score(self):
        from agent_evals.pipeline import _effective_score

        trial = MagicMock()
        trial.task_type = "code_generation"
        trial.score = 0.6
        trial.metrics = {}

        result = _effective_score(trial, frozenset({"code_generation"}))
        assert result == 0.6

    def test_returns_trial_score_with_empty_primary_types(self):
        from agent_evals.pipeline import _effective_score

        trial = MagicMock()
        trial.task_type = "code_generation"
        trial.score = 0.5
        trial.metrics = {"judge_score": 0.9}

        result = _effective_score(trial, frozenset())
        assert result == 0.5


@patch("agent_evals.pipeline.run_multi_objective_analysis")
@patch("agent_evals.pipeline.predict_optimal")
@patch("agent_evals.pipeline.run_anova")
@patch("agent_evals.pipeline.compute_main_effects")
@patch("agent_evals.pipeline.compute_sn_ratios")
@patch("agent_evals.pipeline.build_design")
def test_screening_populates_multi_objective(
    mock_build, mock_sn, mock_me, mock_anova, mock_pred, mock_mo,
):
    """Screening phase calls run_multi_objective_analysis with row costs/latencies."""
    mock_build.return_value = MagicMock()
    mock_sn.return_value = {0: 10.0}
    mock_me.return_value = {}
    mock_anova.return_value = MagicMock(factors=[])
    mock_pred.return_value = MagicMock(optimal_assignment={})
    mock_mo.return_value = {
        "accuracy": {"sn_ratios": {0: 10.0}},
        "cost": {"sn_ratios": {0: -5.0}},
        "latency": {"sn_ratios": {0: -3.0}},
    }

    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    # Ensure mock trials have cost and latency data
    for trial in orch.run.return_value.trials:
        trial.cost = 0.05
        trial.latency_seconds = 1.5
        trial.error = None

    pipeline = DOEPipeline(config=config, orchestrator=orch)
    result = pipeline.run_screening(
        tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
    )

    mock_mo.assert_called_once()
    assert result.multi_objective is not None


@patch("agent_evals.pipeline.run_multi_objective_analysis")
@patch("agent_evals.pipeline.predict_optimal")
@patch("agent_evals.pipeline.run_anova")
@patch("agent_evals.pipeline.compute_main_effects")
@patch("agent_evals.pipeline.compute_sn_ratios")
@patch("agent_evals.pipeline.build_design")
def test_screening_multi_objective_skips_empty_cost(
    mock_build, mock_sn, mock_me, mock_anova, mock_pred, mock_mo,
):
    """Multi-objective still called when cost is None (accuracy-only result)."""
    mock_build.return_value = MagicMock()
    mock_sn.return_value = {0: 10.0}
    mock_me.return_value = {}
    mock_anova.return_value = MagicMock(factors=[])
    mock_pred.return_value = MagicMock(optimal_assignment={})
    mock_mo.return_value = {"accuracy": {"sn_ratios": {0: 10.0}}}

    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    for trial in orch.run.return_value.trials:
        trial.cost = None
        trial.latency_seconds = 0.0
        trial.error = None

    pipeline = DOEPipeline(config=config, orchestrator=orch)
    result = pipeline.run_screening(
        tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
    )

    mock_mo.assert_called_once()
    assert result.multi_objective is not None


class TestPipelineBudgetAcrossPhases:
    """Budget must be reduced across pipeline phases."""

    def test_budget_reduced_before_each_phase(self):
        """Each phase should see remaining budget, not original."""
        config = PipelineConfig(
            models=["model-a"],
            global_budget=10.0,
        )
        orch = MagicMock()
        eval_config = MagicMock()
        eval_config.budget = 10.0
        orch.config.eval_config = eval_config
        orch.store = None

        pipeline = DOEPipeline(config=config, orchestrator=orch)

        # Track budget values before each phase
        budget_before_phase: list[float] = []

        def screening_side_effect(*args, **kwargs):
            budget_before_phase.append(eval_config.budget)
            return PhaseResult(
                run_id="s1", phase="screening", trials=[],
                total_cost=4.0,
            )

        def confirmation_side_effect(*args, **kwargs):
            budget_before_phase.append(eval_config.budget)
            return PhaseResult(
                run_id="c1", phase="confirmation", trials=[],
                total_cost=2.0,
            )

        def refinement_side_effect(*args, **kwargs):
            budget_before_phase.append(eval_config.budget)
            return PhaseResult(
                run_id="r1", phase="refinement", trials=[],
                total_cost=1.0,
            )

        pipeline.run_screening = MagicMock(side_effect=screening_side_effect)
        pipeline.run_confirmation = MagicMock(
            side_effect=confirmation_side_effect,
        )
        pipeline.run_refinement = MagicMock(
            side_effect=refinement_side_effect,
        )

        pipeline.run(tasks=[], variants=[], doc_tree=MagicMock())

        assert len(budget_before_phase) == 3
        assert budget_before_phase[0] == 10.0    # screening: full budget
        assert budget_before_phase[1] == 6.0     # confirmation: 10 - 4
        assert budget_before_phase[2] == 4.0     # refinement: 10 - 4 - 2
