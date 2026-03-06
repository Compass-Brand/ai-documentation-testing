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

    def test_axis_13_invalid(self):
        import pytest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            VariantMetadata(
                name="invalid",
                axis=13,
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
axis: int = Field(ge=0, le=12)
```

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

### Step 7: Commit

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

### Step 4: Extend StrategyConfig

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

---

## Task 4: Tool Description Axis (C3) — Axis 11

**Purpose:** Test how tool description quality and tool set size affect agent performance. Anthropic achieved SOTA on SWE-bench primarily through refined tool descriptions.

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


class TestToolDescRegistration:
    def test_all_variants_discoverable(self):
        from agent_evals.variants.registry import get_variants_for_axis, load_all
        load_all()
        axis_11 = get_variants_for_axis(11)
        assert len(axis_11) >= 4
        names = {v.metadata().name for v in axis_11}
        assert "tool-desc-minimal" in names
        assert "tool-desc-standard" in names
        assert "tool-desc-detailed" in names
        assert "tool-desc-adversarial" in names
```

### Step 2: Run tests to verify they fail

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_axis_11_tool_description.py -v
```

Expected: FAIL — module does not exist.

### Step 3: Implement tool description variants

**Create** `agent-evals/src/agent_evals/variants/tool_description.py`:

```python
"""Axis 11: Tool description quality variants.

Tests how tool description quality affects agent performance.
Four levels: minimal (name+types), standard (one-line),
detailed (examples+edge cases), adversarial (vague/misleading).
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
git commit -m "feat(variants): add axis 11 tool description quality variants

Four levels: minimal (name+types), standard (one-line), detailed
(examples+edge cases), adversarial (vague/misleading). Tests how
tool description quality affects agent performance.

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


class TestInstructionRegistration:
    def test_all_variants_discoverable(self):
        from agent_evals.variants.registry import get_variants_for_axis, load_all
        load_all()
        axis_12 = get_variants_for_axis(12)
        assert len(axis_12) >= 5
        names = {v.metadata().name for v in axis_12}
        assert "instruction-none" in names
        assert "instruction-minimal" in names
        assert "instruction-standard" in names
        assert "instruction-verbose" in names
        assert "instruction-overloaded" in names
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
git commit -m "feat(variants): add axis 12 agent instruction verbosity variants

Five verbosity levels testing ETH Zurich AGENTS.md findings:
none, minimal (<60 lines), standard (~150), verbose (300+),
overloaded (500+). Decomposes which content types help vs hurt.

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

### Step 4: Run tests

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_compaction_modifier.py -v
```

### Step 5: Run full suite and commit

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -v --tb=short 2>&1 | tail -10
git add agent-evals/src/agent_evals/context/modifiers/__init__.py \
  agent-evals/src/agent_evals/context/modifiers/compaction.py \
  agent-evals/tests/test_compaction_modifier.py
git commit -m "feat(context): add compaction modifier for multi-session persistence testing

Simulates context compaction between task phases. Tests whether
documentation format survives summarization. Wraps any strategy
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
Three modes: restricted (remove search), progressive (unlock over turns),
full (baseline, all tools).
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


def filter_tools(
    tools: list[dict[str, Any]],
    mode: str = "full",
    turn: int = 0,
) -> list[dict[str, Any]]:
    """Filter tools based on availability mode and turn number."""
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

Three modes: restricted (no search), progressive (unlock over turns),
full (baseline). Tests whether doc structure compensates for fewer tools.

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
git commit -m "feat(reports): add KV-cache friendliness analysis

Tracks cached_tokens and cache_write_tokens from Phase B.
Computes cache hit rates per variant. Reports format stability
vs caching cost tradeoffs.

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

### Step 2: Run and verify tests pass

These tests validate the data model supports the fields. The actual wiring of hallucination into `_call_judge()` and cache metrics into `_run_trial()` depends on Phase A judge module and Phase B CostMetrics being present.

**Implementation note:** The wiring changes to `runner.py` lines 867-888 are:

```python
# In _run_trial(), after scoring (line ~880):
# If hallucination detection enabled and judge called:
if hallucination_result:
    metrics["hallucination_score"] = hallucination_result.score
    metrics["hallucination_type"] = hallucination_result.hallucination_type

# Cache hit rate from Phase B CostMetrics (already in strategy_metadata):
# No runner change needed — Phase B populates this in GenerationResult
```

### Step 3: Run full suite and commit

```bash
~/.local/bin/uv run pytest agent-evals/tests/ -v --tb=short 2>&1 | tail -10
git add agent-evals/tests/test_runner.py
git commit -m "test(runner): add integration tests for hallucination and cache metrics

Validates TrialResult data model supports hallucination_score in
metrics dict and cache_hit_rate in strategy_metadata.

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
        assert len(variants) >= 4

    def test_axis_12_discovered(self):
        from agent_evals.variants.registry import get_variants_for_axis, load_all
        load_all()
        variants = get_variants_for_axis(12)
        assert len(variants) >= 5

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

## Summary

| Task | Component | New Tests | Commit |
|------|-----------|-----------|--------|
| 0 | Verify baseline | 0 | - |
| 1 | VariantMetadata axis le=12 | 3 | `feat(variants): extend axis range` |
| 2 | MCP-native strategy | ~18 | `feat(context): add MCP-native strategy` |
| 3 | Compression strategy | ~10 | `feat(context): add compression strategy` |
| 4 | Tool description axis (11) | ~12 | `feat(variants): add axis 11` |
| 5 | Agent instruction axis (12) | ~10 | `feat(variants): add axis 12` |
| 6 | Hallucination detection | ~8 | `feat(judge): add hallucination detection` |
| 7 | Compaction modifier | ~5 | `feat(context): add compaction modifier` |
| 8 | Dynamic tools modifier | ~6 | `feat(context): add dynamic tools modifier` |
| 9 | Cache analysis report | ~4 | `feat(reports): add cache analysis` |
| 10 | Runner wiring | ~2 | `test(runner): hallucination + cache metrics` |
| 11 | CLI wiring | ~2 | `feat(cli): wire Phase C strategies` |
| 12 | Integration tests | ~8 | `test: Phase C integration tests` |
| 13 | Final verification | 0 | - |
| **Total** | | **~88** | **~12 commits** |
