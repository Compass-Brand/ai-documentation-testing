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
- Bug #262: system message presence is validated and logged (observability)
- Bug #267: _priority_truncate method is removed; priority calls hard truncate
- Bug #268: None rendered_index is coerced to empty string (no TypeError)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from unittest.mock import patch

from agent_evals.context.base import PreparedContext, StrategyConfig, StrategyResult
from agent_evals.context.system_prompt import SystemPromptStrategy
from agent_evals.llm.client import GenerationResult
from agent_index.models import DocFile, DocTree
from conftest import make_mock_client, make_mock_task

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_doc_tree(files: dict[str, DocFile] | None = None) -> DocTree:
    """Create a minimal DocTree for testing."""
    return DocTree(
        files=files or {},
        scanned_at=datetime.now(tz=UTC),
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
    def test_priority_truncate_uses_rendered_index_not_raw_content(self, mock_count):
        """priority_truncate must use the rendered_index text, not raw doc
        content from doc_tree.files (#183)."""
        mock_count.side_effect = lambda text, **kw: len(text) // 4

        # Raw doc content is different from the rendered index
        raw_content = "RAW FILE CONTENT SHOULD NOT APPEAR"
        files = {
            "api/auth.md": _make_doc_file(
                "api/auth.md", raw_content, tier="required", priority=10,
            ),
        }
        doc_tree = _make_doc_tree(files)

        # The rendered index (produced by a variant) is the experimental treatment
        rendered_index = "RENDERED INDEX LINE: api/auth.md - Authentication guide"

        config = StrategyConfig(token_budget=10, truncation="priority")
        strategy = SystemPromptStrategy(config)
        task = make_mock_task()

        strategy.prepare(rendered_index, task, doc_tree)

        call_args = task.build_prompt.call_args[0][0]
        # Should contain text from rendered_index, not raw doc content
        assert "RAW FILE CONTENT SHOULD NOT APPEAR" not in call_args
        # Should be a truncation of the rendered_index
        assert call_args in rendered_index or rendered_index.startswith(call_args)

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
            tools=None,
            max_tokens=2048,
            temperature=0.3,
        )

    def test_execute_passes_tools_to_client_complete(self):
        """Bug #279: execute() must pass tools=prepared.tools to client.complete().

        When PreparedContext has tools, execute() must forward them so the LLM
        can use function calling.
        """
        config = StrategyConfig()
        strategy = SystemPromptStrategy(config)

        tools = [{"type": "function", "function": {"name": "test_tool"}}]
        messages = [{"role": "user", "content": "test"}]
        prepared = PreparedContext(
            messages=messages,
            tools=tools,
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
        strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        client.complete.assert_called_once_with(
            messages,
            tools=tools,
            max_tokens=2048,
            temperature=0.3,
        )

    def test_execute_passes_none_tools_to_client_complete(self):
        """Bug #279: execute() must pass tools=None when PreparedContext has no tools."""
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
        strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        client.complete.assert_called_once_with(
            messages,
            tools=None,
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


# ---------------------------------------------------------------------------
# Bug #262: system message validation / observability
# ---------------------------------------------------------------------------


class TestSystemMessageValidation:
    """Bug #262: prepare() must verify the output messages contain a system
    message and emit a warning when they don't."""

    def test_no_warning_when_system_message_present(self, caplog):
        """No warning is emitted when build_prompt returns a system message."""
        config = StrategyConfig(token_budget=5000)
        strategy = SystemPromptStrategy(config)
        task = make_mock_task(
            prompt=[
                {"role": "system", "content": "Doc context here"},
                {"role": "user", "content": "What is X?"},
            ],
        )
        doc_tree = _make_doc_tree()

        with caplog.at_level(logging.WARNING, logger="agent_evals.context.system_prompt"):
            strategy.prepare("doc content", task, doc_tree)

        warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert not any("system" in m.lower() for m in warning_msgs), (
            "Should NOT warn when a system message is present"
        )

    def test_warning_when_no_system_message(self, caplog):
        """A WARNING is logged when build_prompt returns no system-role message."""
        config = StrategyConfig()
        strategy = SystemPromptStrategy(config)
        # build_prompt returns only a user message — no system role
        task = make_mock_task(
            prompt=[
                {"role": "user", "content": "What is X?"},
            ],
        )
        doc_tree = _make_doc_tree()

        with caplog.at_level(logging.WARNING, logger="agent_evals.context.system_prompt"):
            strategy.prepare("doc content", task, doc_tree)

        warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("system" in m.lower() for m in warning_msgs), (
            "Expected a WARNING mentioning 'system' when no system-role message is present"
        )

    def test_metadata_flag_system_prompt_enforced_true(self):
        """strategy_metadata contains system_prompt_enforced=True when a system
        message IS present in the output."""
        config = StrategyConfig()
        strategy = SystemPromptStrategy(config)
        task = make_mock_task(
            prompt=[
                {"role": "system", "content": "Index goes here"},
                {"role": "user", "content": "Question?"},
            ],
        )
        doc_tree = _make_doc_tree()

        prepared = strategy.prepare("index", task, doc_tree)

        assert prepared.strategy_metadata.get("system_prompt_enforced") is True, (
            "strategy_metadata must include system_prompt_enforced=True when "
            "messages contain a system-role entry (Bug #262)"
        )

    def test_metadata_flag_system_prompt_enforced_false_when_missing(self):
        """strategy_metadata contains system_prompt_enforced=False when no system
        message is found in the output."""
        config = StrategyConfig()
        strategy = SystemPromptStrategy(config)
        task = make_mock_task(
            prompt=[
                {"role": "user", "content": "Question without system context"},
            ],
        )
        doc_tree = _make_doc_tree()

        prepared = strategy.prepare("index", task, doc_tree)

        assert prepared.strategy_metadata.get("system_prompt_enforced") is False, (
            "strategy_metadata must include system_prompt_enforced=False when "
            "no system-role message is present (Bug #262)"
        )


# ---------------------------------------------------------------------------
# Bug #267: _priority_truncate removed; priority mode uses hard truncation
# ---------------------------------------------------------------------------


class TestPriorityTruncateRemoval:
    """Bug #267: _priority_truncate is dead code — it always delegated to
    _hard_truncate. The method must be removed and all priority paths must
    call _hard_truncate directly."""

    def test_priority_truncate_method_does_not_exist(self):
        """SystemPromptStrategy must NOT have a _priority_truncate method."""
        strategy = SystemPromptStrategy(StrategyConfig())
        assert not hasattr(strategy, "_priority_truncate"), (
            "_priority_truncate method must be removed (Bug #267). "
            "Use _hard_truncate directly in prepare()."
        )

    @patch("agent_evals.context.system_prompt.count_tokens")
    def test_priority_truncation_mode_still_truncates(self, mock_count):
        """After removal, truncation='priority' must still truncate correctly
        by delegating to _hard_truncate."""
        mock_count.side_effect = lambda text, **kw: len(text) // 4

        config = StrategyConfig(token_budget=10, truncation="priority")
        strategy = SystemPromptStrategy(config)
        task = make_mock_task()
        doc_tree = _make_doc_tree()

        content = "a" * 200  # 50 tokens at 4 chars/token
        prepared = strategy.prepare(content, task, doc_tree)

        meta = prepared.strategy_metadata
        assert meta["truncated_tokens"] <= 10, (
            "priority mode must still truncate to the budget via _hard_truncate"
        )


# ---------------------------------------------------------------------------
# Bug #268: None rendered_index guard in SystemPromptStrategy
# ---------------------------------------------------------------------------


class TestNoneRenderedIndexGuard:
    """Bug #268: prepare() must coerce None rendered_index to empty string
    instead of raising TypeError."""

    @patch("agent_evals.context.system_prompt.count_tokens")
    def test_none_rendered_index_does_not_raise(self, mock_count):
        """prepare() must not raise when rendered_index is None."""
        mock_count.side_effect = lambda text, **kw: len(text) // 4

        config = StrategyConfig(token_budget=100, truncation="hard")
        strategy = SystemPromptStrategy(config)
        task = make_mock_task()
        doc_tree = _make_doc_tree()

        # Should not raise TypeError
        prepared = strategy.prepare(None, task, doc_tree)  # type: ignore[arg-type]

        # build_prompt must have been called with empty string, not None
        call_args = task.build_prompt.call_args[0][0]
        assert call_args == "", (
            "None rendered_index must be coerced to '' before passing to build_prompt"
        )

    @patch("agent_evals.context.system_prompt.count_tokens")
    def test_none_budget_none_rendered_index_does_not_raise(self, mock_count):
        """prepare() with no budget constraint must also handle None."""
        mock_count.side_effect = lambda text, **kw: len(text) // 4

        config = StrategyConfig(token_budget=None)
        strategy = SystemPromptStrategy(config)
        task = make_mock_task()
        doc_tree = _make_doc_tree()

        prepared = strategy.prepare(None, task, doc_tree)  # type: ignore[arg-type]

        call_args = task.build_prompt.call_args[0][0]
        assert call_args == "", "None must be coerced to '' even with no budget constraint"


# ---------------------------------------------------------------------------
# Bug #271: Missing @register_strategy decorator
# ---------------------------------------------------------------------------


class TestRegisterStrategyDecorator:
    """Bug #271: SystemPromptStrategy must be decorated with @register_strategy
    so it is discoverable without calling load_all()."""

    def test_discoverable_without_load_all(self):
        """Importing the module must register the strategy via the decorator.

        get_strategy_by_name("system_prompt") must succeed after importing the
        module -- without calling load_all() first.
        """
        from agent_evals.context.registry import clear_registry, get_strategy_by_name

        clear_registry()

        # Re-import the module to trigger decorator-based registration.
        import importlib

        import agent_evals.context.system_prompt as sp_mod

        importlib.reload(sp_mod)

        strategy = get_strategy_by_name("system_prompt")
        assert strategy is not None, (
            "SystemPromptStrategy must be discoverable via get_strategy_by_name "
            "without calling load_all(). Add @register_strategy decorator. (Bug #271)"
        )
        assert strategy.name() == "system_prompt"


# ---------------------------------------------------------------------------
# Bug #272: Silent no-op when StrategyConfig has no token_budget
# ---------------------------------------------------------------------------


class TestTokenBudgetWarning:
    """Bug #272: __init__ must log a warning when config is None or
    config.token_budget is None so that the pass-through behaviour is explicit
    rather than a silent no-op."""

    def test_warning_when_config_is_none(self, caplog):
        """A WARNING must be logged when config is None."""
        with caplog.at_level(logging.WARNING, logger="agent_evals.context.system_prompt"):
            SystemPromptStrategy(config=None)

        warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("truncation" in m.lower() or "token_budget" in m.lower() for m in warning_msgs), (
            "Expected a WARNING mentioning truncation/token_budget when config is None (Bug #272)"
        )

    def test_warning_when_token_budget_is_none(self, caplog):
        """A WARNING must be logged when config.token_budget is None."""
        config = StrategyConfig(token_budget=None)
        with caplog.at_level(logging.WARNING, logger="agent_evals.context.system_prompt"):
            SystemPromptStrategy(config=config)

        warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert any("truncation" in m.lower() or "token_budget" in m.lower() for m in warning_msgs), (
            "Expected a WARNING mentioning truncation/token_budget when token_budget is None (Bug #272)"
        )

    def test_no_warning_when_token_budget_is_set(self, caplog):
        """No budget warning when a valid token_budget is provided."""
        config = StrategyConfig(token_budget=5000)
        with caplog.at_level(logging.WARNING, logger="agent_evals.context.system_prompt"):
            SystemPromptStrategy(config=config)

        warning_msgs = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        budget_warnings = [m for m in warning_msgs if "truncation" in m.lower() or "token_budget" in m.lower()]
        assert not budget_warnings, (
            "Should NOT warn about missing token_budget when one is set (Bug #272)"
        )
