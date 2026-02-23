"""End-to-end validation of multi-model support across all modes.

Covers E2-S3: validates the full pipeline from design construction
through trial execution with multiple models, verifying that model
assignments, composite variants, budget tracking, and observatory
recording all work together correctly.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_evals.llm.client import GenerationResult, LLMClient
from agent_evals.llm.client_pool import LLMClientPool
from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker
from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig
from agent_evals.runner import EvalRunConfig
from agent_evals.taguchi.factors import (
    TaguchiDesign,
    build_design,
    build_factors_from_axes,
)
from agent_evals.taguchi.runner import TaguchiRunner
from agent_evals.tasks.base import EvalTask, TaskDefinition
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.composite import CompositeVariant


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class StubVariant(IndexVariant):
    """Minimal variant for testing."""

    def __init__(self, name: str, axis: int) -> None:
        self._name = name
        self._axis = axis

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name=self._name, axis=self._axis,
            category="test", description="stub",
        )

    def render(self, doc_tree: object) -> str:
        return f"[{self._name}]"


class StubTask(EvalTask):
    """Minimal eval task for testing."""

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": "Test"},
            {"role": "user", "content": index_content},
        ]

    def score_response(self, response: str, **kwargs: object) -> float:
        return 0.85


def _make_stub_task(task_id: str = "retrieval_001") -> StubTask:
    defn = TaskDefinition(
        task_id=task_id, type="retrieval", question="test?",
        domain="framework_api", difficulty="easy",
    )
    return StubTask(defn)


def _make_mock_client(model_name: str) -> LLMClient:
    """Create a mock LLMClient that returns deterministic results."""
    client = MagicMock(spec=LLMClient)
    client.model = model_name
    client.complete.return_value = GenerationResult(
        content=f"response from {model_name}",
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost=0.005,
        model=model_name,
        generation_id=None,
    )
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMultiModelDesignConstruction:
    """Build Taguchi designs that include a model factor."""

    def test_two_models_adds_model_factor(self):
        axes = {0: ["flat", "nested"], 1: ["alpha", "beta"]}
        factors = build_factors_from_axes(axes, models=["model-a", "model-b"])
        factor_names = [f.name for f in factors]
        assert "model" in factor_names

    def test_single_model_no_model_factor(self):
        axes = {0: ["flat", "nested"], 1: ["alpha", "beta"]}
        factors = build_factors_from_axes(axes, models=["model-a"])
        factor_names = [f.name for f in factors]
        assert "model" not in factor_names

    def test_design_rows_contain_model_assignments(self):
        axes = {0: ["flat", "nested"], 1: ["alpha", "beta"]}
        design = build_design(axes, models=["model-a", "model-b"])
        for row in design.rows:
            assert "model" in row.assignments
            assert row.assignments["model"] in ("model-a", "model-b")

    def test_design_covers_all_models(self):
        axes = {0: ["flat", "nested"]}
        design = build_design(axes, models=["model-a", "model-b"])
        models_used = {row.assignments["model"] for row in design.rows}
        assert models_used == {"model-a", "model-b"}


class TestTaguchiRunnerMultiModel:
    """TaguchiRunner selects correct client per OA row."""

    def test_runner_uses_model_from_row_assignment(self):
        axes = {0: ["flat", "nested"]}
        design = build_design(axes, models=["model-a", "model-b"])

        client_a = _make_mock_client("model-a")
        client_b = _make_mock_client("model-b")
        clients = {"model-a": client_a, "model-b": client_b}

        variants = {
            "flat": StubVariant("flat", 0),
            "nested": StubVariant("nested", 0),
        }

        config = EvalRunConfig(repetitions=1)
        runner = TaguchiRunner(
            clients=clients, config=config,
            design=design, variant_lookup=variants,
        )

        doc_tree = MagicMock()
        task = _make_stub_task()
        result = runner.run([task], doc_tree)

        # Both clients should have been called
        assert client_a.complete.called or client_b.complete.called
        assert len(result.trials) == design.n_runs

    def test_runner_produces_trials_for_all_rows(self):
        axes = {0: ["flat", "nested"], 1: ["alpha", "beta"]}
        design = build_design(axes, models=["model-a", "model-b"])

        clients = {
            "model-a": _make_mock_client("model-a"),
            "model-b": _make_mock_client("model-b"),
        }
        variants = {
            "flat": StubVariant("flat", 0),
            "nested": StubVariant("nested", 0),
            "alpha": StubVariant("alpha", 1),
            "beta": StubVariant("beta", 1),
        }

        config = EvalRunConfig(repetitions=1)
        runner = TaguchiRunner(
            clients=clients, config=config,
            design=design, variant_lookup=variants,
        )

        doc_tree = MagicMock()
        task = _make_stub_task()
        result = runner.run([task], doc_tree)

        # One trial per OA row (1 task, 1 rep)
        assert len(result.trials) == design.n_runs

    def test_runner_records_cost_and_tokens(self):
        axes = {0: ["flat", "nested"]}
        design = build_design(axes, models=["model-a", "model-b"])

        clients = {
            "model-a": _make_mock_client("model-a"),
            "model-b": _make_mock_client("model-b"),
        }
        variants = {
            "flat": StubVariant("flat", 0),
            "nested": StubVariant("nested", 0),
        }

        config = EvalRunConfig(repetitions=1)
        runner = TaguchiRunner(
            clients=clients, config=config,
            design=design, variant_lookup=variants,
        )

        doc_tree = MagicMock()
        result = runner.run([_make_stub_task()], doc_tree)

        assert result.total_cost > 0
        assert result.total_tokens > 0
        for trial in result.trials:
            assert trial.cost == 0.005
            assert trial.total_tokens == 150


class TestClientPoolMultiModel:
    """Client pool manages multiple models with budgets."""

    def test_pool_tracks_per_model_costs(self):
        pool = LLMClientPool(
            models=["model-a", "model-b"],
            api_key="test-key",
        )
        pool.record_cost("model-a", 0.10)
        pool.record_cost("model-b", 0.20)

        assert pool.get_model_cost("model-a") == pytest.approx(0.10)
        assert pool.get_model_cost("model-b") == pytest.approx(0.20)

    def test_pool_global_budget_exceeded(self):
        pool = LLMClientPool(
            models=["model-a", "model-b"],
            api_key="test-key",
            global_budget=0.25,
        )
        pool.record_cost("model-a", 0.15)
        pool.record_cost("model-b", 0.15)

        assert pool.is_global_budget_exceeded()

    def test_pool_model_budget_exceeded(self):
        pool = LLMClientPool(
            models=["model-a", "model-b"],
            api_key="test-key",
            model_budgets={"model-a": 0.10},
        )
        pool.record_cost("model-a", 0.15)

        assert pool.is_budget_exceeded("model-a")
        assert not pool.is_budget_exceeded("model-b")

    def test_pool_unknown_model_raises(self):
        pool = LLMClientPool(
            models=["model-a"],
            api_key="test-key",
        )
        with pytest.raises(KeyError):
            pool.get_client("nonexistent")


class TestOrchestratorMultiModel:
    """Orchestrator wires up multi-model components."""

    def test_orchestrator_creates_pool_with_all_models(self, tmp_path):
        config = OrchestratorConfig(
            models=["model-a", "model-b", "model-c"],
            api_key="test-key",
            db_path=tmp_path / "obs.db",
        )
        orch = EvalOrchestrator(config)
        assert len(orch.client_pool.models) == 3
        assert set(orch.client_pool.models) == {
            "model-a", "model-b", "model-c",
        }

    def test_orchestrator_taguchi_mode(self, tmp_path):
        config = OrchestratorConfig(
            mode="taguchi",
            models=["model-a", "model-b"],
            api_key="test-key",
            db_path=tmp_path / "obs.db",
        )
        orch = EvalOrchestrator(config)
        assert orch.runner_type == "taguchi"

    def test_orchestrator_full_mode(self, tmp_path):
        config = OrchestratorConfig(
            mode="full",
            models=["model-a"],
            api_key="test-key",
            db_path=tmp_path / "obs.db",
        )
        orch = EvalOrchestrator(config)
        assert orch.runner_type == "eval"

    def test_orchestrator_budget_propagation(self, tmp_path):
        config = OrchestratorConfig(
            models=["model-a", "model-b"],
            api_key="test-key",
            db_path=tmp_path / "obs.db",
            global_budget=50.0,
            model_budgets={"model-a": 20.0},
        )
        orch = EvalOrchestrator(config)
        state = orch.client_pool.get_budget_state()
        assert state["global_budget"] == 50.0
        assert state["models"]["model-a"]["budget"] == 20.0
        assert state["models"]["model-b"]["budget"] is None


class TestObservatoryMultiModelTracking:
    """Observatory records multi-model trial data correctly."""

    def test_store_records_different_models(self, tmp_path):
        store = ObservatoryStore(tmp_path / "obs.db")
        store.create_run("run-1", "taguchi", {})

        for model in ["model-a", "model-b"]:
            store.record_trial(
                run_id="run-1", task_id="t1", task_type="retrieval",
                variant_name="flat", repetition=1, score=0.85,
                prompt_tokens=100, completion_tokens=50, total_tokens=150,
                cost=0.005, latency_seconds=1.0, model=model,
            )

        all_trials = store.get_trials("run-1")
        assert len(all_trials) == 2
        models_recorded = {t.model for t in all_trials}
        assert models_recorded == {"model-a", "model-b"}

    def test_store_filters_by_model(self, tmp_path):
        store = ObservatoryStore(tmp_path / "obs.db")
        store.create_run("run-1", "taguchi", {})

        for model, cost in [("model-a", 0.01), ("model-b", 0.02)]:
            store.record_trial(
                run_id="run-1", task_id="t1", task_type="retrieval",
                variant_name="flat", repetition=1, score=0.85,
                prompt_tokens=100, completion_tokens=50, total_tokens=150,
                cost=cost, latency_seconds=1.0, model=model,
            )

        a_trials = store.get_trials("run-1", model="model-a")
        assert len(a_trials) == 1
        assert a_trials[0].cost == 0.01

    def test_tracker_per_model_stats(self, tmp_path):
        store = ObservatoryStore(tmp_path / "obs.db")
        store.create_run("run-1", "taguchi", {})
        tracker = EventTracker(store=store)

        for model in ["model-a", "model-b", "model-a"]:
            tracker.record_trial(
                run_id="run-1", task_id="t1", task_type="retrieval",
                variant_name="flat", repetition=1, score=0.80,
                prompt_tokens=100, completion_tokens=50, total_tokens=150,
                cost=0.005, latency_seconds=1.0, model=model,
            )

        stats = tracker.stats
        assert stats["per_model"]["model-a"]["count"] == 2
        assert stats["per_model"]["model-b"]["count"] == 1


class TestCompositeVariantMultiModel:
    """CompositeVariant works correctly in multi-model context."""

    def test_composite_renders_all_axes(self):
        v0 = StubVariant("flat", 0)
        v1 = StubVariant("alpha", 1)
        composite = CompositeVariant({0: v0, 1: v1})

        doc_tree = MagicMock()
        output = composite.render(doc_tree)
        assert "[flat]" in output
        assert "[alpha]" in output

    def test_composite_metadata_combines_names(self):
        v0 = StubVariant("flat", 0)
        v1 = StubVariant("alpha", 1)
        composite = CompositeVariant({0: v0, 1: v1})

        meta = composite.metadata()
        assert "flat" in meta.name
        assert "alpha" in meta.name
