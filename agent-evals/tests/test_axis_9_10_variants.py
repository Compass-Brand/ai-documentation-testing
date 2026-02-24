"""Tests for Axis 9 (cross-reference density) and Axis 10 (temporal markers) index variants."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from agent_evals.variants.base import VariantMetadata
from agent_evals.variants.registry import (
    clear_registry,
    get_variants_for_axis,
    register_variant,
)
from agent_evals.variants.temporal_deprecated import TemporalDeprecatedVariant
from agent_evals.variants.temporal_modified import TemporalModifiedVariant
from agent_evals.variants.temporal_none import TemporalNoneVariant
from agent_evals.variants.temporal_version import TemporalVersionVariant
from agent_evals.variants.xref_dense import XrefDenseVariant
from agent_evals.variants.xref_light import XrefLightVariant
from agent_evals.variants.xref_none import XrefNoneVariant

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    """Clear the registry before every test so tests are isolated."""
    clear_registry()


def _make_doc_tree() -> MagicMock:
    """Create a mock DocTree tailored for Axis 9 and 10 testing.

    The tree has 5 files across 2 sections.  Some files cross-reference
    each other by name in their content, some have version strings,
    last_modified dates, and deprecation markers.
    """
    tree = MagicMock()
    files: dict[str, MagicMock] = {}

    for path, section, tier, content, summary, last_modified in [
        (
            "api/auth.md",
            "API",
            "required",
            "JWT authentication with AuthMiddleware. See caching for performance tips. @since 2.1",
            "JWT authentication module",
            datetime(2025, 6, 15),
        ),
        (
            "api/caching.md",
            "API",
            "recommended",
            "Response caching with CacheConfig. v1.3 release. Uses auth tokens internally.",
            "Response caching layer",
            datetime(2025, 3, 10),
        ),
        (
            "api/legacy.md",
            "API",
            "reference",
            "@deprecated This module is obsolete. Use auth instead. version 0.9",
            "Legacy authentication (deprecated)",
            None,
        ),
        (
            "guides/setup.md",
            "Guides",
            "required",
            "Getting started guide. Requires auth module. No longer supported on Python 2.",
            "Setup guide for new developers",
            datetime(2024, 12, 1),
        ),
        (
            "guides/advanced.md",
            "Guides",
            "reference",
            "Advanced configuration and tuning options.",
            "Advanced configuration guide",
            datetime(2025, 1, 20),
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
        doc.last_modified = last_modified
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
# Axis 9: Cross-Reference Density
# ===========================================================================


class TestXrefNoneMetadata:
    """Verify metadata() for XrefNoneVariant."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = XrefNoneVariant().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = XrefNoneVariant().metadata()
        assert meta.name == "xref-none"

    def test_metadata_axis(self) -> None:
        meta = XrefNoneVariant().metadata()
        assert meta.axis == 9

    def test_metadata_category(self) -> None:
        meta = XrefNoneVariant().metadata()
        assert meta.category == "xref"


class TestXrefNoneRender:
    """Verify render() for XrefNoneVariant."""

    def test_render_contains_all_paths(self, doc_tree: MagicMock) -> None:
        result = XrefNoneVariant().render(doc_tree)
        assert "api/auth.md" in result
        assert "api/caching.md" in result
        assert "api/legacy.md" in result
        assert "guides/setup.md" in result
        assert "guides/advanced.md" in result

    def test_render_has_no_see_also(self, doc_tree: MagicMock) -> None:
        result = XrefNoneVariant().render(doc_tree)
        assert "See also" not in result

    def test_render_has_no_referenced_by(self, doc_tree: MagicMock) -> None:
        result = XrefNoneVariant().render(doc_tree)
        assert "Referenced by" not in result

    def test_render_includes_summaries(self, doc_tree: MagicMock) -> None:
        result = XrefNoneVariant().render(doc_tree)
        assert "JWT authentication module" in result

    def test_render_empty_tree(self) -> None:
        assert XrefNoneVariant().render(_empty_tree()) == ""


class TestXrefLightMetadata:
    """Verify metadata() for XrefLightVariant."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = XrefLightVariant().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = XrefLightVariant().metadata()
        assert meta.name == "xref-light"

    def test_metadata_axis(self) -> None:
        meta = XrefLightVariant().metadata()
        assert meta.axis == 9

    def test_metadata_category(self) -> None:
        meta = XrefLightVariant().metadata()
        assert meta.category == "xref"


class TestXrefLightRender:
    """Verify render() for XrefLightVariant."""

    def test_render_contains_all_paths(self, doc_tree: MagicMock) -> None:
        result = XrefLightVariant().render(doc_tree)
        assert "api/auth.md" in result
        assert "api/caching.md" in result
        assert "api/legacy.md" in result
        assert "guides/setup.md" in result
        assert "guides/advanced.md" in result

    def test_render_has_see_also(self, doc_tree: MagicMock) -> None:
        """Light xref adds See also for files sharing a section."""
        result = XrefLightVariant().render(doc_tree)
        assert "See also:" in result

    def test_render_see_also_lists_same_section_files(self, doc_tree: MagicMock) -> None:
        """See also lines reference files from the same section."""
        result = XrefLightVariant().render(doc_tree)
        lines = result.splitlines()
        # Find the See also line after api/auth.md
        for i, line in enumerate(lines):
            if "api/auth.md" in line and not line.strip().startswith("See also"):
                # Next line should be See also with other API files
                see_also_line = lines[i + 1]
                assert see_also_line.strip().startswith("See also:")
                assert "api/caching.md" in see_also_line
                break

    def test_render_no_referenced_by(self, doc_tree: MagicMock) -> None:
        """Light xref does not add Referenced by."""
        result = XrefLightVariant().render(doc_tree)
        assert "Referenced by" not in result

    def test_render_empty_tree(self) -> None:
        assert XrefLightVariant().render(_empty_tree()) == ""


class TestXrefDenseMetadata:
    """Verify metadata() for XrefDenseVariant."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = XrefDenseVariant().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = XrefDenseVariant().metadata()
        assert meta.name == "xref-dense"

    def test_metadata_axis(self) -> None:
        meta = XrefDenseVariant().metadata()
        assert meta.axis == 9

    def test_metadata_category(self) -> None:
        meta = XrefDenseVariant().metadata()
        assert meta.category == "xref"


class TestXrefDenseRender:
    """Verify render() for XrefDenseVariant."""

    def test_render_contains_all_paths(self, doc_tree: MagicMock) -> None:
        result = XrefDenseVariant().render(doc_tree)
        assert "api/auth.md" in result
        assert "api/caching.md" in result
        assert "api/legacy.md" in result
        assert "guides/setup.md" in result
        assert "guides/advanced.md" in result

    def test_render_has_see_also(self, doc_tree: MagicMock) -> None:
        """Dense xref adds See also entries."""
        result = XrefDenseVariant().render(doc_tree)
        assert "See also:" in result

    def test_render_has_referenced_by(self, doc_tree: MagicMock) -> None:
        """Dense xref adds Referenced by entries for content-based mentions."""
        result = XrefDenseVariant().render(doc_tree)
        # api/auth.md content mentions "caching", so it should reference api/caching.md
        assert "Referenced by:" in result

    def test_render_see_also_includes_content_mentions(self, doc_tree: MagicMock) -> None:
        """See also includes files whose content mentions the current file's stem."""
        result = XrefDenseVariant().render(doc_tree)
        lines = result.splitlines()
        # For api/auth.md, its stem is "auth".
        # api/caching.md mentions "auth" and api/legacy.md mentions "auth",
        # plus guides/setup.md mentions "auth".
        # Section peers for auth: caching, legacy (up to 3 from same section).
        # Content mentioners (not already in section peers) who mention "auth": guides/setup.md
        for i, line in enumerate(lines):
            if line.startswith("- api/auth.md"):
                see_also_line = lines[i + 1]
                assert "See also:" in see_also_line
                # Section peers
                assert "api/caching.md" in see_also_line
                assert "api/legacy.md" in see_also_line
                # Content mentioner from different section
                assert "guides/setup.md" in see_also_line
                break

    def test_render_referenced_by_reflects_content(self, doc_tree: MagicMock) -> None:
        """Referenced by lists files whose stems appear in the current file's content."""
        result = XrefDenseVariant().render(doc_tree)
        lines = result.splitlines()
        # api/auth.md content mentions "caching", so Referenced by should list api/caching.md
        for i, line in enumerate(lines):
            if line.startswith("- api/auth.md"):
                # Look for Referenced by line (may be i+1 or i+2 depending on See also)
                ref_lines = []
                for j in range(i + 1, min(i + 4, len(lines))):
                    if lines[j].strip().startswith("Referenced by:"):
                        ref_lines.append(lines[j])
                assert len(ref_lines) == 1
                assert "api/caching.md" in ref_lines[0]
                break

    def test_render_empty_tree(self) -> None:
        assert XrefDenseVariant().render(_empty_tree()) == ""


# ===========================================================================
# Axis 10: Temporal Markers
# ===========================================================================


class TestTemporalNoneMetadata:
    """Verify metadata() for TemporalNoneVariant."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = TemporalNoneVariant().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = TemporalNoneVariant().metadata()
        assert meta.name == "temporal-none"

    def test_metadata_axis(self) -> None:
        meta = TemporalNoneVariant().metadata()
        assert meta.axis == 10

    def test_metadata_category(self) -> None:
        meta = TemporalNoneVariant().metadata()
        assert meta.category == "temporal"


class TestTemporalNoneRender:
    """Verify render() for TemporalNoneVariant."""

    def test_render_contains_all_paths(self, doc_tree: MagicMock) -> None:
        result = TemporalNoneVariant().render(doc_tree)
        assert "api/auth.md" in result
        assert "api/caching.md" in result
        assert "guides/setup.md" in result

    def test_render_has_no_timestamps(self, doc_tree: MagicMock) -> None:
        result = TemporalNoneVariant().render(doc_tree)
        assert "modified:" not in result
        assert "2025-" not in result
        assert "2024-" not in result

    def test_render_has_no_version_info(self, doc_tree: MagicMock) -> None:
        result = TemporalNoneVariant().render(doc_tree)
        assert "[v" not in result
        assert "unversioned" not in result

    def test_render_has_no_deprecation_tags(self, doc_tree: MagicMock) -> None:
        result = TemporalNoneVariant().render(doc_tree)
        assert "[DEPRECATED]" not in result
        assert "[CURRENT]" not in result

    def test_render_includes_summaries(self, doc_tree: MagicMock) -> None:
        result = TemporalNoneVariant().render(doc_tree)
        assert "JWT authentication module" in result

    def test_render_empty_tree(self) -> None:
        assert TemporalNoneVariant().render(_empty_tree()) == ""

    def test_render_contains_no_date_marker(self, doc_tree: MagicMock) -> None:
        """Temporal-none should include [no-date] to differentiate from xref-none."""
        result = TemporalNoneVariant().render(doc_tree)
        assert "[no-date]" in result

    def test_render_differs_from_xref_none(self, doc_tree: MagicMock) -> None:
        """Temporal-none and xref-none must produce different output."""
        temporal = TemporalNoneVariant().render(doc_tree)
        xref = XrefNoneVariant().render(doc_tree)
        assert temporal != xref


class TestTemporalVersionMetadata:
    """Verify metadata() for TemporalVersionVariant."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = TemporalVersionVariant().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = TemporalVersionVariant().metadata()
        assert meta.name == "temporal-version"

    def test_metadata_axis(self) -> None:
        meta = TemporalVersionVariant().metadata()
        assert meta.axis == 10

    def test_metadata_category(self) -> None:
        meta = TemporalVersionVariant().metadata()
        assert meta.category == "temporal"


class TestTemporalVersionRender:
    """Verify render() for TemporalVersionVariant."""

    def test_render_detects_since_pattern(self, doc_tree: MagicMock) -> None:
        """Detects @since X.Y version patterns."""
        result = TemporalVersionVariant().render(doc_tree)
        # api/auth.md has "@since 2.1"
        assert "[v2.1]" in result

    def test_render_detects_v_prefix_pattern(self, doc_tree: MagicMock) -> None:
        """Detects vX.Y version patterns."""
        result = TemporalVersionVariant().render(doc_tree)
        # api/caching.md has "v1.3"
        assert "[v1.3]" in result

    def test_render_detects_version_keyword_pattern(self, doc_tree: MagicMock) -> None:
        """Detects 'version X.Y' patterns."""
        result = TemporalVersionVariant().render(doc_tree)
        # api/legacy.md has "version 0.9"
        assert "[v0.9]" in result

    def test_render_shows_unversioned_for_no_pattern(self, doc_tree: MagicMock) -> None:
        """Files without version patterns show [unversioned]."""
        result = TemporalVersionVariant().render(doc_tree)
        # guides/advanced.md has no version string
        assert "[unversioned]" in result

    def test_render_contains_all_paths(self, doc_tree: MagicMock) -> None:
        result = TemporalVersionVariant().render(doc_tree)
        assert "api/auth.md" in result
        assert "guides/advanced.md" in result

    def test_render_empty_tree(self) -> None:
        assert TemporalVersionVariant().render(_empty_tree()) == ""


class TestTemporalModifiedMetadata:
    """Verify metadata() for TemporalModifiedVariant."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = TemporalModifiedVariant().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = TemporalModifiedVariant().metadata()
        assert meta.name == "temporal-modified"

    def test_metadata_axis(self) -> None:
        meta = TemporalModifiedVariant().metadata()
        assert meta.axis == 10

    def test_metadata_category(self) -> None:
        meta = TemporalModifiedVariant().metadata()
        assert meta.category == "temporal"


class TestTemporalModifiedRender:
    """Verify render() for TemporalModifiedVariant."""

    def test_render_shows_date_for_files_with_last_modified(self, doc_tree: MagicMock) -> None:
        """Files with last_modified show [modified: YYYY-MM-DD]."""
        result = TemporalModifiedVariant().render(doc_tree)
        assert "[modified: 2025-06-15]" in result  # api/auth.md
        assert "[modified: 2025-03-10]" in result  # api/caching.md
        assert "[modified: 2024-12-01]" in result  # guides/setup.md
        assert "[modified: 2025-01-20]" in result  # guides/advanced.md

    def test_render_shows_unknown_for_none_last_modified(self, doc_tree: MagicMock) -> None:
        """Files with last_modified=None show [modified: unknown]."""
        result = TemporalModifiedVariant().render(doc_tree)
        # api/legacy.md has last_modified=None
        assert "[modified: unknown]" in result

    def test_render_contains_all_paths(self, doc_tree: MagicMock) -> None:
        result = TemporalModifiedVariant().render(doc_tree)
        assert "api/auth.md" in result
        assert "api/legacy.md" in result
        assert "guides/setup.md" in result

    def test_render_empty_tree(self) -> None:
        assert TemporalModifiedVariant().render(_empty_tree()) == ""


class TestTemporalDeprecatedMetadata:
    """Verify metadata() for TemporalDeprecatedVariant."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = TemporalDeprecatedVariant().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = TemporalDeprecatedVariant().metadata()
        assert meta.name == "temporal-deprecated"

    def test_metadata_axis(self) -> None:
        meta = TemporalDeprecatedVariant().metadata()
        assert meta.axis == 10

    def test_metadata_category(self) -> None:
        meta = TemporalDeprecatedVariant().metadata()
        assert meta.category == "temporal"


class TestTemporalDeprecatedRender:
    """Verify render() for TemporalDeprecatedVariant."""

    def test_render_detects_deprecated_marker(self, doc_tree: MagicMock) -> None:
        """Files with @deprecated are tagged [DEPRECATED]."""
        result = TemporalDeprecatedVariant().render(doc_tree)
        lines = result.splitlines()
        legacy_line = [x for x in lines if "api/legacy.md" in x][0]
        assert "[DEPRECATED]" in legacy_line

    def test_render_detects_no_longer_supported(self, doc_tree: MagicMock) -> None:
        """Files with 'no longer supported' are tagged [DEPRECATED]."""
        result = TemporalDeprecatedVariant().render(doc_tree)
        lines = result.splitlines()
        setup_line = [x for x in lines if "guides/setup.md" in x][0]
        assert "[DEPRECATED]" in setup_line

    def test_render_tags_current_files(self, doc_tree: MagicMock) -> None:
        """Files without deprecation signals are tagged [CURRENT]."""
        result = TemporalDeprecatedVariant().render(doc_tree)
        lines = result.splitlines()
        advanced_line = [x for x in lines if "guides/advanced.md" in x][0]
        assert "[CURRENT]" in advanced_line

    def test_render_all_files_have_a_tag(self, doc_tree: MagicMock) -> None:
        """Every file entry has either [DEPRECATED] or [CURRENT]."""
        result = TemporalDeprecatedVariant().render(doc_tree)
        for line in result.splitlines():
            if line.startswith("- "):
                assert "[DEPRECATED]" in line or "[CURRENT]" in line

    def test_render_contains_all_paths(self, doc_tree: MagicMock) -> None:
        result = TemporalDeprecatedVariant().render(doc_tree)
        assert "api/auth.md" in result
        assert "api/caching.md" in result
        assert "api/legacy.md" in result
        assert "guides/setup.md" in result
        assert "guides/advanced.md" in result

    def test_render_empty_tree(self) -> None:
        assert TemporalDeprecatedVariant().render(_empty_tree()) == ""


# ===========================================================================
# Registration tests
# ===========================================================================


class TestAxis9Registration:
    """All Axis 9 cross-reference variants register correctly."""

    def test_all_three_xref_variants_register_on_axis_nine(self) -> None:
        register_variant(XrefNoneVariant)
        register_variant(XrefLightVariant)
        register_variant(XrefDenseVariant)

        variants = get_variants_for_axis(9)
        assert len(variants) == 3
        names = {v.metadata().name for v in variants}
        assert names == {
            "xref-none",
            "xref-light",
            "xref-dense",
        }


class TestAxis10Registration:
    """All Axis 10 temporal variants register correctly."""

    def test_all_four_temporal_variants_register_on_axis_ten(self) -> None:
        register_variant(TemporalNoneVariant)
        register_variant(TemporalVersionVariant)
        register_variant(TemporalModifiedVariant)
        register_variant(TemporalDeprecatedVariant)

        variants = get_variants_for_axis(10)
        assert len(variants) == 4
        names = {v.metadata().name for v in variants}
        assert names == {
            "temporal-none",
            "temporal-version",
            "temporal-modified",
            "temporal-deprecated",
        }
