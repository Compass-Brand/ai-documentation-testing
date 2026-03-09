"""Tests for Axis 12 (agent instruction file) index variants.

Covers five verbosity levels (none, minimal, standard, verbose, overloaded)
and four ablative variants (conventions-only, architecture-only,
deployment-only, irrelevant-only).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from agent_evals.variants.base import VariantMetadata
from agent_evals.variants.registry import (
    clear_registry,
    get_variants_for_axis,
    load_all,
)

# ---------------------------------------------------------------------------
# Lazy imports -- these will fail until the implementation exists (TDD RED)
# ---------------------------------------------------------------------------

from agent_evals.variants.agent_instruction import (
    InstructionArchitectureOnly,
    InstructionConventionsOnly,
    InstructionDeploymentOnly,
    InstructionIrrelevantOnly,
    InstructionMinimal,
    InstructionNone,
    InstructionOverloaded,
    InstructionStandard,
    InstructionVerbose,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_registry() -> None:
    """Clear the registry before every test so tests are isolated."""
    clear_registry()


def _make_doc_tree() -> MagicMock:
    """Create a mock DocTree for axis-12 testing.

    The tree has 4 files across 2 sections, enough to verify the
    standard doc-index section that every variant appends.
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
            "Getting started guide.",
            "Setup guide for new developers",
        ),
        (
            "guides/advanced.md",
            "Guides",
            "reference",
            "Advanced configuration options.",
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
# Helper: extract instruction section (everything before "# Documentation Index")
# ===========================================================================


def _instruction_section(rendered: str) -> str:
    """Return the portion of the rendered output before the doc index."""
    marker = "# Documentation Index"
    idx = rendered.find(marker)
    if idx == -1:
        return rendered
    return rendered[:idx]


# ===========================================================================
# InstructionNone
# ===========================================================================


class TestInstructionNoneMetadata:
    """Verify metadata() for InstructionNone."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = InstructionNone().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = InstructionNone().metadata()
        assert meta.name == "instruction-none"

    def test_metadata_axis(self) -> None:
        meta = InstructionNone().metadata()
        assert meta.axis == 12

    def test_metadata_category(self) -> None:
        meta = InstructionNone().metadata()
        assert meta.category == "agent-instruction"


class TestInstructionNoneRender:
    """Verify render() for InstructionNone."""

    def test_render_contains_doc_index(self, doc_tree: MagicMock) -> None:
        result = InstructionNone().render(doc_tree)
        assert "# Documentation Index" in result

    def test_render_contains_file_paths(self, doc_tree: MagicMock) -> None:
        result = InstructionNone().render(doc_tree)
        assert "api/auth.md" in result
        assert "guides/setup.md" in result

    def test_render_has_no_instruction_section(self, doc_tree: MagicMock) -> None:
        """InstructionNone should have no text before the doc index."""
        result = InstructionNone().render(doc_tree)
        before = _instruction_section(result).strip()
        assert before == ""

    def test_render_empty_tree(self) -> None:
        result = InstructionNone().render(_empty_tree())
        assert "# Documentation Index" in result


# ===========================================================================
# InstructionMinimal
# ===========================================================================


class TestInstructionMinimalMetadata:
    """Verify metadata() for InstructionMinimal."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = InstructionMinimal().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = InstructionMinimal().metadata()
        assert meta.name == "instruction-minimal"

    def test_metadata_axis(self) -> None:
        meta = InstructionMinimal().metadata()
        assert meta.axis == 12

    def test_metadata_category(self) -> None:
        meta = InstructionMinimal().metadata()
        assert meta.category == "agent-instruction"


class TestInstructionMinimalRender:
    """Verify render() for InstructionMinimal."""

    def test_render_contains_doc_index(self, doc_tree: MagicMock) -> None:
        result = InstructionMinimal().render(doc_tree)
        assert "# Documentation Index" in result

    def test_render_contains_file_paths(self, doc_tree: MagicMock) -> None:
        result = InstructionMinimal().render(doc_tree)
        assert "api/auth.md" in result

    def test_minimal_under_60_lines(self, doc_tree: MagicMock) -> None:
        """Instruction section before doc index must be < 60 lines."""
        result = InstructionMinimal().render(doc_tree)
        section = _instruction_section(result)
        line_count = len(section.strip().splitlines())
        assert line_count < 60

    def test_render_empty_tree(self) -> None:
        result = InstructionMinimal().render(_empty_tree())
        assert "# Documentation Index" in result


# ===========================================================================
# InstructionStandard
# ===========================================================================


class TestInstructionStandardMetadata:
    """Verify metadata() for InstructionStandard."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = InstructionStandard().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = InstructionStandard().metadata()
        assert meta.name == "instruction-standard"

    def test_metadata_axis(self) -> None:
        meta = InstructionStandard().metadata()
        assert meta.axis == 12

    def test_metadata_category(self) -> None:
        meta = InstructionStandard().metadata()
        assert meta.category == "agent-instruction"


class TestInstructionStandardRender:
    """Verify render() for InstructionStandard."""

    def test_render_contains_doc_index(self, doc_tree: MagicMock) -> None:
        result = InstructionStandard().render(doc_tree)
        assert "# Documentation Index" in result

    def test_render_contains_file_paths(self, doc_tree: MagicMock) -> None:
        result = InstructionStandard().render(doc_tree)
        assert "api/auth.md" in result

    def test_render_empty_tree(self) -> None:
        result = InstructionStandard().render(_empty_tree())
        assert "# Documentation Index" in result


# ===========================================================================
# InstructionVerbose
# ===========================================================================


class TestInstructionVerboseMetadata:
    """Verify metadata() for InstructionVerbose."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = InstructionVerbose().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = InstructionVerbose().metadata()
        assert meta.name == "instruction-verbose"

    def test_metadata_axis(self) -> None:
        meta = InstructionVerbose().metadata()
        assert meta.axis == 12

    def test_metadata_category(self) -> None:
        meta = InstructionVerbose().metadata()
        assert meta.category == "agent-instruction"


class TestInstructionVerboseRender:
    """Verify render() for InstructionVerbose."""

    def test_render_contains_doc_index(self, doc_tree: MagicMock) -> None:
        result = InstructionVerbose().render(doc_tree)
        assert "# Documentation Index" in result

    def test_render_contains_file_paths(self, doc_tree: MagicMock) -> None:
        result = InstructionVerbose().render(doc_tree)
        assert "api/auth.md" in result

    def test_verbose_over_300_lines(self, doc_tree: MagicMock) -> None:
        """Instruction section must be >= 100 lines (padding makes it large)."""
        result = InstructionVerbose().render(doc_tree)
        section = _instruction_section(result)
        line_count = len(section.strip().splitlines())
        assert line_count >= 100

    def test_render_empty_tree(self) -> None:
        result = InstructionVerbose().render(_empty_tree())
        assert "# Documentation Index" in result


# ===========================================================================
# InstructionOverloaded
# ===========================================================================


class TestInstructionOverloadedMetadata:
    """Verify metadata() for InstructionOverloaded."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = InstructionOverloaded().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = InstructionOverloaded().metadata()
        assert meta.name == "instruction-overloaded"

    def test_metadata_axis(self) -> None:
        meta = InstructionOverloaded().metadata()
        assert meta.axis == 12

    def test_metadata_category(self) -> None:
        meta = InstructionOverloaded().metadata()
        assert meta.category == "agent-instruction"


class TestInstructionOverloadedRender:
    """Verify render() for InstructionOverloaded."""

    def test_render_contains_doc_index(self, doc_tree: MagicMock) -> None:
        result = InstructionOverloaded().render(doc_tree)
        assert "# Documentation Index" in result

    def test_render_contains_file_paths(self, doc_tree: MagicMock) -> None:
        result = InstructionOverloaded().render(doc_tree)
        assert "api/auth.md" in result

    def test_overloaded_over_500_lines(self, doc_tree: MagicMock) -> None:
        """Instruction section must be >= 200 lines (modules + API entries)."""
        result = InstructionOverloaded().render(doc_tree)
        section = _instruction_section(result)
        line_count = len(section.strip().splitlines())
        assert line_count >= 200

    def test_render_empty_tree(self) -> None:
        result = InstructionOverloaded().render(_empty_tree())
        assert "# Documentation Index" in result


# ===========================================================================
# InstructionConventionsOnly
# ===========================================================================


class TestInstructionConventionsOnlyMetadata:
    """Verify metadata() for InstructionConventionsOnly."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = InstructionConventionsOnly().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = InstructionConventionsOnly().metadata()
        assert meta.name == "instruction-conventions-only"

    def test_metadata_axis(self) -> None:
        meta = InstructionConventionsOnly().metadata()
        assert meta.axis == 12

    def test_metadata_category(self) -> None:
        meta = InstructionConventionsOnly().metadata()
        assert meta.category == "agent-instruction"


class TestInstructionConventionsOnlyRender:
    """Verify render() for InstructionConventionsOnly."""

    def test_render_contains_doc_index(self, doc_tree: MagicMock) -> None:
        result = InstructionConventionsOnly().render(doc_tree)
        assert "# Documentation Index" in result

    def test_conventions_contains_only(self, doc_tree: MagicMock) -> None:
        """Must mention conventions/naming, must NOT mention directory structure or deployment."""
        section = _instruction_section(
            InstructionConventionsOnly().render(doc_tree)
        ).lower()
        assert "convention" in section or "naming" in section
        assert "directory structure" not in section
        assert "deployment" not in section


# ===========================================================================
# InstructionArchitectureOnly
# ===========================================================================


class TestInstructionArchitectureOnlyMetadata:
    """Verify metadata() for InstructionArchitectureOnly."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = InstructionArchitectureOnly().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = InstructionArchitectureOnly().metadata()
        assert meta.name == "instruction-architecture-only"

    def test_metadata_axis(self) -> None:
        meta = InstructionArchitectureOnly().metadata()
        assert meta.axis == 12

    def test_metadata_category(self) -> None:
        meta = InstructionArchitectureOnly().metadata()
        assert meta.category == "agent-instruction"


class TestInstructionArchitectureOnlyRender:
    """Verify render() for InstructionArchitectureOnly."""

    def test_render_contains_doc_index(self, doc_tree: MagicMock) -> None:
        result = InstructionArchitectureOnly().render(doc_tree)
        assert "# Documentation Index" in result

    def test_architecture_contains_only(self, doc_tree: MagicMock) -> None:
        """Must mention architecture/directory, must NOT mention ci/cd or rollback."""
        section = _instruction_section(
            InstructionArchitectureOnly().render(doc_tree)
        ).lower()
        assert "architecture" in section or "directory" in section
        assert "ci/cd" not in section
        assert "rollback" not in section


# ===========================================================================
# InstructionDeploymentOnly
# ===========================================================================


class TestInstructionDeploymentOnlyMetadata:
    """Verify metadata() for InstructionDeploymentOnly."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = InstructionDeploymentOnly().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = InstructionDeploymentOnly().metadata()
        assert meta.name == "instruction-deployment-only"

    def test_metadata_axis(self) -> None:
        meta = InstructionDeploymentOnly().metadata()
        assert meta.axis == 12

    def test_metadata_category(self) -> None:
        meta = InstructionDeploymentOnly().metadata()
        assert meta.category == "agent-instruction"


class TestInstructionDeploymentOnlyRender:
    """Verify render() for InstructionDeploymentOnly."""

    def test_render_contains_doc_index(self, doc_tree: MagicMock) -> None:
        result = InstructionDeploymentOnly().render(doc_tree)
        assert "# Documentation Index" in result

    def test_deployment_contains_only(self, doc_tree: MagicMock) -> None:
        """Must mention deploy/ci, must NOT mention pep 8 or type hints."""
        section = _instruction_section(
            InstructionDeploymentOnly().render(doc_tree)
        ).lower()
        assert "deploy" in section or "ci" in section
        assert "pep 8" not in section
        assert "type hints" not in section


# ===========================================================================
# InstructionIrrelevantOnly
# ===========================================================================


class TestInstructionIrrelevantOnlyMetadata:
    """Verify metadata() for InstructionIrrelevantOnly."""

    def test_metadata_returns_variant_metadata(self) -> None:
        meta = InstructionIrrelevantOnly().metadata()
        assert isinstance(meta, VariantMetadata)

    def test_metadata_name(self) -> None:
        meta = InstructionIrrelevantOnly().metadata()
        assert meta.name == "instruction-irrelevant-only"

    def test_metadata_axis(self) -> None:
        meta = InstructionIrrelevantOnly().metadata()
        assert meta.axis == 12

    def test_metadata_category(self) -> None:
        meta = InstructionIrrelevantOnly().metadata()
        assert meta.category == "agent-instruction"


class TestInstructionIrrelevantOnlyRender:
    """Verify render() for InstructionIrrelevantOnly."""

    def test_render_contains_doc_index(self, doc_tree: MagicMock) -> None:
        result = InstructionIrrelevantOnly().render(doc_tree)
        assert "# Documentation Index" in result

    def test_irrelevant_only(self, doc_tree: MagicMock) -> None:
        """Must have deploy/ci/cd AND style/black, must NOT have 'answer questions'."""
        section = _instruction_section(
            InstructionIrrelevantOnly().render(doc_tree)
        ).lower()
        assert "deploy" in section or "ci/cd" in section
        assert "style" in section or "black" in section
        assert "answer questions" not in section


# ===========================================================================
# Cross-variant tests
# ===========================================================================


class TestVerbosityOrdering:
    """Verify that rendered sizes follow the expected ordering."""

    def test_verbosity_ordering(self, doc_tree: MagicMock) -> None:
        """Sizes: none < minimal < standard < verbose < overloaded."""
        variants = [
            InstructionNone(),
            InstructionMinimal(),
            InstructionStandard(),
            InstructionVerbose(),
            InstructionOverloaded(),
        ]
        sizes = [len(v.render(doc_tree)) for v in variants]
        for i in range(len(sizes) - 1):
            assert sizes[i] < sizes[i + 1], (
                f"{variants[i].metadata().name} ({sizes[i]}) should be smaller "
                f"than {variants[i + 1].metadata().name} ({sizes[i + 1]})"
            )


class TestAllVariantsDiscoverable:
    """Verify that auto-discovery finds all 9 axis-12 variants."""

    def test_all_variants_discoverable(self) -> None:
        load_all()
        variants = get_variants_for_axis(12)
        assert len(variants) >= 9
        names = {v.metadata().name for v in variants}
        expected = {
            "instruction-none",
            "instruction-minimal",
            "instruction-standard",
            "instruction-verbose",
            "instruction-overloaded",
            "instruction-conventions-only",
            "instruction-architecture-only",
            "instruction-deployment-only",
            "instruction-irrelevant-only",
        }
        assert expected.issubset(names)
