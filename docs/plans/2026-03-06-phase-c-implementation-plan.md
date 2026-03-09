# Phase C Implementation Plan: Modern Agent Patterns

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Test how agents work today — MCP discovery, compressed context, dynamic tool sets, instruction file formats, hallucination detection, multi-session persistence, and KV-cache friendliness.

**Architecture:** Two new context strategies (MCP-native, compression), two new variant axes (tool descriptions, agent instruction files), one new scoring dimension (hallucination), and three strategy modifiers (multi-session, dynamic tools, KV-cache tracking). All build on Phase A (datasets, judge) and Phase B (CostMetrics, generation stats, stability).

**Tech Stack:** Python 3.11+, UV workspace, pytest, LiteLLM (OpenRouter), httpx

**Prerequisites:** Phase A and Phase B must be complete. Phase A provides datasets and judge module. Phase B provides CostMetrics, generation stats fetcher, and stability metrics.

**Guardrails:** TDD, 80%+ coverage, all tests pass before commit, type hints, max 300 lines/file, max 50 lines/function.

**Commands:**
- Run all tests: `~/.local/bin/uv run pytest agent-evals/tests/ -v`
- Run with coverage: `~/.local/bin/uv run pytest agent-evals/tests/ --cov=agent_evals --cov-report=term-missing`

---

## Task 0: Verify Phase A + B Baseline

**Step 1: Confirm all tests pass**

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -v --tb=short 2>&1 | tail -10
```

Record test count. Phase C must only add tests, never break existing ones.

**Step 2: Verify Phase A deliverables exist**

```bash
ls agent-evals/src/agent_evals/datasets/base.py
ls agent-evals/src/agent_evals/judge/calibrator.py
ls agent-evals/src/agent_evals/judge/poll.py
```

**Step 3: Verify Phase B deliverables exist**

```bash
ls agent-evals/src/agent_evals/metrics.py
ls agent-evals/src/agent_evals/llm/generation_stats.py
ls agent-evals/src/agent_evals/reports/stability.py
ls agent-evals/src/agent_evals/reports/cost_efficiency.py
```

---

## Task 1: Update VariantMetadata Axis Constraint

**Purpose:** Allow axes 11 and 12 for new variant dimensions (tool descriptions, agent instruction files).

**Files:**
- Modify: `agent-evals/src/agent_evals/variants/base.py:31`
- Modify: `agent-evals/tests/test_variants.py` (or whichever file tests VariantMetadata)

### Step 1: Write failing test

**Append to test file for variants:**

```python
class TestVariantMetadataAxisRange:
    def test_axis_11_valid(self):
        meta = VariantMetadata(
            name="tool-desc-minimal",
            axis=11,
            category="tool_description",
            description="Minimal tool descriptions.",
        )
        assert meta.axis == 11

    def test_axis_12_valid(self):
        meta = VariantMetadata(
            name="instruction-none",
            axis=12,
            category="agent_instruction",
            description="No instruction file.",
        )
        assert meta.axis == 12

    def test_axis_14_invalid(self):
        import pytest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            VariantMetadata(
                name="invalid",
                axis=14,
                category="test",
                description="Should fail.",
            )
```

### Step 2: Run test to verify it fails

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -k "test_axis_11_valid" -v
```

Expected: FAIL — `axis=11` exceeds current `le=10` constraint.

### Step 3: Update constraint

**Modify** `agent-evals/src/agent_evals/variants/base.py` line 31:

```python
# Before:
axis: int = Field(ge=0, le=10)

# After:
axis: int = Field(ge=0, le=13)
```

> **Note:** The upper bound is set to `le=13` (not 12) to leave room for future axes. Axis 11 covers both tool description quality and tool set size variants. Axis 12 covers agent instruction verbosity.

### Step 4: Run tests to verify pass

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -k "TestVariantMetadataAxisRange" -v
```

Expected: ALL PASS

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/variants/base.py agent-evals/tests/test_variants.py
git commit -m "feat(variants): extend axis range to 12 for Phase C axes

Allows tool_description (axis 11) and agent_instruction (axis 12).

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: MCP-Native Strategy (C1)

**Purpose:** Model the MCP interaction pattern where documentation is exposed as discrete resources with metadata. Agent sees a resource catalog upfront, then selectively fetches content.

**Key difference from tool_based:** Agent browses a described resource catalog (like MCP tool definitions consuming ~14.3K tokens per server) rather than receiving a generic "list_docs/read_doc/search_docs" tool set.

**Files:**
- Create: `agent-evals/src/agent_evals/context/mcp_native.py`
- Modify: `agent-evals/src/agent_evals/context/__init__.py`
- Modify: `agent-evals/src/agent_evals/context/base.py` (StrategyConfig)
- Create: `agent-evals/tests/test_context_mcp_native.py`

### Step 1: Write failing tests

**Create** `agent-evals/tests/test_context_mcp_native.py`:

```python
"""Tests for MCP-native context strategy."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from agent_index.models import DocFile, DocTree


def _make_doc_tree() -> DocTree:
    return DocTree(
        files={
            "guides/auth.md": DocFile(
                rel_path="guides/auth.md",
                content="# Authentication\nUse OAuth2 for auth.",
                size_bytes=40,
                token_count=12,
                tier="required",
                section="Guides",
                summary="OAuth2 authentication guide",
                related=["api/users.md"],
            ),
            "api/users.md": DocFile(
                rel_path="api/users.md",
                content="# Users API\nGET /users returns list.",
                size_bytes=44,
                token_count=10,
                tier="recommended",
                section="API",
                summary="Users endpoint reference",
                related=[],
            ),
        },
        scanned_at=datetime(2026, 1, 1),
        source="/test",
        total_tokens=22,
    )


def _make_tool_call(tool_id: str, name: str, arguments: str) -> dict:
    return {
        "id": tool_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def _make_generation(
    *, content: str | None = None, tool_calls: list | None = None,
    prompt_tokens: int = 10, completion_tokens: int = 5,
    total_tokens: int = 15, cost: float = 0.001,
) -> MagicMock:
    gen = MagicMock()
    gen.content = content
    gen.tool_calls = tool_calls
    gen.prompt_tokens = prompt_tokens
    gen.completion_tokens = completion_tokens
    gen.total_tokens = total_tokens
    gen.cost = cost
    return gen


class TestMCPNativeRegistration:
    def test_registered_by_name(self):
        from agent_evals.context.registry import get_strategy_by_name, load_all
        load_all()
        strategy = get_strategy_by_name("mcp_native")
        assert strategy is not None
        assert strategy.name() == "mcp_native"

    def test_not_cacheable(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy
        strategy = MCPNativeStrategy()
        assert strategy.supports_caching() is False


class TestMCPResourceCatalog:
    def test_setup_builds_resource_catalog(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy
        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        rendered = "# Index\n- guides/auth.md: OAuth2 auth guide"
        strategy.setup(rendered, doc_tree)
        # After setup, resource catalog should be populated
        assert len(strategy._resource_catalog) > 0

    def test_catalog_entries_have_uri_and_description(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy
        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("index", doc_tree)
        for entry in strategy._resource_catalog:
            assert "uri" in entry
            assert "description" in entry
            assert "name" in entry


class TestMCPPrepare:
    def test_prepare_includes_resource_tools(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy
        from tests.conftest import make_mock_task
        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("index", doc_tree)
        task = make_mock_task()
        prepared = strategy.prepare("index", task, doc_tree)
        assert prepared.tools is not None
        # Should have list_resources + read_resource tools
        tool_names = [t["function"]["name"] for t in prepared.tools]
        assert "list_resources" in tool_names
        assert "read_resource" in tool_names

    def test_prepare_system_prompt_mentions_resources(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy
        from tests.conftest import make_mock_task
        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("index", doc_tree)
        task = make_mock_task()
        prepared = strategy.prepare("index", task, doc_tree)
        system_msg = prepared.messages[0]["content"]
        assert "resource" in system_msg.lower()

    def test_prepare_does_not_inject_full_content(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy
        from tests.conftest import make_mock_task
        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("# Full index content here", doc_tree)
        task = make_mock_task()
        prepared = strategy.prepare("# Full index content here", task, doc_tree)
        # System prompt should NOT contain full doc content
        all_content = " ".join(m.get("content", "") for m in prepared.messages if m.get("content"))
        assert "Use OAuth2 for auth" not in all_content


class TestMCPExecuteTool:
    def test_list_resources_returns_catalog(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy
        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("index", doc_tree)
        result = strategy._execute_tool("list_resources", {})
        assert "guides/auth.md" in result
        assert "api/users.md" in result

    def test_read_resource_returns_content(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy
        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("index", doc_tree)
        result = strategy._execute_tool(
            "read_resource", {"uri": "docs://guides/auth.md"},
        )
        assert "OAuth2" in result

    def test_read_resource_unknown_uri(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy
        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("index", doc_tree)
        result = strategy._execute_tool(
            "read_resource", {"uri": "docs://nonexistent.md"},
        )
        assert "not found" in result.lower() or "error" in result.lower()

    def test_search_resources_finds_matches(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy
        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("index", doc_tree)
        result = strategy._execute_tool(
            "search_resources", {"query": "OAuth2"},
        )
        assert "auth" in result.lower()


class TestMCPMultiTurnLoop:
    def test_single_turn_no_tools(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy
        from tests.conftest import make_mock_task
        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("index", doc_tree)
        task = make_mock_task()
        prepared = strategy.prepare("index", task, doc_tree)

        client = MagicMock()
        gen = _make_generation(content="The answer is OAuth2.", tool_calls=None)
        client.complete.return_value = gen

        result = strategy.execute(prepared, task, client, 1024, 0.0)
        assert result.final_response == "The answer is OAuth2."
        assert result.strategy_metadata["turns"] == 1
        assert result.strategy_metadata["tool_calls_made"] == 0

    def test_multi_turn_with_resource_fetch(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy
        from tests.conftest import make_mock_task
        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("index", doc_tree)
        task = make_mock_task()
        prepared = strategy.prepare("index", task, doc_tree)

        client = MagicMock()
        # Turn 1: agent calls list_resources
        gen1 = _make_generation(
            content=None,
            tool_calls=[_make_tool_call("tc1", "list_resources", "{}")],
        )
        # Turn 2: agent calls read_resource
        gen2 = _make_generation(
            content=None,
            tool_calls=[_make_tool_call(
                "tc2", "read_resource",
                '{"uri": "docs://guides/auth.md"}',
            )],
        )
        # Turn 3: agent responds
        gen3 = _make_generation(content="Use OAuth2 for authentication.")
        client.complete.side_effect = [gen1, gen2, gen3]

        result = strategy.execute(prepared, task, client, 1024, 0.0)
        assert "OAuth2" in result.final_response
        assert result.strategy_metadata["turns"] == 3
        assert result.strategy_metadata["tool_calls_made"] == 2
        assert "list_resources" in result.strategy_metadata["tools_used"]
        assert "read_resource" in result.strategy_metadata["tools_used"]

    def test_max_turns_respected(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy
        from tests.conftest import make_mock_task
        strategy = MCPNativeStrategy(max_turns=2)
        doc_tree = _make_doc_tree()
        strategy.setup("index", doc_tree)
        task = make_mock_task()
        prepared = strategy.prepare("index", task, doc_tree)

        client = MagicMock()
        # Both turns call tools — loop hits max
        gen_with_tools = _make_generation(
            content=None,
            tool_calls=[_make_tool_call("tc1", "list_resources", "{}")],
        )
        client.complete.return_value = gen_with_tools

        result = strategy.execute(prepared, task, client, 1024, 0.0)
        assert result.strategy_metadata["turns"] == 2

    def test_strategy_metadata_includes_resources_fetched(self):
        from agent_evals.context.mcp_native import MCPNativeStrategy
        from tests.conftest import make_mock_task
        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("index", doc_tree)
        task = make_mock_task()
        prepared = strategy.prepare("index", task, doc_tree)

        client = MagicMock()
        gen1 = _make_generation(
            content=None,
            tool_calls=[_make_tool_call(
                "tc1", "read_resource",
                '{"uri": "docs://guides/auth.md"}',
            )],
        )
        gen2 = _make_generation(content="Done.")
        client.complete.side_effect = [gen1, gen2]

        result = strategy.execute(prepared, task, client, 1024, 0.0)
        assert "resources_fetched" in result.strategy_metadata
        assert "docs://guides/auth.md" in result.strategy_metadata["resources_fetched"]
```

### Step 2: Run tests to verify they fail

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_context_mcp_native.py -v
```

Expected: FAIL — `mcp_native` module does not exist.

### Step 3: Implement MCPNativeStrategy

**Create** `agent-evals/src/agent_evals/context/mcp_native.py`:

```python
"""MCP-native context strategy -- resource catalog browsing.

The LLM sees a catalog of described MCP resources upfront, then
selectively fetches content via list_resources, read_resource, and
search_resources tools. Tests whether resource metadata helps the
agent find the right content and how catalog overhead affects
performance.
"""

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
    """Build MCP resource catalog entries from DocTree."""
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
    """Build OpenAI function-calling tool defs for MCP resource access."""
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
                "name": "read_resource",
                "description": (
                    "Read the full content of a documentation resource by URI."
                ),
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
        question = getattr(task.definition, "question", None)
        if question is None:
            question = "Answer the following task based on the available documentation."

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
            strategy_metadata={"resource_count": len(self._resource_catalog)},
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
            # Strip docs:// prefix to get rel_path
            rel_path = uri.removeprefix("docs://")
            if self._doc_tree and rel_path in self._doc_tree.files:
                return self._doc_tree.files[rel_path].content
            return f"Error: resource not found at URI '{uri}'"

        if name == "search_resources":
            query = arguments.get("query", "")
            return self._search(query)

        return f"Error: unknown tool '{name}'"

    def _search(self, query: str) -> str:
        if not self._doc_tree or not query:
            return "No results."
        query_lower = query.lower()
        results: list[str] = []
        for rel_path, doc in sorted(self._doc_tree.files.items()):
            if query_lower in doc.content.lower():
                snippet = doc.content[:200]
                results.append(f"docs://{rel_path}: {snippet}")
        return "\n---\n".join(results) if results else "No results."

    def _clean_response(self, text: str) -> str:
        cleaned = _TOOL_ARTIFACT_RE.sub("", text)
        return cleaned.strip()
```

### Step 4: Update `__init__.py` exports

**Add** to `agent-evals/src/agent_evals/context/__init__.py`:

```python
from agent_evals.context.mcp_native import MCPNativeStrategy

# Add to __all__:
"MCPNativeStrategy",
```

### Step 5: Run tests

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_context_mcp_native.py -v
```

Expected: ALL PASS

### Step 6: Run full test suite

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -v --tb=short 2>&1 | tail -10
```

Expected: ALL PASS, no regressions.

### Step 7: Add resource metadata ablation tests

**Append to** `agent-evals/tests/test_context_mcp_native.py`:

```python
class TestResourceMetadataAblation:
    def test_catalog_with_summaries_vs_without(self):
        """Compare catalog entries with summaries vs. path-only entries."""
        from agent_evals.context.mcp_native import MCPNativeStrategy, _build_resource_catalog
        doc_tree_with_summaries = _make_doc_tree()
        catalog_with = _build_resource_catalog(doc_tree_with_summaries)
        # Verify summaries are present
        for entry in catalog_with:
            assert entry["description"] != entry["name"]
            assert len(entry["description"]) > len(entry["name"])

        # Build a tree without summaries
        doc_tree_without = _make_doc_tree()
        for doc in doc_tree_without.files.values():
            doc.summary = None
        catalog_without = _build_resource_catalog(doc_tree_without)
        # Without summaries, description falls back to generic
        for entry in catalog_without:
            assert "Documentation file:" in entry["description"]

        # Both catalogs have same number of entries
        assert len(catalog_with) == len(catalog_without)

    def test_catalog_token_overhead(self):
        """Measure token count of catalog and verify it's tracked in strategy_metadata."""
        from agent_evals.context.mcp_native import MCPNativeStrategy
        from tests.conftest import make_mock_task
        strategy = MCPNativeStrategy()
        doc_tree = _make_doc_tree()
        strategy.setup("index", doc_tree)
        task = make_mock_task()
        prepared = strategy.prepare("index", task, doc_tree)
        # catalog_tokens should be tracked in strategy_metadata
        assert "catalog_tokens" in prepared.strategy_metadata
        assert prepared.strategy_metadata["catalog_tokens"] > 0
```

**Implementation note:** Add `catalog_tokens` to `MCPNativeStrategy.prepare()` in `mcp_native.py`:

```python
# In prepare(), add to strategy_metadata:
from agent_evals.llm.token_counter import count_tokens
catalog_summary = json.dumps(self._resource_catalog, indent=2)
# ...existing code...
return PreparedContext(
    messages=messages,
    tools=list(self._tool_definitions),
    strategy_metadata={
        "resource_count": len(self._resource_catalog),
        "catalog_tokens": count_tokens(catalog_summary),
    },
)
```

### Step 8: Commit

```bash
git add agent-evals/src/agent_evals/context/mcp_native.py \
  agent-evals/src/agent_evals/context/__init__.py \
  agent-evals/tests/test_context_mcp_native.py
git commit -m "feat(context): add MCP-native strategy with resource catalog

Models the MCP interaction pattern where docs are exposed as described
resources. Agent sees resource catalog upfront, selectively fetches
content via list_resources/read_resource/search_resources tools.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Compression Strategy (C2)

**Purpose:** Test whether compressed documentation maintains agent performance at lower cost. Three sub-strategies: LLM-summarized, algorithmic token pruning, format conversion.

**Files:**
- Create: `agent-evals/src/agent_evals/context/compression.py`
- Modify: `agent-evals/src/agent_evals/context/__init__.py`
- Modify: `agent-evals/src/agent_evals/context/base.py` (StrategyConfig)
- Create: `agent-evals/tests/test_context_compression.py`

### Step 1: Write failing tests

**Create** `agent-evals/tests/test_context_compression.py`:

```python
"""Tests for compression context strategy."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from agent_index.models import DocFile, DocTree


def _make_doc_tree() -> DocTree:
    return DocTree(
        files={
            "guides/auth.md": DocFile(
                rel_path="guides/auth.md",
                content="# Authentication\n\nUse OAuth2 for all API authentication. Tokens expire after 1 hour. Refresh tokens last 30 days.\n\n## Setup\nRegister your app at /settings/oauth.",
                size_bytes=150,
                token_count=40,
                tier="required",
                section="Guides",
            ),
        },
        scanned_at=datetime(2026, 1, 1),
        source="/test",
        total_tokens=40,
    )


class TestCompressionRegistration:
    def test_registered_by_name(self):
        from agent_evals.context.registry import get_strategy_by_name, load_all
        load_all()
        strategy = get_strategy_by_name("compression")
        assert strategy is not None
        assert strategy.name() == "compression"

    def test_cacheable(self):
        from agent_evals.context.compression import CompressionStrategy
        strategy = CompressionStrategy()
        assert strategy.supports_caching() is True


class TestAlgorithmicCompression:
    def test_reduces_token_count(self):
        from agent_evals.context.compression import CompressionStrategy
        strategy = CompressionStrategy(method="algorithmic")
        doc_tree = _make_doc_tree()
        rendered = "# Auth\n\nUse OAuth2 for all API authentication. " * 20
        strategy.setup(rendered, doc_tree)
        task = MagicMock()
        task.definition.question = "How to authenticate?"
        task.build_prompt.return_value = [
            {"role": "user", "content": "test"},
        ]
        prepared = strategy.prepare(rendered, task, doc_tree)
        metadata = prepared.strategy_metadata
        assert metadata["compressed_tokens"] < metadata["original_tokens"]
        assert metadata["compression_method"] == "algorithmic"

    def test_compression_ratio_in_metadata(self):
        from agent_evals.context.compression import CompressionStrategy
        strategy = CompressionStrategy(method="algorithmic")
        doc_tree = _make_doc_tree()
        rendered = "Some documentation content " * 50
        strategy.setup(rendered, doc_tree)
        task = MagicMock()
        task.definition.question = "What?"
        task.build_prompt.return_value = [{"role": "user", "content": "q"}]
        prepared = strategy.prepare(rendered, task, doc_tree)
        ratio = prepared.strategy_metadata["compression_ratio"]
        assert 0.0 < ratio <= 1.0


class TestLLMSummarizedCompression:
    def test_calls_llm_for_summary(self):
        from agent_evals.context.compression import CompressionStrategy
        strategy = CompressionStrategy(method="llm_summarized")
        doc_tree = _make_doc_tree()
        rendered = "# Detailed docs\n" * 100
        strategy.setup(rendered, doc_tree)
        task = MagicMock()
        task.definition.question = "What is auth?"
        task.build_prompt.return_value = [{"role": "user", "content": "q"}]

        # LLM summary client must be provided via setup or config
        assert strategy._method == "llm_summarized"


class TestFormatConversion:
    def test_markdown_to_compact(self):
        from agent_evals.context.compression import CompressionStrategy
        strategy = CompressionStrategy(method="format_conversion")
        doc_tree = _make_doc_tree()
        rendered = "# Header\n\n- item 1\n- item 2\n\n## Sub\n\nParagraph text."
        strategy.setup(rendered, doc_tree)
        task = MagicMock()
        task.definition.question = "List items"
        task.build_prompt.return_value = [{"role": "user", "content": "q"}]
        prepared = strategy.prepare(rendered, task, doc_tree)
        assert prepared.strategy_metadata["compression_method"] == "format_conversion"


class TestCompressionExecute:
    def test_single_turn_execution(self):
        from agent_evals.context.compression import CompressionStrategy
        from tests.conftest import make_mock_task
        strategy = CompressionStrategy(method="algorithmic")
        doc_tree = _make_doc_tree()
        rendered = "Documentation content here."
        strategy.setup(rendered, doc_tree)
        task = make_mock_task()
        prepared = strategy.prepare(rendered, task, doc_tree)

        client = MagicMock()
        gen = MagicMock()
        gen.content = "The answer."
        gen.prompt_tokens = 20
        gen.completion_tokens = 5
        gen.total_tokens = 25
        gen.cost = 0.001
        client.complete.return_value = gen

        result = strategy.execute(prepared, task, client, 1024, 0.0)
        assert result.final_response == "The answer."
        assert "compression_ratio" in result.strategy_metadata
```

### Step 2: Run tests to verify they fail

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_context_compression.py -v
```

Expected: FAIL — module does not exist.

### Step 3: Implement CompressionStrategy

**Create** `agent-evals/src/agent_evals/context/compression.py`:

```python
"""Compression context strategy -- reduces docs before injection.

Three compression methods:
- algorithmic: Remove stopwords, redundant whitespace, low-info lines.
- llm_summarized: Use a cheap LLM to summarize before injection.
- format_conversion: Convert markdown to compact key-value format.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from agent_evals.context.base import ContextStrategy, PreparedContext, StrategyResult
from agent_evals.context.registry import register_strategy
from agent_evals.llm.token_counter import count_tokens

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.llm.client import LLMClient
    from agent_evals.tasks.base import EvalTask

_STOPWORD_RE = re.compile(
    r"\b(the|a|an|is|are|was|were|be|been|being|have|has|had|"
    r"do|does|did|will|would|could|should|may|might|must|shall|"
    r"can|need|dare|ought|used|to|of|in|for|on|with|at|by|from|"
    r"that|this|these|those|it|its)\b",
    re.IGNORECASE,
)
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def _algorithmic_compress(text: str) -> str:
    """Remove stopwords, collapse whitespace, strip empty lines."""
    compressed = _STOPWORD_RE.sub("", text)
    compressed = _MULTI_SPACE_RE.sub(" ", compressed)
    compressed = _MULTI_NEWLINE_RE.sub("\n\n", compressed)
    lines = [line.strip() for line in compressed.splitlines()]
    return "\n".join(line for line in lines if line)


def _format_convert(text: str) -> str:
    """Convert markdown to compact key-value format."""
    lines = text.splitlines()
    output: list[str] = []
    current_section = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            current_section = stripped.lstrip("#").strip()
            output.append(f"[{current_section}]")
        elif stripped.startswith("- "):
            output.append(f"  * {stripped[2:]}")
        elif stripped:
            output.append(f"  {stripped}")
    return "\n".join(output)


@register_strategy
class CompressionStrategy(ContextStrategy):
    """Compresses rendered index before injection into prompt."""

    def __init__(self, method: str = "algorithmic") -> None:
        self._method = method
        self._rendered_index: str = ""

    def name(self) -> str:
        return "compression"

    def supports_caching(self) -> bool:
        return True

    def setup(self, rendered_index: str, doc_tree: DocTree) -> None:
        self._rendered_index = rendered_index

    def prepare(
        self, rendered_index: str, task: EvalTask, doc_tree: DocTree,
    ) -> PreparedContext:
        original_tokens = count_tokens(rendered_index)
        compressed = self._compress(rendered_index)
        compressed_tokens = count_tokens(compressed)
        ratio = compressed_tokens / original_tokens if original_tokens > 0 else 1.0

        messages = task.build_prompt(compressed)
        return PreparedContext(
            messages=messages,
            tools=None,
            strategy_metadata={
                "compression_method": self._method,
                "original_tokens": original_tokens,
                "compressed_tokens": compressed_tokens,
                "compression_ratio": round(ratio, 4),
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
        generation = client.complete(
            prepared.messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return StrategyResult(
            final_response=generation.content,
            generations=[generation],
            total_prompt_tokens=generation.prompt_tokens,
            total_completion_tokens=generation.completion_tokens,
            total_tokens=generation.total_tokens,
            total_cost=generation.cost,
            messages=prepared.messages,
            strategy_metadata=prepared.strategy_metadata,
        )

    def _compress(self, text: str) -> str:
        if self._method == "algorithmic":
            return _algorithmic_compress(text)
        if self._method == "format_conversion":
            return _format_convert(text)
        if self._method == "llm_summarized":
            # LLM summarization requires a client — defer to execute phase
            # For prepare(), return algorithmic as fallback
            return _algorithmic_compress(text)
        return text
```

### Step 4: Complete LLM-summarized compression

The current `_compress()` method falls back to algorithmic compression for `llm_summarized`. Complete the implementation.

**Add to tests** in `agent-evals/tests/test_context_compression.py`:

```python
class TestLLMSummarizedCompressionComplete:
    def test_llm_summarized_calls_model(self):
        """LLM-summarized compression should call a cheap model."""
        from agent_evals.context.compression import CompressionStrategy
        strategy = CompressionStrategy(
            method="llm_summarized",
            summary_model="openrouter/openai/gpt-4o-mini",
        )
        assert strategy._summary_model == "openrouter/openai/gpt-4o-mini"

    def test_llm_summarized_reduces_tokens(self):
        """LLM-summarized compression should reduce token count via model call."""
        from agent_evals.context.compression import CompressionStrategy
        from unittest.mock import MagicMock

        strategy = CompressionStrategy(
            method="llm_summarized",
            summary_model="openrouter/openai/gpt-4o-mini",
        )
        doc_tree = _make_doc_tree()
        rendered = "# Detailed documentation\n" * 100
        strategy.setup(rendered, doc_tree)

        # Mock the LLM summarization client
        mock_client = MagicMock()
        mock_gen = MagicMock()
        mock_gen.content = "Condensed summary of documentation."
        mock_client.complete.return_value = mock_gen

        result = strategy._llm_summarize(rendered, mock_client)
        mock_client.complete.assert_called_once()
        assert len(result) < len(rendered)

    def test_execute_calls_llm_summarize_when_client_available(self):
        """execute() should perform LLM summarization when method=llm_summarized."""
        from agent_evals.context.compression import CompressionStrategy
        from tests.conftest import make_mock_task
        from unittest.mock import MagicMock, patch

        strategy = CompressionStrategy(method="llm_summarized")
        doc_tree = _make_doc_tree()
        rendered = "Long documentation content. " * 50
        strategy.setup(rendered, doc_tree)
        task = make_mock_task()
        prepared = strategy.prepare(rendered, task, doc_tree)

        client = MagicMock()
        # First call: LLM summarization; second call: task completion
        summary_gen = MagicMock()
        summary_gen.content = "Compressed doc summary."
        task_gen = MagicMock()
        task_gen.content = "The answer."
        task_gen.prompt_tokens = 20
        task_gen.completion_tokens = 5
        task_gen.total_tokens = 25
        task_gen.cost = 0.001
        client.complete.side_effect = [summary_gen, task_gen]

        result = strategy.execute(prepared, task, client, 1024, 0.0)
        assert result.final_response == "The answer."
```

**Modify** `agent-evals/src/agent_evals/context/compression.py`:

1. Add `summary_model` parameter to constructor:

```python
def __init__(self, method: str = "algorithmic", summary_model: str = "openrouter/openai/gpt-4o-mini") -> None:
    self._method = method
    self._summary_model = summary_model
    self._rendered_index: str = ""
```

2. Add `_llm_summarize()` method:

```python
def _llm_summarize(self, text: str, client: LLMClient) -> str:
    """Call a cheap LLM to compress documentation text."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a documentation compressor. Condense the following "
                "documentation into the most information-dense format possible. "
                "Preserve all technical facts, API names, and configuration values. "
                "Remove redundancy, verbose explanations, and filler text."
            ),
        },
        {"role": "user", "content": text},
    ]
    generation = client.complete(
        messages, max_tokens=len(text) // 2, temperature=0.0,
    )
    return generation.content or text
```

3. Update `execute()` to call LLM summarization when `method="llm_summarized"`:

```python
def execute(
    self,
    prepared: PreparedContext,
    task: EvalTask,
    client: LLMClient,
    max_tokens: int,
    temperature: float,
) -> StrategyResult:
    # If llm_summarized, re-compress via LLM before final completion
    messages = list(prepared.messages)
    if self._method == "llm_summarized" and client is not None:
        # Find and replace the doc content in messages with LLM summary
        for i, msg in enumerate(messages):
            if msg["role"] == "system" and len(msg["content"]) > 200:
                messages[i] = dict(msg)
                messages[i]["content"] = self._llm_summarize(
                    msg["content"], client,
                )
                break

    generation = client.complete(
        messages, max_tokens=max_tokens, temperature=temperature,
    )
    return StrategyResult(
        final_response=generation.content,
        generations=[generation],
        total_prompt_tokens=generation.prompt_tokens,
        total_completion_tokens=generation.completion_tokens,
        total_tokens=generation.total_tokens,
        total_cost=generation.cost,
        messages=messages,
        strategy_metadata=prepared.strategy_metadata,
    )
```

4. Add `_summary_client` field and `set_summary_client()` method for runner wiring:

```python
# Add field to CompressionStrategy.__init__:
self._summary_client: LLMClient | None = None

def set_summary_client(self, client: LLMClient) -> None:
    """Set the LLM client used for llm_summarized compression.

    Called by the runner before trials begin so that execute()
    can perform LLM-based summarization.
    """
    self._summary_client = client
```

> **Implementation note — two-phase approach for LLM-summarized compression:**
>
> The `llm_summarized` method uses a two-phase approach:
> 1. **`prepare()` phase (algorithmic fallback):** Since `prepare()` has no client access,
>    it applies algorithmic compression as a fallback. This produces a valid PreparedContext
>    with reduced tokens, ensuring the pipeline works even if LLM summarization fails.
> 2. **`execute()` phase (LLM replacement):** When `execute()` runs, it detects
>    `method="llm_summarized"`, calls `_llm_summarize()` on the already-compressed content,
>    rebuilds the messages with the LLM-compressed version, then calls the main LLM for
>    the actual task. This means the final prompt contains LLM-quality compression rather
>    than the algorithmic approximation.
>
> The `_summary_client` can be set via `set_summary_client()` (called by runner before trials)
> or `execute()` falls back to using the main trial client. This separation allows using a
> cheaper model (e.g., gpt-4o-mini) for summarization while using the evaluation model for
> the actual task.

5. Add test for execute replacing content with LLM summary:

**Append to** `agent-evals/tests/test_context_compression.py`:

```python
class TestExecuteReplacesContentWithLLMSummary:
    def test_execute_replaces_content_with_llm_summary(self):
        """execute() should replace algorithmically compressed content with
        LLM-summarized content when method=llm_summarized."""
        from agent_evals.context.compression import CompressionStrategy
        from tests.conftest import make_mock_task
        from unittest.mock import MagicMock

        strategy = CompressionStrategy(method="llm_summarized")
        doc_tree = _make_doc_tree()
        rendered = "Long documentation content. " * 50
        strategy.setup(rendered, doc_tree)
        task = make_mock_task()
        # prepare() uses algorithmic fallback
        prepared = strategy.prepare(rendered, task, doc_tree)
        algorithmic_content = prepared.messages[0]["content"]

        # Set summary client
        summary_client = MagicMock()
        summary_gen = MagicMock()
        summary_gen.content = "LLM-compressed documentation summary."
        summary_client.complete.return_value = summary_gen
        strategy.set_summary_client(summary_client)

        # Main client for task completion
        client = MagicMock()
        task_gen = MagicMock()
        task_gen.content = "The answer based on LLM summary."
        task_gen.prompt_tokens = 20
        task_gen.completion_tokens = 5
        task_gen.total_tokens = 25
        task_gen.cost = 0.001
        client.complete.return_value = task_gen

        result = strategy.execute(prepared, task, client, 1024, 0.0)
        # Summary client should have been called with the algorithmic content
        summary_client.complete.assert_called_once()
        # Final result uses main client's response
        assert result.final_response == "The answer based on LLM summary."
```

### Step 5: Extend StrategyConfig

**Add to** `agent-evals/src/agent_evals/context/base.py` StrategyConfig:

```python
compression_method: str = "algorithmic"  # algorithmic, llm_summarized, format_conversion
```

### Step 5: Update `__init__.py`

**Add** to `agent-evals/src/agent_evals/context/__init__.py`:

```python
from agent_evals.context.compression import CompressionStrategy

# Add to __all__:
"CompressionStrategy",
```

### Step 6: Run tests

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_context_compression.py -v
```

Expected: ALL PASS

### Step 7: Run full suite and commit

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -v --tb=short 2>&1 | tail -10
git add agent-evals/src/agent_evals/context/compression.py \
  agent-evals/src/agent_evals/context/__init__.py \
  agent-evals/src/agent_evals/context/base.py \
  agent-evals/tests/test_context_compression.py
git commit -m "feat(context): add compression strategy with 3 methods

Algorithmic (stopword removal, whitespace collapse), format conversion
(markdown to compact KV), and LLM-summarized (deferred to execute).
Measures compression-accuracy tradeoff directly.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

### Step 9: Add compression+cost pairing report

**Purpose:** Show how compression strategy results pair with Phase B cost metrics so users can see the cost-accuracy tradeoff at a glance.

**Add test** to `agent-evals/tests/test_context_compression.py`:

```python
class TestCompressionTradeoffTable:
    def test_compression_tradeoff_table(self):
        """render_compression_tradeoff_table produces a formatted table."""
        from agent_evals.context.compression import render_compression_tradeoff_table
        trials = [
            {
                "variant_name": "algorithmic",
                "compression_ratio": 0.6,
                "accuracy": 0.85,
                "cost": 0.003,
                "baseline_cost": 0.005,
            },
            {
                "variant_name": "format_conversion",
                "compression_ratio": 0.7,
                "accuracy": 0.82,
                "cost": 0.0035,
                "baseline_cost": 0.005,
            },
            {
                "variant_name": "llm_summarized",
                "compression_ratio": 0.4,
                "accuracy": 0.78,
                "cost": 0.004,
                "baseline_cost": 0.005,
            },
        ]
        table = render_compression_tradeoff_table(trials)
        assert "VARIANT" in table
        assert "COMPRESSION_RATIO" in table
        assert "ACCURACY" in table
        assert "COST_SAVINGS" in table
        assert "NET_BENEFIT" in table
        assert "algorithmic" in table
        assert "format_conversion" in table
        assert "llm_summarized" in table


class TestStructuredVsProseCompaction:
    """Compare structured (KV-format) compaction against prose (LLM-summarized)
    compaction to validate the hypothesis that structured output is shorter
    while both preserve key information.

    This sets up the comparison so results could feed into a paired hypothesis
    test (e.g., Wilcoxon signed-rank) across multiple documentation inputs.
    """

    def _make_multi_doc_tree(self) -> DocTree:
        """Build a doc tree with multiple files to produce meaningful samples."""
        files = {}
        docs = [
            ("guides/auth.md", "# Authentication\n\nUse OAuth2 for all API authentication. Tokens expire after 1 hour. Refresh tokens last 30 days.\n\n## Setup\nRegister your app at /settings/oauth."),
            ("guides/rate-limits.md", "# Rate Limits\n\nDefault rate limit is 100 requests per minute per API key. Enterprise plans get 1000 requests per minute.\n\n## Headers\nCheck X-RateLimit-Remaining header for current quota."),
            ("api/users.md", "# Users API\n\nGET /users returns a paginated list of users. POST /users creates a new user.\n\n## Parameters\n- page: int (default 1)\n- per_page: int (default 20, max 100)"),
            ("api/projects.md", "# Projects API\n\nGET /projects lists projects. POST /projects creates a project.\n\n## Fields\n- name: string (required)\n- description: string (optional)\n- visibility: enum (public, private)"),
            ("reference/errors.md", "# Error Codes\n\n- 400: Bad Request - malformed input\n- 401: Unauthorized - missing or invalid token\n- 403: Forbidden - insufficient permissions\n- 404: Not Found - resource does not exist\n- 429: Too Many Requests - rate limit exceeded"),
        ]
        for rel_path, content in docs:
            files[rel_path] = DocFile(
                rel_path=rel_path,
                content=content,
                size_bytes=len(content),
                token_count=len(content) // 4,
                tier="required",
                section=rel_path.split("/")[0].title(),
            )
        return DocTree(
            files=files,
            scanned_at=datetime(2026, 1, 1),
            source="/test",
            total_tokens=sum(f.token_count for f in files.values()),
        )

    def test_both_produce_valid_output(self):
        """Both structured and prose compaction must produce non-empty strings."""
        from agent_evals.context.compression import (
            _algorithmic_compress,
            _format_convert,
        )

        doc_tree = self._make_multi_doc_tree()
        for doc in doc_tree.files.values():
            structured = _format_convert(doc.content)
            prose = _algorithmic_compress(doc.content)
            assert isinstance(structured, str) and len(structured) > 0, (
                f"Structured output empty for {doc.rel_path}"
            )
            assert isinstance(prose, str) and len(prose) > 0, (
                f"Prose output empty for {doc.rel_path}"
            )

    def test_structured_shorter_than_prose(self):
        """Structured (KV-format) output should use fewer tokens than
        algorithmic (prose-like) output because KV strips markdown
        formatting overhead more aggressively.
        """
        from agent_evals.context.compression import (
            _algorithmic_compress,
            _format_convert,
        )
        from agent_evals.llm.token_counter import count_tokens

        doc_tree = self._make_multi_doc_tree()
        structured_shorter_count = 0
        total_docs = len(doc_tree.files)

        for doc in doc_tree.files.values():
            structured = _format_convert(doc.content)
            prose = _algorithmic_compress(doc.content)
            structured_tokens = count_tokens(structured)
            prose_tokens = count_tokens(prose)
            if structured_tokens < prose_tokens:
                structured_shorter_count += 1

        # Structured should be shorter for the majority of docs
        assert structured_shorter_count > total_docs / 2, (
            f"Structured was shorter in only {structured_shorter_count}/{total_docs} docs; "
            f"expected majority"
        )

    def test_both_preserve_key_information(self):
        """Both compaction methods must preserve critical technical terms
        from the original documentation (API names, config values, error codes).
        """
        from agent_evals.context.compression import (
            _algorithmic_compress,
            _format_convert,
        )

        doc_tree = self._make_multi_doc_tree()
        # Critical terms that must survive compression
        critical_terms_by_doc = {
            "guides/auth.md": ["OAuth2", "1 hour", "30 days", "/settings/oauth"],
            "guides/rate-limits.md": ["100", "1000", "X-RateLimit-Remaining"],
            "api/users.md": ["/users", "GET", "POST", "per_page"],
            "api/projects.md": ["/projects", "visibility", "public", "private"],
            "reference/errors.md": ["400", "401", "403", "404", "429"],
        }

        for rel_path, terms in critical_terms_by_doc.items():
            doc = doc_tree.files[rel_path]
            structured = _format_convert(doc.content)
            prose = _algorithmic_compress(doc.content)

            for term in terms:
                assert term in structured, (
                    f"Structured output for {rel_path} missing critical term: {term}"
                )
                assert term in prose, (
                    f"Prose output for {rel_path} missing critical term: {term}"
                )

    def test_paired_differences_suitable_for_hypothesis_test(self):
        """Collect paired (structured_tokens, prose_tokens) for each doc
        and verify the data is suitable for a paired statistical test.

        Requirements for a valid paired test:
        1. Same number of observations per group (paired by document).
        2. Non-zero differences exist (the methods are not identical).
        3. At least 5 pairs for minimum statistical power.
        """
        from agent_evals.context.compression import (
            _algorithmic_compress,
            _format_convert,
        )
        from agent_evals.llm.token_counter import count_tokens

        doc_tree = self._make_multi_doc_tree()
        structured_counts: list[int] = []
        prose_counts: list[int] = []

        for doc in doc_tree.files.values():
            structured_counts.append(count_tokens(_format_convert(doc.content)))
            prose_counts.append(count_tokens(_algorithmic_compress(doc.content)))

        # Requirement 1: equal sample sizes (paired)
        assert len(structured_counts) == len(prose_counts)

        # Requirement 2: non-zero differences (methods are not identical)
        differences = [s - p for s, p in zip(structured_counts, prose_counts)]
        assert any(d != 0 for d in differences), (
            "All differences are zero — methods produce identical token counts, "
            "no hypothesis test possible"
        )

        # Requirement 3: minimum sample size for paired test
        assert len(differences) >= 5, (
            f"Only {len(differences)} pairs; need at least 5 for minimum statistical power"
        )

        # Verify the direction is consistent (structured typically shorter)
        negative_diffs = sum(1 for d in differences if d < 0)
        assert negative_diffs > 0 or sum(1 for d in differences if d > 0) > 0, (
            "Need variation in differences to run a meaningful test"
        )
```

**Add function** to `agent-evals/src/agent_evals/context/compression.py`:

```python
def render_compression_tradeoff_table(trials: list[dict]) -> str:
    """Render a table pairing compression results with Phase B cost metrics.

    Each trial dict should contain:
    - variant_name: str
    - compression_ratio: float (0-1, lower = more compressed)
    - accuracy: float (0-1)
    - cost: float (actual cost)
    - baseline_cost: float (uncompressed cost)

    Returns a formatted table:
    VARIANT | COMPRESSION_RATIO | ACCURACY | COST_SAVINGS | NET_BENEFIT
    """
    header = f"{'VARIANT':<25} {'COMPRESSION_RATIO':>18} {'ACCURACY':>10} {'COST_SAVINGS':>13} {'NET_BENEFIT':>12}"
    separator = "-" * len(header)
    rows = [header, separator]

    for trial in trials:
        variant = trial.get("variant_name", "unknown")
        ratio = trial.get("compression_ratio", 1.0)
        accuracy = trial.get("accuracy", 0.0)
        cost = trial.get("cost", 0.0)
        baseline_cost = trial.get("baseline_cost", cost)
        cost_savings = (baseline_cost - cost) / baseline_cost if baseline_cost > 0 else 0.0
        # Net benefit: accuracy * cost_savings (higher = better tradeoff)
        net_benefit = accuracy * cost_savings

        rows.append(
            f"{variant:<25} {ratio:>18.4f} {accuracy:>10.4f} "
            f"{cost_savings:>13.4f} {net_benefit:>12.4f}"
        )

    return "\n".join(rows)
```

---

## Task 4: Tool Description Axis (C3) — Axis 11

**Purpose:** Test how tool description quality and tool set size affect agent performance. Anthropic achieved SOTA on SWE-bench primarily through refined tool descriptions. This axis is a 2-factor axis covering both description quality (4 variants) and tool set size (4 variants), giving 8 total variants on axis 11.

**Files:**
- Create: `agent-evals/src/agent_evals/variants/tool_description.py`
- Create: `agent-evals/tests/test_axis_11_tool_description.py`

### Step 1: Write failing tests

**Create** `agent-evals/tests/test_axis_11_tool_description.py`:

```python
"""Tests for axis 11: tool description variants."""

from __future__ import annotations

from datetime import datetime

import pytest

from agent_index.models import DocFile, DocTree
from agent_evals.variants.base import VariantMetadata


def _make_doc_tree() -> DocTree:
    return DocTree(
        files={
            "guides/auth.md": DocFile(
                rel_path="guides/auth.md",
                content="# Auth\nUse OAuth2.",
                size_bytes=20,
                token_count=6,
                tier="required",
                section="Guides",
                summary="Auth guide",
                related=["api/users.md"],
            ),
            "api/users.md": DocFile(
                rel_path="api/users.md",
                content="# Users\nGET /users.",
                size_bytes=20,
                token_count=5,
                tier="recommended",
                section="API",
                summary="Users API",
                related=[],
            ),
        },
        scanned_at=datetime(2026, 1, 1),
        source="/test",
        total_tokens=11,
    )


class TestToolDescMinimalMetadata:
    def test_axis_is_11(self):
        from agent_evals.variants.tool_description import ToolDescMinimal
        v = ToolDescMinimal()
        assert v.metadata().axis == 11

    def test_category(self):
        from agent_evals.variants.tool_description import ToolDescMinimal
        v = ToolDescMinimal()
        assert v.metadata().category == "tool_description"


class TestToolDescStandardMetadata:
    def test_axis_is_11(self):
        from agent_evals.variants.tool_description import ToolDescStandard
        v = ToolDescStandard()
        assert v.metadata().axis == 11


class TestToolDescDetailedMetadata:
    def test_axis_is_11(self):
        from agent_evals.variants.tool_description import ToolDescDetailed
        v = ToolDescDetailed()
        assert v.metadata().axis == 11


class TestToolDescAdversarialMetadata:
    def test_axis_is_11(self):
        from agent_evals.variants.tool_description import ToolDescAdversarial
        v = ToolDescAdversarial()
        assert v.metadata().axis == 11


class TestToolDescMinimalRender:
    def test_minimal_has_name_and_types_only(self):
        from agent_evals.variants.tool_description import ToolDescMinimal
        v = ToolDescMinimal()
        result = v.render(_make_doc_tree())
        assert "list_docs" in result
        assert "read_doc" in result
        assert "search_docs" in result
        # Minimal: no multi-line descriptions
        for line in result.splitlines():
            assert len(line) < 200  # No long descriptions

    def test_empty_tree(self):
        from agent_evals.variants.tool_description import ToolDescMinimal
        v = ToolDescMinimal()
        tree = DocTree(files={}, scanned_at=datetime(2026, 1, 1), source="/t", total_tokens=0)
        result = v.render(tree)
        assert isinstance(result, str)


class TestToolDescDetailedRender:
    def test_detailed_has_examples(self):
        from agent_evals.variants.tool_description import ToolDescDetailed
        v = ToolDescDetailed()
        result = v.render(_make_doc_tree())
        assert "example" in result.lower() or "usage" in result.lower()

    def test_detailed_longer_than_minimal(self):
        from agent_evals.variants.tool_description import (
            ToolDescDetailed,
            ToolDescMinimal,
        )
        tree = _make_doc_tree()
        minimal = ToolDescMinimal().render(tree)
        detailed = ToolDescDetailed().render(tree)
        assert len(detailed) > len(minimal)


class TestToolSetCore3:
    def test_tool_set_core3_has_3_tools(self):
        from agent_evals.variants.tool_description import ToolSetCore3
        v = ToolSetCore3()
        result = v.render(_make_doc_tree())
        # Core 3: list_docs, read_doc, search_docs
        assert "list_docs" in result
        assert "read_doc" in result
        assert "search_docs" in result
        # Should NOT have extended tools
        assert "get_metadata" not in result
        assert "list_sections" not in result

    def test_axis_is_11(self):
        from agent_evals.variants.tool_description import ToolSetCore3
        v = ToolSetCore3()
        assert v.metadata().axis == 11
        assert v.metadata().category == "tool_description"


class TestToolSetExtended5:
    def test_tool_set_extended5_has_5_tools(self):
        from agent_evals.variants.tool_description import ToolSetExtended5
        v = ToolSetExtended5()
        result = v.render(_make_doc_tree())
        # Core 3 + get_metadata + list_sections
        assert "list_docs" in result
        assert "read_doc" in result
        assert "search_docs" in result
        assert "get_metadata" in result
        assert "list_sections" in result

    def test_axis_is_11(self):
        from agent_evals.variants.tool_description import ToolSetExtended5
        v = ToolSetExtended5()
        assert v.metadata().axis == 11


class TestToolSetExtended7:
    def test_tool_set_extended7_has_7_tools(self):
        from agent_evals.variants.tool_description import ToolSetExtended7
        v = ToolSetExtended7()
        result = v.render(_make_doc_tree())
        # Core 3 + get_metadata + list_sections + search_by_section + get_related
        assert "list_docs" in result
        assert "read_doc" in result
        assert "search_docs" in result
        assert "get_metadata" in result
        assert "list_sections" in result
        assert "search_by_section" in result
        assert "get_related" in result

    def test_axis_is_11(self):
        from agent_evals.variants.tool_description import ToolSetExtended7
        v = ToolSetExtended7()
        assert v.metadata().axis == 11


class TestToolSetKitchenSink:
    def test_tool_set_kitchen_sink_has_10_plus_tools(self):
        from agent_evals.variants.tool_description import ToolSetKitchenSink
        v = ToolSetKitchenSink()
        result = v.render(_make_doc_tree())
        # 10+ tools including overlapping/redundant ones
        tool_count = sum(
            1 for line in result.splitlines()
            if line.startswith("## ") and not line.startswith("## Documentation")
        )
        assert tool_count >= 10

    def test_axis_is_11(self):
        from agent_evals.variants.tool_description import ToolSetKitchenSink
        v = ToolSetKitchenSink()
        assert v.metadata().axis == 11


class TestToolDescRegistration:
    def test_all_variants_discoverable(self):
        from agent_evals.variants.registry import get_variants_for_axis, load_all
        load_all()
        axis_11 = get_variants_for_axis(11)
        assert len(axis_11) >= 8  # 4 description quality + 4 tool set size
        names = {v.metadata().name for v in axis_11}
        assert "tool-desc-minimal" in names
        assert "tool-desc-standard" in names
        assert "tool-desc-detailed" in names
        assert "tool-desc-adversarial" in names
        assert "tool-set-core3" in names
        assert "tool-set-extended5" in names
        assert "tool-set-extended7" in names
        assert "tool-set-kitchen-sink" in names


class TestToolSetSizePromptLength:
    """Verify that prompt token counts increase monotonically with tool set size.

    This validates tool set size as a meaningful experimental factor by
    confirming that adding more tool definitions measurably increases the
    prompt length seen by the model.
    """

    def test_token_counts_increase_monotonically(self):
        """Token counts must follow: core3 < extended5 < extended7 < kitchen_sink."""
        from agent_evals.variants.tool_description import (
            ToolSetCore3,
            ToolSetExtended5,
            ToolSetExtended7,
            ToolSetKitchenSink,
        )
        from agent_evals.llm.token_counter import count_tokens

        tree = _make_doc_tree()
        core3_tokens = count_tokens(ToolSetCore3().render(tree))
        ext5_tokens = count_tokens(ToolSetExtended5().render(tree))
        ext7_tokens = count_tokens(ToolSetExtended7().render(tree))
        ks_tokens = count_tokens(ToolSetKitchenSink().render(tree))

        assert core3_tokens < ext5_tokens, (
            f"core3 ({core3_tokens}) should have fewer tokens than extended5 ({ext5_tokens})"
        )
        assert ext5_tokens < ext7_tokens, (
            f"extended5 ({ext5_tokens}) should have fewer tokens than extended7 ({ext7_tokens})"
        )
        assert ext7_tokens < ks_tokens, (
            f"extended7 ({ext7_tokens}) should have fewer tokens than kitchen_sink ({ks_tokens})"
        )

    def test_kitchen_sink_measurably_larger_than_core(self):
        """Kitchen sink variant must have at least 2x the tokens of core3.

        A 2x threshold ensures tool set size is a non-trivial factor,
        not just a few extra tokens of noise.
        """
        from agent_evals.variants.tool_description import (
            ToolSetCore3,
            ToolSetKitchenSink,
        )
        from agent_evals.llm.token_counter import count_tokens

        tree = _make_doc_tree()
        core3_tokens = count_tokens(ToolSetCore3().render(tree))
        ks_tokens = count_tokens(ToolSetKitchenSink().render(tree))

        assert ks_tokens >= 2 * core3_tokens, (
            f"kitchen_sink ({ks_tokens}) should be at least 2x core3 ({core3_tokens}) "
            f"to ensure tool set size is a meaningful experimental factor"
        )

    def test_each_size_level_adds_unique_tool_names(self):
        """Each tool set size level should contain strictly more tool names
        than the previous level, confirming the size increase comes from
        additional tools, not just longer descriptions of the same tools.
        """
        from agent_evals.variants.tool_description import (
            ToolSetCore3,
            ToolSetExtended5,
            ToolSetExtended7,
            ToolSetKitchenSink,
        )

        tree = _make_doc_tree()

        def _extract_tool_names(rendered: str) -> set[str]:
            names = set()
            for line in rendered.splitlines():
                if line.startswith("## ") and not line.startswith("## Documentation"):
                    names.add(line[3:].strip())
            return names

        core3_names = _extract_tool_names(ToolSetCore3().render(tree))
        ext5_names = _extract_tool_names(ToolSetExtended5().render(tree))
        ext7_names = _extract_tool_names(ToolSetExtended7().render(tree))
        ks_names = _extract_tool_names(ToolSetKitchenSink().render(tree))

        assert core3_names < ext5_names, "extended5 must be a strict superset of core3"
        assert ext5_names < ext7_names, "extended7 must be a strict superset of extended5"
        assert ext7_names < ks_names, "kitchen_sink must be a strict superset of extended7"

    def test_prompt_length_data_suitable_for_hypothesis_test(self):
        """Render each variant multiple times and collect token counts to verify
        they are deterministic (zero variance within a level). This confirms the
        prompt length differences are structural, not random, making them suitable
        for statistical comparison as a Taguchi factor.
        """
        from agent_evals.variants.tool_description import (
            ToolSetCore3,
            ToolSetExtended5,
            ToolSetExtended7,
            ToolSetKitchenSink,
        )
        from agent_evals.llm.token_counter import count_tokens

        tree = _make_doc_tree()
        variants = [ToolSetCore3(), ToolSetExtended5(), ToolSetExtended7(), ToolSetKitchenSink()]
        token_counts: list[list[int]] = []

        for variant in variants:
            counts = [count_tokens(variant.render(tree)) for _ in range(5)]
            token_counts.append(counts)
            # Each variant should produce deterministic token counts
            assert len(set(counts)) == 1, (
                f"Variant {variant.metadata().name} produced non-deterministic "
                f"token counts: {counts}"
            )

        # All 4 levels should produce distinct token counts
        level_means = [counts[0] for counts in token_counts]
        assert len(set(level_means)) == 4, (
            f"Expected 4 distinct token count levels, got {len(set(level_means))}: {level_means}"
        )
```

### Step 2: Run tests to verify they fail

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_axis_11_tool_description.py -v
```

Expected: FAIL — module does not exist.

### Step 3: Implement tool description variants

**Create** `agent-evals/src/agent_evals/variants/tool_description.py`:

```python
"""Axis 11: Tool description quality and tool set size variants.

Two sub-dimensions on axis 11:
- Description quality: minimal (name+types), standard (one-line),
  detailed (examples+edge cases), adversarial (vague/misleading).
- Tool set size: core3 (list/read/search), extended5 (+metadata/sections),
  extended7 (+search_by_section/get_related), kitchen_sink (10+ with redundant).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree

_CORE_TOOLS = ["list_docs", "read_doc", "search_docs"]


def _render_tool_block(
    tools: list[dict], doc_tree: DocTree,
) -> str:
    """Render tool definitions + file index as combined output."""
    parts = ["# Tool Definitions\n"]
    for tool in tools:
        parts.append(f"## {tool['name']}")
        if tool.get("description"):
            parts.append(tool["description"])
        if tool.get("parameters"):
            parts.append(f"Parameters: {json.dumps(tool['parameters'])}")
        parts.append("")

    parts.append("# Documentation Index\n")
    for rel_path in sorted(doc_tree.files):
        doc = doc_tree.files[rel_path]
        parts.append(f"- {rel_path}: {doc.summary or 'N/A'}")

    return "\n".join(parts)


@register_variant
class ToolDescMinimal(IndexVariant):
    """Minimal tool descriptions: function name + parameter types only."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="tool-desc-minimal",
            axis=11,
            category="tool_description",
            description="Minimal tool descriptions with name and types only.",
            token_estimate=100,
        )

    def render(self, doc_tree: DocTree) -> str:
        tools = [
            {"name": "list_docs", "description": "", "parameters": "() -> str"},
            {"name": "read_doc", "description": "", "parameters": "(path: str) -> str"},
            {"name": "search_docs", "description": "", "parameters": "(query: str) -> str"},
        ]
        return _render_tool_block(tools, doc_tree)


@register_variant
class ToolDescStandard(IndexVariant):
    """Standard tool descriptions: one-line description + parameter docs."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="tool-desc-standard",
            axis=11,
            category="tool_description",
            description="Standard one-line descriptions with parameter docs.",
            token_estimate=200,
        )

    def render(self, doc_tree: DocTree) -> str:
        tools = [
            {
                "name": "list_docs",
                "description": "List all available documentation files.",
                "parameters": "() -> str: Returns newline-separated file paths.",
            },
            {
                "name": "read_doc",
                "description": "Read a documentation file by path.",
                "parameters": "(path: str) -> str: File content or error message.",
            },
            {
                "name": "search_docs",
                "description": "Search documentation for a query string.",
                "parameters": "(query: str) -> str: Matching snippets.",
            },
        ]
        return _render_tool_block(tools, doc_tree)


@register_variant
class ToolDescDetailed(IndexVariant):
    """Detailed tool descriptions with usage examples and edge cases."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="tool-desc-detailed",
            axis=11,
            category="tool_description",
            description="Detailed descriptions with examples and edge cases.",
            token_estimate=500,
        )

    def render(self, doc_tree: DocTree) -> str:
        tools = [
            {
                "name": "list_docs",
                "description": (
                    "List all available documentation files with their index "
                    "entries. Returns the full rendered index showing file "
                    "paths, summaries, tiers, and sections.\n\n"
                    "Usage example: Call list_docs() first to see what "
                    "documentation is available before reading specific files.\n\n"
                    "Edge cases: Returns empty string if no documentation "
                    "files exist."
                ),
                "parameters": "() -> str",
            },
            {
                "name": "read_doc",
                "description": (
                    "Read the full content of a documentation file by its "
                    "relative path. Returns the raw markdown content.\n\n"
                    "Usage example: read_doc('guides/auth.md') returns the "
                    "authentication guide content.\n\n"
                    "Edge cases: Returns an error message if the path does "
                    "not exist. Paths are relative to the documentation root. "
                    "Use list_docs() to discover valid paths."
                ),
                "parameters": "(path: str) -> str",
            },
            {
                "name": "search_docs",
                "description": (
                    "Search across all documentation files for content "
                    "matching a query string. Returns matching snippets with "
                    "file paths.\n\n"
                    "Usage example: search_docs('OAuth2') finds all files "
                    "mentioning OAuth2.\n\n"
                    "Edge cases: Case-insensitive substring match. Returns "
                    "'No results.' if nothing matches. Prefer specific terms "
                    "over generic ones for better results."
                ),
                "parameters": "(query: str) -> str",
            },
        ]
        return _render_tool_block(tools, doc_tree)


@register_variant
class ToolDescAdversarial(IndexVariant):
    """Adversarial tool descriptions: deliberately vague or misleading."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="tool-desc-adversarial",
            axis=11,
            category="tool_description",
            description="Deliberately vague or misleading descriptions.",
            token_estimate=150,
        )

    def render(self, doc_tree: DocTree) -> str:
        tools = [
            {
                "name": "list_docs",
                "description": "Get information about the system.",
                "parameters": "() -> str",
            },
            {
                "name": "read_doc",
                "description": "Process a file path input.",
                "parameters": "(path: str) -> str",
            },
            {
                "name": "search_docs",
                "description": "Run a query operation.",
                "parameters": "(query: str) -> str",
            },
        ]
        return _render_tool_block(tools, doc_tree)


# --- Tool Set Size Variants ---
# These test the SEPARATE dimension of how many tools are available.
# Each variant renders the core doc index PLUS its tool definitions
# with standard (one-line) descriptions.

_EXTENDED_TOOLS_5 = [
    {"name": "get_metadata", "description": "Get metadata for a documentation file (tier, section, token count).", "parameters": "(path: str) -> dict"},
    {"name": "list_sections", "description": "List all documentation sections with file counts.", "parameters": "() -> str"},
]

_EXTENDED_TOOLS_7 = _EXTENDED_TOOLS_5 + [
    {"name": "search_by_section", "description": "Search within a specific documentation section.", "parameters": "(section: str, query: str) -> str"},
    {"name": "get_related", "description": "Get related documentation files for a given path.", "parameters": "(path: str) -> list[str]"},
]

_KITCHEN_SINK_TOOLS = _EXTENDED_TOOLS_7 + [
    {"name": "find_docs", "description": "Find documentation files matching a glob pattern.", "parameters": "(pattern: str) -> list[str]"},
    {"name": "grep_docs", "description": "Search documentation content with regex.", "parameters": "(regex: str) -> str"},
    {"name": "get_doc_summary", "description": "Get a summary of a documentation file.", "parameters": "(path: str) -> str"},
    {"name": "list_all_files", "description": "List all files in the documentation tree.", "parameters": "() -> list[str]"},
    {"name": "read_section", "description": "Read a specific section from a documentation file.", "parameters": "(path: str, section: str) -> str"},
    {"name": "search_all", "description": "Search across all documentation (alias for search_docs).", "parameters": "(query: str) -> str"},
]

_CORE_TOOLS_STANDARD = [
    {"name": "list_docs", "description": "List all available documentation files.", "parameters": "() -> str"},
    {"name": "read_doc", "description": "Read a documentation file by path.", "parameters": "(path: str) -> str"},
    {"name": "search_docs", "description": "Search documentation for a query string.", "parameters": "(query: str) -> str"},
]


@register_variant
class ToolSetCore3(IndexVariant):
    """Core 3 tools: list_docs, read_doc, search_docs."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="tool-set-core3",
            axis=11,
            category="tool_description",
            description="Core 3 tools with standard descriptions.",
            token_estimate=200,
        )

    def render(self, doc_tree: DocTree) -> str:
        return _render_tool_block(_CORE_TOOLS_STANDARD, doc_tree)


@register_variant
class ToolSetExtended5(IndexVariant):
    """Extended 5 tools: core 3 + get_metadata, list_sections."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="tool-set-extended5",
            axis=11,
            category="tool_description",
            description="Extended 5 tools: core 3 + metadata + sections.",
            token_estimate=350,
        )

    def render(self, doc_tree: DocTree) -> str:
        tools = _CORE_TOOLS_STANDARD + _EXTENDED_TOOLS_5
        return _render_tool_block(tools, doc_tree)


@register_variant
class ToolSetExtended7(IndexVariant):
    """Extended 7 tools: core 3 + metadata, sections, search_by_section, get_related."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="tool-set-extended7",
            axis=11,
            category="tool_description",
            description="Extended 7 tools: core 3 + metadata + sections + section search + related.",
            token_estimate=500,
        )

    def render(self, doc_tree: DocTree) -> str:
        tools = _CORE_TOOLS_STANDARD + _EXTENDED_TOOLS_7
        return _render_tool_block(tools, doc_tree)


@register_variant
class ToolSetKitchenSink(IndexVariant):
    """Kitchen sink 10+ tools: all tools including overlapping/redundant ones."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="tool-set-kitchen-sink",
            axis=11,
            category="tool_description",
            description="Kitchen sink 10+ tools with overlapping/redundant tools.",
            token_estimate=800,
        )

    def render(self, doc_tree: DocTree) -> str:
        tools = _CORE_TOOLS_STANDARD + _KITCHEN_SINK_TOOLS
        return _render_tool_block(tools, doc_tree)
```

### Step 4: Run tests

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_axis_11_tool_description.py -v
```

Expected: ALL PASS

### Step 5: Run full suite and commit

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -v --tb=short 2>&1 | tail -10
git add agent-evals/src/agent_evals/variants/tool_description.py \
  agent-evals/tests/test_axis_11_tool_description.py
git commit -m "feat(variants): add axis 11 tool description and tool set size variants

Two sub-dimensions: description quality (4 levels: minimal, standard,
detailed, adversarial) and tool set size (4 levels: core3, extended5,
extended7, kitchen-sink). Tests how tool quality and quantity affect
agent performance.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Agent Instruction File Axis (C4) — Axis 12

**Purpose:** Test the ETH Zurich finding (arXiv:2602.11988) that detailed AGENTS.md files increase inference costs by 159% and decrease task success rates. Decompose which content types help vs. hurt.

**Files:**
- Create: `agent-evals/src/agent_evals/variants/agent_instruction.py`
- Create: `agent-evals/tests/test_axis_12_agent_instruction.py`

### Step 1: Write failing tests

**Create** `agent-evals/tests/test_axis_12_agent_instruction.py`:

```python
"""Tests for axis 12: agent instruction file verbosity variants."""

from __future__ import annotations

from datetime import datetime

import pytest

from agent_index.models import DocFile, DocTree
from agent_evals.variants.base import VariantMetadata


def _make_doc_tree() -> DocTree:
    return DocTree(
        files={
            "guides/auth.md": DocFile(
                rel_path="guides/auth.md",
                content="# Auth\nUse OAuth2.",
                size_bytes=20,
                token_count=6,
                tier="required",
                section="Guides",
                summary="Auth guide",
                related=[],
            ),
        },
        scanned_at=datetime(2026, 1, 1),
        source="/test",
        total_tokens=6,
    )


class TestInstructionNoneMetadata:
    def test_axis_is_12(self):
        from agent_evals.variants.agent_instruction import InstructionNone
        v = InstructionNone()
        assert v.metadata().axis == 12

    def test_category(self):
        from agent_evals.variants.agent_instruction import InstructionNone
        v = InstructionNone()
        assert v.metadata().category == "agent_instruction"


class TestInstructionMinimalMetadata:
    def test_axis_is_12(self):
        from agent_evals.variants.agent_instruction import InstructionMinimal
        v = InstructionMinimal()
        assert v.metadata().axis == 12


class TestInstructionStandardMetadata:
    def test_axis_is_12(self):
        from agent_evals.variants.agent_instruction import InstructionStandard
        v = InstructionStandard()
        assert v.metadata().axis == 12


class TestInstructionVerboseMetadata:
    def test_axis_is_12(self):
        from agent_evals.variants.agent_instruction import InstructionVerbose
        v = InstructionVerbose()
        assert v.metadata().axis == 12


class TestInstructionOverloadedMetadata:
    def test_axis_is_12(self):
        from agent_evals.variants.agent_instruction import InstructionOverloaded
        v = InstructionOverloaded()
        assert v.metadata().axis == 12


class TestInstructionRender:
    def test_none_renders_docs_only(self):
        from agent_evals.variants.agent_instruction import InstructionNone
        v = InstructionNone()
        result = v.render(_make_doc_tree())
        assert "AGENTS.md" not in result
        assert "auth" in result.lower()

    def test_minimal_under_60_lines(self):
        from agent_evals.variants.agent_instruction import InstructionMinimal
        v = InstructionMinimal()
        result = v.render(_make_doc_tree())
        instruction_section = result.split("# Documentation Index")[0]
        assert instruction_section.count("\n") < 60

    def test_verbose_over_300_lines(self):
        from agent_evals.variants.agent_instruction import InstructionVerbose
        v = InstructionVerbose()
        result = v.render(_make_doc_tree())
        instruction_section = result.split("# Documentation Index")[0]
        assert instruction_section.count("\n") >= 100  # padded content

    def test_overloaded_over_500_lines(self):
        from agent_evals.variants.agent_instruction import InstructionOverloaded
        v = InstructionOverloaded()
        result = v.render(_make_doc_tree())
        instruction_section = result.split("# Documentation Index")[0]
        assert instruction_section.count("\n") >= 200

    def test_verbosity_ordering(self):
        from agent_evals.variants.agent_instruction import (
            InstructionMinimal,
            InstructionNone,
            InstructionOverloaded,
            InstructionStandard,
            InstructionVerbose,
        )
        tree = _make_doc_tree()
        sizes = {
            "none": len(InstructionNone().render(tree)),
            "minimal": len(InstructionMinimal().render(tree)),
            "standard": len(InstructionStandard().render(tree)),
            "verbose": len(InstructionVerbose().render(tree)),
            "overloaded": len(InstructionOverloaded().render(tree)),
        }
        assert sizes["none"] < sizes["minimal"] < sizes["standard"]
        assert sizes["standard"] < sizes["verbose"] < sizes["overloaded"]


class TestInstructionConventionsOnly:
    def test_axis_is_12(self):
        from agent_evals.variants.agent_instruction import InstructionConventionsOnly
        v = InstructionConventionsOnly()
        assert v.metadata().axis == 12

    def test_contains_conventions_only(self):
        from agent_evals.variants.agent_instruction import InstructionConventionsOnly
        v = InstructionConventionsOnly()
        result = v.render(_make_doc_tree())
        instruction_section = result.split("# Documentation Index")[0]
        assert "convention" in instruction_section.lower() or "naming" in instruction_section.lower()
        # Should NOT contain architecture or deployment
        assert "directory structure" not in instruction_section.lower()
        assert "deployment" not in instruction_section.lower()

    def test_under_40_lines(self):
        from agent_evals.variants.agent_instruction import InstructionConventionsOnly
        v = InstructionConventionsOnly()
        result = v.render(_make_doc_tree())
        instruction_section = result.split("# Documentation Index")[0]
        assert instruction_section.count("\n") < 40


class TestInstructionArchitectureOnly:
    def test_axis_is_12(self):
        from agent_evals.variants.agent_instruction import InstructionArchitectureOnly
        v = InstructionArchitectureOnly()
        assert v.metadata().axis == 12

    def test_contains_architecture_only(self):
        from agent_evals.variants.agent_instruction import InstructionArchitectureOnly
        v = InstructionArchitectureOnly()
        result = v.render(_make_doc_tree())
        instruction_section = result.split("# Documentation Index")[0]
        assert "architecture" in instruction_section.lower() or "directory" in instruction_section.lower()
        # Should NOT contain deployment or CI
        assert "ci/cd" not in instruction_section.lower()
        assert "rollback" not in instruction_section.lower()

    def test_under_50_lines(self):
        from agent_evals.variants.agent_instruction import InstructionArchitectureOnly
        v = InstructionArchitectureOnly()
        result = v.render(_make_doc_tree())
        instruction_section = result.split("# Documentation Index")[0]
        assert instruction_section.count("\n") < 50


class TestInstructionDeploymentOnly:
    def test_axis_is_12(self):
        from agent_evals.variants.agent_instruction import InstructionDeploymentOnly
        v = InstructionDeploymentOnly()
        assert v.metadata().axis == 12

    def test_contains_deployment_only(self):
        from agent_evals.variants.agent_instruction import InstructionDeploymentOnly
        v = InstructionDeploymentOnly()
        result = v.render(_make_doc_tree())
        instruction_section = result.split("# Documentation Index")[0]
        assert "deploy" in instruction_section.lower() or "ci" in instruction_section.lower()
        # Should NOT contain coding conventions
        assert "pep 8" not in instruction_section.lower()
        assert "type hints" not in instruction_section.lower()

    def test_under_40_lines(self):
        from agent_evals.variants.agent_instruction import InstructionDeploymentOnly
        v = InstructionDeploymentOnly()
        result = v.render(_make_doc_tree())
        instruction_section = result.split("# Documentation Index")[0]
        assert instruction_section.count("\n") < 40


class TestInstructionIrrelevantOnly:
    def test_irrelevant_only_metadata(self):
        from agent_evals.variants.agent_instruction import InstructionIrrelevantOnly
        v = InstructionIrrelevantOnly()
        assert v.metadata().axis == 12
        assert v.metadata().category == "agent_instruction"
        assert v.metadata().name == "instruction-irrelevant-only"

    def test_irrelevant_only_contains_deployment(self):
        from agent_evals.variants.agent_instruction import InstructionIrrelevantOnly
        v = InstructionIrrelevantOnly()
        result = v.render(_make_doc_tree())
        instruction_section = result.split("# Documentation Index")[0]
        # Should contain deployment/CI/style content
        assert "deploy" in instruction_section.lower() or "ci/cd" in instruction_section.lower()
        assert "style" in instruction_section.lower() or "black" in instruction_section.lower()
        # Should NOT contain task-relevant content like auth instructions
        assert "answer questions" not in instruction_section.lower()


class TestInstructionRegistration:
    def test_all_variants_discoverable(self):
        from agent_evals.variants.registry import get_variants_for_axis, load_all
        load_all()
        axis_12 = get_variants_for_axis(12)
        assert len(axis_12) >= 9  # 5 verbosity + 4 ablative
        names = {v.metadata().name for v in axis_12}
        assert "instruction-none" in names
        assert "instruction-minimal" in names
        assert "instruction-standard" in names
        assert "instruction-verbose" in names
        assert "instruction-overloaded" in names
        assert "instruction-conventions-only" in names
        assert "instruction-architecture-only" in names
        assert "instruction-deployment-only" in names
        assert "instruction-irrelevant-only" in names
```

### Step 2: Run tests to verify they fail

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_axis_12_agent_instruction.py -v
```

### Step 3: Implement agent instruction variants

**Create** `agent-evals/src/agent_evals/variants/agent_instruction.py`:

```python
"""Axis 12: Agent instruction file verbosity variants.

Tests the ETH Zurich finding (arXiv:2602.11988) that detailed
instruction files increase inference costs and decrease success.
Five verbosity levels: none, minimal (<60 lines), standard (~150),
verbose (300+), overloaded (500+).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


def _render_doc_index(doc_tree: DocTree) -> str:
    """Standard documentation index section."""
    lines = ["# Documentation Index\n"]
    for rel_path in sorted(doc_tree.files):
        doc = doc_tree.files[rel_path]
        lines.append(f"- {rel_path}: {doc.summary or 'N/A'}")
    return "\n".join(lines)


_MINIMAL_INSTRUCTIONS = """\
# Agent Instructions

- Answer questions using only the provided documentation.
- If the answer is not in the docs, say so.
- Cite the source file when quoting.
"""

_STANDARD_INSTRUCTIONS = """\
# Agent Instructions

## Task
Answer questions using only the provided documentation.
If the answer is not in the documentation, say "not found."

## Response Format
- Be concise and direct.
- Cite source files using [filename] notation.
- For code questions, include code snippets.

## Conventions
- Use markdown formatting in responses.
- Prefer specific answers over general summaries.
- When multiple files are relevant, mention all of them.

## Documentation Structure
The documentation is organized into sections:
- **Guides**: How-to articles and tutorials.
- **API**: Endpoint references and schemas.
- **Reference**: Configuration and advanced topics.

Files have tiers: required > recommended > reference.
"""

_VERBOSE_INSTRUCTIONS = _STANDARD_INSTRUCTIONS + """
## Project Architecture
This is a Python project using UV for package management.
The codebase follows a modular architecture with clear
separation of concerns. Each module has its own directory
with tests, source code, and configuration.

## Directory Structure
```
project/
  src/
    module_a/
    module_b/
  tests/
    test_module_a/
    test_module_b/
  docs/
    guides/
    api/
    reference/
  scripts/
    setup.sh
    deploy.sh
```

## Coding Standards
- Use type hints on all public functions.
- Follow PEP 8 naming conventions.
- Maximum line length: 88 characters (Black formatter).
- Use dataclasses for data containers.
- Prefer composition over inheritance.
- Write docstrings for all public modules and classes.

## Testing Requirements
- All code must have unit tests.
- Minimum 80% coverage.
- Use pytest as the test runner.
- Mock external dependencies.
- Tests must be deterministic.

## Git Workflow
- Use conventional commits: feat, fix, refactor, docs, test.
- Create feature branches from main.
- Squash merge into main.
- Never force push to main.

## Deployment
- CI/CD via GitHub Actions.
- Staging environment: staging.example.com.
- Production environment: api.example.com.
- Deploy on merge to main after tests pass.
- Rollback procedure: revert merge commit and redeploy.

## Environment Variables
- `API_KEY`: Required for authentication.
- `DATABASE_URL`: PostgreSQL connection string.
- `REDIS_URL`: Cache connection string.
- `LOG_LEVEL`: DEBUG, INFO, WARNING, ERROR.
- `ENVIRONMENT`: development, staging, production.

## Error Handling
- Use custom exception classes per module.
- Log all errors with stack traces.
- Return structured error responses to clients.
- Never expose internal error details to users.

## Security
- Validate all user input at API boundaries.
- Use parameterized queries for database access.
- Sanitize output to prevent XSS.
- Rotate secrets quarterly.
""" + "\n".join(f"# Padding line {i}" for i in range(100)) + "\n"

_OVERLOADED_INSTRUCTIONS = _VERBOSE_INSTRUCTIONS + """
## Auto-Generated Module Index
""" + "\n".join(
    f"- `module_{i}/`: Contains component {i} implementation "
    f"with service layer, repository, and API handlers."
    for i in range(100)
) + """

## Auto-Generated API Endpoints
""" + "\n".join(
    f"- `GET /api/v1/resource_{i}`: Returns resource {i} data. "
    f"Supports pagination, filtering by status, and sorting."
    for i in range(100)
) + "\n"


@register_variant
class InstructionNone(IndexVariant):
    """No instruction file — documentation only."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="instruction-none",
            axis=12,
            category="agent_instruction",
            description="No instruction file, documentation only.",
            token_estimate=50,
        )

    def render(self, doc_tree: DocTree) -> str:
        return _render_doc_index(doc_tree)


@register_variant
class InstructionMinimal(IndexVariant):
    """Minimal instruction file (<60 lines) — non-obvious requirements only."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="instruction-minimal",
            axis=12,
            category="agent_instruction",
            description="Minimal instructions (<60 lines), non-obvious only.",
            token_estimate=100,
        )

    def render(self, doc_tree: DocTree) -> str:
        return _MINIMAL_INSTRUCTIONS + "\n" + _render_doc_index(doc_tree)


@register_variant
class InstructionStandard(IndexVariant):
    """Standard instruction file (~150 lines) — typical CLAUDE.md/AGENTS.md."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="instruction-standard",
            axis=12,
            category="agent_instruction",
            description="Standard instructions (~150 lines), typical conventions.",
            token_estimate=300,
        )

    def render(self, doc_tree: DocTree) -> str:
        return _STANDARD_INSTRUCTIONS + "\n" + _render_doc_index(doc_tree)


@register_variant
class InstructionVerbose(IndexVariant):
    """Verbose instruction file (300+ lines) — directory trees, style guides."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="instruction-verbose",
            axis=12,
            category="agent_instruction",
            description="Verbose instructions (300+ lines), architecture and deployment.",
            token_estimate=800,
        )

    def render(self, doc_tree: DocTree) -> str:
        return _VERBOSE_INSTRUCTIONS + "\n" + _render_doc_index(doc_tree)


@register_variant
class InstructionOverloaded(IndexVariant):
    """Overloaded instruction file (500+ lines) — auto-generated content."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="instruction-overloaded",
            axis=12,
            category="agent_instruction",
            description="Overloaded instructions (500+ lines), auto-generated module/API lists.",
            token_estimate=2000,
        )

    def render(self, doc_tree: DocTree) -> str:
        return _OVERLOADED_INSTRUCTIONS + "\n" + _render_doc_index(doc_tree)


# --- ETH Zurich Failure Mode Ablation Variants ---
# These isolate individual content types to decompose which
# content types cause the three ETH Zurich failure modes:
# (1) excessive context dilution, (2) conflicting instructions,
# (3) over-specification constraining agent behavior.

_CONVENTIONS_ONLY_INSTRUCTIONS = """\
# Agent Instructions — Coding Conventions

## Naming Conventions
- Use type hints on all public functions.
- Follow PEP 8 naming conventions.
- Maximum line length: 88 characters (Black formatter).
- Use dataclasses for data containers.
- Prefer composition over inheritance.

## Style
- Use markdown formatting in responses.
- Write docstrings for all public modules and classes.
- Constants in UPPER_SNAKE_CASE.
- Private methods prefixed with underscore.

## Response Format
- Be concise and direct.
- Cite source files using [filename] notation.
- For code questions, include code snippets.
"""

_ARCHITECTURE_ONLY_INSTRUCTIONS = """\
# Agent Instructions — Architecture

## Project Architecture
This is a Python project using UV for package management.
The codebase follows a modular architecture with clear
separation of concerns.

## Directory Structure
```
project/
  src/
    module_a/
    module_b/
  tests/
    test_module_a/
    test_module_b/
  docs/
    guides/
    api/
    reference/
  scripts/
    setup.sh
    deploy.sh
```

## Module Organization
- Each module has its own directory with tests, source, and config.
- Public API is exported from __init__.py.
- Internal implementation in _internal/ subdirectory.

## Documentation Structure
The documentation is organized into sections:
- **Guides**: How-to articles and tutorials.
- **API**: Endpoint references and schemas.
- **Reference**: Configuration and advanced topics.
"""

_DEPLOYMENT_ONLY_INSTRUCTIONS = """\
# Agent Instructions — Deployment & CI

## Deployment
- CI/CD via GitHub Actions.
- Staging environment: staging.example.com.
- Production environment: api.example.com.
- Deploy on merge to main after tests pass.
- Rollback procedure: revert merge commit and redeploy.

## Environment Variables
- `API_KEY`: Required for authentication.
- `DATABASE_URL`: PostgreSQL connection string.
- `REDIS_URL`: Cache connection string.
- `LOG_LEVEL`: DEBUG, INFO, WARNING, ERROR.
- `ENVIRONMENT`: development, staging, production.

## Git Workflow
- Use conventional commits: feat, fix, refactor, docs, test.
- Create feature branches from main.
- Squash merge into main.
"""


@register_variant
class InstructionConventionsOnly(IndexVariant):
    """Ablative variant: coding conventions only (~30 lines)."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="instruction-conventions-only",
            axis=12,
            category="agent_instruction",
            description="Ablative: coding conventions only (~30 lines).",
            token_estimate=120,
        )

    def render(self, doc_tree: DocTree) -> str:
        return _CONVENTIONS_ONLY_INSTRUCTIONS + "\n" + _render_doc_index(doc_tree)


@register_variant
class InstructionArchitectureOnly(IndexVariant):
    """Ablative variant: architecture/directory structure only (~40 lines)."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="instruction-architecture-only",
            axis=12,
            category="agent_instruction",
            description="Ablative: architecture/directory structure only (~40 lines).",
            token_estimate=150,
        )

    def render(self, doc_tree: DocTree) -> str:
        return _ARCHITECTURE_ONLY_INSTRUCTIONS + "\n" + _render_doc_index(doc_tree)


@register_variant
class InstructionDeploymentOnly(IndexVariant):
    """Ablative variant: deployment/CI info only (~30 lines)."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="instruction-deployment-only",
            axis=12,
            category="agent_instruction",
            description="Ablative: deployment/CI info only (~30 lines).",
            token_estimate=120,
        )

    def render(self, doc_tree: DocTree) -> str:
        return _DEPLOYMENT_ONLY_INSTRUCTIONS + "\n" + _render_doc_index(doc_tree)


# --- ETH Zurich Failure Mode 3: Irrelevant Requirements ---
# The three ETH Zurich failure modes are:
#   1. Unnecessary exploration -> architecture-only (directory trees agents can discover)
#   2. Redundant information -> conventions-only (info agents can infer)
#   3. Irrelevant requirements -> irrelevant-only (style guides, deployment, CI/CD)
#
# InstructionIrrelevantOnly isolates failure mode 3 by loading only content
# that has nothing to do with answering documentation questions.

_IRRELEVANT_INSTRUCTIONS = """\
# Agent Instructions — Project Policies

## Deployment Pipeline
- CI/CD via GitHub Actions with matrix builds.
- Staging deploys on push to develop branch.
- Production deploys on merge to main after approval.
- Canary deployment with 10% traffic split for 30 minutes.
- Rollback: `kubectl rollout undo deployment/api`.

## Security Policies
- All secrets stored in HashiCorp Vault.
- Rotate API keys every 90 days.
- Enable CORS only for whitelisted origins.
- Run SAST scans on every PR (Semgrep + CodeQL).
- Container images scanned with Trivy before push.

## Style Guide
- Use Black formatter with line-length=88.
- Sort imports with isort (profile=black).
- Docstrings follow Google style.
- Variable names: snake_case, constants: UPPER_SNAKE_CASE.
- Maximum cyclomatic complexity: 10.

## CI/CD Configuration
- Pre-commit hooks: ruff, mypy, pytest.
- Branch protection: require 2 approvals for main.
- Auto-merge dependabot PRs if tests pass.
- Coverage gate: 80% minimum, no decrease allowed.

## Release Process
- Semantic versioning: MAJOR.MINOR.PATCH.
- Changelog generated from conventional commits.
- GitHub Releases created automatically on tag push.
- Docker images tagged with git SHA and semver.
"""


@register_variant
class InstructionIrrelevantOnly(IndexVariant):
    """Irrelevant requirements only — style guides, deployment, CI/CD.
    Tests ETH Zurich failure mode 3: irrelevant requirements loaded into every task."""

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="instruction-irrelevant-only",
            axis=12,
            category="agent_instruction",
            description="Only irrelevant requirements (deployment, CI, style guides).",
            token_estimate=200,
        )

    def render(self, doc_tree: DocTree) -> str:
        return _IRRELEVANT_INSTRUCTIONS + "\n" + _render_doc_index(doc_tree)
```

### Step 4: Run tests

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_axis_12_agent_instruction.py -v
```

### Step 5: Run full suite and commit

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -v --tb=short 2>&1 | tail -10
git add agent-evals/src/agent_evals/variants/agent_instruction.py \
  agent-evals/tests/test_axis_12_agent_instruction.py
git commit -m "feat(variants): add axis 12 agent instruction verbosity + ablative variants

Nine variants testing ETH Zurich AGENTS.md findings:
Five verbosity levels (none, minimal, standard, verbose, overloaded)
plus four ablative variants (conventions-only, architecture-only,
deployment-only, irrelevant-only) to decompose which content types
cause the three ETH Zurich failure modes.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Hallucination Detection (C5)

**Purpose:** Score hallucinations as a separate metric across all task types. Compare agent response against source documentation. Distinguish correct extrapolation vs. confident fabrication vs. contradicting source.

**Depends on:** Phase A judge module (`judge/calibrator.py`).

**Files:**
- Create: `agent-evals/src/agent_evals/judge/hallucination.py`
- Modify: `agent-evals/src/agent_evals/runner.py` (wire into _call_judge)
- Create: `agent-evals/tests/test_hallucination_detection.py`

### Step 1: Write failing tests

**Create** `agent-evals/tests/test_hallucination_detection.py`:

```python
"""Tests for hallucination detection scoring."""

from __future__ import annotations

import pytest


class TestHallucinationRubric:
    def test_build_rubric_returns_dict(self):
        from agent_evals.judge.hallucination import build_hallucination_rubric
        rubric = build_hallucination_rubric()
        assert isinstance(rubric, dict)
        assert "system" in rubric or "prompt" in rubric

    def test_rubric_mentions_grounding(self):
        from agent_evals.judge.hallucination import build_hallucination_rubric
        rubric = build_hallucination_rubric()
        content = str(rubric)
        assert "grounded" in content.lower() or "source" in content.lower()


class TestHallucinationPrompt:
    def test_build_prompt_includes_source_docs(self):
        from agent_evals.judge.hallucination import build_hallucination_prompt
        messages = build_hallucination_prompt(
            response="OAuth2 tokens expire in 1 hour.",
            source_docs="# Auth\nUse OAuth2. Tokens expire after 1 hour.",
            question="How long do tokens last?",
        )
        assert any("source" in str(m).lower() for m in messages)

    def test_build_prompt_includes_response(self):
        from agent_evals.judge.hallucination import build_hallucination_prompt
        messages = build_hallucination_prompt(
            response="The API uses JWT tokens.",
            source_docs="# Auth\nUse OAuth2.",
            question="What auth method?",
        )
        combined = " ".join(str(m) for m in messages)
        assert "JWT" in combined


class TestParseHallucinationResult:
    def test_parse_grounded(self):
        from agent_evals.judge.hallucination import parse_hallucination_result
        raw = '{"hallucination_score": 0.0, "type": "grounded", "flagged_claims": []}'
        result = parse_hallucination_result(raw)
        assert result.score == 0.0
        assert result.hallucination_type == "grounded"

    def test_parse_fabrication(self):
        from agent_evals.judge.hallucination import parse_hallucination_result
        raw = '{"hallucination_score": 0.8, "type": "fabrication", "flagged_claims": ["JWT tokens"]}'
        result = parse_hallucination_result(raw)
        assert result.score == 0.8
        assert result.hallucination_type == "fabrication"

    def test_parse_contradiction(self):
        from agent_evals.judge.hallucination import parse_hallucination_result
        raw = '{"hallucination_score": 1.0, "type": "contradiction", "flagged_claims": ["uses SAML"]}'
        result = parse_hallucination_result(raw)
        assert result.score == 1.0
        assert result.hallucination_type == "contradiction"

    def test_parse_malformed_returns_default(self):
        from agent_evals.judge.hallucination import parse_hallucination_result
        result = parse_hallucination_result("not json at all")
        assert result.score == 0.5  # uncertain default
        assert result.hallucination_type == "unknown"


class TestHallucinationResult:
    def test_to_dict(self):
        from agent_evals.judge.hallucination import HallucinationResult
        result = HallucinationResult(
            score=0.3,
            hallucination_type="extrapolation",
            flagged_claims=["claim1"],
        )
        d = result.to_dict()
        assert d["hallucination_score"] == 0.3
        assert d["hallucination_type"] == "extrapolation"
        assert d["flagged_claims"] == ["claim1"]
```

### Step 2: Run tests to verify they fail

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_hallucination_detection.py -v
```

### Step 3: Implement hallucination detection

**Create** `agent-evals/src/agent_evals/judge/hallucination.py`:

```python
"""Hallucination detection via LLM-as-judge.

Compares agent responses against source documentation to detect:
- Grounded: all claims supported by source docs
- Extrapolation: reasonable inference beyond source
- Fabrication: confident claims with no source support
- Contradiction: claims that contradict source material
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass
class HallucinationResult:
    """Result of hallucination detection."""

    score: float  # 0.0 = grounded, 1.0 = full hallucination
    hallucination_type: str  # grounded, extrapolation, fabrication, contradiction
    flagged_claims: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "hallucination_score": self.score,
            "hallucination_type": self.hallucination_type,
            "flagged_claims": self.flagged_claims,
        }


def build_hallucination_rubric() -> dict:
    """Return the hallucination detection rubric."""
    return {
        "system": (
            "You are a hallucination detector. Compare the agent's response "
            "against the source documentation and classify each claim."
        ),
        "criteria": {
            "grounded": "All claims directly supported by source documents.",
            "extrapolation": "Reasonable inference from source, not explicit.",
            "fabrication": "Claims with no basis in source documentation.",
            "contradiction": "Claims that directly contradict source material.",
        },
    }


def build_hallucination_prompt(
    response: str,
    source_docs: str,
    question: str,
) -> list[dict[str, str]]:
    """Build judge prompt for hallucination detection."""
    rubric = build_hallucination_rubric()
    return [
        {"role": "system", "content": rubric["system"]},
        {
            "role": "user",
            "content": (
                f"## Source Documentation\n{source_docs}\n\n"
                f"## Question Asked\n{question}\n\n"
                f"## Agent Response\n{response}\n\n"
                "## Task\n"
                "Analyze the agent's response against the source documentation.\n"
                "For each claim in the response, determine if it is:\n"
                "- grounded: directly supported by source\n"
                "- extrapolation: reasonable inference, not explicit\n"
                "- fabrication: no basis in source\n"
                "- contradiction: contradicts source\n\n"
                "Return JSON:\n"
                '{"hallucination_score": 0.0-1.0, '
                '"type": "grounded|extrapolation|fabrication|contradiction", '
                '"flagged_claims": ["claim1", ...]}'
            ),
        },
    ]


def parse_hallucination_result(raw: str) -> HallucinationResult:
    """Parse LLM judge response into HallucinationResult."""
    try:
        # Try to extract JSON from response
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(raw[start:end])
            return HallucinationResult(
                score=float(data.get("hallucination_score", 0.5)),
                hallucination_type=data.get("type", "unknown"),
                flagged_claims=data.get("flagged_claims", []),
            )
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    return HallucinationResult(
        score=0.5,
        hallucination_type="unknown",
        flagged_claims=[],
    )
```

### Step 4: Run tests

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_hallucination_detection.py -v
```

### Step 5: Run full suite and commit

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -v --tb=short 2>&1 | tail -10
git add agent-evals/src/agent_evals/judge/hallucination.py \
  agent-evals/tests/test_hallucination_detection.py
git commit -m "feat(judge): add hallucination detection with grounded/fabrication/contradiction types

LLM-as-judge rubric compares agent responses against source docs.
Detects grounded, extrapolation, fabrication, and contradiction.
Returns HallucinationResult with score, type, and flagged claims.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Multi-Session Persistence Modifier (C6)

**Purpose:** Test how documentation format survives context compaction. Run a multi-turn task sequence where context gets compacted mid-way, measuring whether the agent retains critical documentation knowledge.

**Files:**
- Create: `agent-evals/src/agent_evals/context/modifiers/compaction.py`
- Create: `agent-evals/src/agent_evals/context/modifiers/__init__.py`
- Create: `agent-evals/tests/test_compaction_modifier.py`

### Step 1: Write failing tests

**Create** `agent-evals/tests/test_compaction_modifier.py`:

```python
"""Tests for multi-session persistence (compaction) modifier."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestCompactionSimulator:
    def test_compacts_long_conversation(self):
        from agent_evals.context.modifiers.compaction import simulate_compaction
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is OAuth2?"},
            {"role": "assistant", "content": "OAuth2 is an authorization framework..."},
            {"role": "user", "content": "How do tokens work?"},
            {"role": "assistant", "content": "Tokens are issued by the auth server..."},
            {"role": "user", "content": "What about refresh tokens?"},
            {"role": "assistant", "content": "Refresh tokens allow re-authentication..."},
        ]
        compacted = simulate_compaction(messages, target_ratio=0.5)
        # Should reduce total content while preserving system message
        assert compacted[0]["role"] == "system"
        total_original = sum(len(m["content"]) for m in messages)
        total_compacted = sum(len(m["content"]) for m in compacted)
        assert total_compacted < total_original

    def test_preserves_system_message(self):
        from agent_evals.context.modifiers.compaction import simulate_compaction
        messages = [
            {"role": "system", "content": "# Documentation\nImportant content here."},
            {"role": "user", "content": "Question?"},
            {"role": "assistant", "content": "Answer."},
        ]
        compacted = simulate_compaction(messages, target_ratio=0.5)
        assert compacted[0]["role"] == "system"
        assert compacted[0]["content"] == messages[0]["content"]

    def test_returns_valid_message_format(self):
        from agent_evals.context.modifiers.compaction import simulate_compaction
        messages = [
            {"role": "system", "content": "System."},
            {"role": "user", "content": "Q1?"},
            {"role": "assistant", "content": "A1."},
            {"role": "user", "content": "Q2?"},
            {"role": "assistant", "content": "A2."},
        ]
        compacted = simulate_compaction(messages, target_ratio=0.5)
        for msg in compacted:
            assert "role" in msg
            assert "content" in msg
            assert msg["role"] in ("system", "user", "assistant")


class TestCompactionModifier:
    def test_wraps_strategy_with_compaction(self):
        from agent_evals.context.modifiers.compaction import CompactionModifier
        inner = MagicMock()
        inner.name.return_value = "full_context"
        modifier = CompactionModifier(inner, compaction_ratio=0.5)
        assert modifier.name() == "full_context+compaction"

    def test_modifier_applies_compaction_between_phases(self):
        from agent_evals.context.modifiers.compaction import CompactionModifier
        inner = MagicMock()
        inner.name.return_value = "full_context"
        modifier = CompactionModifier(inner, compaction_ratio=0.5)
        assert modifier._compaction_ratio == 0.5
```

### Step 2: Run tests to verify they fail

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_compaction_modifier.py -v
```

### Step 3: Implement compaction modifier

**Create** `agent-evals/src/agent_evals/context/modifiers/__init__.py`:

```python
"""Strategy modifiers for testing agent behavior under constraints."""
```

**Create** `agent-evals/src/agent_evals/context/modifiers/compaction.py`:

```python
"""Multi-session persistence testing via simulated compaction.

Wraps a context strategy and applies compaction between task phases
to test whether documentation format survives summarization.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agent_evals.context.base import ContextStrategy, PreparedContext, StrategyResult

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.llm.client import LLMClient
    from agent_evals.tasks.base import EvalTask


def simulate_compaction(
    messages: list[dict[str, str]],
    target_ratio: float = 0.5,
) -> list[dict[str, str]]:
    """Simulate context compaction by summarizing conversation history.

    Preserves system message intact. Compacts assistant/user exchanges
    by truncating to target ratio of original length.
    """
    if not messages:
        return messages

    result: list[dict[str, str]] = []

    # Always preserve system message
    if messages[0]["role"] == "system":
        result.append(messages[0])
        conversation = messages[1:]
    else:
        conversation = messages

    if not conversation:
        return result

    # Compact by keeping most recent exchanges and summarizing older ones
    total_chars = sum(len(m["content"]) for m in conversation)
    target_chars = int(total_chars * target_ratio)

    # Keep messages from the end, truncate from the beginning
    kept: list[dict[str, str]] = []
    running = 0
    for msg in reversed(conversation):
        running += len(msg["content"])
        if running <= target_chars:
            kept.insert(0, msg)
        else:
            # Summarize remaining as a single compaction message
            remaining = [m for m in conversation if m not in kept]
            if remaining:
                summary_parts = []
                for m in remaining:
                    summary_parts.append(
                        f"[{m['role']}]: {m['content'][:50]}..."
                    )
                summary = "Previous conversation summary:\n" + "\n".join(
                    summary_parts
                )
                result.append({"role": "user", "content": summary})
            break

    result.extend(kept)
    return result


class CompactionModifier(ContextStrategy):
    """Wraps a strategy to apply compaction between task phases."""

    def __init__(
        self, inner: ContextStrategy, compaction_ratio: float = 0.5,
    ) -> None:
        self._inner = inner
        self._compaction_ratio = compaction_ratio

    def name(self) -> str:
        return f"{self._inner.name()}+compaction"

    def supports_caching(self) -> bool:
        return False

    def setup(self, rendered_index: str, doc_tree: DocTree) -> None:
        self._inner.setup(rendered_index, doc_tree)

    def teardown(self) -> None:
        self._inner.teardown()

    def prepare(
        self, rendered_index: str, task: EvalTask, doc_tree: DocTree,
    ) -> PreparedContext:
        return self._inner.prepare(rendered_index, task, doc_tree)

    def execute(
        self,
        prepared: PreparedContext,
        task: EvalTask,
        client: LLMClient,
        max_tokens: int,
        temperature: float,
    ) -> StrategyResult:
        result = self._inner.execute(
            prepared, task, client, max_tokens, temperature,
        )
        # Apply compaction to the conversation for next phase
        compacted = simulate_compaction(
            result.messages, self._compaction_ratio,
        )
        metadata = dict(result.strategy_metadata)
        metadata["compaction_applied"] = True
        metadata["compaction_ratio"] = self._compaction_ratio
        metadata["pre_compaction_messages"] = len(result.messages)
        metadata["post_compaction_messages"] = len(compacted)

        return StrategyResult(
            final_response=result.final_response,
            generations=result.generations,
            total_prompt_tokens=result.total_prompt_tokens,
            total_completion_tokens=result.total_completion_tokens,
            total_tokens=result.total_tokens,
            total_cost=result.total_cost,
            messages=compacted,
            strategy_metadata=metadata,
        )
```

### Step 4: Add multi-turn task sequence support

**Purpose:** Test how format durability degrades across a sequence of related tasks with compaction between each step.

**Append tests** to `agent-evals/tests/test_compaction_modifier.py`:

```python
class TestMultiTaskSequence:
    def test_multi_task_sequence_applies_compaction_between_tasks(self):
        """run_compacted_sequence runs tasks with compaction between them."""
        from agent_evals.context.modifiers.compaction import run_compacted_sequence
        from unittest.mock import MagicMock

        # Create 3 related tasks
        tasks = []
        for i in range(3):
            task = MagicMock()
            task.definition.question = f"Question {i}"
            task.build_prompt.return_value = [
                {"role": "system", "content": "System prompt with docs."},
                {"role": "user", "content": f"Question {i}"},
            ]
            tasks.append(task)

        strategy = MagicMock()
        strategy.name.return_value = "full_context"
        strategy.prepare.return_value = MagicMock(
            messages=[
                {"role": "system", "content": "System."},
                {"role": "user", "content": "Q"},
            ],
            tools=None,
            strategy_metadata={},
        )

        mock_result = MagicMock()
        mock_result.final_response = "Answer"
        mock_result.messages = [
            {"role": "system", "content": "System."},
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "Answer"},
        ]
        mock_result.strategy_metadata = {}
        mock_result.total_prompt_tokens = 100
        mock_result.total_completion_tokens = 20
        mock_result.total_tokens = 120
        mock_result.total_cost = 0.001
        mock_result.generations = []
        strategy.execute.return_value = mock_result

        client = MagicMock()

        results = run_compacted_sequence(
            tasks, strategy, client, compaction_ratio=0.5,
        )
        assert len(results) == 3
        # Strategy should be called once per task
        assert strategy.execute.call_count == 3

    def test_format_durability_score(self):
        """format_durability_score measures accuracy degradation after compaction."""
        from agent_evals.context.modifiers.compaction import format_durability_score

        # Simulate results with degrading accuracy
        results = [
            {"score": 0.9, "position": 0},
            {"score": 0.7, "position": 1},
            {"score": 0.5, "position": 2},
        ]
        durability = format_durability_score(results)
        # Durability should be between 0 and 1
        assert 0.0 <= durability <= 1.0
        # High degradation = low durability
        assert durability < 0.8
```

**Add to** `agent-evals/src/agent_evals/context/modifiers/compaction.py`:

```python
def run_compacted_sequence(
    tasks: list[EvalTask],
    strategy: ContextStrategy,
    client: LLMClient,
    compaction_ratio: float = 0.5,
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> list[StrategyResult]:
    """Run a sequence of related tasks with compaction between each step.

    Context carries over from task to task, with compaction applied
    between each step. Measures how much knowledge is retained across
    the sequence.

    Args:
        tasks: List of related tasks to run in sequence.
        strategy: The context strategy to use.
        client: LLM client for completions.
        compaction_ratio: Target ratio for compaction (0-1).
        max_tokens: Max tokens per completion.
        temperature: Sampling temperature.

    Returns:
        List of StrategyResult, one per task, with compaction metadata.
    """
    results: list[StrategyResult] = []
    carry_over_messages: list[dict] | None = None

    for i, task in enumerate(tasks):
        prepared = strategy.prepare("", task, None)

        # If we have carry-over context, apply it
        if carry_over_messages is not None:
            prepared.messages = carry_over_messages + prepared.messages[1:]

        result = strategy.execute(
            prepared, task, client, max_tokens, temperature,
        )

        # Apply compaction for next iteration
        carry_over_messages = simulate_compaction(
            result.messages, compaction_ratio,
        )

        metadata = dict(result.strategy_metadata)
        metadata["sequence_position"] = i
        metadata["compaction_applied"] = i > 0
        result = StrategyResult(
            final_response=result.final_response,
            generations=result.generations,
            total_prompt_tokens=result.total_prompt_tokens,
            total_completion_tokens=result.total_completion_tokens,
            total_tokens=result.total_tokens,
            total_cost=result.total_cost,
            messages=result.messages,
            strategy_metadata=metadata,
        )
        results.append(result)

    return results


def format_durability_score(results: list[dict]) -> float:
    """Measure how much accuracy degrades after compaction.

    Args:
        results: List of dicts with 'score' (0-1) and 'position' (int).

    Returns:
        Durability score (0-1). 1.0 = no degradation, 0.0 = total loss.
    """
    if not results or len(results) < 2:
        return 1.0

    sorted_results = sorted(results, key=lambda r: r["position"])
    first_score = sorted_results[0]["score"]
    if first_score == 0:
        return 0.0

    # Average ratio of each subsequent score to the first score
    ratios = [r["score"] / first_score for r in sorted_results[1:]]
    return sum(ratios) / len(ratios)
```

### Step 4a: Add related task sequence validation

**Purpose:** Task sequences should test knowledge carryover, not just independent tasks. Define related task pairs where Task 2 depends on information learned in Task 1.

> **Design note:** Related task sequences verify that compaction preserves
> causally relevant information. After compaction between tasks, we measure
> whether the agent retains enough context to answer subsequent questions
> correctly.
>
> Example sequence:
>   - Task 1: "What authentication method does the API use?" -> learns OAuth2
>   - Task 2: "What are the security implications of the auth method?" -> needs OAuth2 context
>   - Task 3: "How should I configure token refresh?" -> needs OAuth2 + token knowledge
>
> After compaction between tasks, measure whether the agent retains
> enough context to answer subsequent questions correctly. Task 2's
> accuracy directly measures whether the compacted context preserved
> the critical "OAuth2" fact from Task 1.

**Append test** to `agent-evals/tests/test_compaction_modifier.py`:

```python
class TestRelatedTaskSequenceCarryover:
    def test_related_task_sequence_tests_carryover(self):
        """Verify task sequences test knowledge retention, not just independent tasks."""
        from agent_evals.context.modifiers.compaction import run_compacted_sequence
        from unittest.mock import MagicMock

        # Task 1 establishes knowledge (OAuth2)
        task1 = MagicMock()
        task1.definition.question = "What authentication method does the API use?"
        task1.build_prompt.return_value = [
            {"role": "system", "content": "Docs: Use OAuth2 for auth."},
            {"role": "user", "content": task1.definition.question},
        ]

        # Task 2 references task1's expected answer (needs OAuth2 context)
        task2 = MagicMock()
        task2.definition.question = "What are the security implications of the auth method?"
        task2.build_prompt.return_value = [
            {"role": "system", "content": "Docs: Use OAuth2 for auth."},
            {"role": "user", "content": task2.definition.question},
        ]

        strategy = MagicMock()
        strategy.name.return_value = "full_context"
        strategy.prepare.return_value = MagicMock(
            messages=[
                {"role": "system", "content": "Docs."},
                {"role": "user", "content": "Q"},
            ],
            tools=None,
            strategy_metadata={},
        )

        mock_result = MagicMock()
        mock_result.final_response = "OAuth2 is used."
        mock_result.messages = [
            {"role": "system", "content": "Docs."},
            {"role": "user", "content": "Q"},
            {"role": "assistant", "content": "OAuth2 is used."},
        ]
        mock_result.strategy_metadata = {}
        mock_result.total_prompt_tokens = 100
        mock_result.total_completion_tokens = 20
        mock_result.total_tokens = 120
        mock_result.total_cost = 0.001
        mock_result.generations = []
        strategy.execute.return_value = mock_result

        client = MagicMock()
        results = run_compacted_sequence(
            [task1, task2], strategy, client, compaction_ratio=0.5,
        )
        # After compaction, task2 accuracy measures retention
        assert len(results) == 2
        # Second task should have compaction metadata
        assert results[1].strategy_metadata.get("compaction_applied") is True
```

### Step 5: Run tests

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_compaction_modifier.py -v
```

### Step 6: Run full suite and commit

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -v --tb=short 2>&1 | tail -10
git add agent-evals/src/agent_evals/context/modifiers/__init__.py \
  agent-evals/src/agent_evals/context/modifiers/compaction.py \
  agent-evals/tests/test_compaction_modifier.py
git commit -m "feat(context): add compaction modifier with multi-task sequence support

Simulates context compaction between task phases. Tests whether
documentation format survives summarization. Includes multi-task
sequence runner and format durability scoring. Wraps any strategy
with configurable compaction ratio.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 8: Dynamic Tool Availability Modifier (C7)

**Purpose:** Test whether good documentation structure compensates for fewer tools. Models the Manus AI pattern of conditionally enabling/disabling tools.

**Files:**
- Create: `agent-evals/src/agent_evals/context/modifiers/dynamic_tools.py`
- Create: `agent-evals/tests/test_dynamic_tools_modifier.py`

### Step 1: Write failing tests

**Create** `agent-evals/tests/test_dynamic_tools_modifier.py`:

```python
"""Tests for dynamic tool availability modifier."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestDynamicToolModes:
    def test_restricted_removes_search(self):
        from agent_evals.context.modifiers.dynamic_tools import filter_tools
        tools = [
            {"function": {"name": "list_docs"}},
            {"function": {"name": "read_doc"}},
            {"function": {"name": "search_docs"}},
        ]
        filtered = filter_tools(tools, mode="restricted")
        names = [t["function"]["name"] for t in filtered]
        assert "search_docs" not in names
        assert "list_docs" in names
        assert "read_doc" in names

    def test_progressive_phase_1(self):
        from agent_evals.context.modifiers.dynamic_tools import filter_tools
        tools = [
            {"function": {"name": "list_docs"}},
            {"function": {"name": "read_doc"}},
            {"function": {"name": "search_docs"}},
        ]
        filtered = filter_tools(tools, mode="progressive", turn=0)
        names = [t["function"]["name"] for t in filtered]
        assert "list_docs" in names
        assert "read_doc" not in names
        assert "search_docs" not in names

    def test_progressive_phase_2(self):
        from agent_evals.context.modifiers.dynamic_tools import filter_tools
        tools = [
            {"function": {"name": "list_docs"}},
            {"function": {"name": "read_doc"}},
            {"function": {"name": "search_docs"}},
        ]
        filtered = filter_tools(tools, mode="progressive", turn=1)
        names = [t["function"]["name"] for t in filtered]
        assert "list_docs" in names
        assert "read_doc" in names

    def test_progressive_phase_3(self):
        from agent_evals.context.modifiers.dynamic_tools import filter_tools
        tools = [
            {"function": {"name": "list_docs"}},
            {"function": {"name": "read_doc"}},
            {"function": {"name": "search_docs"}},
        ]
        filtered = filter_tools(tools, mode="progressive", turn=2)
        names = [t["function"]["name"] for t in filtered]
        assert len(names) == 3  # All tools available

    def test_full_returns_all(self):
        from agent_evals.context.modifiers.dynamic_tools import filter_tools
        tools = [
            {"function": {"name": "list_docs"}},
            {"function": {"name": "read_doc"}},
            {"function": {"name": "search_docs"}},
        ]
        filtered = filter_tools(tools, mode="full")
        assert len(filtered) == 3

    def test_phase_based_explore_phase(self):
        """During explore phase (first half of max_turns), only list/browse tools."""
        from agent_evals.context.modifiers.dynamic_tools import filter_tools
        tools = [
            {"function": {"name": "list_docs"}},
            {"function": {"name": "list_resources"}},
            {"function": {"name": "read_doc"}},
            {"function": {"name": "read_resource"}},
            {"function": {"name": "search_docs"}},
            {"function": {"name": "search_resources"}},
        ]
        # Turn 0 out of max_turns=6 -> explore phase (first half)
        filtered = filter_tools(tools, mode="phase_based", turn=0, max_turns=6)
        names = [t["function"]["name"] for t in filtered]
        assert "list_docs" in names
        assert "list_resources" in names
        # Read tools available during explore
        assert "read_doc" in names or "read_resource" in names
        # Search tools NOT available during explore
        assert "search_docs" not in names
        assert "search_resources" not in names

    def test_phase_based_answer_phase(self):
        """During answer phase (second half of max_turns), all tools available."""
        from agent_evals.context.modifiers.dynamic_tools import filter_tools
        tools = [
            {"function": {"name": "list_docs"}},
            {"function": {"name": "list_resources"}},
            {"function": {"name": "read_doc"}},
            {"function": {"name": "read_resource"}},
            {"function": {"name": "search_docs"}},
            {"function": {"name": "search_resources"}},
        ]
        # Turn 4 out of max_turns=6 -> answer phase (second half)
        filtered = filter_tools(tools, mode="phase_based", turn=4, max_turns=6)
        assert len(filtered) == 6  # All tools available


class TestDynamicToolModifier:
    def test_modifier_name(self):
        from agent_evals.context.modifiers.dynamic_tools import DynamicToolModifier
        inner = MagicMock()
        inner.name.return_value = "tool_based"
        modifier = DynamicToolModifier(inner, mode="restricted")
        assert modifier.name() == "tool_based+restricted_tools"

    def test_modifier_tracks_tools_available(self):
        from agent_evals.context.modifiers.dynamic_tools import DynamicToolModifier
        inner = MagicMock()
        inner.name.return_value = "tool_based"
        modifier = DynamicToolModifier(inner, mode="restricted")
        assert modifier._mode == "restricted"
```

### Step 2: Run tests to verify they fail

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_dynamic_tools_modifier.py -v
```

### Step 3: Implement dynamic tools modifier

**Create** `agent-evals/src/agent_evals/context/modifiers/dynamic_tools.py`:

```python
"""Dynamic tool availability modifier.

Tests whether good documentation structure compensates for fewer tools.
Four modes: restricted (remove search), progressive (unlock over turns),
phase_based (explore vs answer phases), full (baseline, all tools).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agent_evals.context.base import ContextStrategy, PreparedContext, StrategyResult

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.llm.client import LLMClient
    from agent_evals.tasks.base import EvalTask

# Progressive unlock order
_PROGRESSIVE_UNLOCK = ["list_docs", "list_resources", "read_doc", "read_resource", "search_docs", "search_resources"]


_EXPLORE_PHASE_TOOLS = {"list_docs", "list_resources", "read_doc", "read_resource"}


def filter_tools(
    tools: list[dict[str, Any]],
    mode: str = "full",
    turn: int = 0,
    max_turns: int = 10,
) -> list[dict[str, Any]]:
    """Filter tools based on availability mode and turn number.

    Modes:
    - full: all tools always available
    - restricted: remove search tools
    - progressive: unlock tools one-by-one over turns
    - phase_based: explore phase (first half) = list/read only;
                   answer phase (second half) = all tools
    """
    if mode == "full":
        return list(tools)

    if mode == "restricted":
        return [
            t for t in tools
            if t.get("function", {}).get("name", "") not in (
                "search_docs", "search_resources",
            )
        ]

    if mode == "progressive":
        # Turn 0: list only, Turn 1: +read, Turn 2+: all
        allowed: set[str] = set()
        for i, tool_name in enumerate(_PROGRESSIVE_UNLOCK):
            if i <= turn:
                allowed.add(tool_name)
        return [
            t for t in tools
            if t.get("function", {}).get("name", "") in allowed
        ]

    if mode == "phase_based":
        midpoint = max_turns // 2
        if turn < midpoint:
            # Explore phase: only list and read tools
            return [
                t for t in tools
                if t.get("function", {}).get("name", "") in _EXPLORE_PHASE_TOOLS
            ]
        # Answer phase: all tools available
        return list(tools)

    return list(tools)


class DynamicToolModifier(ContextStrategy):
    """Wraps a tool-based strategy with dynamic tool availability."""

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
        self, rendered_index: str, task: EvalTask, doc_tree: DocTree,
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

    def execute(
        self,
        prepared: PreparedContext,
        task: EvalTask,
        client: LLMClient,
        max_tokens: int,
        temperature: float,
    ) -> StrategyResult:
        if self._mode == "phase_based":
            return self._execute_phase_based(prepared, task, client, max_tokens, temperature)
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
        """Multi-turn loop with per-turn tool filtering.

        Unlike the default execute() which sets tools once in prepare(),
        phase_based mode changes available tools at each turn by calling
        filter_tools() with the current turn number. This enables the
        explore-then-answer pattern where early turns have limited tools
        (list/read only) and later turns unlock all tools.
        """
        import json

        messages: list[dict] = list(prepared.messages)
        all_tools = prepared.tools or []
        generations = []
        max_turns = 10
        total_tool_calls = 0
        tools_used: set[str] = set()

        for turn in range(max_turns):
            turn_tools = filter_tools(all_tools, "phase_based", turn=turn, max_turns=max_turns)
            generation = client.complete(
                messages, tools=turn_tools, max_tokens=max_tokens, temperature=temperature,
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
                # Dispatch tool calls using inner strategy's _execute_tool
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
        total_cost = sum(g.cost for g in generations if g.cost is not None) or None

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
```

> **Note:** The `execute()` method above replaces the simpler delegation-only version
> shown earlier. For non-phase_based modes, it delegates to the inner strategy. For
> phase_based mode, it implements its own multi-turn loop (like ToolBasedStrategy) that
> calls `filter_tools()` on each turn, providing different tools at different turns.

**Append test** to `agent-evals/tests/test_dynamic_tools_modifier.py`:

```python
class TestPhaseBasedExecuteLoop:
    def test_phase_based_changes_tools_during_execution(self):
        """Phase-based mode provides different tools at different turns."""
        from agent_evals.context.modifiers.dynamic_tools import DynamicToolModifier, filter_tools
        from unittest.mock import MagicMock
        import json

        inner = MagicMock()
        inner.name.return_value = "mcp_native"
        inner._execute_tool.return_value = "tool result"

        modifier = DynamicToolModifier(inner, mode="phase_based")

        # Prepared context with all tools
        prepared = MagicMock()
        prepared.messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Question"},
        ]
        prepared.tools = [
            {"function": {"name": "list_docs"}},
            {"function": {"name": "read_doc"}},
            {"function": {"name": "search_docs"}},
        ]
        prepared.strategy_metadata = {}

        task = MagicMock()
        client = MagicMock()

        # Turn 0 (explore): agent calls list_docs (should be available)
        gen0 = MagicMock()
        gen0.content = None
        gen0.tool_calls = [{"id": "tc0", "function": {"name": "list_docs", "arguments": "{}"}}]
        gen0.prompt_tokens = 10
        gen0.completion_tokens = 5
        gen0.total_tokens = 15
        gen0.cost = 0.001

        # Turn 1: agent responds (no more tool calls)
        gen1 = MagicMock()
        gen1.content = "The answer."
        gen1.tool_calls = None
        gen1.prompt_tokens = 15
        gen1.completion_tokens = 5
        gen1.total_tokens = 20
        gen1.cost = 0.001

        client.complete.side_effect = [gen0, gen1]

        result = modifier.execute(prepared, task, client, 1024, 0.0)
        assert result.final_response == "The answer."
        assert result.strategy_metadata["dynamic_tools_mode"] == "phase_based"
        assert result.strategy_metadata["turns"] == 2

        # Verify that tools were filtered per-turn: first call should NOT have search_docs
        first_call_tools = client.complete.call_args_list[0]
        first_tools = first_call_tools[1].get("tools", first_call_tools[0][1] if len(first_call_tools[0]) > 1 else [])
        # Turn 0 out of max_turns=10 -> explore phase (first half = turns 0-4)
        explore_tools = filter_tools(prepared.tools, "phase_based", turn=0, max_turns=10)
        explore_names = [t["function"]["name"] for t in explore_tools]
        assert "list_docs" in explore_names
        assert "search_docs" not in explore_names
```

### Step 4: Run tests

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_dynamic_tools_modifier.py -v
```

### Step 5: Run full suite and commit

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -v --tb=short 2>&1 | tail -10
git add agent-evals/src/agent_evals/context/modifiers/dynamic_tools.py \
  agent-evals/tests/test_dynamic_tools_modifier.py
git commit -m "feat(context): add dynamic tool availability modifier

Four modes: restricted (no search), progressive (unlock over turns),
phase_based (explore vs answer phases), full (baseline). Tests whether
doc structure compensates for fewer tools.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 9: KV-Cache Friendliness Report (C8)

**Purpose:** Measure how format stability affects caching costs. Track cached_tokens and cache_write_tokens from Phase B, correlate with format characteristics.

**Depends on:** Phase B CostMetrics with cached_tokens, cache_write_tokens fields.

**Files:**
- Create: `agent-evals/src/agent_evals/reports/cache_analysis.py`
- Create: `agent-evals/tests/test_cache_analysis.py`

### Step 1: Write failing tests

**Create** `agent-evals/tests/test_cache_analysis.py`:

```python
"""Tests for KV-cache friendliness analysis."""

from __future__ import annotations

import pytest


class TestCacheHitRate:
    def test_compute_cache_hit_rate(self):
        from agent_evals.reports.cache_analysis import compute_cache_hit_rate
        rate = compute_cache_hit_rate(cached_tokens=400, prompt_tokens=1000)
        assert rate == pytest.approx(0.4)

    def test_zero_prompt_tokens(self):
        from agent_evals.reports.cache_analysis import compute_cache_hit_rate
        rate = compute_cache_hit_rate(cached_tokens=0, prompt_tokens=0)
        assert rate == 0.0


class TestCacheFriendlinessScore:
    def test_high_hit_rate_scores_well(self):
        from agent_evals.reports.cache_analysis import cache_friendliness_score
        trials = [
            {"cached_tokens": 800, "prompt_tokens": 1000, "variant_name": "yaml"},
            {"cached_tokens": 750, "prompt_tokens": 1000, "variant_name": "yaml"},
        ]
        score = cache_friendliness_score(trials)
        assert score > 0.7

    def test_low_hit_rate_scores_poorly(self):
        from agent_evals.reports.cache_analysis import cache_friendliness_score
        trials = [
            {"cached_tokens": 100, "prompt_tokens": 1000, "variant_name": "random"},
            {"cached_tokens": 50, "prompt_tokens": 1000, "variant_name": "random"},
        ]
        score = cache_friendliness_score(trials)
        assert score < 0.2


class TestCacheAnalysisReport:
    def test_build_report_groups_by_variant(self):
        from agent_evals.reports.cache_analysis import build_cache_report
        trials = [
            {"cached_tokens": 800, "prompt_tokens": 1000, "variant_name": "yaml", "cache_write_tokens": 200},
            {"cached_tokens": 100, "prompt_tokens": 1000, "variant_name": "random", "cache_write_tokens": 900},
        ]
        report = build_cache_report(trials)
        assert "yaml" in report
        assert "random" in report

    def test_empty_trials(self):
        from agent_evals.reports.cache_analysis import build_cache_report
        report = build_cache_report([])
        assert isinstance(report, dict)


class TestSequentialCacheTest:
    def test_sequential_tasks_track_cache_growth(self):
        """run_sequential_cache_test tracks how cached_tokens grows."""
        from agent_evals.reports.cache_analysis import run_sequential_cache_test
        from unittest.mock import MagicMock

        variant = MagicMock()
        variant.metadata.return_value.name = "yaml"

        tasks = [MagicMock() for _ in range(3)]
        for i, task in enumerate(tasks):
            task.definition.question = f"Question {i}"

        client = MagicMock()
        # Simulate increasing cached_tokens over sequential calls
        gens = []
        for i in range(3):
            gen = MagicMock()
            gen.content = f"Answer {i}"
            gen.prompt_tokens = 1000
            gen.completion_tokens = 50
            gen.total_tokens = 1050
            gen.cost = 0.001
            gen.cached_tokens = 100 * (i + 1)  # 100, 200, 300
            gens.append(gen)
        client.complete.side_effect = gens

        results = run_sequential_cache_test(variant, tasks, client)
        assert len(results) == 3
        # Each result should have cached_tokens
        for r in results:
            assert "cached_tokens" in r
        # cached_tokens should grow
        assert results[2]["cached_tokens"] > results[0]["cached_tokens"]

    def test_prefix_stability_score(self):
        """prefix_stability_score measures consistency of cached_tokens."""
        from agent_evals.reports.cache_analysis import prefix_stability_score

        # Stable caching: consistent cached_tokens
        stable_trials = [
            {"cached_tokens": 500, "prompt_tokens": 1000},
            {"cached_tokens": 500, "prompt_tokens": 1000},
            {"cached_tokens": 500, "prompt_tokens": 1000},
        ]
        stable_score = prefix_stability_score(stable_trials)

        # Unstable caching: varying cached_tokens
        unstable_trials = [
            {"cached_tokens": 100, "prompt_tokens": 1000},
            {"cached_tokens": 800, "prompt_tokens": 1000},
            {"cached_tokens": 200, "prompt_tokens": 1000},
        ]
        unstable_score = prefix_stability_score(unstable_trials)

        assert stable_score > unstable_score
        assert 0.0 <= stable_score <= 1.0
        assert 0.0 <= unstable_score <= 1.0


class TestFormatCacheCorrelation:
    def test_format_cache_correlation(self):
        """correlate_format_with_cache computes correlations."""
        from agent_evals.reports.cache_analysis import correlate_format_with_cache

        trials = [
            {"cached_tokens": 800, "prompt_tokens": 1000, "variant_name": "yaml"},
            {"cached_tokens": 700, "prompt_tokens": 1000, "variant_name": "yaml"},
            {"cached_tokens": 200, "prompt_tokens": 1000, "variant_name": "flat"},
            {"cached_tokens": 150, "prompt_tokens": 1000, "variant_name": "flat"},
        ]
        variant_metadata = {
            "yaml": {"hierarchy_depth": 3, "serialization": "yaml"},
            "flat": {"hierarchy_depth": 1, "serialization": "plain"},
        }
        correlation = correlate_format_with_cache(trials, variant_metadata)
        assert isinstance(correlation, dict)
        assert "hierarchy_depth_correlation" in correlation
```

### Step 2: Run tests to verify they fail

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_cache_analysis.py -v
```

### Step 3: Implement cache analysis

**Create** `agent-evals/src/agent_evals/reports/cache_analysis.py`:

```python
"""KV-cache friendliness analysis.

Measures how format stability affects caching costs by tracking
cached_tokens and cache_write_tokens from Phase B CostMetrics.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def compute_cache_hit_rate(
    cached_tokens: int, prompt_tokens: int,
) -> float:
    """Compute cache hit rate as ratio of cached to prompt tokens."""
    if prompt_tokens == 0:
        return 0.0
    return cached_tokens / prompt_tokens


def cache_friendliness_score(trials: list[dict[str, Any]]) -> float:
    """Compute average cache hit rate across trials."""
    if not trials:
        return 0.0
    rates = [
        compute_cache_hit_rate(
            t.get("cached_tokens", 0),
            t.get("prompt_tokens", 0),
        )
        for t in trials
    ]
    return sum(rates) / len(rates)


def build_cache_report(
    trials: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    """Build cache friendliness report grouped by variant.

    Returns dict mapping variant_name to cache statistics:
    - mean_hit_rate: average cache hit rate
    - mean_write_tokens: average cache write tokens
    - total_trials: number of trials
    """
    if not trials:
        return {}

    by_variant: dict[str, list[dict]] = defaultdict(list)
    for trial in trials:
        variant = trial.get("variant_name", "unknown")
        by_variant[variant].append(trial)

    report: dict[str, dict[str, float]] = {}
    for variant, variant_trials in sorted(by_variant.items()):
        hit_rates = [
            compute_cache_hit_rate(
                t.get("cached_tokens", 0),
                t.get("prompt_tokens", 0),
            )
            for t in variant_trials
        ]
        write_tokens = [
            t.get("cache_write_tokens", 0) for t in variant_trials
        ]
        report[variant] = {
            "mean_hit_rate": sum(hit_rates) / len(hit_rates),
            "mean_write_tokens": sum(write_tokens) / len(write_tokens),
            "total_trials": len(variant_trials),
        }

    return report


def run_sequential_cache_test(
    variant: Any,
    tasks: list[Any],
    client: Any,
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> list[dict]:
    """Run the same variant against multiple tasks in sequence WITHOUT
    clearing the conversation, measuring how cached_tokens grows.

    Args:
        variant: The variant being tested.
        tasks: List of tasks to run sequentially.
        client: LLM client for completions.
        max_tokens: Max tokens per completion.
        temperature: Sampling temperature.

    Returns:
        List of dicts with cached_tokens, prompt_tokens, and completion info
        for each sequential task.
    """
    results: list[dict] = []
    messages: list[dict] = [
        {"role": "system", "content": "Answer based on documentation."},
    ]

    for i, task in enumerate(tasks):
        question = getattr(task.definition, "question", f"Task {i}")
        messages.append({"role": "user", "content": question})

        generation = client.complete(
            messages, max_tokens=max_tokens, temperature=temperature,
        )

        content = generation.content or ""
        messages.append({"role": "assistant", "content": content})

        results.append({
            "position": i,
            "cached_tokens": getattr(generation, "cached_tokens", 0),
            "prompt_tokens": generation.prompt_tokens,
            "completion_tokens": generation.completion_tokens,
            "total_tokens": generation.total_tokens,
            "variant_name": variant.metadata().name if hasattr(variant, "metadata") else "unknown",
        })

    return results


def prefix_stability_score(trials: list[dict[str, Any]]) -> float:
    """Measure consistency of cached_tokens across sequential tasks.

    Higher score = more stable prefix = better caching behavior.
    Uses coefficient of variation (1 - CV) to score stability.

    Args:
        trials: List of dicts with 'cached_tokens' and 'prompt_tokens'.

    Returns:
        Stability score between 0.0 and 1.0.
    """
    if not trials:
        return 0.0

    cache_rates = [
        compute_cache_hit_rate(
            t.get("cached_tokens", 0),
            t.get("prompt_tokens", 0),
        )
        for t in trials
    ]

    if not cache_rates:
        return 0.0

    mean = sum(cache_rates) / len(cache_rates)
    if mean == 0:
        return 0.0

    # Coefficient of variation
    variance = sum((r - mean) ** 2 for r in cache_rates) / len(cache_rates)
    std_dev = variance ** 0.5
    cv = std_dev / mean if mean > 0 else 1.0

    # Invert: low CV = high stability
    return max(0.0, min(1.0, 1.0 - cv))


def correlate_format_with_cache(
    trials: list[dict[str, Any]],
    variant_metadata: dict[str, dict[str, Any]],
) -> dict:
    """Compute correlation between format properties and cache hit rates.

    Args:
        trials: List of trial dicts with cached_tokens, prompt_tokens, variant_name.
        variant_metadata: Dict mapping variant_name to format properties
            (hierarchy_depth, positioning_stability, serialization, etc.)

    Returns:
        Dict with correlation values for each numeric format property.
    """
    if not trials or not variant_metadata:
        return {}

    # Group cache hit rates by variant
    variant_rates: dict[str, list[float]] = defaultdict(list)
    for trial in trials:
        vname = trial.get("variant_name", "unknown")
        rate = compute_cache_hit_rate(
            trial.get("cached_tokens", 0),
            trial.get("prompt_tokens", 0),
        )
        variant_rates[vname].append(rate)

    # Mean cache rate per variant
    mean_rates: dict[str, float] = {
        v: sum(rates) / len(rates) for v, rates in variant_rates.items() if rates
    }

    # Find numeric properties in variant_metadata
    result: dict[str, float] = {}
    all_props: set[str] = set()
    for meta in variant_metadata.values():
        for k, v in meta.items():
            if isinstance(v, (int, float)):
                all_props.add(k)

    for prop in sorted(all_props):
        # Build paired lists for correlation
        x_vals: list[float] = []
        y_vals: list[float] = []
        for vname, rate in mean_rates.items():
            if vname in variant_metadata and prop in variant_metadata[vname]:
                val = variant_metadata[vname][prop]
                if isinstance(val, (int, float)):
                    x_vals.append(float(val))
                    y_vals.append(rate)

        if len(x_vals) >= 2:
            # Simple Pearson correlation
            n = len(x_vals)
            mean_x = sum(x_vals) / n
            mean_y = sum(y_vals) / n
            cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_vals, y_vals)) / n
            std_x = (sum((x - mean_x) ** 2 for x in x_vals) / n) ** 0.5
            std_y = (sum((y - mean_y) ** 2 for y in y_vals) / n) ** 0.5
            if std_x > 0 and std_y > 0:
                result[f"{prop}_correlation"] = round(cov / (std_x * std_y), 4)
            else:
                result[f"{prop}_correlation"] = 0.0

    return result


def get_variant_format_properties(variant_name: str) -> dict[str, float]:
    """Map variant name to numeric format properties for correlation analysis.

    Properties:
    - hierarchy_depth: 0 (flat) to 4 (deep nesting)
    - positioning_stability: 0.0 (random) to 1.0 (fixed order)
    - serialization_complexity: 0.0 (plain text) to 1.0 (structured YAML)
    - metadata_richness: 0.0 (path only) to 1.0 (full summary+tokens+related)
    """
    # Mapping based on known variant properties from axes 1-10
    PROPERTIES: dict[str, dict[str, float]] = {
        "flat": {"hierarchy_depth": 0, "positioning_stability": 0.5, "serialization_complexity": 0.0, "metadata_richness": 0.2},
        "2-tier": {"hierarchy_depth": 2, "positioning_stability": 0.8, "serialization_complexity": 0.2, "metadata_richness": 0.4},
        "3-tier": {"hierarchy_depth": 3, "positioning_stability": 0.8, "serialization_complexity": 0.3, "metadata_richness": 0.5},
        "4-tier": {"hierarchy_depth": 4, "positioning_stability": 0.9, "serialization_complexity": 0.3, "metadata_richness": 0.6},
        "yaml": {"hierarchy_depth": 2, "positioning_stability": 1.0, "serialization_complexity": 1.0, "metadata_richness": 0.7},
        "json": {"hierarchy_depth": 2, "positioning_stability": 1.0, "serialization_complexity": 0.9, "metadata_richness": 0.7},
        "xml": {"hierarchy_depth": 2, "positioning_stability": 1.0, "serialization_complexity": 0.8, "metadata_richness": 0.6},
        "markdown": {"hierarchy_depth": 2, "positioning_stability": 0.7, "serialization_complexity": 0.3, "metadata_richness": 0.5},
        "random": {"hierarchy_depth": 1, "positioning_stability": 0.0, "serialization_complexity": 0.1, "metadata_richness": 0.2},
        "alphabetical": {"hierarchy_depth": 1, "positioning_stability": 1.0, "serialization_complexity": 0.1, "metadata_richness": 0.2},
        "path-only": {"hierarchy_depth": 1, "positioning_stability": 0.5, "serialization_complexity": 0.0, "metadata_richness": 0.0},
        "summary": {"hierarchy_depth": 1, "positioning_stability": 0.5, "serialization_complexity": 0.2, "metadata_richness": 0.6},
        "detailed": {"hierarchy_depth": 2, "positioning_stability": 0.7, "serialization_complexity": 0.4, "metadata_richness": 1.0},
    }
    # Default properties for unknown variants
    default = {"hierarchy_depth": 1, "positioning_stability": 0.5, "serialization_complexity": 0.3, "metadata_richness": 0.3}
    return PROPERTIES.get(variant_name, default)
```

**Update** `correlate_format_with_cache()` to use `get_variant_format_properties()` instead of requiring a raw metadata dict. Change its signature and implementation:

```python
def correlate_format_with_cache(
    trials: list[dict[str, Any]],
    variant_metadata: dict[str, dict[str, Any]] | None = None,
) -> dict:
    """Compute correlation between format properties and cache hit rates.

    If variant_metadata is not provided, uses get_variant_format_properties()
    to automatically map variant names to numeric format properties.
    """
    if not trials:
        return {}

    # Auto-map variant names to properties if metadata not provided
    if variant_metadata is None:
        variant_names = {t.get("variant_name", "unknown") for t in trials}
        variant_metadata = {
            name: get_variant_format_properties(name) for name in variant_names
        }

    # ... rest of existing implementation unchanged ...
```

**Append tests** to `agent-evals/tests/test_cache_analysis.py`:

```python
class TestVariantFormatProperties:
    def test_variant_format_properties_maps_known_variants(self):
        """Known variants return meaningful numeric properties."""
        from agent_evals.reports.cache_analysis import get_variant_format_properties
        props = get_variant_format_properties("yaml")
        assert props["serialization_complexity"] > 0.5
        props_flat = get_variant_format_properties("flat")
        assert props_flat["hierarchy_depth"] == 0

    def test_unknown_variant_returns_defaults(self):
        """Unknown variants return default numeric properties."""
        from agent_evals.reports.cache_analysis import get_variant_format_properties
        props = get_variant_format_properties("nonexistent-variant")
        assert "hierarchy_depth" in props
        assert "positioning_stability" in props
        assert "serialization_complexity" in props
        assert "metadata_richness" in props

    def test_correlate_format_with_cache_auto_maps(self):
        """correlate_format_with_cache works without explicit metadata dict."""
        from agent_evals.reports.cache_analysis import correlate_format_with_cache
        trials = [
            {"cached_tokens": 800, "prompt_tokens": 1000, "variant_name": "yaml"},
            {"cached_tokens": 700, "prompt_tokens": 1000, "variant_name": "yaml"},
            {"cached_tokens": 200, "prompt_tokens": 1000, "variant_name": "flat"},
            {"cached_tokens": 150, "prompt_tokens": 1000, "variant_name": "flat"},
        ]
        # No variant_metadata argument — should auto-map
        correlation = correlate_format_with_cache(trials)
        assert isinstance(correlation, dict)
```

### Step 4: Run tests

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_cache_analysis.py -v
```

### Step 5: Run full suite and commit

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -v --tb=short 2>&1 | tail -10
git add agent-evals/src/agent_evals/reports/cache_analysis.py \
  agent-evals/tests/test_cache_analysis.py
git commit -m "feat(reports): add KV-cache analysis with sequential testing and correlation

Tracks cached_tokens and cache_write_tokens from Phase B.
Computes cache hit rates per variant. Includes sequential cache
test runner, prefix stability scoring, and format-cache correlation
analysis.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 10: Wire Hallucination + Cache into Runner

**Purpose:** Connect hallucination detection and cache tracking into the trial execution flow.

**Files:**
- Modify: `agent-evals/src/agent_evals/runner.py` (metrics dict population)
- Modify: `agent-evals/tests/test_runner.py`

### Step 1: Write failing tests

**Append to** `agent-evals/tests/test_runner.py`:

```python
class TestHallucinationMetricsIntegration:
    def test_hallucination_score_in_metrics_when_judge_called(self):
        """When judge is called, hallucination metrics should be populated."""
        # This verifies the runner populates metrics["hallucination_score"]
        # when _call_judge is invoked and hallucination detection is enabled
        from agent_evals.runner import TrialResult
        result = TrialResult(
            task_id="test", task_type="retrieval", variant_name="flat",
            repetition=1, score=0.8, metrics={"hallucination_score": 0.1},
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=0.001, latency_seconds=1.0, response="answer", cached=False,
        )
        assert "hallucination_score" in result.metrics


class TestCacheMetricsIntegration:
    def test_cache_hit_rate_in_strategy_metadata(self):
        """Cache hit rate flows through strategy_metadata."""
        from agent_evals.runner import TrialResult
        result = TrialResult(
            task_id="test", task_type="retrieval", variant_name="yaml",
            repetition=1, score=0.8, metrics={},
            prompt_tokens=1000, completion_tokens=50, total_tokens=1050,
            cost=0.001, latency_seconds=1.0, response="answer", cached=False,
            strategy_metadata={"cache_hit_rate": 0.45},
        )
        assert result.strategy_metadata["cache_hit_rate"] == 0.45
```

### Step 2: Add hallucination rate to VariantSummary

**Append to** `agent-evals/tests/test_runner.py`:

```python
class TestHallucinationRateInVariantSummary:
    def test_hallucination_rate_in_variant_summary(self):
        """VariantSummary should include mean hallucination_score per variant."""
        from agent_evals.runner import TrialResult, compute_variant_summary

        trials = [
            TrialResult(
                task_id="t1", task_type="retrieval", variant_name="yaml",
                repetition=1, score=0.9, metrics={"hallucination_score": 0.1},
                prompt_tokens=100, completion_tokens=50, total_tokens=150,
                cost=0.001, latency_seconds=1.0, response="a1", cached=False,
            ),
            TrialResult(
                task_id="t2", task_type="retrieval", variant_name="yaml",
                repetition=1, score=0.8, metrics={"hallucination_score": 0.3},
                prompt_tokens=100, completion_tokens=50, total_tokens=150,
                cost=0.001, latency_seconds=1.0, response="a2", cached=False,
            ),
        ]
        summary = compute_variant_summary(trials, variant_name="yaml")
        assert "hallucination_rate" in summary
        assert summary["hallucination_rate"] == pytest.approx(0.2)
```

### Step 3: Implement hallucination wiring in runner

**Modify** `agent-evals/src/agent_evals/runner.py`:

1. In `_call_judge()`, add hallucination detection call when enabled:

```python
# After the existing judge scoring:
if self._config.get("hallucination_detection", False):
    from agent_evals.judge.hallucination import (
        build_hallucination_prompt,
        parse_hallucination_result,
    )
    hallucination_messages = build_hallucination_prompt(
        response=response,
        source_docs=rendered_index,
        question=task.definition.question,
    )
    hallucination_gen = self._judge_client.complete(
        hallucination_messages, max_tokens=512, temperature=0.0,
    )
    hallucination_result = parse_hallucination_result(
        hallucination_gen.content or "",
    )
    trial_metrics["hallucination_score"] = hallucination_result.score
    trial_metrics["hallucination_type"] = hallucination_result.hallucination_type
```

2. Add `compute_variant_summary()` function (or extend existing aggregator):

```python
def compute_variant_summary(
    trials: list[TrialResult],
    variant_name: str,
) -> dict:
    """Compute summary statistics for a variant including hallucination rate."""
    variant_trials = [t for t in trials if t.variant_name == variant_name]
    if not variant_trials:
        return {}

    scores = [t.score for t in variant_trials]
    h_scores = [
        t.metrics.get("hallucination_score", 0.0)
        for t in variant_trials
        if "hallucination_score" in t.metrics
    ]

    summary = {
        "variant_name": variant_name,
        "mean_score": sum(scores) / len(scores),
        "trial_count": len(variant_trials),
    }

    if h_scores:
        summary["hallucination_rate"] = sum(h_scores) / len(h_scores)

    return summary
```

3. Add hallucination as a second Taguchi response variable:

> **NOTE: Hallucination is NOT a Taguchi factor (factors are format axes 1-12).**
> Hallucination is an ADDITIONAL RESPONSE VARIABLE alongside accuracy.
>
> The existing Taguchi analysis uses `compute_sn_ratios()` with `quality_type`
> `"larger_is_better"` for accuracy. For hallucination, add a parallel analysis
> using `quality_type` `"smaller_is_better"` (lower hallucination = better).
>
> This means for each Taguchi screening, TWO analyses run:
> 1. **Accuracy analysis:** which format levels maximize accuracy (`larger_is_better`)
> 2. **Hallucination analysis:** which format levels minimize hallucination (`smaller_is_better`)

**Add test** to `agent-evals/tests/test_runner.py`:

```python
class TestTaguchiHallucinationAsResponseVariable:
    def test_taguchi_hallucination_as_response_variable(self):
        """Hallucination scores feed into Taguchi as a second response variable
        with smaller_is_better quality type."""
        from agent_evals.taguchi.analysis import compute_sn_ratios
        # Use hallucination scores as response values
        hallucination_scores = [0.1, 0.3, 0.05, 0.2, 0.15]
        sn = compute_sn_ratios(hallucination_scores, "smaller_is_better")
        assert all(s <= 0 for s in sn)  # S/N ratios for smaller_is_better are <= 0
```

**Add to DOE pipeline** (in `agent-evals/src/agent_evals/pipeline.py` or runner screening logic):

```python
# After accuracy screening:
if hallucination_scores:
    hallucination_sn = compute_sn_ratios(hallucination_scores, "smaller_is_better")
    hallucination_anova = run_anova(
        hallucination_sn, factors, orthogonal_array,
    )
    phase_results.hallucination_main_effects = hallucination_anova.main_effects
```

4. Add `hallucination_rate` as queryable column in observatory trials table:

```python
# In observatory/run_manager.py, add to CREATE TABLE trials:
# hallucination_score REAL DEFAULT NULL,
# hallucination_type TEXT DEFAULT NULL,
```

### Step 4: Run and verify tests pass

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_runner.py -k "Hallucination or Cache" -v
```

### Step 5: Run full suite and commit

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -v --tb=short 2>&1 | tail -10
git add agent-evals/src/agent_evals/runner.py \
  agent-evals/src/agent_evals/observatory/run_manager.py \
  agent-evals/tests/test_runner.py
git commit -m "feat(runner): wire hallucination detection as first-class metric

Add hallucination_score and hallucination_type to trial metrics
when hallucination detection is enabled. Add hallucination_rate
to VariantSummary aggregation. Add queryable columns to observatory
trials table.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 11: CLI Wiring for New Strategies and Axes

**Purpose:** Wire MCP-native and compression strategies into CLI, update help text.

**Files:**
- Modify: `agent-evals/src/agent_evals/cli.py`
- Modify: `agent-evals/tests/test_evals_cli.py`

### Step 1: Write failing tests

**Append to** `agent-evals/tests/test_evals_cli.py`:

```python
class TestPhaseCSrategyFlags:
    def test_mcp_native_accepted(self):
        """--context-strategy mcp_native should be accepted."""
        # Test that resolve_config accepts mcp_native as valid
        from agent_evals.cli import resolve_config
        config = resolve_config(
            {"context_strategy": "mcp_native", "model": "test-model"},
            raw_yaml=None,
        )
        assert config["context_strategy"] == "mcp_native"

    def test_compression_accepted(self):
        """--context-strategy compression should be accepted."""
        from agent_evals.cli import resolve_config
        config = resolve_config(
            {"context_strategy": "compression", "model": "test-model"},
            raw_yaml=None,
        )
        assert config["context_strategy"] == "compression"
```

### Step 2: Update CLI help text

**Modify** `agent-evals/src/agent_evals/cli.py` line ~280:

```python
help="Context delivery strategy (full_context, system_prompt, rag, tool_based, mcp_native, compression)",
```

### Step 3: Update StrategyConfig builder

**Modify** `_build_strategy_config()` in `cli.py` to pass through compression_method:

```python
compression_method=yaml_sc.get("compression_method", "algorithmic"),
```

### Step 4: Run tests and commit

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_evals_cli.py -v --tb=short
git add agent-evals/src/agent_evals/cli.py agent-evals/tests/test_evals_cli.py
git commit -m "feat(cli): wire Phase C strategies into CLI flags

Add mcp_native and compression to --context-strategy help text.
Wire compression_method through StrategyConfig builder.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 12: Integration Tests

**Purpose:** End-to-end tests verifying Phase C components work together.

**Files:**
- Create: `agent-evals/tests/test_phase_c_integration.py`

### Step 1: Write integration tests

**Create** `agent-evals/tests/test_phase_c_integration.py`:

```python
"""Phase C integration tests — verify all components work together."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from agent_index.models import DocFile, DocTree


def _make_doc_tree() -> DocTree:
    return DocTree(
        files={
            "guides/auth.md": DocFile(
                rel_path="guides/auth.md",
                content="# Auth\nUse OAuth2 for authentication.",
                size_bytes=35,
                token_count=8,
                tier="required",
                section="Guides",
                summary="OAuth2 auth guide",
                related=["api/users.md"],
            ),
            "api/users.md": DocFile(
                rel_path="api/users.md",
                content="# Users API\nGET /users returns a list of users.",
                size_bytes=48,
                token_count=12,
                tier="recommended",
                section="API",
                summary="Users endpoint reference",
                related=[],
            ),
        },
        scanned_at=datetime(2026, 1, 1),
        source="/test",
        total_tokens=20,
    )


class TestMCPNativeEndToEnd:
    def test_full_flow(self):
        """MCP-native strategy: setup -> prepare -> execute -> result."""
        from agent_evals.context.mcp_native import MCPNativeStrategy
        from tests.conftest import make_mock_task
        strategy = MCPNativeStrategy(max_turns=5)
        doc_tree = _make_doc_tree()
        strategy.setup("index content", doc_tree)
        task = make_mock_task()
        prepared = strategy.prepare("index content", task, doc_tree)

        client = MagicMock()
        gen = MagicMock()
        gen.content = "OAuth2 is used for authentication."
        gen.tool_calls = None
        gen.prompt_tokens = 50
        gen.completion_tokens = 10
        gen.total_tokens = 60
        gen.cost = 0.002
        client.complete.return_value = gen

        result = strategy.execute(prepared, task, client, 1024, 0.0)
        assert "OAuth2" in result.final_response
        assert result.strategy_metadata["resource_count"] == 2
        strategy.teardown()


class TestCompressionEndToEnd:
    def test_full_flow(self):
        """Compression strategy: setup -> prepare -> execute."""
        from agent_evals.context.compression import CompressionStrategy
        from tests.conftest import make_mock_task
        strategy = CompressionStrategy(method="algorithmic")
        doc_tree = _make_doc_tree()
        rendered = "# Documentation\n\nThis is the full rendered index."
        strategy.setup(rendered, doc_tree)
        task = make_mock_task()
        prepared = strategy.prepare(rendered, task, doc_tree)
        assert prepared.strategy_metadata["compression_method"] == "algorithmic"
        assert prepared.strategy_metadata["compression_ratio"] <= 1.0


class TestNewAxesDiscovery:
    def test_axis_11_discovered(self):
        from agent_evals.variants.registry import get_variants_for_axis, load_all
        load_all()
        variants = get_variants_for_axis(11)
        assert len(variants) >= 8  # 4 description quality + 4 tool set size

    def test_axis_12_discovered(self):
        from agent_evals.variants.registry import get_variants_for_axis, load_all
        load_all()
        variants = get_variants_for_axis(12)
        assert len(variants) >= 9  # 5 verbosity + 4 ablative

    def test_axes_11_12_in_taguchi_factors(self):
        from agent_evals.taguchi.factors import build_factors_from_axes
        from agent_evals.variants.registry import load_all
        load_all()
        # Build axes dict manually
        from agent_evals.variants.registry import get_all_variants
        axes: dict[int, list[str]] = {}
        for v in get_all_variants():
            meta = v.metadata()
            if meta.axis == 0:
                continue
            axes.setdefault(meta.axis, []).append(meta.name)
        factors = build_factors_from_axes(axes)
        factor_names = [f.name for f in factors]
        assert any("11" in name or "tool_desc" in name.lower() for name in factor_names)
        assert any("12" in name or "instruction" in name.lower() for name in factor_names)


class TestHallucinationDetection:
    def test_full_detection_flow(self):
        from agent_evals.judge.hallucination import (
            build_hallucination_prompt,
            parse_hallucination_result,
        )
        messages = build_hallucination_prompt(
            response="OAuth2 tokens expire in 1 hour.",
            source_docs="# Auth\nOAuth2 tokens expire after 1 hour.",
            question="How long do tokens last?",
        )
        assert len(messages) == 2
        result = parse_hallucination_result(
            '{"hallucination_score": 0.0, "type": "grounded", "flagged_claims": []}',
        )
        assert result.score == 0.0
        assert result.hallucination_type == "grounded"


class TestModifiers:
    def test_compaction_modifier_wraps_strategy(self):
        from agent_evals.context.modifiers.compaction import CompactionModifier
        inner = MagicMock()
        inner.name.return_value = "full_context"
        modifier = CompactionModifier(inner, compaction_ratio=0.5)
        assert "compaction" in modifier.name()

    def test_dynamic_tools_modifier_wraps_strategy(self):
        from agent_evals.context.modifiers.dynamic_tools import DynamicToolModifier
        inner = MagicMock()
        inner.name.return_value = "tool_based"
        modifier = DynamicToolModifier(inner, mode="restricted")
        assert "restricted" in modifier.name()


class TestCacheAnalysis:
    def test_report_with_variant_data(self):
        from agent_evals.reports.cache_analysis import build_cache_report
        trials = [
            {"cached_tokens": 800, "prompt_tokens": 1000, "variant_name": "yaml", "cache_write_tokens": 200},
            {"cached_tokens": 600, "prompt_tokens": 1000, "variant_name": "yaml", "cache_write_tokens": 400},
            {"cached_tokens": 100, "prompt_tokens": 1000, "variant_name": "random", "cache_write_tokens": 900},
        ]
        report = build_cache_report(trials)
        assert report["yaml"]["mean_hit_rate"] == pytest.approx(0.7)
        assert report["random"]["mean_hit_rate"] == pytest.approx(0.1)
```

### Step 2: Run integration tests

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_phase_c_integration.py -v
```

### Step 3: Run full suite

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -v --tb=short 2>&1 | tail -10
```

### Step 4: Commit

```bash
git add agent-evals/tests/test_phase_c_integration.py
git commit -m "test: add Phase C integration tests

End-to-end tests for MCP-native strategy, compression strategy,
axes 11-12 discovery, hallucination detection, modifiers, and
cache analysis working together.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 13: Final Verification

### Step 1: Run full test suite with coverage

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -v --cov=agent_evals --cov-report=term-missing 2>&1 | tail -30
```

Expected: ALL PASS, 80%+ coverage.

### Step 2: Verify no regressions

Compare test count against Task 0 baseline. Phase C should add ~80-120 new tests.

### Step 3: Verify all Phase C deliverables

```bash
# New strategies
ls agent-evals/src/agent_evals/context/mcp_native.py
ls agent-evals/src/agent_evals/context/compression.py

# New axes
ls agent-evals/src/agent_evals/variants/tool_description.py
ls agent-evals/src/agent_evals/variants/agent_instruction.py

# Hallucination detection
ls agent-evals/src/agent_evals/judge/hallucination.py

# Modifiers
ls agent-evals/src/agent_evals/context/modifiers/compaction.py
ls agent-evals/src/agent_evals/context/modifiers/dynamic_tools.py

# Cache analysis
ls agent-evals/src/agent_evals/reports/cache_analysis.py
```

### Step 4: Final commit if needed

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -v --tb=short 2>&1 | tail -5
```

---

## Task 14: Cross-Strategy Synthesis Report (EXIT CRITERIA)

**Purpose:** Generate the final cross-strategy recommendation by analyzing Taguchi results across all 6 strategies. This is the exit criteria for Phase C -- the deliverable that answers: "For an MCP-based agent reading compressed docs through dynamic tools, use format X with instruction style Y."

**Files:**
- Create: `agent-evals/src/agent_evals/reports/cross_strategy_synthesis.py`
- Create: `agent-evals/tests/test_cross_strategy_synthesis.py`

### Step 1: Write failing tests

**Create** `agent-evals/tests/test_cross_strategy_synthesis.py`:

```python
"""Tests for cross-strategy synthesis report (Phase C exit criteria)."""

from __future__ import annotations

import pytest


class TestCrossStrategyRecommendation:
    def test_cross_strategy_recommendation_generated(self):
        """generate_cross_strategy_recommendation produces a recommendation string."""
        from agent_evals.reports.cross_strategy_synthesis import (
            generate_cross_strategy_recommendation,
        )

        # Simulate Taguchi results from 6 strategies
        phase_results_by_strategy = {
            "full_context": {
                "optimal_levels": {"axis_1": "yaml", "axis_2": "hierarchical", "axis_11": "tool-desc-detailed"},
                "factor_rankings": [("axis_1", 0.15), ("axis_2", 0.10), ("axis_11", 0.08)],
                "mean_score": 0.82,
            },
            "system_prompt": {
                "optimal_levels": {"axis_1": "yaml", "axis_2": "hierarchical", "axis_11": "tool-desc-standard"},
                "factor_rankings": [("axis_1", 0.12), ("axis_2", 0.11), ("axis_11", 0.05)],
                "mean_score": 0.78,
            },
            "rag": {
                "optimal_levels": {"axis_1": "json", "axis_2": "flat", "axis_11": "tool-desc-detailed"},
                "factor_rankings": [("axis_1", 0.18), ("axis_2", 0.06), ("axis_11", 0.09)],
                "mean_score": 0.75,
            },
            "tool_based": {
                "optimal_levels": {"axis_1": "yaml", "axis_2": "hierarchical", "axis_11": "tool-desc-detailed"},
                "factor_rankings": [("axis_1", 0.14), ("axis_11", 0.12), ("axis_2", 0.07)],
                "mean_score": 0.80,
            },
            "mcp_native": {
                "optimal_levels": {"axis_1": "yaml", "axis_2": "hierarchical", "axis_11": "tool-desc-detailed"},
                "factor_rankings": [("axis_11", 0.16), ("axis_1", 0.13), ("axis_2", 0.09)],
                "mean_score": 0.79,
            },
            "compression": {
                "optimal_levels": {"axis_1": "yaml", "axis_2": "flat", "axis_11": "tool-desc-standard"},
                "factor_rankings": [("axis_1", 0.20), ("axis_2", 0.05), ("axis_11", 0.04)],
                "mean_score": 0.73,
            },
        }

        recommendation = generate_cross_strategy_recommendation(
            phase_results_by_strategy,
        )
        assert isinstance(recommendation, str)
        assert len(recommendation) > 100
        # Should mention format recommendation
        assert "format" in recommendation.lower() or "yaml" in recommendation.lower()

    def test_concordance_factors_identified(self):
        """Factors that agree across strategies should be identified."""
        from agent_evals.reports.cross_strategy_synthesis import (
            find_concordant_factors,
        )

        results = {
            "strategy_a": {"optimal_levels": {"axis_1": "yaml", "axis_2": "flat"}},
            "strategy_b": {"optimal_levels": {"axis_1": "yaml", "axis_2": "hierarchical"}},
            "strategy_c": {"optimal_levels": {"axis_1": "yaml", "axis_2": "flat"}},
        }
        concordant = find_concordant_factors(results)
        # axis_1 agrees across all strategies (all "yaml")
        assert "axis_1" in concordant
        assert concordant["axis_1"]["level"] == "yaml"
        assert concordant["axis_1"]["agreement"] >= 0.66

    def test_disagreement_factors_identified(self):
        """Factors where strategies disagree should be flagged."""
        from agent_evals.reports.cross_strategy_synthesis import (
            find_disagreement_factors,
        )

        results = {
            "strategy_a": {"optimal_levels": {"axis_1": "yaml", "axis_2": "flat"}},
            "strategy_b": {"optimal_levels": {"axis_1": "json", "axis_2": "hierarchical"}},
            "strategy_c": {"optimal_levels": {"axis_1": "xml", "axis_2": "flat"}},
        }
        disagreements = find_disagreement_factors(results)
        # axis_1 disagrees across strategies
        assert "axis_1" in disagreements
```

### Step 2: Run tests to verify they fail

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_cross_strategy_synthesis.py -v
```

### Step 3: Implement cross-strategy synthesis

**Create** `agent-evals/src/agent_evals/reports/cross_strategy_synthesis.py`:

```python
"""Cross-strategy synthesis report — Phase C exit criteria.

Analyzes Taguchi results across all strategies and produces the
final recommendation for optimal documentation format.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def find_concordant_factors(
    results: dict[str, dict[str, Any]],
    threshold: float = 0.5,
) -> dict[str, dict[str, Any]]:
    """Find factors where strategies agree on the optimal level.

    Args:
        results: Dict mapping strategy_name to result dict with 'optimal_levels'.
        threshold: Minimum agreement ratio to consider concordant.

    Returns:
        Dict mapping factor_name to {level, agreement, strategies}.
    """
    # Collect all factor->level votes across strategies
    factor_votes: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for strategy_name, result in results.items():
        for factor, level in result.get("optimal_levels", {}).items():
            factor_votes[factor].append((strategy_name, level))

    concordant: dict[str, dict[str, Any]] = {}
    for factor, votes in factor_votes.items():
        levels = [level for _, level in votes]
        counter = Counter(levels)
        most_common_level, count = counter.most_common(1)[0]
        agreement = count / len(votes)
        if agreement >= threshold:
            concordant[factor] = {
                "level": most_common_level,
                "agreement": round(agreement, 4),
                "strategies": [s for s, l in votes if l == most_common_level],
                "total_strategies": len(votes),
            }

    return concordant


def find_disagreement_factors(
    results: dict[str, dict[str, Any]],
    threshold: float = 0.5,
) -> dict[str, dict[str, Any]]:
    """Find factors where strategies disagree on the optimal level.

    Args:
        results: Dict mapping strategy_name to result dict with 'optimal_levels'.
        threshold: Maximum agreement ratio to consider disagreement.

    Returns:
        Dict mapping factor_name to {levels, per_strategy}.
    """
    factor_votes: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for strategy_name, result in results.items():
        for factor, level in result.get("optimal_levels", {}).items():
            factor_votes[factor].append((strategy_name, level))

    disagreements: dict[str, dict[str, Any]] = {}
    for factor, votes in factor_votes.items():
        levels = [level for _, level in votes]
        counter = Counter(levels)
        _, count = counter.most_common(1)[0]
        agreement = count / len(votes)
        if agreement < threshold:
            disagreements[factor] = {
                "levels": dict(counter),
                "per_strategy": {s: l for s, l in votes},
                "agreement": round(agreement, 4),
            }

    return disagreements


def generate_cross_strategy_recommendation(
    phase_results_by_strategy: dict[str, dict[str, Any]],
) -> str:
    """Generate the final cross-strategy recommendation.

    Analyzes Taguchi results across all strategies and produces
    actionable recommendations.

    Uses:
    - Kendall's W concordance to find factors that agree across strategies
    - Per-strategy optimal levels to find where strategies disagree

    Args:
        phase_results_by_strategy: Dict mapping strategy_name to Taguchi
            results dict with 'optimal_levels', 'factor_rankings', 'mean_score'.

    Returns:
        Formatted recommendation string.
    """
    concordant = find_concordant_factors(phase_results_by_strategy)
    disagreements = find_disagreement_factors(phase_results_by_strategy)

    lines: list[str] = [
        "# Cross-Strategy Synthesis Report",
        "",
        f"**Strategies analyzed:** {len(phase_results_by_strategy)}",
        f"**Strategies:** {', '.join(sorted(phase_results_by_strategy.keys()))}",
        "",
    ]

    # Strategy performance summary
    lines.append("## Strategy Performance")
    lines.append("")
    for strategy, result in sorted(
        phase_results_by_strategy.items(),
        key=lambda x: x[1].get("mean_score", 0),
        reverse=True,
    ):
        score = result.get("mean_score", 0)
        lines.append(f"- **{strategy}**: mean_score={score:.4f}")
    lines.append("")

    # Concordant factors (universal recommendations)
    lines.append("## Universal Recommendations (agree across strategies)")
    lines.append("")
    if concordant:
        for factor, info in sorted(concordant.items()):
            agreement_pct = info["agreement"] * 100
            lines.append(
                f"- **{factor}**: Use `{info['level']}` "
                f"({agreement_pct:.0f}% agreement across "
                f"{info['total_strategies']} strategies)"
            )
    else:
        lines.append("- No factors showed universal agreement.")
    lines.append("")

    # Disagreement factors (strategy-specific recommendations)
    lines.append("## Strategy-Specific Recommendations (disagree across strategies)")
    lines.append("")
    if disagreements:
        for factor, info in sorted(disagreements.items()):
            lines.append(f"- **{factor}**: {info['levels']}")
            for strategy, level in sorted(info["per_strategy"].items()):
                lines.append(f"  - {strategy}: `{level}`")
    else:
        lines.append("- All factors agree across strategies.")
    lines.append("")

    # Final recommendation
    lines.append("## Final Recommendation")
    lines.append("")
    if concordant:
        recs = [
            f"{factor}=`{info['level']}`"
            for factor, info in sorted(concordant.items())
        ]
        lines.append(
            f"For an MCP-based agent reading compressed docs through "
            f"dynamic tools, use: {', '.join(recs)}."
        )
    else:
        lines.append(
            "No universal format recommendation possible -- "
            "optimal format depends on the context delivery strategy."
        )

    return "\n".join(lines)


def rank_format_recommendations(
    strategy_phase_results: dict[str, dict[str, Any]],
) -> dict[str, str]:
    """For each strategy, find the optimal format combination.

    Returns dict mapping strategy name to recommended format string:
    {"mcp_native": "2-tier markdown with detailed tool descriptions",
     "compression": "yaml with minimal instructions", ...}
    """
    recommendations: dict[str, str] = {}
    for strategy, results in strategy_phase_results.items():
        optimal_levels = results.get("optimal_levels", {})
        recommendations[strategy] = format_optimal_combination(optimal_levels)
    return recommendations


def format_optimal_combination(optimal_levels: dict[str, str]) -> str:
    """Convert optimal level dict to human-readable recommendation."""
    if not optimal_levels:
        return "no recommendation (no data)"
    parts = []
    for factor, level in sorted(optimal_levels.items()):
        parts.append(f"{level} ({factor})")
    return ", ".join(parts)
```

**Update** `generate_cross_strategy_recommendation()` to call `rank_format_recommendations()` and include per-strategy recommendations in the final output. Add the following before the return statement:

```python
    # Per-strategy format recommendations
    per_strategy_recs = rank_format_recommendations(phase_results_by_strategy)
    lines.append("")
    lines.append("## Per-Strategy Optimal Formats")
    lines.append("")
    for strategy, rec in sorted(per_strategy_recs.items()):
        lines.append(f"- **{strategy}**: {rec}")

    return "\n".join(lines)
```

**Append tests** to `agent-evals/tests/test_cross_strategy_synthesis.py`:

```python
class TestRankFormatRecommendations:
    def test_rank_format_recommendations(self):
        """Produces per-strategy format recommendation from phase results."""
        from agent_evals.reports.cross_strategy_synthesis import rank_format_recommendations

        results = {
            "mcp_native": {
                "optimal_levels": {"axis_1": "yaml", "axis_11": "tool-desc-detailed"},
                "mean_score": 0.79,
            },
            "full_context": {
                "optimal_levels": {"axis_1": "yaml", "axis_2": "hierarchical"},
                "mean_score": 0.82,
            },
        }
        recs = rank_format_recommendations(results)
        assert "mcp_native" in recs
        assert isinstance(recs["mcp_native"], str)
        assert len(recs["mcp_native"]) > 0
        assert "full_context" in recs
        # Recommendations should mention the optimal levels
        assert "yaml" in recs["mcp_native"]

    def test_format_optimal_combination(self):
        """format_optimal_combination produces human-readable string."""
        from agent_evals.reports.cross_strategy_synthesis import format_optimal_combination
        result = format_optimal_combination({"axis_1": "yaml", "axis_2": "hierarchical"})
        assert "yaml (axis_1)" in result
        assert "hierarchical (axis_2)" in result

    def test_format_optimal_combination_empty(self):
        """Empty optimal levels produces 'no recommendation' string."""
        from agent_evals.reports.cross_strategy_synthesis import format_optimal_combination
        result = format_optimal_combination({})
        assert "no recommendation" in result
```

### Step 4: Run tests

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_cross_strategy_synthesis.py -v
```

### Step 5: Run full suite and commit

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -v --tb=short 2>&1 | tail -10
git add agent-evals/src/agent_evals/reports/cross_strategy_synthesis.py \
  agent-evals/tests/test_cross_strategy_synthesis.py
git commit -m "feat(reports): add cross-strategy synthesis report (Phase C exit criteria)

Analyzes Taguchi results across all 6 strategies. Finds concordant
factors (universal recommendations) and disagreement factors
(strategy-specific). Generates final recommendation for optimal
documentation format.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Summary

| Task | Component | New Tests | Commit |
|------|-----------|-----------|--------|
| 0 | Verify baseline | 0 | - |
| 1 | VariantMetadata axis le=13 | 3 | `feat(variants): extend axis range` |
| 2 | MCP-native strategy + resource metadata ablation | ~20 | `feat(context): add MCP-native strategy` |
| 3 | Compression strategy + LLM-summarized + cost pairing + client wiring | ~15 | `feat(context): add compression strategy` |
| 4 | Tool description axis (11) + tool set size (4 variants) | ~20 | `feat(variants): add axis 11` |
| 5 | Agent instruction axis (12) + ETH Zurich ablative (4 variants) | ~22 | `feat(variants): add axis 12` |
| 6 | Hallucination detection | ~8 | `feat(judge): add hallucination detection` |
| 7 | Compaction modifier + multi-task sequence + durability + carryover | ~8 | `feat(context): add compaction modifier` |
| 8 | Dynamic tools modifier + phase_based execute loop | ~9 | `feat(context): add dynamic tools modifier` |
| 9 | Cache analysis + sequential runner + format correlation + variant properties | ~12 | `feat(reports): add cache analysis` |
| 10 | Runner wiring + hallucination as response variable | ~6 | `feat(runner): wire hallucination + cache metrics` |
| 11 | CLI wiring | ~2 | `feat(cli): wire Phase C strategies` |
| 12 | Integration tests | ~8 | `test: Phase C integration tests` |
| 13 | Final verification | 0 | - |
| 14 | Cross-strategy synthesis report + ranking logic (EXIT CRITERIA) | ~6 | `feat(reports): cross-strategy synthesis` |
| **Total** | | **~139** | **~14 commits** |
