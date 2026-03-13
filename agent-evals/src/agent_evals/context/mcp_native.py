"""MCP-native context strategy -- resource catalog browsing."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any

from agent_evals.context.base import ContextStrategy, PreparedContext, StrategyResult
from agent_evals.context.registry import register_strategy

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.llm.client import GenerationResult, LLMClient
    from agent_evals.tasks.base import EvalTask

logger = logging.getLogger(__name__)

DEFAULT_MAX_TURNS = 10

_TOOL_ARTIFACT_RE = re.compile(
    r"\s*```(?:json)?\s*\{[^}]*\"?tool_calls\"?[^}]*\}\s*```\s*$",
    re.DOTALL,
)


def _build_resource_catalog(doc_tree: DocTree) -> list[dict[str, str]]:
    catalog: list[dict[str, str]] = []
    for rel_path in sorted(doc_tree.files):
        doc = doc_tree.files[rel_path]
        catalog.append({
            "uri": f"docs://{rel_path}",
            "name": rel_path,
            "description": doc.summary or f"Documentation file: {rel_path}",
            "mimeType": "text/markdown",
            "tier": doc.tier,
            "section": doc.section,
            "token_count": str(doc.token_count or 0),
        })
    return catalog


def _build_tool_definitions(catalog: list[dict[str, str]]) -> list[dict[str, Any]]:
    uri_enum = [entry["uri"] for entry in catalog]
    return [
        {
            "type": "function",
            "function": {
                "name": "list_resources",
                "description": (
                    "List all available documentation resources with their "
                    "URIs, descriptions, tiers, and sections."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_resource",
                "description": "Read the full content of a documentation resource by URI.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "uri": {
                            "type": "string",
                            "description": "Resource URI to read.",
                            "enum": uri_enum,
                        },
                    },
                    "required": ["uri"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_resources",
                "description": (
                    "Search across all documentation resources for content "
                    "matching a query string."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query.",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
    ]


@register_strategy
class MCPNativeStrategy(ContextStrategy):
    """MCP-native strategy with resource catalog browsing."""

    def __init__(self, max_turns: int = DEFAULT_MAX_TURNS) -> None:
        self._max_turns = max_turns
        self._doc_tree: DocTree | None = None
        self._resource_catalog: list[dict[str, str]] = []
        self._tool_definitions: list[dict[str, Any]] = []

    def name(self) -> str:
        return "mcp_native"

    def supports_caching(self) -> bool:
        return False

    def setup(self, rendered_index: str, doc_tree: DocTree) -> None:
        self._doc_tree = doc_tree
        self._resource_catalog = _build_resource_catalog(doc_tree)
        self._tool_definitions = _build_tool_definitions(self._resource_catalog)

    def teardown(self) -> None:
        self._doc_tree = None
        self._resource_catalog = []
        self._tool_definitions = []

    def prepare(
        self, rendered_index: str, task: EvalTask, doc_tree: DocTree,
    ) -> PreparedContext:
        from agent_evals.llm.token_counter import count_tokens

        question = getattr(task.definition, "question", None)
        if question is None:
            question = (
                "Answer the following task based on the available documentation."
            )

        catalog_summary = json.dumps(self._resource_catalog, indent=2)
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "You are a documentation assistant with access to MCP "
                    "resources. Use list_resources to see available docs, "
                    "read_resource to fetch content by URI, and "
                    "search_resources to search across all docs.\n\n"
                    f"Available resources:\n{catalog_summary}"
                ),
            },
            {"role": "user", "content": question},
        ]

        return PreparedContext(
            messages=messages,
            tools=list(self._tool_definitions),
            strategy_metadata={
                "resource_count": len(self._resource_catalog),
                "catalog_tokens": count_tokens(catalog_summary),
            },
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
        resources_fetched: list[str] = []

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

                tool_result = self._execute_tool(fn_name, fn_args)
                tools_used.add(fn_name)
                total_tool_calls += 1

                if fn_name == "read_resource" and "uri" in fn_args:
                    resources_fetched.append(fn_args["uri"])

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result,
                })

        num_turns = len(generations)
        last_gen = generations[-1]
        final_text = self._clean_response(last_gen.content or "")

        total_prompt = sum(g.prompt_tokens for g in generations)
        total_completion = sum(g.completion_tokens for g in generations)
        total_tokens = sum(g.total_tokens for g in generations)
        known_costs = [g.cost for g in generations if g.cost is not None]
        total_cost = sum(known_costs) if known_costs else None

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
                "resources_fetched": resources_fetched,
                "resource_count": len(self._resource_catalog),
            },
        )

    def _execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        if name == "list_resources":
            return json.dumps(self._resource_catalog, indent=2)

        if name == "read_resource":
            uri = arguments.get("uri", "")
            rel_path = uri.removeprefix("docs://")
            if self._doc_tree and rel_path in self._doc_tree.files:
                return self._doc_tree.files[rel_path].content
            return f"Error: resource not found at URI '{uri}'"

        if name == "search_resources":
            query = arguments.get("query", "")
            return self._search(query)

        return f"Error: unknown tool '{name}'"

    _MAX_SEARCH_RESULTS = 20

    def _search(self, query: str) -> str:
        if not self._doc_tree or not query:
            return "No results."

        query_lower = query.lower()
        results: list[str] = []
        for rel_path, doc in sorted(self._doc_tree.files.items()):
            if query_lower in doc.content.lower():
                lines = doc.content.split("\n")
                matches = [
                    line.strip()
                    for line in lines
                    if query_lower in line.lower()
                ]
                snippet = "\n".join(matches[:5])
                results.append(f"docs://{rel_path}:\n{snippet}")
                if len(results) >= self._MAX_SEARCH_RESULTS:
                    break

        return "\n---\n".join(results) if results else "No results."

    def _clean_response(self, text: str) -> str:
        cleaned = _TOOL_ARTIFACT_RE.sub("", text)
        return cleaned.strip()
