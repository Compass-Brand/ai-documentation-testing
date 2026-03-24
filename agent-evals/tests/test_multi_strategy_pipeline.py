"""Tests for MultiStrategyPipeline and strategy wiring through the stack."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

from agent_evals.context.base import StrategyConfig
from agent_evals.pipeline import (
    DOEPipeline,
    MultiStrategyPipeline,
    MultiStrategyResult,
    PhaseResult,
    PipelineConfig,
    PipelineResult,
)
from agent_evals.runner import EvalRunConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_orchestrator(score: float = 0.5) -> MagicMock:
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
    orch.run.return_value = result
    return orch


def _make_variants() -> list[MagicMock]:
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
# PipelineConfig new fields
# ---------------------------------------------------------------------------


class TestPipelineConfigStrategyFields:
    """PipelineConfig gains strategy_config and strategy_reps."""

    def test_default_strategy_config(self) -> None:
        config = PipelineConfig(models=["m"])
        assert isinstance(config.strategy_config, StrategyConfig)
        assert config.strategy_config.strategy == "full_context"

    def test_custom_strategy_config(self) -> None:
        sc = StrategyConfig(strategy="rag", rag_top_k=10)
        config = PipelineConfig(models=["m"], strategy_config=sc)
        assert config.strategy_config.strategy == "rag"
        assert config.strategy_config.rag_top_k == 10

    def test_default_strategy_reps_empty(self) -> None:
        config = PipelineConfig(models=["m"])
        assert config.strategy_reps == {}

    def test_custom_strategy_reps(self) -> None:
        config = PipelineConfig(
            models=["m"], strategy_reps={"rag": 5, "tool_based": 10}
        )
        assert config.strategy_reps["rag"] == 5
        assert config.strategy_reps["tool_based"] == 10


# ---------------------------------------------------------------------------
# MultiStrategyResult
# ---------------------------------------------------------------------------


class TestMultiStrategyResult:
    """MultiStrategyResult aggregates per-strategy PipelineResults."""

    def test_stores_per_strategy_results(self) -> None:
        screening = PhaseResult(run_id="r1", phase="screening", trials=[])
        pr = PipelineResult(pipeline_id="p1", screening=screening)
        msr = MultiStrategyResult(
            pipeline_id="multi-1",
            strategy_results={"full_context": pr},
        )
        assert "full_context" in msr.strategy_results
        assert msr.pipeline_id == "multi-1"

    def test_total_cost_aggregates(self) -> None:
        s1 = PhaseResult(run_id="r1", phase="screening", trials=[])
        pr1 = PipelineResult(
            pipeline_id="p1", screening=s1, total_cost=1.0
        )
        pr2 = PipelineResult(
            pipeline_id="p2", screening=s1, total_cost=2.5
        )
        msr = MultiStrategyResult(
            pipeline_id="multi-1",
            strategy_results={"full_context": pr1, "rag": pr2},
            total_cost=3.5,
        )
        assert msr.total_cost == 3.5


# ---------------------------------------------------------------------------
# MultiStrategyPipeline
# ---------------------------------------------------------------------------


class TestMultiStrategyPipelineCreation:
    """MultiStrategyPipeline creates separate DOEPipeline per strategy."""

    def test_creates_pipeline_per_strategy(self) -> None:
        config = PipelineConfig(models=["m"])
        orch = _make_mock_orchestrator()
        msp = MultiStrategyPipeline(
            config=config,
            orchestrator=orch,
            strategies=["full_context", "rag"],
        )
        assert len(msp.strategies) == 2

    def test_deep_copy_isolation(self) -> None:
        """Modifying one pipeline's config doesn't affect others."""
        config = PipelineConfig(
            models=["m"], screening_reps=3, confirmation_reps=5
        )
        orch = _make_mock_orchestrator()
        msp = MultiStrategyPipeline(
            config=config,
            orchestrator=orch,
            strategies=["full_context", "rag"],
        )
        # Get the per-strategy configs
        configs = msp._build_strategy_configs()
        configs["full_context"].screening_reps = 99
        assert configs["rag"].screening_reps == 3

    def test_strategy_specific_pipeline_id(self) -> None:
        """Each strategy gets a pipeline_id like 'pipe-001__rag'."""
        config = PipelineConfig(models=["m"])
        orch = _make_mock_orchestrator()
        msp = MultiStrategyPipeline(
            config=config,
            orchestrator=orch,
            strategies=["full_context", "rag"],
            pipeline_id="pipe-001",
        )
        ids = msp._build_pipeline_ids()
        assert ids["full_context"] == "pipe-001__full_context"
        assert ids["rag"] == "pipe-001__rag"

    def test_per_strategy_rep_overrides(self) -> None:
        """strategy_reps overrides screening_reps and confirmation_reps."""
        config = PipelineConfig(
            models=["m"],
            screening_reps=3,
            confirmation_reps=5,
            strategy_reps={"rag": 7, "tool_based": 10},
        )
        orch = _make_mock_orchestrator()
        msp = MultiStrategyPipeline(
            config=config,
            orchestrator=orch,
            strategies=["full_context", "rag", "tool_based"],
        )
        configs = msp._build_strategy_configs()
        # full_context keeps defaults
        assert configs["full_context"].screening_reps == 3
        assert configs["full_context"].confirmation_reps == 5
        # rag gets overridden
        assert configs["rag"].screening_reps == 7
        assert configs["rag"].confirmation_reps == 9  # screening + 2
        # tool_based gets overridden
        assert configs["tool_based"].screening_reps == 10
        assert configs["tool_based"].confirmation_reps == 12  # screening + 2


class TestMultiStrategyPipelineRun:
    """MultiStrategyPipeline.run() executes per-strategy pipelines."""

    def test_run_returns_multi_strategy_result(self) -> None:
        config = PipelineConfig(models=["m"])
        orch = _make_mock_orchestrator()
        msp = MultiStrategyPipeline(
            config=config,
            orchestrator=orch,
            strategies=["full_context", "rag"],
        )

        screening = PhaseResult(
            run_id="r1", phase="screening", trials=[],
            significant_factors=["axis_1"], optimal={"axis_1": "a"},
            total_cost=1.0, elapsed_seconds=10.0,
        )
        confirmation = PhaseResult(
            run_id="r2", phase="confirmation", trials=[],
            total_cost=0.5, elapsed_seconds=5.0,
        )
        refinement = PhaseResult(
            run_id="r3", phase="refinement", trials=[],
            total_cost=2.0, elapsed_seconds=20.0,
        )

        mock_result = PipelineResult(
            pipeline_id="p1",
            screening=screening,
            confirmation=confirmation,
            refinement=refinement,
            total_trials=10,
            total_cost=3.5,
            elapsed_seconds=35.0,
        )

        with patch.object(DOEPipeline, "run", return_value=mock_result):
            result = msp.run(
                tasks=[], variants=_make_variants(), doc_tree=MagicMock()
            )

        assert isinstance(result, MultiStrategyResult)
        assert "full_context" in result.strategy_results
        assert "rag" in result.strategy_results


class TestMultiStrategyPipelineResume:
    """Resume tracks per-strategy completion."""

    def test_completed_strategies_are_skipped(self) -> None:
        config = PipelineConfig(models=["m"])
        orch = _make_mock_orchestrator()
        msp = MultiStrategyPipeline(
            config=config,
            orchestrator=orch,
            strategies=["full_context", "rag"],
            pipeline_id="pipe-001",
        )
        # Mark full_context as completed
        screening = PhaseResult(
            run_id="r1", phase="screening", trials=[],
            total_cost=1.0, elapsed_seconds=10.0,
        )
        msp._completed_strategies["full_context"] = PipelineResult(
            pipeline_id="pipe-001__full_context",
            screening=screening,
            total_cost=1.0,
            elapsed_seconds=10.0,
        )

        mock_result = PipelineResult(
            pipeline_id="pipe-001__rag",
            screening=screening,
            total_cost=2.0,
            elapsed_seconds=20.0,
        )

        with patch.object(DOEPipeline, "run", return_value=mock_result) as mock_run:
            result = msp.run(
                tasks=[], variants=_make_variants(), doc_tree=MagicMock()
            )

        # DOEPipeline.run should only be called once (for rag, not full_context)
        assert mock_run.call_count == 1
        assert "full_context" in result.strategy_results
        assert "rag" in result.strategy_results


# ---------------------------------------------------------------------------
# Orchestrator strategy wiring
# ---------------------------------------------------------------------------


class TestOrchestratorStrategyConfig:
    """OrchestratorConfig gains strategy_config field."""

    def test_default_strategy_config(self) -> None:
        from agent_evals.orchestrator import OrchestratorConfig

        config = OrchestratorConfig()
        assert isinstance(config.strategy_config, StrategyConfig)
        assert config.strategy_config.strategy == "full_context"

    def test_custom_strategy_config(self) -> None:
        from agent_evals.orchestrator import OrchestratorConfig

        sc = StrategyConfig(strategy="rag")
        config = OrchestratorConfig(strategy_config=sc)
        assert config.strategy_config.strategy == "rag"


class TestOrchestratorStrategyFactory:
    """Orchestrator passes strategy_factory to runners."""

    def test_run_full_passes_strategy_factory(self) -> None:
        """_run_full creates EvalRunner with strategy_factory from config."""
        from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig
        from agent_evals.runner import EvalRunConfig

        sc = StrategyConfig(strategy="rag")
        config = OrchestratorConfig(
            models=["test/model"],
            api_key="test-key",
            strategy_config=sc,
            eval_config=EvalRunConfig(),
        )

        with patch("agent_evals.orchestrator.LLMClientPool"), \
             patch("agent_evals.orchestrator.ObservatoryStore"), \
             patch("agent_evals.orchestrator.EventTracker"), \
             patch("agent_evals.orchestrator.EvalRunner") as MockRunner:
            mock_runner_instance = MagicMock()
            mock_runner_instance.run.return_value = MagicMock(
                trials=[], total_cost=0, total_tokens=0,
                elapsed_seconds=0, graceful_shutdown=False,
            )
            MockRunner.return_value = mock_runner_instance

            orch = EvalOrchestrator(config)
            orch._run_full(
                tasks=[], variants=[], doc_tree=MagicMock(),
                eval_config=EvalRunConfig(),
                progress_callback=None, source="test",
            )

            # EvalRunner should have been called with a strategy_factory kwarg
            MockRunner.assert_called_once()
            call_kwargs = MockRunner.call_args
            assert "strategy_factory" in call_kwargs.kwargs  # noqa: E501

    def test_run_taguchi_passes_strategy_factory(self) -> None:
        """_run_taguchi creates TaguchiRunner with strategy_factory."""
        from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig
        from agent_evals.runner import EvalRunConfig

        sc = StrategyConfig(strategy="rag")
        config = OrchestratorConfig(
            models=["test/model"],
            api_key="test-key",
            strategy_config=sc,
            eval_config=EvalRunConfig(),
        )

        with patch("agent_evals.orchestrator.LLMClientPool"), \
             patch("agent_evals.orchestrator.ObservatoryStore"), \
             patch("agent_evals.orchestrator.EventTracker"), \
             patch("agent_evals.taguchi.runner.TaguchiRunner") as MockRunner:
            mock_runner_instance = MagicMock()
            mock_runner_instance.run.return_value = MagicMock(
                trials=[], total_cost=0, total_tokens=0,
                elapsed_seconds=0, graceful_shutdown=False,
            )
            MockRunner.return_value = mock_runner_instance

            orch = EvalOrchestrator(config)
            mock_design = MagicMock()
            orch._run_taguchi(
                tasks=[], doc_tree=MagicMock(),
                eval_config=EvalRunConfig(),
                design=mock_design,
                variant_lookup={"v": MagicMock()},
                progress_callback=None, source="test",
            )

            MockRunner.assert_called_once()
            call_kwargs = MockRunner.call_args
            assert "strategy_factory" in call_kwargs.kwargs


# ---------------------------------------------------------------------------
# Bug #254: Budget drains across strategies
# ---------------------------------------------------------------------------


class TestBudgetResetAcrossStrategies:
    """Budget must be restored at the start of each strategy iteration."""

    def test_budget_not_drained_across_strategies(self) -> None:
        """Each strategy should see the original budget, not a depleted one.

        _reduce_remaining_budget (called inside DOEPipeline.run) mutates
        orchestrator.config.eval_config.budget. Without a restore, strategy
        2 would see a smaller budget than strategy 1.
        """
        eval_config = EvalRunConfig(budget=10.0)
        config = PipelineConfig(models=["m"])
        orch = _make_mock_orchestrator()
        orch.config = MagicMock()
        orch.config.eval_config = eval_config
        orch.config.strategy_config = StrategyConfig()

        msp = MultiStrategyPipeline(
            config=config,
            orchestrator=orch,
            strategies=["full_context", "rag", "tool_based"],
        )

        screening = PhaseResult(
            run_id="r1", phase="screening", trials=[],
            total_cost=3.0, elapsed_seconds=10.0,
        )
        mock_result = PipelineResult(
            pipeline_id="p1",
            screening=screening,
            total_trials=10,
            total_cost=3.0,
            elapsed_seconds=10.0,
        )

        budgets_seen: list[float | None] = []

        def spy_run(self_pipeline, **kwargs):
            # Record the budget BEFORE this strategy drains it
            budget = getattr(orch.config.eval_config, "budget", None)
            budgets_seen.append(budget)
            # Simulate _reduce_remaining_budget draining 4.0 during the run
            if budget is not None:
                orch.config.eval_config.budget = max(budget - 4.0, 0.0)
            return mock_result

        with patch.object(DOEPipeline, "run", spy_run):
            msp.run(
                tasks=[], variants=_make_variants(), doc_tree=MagicMock()
            )

        # All three strategies should see the original budget (10.0),
        # NOT a progressively depleted one (10.0, 6.0, 2.0)
        assert len(budgets_seen) == 3
        assert budgets_seen[0] == 10.0
        assert budgets_seen[1] == 10.0
        assert budgets_seen[2] == 10.0


# ---------------------------------------------------------------------------
# Bug #255: compression_method dropped from StrategyConfig
# ---------------------------------------------------------------------------


class TestCompressionMethodPropagated:
    """compression_method must be passed through to per-strategy configs."""

    def test_compression_method_preserved_in_strategy_configs(self) -> None:
        """_build_strategy_configs must include compression_method."""
        sc = StrategyConfig(
            strategy="compression",
            compression_method="semantic",
        )
        config = PipelineConfig(
            models=["m"],
            strategy_config=sc,
        )
        orch = _make_mock_orchestrator()
        msp = MultiStrategyPipeline(
            config=config,
            orchestrator=orch,
            strategies=["compression", "full_context"],
        )
        configs = msp._build_strategy_configs()
        assert configs["compression"].strategy_config.compression_method == "semantic"
        assert configs["full_context"].strategy_config.compression_method == "semantic"


# ---------------------------------------------------------------------------
# Bug #269: refinement_reps not overridden by strategy_reps
# ---------------------------------------------------------------------------


class TestRefinementRepsOverride:
    """strategy_reps must also override refinement_reps."""

    def test_refinement_reps_overridden_by_strategy_reps(self) -> None:
        """When strategy_reps provides a value, refinement_reps must update."""
        config = PipelineConfig(
            models=["m"],
            screening_reps=3,
            confirmation_reps=5,
            refinement_reps=3,
            strategy_reps={"rag": 7},
        )
        orch = _make_mock_orchestrator()
        msp = MultiStrategyPipeline(
            config=config,
            orchestrator=orch,
            strategies=["full_context", "rag"],
        )
        configs = msp._build_strategy_configs()
        # full_context keeps default
        assert configs["full_context"].refinement_reps == 3
        # rag should be overridden to 7
        assert configs["rag"].refinement_reps == 7


# ---------------------------------------------------------------------------
# Bug #270: No exception handling in strategy loop
# ---------------------------------------------------------------------------


class TestStrategyLoopExceptionHandling:
    """If one strategy crashes, accumulated results must be preserved."""

    def test_strategy_crash_does_not_lose_results(self) -> None:
        """A crash in strategy 2 must not discard strategy 1's results."""
        config = PipelineConfig(models=["m"])
        orch = _make_mock_orchestrator()
        orch.config = MagicMock()
        orch.config.eval_config = EvalRunConfig()
        orch.config.strategy_config = StrategyConfig()

        msp = MultiStrategyPipeline(
            config=config,
            orchestrator=orch,
            strategies=["full_context", "rag", "tool_based"],
        )

        screening = PhaseResult(
            run_id="r1", phase="screening", trials=[],
            total_cost=1.0, elapsed_seconds=5.0,
        )
        good_result = PipelineResult(
            pipeline_id="p1",
            screening=screening,
            total_trials=10,
            total_cost=1.0,
            elapsed_seconds=5.0,
        )

        call_count = 0

        def run_side_effect(self_pipeline, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Strategy 'rag' exploded")
            return good_result

        with patch.object(DOEPipeline, "run", run_side_effect):
            result = msp.run(
                tasks=[], variants=_make_variants(), doc_tree=MagicMock()
            )

        # full_context and tool_based should be present; rag missing
        assert isinstance(result, MultiStrategyResult)
        assert "full_context" in result.strategy_results
        assert "rag" not in result.strategy_results
        assert "tool_based" in result.strategy_results

    def test_strategy_crash_is_logged(self, caplog) -> None:
        """A crash in one strategy must produce a log message."""
        config = PipelineConfig(models=["m"])
        orch = _make_mock_orchestrator()
        orch.config = MagicMock()
        orch.config.eval_config = EvalRunConfig()
        orch.config.strategy_config = StrategyConfig()

        msp = MultiStrategyPipeline(
            config=config,
            orchestrator=orch,
            strategies=["rag"],
        )

        def crash(*args, **kwargs):
            raise RuntimeError("boom")

        with patch.object(DOEPipeline, "run", crash), \
             caplog.at_level(logging.ERROR, logger="agent_evals.pipeline"):
            result = msp.run(
                tasks=[], variants=_make_variants(), doc_tree=MagicMock()
            )

        assert "rag" not in result.strategy_results
        assert any(
            "rag" in r.message and "boom" in r.message
            for r in caplog.records
        )


# ---------------------------------------------------------------------------
# Bug #259: Unknown strategy name in _build_strategy_configs warns
# ---------------------------------------------------------------------------


class TestUnknownStrategyWarning:
    """_build_strategy_configs should warn about unknown strategy names."""

    def test_unknown_strategy_name_logs_warning(self, caplog) -> None:
        """Typo in strategies list should produce a WARNING."""
        config = PipelineConfig(models=["m"])
        orch = _make_mock_orchestrator()
        msp = MultiStrategyPipeline(
            config=config,
            orchestrator=orch,
            strategies=["full_context", "rga"],  # typo
        )
        with caplog.at_level(logging.WARNING, logger="agent_evals.pipeline"):
            configs = msp._build_strategy_configs()

        # Config should still be built (non-blocking)
        assert "rga" in configs
        # But a WARNING should have been logged
        assert any(
            "rga" in r.message for r in caplog.records
            if r.levelno >= logging.WARNING
        )
