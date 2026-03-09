"""Tests for Axis 11: Tool description quality and tool set size variants."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from agent_evals.variants.base import VariantMetadata
from agent_evals.variants.registry import (
    clear_registry,
    get_variants_for_axis,
    register_variant,
)
from agent_evals.variants.tool_description import (
    ToolDescAdversarial,
    ToolDescDetailed,
    ToolDescMinimal,
    ToolDescStandard,
    ToolSetCore3,
    ToolSetExtended5,
    ToolSetExtended7,
    ToolSetKitchenSink,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    """Clear the registry before every test so tests are isolated."""
    clear_registry()


def _make_doc_tree() -> MagicMock:
    """Create a mock DocTree for axis 11 testing.

    The tree has 4 files across 2 sections, matching patterns used
    for tool-based retrieval testing.
    """
    tree = MagicMock()
    files: dict[str, MagicMock] = {}

    for path, section, tier, content, summary in [
        (
            "api/auth.md",
            "API",
            "required",
            "JWT authentication with AuthMiddleware.",
            "JWT authentication module",
        ),
        (
            "api/caching.md",
            "API",
            "recommended",
            "Response caching with CacheConfig.",
            "Response caching layer",
        ),
        (
            "guides/setup.md",
            "Guides",
            "required",
            "Getting started guide. Requires auth module.",
            "Setup guide for new developers",
        ),
        (
            "guides/advanced.md",
            "Guides",
            "reference",
            "Advanced configuration and tuning options.",
            "Advanced configuration guide",
        ),
    ]:
        doc = MagicMock()
        doc.rel_path = path
        doc.content = content
        doc.size_bytes = len(content)
        doc.token_count = len(content) // 4
        doc.tier = tier
        doc.section = section
        doc.priority = 0
        doc.summary = summary
        files[path] = doc

    tree.files = files
    return tree


@pytest.fixture
def doc_tree() -> MagicMock:
    """Provide a mock DocTree."""
    return _make_doc_tree()


def _empty_tree() -> MagicMock:
    """Create an empty mock DocTree."""
    tree = MagicMock()
    tree.files = {}
    return tree


# ===========================================================================
# Description Quality — ToolDescMinimal
# ===========================================================================


class TestToolDescMinimalMetadata:
    """Verify metadata() for ToolDescMinimal."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = ToolDescMinimal().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = ToolDescMinimal().metadata()
        assert meta.name == "tool-desc-minimal"

    def test_metadata_axis(self) -> None:
        meta = ToolDescMinimal().metadata()
        assert meta.axis == 11

    def test_metadata_category(self) -> None:
        meta = ToolDescMinimal().metadata()
        assert meta.category == "tool-description"


class TestToolDescMinimalRender:
    """Verify render() for ToolDescMinimal."""

    def test_render_contains_tool_names(self, doc_tree: MagicMock) -> None:
        result = ToolDescMinimal().render(doc_tree)
        assert "list_docs" in result
        assert "read_doc" in result
        assert "search_docs" in result

    def test_render_has_no_descriptions(self, doc_tree: MagicMock) -> None:
        """Minimal tools have no description text."""
        result = ToolDescMinimal().render(doc_tree)
        assert "List all available" not in result
        assert "Read a documentation" not in result
        assert "Search documentation" not in result

    def test_render_has_parameters(self, doc_tree: MagicMock) -> None:
        result = ToolDescMinimal().render(doc_tree)
        assert "Parameters:" in result

    def test_render_contains_doc_index(self, doc_tree: MagicMock) -> None:
        result = ToolDescMinimal().render(doc_tree)
        assert "Documentation Index" in result
        assert "api/auth.md" in result
        assert "guides/setup.md" in result

    def test_render_empty_tree(self) -> None:
        result = ToolDescMinimal().render(_empty_tree())
        assert "Tool Definitions" in result
        assert "Documentation Index" in result


# ===========================================================================
# Description Quality — ToolDescStandard
# ===========================================================================


class TestToolDescStandardMetadata:
    """Verify metadata() for ToolDescStandard."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = ToolDescStandard().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = ToolDescStandard().metadata()
        assert meta.name == "tool-desc-standard"

    def test_metadata_axis(self) -> None:
        meta = ToolDescStandard().metadata()
        assert meta.axis == 11

    def test_metadata_category(self) -> None:
        meta = ToolDescStandard().metadata()
        assert meta.category == "tool-description"


# ===========================================================================
# Description Quality — ToolDescDetailed
# ===========================================================================


class TestToolDescDetailedMetadata:
    """Verify metadata() for ToolDescDetailed."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = ToolDescDetailed().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = ToolDescDetailed().metadata()
        assert meta.name == "tool-desc-detailed"

    def test_metadata_axis(self) -> None:
        meta = ToolDescDetailed().metadata()
        assert meta.axis == 11

    def test_metadata_category(self) -> None:
        meta = ToolDescDetailed().metadata()
        assert meta.category == "tool-description"


class TestToolDescDetailedRender:
    """Verify render() for ToolDescDetailed produces longer descriptions."""

    def test_render_longer_than_standard(self, doc_tree: MagicMock) -> None:
        """Detailed variant should be longer than standard."""
        detailed = ToolDescDetailed().render(doc_tree)
        standard = ToolDescStandard().render(doc_tree)
        assert len(detailed) > len(standard)

    def test_render_contains_examples_or_edge_cases(self, doc_tree: MagicMock) -> None:
        """Detailed descriptions should mention examples or edge cases."""
        result = ToolDescDetailed().render(doc_tree)
        assert "example" in result.lower() or "edge" in result.lower() or "e.g." in result.lower()

    def test_render_contains_all_core_tools(self, doc_tree: MagicMock) -> None:
        result = ToolDescDetailed().render(doc_tree)
        assert "list_docs" in result
        assert "read_doc" in result
        assert "search_docs" in result


# ===========================================================================
# Description Quality — ToolDescAdversarial
# ===========================================================================


class TestToolDescAdversarialMetadata:
    """Verify metadata() for ToolDescAdversarial."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = ToolDescAdversarial().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = ToolDescAdversarial().metadata()
        assert meta.name == "tool-desc-adversarial"

    def test_metadata_axis(self) -> None:
        meta = ToolDescAdversarial().metadata()
        assert meta.axis == 11

    def test_metadata_category(self) -> None:
        meta = ToolDescAdversarial().metadata()
        assert meta.category == "tool-description"


# ===========================================================================
# Tool Set Size — ToolSetCore3
# ===========================================================================


class TestToolSetCore3:
    """Verify ToolSetCore3 renders exactly 3 core tools."""

    def test_metadata_name(self) -> None:
        meta = ToolSetCore3().metadata()
        assert meta.name == "toolset-core-3"

    def test_metadata_axis(self) -> None:
        meta = ToolSetCore3().metadata()
        assert meta.axis == 11

    def test_metadata_category(self) -> None:
        meta = ToolSetCore3().metadata()
        assert meta.category == "tool-set-size"

    def test_render_contains_exactly_3_tools(self, doc_tree: MagicMock) -> None:
        result = ToolSetCore3().render(doc_tree)
        assert "list_docs" in result
        assert "read_doc" in result
        assert "search_docs" in result
        # Should NOT contain extended tools
        assert "get_metadata" not in result
        assert "list_sections" not in result

    def test_render_contains_doc_index(self, doc_tree: MagicMock) -> None:
        result = ToolSetCore3().render(doc_tree)
        assert "Documentation Index" in result
        assert "api/auth.md" in result

    def test_render_empty_tree(self) -> None:
        result = ToolSetCore3().render(_empty_tree())
        assert "list_docs" in result
        assert "Documentation Index" in result


# ===========================================================================
# Tool Set Size — ToolSetExtended5
# ===========================================================================


class TestToolSetExtended5:
    """Verify ToolSetExtended5 renders 5 tools."""

    def test_metadata_name(self) -> None:
        meta = ToolSetExtended5().metadata()
        assert meta.name == "toolset-extended-5"

    def test_metadata_axis(self) -> None:
        meta = ToolSetExtended5().metadata()
        assert meta.axis == 11

    def test_metadata_category(self) -> None:
        meta = ToolSetExtended5().metadata()
        assert meta.category == "tool-set-size"

    def test_render_contains_core_plus_two(self, doc_tree: MagicMock) -> None:
        result = ToolSetExtended5().render(doc_tree)
        assert "list_docs" in result
        assert "read_doc" in result
        assert "search_docs" in result
        assert "get_metadata" in result
        assert "list_sections" in result

    def test_render_does_not_contain_extended_7_tools(self, doc_tree: MagicMock) -> None:
        result = ToolSetExtended5().render(doc_tree)
        assert "search_by_section" not in result
        assert "get_related" not in result


# ===========================================================================
# Tool Set Size — ToolSetExtended7
# ===========================================================================


class TestToolSetExtended7:
    """Verify ToolSetExtended7 renders 7 tools."""

    def test_metadata_name(self) -> None:
        meta = ToolSetExtended7().metadata()
        assert meta.name == "toolset-extended-7"

    def test_metadata_axis(self) -> None:
        meta = ToolSetExtended7().metadata()
        assert meta.axis == 11

    def test_metadata_category(self) -> None:
        meta = ToolSetExtended7().metadata()
        assert meta.category == "tool-set-size"

    def test_render_contains_all_7_tools(self, doc_tree: MagicMock) -> None:
        result = ToolSetExtended7().render(doc_tree)
        assert "list_docs" in result
        assert "read_doc" in result
        assert "search_docs" in result
        assert "get_metadata" in result
        assert "list_sections" in result
        assert "search_by_section" in result
        assert "get_related" in result

    def test_render_does_not_contain_kitchen_sink_tools(self, doc_tree: MagicMock) -> None:
        result = ToolSetExtended7().render(doc_tree)
        assert "find_docs" not in result
        assert "grep_docs" not in result


# ===========================================================================
# Tool Set Size — ToolSetKitchenSink
# ===========================================================================


class TestToolSetKitchenSink:
    """Verify ToolSetKitchenSink renders 10+ tools."""

    def test_metadata_name(self) -> None:
        meta = ToolSetKitchenSink().metadata()
        assert meta.name == "toolset-kitchen-sink"

    def test_metadata_axis(self) -> None:
        meta = ToolSetKitchenSink().metadata()
        assert meta.axis == 11

    def test_metadata_category(self) -> None:
        meta = ToolSetKitchenSink().metadata()
        assert meta.category == "tool-set-size"

    def test_render_contains_all_tools(self, doc_tree: MagicMock) -> None:
        result = ToolSetKitchenSink().render(doc_tree)
        for tool_name in [
            "list_docs",
            "read_doc",
            "search_docs",
            "get_metadata",
            "list_sections",
            "search_by_section",
            "get_related",
            "find_docs",
            "grep_docs",
            "get_doc_summary",
            "list_all_files",
            "read_section",
            "search_all",
        ]:
            assert tool_name in result, f"Missing tool: {tool_name}"

    def test_render_has_redundant_tools(self, doc_tree: MagicMock) -> None:
        """Kitchen sink includes overlapping tools like search_all."""
        result = ToolSetKitchenSink().render(doc_tree)
        assert "search_all" in result
        assert "search_docs" in result


# ===========================================================================
# Registration
# ===========================================================================


class TestToolDescRegistration:
    """All axis 11 variants register correctly."""

    def test_all_eight_variants_register_on_axis_eleven(self) -> None:
        register_variant(ToolDescMinimal)
        register_variant(ToolDescStandard)
        register_variant(ToolDescDetailed)
        register_variant(ToolDescAdversarial)
        register_variant(ToolSetCore3)
        register_variant(ToolSetExtended5)
        register_variant(ToolSetExtended7)
        register_variant(ToolSetKitchenSink)

        variants = get_variants_for_axis(11)
        assert len(variants) == 8
        names = {v.metadata().name for v in variants}
        assert names == {
            "tool-desc-minimal",
            "tool-desc-standard",
            "tool-desc-detailed",
            "tool-desc-adversarial",
            "toolset-core-3",
            "toolset-extended-5",
            "toolset-extended-7",
            "toolset-kitchen-sink",
        }


# ===========================================================================
# Prompt length ordering
# ===========================================================================


class TestToolSetSizePromptLength:
    """Tool set size variants produce progressively longer prompts."""

    def test_core3_shorter_than_extended5(self, doc_tree: MagicMock) -> None:
        core = ToolSetCore3().render(doc_tree)
        ext5 = ToolSetExtended5().render(doc_tree)
        assert len(core) < len(ext5)

    def test_extended5_shorter_than_extended7(self, doc_tree: MagicMock) -> None:
        ext5 = ToolSetExtended5().render(doc_tree)
        ext7 = ToolSetExtended7().render(doc_tree)
        assert len(ext5) < len(ext7)

    def test_extended7_shorter_than_kitchen_sink(self, doc_tree: MagicMock) -> None:
        ext7 = ToolSetExtended7().render(doc_tree)
        sink = ToolSetKitchenSink().render(doc_tree)
        assert len(ext7) < len(sink)
