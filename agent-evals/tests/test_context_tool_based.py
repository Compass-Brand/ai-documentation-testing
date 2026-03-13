"""Tests for ToolBasedStrategy (Phase 4).

Tests cover:
- Tool definitions are valid OpenAI function calling format
- list_docs returns rendered index
- read_doc returns file content from DocTree
- read_doc with invalid path returns error message
- search_docs finds matching content
- search_docs with no matches returns empty
- Multi-turn loop: LLM calls tool -> gets result -> responds
- MAX_TURNS cap prevents infinite loops
- final_response is cleaned of artifacts
- supports_caching returns False
- Strategy metadata includes turn count and tool usage
- content=None + tool_calls is handled correctly
- LLMClient.complete() explicit tools parameter
- GenerationResult.tool_calls field
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from agent_index.models import DocFile, DocTree
from conftest import make_mock_task

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc_tree() -> DocTree:
    """Create a minimal DocTree for testing."""
    return DocTree(
        files={
            "guides/auth.md": DocFile(
                rel_path="guides/auth.md",
                content="# Authentication\nUse JWT tokens for auth.",
                size_bytes=42,
                token_count=10,
                tier="required",
                section="Guides",
            ),
            "api/users.md": DocFile(
                rel_path="api/users.md",
                content="# Users API\nGET /users returns a list of users.",
                size_bytes=50,
                token_count=12,
                tier="recommended",
                section="API",
            ),
        },
        scanned_at=datetime(2026, 1, 1),
        source="/test",
        total_tokens=22,
    )


def _make_tool_call(tool_id: str, name: str, arguments: str) -> dict:
    """Create a tool call dict matching the serialized OpenAI format.

    GenerationResult.tool_calls stores dicts (serialized by LLMClient),
    so test helpers must produce the same shape.
    """
    return {
        "id": tool_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": arguments,
        },
    }


def _make_generation_result(
    *,
    content: str | None = None,
    tool_calls: list | None = None,
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    total_tokens: int = 15,
    cost: float | None = 0.001,
    model: str = "test-model",
) -> MagicMock:
    """Create a GenerationResult-like mock with tool_calls support."""
    from agent_evals.llm.client import GenerationResult

    gen = GenerationResult(
        content=content or "",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost=cost,
        model=model,
        generation_id="gen-1",
        tool_calls=tool_calls,
    )
    return gen


# ---------------------------------------------------------------------------
# Tool Definitions
# ---------------------------------------------------------------------------


class TestToolDefinitions:
    """Tool definitions must be valid OpenAI function calling format."""

    def test_tool_definitions_are_valid_openai_format(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index content", doc_tree)

        task = make_mock_task()
        prepared = strategy.prepare("# Index content", task, doc_tree)

        assert prepared.tools is not None
        for tool in prepared.tools:
            assert tool["type"] == "function"
            assert "function" in tool
            fn = tool["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn
            assert fn["parameters"]["type"] == "object"

    def test_has_list_docs_tool(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        prepared = strategy.prepare("# Index", task, doc_tree)

        names = [t["function"]["name"] for t in prepared.tools]
        assert "list_docs" in names

    def test_has_read_doc_tool(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        prepared = strategy.prepare("# Index", task, doc_tree)

        names = [t["function"]["name"] for t in prepared.tools]
        assert "read_doc" in names

    def test_has_search_docs_tool(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        prepared = strategy.prepare("# Index", task, doc_tree)

        names = [t["function"]["name"] for t in prepared.tools]
        assert "search_docs" in names

    def test_read_doc_has_path_parameter(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        prepared = strategy.prepare("# Index", task, doc_tree)

        read_doc = next(
            t for t in prepared.tools if t["function"]["name"] == "read_doc"
        )
        params = read_doc["function"]["parameters"]
        assert "path" in params.get("properties", {})
        assert "path" in params.get("required", [])

    def test_search_docs_has_query_parameter(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        prepared = strategy.prepare("# Index", task, doc_tree)

        search_docs = next(
            t for t in prepared.tools if t["function"]["name"] == "search_docs"
        )
        params = search_docs["function"]["parameters"]
        assert "query" in params.get("properties", {})
        assert "query" in params.get("required", [])


# ---------------------------------------------------------------------------
# Tool Execution
# ---------------------------------------------------------------------------


class TestToolExecution:
    """Individual tool functions return correct results."""

    def test_list_docs_returns_rendered_index(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        rendered = "# My Rendered Index\n- auth.md\n- users.md"
        strategy.setup(rendered, doc_tree)

        result = strategy._execute_tool("list_docs", {})
        assert result == rendered

    def test_read_doc_returns_file_content(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        result = strategy._execute_tool("read_doc", {"path": "guides/auth.md"})
        assert "Authentication" in result
        assert "JWT tokens" in result

    def test_read_doc_invalid_path_returns_error(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        result = strategy._execute_tool("read_doc", {"path": "nonexistent.md"})
        assert "error" in result.lower() or "not found" in result.lower()

    def test_search_docs_finds_matching_content(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        result = strategy._execute_tool("search_docs", {"query": "JWT"})
        assert "JWT" in result
        assert "auth.md" in result

    def test_search_docs_no_matches_returns_empty(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        result = strategy._execute_tool("search_docs", {"query": "zzzznonexistentzzzz"})
        assert result == "" or "no match" in result.lower()

    def test_search_docs_caps_results(self):
        """Bug #219: search_docs should cap results to avoid context overflow."""
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        # Create a doc_tree with 30 files all matching "common"
        files = {}
        for i in range(30):
            files[f"docs/file_{i:03d}.md"] = DocFile(
                rel_path=f"docs/file_{i:03d}.md",
                content=f"# File {i}\nThis contains common content.",
                size_bytes=40,
                token_count=10,
                tier="optional",
                section="Docs",
            )
        doc_tree = DocTree(
            files=files,
            scanned_at=datetime(2026, 1, 1),
            source="/test",
            total_tokens=300,
        )
        strategy.setup("# Index", doc_tree)

        result = strategy._execute_tool("search_docs", {"query": "common"})
        # Should be capped at a reasonable number (e.g. 20 files)
        file_matches = [line for line in result.split("\n") if line.startswith("--- ")]
        assert len(file_matches) <= 20

    def test_search_docs_case_insensitive(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        result = strategy._execute_tool("search_docs", {"query": "jwt"})
        assert "JWT" in result

    def test_unknown_tool_returns_error(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        result = strategy._execute_tool("nonexistent_tool", {})
        assert "error" in result.lower() or "unknown" in result.lower()


# ---------------------------------------------------------------------------
# Prepare
# ---------------------------------------------------------------------------


class TestPrepare:
    """prepare() builds tool definitions + initial user message."""

    def test_prepare_returns_tools(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        prepared = strategy.prepare("# Index", task, doc_tree)

        assert prepared.tools is not None
        assert len(prepared.tools) == 3

    def test_prepare_messages_contain_task_question(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        task.definition.question = "What is the auth method?"
        prepared = strategy.prepare("# Index", task, doc_tree)

        user_msgs = [m for m in prepared.messages if m["role"] == "user"]
        assert len(user_msgs) >= 1
        assert "What is the auth method?" in user_msgs[-1]["content"]

    def test_prepare_does_not_include_index_in_prompt(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        rendered = "UNIQUE_INDEX_MARKER_12345"
        strategy.setup(rendered, doc_tree)

        task = make_mock_task()
        task.definition.question = "What is the auth method?"
        prepared = strategy.prepare(rendered, task, doc_tree)

        all_content = " ".join(m.get("content", "") for m in prepared.messages)
        assert "UNIQUE_INDEX_MARKER_12345" not in all_content

    def test_prepare_does_not_call_build_prompt(self):
        """Tool-based strategy bypasses task.build_prompt()."""
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        task.definition.question = "What is auth?"
        strategy.prepare("# Index", task, doc_tree)

        task.build_prompt.assert_not_called()


# ---------------------------------------------------------------------------
# Multi-Turn Execute Loop
# ---------------------------------------------------------------------------


class TestExecuteLoop:
    """execute() manages multi-turn agentic loop."""

    def test_single_turn_text_response(self):
        """LLM responds with text immediately (no tool calls)."""
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        gen = _make_generation_result(content="The answer is JWT.", tool_calls=None)
        client.complete.return_value = gen

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "What is auth?"}],
            tools=[{"type": "function", "function": {"name": "list_docs"}}],
            strategy_metadata={},
        )

        result = strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        assert result.final_response == "The answer is JWT."
        assert len(result.generations) == 1

    def test_multi_turn_tool_then_response(self):
        """LLM calls a tool, gets result, then responds with text."""
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        # Turn 1: LLM calls list_docs
        tool_call = _make_tool_call("call_1", "list_docs", "{}")
        gen_with_tool = _make_generation_result(
            content=None, tool_calls=[tool_call]
        )

        # Turn 2: LLM responds with text
        gen_final = _make_generation_result(
            content="Based on the docs, use JWT.", tool_calls=None
        )

        client.complete.side_effect = [gen_with_tool, gen_final]

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "What is auth?"}],
            tools=[{"type": "function", "function": {"name": "list_docs"}}],
            strategy_metadata={},
        )

        result = strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        assert result.final_response == "Based on the docs, use JWT."
        assert client.complete.call_count == 2
        assert len(result.generations) == 2

    def test_max_turns_prevents_infinite_loop(self):
        """MAX_TURNS cap stops execution even if LLM keeps calling tools."""
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy(max_turns=3)
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        # Always returns tool calls, never text
        tool_call = _make_tool_call("call_n", "list_docs", "{}")
        gen_tool = _make_generation_result(content=None, tool_calls=[tool_call])
        client.complete.return_value = gen_tool

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "What is auth?"}],
            tools=[{"type": "function", "function": {"name": "list_docs"}}],
            strategy_metadata={},
        )

        result = strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        # Should stop after max_turns
        assert client.complete.call_count == 3
        assert result.final_response is not None

    def test_multiple_tool_calls_in_one_turn(self):
        """LLM calls multiple tools in a single turn."""
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        # Turn 1: LLM calls two tools
        tc1 = _make_tool_call("call_1", "list_docs", "{}")
        tc2 = _make_tool_call("call_2", "read_doc", '{"path": "guides/auth.md"}')
        gen_multi = _make_generation_result(content=None, tool_calls=[tc1, tc2])

        # Turn 2: final answer
        gen_final = _make_generation_result(content="Use JWT tokens.", tool_calls=None)

        client.complete.side_effect = [gen_multi, gen_final]

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "What is auth?"}],
            tools=[],
            strategy_metadata={},
        )

        result = strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        assert result.final_response == "Use JWT tokens."
        assert client.complete.call_count == 2

    def test_messages_contain_full_conversation_history(self):
        """StrategyResult.messages contains the full multi-turn history."""
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        tool_call = _make_tool_call("call_1", "list_docs", "{}")
        gen_tool = _make_generation_result(content=None, tool_calls=[tool_call])
        gen_final = _make_generation_result(content="Answer.", tool_calls=None)
        client.complete.side_effect = [gen_tool, gen_final]

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "Question"}],
            tools=[],
            strategy_metadata={},
        )

        result = strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        # Should have: user msg, assistant tool_call, tool result, assistant final
        assert len(result.messages) > 2
        roles = [m["role"] for m in result.messages]
        assert "tool" in roles or "function" in roles

    def test_content_none_with_tool_calls_handled(self):
        """content=None with tool_calls is NOT treated as an error."""
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        # content is None but tool_calls present — this is valid
        tool_call = _make_tool_call("call_1", "list_docs", "{}")
        gen_tool = _make_generation_result(content=None, tool_calls=[tool_call])
        gen_final = _make_generation_result(content="Final answer.", tool_calls=None)
        client.complete.side_effect = [gen_tool, gen_final]

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "Q"}],
            tools=[],
            strategy_metadata={},
        )

        result = strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        assert result.final_response == "Final answer."
        assert client.complete.call_count == 2


# ---------------------------------------------------------------------------
# Final Response Cleaning
# ---------------------------------------------------------------------------


class TestFinalResponseCleaning:
    """final_response is cleaned of tool-call artifacts."""

    def test_clean_response_strips_tool_artifacts(self):
        """If the last response contains tool-call JSON fragments, they're removed."""
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        # Test the cleaning utility directly
        raw = "The answer is JWT.\n\n```json\n{\"tool_calls\": []}\n```"
        cleaned = strategy._clean_response(raw)
        assert "tool_calls" not in cleaned
        assert "JWT" in cleaned

    def test_clean_response_preserves_normal_text(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        normal = "Authentication uses JWT tokens for security."
        assert strategy._clean_response(normal) == normal


# ---------------------------------------------------------------------------
# Strategy Properties
# ---------------------------------------------------------------------------


class TestStrategyProperties:
    """Strategy name, caching, and metadata."""

    def test_name_returns_tool_based(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        assert ToolBasedStrategy().name() == "tool_based"

    def test_supports_caching_returns_false(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        assert ToolBasedStrategy().supports_caching() is False

    def test_strategy_metadata_includes_turns(self):
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        tool_call = _make_tool_call("call_1", "list_docs", "{}")
        gen_tool = _make_generation_result(content=None, tool_calls=[tool_call])
        gen_final = _make_generation_result(content="Answer", tool_calls=None)
        client.complete.side_effect = [gen_tool, gen_final]

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "Q"}],
            tools=[],
            strategy_metadata={},
        )

        result = strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        assert "turns" in result.strategy_metadata
        assert result.strategy_metadata["turns"] == 2

    def test_strategy_metadata_includes_tool_calls_made(self):
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        tc1 = _make_tool_call("call_1", "list_docs", "{}")
        tc2 = _make_tool_call("call_2", "read_doc", '{"path": "guides/auth.md"}')
        gen_tool = _make_generation_result(content=None, tool_calls=[tc1, tc2])
        gen_final = _make_generation_result(content="Answer", tool_calls=None)
        client.complete.side_effect = [gen_tool, gen_final]

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "Q"}],
            tools=[],
            strategy_metadata={},
        )

        result = strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        assert "tool_calls_made" in result.strategy_metadata
        assert result.strategy_metadata["tool_calls_made"] == 2

    def test_strategy_metadata_includes_tools_used(self):
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        tc1 = _make_tool_call("call_1", "list_docs", "{}")
        tc2 = _make_tool_call("call_2", "read_doc", '{"path": "guides/auth.md"}')
        gen_tool = _make_generation_result(content=None, tool_calls=[tc1, tc2])
        gen_final = _make_generation_result(content="Answer", tool_calls=None)
        client.complete.side_effect = [gen_tool, gen_final]

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "Q"}],
            tools=[],
            strategy_metadata={},
        )

        result = strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        assert "tools_used" in result.strategy_metadata
        assert set(result.strategy_metadata["tools_used"]) == {"list_docs", "read_doc"}


# ---------------------------------------------------------------------------
# LLMClient Extensions
# ---------------------------------------------------------------------------


class TestGenerationResultToolCalls:
    """GenerationResult has a tool_calls field."""

    def test_generation_result_has_tool_calls_field(self):
        from agent_evals.llm.client import GenerationResult

        gen = GenerationResult(
            content="test",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost=None,
            model="test",
            generation_id=None,
            tool_calls=[{"id": "call_1", "type": "function"}],
        )
        assert gen.tool_calls == [{"id": "call_1", "type": "function"}]

    def test_generation_result_tool_calls_defaults_none(self):
        from agent_evals.llm.client import GenerationResult

        gen = GenerationResult(
            content="test",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost=None,
            model="test",
            generation_id=None,
        )
        assert gen.tool_calls is None


# ---------------------------------------------------------------------------
# Registry Discovery
# ---------------------------------------------------------------------------


class TestTeardown:
    """Bug #220: teardown() must clear internal state to prevent leaks."""

    def test_teardown_clears_doc_tree(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("index", doc_tree)
        assert strategy._doc_tree is not None

        strategy.teardown()
        assert strategy._doc_tree is None

    def test_teardown_clears_rendered_index(self):
        from agent_evals.context.tool_based import ToolBasedStrategy

        strategy = ToolBasedStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("my index content", doc_tree)
        assert strategy._rendered_index == "my index content"

        strategy.teardown()
        assert strategy._rendered_index == ""


class TestRegistryDiscovery:
    """ToolBasedStrategy is discovered by the registry."""

    def test_registry_discovers_tool_based(self):
        from agent_evals.context.registry import get_all_strategies, load_all

        load_all()
        strategies = get_all_strategies()
        names = [s.name() for s in strategies]
        assert "tool_based" in names

    def test_registry_get_by_name(self):
        from agent_evals.context.registry import get_strategy_by_name, load_all

        load_all()
        strategy = get_strategy_by_name("tool_based")
        assert strategy is not None
        assert strategy.name() == "tool_based"
