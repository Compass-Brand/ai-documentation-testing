"""Tests for the context strategy module (Phase 1).

Tests cover:
- ContextStrategy ABC interface enforcement
- FullContextStrategy.prepare() produces correct messages
- FullContextStrategy.execute() wraps client response correctly
- FullContextStrategy.supports_caching() returns True
- StrategyConfig defaults
- PreparedContext and StrategyResult dataclass construction
- Registry discovers FullContextStrategy
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from conftest import make_mock_client, make_mock_task


# ---------------------------------------------------------------------------
# ContextStrategy ABC
# ---------------------------------------------------------------------------


class TestContextStrategyABC:
    """ContextStrategy enforces the abstract interface."""

    def test_cannot_instantiate_abc_directly(self):
        from agent_evals.context.base import ContextStrategy

        with pytest.raises(TypeError):
            ContextStrategy()

    def test_subclass_must_implement_name(self):
        from agent_evals.context.base import ContextStrategy, PreparedContext, StrategyResult

        class Incomplete(ContextStrategy):
            def prepare(self, rendered_index, task, doc_tree):
                return PreparedContext(messages=[], tools=None, strategy_metadata={})

            def execute(self, prepared, task, client, max_tokens, temperature):
                return StrategyResult(
                    final_response="",
                    generations=[],
                    total_prompt_tokens=0,
                    total_completion_tokens=0,
                    total_tokens=0,
                    total_cost=None,
                    messages=[],
                    strategy_metadata={},
                )

        with pytest.raises(TypeError):
            Incomplete()

    def test_subclass_must_implement_prepare(self):
        from agent_evals.context.base import ContextStrategy

        class Incomplete(ContextStrategy):
            def name(self) -> str:
                return "incomplete"

            def execute(self, prepared, task, client, max_tokens, temperature):
                pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_subclass_must_implement_execute(self):
        from agent_evals.context.base import ContextStrategy

        class Incomplete(ContextStrategy):
            def name(self) -> str:
                return "incomplete"

            def prepare(self, rendered_index, task, doc_tree):
                pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_setup_default_is_noop(self):
        from agent_evals.context.base import ContextStrategy, PreparedContext, StrategyResult

        class Minimal(ContextStrategy):
            def name(self) -> str:
                return "minimal"

            def prepare(self, rendered_index, task, doc_tree):
                return PreparedContext(messages=[], tools=None, strategy_metadata={})

            def execute(self, prepared, task, client, max_tokens, temperature):
                return StrategyResult(
                    final_response="",
                    generations=[],
                    total_prompt_tokens=0,
                    total_completion_tokens=0,
                    total_tokens=0,
                    total_cost=None,
                    messages=[],
                    strategy_metadata={},
                )

        strategy = Minimal()
        # Default setup/teardown should be no-ops (not raise)
        strategy.setup("index", MagicMock())
        strategy.teardown()

    def test_supports_caching_default_true(self):
        from agent_evals.context.base import ContextStrategy, PreparedContext, StrategyResult

        class Minimal(ContextStrategy):
            def name(self) -> str:
                return "minimal"

            def prepare(self, rendered_index, task, doc_tree):
                return PreparedContext(messages=[], tools=None, strategy_metadata={})

            def execute(self, prepared, task, client, max_tokens, temperature):
                return StrategyResult(
                    final_response="",
                    generations=[],
                    total_prompt_tokens=0,
                    total_completion_tokens=0,
                    total_tokens=0,
                    total_cost=None,
                    messages=[],
                    strategy_metadata={},
                )

        assert Minimal().supports_caching() is True


# ---------------------------------------------------------------------------
# PreparedContext dataclass
# ---------------------------------------------------------------------------


class TestPreparedContext:
    def test_construction(self):
        from agent_evals.context.base import PreparedContext

        ctx = PreparedContext(
            messages=[{"role": "user", "content": "hello"}],
            tools=None,
            strategy_metadata={"key": "value"},
        )
        assert ctx.messages == [{"role": "user", "content": "hello"}]
        assert ctx.tools is None
        assert ctx.strategy_metadata == {"key": "value"}

    def test_with_tools(self):
        from agent_evals.context.base import PreparedContext

        tools = [{"type": "function", "function": {"name": "test"}}]
        ctx = PreparedContext(
            messages=[],
            tools=tools,
            strategy_metadata={},
        )
        assert ctx.tools == tools


# ---------------------------------------------------------------------------
# StrategyResult dataclass
# ---------------------------------------------------------------------------


class TestStrategyResult:
    def test_construction(self):
        from agent_evals.context.base import StrategyResult

        result = StrategyResult(
            final_response="answer",
            generations=[],
            total_prompt_tokens=100,
            total_completion_tokens=50,
            total_tokens=150,
            total_cost=0.005,
            messages=[{"role": "user", "content": "q"}],
            strategy_metadata={},
        )
        assert result.final_response == "answer"
        assert result.total_tokens == 150
        assert result.total_cost == 0.005

    def test_with_generation_results(self):
        from agent_evals.context.base import StrategyResult
        from agent_evals.llm.client import GenerationResult

        gen = GenerationResult(
            content="response",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost=0.001,
            model="test",
            generation_id="gen-1",
        )
        result = StrategyResult(
            final_response="response",
            generations=[gen],
            total_prompt_tokens=10,
            total_completion_tokens=5,
            total_tokens=15,
            total_cost=0.001,
            messages=[],
            strategy_metadata={},
        )
        assert len(result.generations) == 1
        assert result.generations[0].content == "response"


# ---------------------------------------------------------------------------
# StrategyConfig dataclass
# ---------------------------------------------------------------------------


class TestStrategyConfig:
    def test_defaults(self):
        from agent_evals.context.base import StrategyConfig

        cfg = StrategyConfig()
        assert cfg.strategy == "full_context"
        assert cfg.token_budget is None
        assert cfg.truncation == "hard"
        assert cfg.chunk_method == "heading"
        assert cfg.rag_top_k == 5
        assert cfg.embedding_model == "text-embedding-3-small"
        assert cfg.max_turns == 10

    def test_custom_values(self):
        from agent_evals.context.base import StrategyConfig

        cfg = StrategyConfig(
            strategy="rag",
            token_budget=4096,
            rag_top_k=10,
        )
        assert cfg.strategy == "rag"
        assert cfg.token_budget == 4096
        assert cfg.rag_top_k == 10


# ---------------------------------------------------------------------------
# FullContextStrategy
# ---------------------------------------------------------------------------


class TestFullContextStrategy:
    def test_name(self):
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy()
        assert strategy.name() == "full_context"

    def test_supports_caching(self):
        from agent_evals.context.full import FullContextStrategy

        assert FullContextStrategy().supports_caching() is True

    def test_prepare_calls_build_prompt(self):
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy()
        task = make_mock_task()
        doc_tree = MagicMock()

        prepared = strategy.prepare("rendered index", task, doc_tree)

        task.build_prompt.assert_called_once_with("rendered index")
        assert prepared.messages == task.build_prompt.return_value
        assert prepared.tools is None
        assert prepared.strategy_metadata == {}

    def test_execute_calls_client_complete(self):
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.full import FullContextStrategy
        from agent_evals.llm.client import GenerationResult

        strategy = FullContextStrategy()
        messages = [{"role": "user", "content": "test"}]
        prepared = PreparedContext(
            messages=messages,
            tools=None,
            strategy_metadata={},
        )

        client = make_mock_client()
        gen = GenerationResult(
            content="response text",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.005,
            model="mock-model",
            generation_id="gen-1",
        )
        client.complete.return_value = gen

        task = make_mock_task()
        result = strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        client.complete.assert_called_once_with(
            messages,
            max_tokens=2048,
            temperature=0.3,
        )
        assert result.final_response == "response text"
        assert result.total_prompt_tokens == 100
        assert result.total_completion_tokens == 50
        assert result.total_tokens == 150
        assert result.total_cost == 0.005
        assert len(result.generations) == 1
        assert result.generations[0] is gen
        assert result.messages == messages

    def test_execute_produces_identical_results_to_current_behavior(self):
        """FullContextStrategy must produce the same output as the old
        render → build_prompt → complete pipeline."""
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.full import FullContextStrategy
        from agent_evals.llm.client import GenerationResult

        strategy = FullContextStrategy()
        task = make_mock_task()
        doc_tree = MagicMock()
        client = make_mock_client()

        gen = GenerationResult(
            content="LLM answer",
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
            cost=0.01,
            model="test-model",
            generation_id="gen-2",
        )
        client.complete.return_value = gen

        # Old pipeline: variant.render() → task.build_prompt(index) → client.complete(messages)
        rendered_index = "# Docs\nSome content"
        messages_old = task.build_prompt(rendered_index)

        # New pipeline: strategy.prepare() → strategy.execute()
        task.build_prompt.reset_mock()
        prepared = strategy.prepare(rendered_index, task, doc_tree)
        result = strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        # Messages built identically
        assert prepared.messages == messages_old
        # Final response matches generation content
        assert result.final_response == gen.content
        # Tokens match
        assert result.total_prompt_tokens == gen.prompt_tokens
        assert result.total_completion_tokens == gen.completion_tokens
        assert result.total_tokens == gen.total_tokens
        assert result.total_cost == gen.cost

    def test_setup_teardown_are_noops(self):
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy()
        # Should not raise
        strategy.setup("index content", MagicMock())
        strategy.teardown()


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestContextRegistry:
    def test_get_all_strategies_includes_full_context(self):
        from agent_evals.context.registry import get_all_strategies, load_all

        load_all()
        strategies = get_all_strategies()
        names = [s.name() for s in strategies]
        assert "full_context" in names

    def test_get_strategy_by_name(self):
        from agent_evals.context.registry import get_strategy_by_name, load_all

        load_all()
        strategy = get_strategy_by_name("full_context")
        assert strategy is not None
        assert strategy.name() == "full_context"

    def test_get_strategy_by_name_returns_none_for_unknown(self):
        from agent_evals.context.registry import get_strategy_by_name, load_all

        load_all()
        assert get_strategy_by_name("nonexistent") is None

    def test_clear_registry(self):
        from agent_evals.context.registry import (
            clear_registry,
            get_all_strategies,
            load_all,
        )

        load_all()
        assert len(get_all_strategies()) > 0
        clear_registry()
        assert len(get_all_strategies()) == 0

    def test_load_all_is_idempotent(self):
        from agent_evals.context.registry import get_all_strategies, load_all

        load_all()
        count1 = len(get_all_strategies())
        load_all()
        count2 = len(get_all_strategies())
        assert count1 == count2


# ---------------------------------------------------------------------------
# Public API (__init__.py exports)
# ---------------------------------------------------------------------------


class TestPublicAPI:
    def test_imports_from_context_package(self):
        from agent_evals.context import (
            ContextStrategy,
            FullContextStrategy,
            PreparedContext,
            StrategyConfig,
            StrategyResult,
        )

        assert ContextStrategy is not None
        assert FullContextStrategy is not None
        assert PreparedContext is not None
        assert StrategyResult is not None
        assert StrategyConfig is not None
