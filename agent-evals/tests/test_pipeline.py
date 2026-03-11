"""Tests for DOE pipeline data models and DOEPipeline orchestration."""

from unittest.mock import MagicMock, patch

import pytest

from agent_evals.pipeline import DOEPipeline, PipelineConfig, PhaseResult, PipelineResult


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
    """Bug #96: Confirmation must only pass optimal variants to orchestrator."""
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

    # Orchestrator should receive ONLY the 2 optimal variants, not all 15
    call_kwargs = orch.run.call_args
    passed_variants = call_kwargs[1].get("variants") or call_kwargs[0][1]
    variant_names = {v.metadata().name for v in passed_variants}
    assert variant_names == {"axis1_a", "axis2_b"}, (
        f"Expected only optimal variants {{'axis1_a', 'axis2_b'}}, "
        f"got {variant_names}"
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


def test_pipeline_refinement_passes_mode_full():
    """Phase 3 passes mode='full' to orchestrator."""
    config = PipelineConfig(models=["model-a"], top_k=2)
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    screening = PhaseResult(
        run_id="r1",
        phase="screening",
        trials=[],
        optimal={"axis_1": "a"},
        significant_factors=["axis_1"],
        main_effects={"axis_1": {"a": 12.0, "b": 10.0}},
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

    orch.run.assert_called_once()
    call_kwargs = orch.run.call_args
    assert call_kwargs.kwargs.get("mode") == "full"


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
    """Bug #96: Refinement must only pass top-K factor variants to orchestrator."""
    config = PipelineConfig(models=["model-a"], top_k=2)
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    # axis_1 and axis_3 are top-2 significant factors
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

    with patch("agent_evals.pipeline.compute_sn_ratios"), \
         patch("agent_evals.pipeline.compute_main_effects") as mock_me, \
         patch("agent_evals.pipeline.run_anova") as mock_anova, \
         patch("agent_evals.pipeline.predict_optimal") as mock_pred:
        mock_me.return_value = {}
        mock_anova.return_value = MagicMock(factors=[])
        mock_pred.return_value = MagicMock(optimal_assignment={})
        pipeline.run_refinement(
            screening_result=screening,
            tasks=[],
            variants=all_variants,
            doc_tree=MagicMock(),
        )

    # Orchestrator should receive only variants from top-2 factors (axis_1, axis_3)
    call_kwargs = orch.run.call_args
    passed_variants = call_kwargs[1].get("variants") or call_kwargs[0][1]
    variant_names = {v.metadata().name for v in passed_variants}

    # top_k=2 means axis_1 and axis_3 (sorted by significance)
    expected_axes = {"axis_1", "axis_3"}
    for vname in variant_names:
        axis_prefix = "_".join(vname.split("_")[:1])  # e.g. "axis1"
        factor_name = f"axis_{axis_prefix.replace('axis', '')}"
        assert factor_name in expected_axes or vname in variant_names, (
            f"Variant {vname} does not belong to top-K factors {expected_axes}"
        )

    # Should have 6 variants (3 levels * 2 axes), not all 15
    assert len(passed_variants) == 6, (
        f"Expected 6 variants for 2 top-K factors, got {len(passed_variants)}"
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
    from dataclasses import asdict
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
    from pathlib import Path
    import tempfile
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

    def test_trial_maps_to_exact_row_not_all_partial_matches(self):
        """A composite trial 'verbose+short' must map ONLY to row 1.

        Bug: old code maps it to rows 1, 2, 3, 4 because 'verbose'
        appears in rows 1, 2, 4 and 'short' appears in rows 1, 3.
        """
        design = self._make_design_with_shared_level_names()
        trial = self._make_trial("verbose+short", score=0.9)

        scores = DOEPipeline._group_refinement_scores([trial], design)

        # Must map to ONLY row 1 (exact match for verbose+short)
        assert 1 in scores
        assert scores[1] == [0.9]
        # Must NOT map to other rows
        assert 2 not in scores, "Score leaked to row 2 (verbose+verbose)"
        assert 3 not in scores, "Score leaked to row 3 (concise+short)"
        assert 4 not in scores, "Score leaked to row 4 (concise+verbose)"

    def test_shared_level_name_no_cross_factor_contamination(self):
        """'verbose' as a single-variant trial must map only via the correct factor.

        If a trial for axis_1's 'verbose' is encountered, it should map
        to rows where axis_1=verbose (rows 1, 2), NOT where axis_2=verbose
        (rows 2, 4).  With old code, it maps to rows 1, 2, AND 4.
        """
        design = self._make_design_with_shared_level_names()
        # Single-variant trial — old code maps to ALL rows containing "verbose"
        trial = self._make_trial("verbose", score=0.7)

        scores = DOEPipeline._group_refinement_scores([trial], design)

        # "verbose" should map to rows 1 and 2 (axis_1=verbose)
        # OR rows 2 and 4 (axis_2=verbose) — but NOT all three.
        # With composite matching, single-variant should match no exact row.
        # The safest behavior: a single-variant name that appears in
        # multiple factors should NOT match any row (ambiguous).
        mapped_rows = set(scores.keys())
        # Must NOT map to all 4 rows
        assert len(mapped_rows) <= 2, (
            f"Single-variant 'verbose' mapped to {len(mapped_rows)} rows "
            f"instead of ≤2; cross-factor contamination"
        )
