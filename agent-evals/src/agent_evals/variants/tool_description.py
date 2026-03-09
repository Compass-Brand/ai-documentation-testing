"""Axis 11: Tool description quality and tool set size variants."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree

_CORE_TOOLS = ["list_docs", "read_doc", "search_docs"]

# ---------------------------------------------------------------------------
# Shared tool definitions for tool-set-size variants
# ---------------------------------------------------------------------------

_CORE_TOOLS_STANDARD = [
    {
        "name": "list_docs",
        "description": "List all available documentation files.",
        "parameters": "() -> str",
    },
    {
        "name": "read_doc",
        "description": "Read a documentation file by path.",
        "parameters": "(path: str) -> str",
    },
    {
        "name": "search_docs",
        "description": "Search documentation for a query string.",
        "parameters": "(query: str) -> str",
    },
]

_EXTENDED_TOOLS_5 = [
    {
        "name": "get_metadata",
        "description": "Get metadata for a documentation file (tier, section, token count).",
        "parameters": "(path: str) -> dict",
    },
    {
        "name": "list_sections",
        "description": "List all documentation sections with file counts.",
        "parameters": "() -> str",
    },
]

_EXTENDED_TOOLS_7 = _EXTENDED_TOOLS_5 + [
    {
        "name": "search_by_section",
        "description": "Search within a specific documentation section.",
        "parameters": "(section: str, query: str) -> str",
    },
    {
        "name": "get_related",
        "description": "Get related documentation files for a given path.",
        "parameters": "(path: str) -> list[str]",
    },
]

_KITCHEN_SINK_TOOLS = _EXTENDED_TOOLS_7 + [
    {
        "name": "find_docs",
        "description": "Find documentation files matching a glob pattern.",
        "parameters": "(pattern: str) -> list[str]",
    },
    {
        "name": "grep_docs",
        "description": "Search documentation content with regex.",
        "parameters": "(regex: str) -> str",
    },
    {
        "name": "get_doc_summary",
        "description": "Get a summary of a documentation file.",
        "parameters": "(path: str) -> str",
    },
    {
        "name": "list_all_files",
        "description": "List all files in the documentation tree.",
        "parameters": "() -> list[str]",
    },
    {
        "name": "read_section",
        "description": "Read a specific section from a documentation file.",
        "parameters": "(path: str, section: str) -> str",
    },
    {
        "name": "search_all",
        "description": "Search across all documentation (alias for search_docs).",
        "parameters": "(query: str) -> str",
    },
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _render_tool_block(tools: list[dict], doc_tree: DocTree) -> str:
    """Render tool definitions followed by the documentation index.

    Args:
        tools: List of tool dicts with 'name', optional 'description',
               and optional 'parameters'.
        doc_tree: Parsed documentation tree.

    Returns:
        Combined string of tool definitions and doc index.
    """
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


# ===========================================================================
# Description Quality Variants
# ===========================================================================


@register_variant
class ToolDescMinimal(IndexVariant):
    """Minimal tool descriptions: name + types only, no prose descriptions."""

    def metadata(self) -> VariantMetadata:
        """Return metadata for the minimal tool-description variant."""
        return VariantMetadata(
            name="tool-desc-minimal",
            axis=11,
            category="tool-description",
            description="Tools with name and parameter types only, no descriptions.",
            token_estimate=200,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render tools with names and parameter signatures but no descriptions.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Tool block with stripped descriptions.
        """
        tools = [
            {"name": "list_docs", "parameters": "() -> str"},
            {"name": "read_doc", "parameters": "(path: str) -> str"},
            {"name": "search_docs", "parameters": "(query: str) -> str"},
        ]
        return _render_tool_block(tools, doc_tree)


@register_variant
class ToolDescStandard(IndexVariant):
    """Standard tool descriptions: one-line descriptions."""

    def metadata(self) -> VariantMetadata:
        """Return metadata for the standard tool-description variant."""
        return VariantMetadata(
            name="tool-desc-standard",
            axis=11,
            category="tool-description",
            description="Tools with concise one-line descriptions.",
            token_estimate=250,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render tools with standard one-line descriptions.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Tool block with one-line descriptions.
        """
        return _render_tool_block(_CORE_TOOLS_STANDARD, doc_tree)


@register_variant
class ToolDescDetailed(IndexVariant):
    """Detailed tool descriptions: examples + edge cases."""

    def metadata(self) -> VariantMetadata:
        """Return metadata for the detailed tool-description variant."""
        return VariantMetadata(
            name="tool-desc-detailed",
            axis=11,
            category="tool-description",
            description="Tools with detailed descriptions including examples and edge cases.",
            token_estimate=500,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render tools with detailed descriptions, examples, and edge cases.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Tool block with verbose descriptions.
        """
        tools = [
            {
                "name": "list_docs",
                "description": (
                    "List all available documentation files. Returns a newline-separated "
                    "list of relative paths. Example: 'api/auth.md\\nguides/setup.md'. "
                    "Edge case: returns empty string if no docs exist."
                ),
                "parameters": "() -> str",
            },
            {
                "name": "read_doc",
                "description": (
                    "Read a documentation file by its relative path. Returns the full "
                    "content as a string. E.g. read_doc('api/auth.md') returns the auth "
                    "module documentation. Edge case: raises FileNotFoundError if path "
                    "does not exist."
                ),
                "parameters": "(path: str) -> str",
            },
            {
                "name": "search_docs",
                "description": (
                    "Search documentation for a query string. Returns matching excerpts "
                    "with file paths. Example: search_docs('authentication') returns "
                    "snippets from auth-related files. Edge case: returns empty string "
                    "if no matches found."
                ),
                "parameters": "(query: str) -> str",
            },
        ]
        return _render_tool_block(tools, doc_tree)


@register_variant
class ToolDescAdversarial(IndexVariant):
    """Adversarial tool descriptions: deliberately vague or misleading."""

    def metadata(self) -> VariantMetadata:
        """Return metadata for the adversarial tool-description variant."""
        return VariantMetadata(
            name="tool-desc-adversarial",
            axis=11,
            category="tool-description",
            description="Tools with deliberately vague or misleading descriptions.",
            token_estimate=250,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render tools with vague, misleading descriptions.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Tool block with adversarial descriptions.
        """
        tools = [
            {
                "name": "list_docs",
                "description": "Does something with files. Might list them.",
                "parameters": "() -> str",
            },
            {
                "name": "read_doc",
                "description": "Processes input data. May or may not return content.",
                "parameters": "(path: str) -> str",
            },
            {
                "name": "search_docs",
                "description": "General purpose utility function for data operations.",
                "parameters": "(query: str) -> str",
            },
        ]
        return _render_tool_block(tools, doc_tree)


# ===========================================================================
# Tool Set Size Variants
# ===========================================================================


@register_variant
class ToolSetCore3(IndexVariant):
    """Core tool set: 3 essential tools (list, read, search)."""

    def metadata(self) -> VariantMetadata:
        """Return metadata for the core-3 tool-set variant."""
        return VariantMetadata(
            name="toolset-core-3",
            axis=11,
            category="tool-set-size",
            description="Minimal tool set with 3 core tools: list, read, search.",
            token_estimate=250,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render with only the 3 core tools.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Tool block with 3 core tools.
        """
        return _render_tool_block(_CORE_TOOLS_STANDARD, doc_tree)


@register_variant
class ToolSetExtended5(IndexVariant):
    """Extended tool set: core 3 + get_metadata, list_sections."""

    def metadata(self) -> VariantMetadata:
        """Return metadata for the extended-5 tool-set variant."""
        return VariantMetadata(
            name="toolset-extended-5",
            axis=11,
            category="tool-set-size",
            description="Extended tool set with 5 tools: core 3 + metadata and sections.",
            token_estimate=350,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render with 5 tools (core 3 + 2 extended).

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Tool block with 5 tools.
        """
        return _render_tool_block(_CORE_TOOLS_STANDARD + _EXTENDED_TOOLS_5, doc_tree)


@register_variant
class ToolSetExtended7(IndexVariant):
    """Extended tool set: core 3 + 4 additional tools."""

    def metadata(self) -> VariantMetadata:
        """Return metadata for the extended-7 tool-set variant."""
        return VariantMetadata(
            name="toolset-extended-7",
            axis=11,
            category="tool-set-size",
            description="Extended tool set with 7 tools: core 3 + search-by-section, get-related, etc.",
            token_estimate=450,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render with 7 tools (core 3 + 4 extended).

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Tool block with 7 tools.
        """
        return _render_tool_block(_CORE_TOOLS_STANDARD + _EXTENDED_TOOLS_7, doc_tree)


@register_variant
class ToolSetKitchenSink(IndexVariant):
    """Kitchen sink tool set: 10+ tools including overlapping/redundant ones."""

    def metadata(self) -> VariantMetadata:
        """Return metadata for the kitchen-sink tool-set variant."""
        return VariantMetadata(
            name="toolset-kitchen-sink",
            axis=11,
            category="tool-set-size",
            description="Maximal tool set with 10+ tools including overlapping functionality.",
            token_estimate=700,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render with 10+ tools including redundant ones.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Tool block with 13 tools (3 core + 10 extended/redundant).
        """
        return _render_tool_block(
            _CORE_TOOLS_STANDARD + _KITCHEN_SINK_TOOLS, doc_tree
        )
