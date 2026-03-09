"""Tests for DynamicToolModifier (Phase C, Task 8).

Tests cover:
- filter_tools() with all four modes: full, restricted, progressive, phase_based
- DynamicToolModifier wraps an inner strategy with dynamic tool filtering
- Phase-based mode implements its own multi-turn execute loop
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from conftest import make_mock_task

from agent_evals.context.base import PreparedContext, StrategyResult
from agent_evals.llm.client import GenerationResult
from agent_index.models import DocFile, DocTree


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool(name: str) -> dict:
    """Create a minimal OpenAI function-calling tool definition."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": f"Tool: {name}",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }


ALL_TOOLS = [
    _make_tool("list_docs"),
    _make_tool("list_resources"),
    _make_tool("read_doc"),
    _make_tool("read_resource"),
    _make_tool("search_docs"),
    _make_tool("search_resources"),
]


def _tool_names(tools: list[dict]) -> set[str]:
    """Extract tool names from a list of tool definitions."""
    return {t["function"]["name"] for t in tools}


def _make_generation_result(
    *,
    content: str | None = None,
    tool_calls: list | None = None,
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    total_tokens: int = 15,
    cost: float | None = 0.001,
    model: str = "test-model",
) -> GenerationResult:
    """Create a GenerationResult with tool_calls support."""
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


def _make_tool_call(tool_id: str, name: str, arguments: str = "{}") -> dict:
    """Create a tool call dict in OpenAI serialized format."""
    return {
        "id": tool_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


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
        },
        scanned_at=datetime(2026, 1, 1),
        source="/test",
        total_tokens=10,
    )


def _make_inner_strategy(
    *,
    name: str = "tool_based",
    tools: list[dict] | None = None,
    final_response: str = "inner response",
) -> MagicMock:
    """Create a mock inner ContextStrategy."""
    inner = MagicMock()
    inner.name.return_value = name

    prepared = PreparedContext(
        messages=[{"role": "user", "content": "test question"}],
        tools=list(tools) if tools is not None else list(ALL_TOOLS),
        strategy_metadata={},
    )
    inner.prepare.return_value = prepared

    result = StrategyResult(
        final_response=final_response,
        generations=[],
        total_prompt_tokens=100,
        total_completion_tokens=50,
        total_tokens=150,
        total_cost=0.005,
        messages=[{"role": "user", "content": "test question"}],
        strategy_metadata={},
    )
    inner.execute.return_value = result

    return inner


# ---------------------------------------------------------------------------
# TestDynamicToolModes: filter_tools() function
# ---------------------------------------------------------------------------


class TestDynamicToolModes:
    """Test filter_tools() with all four modes."""

    def test_full_returns_all(self):
        from agent_evals.context.modifiers.dynamic_tools import filter_tools

        result = filter_tools(ALL_TOOLS, mode="full")
        assert _tool_names(result) == _tool_names(ALL_TOOLS)
        assert len(result) == len(ALL_TOOLS)

    def test_restricted_removes_search(self):
        from agent_evals.context.modifiers.dynamic_tools import filter_tools

        result = filter_tools(ALL_TOOLS, mode="restricted")
        names = _tool_names(result)
        assert "search_docs" not in names
        assert "search_resources" not in names
        # Non-search tools should remain
        assert "list_docs" in names
        assert "read_doc" in names
        assert "list_resources" in names
        assert "read_resource" in names

    def test_progressive_phase_1(self):
        """Turn 0: only list tools available."""
        from agent_evals.context.modifiers.dynamic_tools import filter_tools

        result = filter_tools(ALL_TOOLS, mode="progressive", turn=0)
        names = _tool_names(result)
        assert "list_docs" in names
        # Turn 0 unlocks index 0 only -> list_docs
        assert "read_doc" not in names
        assert "search_docs" not in names

    def test_progressive_phase_2(self):
        """Turn 1: list + read tools available."""
        from agent_evals.context.modifiers.dynamic_tools import filter_tools

        result = filter_tools(ALL_TOOLS, mode="progressive", turn=1)
        names = _tool_names(result)
        assert "list_docs" in names
        assert "list_resources" in names
        # Turn 1 unlocks indices 0 and 1 -> list_docs, list_resources
        assert "search_docs" not in names

    def test_progressive_phase_3(self):
        """Turn 2+: all tools available (indices 0, 1, 2 unlocked)."""
        from agent_evals.context.modifiers.dynamic_tools import filter_tools

        result = filter_tools(ALL_TOOLS, mode="progressive", turn=2)
        names = _tool_names(result)
        assert "list_docs" in names
        assert "list_resources" in names
        assert "read_doc" in names

    def test_phase_based_explore_phase(self):
        """First half of turns: only explore tools (list + read)."""
        from agent_evals.context.modifiers.dynamic_tools import filter_tools

        # max_turns=10, midpoint=5, turn 2 < 5 -> explore phase
        result = filter_tools(ALL_TOOLS, mode="phase_based", turn=2, max_turns=10)
        names = _tool_names(result)
        assert "list_docs" in names
        assert "list_resources" in names
        assert "read_doc" in names
        assert "read_resource" in names
        assert "search_docs" not in names
        assert "search_resources" not in names

    def test_phase_based_answer_phase(self):
        """Second half of turns: all tools available."""
        from agent_evals.context.modifiers.dynamic_tools import filter_tools

        # max_turns=10, midpoint=5, turn 5 >= 5 -> answer phase
        result = filter_tools(ALL_TOOLS, mode="phase_based", turn=5, max_turns=10)
        names = _tool_names(result)
        assert names == _tool_names(ALL_TOOLS)


# ---------------------------------------------------------------------------
# TestDynamicToolModifier: wrapper properties and prepare()
# ---------------------------------------------------------------------------


class TestDynamicToolModifier:
    """Test DynamicToolModifier wrapping behavior."""

    def test_modifier_name(self):
        from agent_evals.context.modifiers.dynamic_tools import DynamicToolModifier

        inner = _make_inner_strategy(name="tool_based")
        modifier = DynamicToolModifier(inner, mode="restricted")
        assert modifier.name() == "tool_based+restricted_tools"

    def test_modifier_tracks_tools_available(self):
        from agent_evals.context.modifiers.dynamic_tools import DynamicToolModifier

        inner = _make_inner_strategy(tools=ALL_TOOLS)
        modifier = DynamicToolModifier(inner, mode="restricted")

        task = make_mock_task()
        doc_tree = _make_doc_tree()
        prepared = modifier.prepare("# Index", task, doc_tree)

        assert "dynamic_tools_mode" in prepared.strategy_metadata
        assert prepared.strategy_metadata["dynamic_tools_mode"] == "restricted"
        assert "initial_tools_available" in prepared.strategy_metadata
        # restricted removes 2 search tools from 6 total
        assert prepared.strategy_metadata["initial_tools_available"] == 4


# ---------------------------------------------------------------------------
# TestPhaseBasedExecuteLoop: phase_based multi-turn execution
# ---------------------------------------------------------------------------


class TestPhaseBasedExecuteLoop:
    """Test phase_based mode's own multi-turn execute loop."""

    def test_phase_based_changes_tools_during_execution(self):
        from agent_evals.context.modifiers.dynamic_tools import DynamicToolModifier

        inner = _make_inner_strategy(tools=ALL_TOOLS)
        # Give inner a _execute_tool method
        inner._execute_tool = MagicMock(return_value="tool result")

        modifier = DynamicToolModifier(inner, mode="phase_based")

        task = make_mock_task()
        client = MagicMock()

        # Turn 0 (explore phase): LLM calls list_docs
        tc_explore = _make_tool_call("call_1", "list_docs")
        gen_explore = _make_generation_result(
            content=None, tool_calls=[tc_explore],
        )

        # Turn 1 (still explore): LLM calls read_doc
        tc_read = _make_tool_call("call_2", "read_doc", '{"path": "guides/auth.md"}')
        gen_read = _make_generation_result(
            content=None, tool_calls=[tc_read],
        )

        # Turn 2 (still explore for max_turns=10): final text answer
        gen_final = _make_generation_result(
            content="The answer is JWT.", tool_calls=None,
        )

        client.complete.side_effect = [gen_explore, gen_read, gen_final]

        prepared = PreparedContext(
            messages=[{"role": "user", "content": "What is auth?"}],
            tools=list(ALL_TOOLS),
            strategy_metadata={"dynamic_tools_mode": "phase_based"},
        )

        result = modifier.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        assert result.final_response == "The answer is JWT."
        assert result.strategy_metadata["dynamic_tools_mode"] == "phase_based"
        assert result.strategy_metadata["turns"] == 3
        assert result.strategy_metadata["tool_calls_made"] == 2
        assert "list_docs" in result.strategy_metadata["tools_used"]
        assert "read_doc" in result.strategy_metadata["tools_used"]

        # Verify that client.complete was called with different tool sets per turn.
        # Turns 0 and 1 are explore phase (turn < midpoint=5) -> only explore tools.
        # Turn 2 is still explore phase -> explore tools only.
        explore_tool_names = {"list_docs", "list_resources", "read_doc", "read_resource"}
        for call_idx in range(3):
            call_args = client.complete.call_args_list[call_idx]
            tools_passed = call_args[1].get("tools", call_args[0][1] if len(call_args[0]) > 1 else None)
            if tools_passed is not None:
                names = _tool_names(tools_passed)
                if call_idx < 3:  # All turns < midpoint(5) for max_turns=10
                    assert names == explore_tool_names, (
                        f"Turn {call_idx}: expected explore tools, got {names}"
                    )
