"""Tests for DOE pipeline data models and DOEPipeline orchestration."""

from unittest.mock import MagicMock, patch

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
    sig_factor_1.omega_squared = 0.4

    sig_factor_2 = MagicMock()
    sig_factor_2.factor_name = "axis_3"
    sig_factor_2.p_value = 0.02
    sig_factor_2.omega_squared = 0.2

    nonsig_factor = MagicMock()
    nonsig_factor.factor_name = "axis_2"
    nonsig_factor.p_value = 0.15
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


# ---------------------------------------------------------------------------
# DOEPipeline.run_refinement tests
# ---------------------------------------------------------------------------


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
