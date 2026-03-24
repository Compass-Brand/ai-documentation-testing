"""Tool-based context strategy -- multi-turn agentic doc access.

The LLM navigates documentation through tools (list_docs, read_doc,
search_docs) rather than receiving the full index in the prompt.
Tests whether index FORMAT helps the agent navigate and find files.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from typing import TYPE_CHECKING, Any

from agent_evals.context.base import ContextStrategy, PreparedContext, StrategyResult
from agent_evals.context.registry import register_strategy

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.llm.client import GenerationResult, LLMClient
    from agent_evals.tasks.base import EvalTask

logger = logging.getLogger(__name__)

DEFAULT_MAX_TURNS = 10

_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_docs",
            "description": "List all available documentation files with their index entries.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_doc",
            "description": "Read the full content of a documentation file by its path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path of the document to read.",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": "Search across all documentation files for content matching a query string.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Substring to search for across all documentation content.",
                    },
                },
                "required": ["query"],
            },
        },
    },
]

# Regex to strip trailing tool-call JSON artifacts from final responses.
# Uses [\s\S]*? (any character including newlines, non-greedy) to handle
# nested braces in tool_calls JSON like {"tool_calls": [{"id": "..."}]}.
_TOOL_ARTIFACT_RE = re.compile(
    r"\s*```(?:json)?\s*\{[\s\S]*?\"tool_calls\"[\s\S]*?\}\s*```\s*$",
    re.DOTALL,
)


@register_strategy
class ToolBasedStrategy(ContextStrategy):
    """Multi-turn agentic strategy with documentation tools."""

    def __init__(self, max_turns: int = DEFAULT_MAX_TURNS) -> None:
        self._max_turns = max(max_turns, 1)
        self._rendered_index: str = ""
        self._doc_tree: DocTree | None = None
        self._lock = threading.Lock()

    def name(self) -> str:
        return "tool_based"

    def supports_caching(self) -> bool:
        return False

    def setup(self, rendered_index: str, doc_tree: DocTree) -> None:
        with self._lock:
            self._rendered_index = rendered_index
            self._doc_tree = doc_tree

    def teardown(self) -> None:
        with self._lock:
            self._doc_tree = None
            self._rendered_index = ""

    def prepare(
        self, rendered_index: str, task: EvalTask, doc_tree: DocTree,
    ) -> PreparedContext:
        question = getattr(task.definition, "question", None)
        if question is None:
            question = "Answer the following task based on the available documentation."

        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are a documentation assistant. Use the provided tools "
                    "to find information in the documentation and answer the "
                    "user's question. Call list_docs to see available files, "
                    "read_doc to read a file, and search_docs to search content."
                ),
            },
            {"role": "user", "content": question},
        ]

        return PreparedContext(
            messages=messages,
            tools=list(_TOOL_DEFINITIONS),
            strategy_metadata={},
        )

    def execute(
        self,
        prepared: PreparedContext,
        task: EvalTask,
        client: LLMClient,
        max_tokens: int,
        temperature: float,
    ) -> StrategyResult:
        messages: list[dict] = list(prepared.messages)
        tool_defs = prepared.tools
        generations: list[GenerationResult] = []
        total_tool_calls = 0
        tools_used: set[str] = set()

        for turn in range(self._max_turns):
            generation = client.complete(
                messages,
                tools=tool_defs,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            generations.append(generation)

            if not generation.tool_calls:
                break

            # Append assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": generation.content or None,
                "tool_calls": generation.tool_calls,
            })

            # Execute each tool call and append results
            for tc in generation.tool_calls:
                fn_name = tc["function"]["name"]
                try:
                    fn_args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, TypeError):
                    fn_args = {}

                tool_result = self._execute_tool(fn_name, fn_args)
                tools_used.add(fn_name)
                total_tool_calls += 1

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result,
                })

        num_turns = len(generations)
        if not generations:
            return StrategyResult(
                final_response="",
                generations=[],
                total_prompt_tokens=0,
                total_completion_tokens=0,
                total_tokens=0,
                total_cost=None,
                messages=messages,
                strategy_metadata={
                    "turns": 0,
                    "tool_calls_made": total_tool_calls,
                    "tools_used": sorted(tools_used),
                },
            )
        last_gen = generations[-1]
        final_text = self._clean_response(last_gen.content or "")

        total_prompt = sum(g.prompt_tokens for g in generations)
        total_completion = sum(g.completion_tokens for g in generations)
        total_tokens = sum(g.total_tokens for g in generations)
        costs = [g.cost for g in generations if g.cost is not None]
        total_cost = sum(costs) if costs else None

        return StrategyResult(
            final_response=final_text,
            generations=generations,
            total_prompt_tokens=total_prompt,
            total_completion_tokens=total_completion,
            total_tokens=total_tokens,
            total_cost=total_cost,
            messages=messages,
            strategy_metadata={
                "turns": num_turns,
                "tool_calls_made": total_tool_calls,
                "tools_used": sorted(tools_used),
            },
        )

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Execute a tool by name and return its string result."""
        with self._lock:
            if name == "list_docs":
                return self._rendered_index

            if name == "read_doc":
                path = arguments.get("path", "")
                if self._doc_tree and path in self._doc_tree.files:
                    return self._doc_tree.files[path].content
                return f"Error: file not found at path '{path}'"

            if name == "search_docs":
                query = arguments.get("query", "")
                return self._search(query)

            return f"Error: unknown tool '{name}'"

    _MAX_SEARCH_RESULTS = 20

    def _search(self, query: str) -> str:
        """Substring search across all DocTree file contents."""
        if not self._doc_tree or not query:
            return "No matches found."

        query_lower = query.lower()
        results: list[str] = []

        for path, doc_file in sorted(self._doc_tree.files.items()):
            content = doc_file.content
            if query_lower in content.lower():
                lines = content.split("\n")
                matches = [
                    line.strip()
                    for line in lines
                    if query_lower in line.lower()
                ]
                snippet = "\n".join(matches[:5])
                results.append(f"--- {path} ---\n{snippet}")
                if len(results) >= self._MAX_SEARCH_RESULTS:
                    break

        if not results:
            return "No matches found."
        return "\n\n".join(results)

    def _clean_response(self, text: str) -> str:
        """Remove tool-call JSON artifacts from the final response text."""
        cleaned = _TOOL_ARTIFACT_RE.sub("", text)
        return cleaned.strip()
