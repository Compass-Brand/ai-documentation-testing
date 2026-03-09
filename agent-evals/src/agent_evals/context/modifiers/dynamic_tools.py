"""Dynamic tool availability modifier."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from agent_evals.context.base import ContextStrategy, PreparedContext, StrategyResult

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.llm.client import LLMClient
    from agent_evals.tasks.base import EvalTask

_PROGRESSIVE_UNLOCK = [
    "list_docs",
    "list_resources",
    "read_doc",
    "read_resource",
    "search_docs",
    "search_resources",
]
_EXPLORE_PHASE_TOOLS = {
    "list_docs",
    "list_resources",
    "read_doc",
    "read_resource",
}


def filter_tools(
    tools: list[dict[str, Any]],
    mode: str = "full",
    turn: int = 0,
    max_turns: int = 10,
) -> list[dict[str, Any]]:
    """Filter tool definitions based on mode and turn number.

    Modes:
    - "full": all tools available
    - "restricted": remove search_docs and search_resources
    - "progressive": unlock tools one-by-one per turn
    - "phase_based": explore phase (first half) = list+read only,
      answer phase (second half) = all tools
    """
    if mode == "full":
        return list(tools)

    if mode == "restricted":
        return [
            t
            for t in tools
            if t.get("function", {}).get("name", "")
            not in ("search_docs", "search_resources")
        ]

    if mode == "progressive":
        allowed: set[str] = set()
        for i, tool_name in enumerate(_PROGRESSIVE_UNLOCK):
            if i <= turn:
                allowed.add(tool_name)
        return [
            t
            for t in tools
            if t.get("function", {}).get("name", "") in allowed
        ]

    if mode == "phase_based":
        midpoint = max_turns // 2
        if turn < midpoint:
            return [
                t
                for t in tools
                if t.get("function", {}).get("name", "")
                in _EXPLORE_PHASE_TOOLS
            ]
        return list(tools)

    return list(tools)


class DynamicToolModifier(ContextStrategy):
    """Wraps a strategy with dynamic tool filtering per mode."""

    def __init__(self, inner: ContextStrategy, mode: str = "full") -> None:
        self._inner = inner
        self._mode = mode

    def name(self) -> str:
        return f"{self._inner.name()}+{self._mode}_tools"

    def supports_caching(self) -> bool:
        return False

    def setup(self, rendered_index: str, doc_tree: DocTree) -> None:
        self._inner.setup(rendered_index, doc_tree)

    def teardown(self) -> None:
        self._inner.teardown()

    def prepare(
        self,
        rendered_index: str,
        task: EvalTask,
        doc_tree: DocTree,
    ) -> PreparedContext:
        prepared = self._inner.prepare(rendered_index, task, doc_tree)
        if prepared.tools:
            prepared.tools = filter_tools(prepared.tools, self._mode, turn=0)
        metadata = dict(prepared.strategy_metadata)
        metadata["dynamic_tools_mode"] = self._mode
        metadata["initial_tools_available"] = len(prepared.tools or [])
        prepared.strategy_metadata = metadata
        return prepared

    def execute(
        self,
        prepared: PreparedContext,
        task: EvalTask,
        client: LLMClient,
        max_tokens: int,
        temperature: float,
    ) -> StrategyResult:
        if self._mode == "phase_based":
            return self._execute_phase_based(
                prepared, task, client, max_tokens, temperature,
            )

        result = self._inner.execute(
            prepared, task, client, max_tokens, temperature,
        )
        metadata = dict(result.strategy_metadata)
        metadata["dynamic_tools_mode"] = self._mode
        return StrategyResult(
            final_response=result.final_response,
            generations=result.generations,
            total_prompt_tokens=result.total_prompt_tokens,
            total_completion_tokens=result.total_completion_tokens,
            total_tokens=result.total_tokens,
            total_cost=result.total_cost,
            messages=result.messages,
            strategy_metadata=metadata,
        )

    def _execute_phase_based(
        self,
        prepared: PreparedContext,
        task: EvalTask,
        client: LLMClient,
        max_tokens: int,
        temperature: float,
    ) -> StrategyResult:
        """Multi-turn loop with tool availability changing by phase."""
        messages: list[dict] = list(prepared.messages)
        all_tools = prepared.tools or []
        generations = []
        max_turns = 10
        total_tool_calls = 0
        tools_used: set[str] = set()

        for turn in range(max_turns):
            turn_tools = filter_tools(
                all_tools, "phase_based", turn=turn, max_turns=max_turns,
            )
            generation = client.complete(
                messages,
                tools=turn_tools,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            generations.append(generation)

            if not generation.tool_calls:
                break

            messages.append({
                "role": "assistant",
                "content": generation.content or None,
                "tool_calls": generation.tool_calls,
            })

            for tc in generation.tool_calls:
                fn_name = tc["function"]["name"]
                try:
                    fn_args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, TypeError):
                    fn_args = {}

                tool_result = self._inner._execute_tool(fn_name, fn_args)
                tools_used.add(fn_name)
                total_tool_calls += 1

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result,
                })

        num_turns = len(generations)
        last_gen = generations[-1]
        final_text = (last_gen.content or "").strip()

        total_prompt = sum(g.prompt_tokens for g in generations)
        total_completion = sum(g.completion_tokens for g in generations)
        total_tokens = sum(g.total_tokens for g in generations)
        total_cost = (
            sum(g.cost for g in generations if g.cost is not None) or None
        )

        return StrategyResult(
            final_response=final_text,
            generations=generations,
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
            total_tokens=total_tokens,
            total_cost=total_cost,
            messages=messages,
            strategy_metadata={
                "dynamic_tools_mode": "phase_based",
                "turns": num_turns,
                "tool_calls_made": total_tool_calls,
                "tools_used": sorted(tools_used),
            },
        )
