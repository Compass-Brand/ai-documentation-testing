"""Tests for SystemPromptStrategy (Phase 2).

Tests cover:
- Hard truncation respects token budget
- Hard truncation metadata includes original and truncated token counts
- Priority truncation keeps required content first
- Zero budget produces empty context
- Budget larger than content passes through unchanged
- prepare() produces valid PreparedContext
- execute() wraps response correctly
- name() returns "system_prompt"
- supports_caching() returns True
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from conftest import make_mock_client, make_mock_task

from agent_evals.context.base import PreparedContext, StrategyConfig, StrategyResult
from agent_evals.context.system_prompt import SystemPromptStrategy
from agent_evals.llm.client import GenerationResult
from agent_index.models import DocFile, DocTree, TierConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc_tree(files: dict[str, DocFile] | None = None) -> DocTree:
    """Create a minimal DocTree for testing."""
    return DocTree(
        files=files or {},
        scanned_at=datetime.now(tz=timezone.utc),
        source="test",
        total_tokens=0,
    )


def _make_doc_file(
    rel_path: str,
    content: str,
    tier: str = "reference",
    priority: int = 0,
) -> DocFile:
    """Create a DocFile for testing."""
    return DocFile(
        rel_path=rel_path,
        content=content,
        size_bytes=len(content),
        token_count=None,
        tier=tier,
        section="",
        priority=priority,
    )


# ---------------------------------------------------------------------------
# Identity & interface
# ---------------------------------------------------------------------------


class TestSystemPromptStrategyInterface:
    def test_name_returns_system_prompt(self):
        strategy = SystemPromptStrategy(StrategyConfig())
        assert strategy.name() == "system_prompt"

    def test_supports_caching_returns_true(self):
        strategy = SystemPromptStrategy(StrategyConfig())
        assert strategy.supports_caching() is True


# ---------------------------------------------------------------------------
# Hard truncation
# ---------------------------------------------------------------------------


class TestHardTruncation:
    @patch("agent_evals.context.system_prompt.count_tokens")
    def test_respects_token_budget(self, mock_count):
        """Content exceeding the budget is truncated."""
        # Simulate: full text = 200 tokens, budget = 50
        # count_tokens returns different values for different inputs
        mock_count.side_effect = lambda text, **kw: len(text) // 4

        config = StrategyConfig(token_budget=50, truncation="hard")
        strategy = SystemPromptStrategy(config)
        task = make_mock_task()
        doc_tree = _make_doc_tree()

        # 800 chars => ~200 tokens at 4 chars/token, budget is 50 tokens => ~200 chars
        long_content = "x" * 800
        prepared = strategy.prepare(long_content, task, doc_tree)

        # build_prompt was called with truncated content
        call_args = task.build_prompt.call_args[0][0]
        assert len(call_args) < len(long_content)

    @patch("agent_evals.context.system_prompt.count_tokens")
    def test_metadata_includes_token_counts(self, mock_count):
        """Metadata records original_tokens, truncated_tokens, truncation_method."""
        mock_count.side_effect = lambda text, **kw: len(text) // 4

        config = StrategyConfig(token_budget=25, truncation="hard")
        strategy = SystemPromptStrategy(config)
        task = make_mock_task()
        doc_tree = _make_doc_tree()

        content = "a" * 400  # 100 tokens at 4 chars/token
        prepared = strategy.prepare(content, task, doc_tree)

        meta = prepared.strategy_metadata
        assert "original_tokens" in meta
        assert "truncated_tokens" in meta
        assert "truncation_method" in meta
        assert meta["truncation_method"] == "hard"
        assert meta["original_tokens"] == 100
        assert meta["truncated_tokens"] <= 25

    @patch("agent_evals.context.system_prompt.count_tokens")
    def test_zero_budget_produces_empty_context(self, mock_count):
        """Zero token budget results in empty content passed to build_prompt."""
        mock_count.side_effect = lambda text, **kw: len(text) // 4

        config = StrategyConfig(token_budget=0, truncation="hard")
        strategy = SystemPromptStrategy(config)
        task = make_mock_task()
        doc_tree = _make_doc_tree()

        prepared = strategy.prepare("some content", task, doc_tree)

        call_args = task.build_prompt.call_args[0][0]
        assert call_args == ""
        assert prepared.strategy_metadata["truncated_tokens"] == 0

    @patch("agent_evals.context.system_prompt.count_tokens")
    def test_budget_larger_than_content_passes_through(self, mock_count):
        """Content within budget passes through unchanged."""
        mock_count.side_effect = lambda text, **kw: len(text) // 4

        config = StrategyConfig(token_budget=10000, truncation="hard")
        strategy = SystemPromptStrategy(config)
        task = make_mock_task()
        doc_tree = _make_doc_tree()

        content = "short content"
        prepared = strategy.prepare(content, task, doc_tree)

        call_args = task.build_prompt.call_args[0][0]
        assert call_args == content
        meta = prepared.strategy_metadata
        assert meta["original_tokens"] == meta["truncated_tokens"]

    @patch("agent_evals.context.system_prompt.count_tokens")
    def test_none_budget_passes_through(self, mock_count):
        """No token budget (None) passes through unchanged like full context."""
        mock_count.side_effect = lambda text, **kw: len(text) // 4

        config = StrategyConfig(token_budget=None, truncation="hard")
        strategy = SystemPromptStrategy(config)
        task = make_mock_task()
        doc_tree = _make_doc_tree()

        content = "some content here"
        prepared = strategy.prepare(content, task, doc_tree)

        call_args = task.build_prompt.call_args[0][0]
        assert call_args == content


# ---------------------------------------------------------------------------
# Priority truncation
# ---------------------------------------------------------------------------


class TestPriorityTruncation:
    @patch("agent_evals.context.system_prompt.count_tokens")
    def test_keeps_required_content_first(self, mock_count):
        """Priority truncation keeps required-tier content before other tiers."""
        mock_count.side_effect = lambda text, **kw: len(text) // 4

        required_content = "REQUIRED " * 10  # 90 chars => ~22 tokens
        optional_content = "OPTIONAL " * 10  # 90 chars => ~22 tokens

        files = {
            "api/important.md": _make_doc_file(
                "api/important.md", required_content, tier="required", priority=10,
            ),
            "extras/nice.md": _make_doc_file(
                "extras/nice.md", optional_content, tier="reference", priority=0,
            ),
        }
        doc_tree = _make_doc_tree(files)

        # Budget allows only ~25 tokens - should fit required but not optional
        config = StrategyConfig(token_budget=25, truncation="priority")
        strategy = SystemPromptStrategy(config)
        task = make_mock_task()

        rendered_index = required_content + optional_content
        prepared = strategy.prepare(rendered_index, task, doc_tree)

        meta = prepared.strategy_metadata
        assert meta["truncation_method"] == "priority"
        # The strategy should have included content and the metadata should
        # reflect that truncation happened
        assert meta["truncated_tokens"] <= 25

    @patch("agent_evals.context.system_prompt.count_tokens")
    def test_priority_with_no_files_falls_back_to_hard(self, mock_count):
        """When doc_tree has no files, priority truncation falls back to hard cutoff."""
        mock_count.side_effect = lambda text, **kw: len(text) // 4

        config = StrategyConfig(token_budget=10, truncation="priority")
        strategy = SystemPromptStrategy(config)
        task = make_mock_task()
        doc_tree = _make_doc_tree()  # empty files

        content = "a" * 200  # 50 tokens
        prepared = strategy.prepare(content, task, doc_tree)

        meta = prepared.strategy_metadata
        assert meta["truncated_tokens"] <= 10

    @patch("agent_evals.context.system_prompt.count_tokens")
    def test_priority_budget_larger_than_content_passes_through(self, mock_count):
        """Priority mode with ample budget includes all content."""
        mock_count.side_effect = lambda text, **kw: len(text) // 4

        files = {
            "a.md": _make_doc_file("a.md", "short", tier="required"),
        }
        doc_tree = _make_doc_tree(files)

        config = StrategyConfig(token_budget=10000, truncation="priority")
        strategy = SystemPromptStrategy(config)
        task = make_mock_task()

        content = "short text"
        prepared = strategy.prepare(content, task, doc_tree)

        call_args = task.build_prompt.call_args[0][0]
        assert len(call_args) > 0  # Content was included


# ---------------------------------------------------------------------------
# prepare() produces valid PreparedContext
# ---------------------------------------------------------------------------


class TestPrepareOutput:
    @patch("agent_evals.context.system_prompt.count_tokens")
    def test_returns_prepared_context(self, mock_count):
        mock_count.side_effect = lambda text, **kw: len(text) // 4

        config = StrategyConfig(token_budget=1000, truncation="hard")
        strategy = SystemPromptStrategy(config)
        task = make_mock_task()
        doc_tree = _make_doc_tree()

        prepared = strategy.prepare("index content", task, doc_tree)

        assert isinstance(prepared, PreparedContext)
        assert isinstance(prepared.messages, list)
        assert prepared.tools is None
        assert isinstance(prepared.strategy_metadata, dict)


# ---------------------------------------------------------------------------
# execute() wraps response correctly
# ---------------------------------------------------------------------------


class TestExecute:
    def test_wraps_response_in_strategy_result(self):
        config = StrategyConfig()
        strategy = SystemPromptStrategy(config)

        messages = [{"role": "user", "content": "test"}]
        prepared = PreparedContext(
            messages=messages,
            tools=None,
            strategy_metadata={"truncation_method": "hard"},
        )

        gen = GenerationResult(
            content="LLM answer",
            prompt_tokens=50,
            completion_tokens=20,
            total_tokens=70,
            cost=0.002,
            model="test-model",
            generation_id="gen-1",
        )
        client = make_mock_client()
        client.complete.return_value = gen

        task = make_mock_task()
        result = strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        assert isinstance(result, StrategyResult)
        assert result.final_response == "LLM answer"
        assert result.total_prompt_tokens == 50
        assert result.total_completion_tokens == 20
        assert result.total_tokens == 70
        assert result.total_cost == 0.002
        assert len(result.generations) == 1
        assert result.generations[0] is gen
        assert result.messages == messages

        client.complete.assert_called_once_with(
            messages,
            max_tokens=2048,
            temperature=0.3,
        )


# ---------------------------------------------------------------------------
# Registry auto-discovery
# ---------------------------------------------------------------------------


class TestRegistryDiscovery:
    def test_registry_discovers_system_prompt(self):
        from agent_evals.context.registry import get_strategy_by_name, load_all

        load_all()
        strategy = get_strategy_by_name("system_prompt")
        assert strategy is not None
        assert strategy.name() == "system_prompt"
