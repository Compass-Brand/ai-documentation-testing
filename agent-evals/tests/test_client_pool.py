"""Tests for LLMClientPool managing multiple model clients.

Covers E2-S1: Multi-Model LLM Client Pool.
"""

from __future__ import annotations

import threading

import pytest

from agent_evals.llm.client_pool import LLMClientPool


class TestLLMClientPoolCreation:
    """Tests for pool creation and model listing."""

    def test_create_with_models(self) -> None:
        pool = LLMClientPool(
            models=["model-a", "model-b"],
            api_key="test-key",
        )
        assert len(pool.models) == 2

    def test_models_property_returns_configured_models(self) -> None:
        pool = LLMClientPool(
            models=["a", "b", "c"],
            api_key="test-key",
        )
        assert pool.models == ["a", "b", "c"]

    def test_models_property_preserves_order(self) -> None:
        pool = LLMClientPool(
            models=["z-model", "a-model", "m-model"],
            api_key="test-key",
        )
        assert pool.models == ["z-model", "a-model", "m-model"]

    def test_create_empty_pool(self) -> None:
        pool = LLMClientPool(models=[], api_key="test-key")
        assert pool.models == []

    def test_get_all_models_returns_same_as_models(self) -> None:
        pool = LLMClientPool(
            models=["a", "b"],
            api_key="test-key",
        )
        assert pool.get_all_models() == pool.models


class TestLLMClientPoolGetClient:
    """Tests for get_client() lazy client creation."""

    def test_get_client_returns_correct_model(self) -> None:
        pool = LLMClientPool(models=["model-a"], api_key="test-key")
        client = pool.get_client("model-a")
        assert client.model == "model-a"

    def test_get_unknown_model_raises_key_error(self) -> None:
        pool = LLMClientPool(models=["model-a"], api_key="test-key")
        with pytest.raises(KeyError, match="model-b"):
            pool.get_client("model-b")

    def test_get_client_returns_same_instance(self) -> None:
        """Lazy creation should cache clients."""
        pool = LLMClientPool(models=["model-a"], api_key="test-key")
        client1 = pool.get_client("model-a")
        client2 = pool.get_client("model-a")
        assert client1 is client2

    def test_temperature_passed_to_all_clients(self) -> None:
        pool = LLMClientPool(
            models=["a", "b"],
            api_key="key",
            temperature=0.7,
        )
        assert pool.get_client("a").temperature == 0.7
        assert pool.get_client("b").temperature == 0.7

    def test_api_key_passed_to_clients(self) -> None:
        pool = LLMClientPool(models=["m"], api_key="my-key")
        client = pool.get_client("m")
        assert client.api_key == "my-key"

    def test_provider_config_passed_to_clients(self) -> None:
        config = {"order": ["Anthropic"]}
        pool = LLMClientPool(
            models=["m"],
            api_key="key",
            provider_config=config,
        )
        client = pool.get_client("m")
        assert client.provider_config == config


class TestLLMClientPoolBudget:
    """Tests for per-model and global budget tracking."""

    def test_record_cost_accumulates_per_model(self) -> None:
        pool = LLMClientPool(models=["a", "b"], api_key="key")
        pool.record_cost("a", 0.10)
        pool.record_cost("a", 0.05)
        pool.record_cost("b", 0.20)
        assert pool.get_model_cost("a") == pytest.approx(0.15)
        assert pool.get_model_cost("b") == pytest.approx(0.20)

    def test_is_budget_exceeded_false_when_no_budget(self) -> None:
        pool = LLMClientPool(models=["a"], api_key="key")
        pool.record_cost("a", 100.0)
        assert pool.is_budget_exceeded("a") is False

    def test_is_budget_exceeded_with_per_model_budget(self) -> None:
        pool = LLMClientPool(
            models=["a"],
            api_key="key",
            model_budgets={"a": 0.50},
        )
        pool.record_cost("a", 0.30)
        assert pool.is_budget_exceeded("a") is False
        pool.record_cost("a", 0.25)
        assert pool.is_budget_exceeded("a") is True

    def test_global_budget_exceeded(self) -> None:
        pool = LLMClientPool(
            models=["a", "b"],
            api_key="key",
            global_budget=1.00,
        )
        pool.record_cost("a", 0.60)
        pool.record_cost("b", 0.50)
        assert pool.is_global_budget_exceeded() is True

    def test_global_budget_not_exceeded(self) -> None:
        pool = LLMClientPool(
            models=["a", "b"],
            api_key="key",
            global_budget=2.00,
        )
        pool.record_cost("a", 0.60)
        pool.record_cost("b", 0.30)
        assert pool.is_global_budget_exceeded() is False

    def test_global_budget_none_never_exceeded(self) -> None:
        pool = LLMClientPool(models=["a"], api_key="key")
        pool.record_cost("a", 999.0)
        assert pool.is_global_budget_exceeded() is False

    def test_get_budget_state_returns_all_models(self) -> None:
        pool = LLMClientPool(
            models=["a", "b"],
            api_key="key",
            model_budgets={"a": 1.00},
            global_budget=5.00,
        )
        pool.record_cost("a", 0.25)
        pool.record_cost("b", 0.10)
        state = pool.get_budget_state()

        assert state["global_budget"] == 5.00
        assert state["global_spent"] == pytest.approx(0.35)
        assert state["models"]["a"]["spent"] == pytest.approx(0.25)
        assert state["models"]["a"]["budget"] == 1.00
        assert state["models"]["b"]["spent"] == pytest.approx(0.10)
        assert state["models"]["b"]["budget"] is None

    def test_record_cost_unknown_model_raises(self) -> None:
        pool = LLMClientPool(models=["a"], api_key="key")
        with pytest.raises(KeyError, match="unknown"):
            pool.record_cost("unknown", 0.10)

    def test_get_model_cost_unknown_model_raises(self) -> None:
        pool = LLMClientPool(models=["a"], api_key="key")
        with pytest.raises(KeyError, match="unknown"):
            pool.get_model_cost("unknown")


class TestLLMClientPoolThreadSafety:
    """Tests for thread-safe concurrent access."""

    def test_concurrent_get_client_returns_same_instance(self) -> None:
        """Multiple threads calling get_client should all get the same instance."""
        pool = LLMClientPool(models=["model-a"], api_key="key")
        results: list[object] = []
        barrier = threading.Barrier(10)

        def _get() -> None:
            barrier.wait()
            results.append(pool.get_client("model-a"))

        threads = [threading.Thread(target=_get) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 10
        assert all(r is results[0] for r in results)

    def test_concurrent_record_cost_is_consistent(self) -> None:
        """Multiple threads recording costs should produce correct totals."""
        pool = LLMClientPool(models=["a"], api_key="key")
        barrier = threading.Barrier(50)

        def _record() -> None:
            barrier.wait()
            pool.record_cost("a", 0.01)

        threads = [threading.Thread(target=_record) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert pool.get_model_cost("a") == pytest.approx(0.50)
