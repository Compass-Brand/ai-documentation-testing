"""Tests for Axis 3 (format) and Axis 4 (position) index variants."""

from __future__ import annotations

import re
from unittest.mock import MagicMock

import pytest
from agent_evals.variants.base import VariantMetadata
from agent_evals.variants.format_markdown_list import FormatMarkdownList
from agent_evals.variants.format_markdown_table import FormatMarkdownTable
from agent_evals.variants.format_pipe_delimited import FormatPipeDelimited
from agent_evals.variants.format_plain_markdown import FormatPlainMarkdown
from agent_evals.variants.format_yaml import FormatYaml
from agent_evals.variants.position_bluf import PositionBluf
from agent_evals.variants.position_edges import PositionEdges
from agent_evals.variants.position_natural import PositionNatural
from agent_evals.variants.position_random import PositionRandom
from agent_evals.variants.registry import (
    clear_registry,
    get_variants_for_axis,
    register_variant,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    """Clear the registry before every test so tests are isolated."""
    clear_registry()


def _make_doc_tree() -> MagicMock:
    """Create a mock DocTree with five files spanning two sections and three tiers."""
    tree = MagicMock()
    files: dict[str, MagicMock] = {}
    for path, section, tier, content, priority in [
        (
            "api/auth.md",
            "API",
            "required",
            "JWT authentication with AuthMiddleware. Supports HS256 algorithm.",
            10,
        ),
        (
            "api/caching.md",
            "API",
            "recommended",
            "Response caching with CacheConfig. Default TTL is 300 seconds.",
            5,
        ),
        (
            "api/config.md",
            "API",
            "reference",
            "Configuration management. DATABASE_URL is required.",
            3,
        ),
        (
            "guides/setup.md",
            "Guides",
            "required",
            "Getting started guide for new developers.",
            8,
        ),
        (
            "guides/advanced.md",
            "Guides",
            "reference",
            "Advanced configuration and tuning options.",
            2,
        ),
    ]:
        doc = MagicMock()
        doc.rel_path = path
        doc.content = content
        doc.size_bytes = len(content)
        doc.token_count = len(content) // 4
        doc.tier = tier
        doc.section = section
        doc.priority = priority
        doc.summary = None
        files[path] = doc
    tree.files = files
    return tree


@pytest.fixture()
def mock_doc_tree() -> MagicMock:
    """Provide a mock DocTree for tests."""
    return _make_doc_tree()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _extract_paths(rendered: str) -> list[str]:
    """Extract file paths from rendered output using a broad regex.

    Handles paths in pipe-delimited rows, YAML ``path:`` keys, Markdown
    bold links, Markdown table cells, and prose mentions.
    """
    # Match common path patterns like "api/auth.md"
    return re.findall(r"[\w/]+\.md", rendered)


# ===========================================================================
# Axis 3: Format variants
# ===========================================================================


class TestFormatPipeDelimited:
    """Tests for FormatPipeDelimited variant."""

    def test_metadata_fields(self) -> None:
        v = FormatPipeDelimited()
        meta = v.metadata()
        assert isinstance(meta, VariantMetadata)
        assert meta.name == "format-pipe-delimited"
        assert meta.axis == 3
        assert meta.category == "format"
        assert meta.token_estimate == 300

    def test_render_has_pipe_delimiters(self, mock_doc_tree: MagicMock) -> None:
        v = FormatPipeDelimited()
        result = v.render(mock_doc_tree)
        # Header row
        assert result.startswith("path|section|tier|tokens|summary")
        # Every non-header line should contain pipes
        lines = result.strip().split("\n")
        for line in lines:
            assert "|" in line

    def test_render_contains_all_files(self, mock_doc_tree: MagicMock) -> None:
        v = FormatPipeDelimited()
        result = v.render(mock_doc_tree)
        assert "api/auth.md" in result
        assert "api/caching.md" in result
        assert "api/config.md" in result
        assert "guides/setup.md" in result
        assert "guides/advanced.md" in result

    def test_render_contains_section_and_tier(self, mock_doc_tree: MagicMock) -> None:
        v = FormatPipeDelimited()
        result = v.render(mock_doc_tree)
        assert "API" in result
        assert "required" in result
        assert "recommended" in result
        assert "reference" in result

    def test_registration(self) -> None:
        register_variant(FormatPipeDelimited)
        variants = get_variants_for_axis(3)
        names = {v.metadata().name for v in variants}
        assert "format-pipe-delimited" in names


class TestFormatYaml:
    """Tests for FormatYaml variant."""

    def test_metadata_fields(self) -> None:
        v = FormatYaml()
        meta = v.metadata()
        assert isinstance(meta, VariantMetadata)
        assert meta.name == "format-yaml"
        assert meta.axis == 3
        assert meta.category == "format"
        assert meta.token_estimate == 500

    def test_render_has_yaml_structure(self, mock_doc_tree: MagicMock) -> None:
        v = FormatYaml()
        result = v.render(mock_doc_tree)
        assert result.startswith("files:")
        # YAML key: value pairs
        assert "path:" in result
        assert "section:" in result
        assert "tier:" in result
        assert "tokens:" in result
        assert "summary:" in result

    def test_render_contains_all_files(self, mock_doc_tree: MagicMock) -> None:
        v = FormatYaml()
        result = v.render(mock_doc_tree)
        assert "api/auth.md" in result
        assert "api/caching.md" in result
        assert "api/config.md" in result
        assert "guides/setup.md" in result
        assert "guides/advanced.md" in result

    def test_render_uses_yaml_list_syntax(self, mock_doc_tree: MagicMock) -> None:
        v = FormatYaml()
        result = v.render(mock_doc_tree)
        # YAML list items start with "  - "
        assert "  - path:" in result

    def test_registration(self) -> None:
        register_variant(FormatYaml)
        variants = get_variants_for_axis(3)
        names = {v.metadata().name for v in variants}
        assert "format-yaml" in names


class TestFormatMarkdownList:
    """Tests for FormatMarkdownList variant."""

    def test_metadata_fields(self) -> None:
        v = FormatMarkdownList()
        meta = v.metadata()
        assert isinstance(meta, VariantMetadata)
        assert meta.name == "format-markdown-list"
        assert meta.axis == 3
        assert meta.category == "format"
        assert meta.token_estimate == 400

    def test_render_has_markdown_heading(self, mock_doc_tree: MagicMock) -> None:
        v = FormatMarkdownList()
        result = v.render(mock_doc_tree)
        assert "# Documentation Index" in result
        assert "## API" in result
        assert "## Guides" in result

    def test_render_has_bold_paths(self, mock_doc_tree: MagicMock) -> None:
        v = FormatMarkdownList()
        result = v.render(mock_doc_tree)
        assert "**api/auth.md**" in result
        assert "**guides/setup.md**" in result

    def test_render_has_bullet_items(self, mock_doc_tree: MagicMock) -> None:
        v = FormatMarkdownList()
        result = v.render(mock_doc_tree)
        bullet_lines = [line for line in result.split("\n") if line.startswith("- **")]
        # Should have 5 bullet items (one per file)
        assert len(bullet_lines) == 5

    def test_render_includes_tier_and_tokens(self, mock_doc_tree: MagicMock) -> None:
        v = FormatMarkdownList()
        result = v.render(mock_doc_tree)
        # Check that tier and token info appear in parentheses
        assert "(required," in result
        assert "(recommended," in result
        assert "(reference," in result
        assert "tokens)" in result

    def test_registration(self) -> None:
        register_variant(FormatMarkdownList)
        variants = get_variants_for_axis(3)
        names = {v.metadata().name for v in variants}
        assert "format-markdown-list" in names


class TestFormatMarkdownTable:
    """Tests for FormatMarkdownTable variant."""

    def test_metadata_fields(self) -> None:
        v = FormatMarkdownTable()
        meta = v.metadata()
        assert isinstance(meta, VariantMetadata)
        assert meta.name == "format-markdown-table"
        assert meta.axis == 3
        assert meta.category == "format"
        assert meta.token_estimate == 400

    def test_render_has_table_structure(self, mock_doc_tree: MagicMock) -> None:
        v = FormatMarkdownTable()
        result = v.render(mock_doc_tree)
        assert "# Documentation Index" in result
        # Table header
        assert "| Path | Section | Tier | Tokens | Summary |" in result
        # Table separator with dashes
        assert "|------|---------|------|--------|---------|" in result

    def test_render_has_data_rows(self, mock_doc_tree: MagicMock) -> None:
        v = FormatMarkdownTable()
        result = v.render(mock_doc_tree)
        # Data rows are pipe-separated
        lines = result.strip().split("\n")
        # Header line, blank, table header, separator, 5 data rows = 9 lines
        data_rows = [line for line in lines if line.startswith(("| api/", "| guides/"))]
        assert len(data_rows) == 5

    def test_render_contains_all_files(self, mock_doc_tree: MagicMock) -> None:
        v = FormatMarkdownTable()
        result = v.render(mock_doc_tree)
        assert "api/auth.md" in result
        assert "api/caching.md" in result
        assert "api/config.md" in result
        assert "guides/setup.md" in result
        assert "guides/advanced.md" in result

    def test_registration(self) -> None:
        register_variant(FormatMarkdownTable)
        variants = get_variants_for_axis(3)
        names = {v.metadata().name for v in variants}
        assert "format-markdown-table" in names


class TestFormatPlainMarkdown:
    """Tests for FormatPlainMarkdown variant."""

    def test_metadata_fields(self) -> None:
        v = FormatPlainMarkdown()
        meta = v.metadata()
        assert isinstance(meta, VariantMetadata)
        assert meta.name == "format-plain-markdown"
        assert meta.axis == 3
        assert meta.category == "format"
        assert meta.token_estimate == 600

    def test_render_is_prose(self, mock_doc_tree: MagicMock) -> None:
        v = FormatPlainMarkdown()
        result = v.render(mock_doc_tree)
        # Should NOT have Markdown table separators or bullet lists
        assert "|--|" not in result
        assert "- **" not in result
        # Should read as prose sentences
        assert "The documentation contains" in result

    def test_render_mentions_sections(self, mock_doc_tree: MagicMock) -> None:
        v = FormatPlainMarkdown()
        result = v.render(mock_doc_tree)
        assert "API" in result
        assert "Guides" in result

    def test_render_mentions_tiers(self, mock_doc_tree: MagicMock) -> None:
        v = FormatPlainMarkdown()
        result = v.render(mock_doc_tree)
        assert "required" in result
        assert "recommended" in result
        assert "reference" in result

    def test_render_mentions_files(self, mock_doc_tree: MagicMock) -> None:
        v = FormatPlainMarkdown()
        result = v.render(mock_doc_tree)
        assert "auth.md" in result
        assert "caching.md" in result
        assert "config.md" in result
        assert "setup.md" in result
        assert "advanced.md" in result

    def test_registration(self) -> None:
        register_variant(FormatPlainMarkdown)
        variants = get_variants_for_axis(3)
        names = {v.metadata().name for v in variants}
        assert "format-plain-markdown" in names


# ===========================================================================
# Axis 4: Position variants
# ===========================================================================


class TestPositionNatural:
    """Tests for PositionNatural variant."""

    def test_metadata_fields(self) -> None:
        v = PositionNatural()
        meta = v.metadata()
        assert isinstance(meta, VariantMetadata)
        assert meta.name == "position-natural"
        assert meta.axis == 4
        assert meta.category == "position"
        assert meta.token_estimate == 400

    def test_render_alphabetical_order(self, mock_doc_tree: MagicMock) -> None:
        v = PositionNatural()
        result = v.render(mock_doc_tree)
        paths = _extract_paths(result)
        expected_order = [
            "api/auth.md",
            "api/caching.md",
            "api/config.md",
            "guides/advanced.md",
            "guides/setup.md",
        ]
        assert paths == expected_order

    def test_render_has_section_headings(self, mock_doc_tree: MagicMock) -> None:
        v = PositionNatural()
        result = v.render(mock_doc_tree)
        assert "# Documentation Index" in result
        assert "## API" in result
        assert "## Guides" in result

    def test_render_contains_tier_info(self, mock_doc_tree: MagicMock) -> None:
        v = PositionNatural()
        result = v.render(mock_doc_tree)
        assert "required" in result
        assert "recommended" in result
        assert "reference" in result

    def test_registration(self) -> None:
        register_variant(PositionNatural)
        variants = get_variants_for_axis(4)
        names = {v.metadata().name for v in variants}
        assert "position-natural" in names


class TestPositionBluf:
    """Tests for PositionBluf variant."""

    def test_metadata_fields(self) -> None:
        v = PositionBluf()
        meta = v.metadata()
        assert isinstance(meta, VariantMetadata)
        assert meta.name == "position-bluf"
        assert meta.axis == 4
        assert meta.category == "position"
        assert meta.token_estimate == 400

    def test_render_required_files_first(self, mock_doc_tree: MagicMock) -> None:
        v = PositionBluf()
        result = v.render(mock_doc_tree)
        paths = _extract_paths(result)
        # BLUF sort: auth (req, p10), setup (req, p8), caching (rec, p5),
        # config (ref, p3), advanced (ref, p2).
        # _render_two_tier groups by section in first-appearance order:
        #   API section: auth, caching, config
        #   Guides section: setup, advanced
        expected_order = [
            "api/auth.md",
            "api/caching.md",
            "api/config.md",
            "guides/setup.md",
            "guides/advanced.md",
        ]
        assert paths == expected_order
        # Verify that within each section, required files precede others.
        api_paths = [p for p in paths if p.startswith("api/")]
        assert api_paths[0] == "api/auth.md"  # required before recommended/reference

    def test_render_has_section_headings(self, mock_doc_tree: MagicMock) -> None:
        v = PositionBluf()
        result = v.render(mock_doc_tree)
        assert "# Documentation Index" in result

    def test_registration(self) -> None:
        register_variant(PositionBluf)
        variants = get_variants_for_axis(4)
        names = {v.metadata().name for v in variants}
        assert "position-bluf" in names


class TestPositionEdges:
    """Tests for PositionEdges variant."""

    def test_metadata_fields(self) -> None:
        v = PositionEdges()
        meta = v.metadata()
        assert isinstance(meta, VariantMetadata)
        assert meta.name == "position-edges"
        assert meta.axis == 4
        assert meta.category == "position"
        assert meta.token_estimate == 400

    def test_render_required_at_edges(self, mock_doc_tree: MagicMock) -> None:
        v = PositionEdges()
        result = v.render(mock_doc_tree)
        paths = _extract_paths(result)
        # Required files (alphabetical): api/auth.md, guides/setup.md
        # 2 required files -> midpoint=1 -> top=[auth], bottom=[setup]
        # Non-required (alphabetical): caching, config, advanced
        expected_order = [
            "api/auth.md",       # top required
            "api/caching.md",    # middle
            "api/config.md",     # middle
            "guides/advanced.md",  # middle
            "guides/setup.md",   # bottom required
        ]
        assert paths == expected_order

    def test_render_first_file_is_required(self, mock_doc_tree: MagicMock) -> None:
        v = PositionEdges()
        result = v.render(mock_doc_tree)
        paths = _extract_paths(result)
        # First file should be required
        first_path = paths[0]
        assert mock_doc_tree.files[first_path].tier == "required"

    def test_render_last_file_is_required(self, mock_doc_tree: MagicMock) -> None:
        v = PositionEdges()
        result = v.render(mock_doc_tree)
        paths = _extract_paths(result)
        # Last file should be required
        last_path = paths[-1]
        assert mock_doc_tree.files[last_path].tier == "required"

    def test_registration(self) -> None:
        register_variant(PositionEdges)
        variants = get_variants_for_axis(4)
        names = {v.metadata().name for v in variants}
        assert "position-edges" in names


class TestPositionRandom:
    """Tests for PositionRandom variant."""

    def test_metadata_fields(self) -> None:
        v = PositionRandom()
        meta = v.metadata()
        assert isinstance(meta, VariantMetadata)
        assert meta.name == "position-random"
        assert meta.axis == 4
        assert meta.category == "position"
        assert meta.token_estimate == 400

    def test_render_is_deterministic(self, mock_doc_tree: MagicMock) -> None:
        v1 = PositionRandom()
        v2 = PositionRandom()
        result1 = v1.render(mock_doc_tree)
        result2 = v2.render(mock_doc_tree)
        assert result1 == result2

    def test_render_contains_all_files(self, mock_doc_tree: MagicMock) -> None:
        v = PositionRandom()
        result = v.render(mock_doc_tree)
        assert "api/auth.md" in result
        assert "api/caching.md" in result
        assert "api/config.md" in result
        assert "guides/setup.md" in result
        assert "guides/advanced.md" in result

    def test_render_differs_from_alphabetical(self, mock_doc_tree: MagicMock) -> None:
        v_random = PositionRandom()
        v_natural = PositionNatural()
        random_paths = _extract_paths(v_random.render(mock_doc_tree))
        natural_paths = _extract_paths(v_natural.render(mock_doc_tree))
        # Random order with seed=42 should differ from alphabetical
        assert random_paths != natural_paths

    def test_registration(self) -> None:
        register_variant(PositionRandom)
        variants = get_variants_for_axis(4)
        names = {v.metadata().name for v in variants}
        assert "position-random" in names


# ===========================================================================
# Cross-variant tests
# ===========================================================================


class TestAxis3Registration:
    """All Axis 3 format variants can coexist in the registry."""

    def test_all_five_format_variants_register_on_axis_three(self) -> None:
        register_variant(FormatPipeDelimited)
        register_variant(FormatYaml)
        register_variant(FormatMarkdownList)
        register_variant(FormatMarkdownTable)
        register_variant(FormatPlainMarkdown)

        variants = get_variants_for_axis(3)
        assert len(variants) == 5
        names = {v.metadata().name for v in variants}
        assert names == {
            "format-pipe-delimited",
            "format-yaml",
            "format-markdown-list",
            "format-markdown-table",
            "format-plain-markdown",
        }


class TestAxis4Registration:
    """All Axis 4 position variants can coexist in the registry."""

    def test_all_four_position_variants_register_on_axis_four(self) -> None:
        register_variant(PositionNatural)
        register_variant(PositionBluf)
        register_variant(PositionEdges)
        register_variant(PositionRandom)

        variants = get_variants_for_axis(4)
        assert len(variants) == 4
        names = {v.metadata().name for v in variants}
        assert names == {
            "position-natural",
            "position-bluf",
            "position-edges",
            "position-random",
        }
