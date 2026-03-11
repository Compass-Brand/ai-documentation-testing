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

from datetime import datetime, timezone
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
        scanned_at=datetime.now(tz=timezone.utc),
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

    def test_prepare_appends_doc_content_to_rendered_index(self):
        """prepare() should pass rendered index + doc content to build_prompt."""
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy()
        task = make_mock_task()
        doc_tree = _make_doc_tree({
            "guides/auth.md": ("Auth guide content", 10),
        })

        prepared = strategy.prepare("rendered index", task, doc_tree)

        # build_prompt should receive index + separator + document content
        call_args = task.build_prompt.call_args[0][0]
        assert call_args.startswith("rendered index")
        assert "---\n## Document Contents" in call_args
        assert "### guides/auth.md" in call_args
        assert "Auth guide content" in call_args
        assert prepared.messages == task.build_prompt.return_value
        assert prepared.tools is None

    def test_prepare_with_empty_doc_tree_passes_index_only(self):
        """When doc_tree has no files, only the rendered index is passed."""
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy()
        task = make_mock_task()
        doc_tree = _make_doc_tree({})

        strategy.prepare("rendered index", task, doc_tree)

        task.build_prompt.assert_called_once_with("rendered index")

    def test_prepare_includes_multiple_files_sorted(self):
        """Files should be included in sorted order by rel_path."""
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy()
        task = make_mock_task()
        doc_tree = _make_doc_tree({
            "guides/setup.md": ("Setup content", 10),
            "api/endpoints.md": ("API content", 10),
            "guides/auth.md": ("Auth content", 10),
        })

        strategy.prepare("index", task, doc_tree)

        call_args = task.build_prompt.call_args[0][0]
        # Files should appear in sorted order
        api_pos = call_args.index("### api/endpoints.md")
        auth_pos = call_args.index("### guides/auth.md")
        setup_pos = call_args.index("### guides/setup.md")
        assert api_pos < auth_pos < setup_pos

    def test_prepare_respects_max_content_tokens(self):
        """Files exceeding the token budget should be excluded."""
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy(max_content_tokens=25)
        task = make_mock_task()
        doc_tree = _make_doc_tree({
            "a.md": ("Small file", 10),
            "b.md": ("Medium file", 15),
            "c.md": ("Large file", 20),
        })

        strategy.prepare("index", task, doc_tree)

        call_args = task.build_prompt.call_args[0][0]
        # a.md (10 tokens) fits, b.md (15 tokens) would push to 25 -- fits exactly at boundary?
        # 10 + 15 = 25, which is NOT > 25, so b.md fits
        assert "### a.md" in call_args
        assert "### b.md" in call_args
        # c.md (20 tokens) would push to 45 > 25, excluded
        assert "### c.md" not in call_args

    def test_prepare_stops_at_first_file_exceeding_budget(self):
        """Token budget enforcement stops at the first file that would exceed it."""
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy(max_content_tokens=5)
        task = make_mock_task()
        doc_tree = _make_doc_tree({
            "a.md": ("Content A", 10),  # 10 > 5, excluded
            "b.md": ("Content B", 3),   # Would be fine but a.md broke the loop
        })

        strategy.prepare("index", task, doc_tree)

        call_args = task.build_prompt.call_args[0][0]
        # Since files are sorted and a.md (10) > budget (5), it stops
        assert "### a.md" not in call_args
        # b.md comes after a.md alphabetically but a.md exceeds budget
        # so the loop breaks at a.md and b.md is never reached
        assert "### b.md" not in call_args
        # Falls back to index only
        assert call_args == "index"

    def test_prepare_uses_heuristic_when_token_count_is_none(self):
        """When token_count is None, _estimate_tokens (~4 chars/token) is used."""
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy(max_content_tokens=100)
        task = make_mock_task()
        # 20 chars = ~5 tokens via heuristic
        doc_tree = _make_doc_tree({
            "a.md": ("twelve chars1234", None),
        })

        strategy.prepare("index", task, doc_tree)

        call_args = task.build_prompt.call_args[0][0]
        assert "### a.md" in call_args
        assert "twelve chars1234" in call_args

    def test_prepare_strategy_metadata(self):
        """strategy_metadata should include content stats."""
        from agent_evals.context.full import FullContextStrategy

        strategy = FullContextStrategy(max_content_tokens=1000)
        task = make_mock_task()
        doc_tree = _make_doc_tree({
            "a.md": ("Content", 50),
            "b.md": ("More content", 60),
        })

        prepared = strategy.prepare("the index", task, doc_tree)

        assert "index_tokens" in prepared.strategy_metadata
        assert prepared.strategy_metadata["content_files_included"] == 2
        assert prepared.strategy_metadata["max_content_tokens"] == 1000

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

    def test_prepare_includes_doc_content_unlike_old_behavior(self):
        """The fixed prepare() should include doc content that the old
        pipeline was missing -- this is the core P0 bug fix validation."""
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
        # Should contain the index metadata
        assert "[FILE] guides/auth.md: Auth guide" in call_args
        # AND the actual document content (the P0 fix)
        assert "# Authentication\nUse JWT tokens..." in call_args
        assert "# Users API\nGET /api/users..." in call_args

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
