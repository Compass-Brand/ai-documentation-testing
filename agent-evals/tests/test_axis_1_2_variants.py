"""Tests for Axis 1 (structure) and Axis 2 (metadata) index variants."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from agent_evals.variants.base import VariantMetadata
from agent_evals.variants.metadata_path_only import MetadataPathOnlyVariant
from agent_evals.variants.metadata_with_related import MetadataWithRelatedVariant
from agent_evals.variants.metadata_with_summary import MetadataWithSummaryVariant
from agent_evals.variants.metadata_with_tokens import MetadataWithTokensVariant
from agent_evals.variants.registry import (
    clear_registry,
    get_all_variants,
    get_variants_for_axis,
    register_variant,
)
from agent_evals.variants.structure_2tier import Structure2TierVariant
from agent_evals.variants.structure_3tier import Structure3TierVariant
from agent_evals.variants.structure_4tier import Structure4TierVariant
from agent_evals.variants.structure_flat import StructureFlatVariant
from agent_evals.variants.structure_inline_required import (
    StructureInlineRequiredVariant,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc_tree() -> MagicMock:
    """Create a minimal mock DocTree for testing."""
    tree = MagicMock()
    files: dict[str, MagicMock] = {}
    for path, section, tier, content in [
        ("api/auth.md", "API", "required", "JWT authentication with AuthMiddleware..."),
        ("api/caching.md", "API", "recommended", "Response caching with CacheConfig..."),
        ("guides/setup.md", "Guides", "required", "Getting started guide..."),
        ("guides/advanced.md", "Guides", "reference", "Advanced configuration..."),
    ]:
        doc = MagicMock()
        doc.rel_path = path
        doc.content = content
        doc.size_bytes = len(content)
        doc.token_count = len(content) // 4
        doc.tier = tier
        doc.section = section
        doc.priority = 0
        doc.summary = None
        files[path] = doc
    tree.files = files
    return tree


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    """Clear the registry before every test so tests are isolated."""
    clear_registry()


@pytest.fixture()
def doc_tree() -> MagicMock:
    """Provide a mock DocTree."""
    return _make_doc_tree()


# ---------------------------------------------------------------------------
# Axis 1: Structure variants -- metadata tests
# ---------------------------------------------------------------------------


class TestStructureMetadata:
    """Verify metadata() for all five Axis 1 structure variants."""

    @pytest.mark.parametrize(
        ("variant_cls", "expected_name"),
        [
            (StructureFlatVariant, "structure-flat"),
            (Structure2TierVariant, "structure-2tier"),
            (Structure3TierVariant, "structure-3tier"),
            (Structure4TierVariant, "structure-4tier"),
            (StructureInlineRequiredVariant, "structure-inline-required"),
        ],
    )
    def test_metadata_name(self, variant_cls: type, expected_name: str) -> None:
        """Each structure variant reports the correct name."""
        meta = variant_cls().metadata()
        assert meta.name == expected_name

    @pytest.mark.parametrize(
        "variant_cls",
        [
            StructureFlatVariant,
            Structure2TierVariant,
            Structure3TierVariant,
            Structure4TierVariant,
            StructureInlineRequiredVariant,
        ],
    )
    def test_metadata_axis(self, variant_cls: type) -> None:
        """All structure variants belong to axis 1."""
        meta = variant_cls().metadata()
        assert meta.axis == 1

    @pytest.mark.parametrize(
        "variant_cls",
        [
            StructureFlatVariant,
            Structure2TierVariant,
            Structure3TierVariant,
            Structure4TierVariant,
            StructureInlineRequiredVariant,
        ],
    )
    def test_metadata_category(self, variant_cls: type) -> None:
        """All structure variants have category 'structure'."""
        meta = variant_cls().metadata()
        assert meta.category == "structure"

    @pytest.mark.parametrize(
        "variant_cls",
        [
            StructureFlatVariant,
            Structure2TierVariant,
            Structure3TierVariant,
            Structure4TierVariant,
            StructureInlineRequiredVariant,
        ],
    )
    def test_metadata_returns_variant_metadata(self, variant_cls: type) -> None:
        """metadata() returns a VariantMetadata instance."""
        meta = variant_cls().metadata()
        assert isinstance(meta, VariantMetadata)


# ---------------------------------------------------------------------------
# Axis 2: Metadata variants -- metadata tests
# ---------------------------------------------------------------------------


class TestPointerMetadata:
    """Verify metadata() for all four Axis 2 pointer-metadata variants."""

    @pytest.mark.parametrize(
        ("variant_cls", "expected_name"),
        [
            (MetadataPathOnlyVariant, "metadata-path-only"),
            (MetadataWithSummaryVariant, "metadata-with-summary"),
            (MetadataWithTokensVariant, "metadata-with-tokens"),
            (MetadataWithRelatedVariant, "metadata-with-related"),
        ],
    )
    def test_metadata_name(self, variant_cls: type, expected_name: str) -> None:
        """Each metadata variant reports the correct name."""
        meta = variant_cls().metadata()
        assert meta.name == expected_name

    @pytest.mark.parametrize(
        "variant_cls",
        [
            MetadataPathOnlyVariant,
            MetadataWithSummaryVariant,
            MetadataWithTokensVariant,
            MetadataWithRelatedVariant,
        ],
    )
    def test_metadata_axis(self, variant_cls: type) -> None:
        """All pointer-metadata variants belong to axis 2."""
        meta = variant_cls().metadata()
        assert meta.axis == 2

    @pytest.mark.parametrize(
        "variant_cls",
        [
            MetadataPathOnlyVariant,
            MetadataWithSummaryVariant,
            MetadataWithTokensVariant,
            MetadataWithRelatedVariant,
        ],
    )
    def test_metadata_category(self, variant_cls: type) -> None:
        """All pointer-metadata variants have category 'metadata'."""
        meta = variant_cls().metadata()
        assert meta.category == "metadata"


# ---------------------------------------------------------------------------
# Axis 1: Structure variant render tests
# ---------------------------------------------------------------------------


class TestStructureFlatRender:
    """Tests for StructureFlatVariant.render()."""

    def test_render_contains_all_paths(self, doc_tree: MagicMock) -> None:
        """Flat render includes every file path."""
        result = StructureFlatVariant().render(doc_tree)
        assert "api/auth.md" in result
        assert "api/caching.md" in result
        assert "guides/setup.md" in result
        assert "guides/advanced.md" in result

    def test_render_is_flat_list(self, doc_tree: MagicMock) -> None:
        """Flat render has no heading markers (##)."""
        result = StructureFlatVariant().render(doc_tree)
        assert "##" not in result

    def test_render_each_line_starts_with_dash(self, doc_tree: MagicMock) -> None:
        """Every line in the flat render is a bulleted item."""
        result = StructureFlatVariant().render(doc_tree)
        for line in result.strip().splitlines():
            assert line.startswith("- ")

    def test_render_includes_summary(self, doc_tree: MagicMock) -> None:
        """Flat render includes content-derived summaries."""
        result = StructureFlatVariant().render(doc_tree)
        assert "JWT authentication" in result

    def test_render_empty_tree(self) -> None:
        """Flat render returns empty string for empty tree."""
        tree = MagicMock()
        tree.files = {}
        assert StructureFlatVariant().render(tree) == ""


class TestStructure2TierRender:
    """Tests for Structure2TierVariant.render()."""

    def test_render_has_section_headings(self, doc_tree: MagicMock) -> None:
        """2-tier render has ## section headings."""
        result = Structure2TierVariant().render(doc_tree)
        assert "## API" in result
        assert "## Guides" in result

    def test_render_groups_files_under_sections(self, doc_tree: MagicMock) -> None:
        """Files appear under their correct section heading."""
        result = Structure2TierVariant().render(doc_tree)
        lines = result.splitlines()
        # Find "## API" and verify api files follow
        api_idx = next(i for i, line in enumerate(lines) if line == "## API")
        # Next lines should be api files
        assert "api/auth.md" in lines[api_idx + 1]
        assert "api/caching.md" in lines[api_idx + 2]

    def test_render_no_tier_headings(self, doc_tree: MagicMock) -> None:
        """2-tier render does NOT have ### tier headings."""
        result = Structure2TierVariant().render(doc_tree)
        assert "###" not in result

    def test_render_empty_tree(self) -> None:
        """2-tier render returns empty string for empty tree."""
        tree = MagicMock()
        tree.files = {}
        assert Structure2TierVariant().render(tree) == ""


class TestStructure3TierRender:
    """Tests for Structure3TierVariant.render()."""

    def test_render_has_section_headings(self, doc_tree: MagicMock) -> None:
        """3-tier render has ## section headings."""
        result = Structure3TierVariant().render(doc_tree)
        assert "## API" in result
        assert "## Guides" in result

    def test_render_has_tier_headings(self, doc_tree: MagicMock) -> None:
        """3-tier render has ### tier headings."""
        result = Structure3TierVariant().render(doc_tree)
        assert "### Required" in result
        assert "### Recommended" in result
        assert "### Reference" in result

    def test_render_no_subdir_headings(self, doc_tree: MagicMock) -> None:
        """3-tier render does NOT have #### subdir headings."""
        result = Structure3TierVariant().render(doc_tree)
        assert "####" not in result

    def test_render_empty_tree(self) -> None:
        """3-tier render returns empty string for empty tree."""
        tree = MagicMock()
        tree.files = {}
        assert Structure3TierVariant().render(tree) == ""


class TestStructure4TierRender:
    """Tests for Structure4TierVariant.render()."""

    def test_render_has_section_headings(self, doc_tree: MagicMock) -> None:
        """4-tier render has ## section headings."""
        result = Structure4TierVariant().render(doc_tree)
        assert "## API" in result
        assert "## Guides" in result

    def test_render_has_tier_headings(self, doc_tree: MagicMock) -> None:
        """4-tier render has ### tier headings."""
        result = Structure4TierVariant().render(doc_tree)
        assert "### Required" in result

    def test_render_has_subdir_headings(self, doc_tree: MagicMock) -> None:
        """4-tier render has #### subdirectory headings."""
        result = Structure4TierVariant().render(doc_tree)
        assert "#### api" in result or "#### guides" in result

    def test_render_empty_tree(self) -> None:
        """4-tier render returns empty string for empty tree."""
        tree = MagicMock()
        tree.files = {}
        assert Structure4TierVariant().render(tree) == ""


class TestStructureInlineRequiredRender:
    """Tests for StructureInlineRequiredVariant.render()."""

    def test_render_inlines_required_content(self, doc_tree: MagicMock) -> None:
        """Required-tier files have full content inlined."""
        result = StructureInlineRequiredVariant().render(doc_tree)
        # api/auth.md is required, so its content should be inlined
        assert "## api/auth.md [REQUIRED]" in result
        assert "JWT authentication with AuthMiddleware" in result

    def test_render_summarises_non_required(self, doc_tree: MagicMock) -> None:
        """Non-required files are listed with tier and summary."""
        result = StructureInlineRequiredVariant().render(doc_tree)
        assert "api/caching.md (recommended):" in result

    def test_render_required_marker_present(self, doc_tree: MagicMock) -> None:
        """Required files have the [REQUIRED] marker."""
        result = StructureInlineRequiredVariant().render(doc_tree)
        assert "[REQUIRED]" in result

    def test_render_empty_tree(self) -> None:
        """Inline-required render returns empty string for empty tree."""
        tree = MagicMock()
        tree.files = {}
        assert StructureInlineRequiredVariant().render(tree) == ""


# ---------------------------------------------------------------------------
# Axis 2: Metadata variant render tests
# ---------------------------------------------------------------------------


class TestMetadataPathOnlyRender:
    """Tests for MetadataPathOnlyVariant.render()."""

    def test_render_contains_all_paths(self, doc_tree: MagicMock) -> None:
        """Path-only render includes every file path."""
        result = MetadataPathOnlyVariant().render(doc_tree)
        assert "api/auth.md" in result
        assert "api/caching.md" in result
        assert "guides/setup.md" in result
        assert "guides/advanced.md" in result

    def test_render_has_no_summaries(self, doc_tree: MagicMock) -> None:
        """Path-only render does not include content text."""
        result = MetadataPathOnlyVariant().render(doc_tree)
        assert "JWT" not in result
        assert "caching" not in result.lower().replace("api/caching.md", "")

    def test_render_has_no_token_counts(self, doc_tree: MagicMock) -> None:
        """Path-only render does not include token counts."""
        result = MetadataPathOnlyVariant().render(doc_tree)
        assert "token" not in result.lower()

    def test_render_empty_tree(self) -> None:
        """Path-only render returns empty string for empty tree."""
        tree = MagicMock()
        tree.files = {}
        assert MetadataPathOnlyVariant().render(tree) == ""


class TestMetadataWithSummaryRender:
    """Tests for MetadataWithSummaryVariant.render()."""

    def test_render_includes_paths(self, doc_tree: MagicMock) -> None:
        """Summary render includes file paths."""
        result = MetadataWithSummaryVariant().render(doc_tree)
        assert "api/auth.md" in result
        assert "guides/setup.md" in result

    def test_render_includes_summary_text(self, doc_tree: MagicMock) -> None:
        """Summary render includes content-derived summaries."""
        result = MetadataWithSummaryVariant().render(doc_tree)
        assert "JWT authentication" in result

    def test_render_uses_em_dash(self, doc_tree: MagicMock) -> None:
        """Summary render separates path and summary with an em dash."""
        result = MetadataWithSummaryVariant().render(doc_tree)
        assert "\u2014" in result  # em dash

    def test_render_empty_tree(self) -> None:
        """Summary render returns empty string for empty tree."""
        tree = MagicMock()
        tree.files = {}
        assert MetadataWithSummaryVariant().render(tree) == ""


class TestMetadataWithTokensRender:
    """Tests for MetadataWithTokensVariant.render()."""

    def test_render_includes_token_count(self, doc_tree: MagicMock) -> None:
        """Token render includes token counts."""
        result = MetadataWithTokensVariant().render(doc_tree)
        assert "tokens]" in result

    def test_render_includes_tier(self, doc_tree: MagicMock) -> None:
        """Token render includes tier labels."""
        result = MetadataWithTokensVariant().render(doc_tree)
        assert "tier: required" in result
        assert "tier: recommended" in result

    def test_render_format(self, doc_tree: MagicMock) -> None:
        """Token render uses [tier: X, ~N tokens] format."""
        result = MetadataWithTokensVariant().render(doc_tree)
        # api/auth.md has content length 43, token_count = 43 // 4 = 10
        assert "api/auth.md [tier: required, ~10 tokens]" in result

    def test_render_empty_tree(self) -> None:
        """Token render returns empty string for empty tree."""
        tree = MagicMock()
        tree.files = {}
        assert MetadataWithTokensVariant().render(tree) == ""


class TestMetadataWithRelatedRender:
    """Tests for MetadataWithRelatedVariant.render()."""

    def test_render_includes_paths(self, doc_tree: MagicMock) -> None:
        """Related render includes file paths."""
        result = MetadataWithRelatedVariant().render(doc_tree)
        assert "api/auth.md" in result
        assert "guides/setup.md" in result

    def test_render_includes_summary(self, doc_tree: MagicMock) -> None:
        """Related render includes content summaries."""
        result = MetadataWithRelatedVariant().render(doc_tree)
        assert "JWT authentication" in result

    def test_render_includes_related_files(self, doc_tree: MagicMock) -> None:
        """Related render lists cross-references for same-section files."""
        result = MetadataWithRelatedVariant().render(doc_tree)
        # api/auth.md and api/caching.md share the "API" section,
        # so each should reference the other
        assert "Related:" in result

    def test_render_empty_tree(self) -> None:
        """Related render returns empty string for empty tree."""
        tree = MagicMock()
        tree.files = {}
        assert MetadataWithRelatedVariant().render(tree) == ""


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


class TestAxisRegistration:
    """Verify all 9 variants register correctly via @register_variant."""

    def test_all_axis_1_variants_register(self) -> None:
        """All five structure variants register on axis 1."""
        register_variant(StructureFlatVariant)
        register_variant(Structure2TierVariant)
        register_variant(Structure3TierVariant)
        register_variant(Structure4TierVariant)
        register_variant(StructureInlineRequiredVariant)

        axis1 = get_variants_for_axis(1)
        assert len(axis1) == 5
        names = {v.metadata().name for v in axis1}
        assert names == {
            "structure-flat",
            "structure-2tier",
            "structure-3tier",
            "structure-4tier",
            "structure-inline-required",
        }

    def test_all_axis_2_variants_register(self) -> None:
        """All four metadata variants register on axis 2."""
        register_variant(MetadataPathOnlyVariant)
        register_variant(MetadataWithSummaryVariant)
        register_variant(MetadataWithTokensVariant)
        register_variant(MetadataWithRelatedVariant)

        axis2 = get_variants_for_axis(2)
        assert len(axis2) == 4
        names = {v.metadata().name for v in axis2}
        assert names == {
            "metadata-path-only",
            "metadata-with-summary",
            "metadata-with-tokens",
            "metadata-with-related",
        }

    def test_all_nine_variants_in_get_all(self) -> None:
        """All 9 variants appear in get_all_variants."""
        for cls in [
            StructureFlatVariant,
            Structure2TierVariant,
            Structure3TierVariant,
            Structure4TierVariant,
            StructureInlineRequiredVariant,
            MetadataPathOnlyVariant,
            MetadataWithSummaryVariant,
            MetadataWithTokensVariant,
            MetadataWithRelatedVariant,
        ]:
            register_variant(cls)

        all_v = get_all_variants()
        assert len(all_v) == 9

    def test_decorator_registration_is_idempotent(self) -> None:
        """Re-registering the same class does not create duplicates."""
        register_variant(StructureFlatVariant)
        register_variant(StructureFlatVariant)
        assert len(get_all_variants()) == 1


# ---------------------------------------------------------------------------
# Deterministic output ordering
# ---------------------------------------------------------------------------


class TestOutputOrdering:
    """Verify that renders produce deterministic, path-sorted output."""

    def test_flat_output_is_sorted(self, doc_tree: MagicMock) -> None:
        """StructureFlatVariant output lines are sorted by file path."""
        result = StructureFlatVariant().render(doc_tree)
        lines = [line for line in result.splitlines() if line.startswith("- ")]
        paths = [line.split(":")[0].lstrip("- ") for line in lines]
        assert paths == sorted(paths)

    def test_path_only_output_is_sorted(self, doc_tree: MagicMock) -> None:
        """MetadataPathOnlyVariant output lines are sorted by file path."""
        result = MetadataPathOnlyVariant().render(doc_tree)
        lines = [line for line in result.splitlines() if line.startswith("- ")]
        paths = [line.lstrip("- ").strip() for line in lines]
        assert paths == sorted(paths)
