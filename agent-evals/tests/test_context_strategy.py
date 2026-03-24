"""Tests for the context strategy module (Phase 1).

Tests cover:
- ContextStrategy ABC interface enforcement
- FullContextStrategy.prepare() appends doc content to rendered index
- FullContextStrategy.prepare() respects max_content_tokens budget
- FullContextStrategy.execute() wraps client response correctly
- FullContextStrategy.supports_caching() returns True
- StrategyConfig defaults
- PreparedContext and StrategyResult dataclass construction
- Registry discovers FullContextStrategy
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from conftest import make_mock_client, make_mock_task


def _make_doc_tree(
    files: dict[str, tuple[str, int | None]],
):
    """Build a DocTree for testing.

    Args:
        files: Mapping of rel_path -> (content, token_count).
            token_count may be None to test the heuristic fallback.
    """
    from agent_index.models import DocFile, DocTree

    doc_files = {}
    for rel_path, (content, token_count) in files.items():
        doc_files[rel_path] = DocFile(
            rel_path=rel_path,
            content=content,
            size_bytes=len(content.encode()),
            token_count=token_count,
            tier="recommended",
            section="General",
        )

    return DocTree(
        files=doc_files,
        scanned_at=datetime.now(tz=UTC),
        source="/test",
        total_tokens=sum(
            tc for _, (_, tc) in files.items() if tc is not None
        ),
    )


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

    def test_prepare_passes_rendered_index_directly(self):
        """prepare() should pass rendered index directly to build_prompt
        without appending raw doc content (fixes #193)."""
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy()
        task = make_mock_task()
        doc_tree = _make_doc_tree({
            "guides/auth.md": ("Auth guide content", 10),
        })

        prepared = strategy.prepare("rendered index", task, doc_tree)

        # build_prompt should receive the rendered index as-is
        call_args = task.build_prompt.call_args[0][0]
        assert call_args == "rendered index"
        assert prepared.messages == task.build_prompt.return_value
        assert prepared.tools is None

    def test_prepare_with_empty_doc_tree_passes_index_only(self):
        """When doc_tree has no files, rendered index is passed as-is."""
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy()
        task = make_mock_task()
        doc_tree = _make_doc_tree({})

        strategy.prepare("rendered index", task, doc_tree)

        task.build_prompt.assert_called_once_with("rendered index")

    def test_prepare_passes_rendered_index_as_is(self):
        """prepare() passes rendered_index directly regardless of doc_tree content."""
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy()
        task = make_mock_task()
        doc_tree = _make_doc_tree({
            "guides/setup.md": ("Setup content", 10),
            "api/endpoints.md": ("API content", 10),
            "guides/auth.md": ("Auth content", 10),
        })

        strategy.prepare("my custom index", task, doc_tree)

        call_args = task.build_prompt.call_args[0][0]
        assert call_args == "my custom index"

    def test_prepare_strategy_metadata(self):
        """strategy_metadata should include index token stats but NOT max_content_tokens.

        max_content_tokens was removed (Bug #264) because it implied a truncation
        guarantee that FullContextStrategy does not enforce — truncation is
        SystemPromptStrategy's job. FullContextStrategy passes everything through.
        """
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy(max_content_tokens=1000)
        task = make_mock_task()
        doc_tree = _make_doc_tree({
            "a.md": ("Content", 50),
            "b.md": ("More content", 60),
        })

        prepared = strategy.prepare("the index", task, doc_tree)

        assert "index_tokens" in prepared.strategy_metadata
        assert "max_content_tokens" not in prepared.strategy_metadata

    def test_default_max_content_tokens(self):
        """Default max_content_tokens should be 50000."""
        from agent_evals.context.full import DEFAULT_MAX_CONTENT_TOKENS, FullContextStrategy

        strategy = FullContextStrategy()
        assert strategy._max_content_tokens == DEFAULT_MAX_CONTENT_TOKENS
        assert DEFAULT_MAX_CONTENT_TOKENS == 50_000

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

    def test_prepare_passes_rendered_index_without_raw_content(self):
        """prepare() uses only the rendered index -- variant-rendered content
        is the experimental treatment; appending raw doc content would dilute
        axis effects across variants (#193)."""
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy()
        task = make_mock_task()
        doc_tree = _make_doc_tree({
            "guides/auth.md": ("# Authentication\nUse JWT tokens...", 20),
            "api/users.md": ("# Users API\nGET /api/users...", 15),
        })

        rendered_index = "[FILE] guides/auth.md: Auth guide\n[FILE] api/users.md: Users API"
        strategy.prepare(rendered_index, task, doc_tree)

        call_args = task.build_prompt.call_args[0][0]
        # Should contain the rendered index
        assert "[FILE] guides/auth.md: Auth guide" in call_args
        # Should NOT append raw doc content
        assert "# Authentication\nUse JWT tokens..." not in call_args
        assert "# Users API\nGET /api/users..." not in call_args

    def test_prepare_uses_only_rendered_index_not_raw_doc_content(self):
        """prepare() should use only the rendered_index, not append raw doc
        content from doc_tree.files, because the rendered index IS the
        variant-specific content. Appending raw docs dilutes axis effects (#193)."""
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy()
        task = make_mock_task()
        doc_tree = _make_doc_tree({
            "a.md": ("Raw content A", 10),
            "b.md": ("Raw content B", 10),
        })

        # Two different rendered indices (simulating different variants)
        rendered_flat = "FLAT INDEX: a.md, b.md"
        rendered_nested = "NESTED INDEX:\n  section/\n    a.md\n    b.md"

        strategy.prepare(rendered_flat, task, doc_tree)
        flat_content = task.build_prompt.call_args[0][0]

        task.reset_mock()
        strategy.prepare(rendered_nested, task, doc_tree)
        nested_content = task.build_prompt.call_args[0][0]

        # The two calls should produce DIFFERENT content
        assert flat_content != nested_content, (
            "FullContextStrategy should produce different content for different "
            "rendered indices — raw doc content must not dilute variant effects"
        )
        # rendered_index should be included
        assert "FLAT INDEX" in flat_content
        assert "NESTED INDEX" in nested_content
        # Raw doc content should NOT be appended (it's the same for both)
        assert "Raw content A" not in flat_content
        assert "Raw content B" not in flat_content

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


# ---------------------------------------------------------------------------
# Bug #268: No None guard on rendered_index in FullContextStrategy
# ---------------------------------------------------------------------------


class TestFullContextStrategyNoneGuard:
    """Bug #268: FullContextStrategy.prepare() must coerce None rendered_index
    to empty string instead of raising TypeError."""

    def test_none_rendered_index_does_not_raise(self):
        """prepare() must not raise TypeError when rendered_index is None."""
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy()
        task = make_mock_task()
        doc_tree = _make_doc_tree({})

        # Must not raise
        prepared = strategy.prepare(None, task, doc_tree)  # type: ignore[arg-type]

        # build_prompt must be called with empty string, not None
        call_args = task.build_prompt.call_args[0][0]
        assert call_args == "", (
            "None rendered_index must be coerced to '' before passing to "
            "build_prompt (Bug #268)"
        )

    def test_none_rendered_index_metadata_is_zero_tokens(self):
        """When rendered_index is None, index_tokens metadata must be 0."""
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy()
        task = make_mock_task()
        doc_tree = _make_doc_tree({})

        prepared = strategy.prepare(None, task, doc_tree)  # type: ignore[arg-type]

        assert prepared.strategy_metadata["index_tokens"] == 0, (
            "index_tokens must be 0 when rendered_index is None (Bug #268)"
        )


# ---------------------------------------------------------------------------
# Bug #256: @register_strategy decorator missing from FullContextStrategy
# ---------------------------------------------------------------------------


class TestFullContextStrategyRegistration:
    """FullContextStrategy must be registered via @register_strategy so it is
    discoverable without relying on load_all()'s __subclasses__ fallback."""

    def test_full_context_registered_on_import_without_load_all(self):
        """Importing full.py alone should register FullContextStrategy.

        The @register_strategy decorator must be present on the class so that
        get_strategy_by_name('full_context') works immediately after import
        without requiring a separate load_all() call.
        """
        from agent_evals.context.registry import clear_registry, get_strategy_by_name

        # Clear so we start fresh (no load_all() residue)
        clear_registry()

        # Import the module — the decorator should fire at import time
        import importlib

        import agent_evals.context.full as full_mod
        importlib.reload(full_mod)

        strategy = get_strategy_by_name("full_context")
        assert strategy is not None, (
            "FullContextStrategy not found in registry after importing full.py. "
            "Add @register_strategy decorator to FullContextStrategy."
        )
        assert strategy.name() == "full_context"

    def test_full_context_strategy_metadata_has_no_max_content_tokens(self):
        """strategy_metadata must NOT include max_content_tokens (Bug #264).

        max_content_tokens was stored in metadata but never enforced, implying
        a truncation guarantee that does not exist. It must be removed to avoid
        misleading callers.
        """
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy()
        task = make_mock_task()
        doc_tree = _make_doc_tree({"a.md": ("content", 10)})
        prepared = strategy.prepare("index content", task, doc_tree)

        assert "max_content_tokens" not in prepared.strategy_metadata, (
            "max_content_tokens must be removed from strategy_metadata — it implies "
            "a truncation guarantee that FullContextStrategy does not enforce (Bug #264)."
        )
