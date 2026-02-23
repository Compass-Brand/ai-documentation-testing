"""Tests for DOE pipeline data models."""

from agent_evals.pipeline import PipelineConfig, PhaseResult, PipelineResult


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
