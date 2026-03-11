"""Tests for MCPNativeStrategy (Phase C, Task 2).

Tests cover:
- Registration: strategy is discoverable by registry
- Resource catalog: DocTree -> MCP resource catalog conversion
- Prepare: system prompt includes catalog, messages use task question
- Tool execution: list_resources, read_resource, search_resources
- Multi-turn loop: tool calls -> results -> final response, max_turns cap
- Resource metadata: resources_fetched tracking, catalog_tokens in metadata
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from conftest import make_mock_task

from agent_index.models import DocFile, DocTree


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
                summary="Authentication guide using JWT",
            ),
            "api/users.md": DocFile(
                rel_path="api/users.md",
                content="# Users API\nGET /users returns a list of users.",
                size_bytes=50,
                token_count=12,
                tier="recommended",
                section="API",
                summary="Users API endpoint docs",
            ),
        },
        scanned_at=datetime(2026, 1, 1),
        source="/test",
        total_tokens=22,
    )


def _make_tool_call(tool_id: str, name: str, arguments: str) -> dict:
    """Create a tool call dict matching the serialized OpenAI format."""
    return {
        "id": tool_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": arguments,
        },
    }


def _make_generation(
    *,
    content: str | None = None,
    tool_calls: list | None = None,
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    total_tokens: int = 15,
    cost: float | None = 0.001,
    model: str = "test-model",
) -> MagicMock:
    """Create a GenerationResult with tool_calls support."""
    from agent_evals.llm.client import GenerationResult

    return GenerationResult(
        content=content or "",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost=cost,
        model=model,
        generation_id="gen-1",
        tool_calls=tool_calls,
    )


# ---------------------------------------------------------------------------
# TestMCPNativeRegistration
# ---------------------------------------------------------------------------


class TestMCPNativeRegistration:
    """MCPNativeStrategy is discoverable by the registry."""

    def test_registry_discovers_mcp_native(self):
        from agent_evals.context.registry import get_all_strategies, load_all

        load_all()
        strategies = get_all_strategies()
        names = [s.name() for s in strategies]
        assert "mcp_native" in names

    def test_registry_get_by_name(self):
        from agent_evals.context.registry import get_strategy_by_name, load_all

        load_all()
        strategy = get_strategy_by_name("mcp_native")
        assert strategy is not None
        assert strategy.name() == "mcp_native"

    def test_name_returns_mcp_native(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        assert MCPNativeStrategy().name() == "mcp_native"

    def test_supports_caching_returns_false(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        assert MCPNativeStrategy().supports_caching() is False


# ---------------------------------------------------------------------------
# TestMCPResourceCatalog
# ---------------------------------------------------------------------------


class TestMCPResourceCatalog:
    """DocTree -> MCP resource catalog conversion."""

    def test_catalog_has_entry_per_file(self):
        from agent_evals.context.mcp_native import _build_resource_catalog

        doc_tree = _make_doc_tree()
        catalog = _build_resource_catalog(doc_tree)
        assert len(catalog) == 2

    def test_catalog_entry_has_uri(self):
        from agent_evals.context.mcp_native import _build_resource_catalog

        doc_tree = _make_doc_tree()
        catalog = _build_resource_catalog(doc_tree)
        uris = [e["uri"] for e in catalog]
        assert "docs://api/users.md" in uris
        assert "docs://guides/auth.md" in uris

    def test_catalog_entry_has_name(self):
        from agent_evals.context.mcp_native import _build_resource_catalog

        doc_tree = _make_doc_tree()
        catalog = _build_resource_catalog(doc_tree)
        names = [e["name"] for e in catalog]
        assert "api/users.md" in names
        assert "guides/auth.md" in names

    def test_catalog_entry_has_description_from_summary(self):
        from agent_evals.context.mcp_native import _build_resource_catalog

        doc_tree = _make_doc_tree()
        catalog = _build_resource_catalog(doc_tree)
        auth_entry = next(e for e in catalog if e["name"] == "guides/auth.md")
        assert auth_entry["description"] == "Authentication guide using JWT"

    def test_catalog_entry_fallback_description_when_no_summary(self):
        from agent_evals.context.mcp_native import _build_resource_catalog

        doc_tree = _make_doc_tree()
        # Remove summary from one file
        doc_tree.files["guides/auth.md"].summary = None
        catalog = _build_resource_catalog(doc_tree)
        auth_entry = next(e for e in catalog if e["name"] == "guides/auth.md")
        assert "guides/auth.md" in auth_entry["description"]

    def test_catalog_entry_has_mime_type(self):
        from agent_evals.context.mcp_native import _build_resource_catalog

        doc_tree = _make_doc_tree()
        catalog = _build_resource_catalog(doc_tree)
        for entry in catalog:
            assert entry["mimeType"] == "text/markdown"

    def test_catalog_entry_has_tier(self):
        from agent_evals.context.mcp_native import _build_resource_catalog

        doc_tree = _make_doc_tree()
        catalog = _build_resource_catalog(doc_tree)
        auth_entry = next(e for e in catalog if e["name"] == "guides/auth.md")
        assert auth_entry["tier"] == "required"

    def test_catalog_entry_has_section(self):
        from agent_evals.context.mcp_native import _build_resource_catalog

        doc_tree = _make_doc_tree()
        catalog = _build_resource_catalog(doc_tree)
        auth_entry = next(e for e in catalog if e["name"] == "guides/auth.md")
        assert auth_entry["section"] == "Guides"

    def test_catalog_entry_has_token_count(self):
        from agent_evals.context.mcp_native import _build_resource_catalog

        doc_tree = _make_doc_tree()
        catalog = _build_resource_catalog(doc_tree)
        auth_entry = next(e for e in catalog if e["name"] == "guides/auth.md")
        assert auth_entry["token_count"] == "10"

    def test_catalog_entries_sorted_by_path(self):
        from agent_evals.context.mcp_native import _build_resource_catalog

        doc_tree = _make_doc_tree()
        catalog = _build_resource_catalog(doc_tree)
        names = [e["name"] for e in catalog]
        assert names == sorted(names)

    def test_empty_doc_tree_returns_empty_catalog(self):
        from agent_evals.context.mcp_native import _build_resource_catalog

        doc_tree = DocTree(
            files={},
            scanned_at=datetime(2026, 1, 1),
            source="/empty",
            total_tokens=0,
        )
        catalog = _build_resource_catalog(doc_tree)
        assert catalog == []


# ---------------------------------------------------------------------------
# TestMCPPrepare
# ---------------------------------------------------------------------------


class TestMCPPrepare:
    """prepare() builds system prompt with catalog and 3 tool definitions."""

    def test_prepare_returns_three_tools(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        prepared = strategy.prepare("# Index", task, doc_tree)

        assert prepared.tools is not None
        assert len(prepared.tools) == 3

    def test_prepare_tool_names(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        prepared = strategy.prepare("# Index", task, doc_tree)

        names = [t["function"]["name"] for t in prepared.tools]
        assert "list_resources" in names
        assert "read_resource" in names
        assert "search_resources" in names

    def test_read_resource_has_uri_enum(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        prepared = strategy.prepare("# Index", task, doc_tree)

        read_tool = next(
            t for t in prepared.tools if t["function"]["name"] == "read_resource"
        )
        uri_param = read_tool["function"]["parameters"]["properties"]["uri"]
        assert "enum" in uri_param
        assert "docs://guides/auth.md" in uri_param["enum"]
        assert "docs://api/users.md" in uri_param["enum"]

    def test_prepare_system_prompt_contains_catalog(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        prepared = strategy.prepare("# Index", task, doc_tree)

        system_msgs = [m for m in prepared.messages if m["role"] == "system"]
        assert len(system_msgs) >= 1
        system_content = system_msgs[0]["content"]
        assert "docs://guides/auth.md" in system_content
        assert "docs://api/users.md" in system_content

    def test_prepare_user_message_contains_question(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        task.definition.question = "How do I authenticate?"
        prepared = strategy.prepare("# Index", task, doc_tree)

        user_msgs = [m for m in prepared.messages if m["role"] == "user"]
        assert len(user_msgs) >= 1
        assert "How do I authenticate?" in user_msgs[-1]["content"]

    def test_prepare_metadata_has_resource_count(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        prepared = strategy.prepare("# Index", task, doc_tree)

        assert "resource_count" in prepared.strategy_metadata
        assert prepared.strategy_metadata["resource_count"] == 2

    def test_prepare_metadata_has_catalog_tokens(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        prepared = strategy.prepare("# Index", task, doc_tree)

        assert "catalog_tokens" in prepared.strategy_metadata
        assert prepared.strategy_metadata["catalog_tokens"] > 0

    def test_prepare_does_not_call_build_prompt(self):
        """MCP-native strategy bypasses task.build_prompt()."""
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        task.definition.question = "What is auth?"
        strategy.prepare("# Index", task, doc_tree)

        task.build_prompt.assert_not_called()

    def test_tools_have_valid_openai_format(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        prepared = strategy.prepare("# Index", task, doc_tree)

        for tool in prepared.tools:
            assert tool["type"] == "function"
            assert "function" in tool
            fn = tool["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn
            assert fn["parameters"]["type"] == "object"


# ---------------------------------------------------------------------------
# TestMCPExecuteTool
# ---------------------------------------------------------------------------


class TestMCPExecuteTool:
    """Individual tool functions return correct results."""

    def test_list_resources_returns_catalog_json(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        result = strategy._execute_tool("list_resources", {})
        parsed = json.loads(result)
        assert len(parsed) == 2
        uris = [e["uri"] for e in parsed]
        assert "docs://guides/auth.md" in uris

    def test_read_resource_returns_file_content(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        result = strategy._execute_tool(
            "read_resource", {"uri": "docs://guides/auth.md"}
        )
        assert "Authentication" in result
        assert "JWT tokens" in result

    def test_read_resource_invalid_uri_returns_error(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        result = strategy._execute_tool(
            "read_resource", {"uri": "docs://nonexistent.md"}
        )
        assert "error" in result.lower() or "not found" in result.lower()

    def test_search_resources_finds_matching_content(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        result = strategy._execute_tool("search_resources", {"query": "JWT"})
        assert "JWT" in result
        assert "auth.md" in result

    def test_search_resources_returns_matching_lines_not_beginning(self):
        """Bug #218: _search should return lines containing the query, not first 200 chars."""
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        # Create a doc with the match deep in the content
        doc_tree = DocTree(
            files={
                "guides/large.md": DocFile(
                    rel_path="guides/large.md",
                    content=(
                        "# Large Document\n"
                        + "This is filler content.\n" * 20
                        + "The SECRET_KEYWORD is here.\n"
                        + "More filler content.\n" * 20
                    ),
                    size_bytes=1000,
                    token_count=200,
                    tier="required",
                    section="Guides",
                    summary="Large doc",
                ),
            },
            scanned_at=datetime(2026, 1, 1),
            source="/test",
            total_tokens=200,
        )
        strategy.setup("# Index", doc_tree)

        result = strategy._execute_tool("search_resources", {"query": "SECRET_KEYWORD"})
        # The result should contain the actual matching line, not just the first 200 chars
        assert "SECRET_KEYWORD" in result

    def test_search_resources_case_insensitive(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        result = strategy._execute_tool("search_resources", {"query": "jwt"})
        assert "JWT" in result

    def test_search_resources_no_match_returns_no_results(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        result = strategy._execute_tool(
            "search_resources", {"query": "zzzznonexistentzzzz"}
        )
        assert "no results" in result.lower()

    def test_search_resources_caps_results(self):
        """Bug #219: search_resources should cap results to avoid context overflow."""
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        files = {}
        for i in range(30):
            files[f"docs/file_{i:03d}.md"] = DocFile(
                rel_path=f"docs/file_{i:03d}.md",
                content=f"# File {i}\nThis contains common content.",
                size_bytes=40,
                token_count=10,
                tier="optional",
                section="Docs",
                summary=f"File {i}",
            )
        doc_tree = DocTree(
            files=files,
            scanned_at=datetime(2026, 1, 1),
            source="/test",
            total_tokens=300,
        )
        strategy.setup("# Index", doc_tree)

        result = strategy._execute_tool("search_resources", {"query": "common"})
        # Should be capped at a reasonable number (e.g. 20 files)
        file_matches = [line for line in result.split("\n") if line.startswith("docs://")]
        assert len(file_matches) <= 20

    def test_search_resources_empty_query_returns_no_results(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        result = strategy._execute_tool("search_resources", {"query": ""})
        assert "no results" in result.lower()

    def test_unknown_tool_returns_error(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        result = strategy._execute_tool("nonexistent_tool", {})
        assert "error" in result.lower() or "unknown" in result.lower()


# ---------------------------------------------------------------------------
# TestMCPMultiTurnLoop
# ---------------------------------------------------------------------------


class TestMCPMultiTurnLoop:
    """execute() manages multi-turn agentic loop."""

    def test_single_turn_text_response(self):
        """LLM responds with text immediately (no tool calls)."""
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        gen = _make_generation(content="The answer is JWT.", tool_calls=None)
        client.complete.return_value = gen

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "What is auth?"}],
            tools=[{"type": "function", "function": {"name": "list_resources"}}],
            strategy_metadata={"resource_count": 2, "catalog_tokens": 50},
        )

        result = strategy.execute(
            prepared, task, client, max_tokens=2048, temperature=0.3
        )

        assert result.final_response == "The answer is JWT."
        assert len(result.generations) == 1
        assert result.strategy_metadata["turns"] == 1
        assert result.strategy_metadata["tool_calls_made"] == 0

    def test_multi_turn_tool_then_response(self):
        """LLM calls a tool, gets result, then responds with text."""
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        # Turn 1: LLM calls list_resources
        tool_call = _make_tool_call("call_1", "list_resources", "{}")
        gen_with_tool = _make_generation(content=None, tool_calls=[tool_call])

        # Turn 2: LLM responds with text
        gen_final = _make_generation(
            content="Based on the docs, use JWT.", tool_calls=None
        )

        client.complete.side_effect = [gen_with_tool, gen_final]

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "What is auth?"}],
            tools=[],
            strategy_metadata={"resource_count": 2, "catalog_tokens": 50},
        )

        result = strategy.execute(
            prepared, task, client, max_tokens=2048, temperature=0.3
        )

        assert result.final_response == "Based on the docs, use JWT."
        assert client.complete.call_count == 2
        assert len(result.generations) == 2
        assert result.strategy_metadata["turns"] == 2
        assert result.strategy_metadata["tool_calls_made"] == 1

    def test_max_turns_prevents_infinite_loop(self):
        """MAX_TURNS cap stops execution even if LLM keeps calling tools."""
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy(max_turns=3)
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        # Always returns tool calls, never text
        tool_call = _make_tool_call("call_n", "list_resources", "{}")
        gen_tool = _make_generation(content=None, tool_calls=[tool_call])
        client.complete.return_value = gen_tool

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "What is auth?"}],
            tools=[],
            strategy_metadata={"resource_count": 2, "catalog_tokens": 50},
        )

        result = strategy.execute(
            prepared, task, client, max_tokens=2048, temperature=0.3
        )

        assert client.complete.call_count == 3
        assert result.final_response is not None

    def test_multiple_tool_calls_in_one_turn(self):
        """LLM calls multiple tools in a single turn."""
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        tc1 = _make_tool_call("call_1", "list_resources", "{}")
        tc2 = _make_tool_call(
            "call_2", "read_resource", '{"uri": "docs://guides/auth.md"}'
        )
        gen_multi = _make_generation(content=None, tool_calls=[tc1, tc2])
        gen_final = _make_generation(content="Use JWT tokens.", tool_calls=None)

        client.complete.side_effect = [gen_multi, gen_final]

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "What is auth?"}],
            tools=[],
            strategy_metadata={"resource_count": 2, "catalog_tokens": 50},
        )

        result = strategy.execute(
            prepared, task, client, max_tokens=2048, temperature=0.3
        )

        assert result.final_response == "Use JWT tokens."
        assert client.complete.call_count == 2
        assert result.strategy_metadata["tool_calls_made"] == 2

    def test_messages_contain_full_conversation_history(self):
        """StrategyResult.messages contains the full multi-turn history."""
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        tool_call = _make_tool_call("call_1", "list_resources", "{}")
        gen_tool = _make_generation(content=None, tool_calls=[tool_call])
        gen_final = _make_generation(content="Answer.", tool_calls=None)
        client.complete.side_effect = [gen_tool, gen_final]

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "Question"}],
            tools=[],
            strategy_metadata={"resource_count": 2, "catalog_tokens": 50},
        )

        result = strategy.execute(
            prepared, task, client, max_tokens=2048, temperature=0.3
        )

        assert len(result.messages) > 2
        roles = [m["role"] for m in result.messages]
        assert "tool" in roles

    def test_content_none_with_tool_calls_handled(self):
        """content=None with tool_calls is NOT treated as an error."""
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        tool_call = _make_tool_call("call_1", "list_resources", "{}")
        gen_tool = _make_generation(content=None, tool_calls=[tool_call])
        gen_final = _make_generation(content="Final answer.", tool_calls=None)
        client.complete.side_effect = [gen_tool, gen_final]

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "Q"}],
            tools=[],
            strategy_metadata={"resource_count": 2, "catalog_tokens": 50},
        )

        result = strategy.execute(
            prepared, task, client, max_tokens=2048, temperature=0.3
        )

        assert result.final_response == "Final answer."
        assert client.complete.call_count == 2

    def test_token_aggregation_across_turns(self):
        """Total tokens are summed across all turns."""
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        tool_call = _make_tool_call("call_1", "list_resources", "{}")
        gen_tool = _make_generation(
            content=None,
            tool_calls=[tool_call],
            prompt_tokens=20,
            completion_tokens=10,
            total_tokens=30,
            cost=0.002,
        )
        gen_final = _make_generation(
            content="Answer.",
            tool_calls=None,
            prompt_tokens=30,
            completion_tokens=15,
            total_tokens=45,
            cost=0.003,
        )
        client.complete.side_effect = [gen_tool, gen_final]

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "Q"}],
            tools=[],
            strategy_metadata={"resource_count": 2, "catalog_tokens": 50},
        )

        result = strategy.execute(
            prepared, task, client, max_tokens=2048, temperature=0.3
        )

        assert result.total_prompt_tokens == 50
        assert result.total_completion_tokens == 25
        assert result.total_tokens == 75
        assert result.total_cost == 0.005


# ---------------------------------------------------------------------------
# TestResourceMetadataAblation
# ---------------------------------------------------------------------------


class TestResourceMetadataAblation:
    """Strategy metadata tracks resources fetched and tools used."""

    def test_resources_fetched_tracks_read_resource_uris(self):
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        tc1 = _make_tool_call(
            "call_1", "read_resource", '{"uri": "docs://guides/auth.md"}'
        )
        tc2 = _make_tool_call(
            "call_2", "read_resource", '{"uri": "docs://api/users.md"}'
        )
        gen_tool = _make_generation(content=None, tool_calls=[tc1, tc2])
        gen_final = _make_generation(content="Answer.", tool_calls=None)
        client.complete.side_effect = [gen_tool, gen_final]

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "Q"}],
            tools=[],
            strategy_metadata={"resource_count": 2, "catalog_tokens": 50},
        )

        result = strategy.execute(
            prepared, task, client, max_tokens=2048, temperature=0.3
        )

        assert "resources_fetched" in result.strategy_metadata
        fetched = result.strategy_metadata["resources_fetched"]
        assert "docs://guides/auth.md" in fetched
        assert "docs://api/users.md" in fetched

    def test_tools_used_tracks_distinct_tool_names(self):
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        tc1 = _make_tool_call("call_1", "list_resources", "{}")
        tc2 = _make_tool_call(
            "call_2", "read_resource", '{"uri": "docs://guides/auth.md"}'
        )
        gen_tool = _make_generation(content=None, tool_calls=[tc1, tc2])
        gen_final = _make_generation(content="Answer.", tool_calls=None)
        client.complete.side_effect = [gen_tool, gen_final]

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "Q"}],
            tools=[],
            strategy_metadata={"resource_count": 2, "catalog_tokens": 50},
        )

        result = strategy.execute(
            prepared, task, client, max_tokens=2048, temperature=0.3
        )

        assert "tools_used" in result.strategy_metadata
        assert set(result.strategy_metadata["tools_used"]) == {
            "list_resources",
            "read_resource",
        }

    def test_resource_count_in_execute_metadata(self):
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        gen_final = _make_generation(content="Answer.", tool_calls=None)
        client.complete.return_value = gen_final

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "Q"}],
            tools=[],
            strategy_metadata={"resource_count": 2, "catalog_tokens": 50},
        )

        result = strategy.execute(
            prepared, task, client, max_tokens=2048, temperature=0.3
        )

        assert result.strategy_metadata["resource_count"] == 2

    def test_no_tool_calls_yields_empty_resources_fetched(self):
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        gen_final = _make_generation(content="Answer.", tool_calls=None)
        client.complete.return_value = gen_final

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "Q"}],
            tools=[],
            strategy_metadata={"resource_count": 2, "catalog_tokens": 50},
        )

        result = strategy.execute(
            prepared, task, client, max_tokens=2048, temperature=0.3
        )

        assert result.strategy_metadata["resources_fetched"] == []
        assert result.strategy_metadata["tool_calls_made"] == 0
        assert result.strategy_metadata["tools_used"] == []

    def test_search_resources_not_tracked_in_resources_fetched(self):
        """search_resources calls should NOT appear in resources_fetched."""
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        task = make_mock_task()
        client = MagicMock()

        tc1 = _make_tool_call("call_1", "search_resources", '{"query": "JWT"}')
        gen_tool = _make_generation(content=None, tool_calls=[tc1])
        gen_final = _make_generation(content="Answer.", tool_calls=None)
        client.complete.side_effect = [gen_tool, gen_final]

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "Q"}],
            tools=[],
            strategy_metadata={"resource_count": 2, "catalog_tokens": 50},
        )

        result = strategy.execute(
            prepared, task, client, max_tokens=2048, temperature=0.3
        )

        assert result.strategy_metadata["resources_fetched"] == []
        assert "search_resources" in result.strategy_metadata["tools_used"]


# ---------------------------------------------------------------------------
# TestSetupTeardown
# ---------------------------------------------------------------------------


class TestSetupTeardown:
    """setup() and teardown() manage internal state."""

    def test_setup_populates_catalog(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        assert len(strategy._resource_catalog) == 2

    def test_teardown_clears_state(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Index", doc_tree)

        strategy.teardown()

        assert strategy._doc_tree is None
        assert strategy._resource_catalog == []
        assert strategy._tool_definitions == []


# ---------------------------------------------------------------------------
# TestCleanResponse
# ---------------------------------------------------------------------------


class TestCleanResponse:
    """final_response is cleaned of tool-call artifacts."""

    def test_clean_response_strips_tool_artifacts(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        raw = 'The answer is JWT.\n\n```json\n{"tool_calls": []}\n```'
        cleaned = strategy._clean_response(raw)
        assert "tool_calls" not in cleaned
        assert "JWT" in cleaned

    def test_clean_response_preserves_normal_text(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy

        strategy = MCPNativeStrategy()
        normal = "Authentication uses JWT tokens for security."
        assert strategy._clean_response(normal) == normal
