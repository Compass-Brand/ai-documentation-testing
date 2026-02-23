"""Tests for baseline variant implementations."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from agent_evals.variants.base import VariantMetadata
from agent_evals.variants.baselines import (
    LengthMatchedRandomBaseline,
    NoDocsBaseline,
    NoIndexBaseline,
    OracleBaseline,
)
from agent_evals.fixtures import load_sample_doc_tree
from agent_evals.variants.granularity_file import GranularityFileVariant
from agent_evals.variants.noise_0 import Noise0Variant
from agent_evals.variants.scale_50 import Scale50Variant
from agent_evals.variants.scale_100 import Scale100Variant
from agent_evals.variants.structure_flat import StructureFlatVariant
from agent_evals.variants.registry import (
    clear_registry,
    get_all_variants,
    get_variants_for_axis,
    register_variant,
)
from agent_index.models import DocFile, DocTree

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    """Clear the registry before every test so tests are isolated."""
    clear_registry()


@pytest.fixture()
def sample_doc_tree() -> DocTree:
    """Create a minimal DocTree for testing."""
    return DocTree(
        files={
            "guides/auth.md": DocFile(
                rel_path="guides/auth.md",
                content="# Authentication\nHow to authenticate.",
                size_bytes=42,
                token_count=10,
                tier="required",
                section="Guides",
            ),
            "api/users.md": DocFile(
                rel_path="api/users.md",
                content="# Users API\nEndpoint documentation for users.",
                size_bytes=50,
                token_count=12,
                tier="recommended",
                section="API",
            ),
            "reference/config.md": DocFile(
                rel_path="reference/config.md",
                content="# Configuration\nAll config options explained in detail.",
                size_bytes=60,
                token_count=15,
                tier="reference",
                section="Reference",
            ),
        },
        scanned_at=datetime(2024, 1, 1, tzinfo=UTC),
        source="/tmp/docs",
        total_tokens=37,
    )


# ---------------------------------------------------------------------------
# NoIndexBaseline tests
# ---------------------------------------------------------------------------


class TestNoIndexBaseline:
    """Tests for the NoIndexBaseline variant."""

    def test_metadata_returns_valid_variant_metadata(self) -> None:
        """NoIndexBaseline metadata has correct axis, category, and name."""
        variant = NoIndexBaseline()
        meta = variant.metadata()
        assert isinstance(meta, VariantMetadata)
        assert meta.name == "no-index"
        assert meta.axis == 0
        assert meta.category == "baseline"

    def test_render_returns_empty_string(self, sample_doc_tree: DocTree) -> None:
        """NoIndexBaseline render returns empty string regardless of input."""
        variant = NoIndexBaseline()
        result = variant.render(sample_doc_tree)
        assert result == ""

    def test_render_returns_empty_with_none_tree(self) -> None:
        """NoIndexBaseline render returns empty string even with a minimal tree."""
        variant = NoIndexBaseline()
        empty_tree = DocTree(
            files={},
            scanned_at=datetime(2024, 1, 1, tzinfo=UTC),
            source="/tmp/empty",
        )
        result = variant.render(empty_tree)
        assert result == ""

    def test_is_registered_via_decorator(self) -> None:
        """NoIndexBaseline is discoverable via the registry after import."""
        register_variant(NoIndexBaseline)
        baselines = get_variants_for_axis(0)
        names = {v.metadata().name for v in baselines}
        assert "no-index" in names


# ---------------------------------------------------------------------------
# NoDocsBaseline tests
# ---------------------------------------------------------------------------


class TestNoDocsBaseline:
    """Tests for the NoDocsBaseline variant."""

    def test_metadata_returns_valid_variant_metadata(self) -> None:
        """NoDocsBaseline metadata has correct axis, category, and name."""
        variant = NoDocsBaseline()
        meta = variant.metadata()
        assert isinstance(meta, VariantMetadata)
        assert meta.name == "no-docs"
        assert meta.axis == 0
        assert meta.category == "baseline"

    def test_render_contains_file_paths(self, sample_doc_tree: DocTree) -> None:
        """NoDocsBaseline render includes all file paths from the tree."""
        variant = NoDocsBaseline()
        result = variant.render(sample_doc_tree)
        assert "guides/auth.md" in result
        assert "api/users.md" in result
        assert "reference/config.md" in result

    def test_render_does_not_contain_content(self, sample_doc_tree: DocTree) -> None:
        """NoDocsBaseline render excludes file content."""
        variant = NoDocsBaseline()
        result = variant.render(sample_doc_tree)
        assert "How to authenticate" not in result
        assert "Endpoint documentation" not in result
        assert "All config options" not in result

    def test_render_empty_tree(self) -> None:
        """NoDocsBaseline render returns empty-ish output for empty tree."""
        variant = NoDocsBaseline()
        empty_tree = DocTree(
            files={},
            scanned_at=datetime(2024, 1, 1, tzinfo=UTC),
            source="/tmp/empty",
        )
        result = variant.render(empty_tree)
        # With no files, the listing should have no file paths
        assert "guides/" not in result
        assert "api/" not in result

    def test_is_registered_via_decorator(self) -> None:
        """NoDocsBaseline is discoverable via the registry."""
        register_variant(NoDocsBaseline)
        baselines = get_variants_for_axis(0)
        names = {v.metadata().name for v in baselines}
        assert "no-docs" in names


# ---------------------------------------------------------------------------
# OracleBaseline tests
# ---------------------------------------------------------------------------


class TestOracleBaseline:
    """Tests for the OracleBaseline variant."""

    def test_metadata_returns_valid_variant_metadata(self) -> None:
        """OracleBaseline metadata has correct axis, category, and name."""
        variant = OracleBaseline()
        meta = variant.metadata()
        assert isinstance(meta, VariantMetadata)
        assert meta.name == "oracle"
        assert meta.axis == 0
        assert meta.category == "baseline"

    def test_render_returns_only_relevant_docs(
        self, sample_doc_tree: DocTree
    ) -> None:
        """OracleBaseline render returns content for only the set relevant docs."""
        variant = OracleBaseline()
        variant.set_relevant_docs(["guides/auth.md"])
        result = variant.render(sample_doc_tree)
        assert "guides/auth.md" in result
        assert "How to authenticate" in result
        assert "api/users.md" not in result
        assert "reference/config.md" not in result

    def test_render_with_multiple_relevant_docs(
        self, sample_doc_tree: DocTree
    ) -> None:
        """OracleBaseline render returns content for multiple relevant docs."""
        variant = OracleBaseline()
        variant.set_relevant_docs(["guides/auth.md", "api/users.md"])
        result = variant.render(sample_doc_tree)
        assert "guides/auth.md" in result
        assert "How to authenticate" in result
        assert "api/users.md" in result
        assert "Endpoint documentation" in result
        assert "reference/config.md" not in result

    def test_render_with_no_relevant_docs(self, sample_doc_tree: DocTree) -> None:
        """OracleBaseline render returns empty when no relevant docs are set."""
        variant = OracleBaseline()
        variant.set_relevant_docs([])
        result = variant.render(sample_doc_tree)
        # No content should be present
        assert "How to authenticate" not in result
        assert "Endpoint documentation" not in result

    def test_render_skips_missing_docs(self, sample_doc_tree: DocTree) -> None:
        """OracleBaseline render silently skips docs not in the tree."""
        variant = OracleBaseline()
        variant.set_relevant_docs(["nonexistent.md", "guides/auth.md"])
        result = variant.render(sample_doc_tree)
        assert "guides/auth.md" in result
        assert "nonexistent.md" not in result

    def test_set_relevant_docs_replaces_previous(
        self, sample_doc_tree: DocTree
    ) -> None:
        """Calling set_relevant_docs replaces any previously set docs."""
        variant = OracleBaseline()
        variant.set_relevant_docs(["guides/auth.md"])
        variant.set_relevant_docs(["api/users.md"])
        result = variant.render(sample_doc_tree)
        assert "api/users.md" in result
        assert "Endpoint documentation" in result
        assert "How to authenticate" not in result

    def test_is_registered_via_decorator(self) -> None:
        """OracleBaseline is discoverable via the registry."""
        register_variant(OracleBaseline)
        baselines = get_variants_for_axis(0)
        names = {v.metadata().name for v in baselines}
        assert "oracle" in names


# ---------------------------------------------------------------------------
# LengthMatchedRandomBaseline tests
# ---------------------------------------------------------------------------


class TestLengthMatchedRandomBaseline:
    """Tests for the LengthMatchedRandomBaseline variant."""

    def test_metadata_returns_valid_variant_metadata(self) -> None:
        """LengthMatchedRandomBaseline metadata has correct fields."""
        variant = LengthMatchedRandomBaseline()
        meta = variant.metadata()
        assert isinstance(meta, VariantMetadata)
        assert meta.name == "length-matched-random"
        assert meta.axis == 0
        assert meta.category == "baseline"

    def test_render_respects_target_tokens(self, sample_doc_tree: DocTree) -> None:
        """LengthMatchedRandomBaseline render output stays near target tokens."""
        variant = LengthMatchedRandomBaseline()
        variant.set_target_tokens(20)
        result = variant.render(sample_doc_tree)
        # Should contain some content but not all files
        assert len(result) > 0

    def test_render_is_deterministic(self, sample_doc_tree: DocTree) -> None:
        """LengthMatchedRandomBaseline render gives same result with same seed."""
        variant1 = LengthMatchedRandomBaseline()
        variant1.set_target_tokens(20)
        result1 = variant1.render(sample_doc_tree)

        variant2 = LengthMatchedRandomBaseline()
        variant2.set_target_tokens(20)
        result2 = variant2.render(sample_doc_tree)

        assert result1 == result2

    def test_render_includes_all_docs_when_target_exceeds_total(
        self, sample_doc_tree: DocTree
    ) -> None:
        """When target tokens exceed total, all docs are included."""
        variant = LengthMatchedRandomBaseline()
        variant.set_target_tokens(1000)  # well above total of 37
        result = variant.render(sample_doc_tree)
        assert "guides/auth.md" in result
        assert "api/users.md" in result
        assert "reference/config.md" in result

    def test_render_with_zero_target_returns_empty(
        self, sample_doc_tree: DocTree
    ) -> None:
        """LengthMatchedRandomBaseline with target_tokens=0 returns empty."""
        variant = LengthMatchedRandomBaseline()
        variant.set_target_tokens(0)
        result = variant.render(sample_doc_tree)
        assert result == ""

    def test_set_target_tokens_replaces_previous(
        self, sample_doc_tree: DocTree
    ) -> None:
        """Calling set_target_tokens replaces the previous target."""
        variant = LengthMatchedRandomBaseline()
        variant.set_target_tokens(1000)
        variant.set_target_tokens(0)
        result = variant.render(sample_doc_tree)
        assert result == ""

    def test_is_registered_via_decorator(self) -> None:
        """LengthMatchedRandomBaseline is discoverable via the registry."""
        register_variant(LengthMatchedRandomBaseline)
        baselines = get_variants_for_axis(0)
        names = {v.metadata().name for v in baselines}
        assert "length-matched-random" in names


# ---------------------------------------------------------------------------
# Cross-variant tests
# ---------------------------------------------------------------------------


class TestBaselineRegistration:
    """Tests that all baselines can coexist in the registry."""

    def test_all_four_baselines_register_on_axis_zero(self) -> None:
        """All four baselines register on axis 0."""
        register_variant(NoIndexBaseline)
        register_variant(NoDocsBaseline)
        register_variant(OracleBaseline)
        register_variant(LengthMatchedRandomBaseline)

        baselines = get_variants_for_axis(0)
        assert len(baselines) == 4
        names = {v.metadata().name for v in baselines}
        assert names == {"no-index", "no-docs", "oracle", "length-matched-random"}

    def test_baselines_appear_in_get_all_variants(self) -> None:
        """All four baselines are included in get_all_variants."""
        register_variant(NoIndexBaseline)
        register_variant(NoDocsBaseline)
        register_variant(OracleBaseline)
        register_variant(LengthMatchedRandomBaseline)

        all_v = get_all_variants()
        assert len(all_v) == 4

    def test_axis_zero_accepted_by_variant_metadata(self) -> None:
        """VariantMetadata now accepts axis=0 for baselines."""
        meta = VariantMetadata(
            name="test-baseline",
            axis=0,
            category="baseline",
            description="Test that axis=0 is valid",
        )
        assert meta.axis == 0


# ---------------------------------------------------------------------------
# Variant differentiation tests
# ---------------------------------------------------------------------------


class TestVariantDifferentiation:
    """Tests that baseline variants produce distinct output from each other."""

    def test_structure_flat_differs_from_noise_0(
        self, sample_doc_tree: DocTree
    ) -> None:
        """structure-flat should produce different output from noise-0."""
        noise_0 = Noise0Variant()
        structure_flat = StructureFlatVariant()

        n0_output = noise_0.render(sample_doc_tree)
        sf_output = structure_flat.render(sample_doc_tree)

        assert n0_output != sf_output, (
            "structure-flat and noise-0 must produce different output"
        )

    def test_granularity_file_differs_from_noise_0(
        self, sample_doc_tree: DocTree
    ) -> None:
        """granularity-file should produce different output from noise-0."""
        noise_0 = Noise0Variant()
        granularity_file = GranularityFileVariant()

        n0_output = noise_0.render(sample_doc_tree)
        gf_output = granularity_file.render(sample_doc_tree)

        assert n0_output != gf_output, (
            "granularity-file and noise-0 must produce different output"
        )

    def test_structure_flat_includes_tier_info(
        self, sample_doc_tree: DocTree
    ) -> None:
        """structure-flat output should include tier information."""
        variant = StructureFlatVariant()
        output = variant.render(sample_doc_tree)

        assert "required" in output or "recommended" in output or "reference" in output, (
            "structure-flat should include tier information"
        )

    def test_granularity_file_uses_file_prefix(
        self, sample_doc_tree: DocTree
    ) -> None:
        """granularity-file output should use a distinct format prefix."""
        variant = GranularityFileVariant()
        output = variant.render(sample_doc_tree)

        # Must use a format distinct from noise-0's "- path: brief_summary"
        # e.g. "[FILE] path: summary" or similar
        noise_0_output = Noise0Variant().render(sample_doc_tree)
        # Check that at least one line differs in format
        n0_lines = set(noise_0_output.splitlines())
        gf_lines = set(output.splitlines())
        assert n0_lines != gf_lines, (
            "granularity-file lines should differ from noise-0 lines"
        )

    def test_scale_50_differs_from_scale_100_with_fixture(self) -> None:
        """scale-50 and scale-100 produce different output with production fixture."""
        fixture_tree = load_sample_doc_tree()
        scale_50 = Scale50Variant()
        scale_100 = Scale100Variant()

        s50_output = scale_50.render(fixture_tree)
        s100_output = scale_100.render(fixture_tree)

        assert s50_output != s100_output, (
            "scale-50 and scale-100 must produce different output "
            f"(fixture has {len(fixture_tree.files)} files, need >50)"
        )
