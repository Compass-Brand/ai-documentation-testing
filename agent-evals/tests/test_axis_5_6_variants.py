"""Tests for Axis 5 (doc transformation) and Axis 6 (index scale) variants."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from agent_evals.variants.base import VariantMetadata
from agent_evals.variants.registry import (
    clear_registry,
    get_all_variants,
    get_variants_for_axis,
    register_variant,
)
from agent_evals.variants.scale_5 import Scale5Variant
from agent_evals.variants.scale_15 import Scale15Variant
from agent_evals.variants.scale_50 import Scale50Variant
from agent_evals.variants.scale_100 import Scale100Variant
from agent_evals.variants.scale_200 import Scale200Variant
from agent_evals.variants.transform_algorithmic import TransformAlgorithmicVariant
from agent_evals.variants.transform_llm_compressed import (
    TransformLlmCompressedVariant,
)
from agent_evals.variants.transform_passthrough import TransformPassthroughVariant
from agent_evals.variants.transform_restructured import TransformRestructuredVariant
from agent_evals.variants.transform_tagged import TransformTaggedVariant

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc_tree(file_count: int = 10) -> MagicMock:
    """Create a mock DocTree with varied content for testing.

    Generates *file_count* files with a mix of markdown headings, code
    blocks, and multi-paragraph text to exercise all transform variants.
    """
    file_specs: list[tuple[str, str, str, str]] = [
        (
            "api/auth.md",
            "API",
            "required",
            (
                "# Authentication\n\n"
                "JWT tokens are used for auth.\n\n"
                "## Setup\n\n"
                "Install the auth middleware:\n\n"
                "```python\nfrom auth import middleware\n```\n\n"
                "Then configure the secret key.\n\n"
                "## Refresh Tokens\n\n"
                "Tokens expire after 1 hour."
            ),
        ),
        (
            "api/caching.md",
            "API",
            "recommended",
            (
                "# Caching\n\n"
                "Response caching with CacheConfig.\n\n"
                "```typescript\nconst cache = new CacheConfig();\n```\n\n"
                "Set TTL to 300 seconds for best results."
            ),
        ),
        (
            "guides/setup.md",
            "Guides",
            "required",
            (
                "# Getting Started\n\n"
                "Welcome to the project.\n\n"
                "## Prerequisites\n\n"
                "You need Python 3.11+ and Node.js 18+.\n\n"
                "## Installation\n\n"
                "Run `pip install myproject` to begin.\n\n"
                "Then run `npm install` for frontend dependencies."
            ),
        ),
        (
            "guides/advanced.md",
            "Guides",
            "reference",
            (
                "# Advanced Configuration\n\n"
                "This guide covers advanced topics.\n\n"
                "## Custom Plugins\n\n"
                "```python\nclass MyPlugin:\n    pass\n```\n\n"
                "Register plugins in the config file."
            ),
        ),
        (
            "guides/deployment.md",
            "Guides",
            "recommended",
            (
                "# Deployment\n\n"
                "Deploy to production in three steps.\n\n"
                "Step 1: Build the image.\n"
                "Step 2: Push to registry.\n"
                "Step 3: Update the service."
            ),
        ),
        (
            "reference/api-spec.md",
            "Reference",
            "reference",
            (
                "# API Specification\n\n"
                "## Endpoints\n\n"
                "### GET /users\n\n"
                "Returns a list of users.\n\n"
                "### POST /users\n\n"
                "Creates a new user.\n\n"
                "```json\n{\"name\": \"example\"}\n```"
            ),
        ),
        (
            "reference/changelog.md",
            "Reference",
            "reference",
            (
                "# Changelog\n\n"
                "## v2.0.0\n\n"
                "Breaking changes to auth module.\n\n"
                "## v1.5.0\n\n"
                "Added caching support."
            ),
        ),
        (
            "reference/glossary.md",
            "Reference",
            "reference",
            "A plain text file with no headings or code blocks.\nJust simple text.",
        ),
        (
            "tutorials/quickstart.md",
            "Tutorials",
            "required",
            (
                "# Quickstart\n\n"
                "Get running in five minutes.\n\n"
                "```bash\npip install myproject\nmyproject init\n```\n\n"
                "Follow the prompts to finish setup."
            ),
        ),
        (
            "tutorials/testing.md",
            "Tutorials",
            "recommended",
            (
                "# Testing Guide\n\n"
                "Write tests with pytest.\n\n"
                "```python\ndef test_example():\n    assert True\n```\n\n"
                "Run `pytest` to execute all tests."
            ),
        ),
    ]

    tree = MagicMock()
    files: dict[str, MagicMock] = {}

    for i, (path, section, tier, content) in enumerate(file_specs):
        if i >= file_count:
            break
        doc = MagicMock()
        doc.rel_path = path
        doc.content = content
        doc.size_bytes = len(content)
        doc.token_count = len(content) // 4
        doc.tier = tier
        doc.section = section
        doc.priority = 0
        doc.summary = None
        doc.related = []
        files[path] = doc

    tree.files = files
    return tree


def _make_large_doc_tree(file_count: int) -> MagicMock:
    """Create a mock DocTree with many simple files for scale testing."""
    tree = MagicMock()
    files: dict[str, MagicMock] = {}
    for i in range(file_count):
        path = f"docs/file_{i:04d}.md"
        doc = MagicMock()
        doc.rel_path = path
        doc.content = f"# File {i}\n\nContent of file number {i}."
        doc.size_bytes = 40
        doc.token_count = 10
        doc.tier = "reference"
        doc.section = "Docs"
        doc.priority = 0
        doc.summary = None
        doc.related = []
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


@pytest.fixture
def doc_tree() -> MagicMock:
    """Provide a mock DocTree with ~10 files."""
    return _make_doc_tree()


@pytest.fixture
def empty_tree() -> MagicMock:
    """Provide a mock DocTree with no files."""
    tree = MagicMock()
    tree.files = {}
    return tree


# ---------------------------------------------------------------------------
# Axis 5: Transform variants -- metadata tests
# ---------------------------------------------------------------------------


class TestTransformMetadata:
    """Verify metadata() for all five Axis 5 transform variants."""

    @pytest.mark.parametrize(
        ("variant_cls", "expected_name"),
        [
            (TransformPassthroughVariant, "transform-passthrough"),
            (TransformAlgorithmicVariant, "transform-algorithmic"),
            (TransformLlmCompressedVariant, "transform-llm-compressed"),
            (TransformRestructuredVariant, "transform-restructured"),
            (TransformTaggedVariant, "transform-tagged"),
        ],
    )
    def test_metadata_name(self, variant_cls: type, expected_name: str) -> None:
        """Each transform variant reports the correct name."""
        meta = variant_cls().metadata()
        assert meta.name == expected_name

    @pytest.mark.parametrize(
        "variant_cls",
        [
            TransformPassthroughVariant,
            TransformAlgorithmicVariant,
            TransformLlmCompressedVariant,
            TransformRestructuredVariant,
            TransformTaggedVariant,
        ],
    )
    def test_metadata_axis(self, variant_cls: type) -> None:
        """All transform variants belong to axis 5."""
        meta = variant_cls().metadata()
        assert meta.axis == 5

    @pytest.mark.parametrize(
        "variant_cls",
        [
            TransformPassthroughVariant,
            TransformAlgorithmicVariant,
            TransformLlmCompressedVariant,
            TransformRestructuredVariant,
            TransformTaggedVariant,
        ],
    )
    def test_metadata_category(self, variant_cls: type) -> None:
        """All transform variants have category 'transform'."""
        meta = variant_cls().metadata()
        assert meta.category == "transform"

    @pytest.mark.parametrize(
        "variant_cls",
        [
            TransformPassthroughVariant,
            TransformAlgorithmicVariant,
            TransformLlmCompressedVariant,
            TransformRestructuredVariant,
            TransformTaggedVariant,
        ],
    )
    def test_metadata_returns_variant_metadata(self, variant_cls: type) -> None:
        """metadata() returns a VariantMetadata instance."""
        meta = variant_cls().metadata()
        assert isinstance(meta, VariantMetadata)


# ---------------------------------------------------------------------------
# Axis 6: Scale variants -- metadata tests
# ---------------------------------------------------------------------------


class TestScaleMetadata:
    """Verify metadata() for all five Axis 6 scale variants."""

    @pytest.mark.parametrize(
        ("variant_cls", "expected_name"),
        [
            (Scale5Variant, "scale-5"),
            (Scale15Variant, "scale-15"),
            (Scale50Variant, "scale-50"),
            (Scale100Variant, "scale-100"),
            (Scale200Variant, "scale-200"),
        ],
    )
    def test_metadata_name(self, variant_cls: type, expected_name: str) -> None:
        """Each scale variant reports the correct name."""
        meta = variant_cls().metadata()
        assert meta.name == expected_name

    @pytest.mark.parametrize(
        "variant_cls",
        [
            Scale5Variant,
            Scale15Variant,
            Scale50Variant,
            Scale100Variant,
            Scale200Variant,
        ],
    )
    def test_metadata_axis(self, variant_cls: type) -> None:
        """All scale variants belong to axis 6."""
        meta = variant_cls().metadata()
        assert meta.axis == 6

    @pytest.mark.parametrize(
        "variant_cls",
        [
            Scale5Variant,
            Scale15Variant,
            Scale50Variant,
            Scale100Variant,
            Scale200Variant,
        ],
    )
    def test_metadata_category(self, variant_cls: type) -> None:
        """All scale variants have category 'scale'."""
        meta = variant_cls().metadata()
        assert meta.category == "scale"

    @pytest.mark.parametrize(
        "variant_cls",
        [
            Scale5Variant,
            Scale15Variant,
            Scale50Variant,
            Scale100Variant,
            Scale200Variant,
        ],
    )
    def test_metadata_returns_variant_metadata(self, variant_cls: type) -> None:
        """metadata() returns a VariantMetadata instance."""
        meta = variant_cls().metadata()
        assert isinstance(meta, VariantMetadata)


# ---------------------------------------------------------------------------
# Axis 5: Transform variant render tests
# ---------------------------------------------------------------------------


class TestTransformPassthroughRender:
    """Tests for TransformPassthroughVariant.render()."""

    def test_render_contains_all_paths(self, doc_tree: MagicMock) -> None:
        """Passthrough render includes every file path."""
        result = TransformPassthroughVariant().render(doc_tree)
        for path in doc_tree.files:
            assert path in result

    def test_render_contains_raw_content(self, doc_tree: MagicMock) -> None:
        """Passthrough render reproduces raw content verbatim."""
        result = TransformPassthroughVariant().render(doc_tree)
        assert "JWT tokens are used for auth." in result
        assert "```python" in result

    def test_render_uses_section_headings(self, doc_tree: MagicMock) -> None:
        """Each file appears under a ## heading."""
        result = TransformPassthroughVariant().render(doc_tree)
        assert "## api/auth.md" in result
        assert "## guides/setup.md" in result

    def test_render_empty_tree(self, empty_tree: MagicMock) -> None:
        """Passthrough render returns empty string for empty tree."""
        assert TransformPassthroughVariant().render(empty_tree) == ""


class TestTransformAlgorithmicRender:
    """Tests for TransformAlgorithmicVariant.render()."""

    def test_render_contains_paths(self, doc_tree: MagicMock) -> None:
        """Algorithmic render includes file paths."""
        result = TransformAlgorithmicVariant().render(doc_tree)
        assert "api/auth.md" in result
        assert "guides/setup.md" in result

    def test_render_strips_blank_lines(self) -> None:
        """Algorithmic render removes blank lines from within file content."""
        tree = MagicMock()
        doc = MagicMock()
        doc.rel_path = "test.md"
        doc.content = "Line one\n\n\nLine two\n\nLine three"
        doc.tier = "reference"
        doc.section = "Docs"
        tree.files = {"test.md": doc}

        result = TransformAlgorithmicVariant().render(tree)
        # Extract just the content portion (after "## test.md\n\n")
        content_part = result.split("\n\n", 1)[1]
        # Compressed content should have no blank lines
        assert "\n\n" not in content_part
        assert "Line one" in content_part
        assert "Line two" in content_part
        assert "Line three" in content_part

    def test_render_truncates_long_content(self) -> None:
        """Content longer than 20 lines is truncated."""
        tree = MagicMock()
        long_content = "\n".join(f"Line {i}" for i in range(50))
        doc = MagicMock()
        doc.rel_path = "long.md"
        doc.content = long_content
        doc.tier = "reference"
        doc.section = "Docs"
        tree.files = {"long.md": doc}

        result = TransformAlgorithmicVariant().render(tree)
        # Should have at most 20 content lines (some may be blank and stripped)
        # The heading is separate, so count lines in the content portion
        content_part = result.split("\n\n", 1)[1] if "\n\n" in result else result
        content_lines = [ln for ln in content_part.splitlines() if ln.strip()]
        assert len(content_lines) <= 20

    def test_render_empty_tree(self, empty_tree: MagicMock) -> None:
        """Algorithmic render returns empty string for empty tree."""
        assert TransformAlgorithmicVariant().render(empty_tree) == ""


class TestTransformLlmCompressedRender:
    """Tests for TransformLlmCompressedVariant.render()."""

    def test_render_contains_paths(self, doc_tree: MagicMock) -> None:
        """LLM-compressed render includes file paths."""
        result = TransformLlmCompressedVariant().render(doc_tree)
        assert "api/auth.md" in result

    def test_render_extracts_paragraph_leads(self, doc_tree: MagicMock) -> None:
        """LLM-compressed render extracts first line of each paragraph."""
        result = TransformLlmCompressedVariant().render(doc_tree)
        # "# Authentication" is the first line of the first paragraph
        assert "# Authentication" in result
        # "JWT tokens are used for auth." is first line of second paragraph
        assert "JWT tokens are used for auth." in result

    def test_render_omits_subsequent_lines(self) -> None:
        """LLM-compressed render omits non-first-line paragraph content."""
        tree = MagicMock()
        doc = MagicMock()
        doc.rel_path = "test.md"
        doc.content = (
            "First line of paragraph one.\n"
            "Second line of paragraph one.\n"
            "Third line of paragraph one.\n"
            "\n"
            "First line of paragraph two.\n"
            "Second line of paragraph two."
        )
        doc.tier = "reference"
        doc.section = "Docs"
        tree.files = {"test.md": doc}

        result = TransformLlmCompressedVariant().render(tree)
        assert "First line of paragraph one." in result
        assert "First line of paragraph two." in result
        # Second and third lines should NOT appear
        assert "Second line of paragraph one." not in result
        assert "Third line of paragraph one." not in result
        assert "Second line of paragraph two." not in result

    def test_render_empty_tree(self, empty_tree: MagicMock) -> None:
        """LLM-compressed render returns empty string for empty tree."""
        assert TransformLlmCompressedVariant().render(empty_tree) == ""


class TestTransformRestructuredRender:
    """Tests for TransformRestructuredVariant.render()."""

    def test_render_contains_paths(self, doc_tree: MagicMock) -> None:
        """Restructured render includes file paths."""
        result = TransformRestructuredVariant().render(doc_tree)
        assert "api/auth.md" in result

    def test_render_builds_toc(self, doc_tree: MagicMock) -> None:
        """Restructured render builds a Table of Contents."""
        result = TransformRestructuredVariant().render(doc_tree)
        assert "Table of Contents" in result

    def test_render_includes_excerpts_section(self, doc_tree: MagicMock) -> None:
        """Restructured render includes an Excerpts section."""
        result = TransformRestructuredVariant().render(doc_tree)
        assert "Excerpts" in result

    def test_render_indents_subheadings(self, doc_tree: MagicMock) -> None:
        """TOC indents sub-headings with two spaces per level."""
        result = TransformRestructuredVariant().render(doc_tree)
        # api/auth.md has ## Setup, which should be indented with 2 spaces
        assert "  - Setup" in result

    def test_render_handles_no_headings(self) -> None:
        """Files with no headings still produce output."""
        tree = MagicMock()
        doc = MagicMock()
        doc.rel_path = "plain.txt"
        doc.content = "Just plain text with no headings."
        doc.tier = "reference"
        doc.section = "Docs"
        tree.files = {"plain.txt": doc}

        result = TransformRestructuredVariant().render(tree)
        assert "plain.txt" in result
        assert "Just plain text" in result

    def test_render_empty_tree(self, empty_tree: MagicMock) -> None:
        """Restructured render returns empty string for empty tree."""
        assert TransformRestructuredVariant().render(empty_tree) == ""


class TestTransformTaggedRender:
    """Tests for TransformTaggedVariant.render()."""

    def test_render_contains_paths(self, doc_tree: MagicMock) -> None:
        """Tagged render includes file paths."""
        result = TransformTaggedVariant().render(doc_tree)
        assert "api/auth.md" in result

    def test_render_includes_tier_tag(self, doc_tree: MagicMock) -> None:
        """Tagged render includes tier tags."""
        result = TransformTaggedVariant().render(doc_tree)
        assert "tier:required" in result
        assert "tier:recommended" in result
        assert "tier:reference" in result

    def test_render_includes_section_tag(self, doc_tree: MagicMock) -> None:
        """Tagged render includes section tags."""
        result = TransformTaggedVariant().render(doc_tree)
        assert "section:API" in result
        assert "section:Guides" in result

    def test_render_includes_language_tags(self, doc_tree: MagicMock) -> None:
        """Tagged render extracts language tags from code blocks."""
        result = TransformTaggedVariant().render(doc_tree)
        assert "lang:python" in result
        assert "lang:typescript" in result

    def test_render_includes_topic_tags(self, doc_tree: MagicMock) -> None:
        """Tagged render extracts topic tags from headings."""
        result = TransformTaggedVariant().render(doc_tree)
        assert "topic:authentication" in result

    def test_render_bulleted_list(self, doc_tree: MagicMock) -> None:
        """Tagged render produces a bulleted list."""
        result = TransformTaggedVariant().render(doc_tree)
        for line in result.strip().splitlines():
            assert line.startswith("- ")

    def test_render_empty_tree(self, empty_tree: MagicMock) -> None:
        """Tagged render returns empty string for empty tree."""
        assert TransformTaggedVariant().render(empty_tree) == ""


# ---------------------------------------------------------------------------
# Axis 6: Scale variant render tests
# ---------------------------------------------------------------------------


class TestScale5Render:
    """Tests for Scale5Variant.render()."""

    def test_render_limits_to_5_files(self, doc_tree: MagicMock) -> None:
        """Scale-5 renders at most 5 files from a 10-file tree."""
        result = Scale5Variant().render(doc_tree)
        lines = [ln for ln in result.strip().splitlines() if ln.startswith("- ")]
        assert len(lines) == 5

    def test_render_includes_tier(self, doc_tree: MagicMock) -> None:
        """Scale-5 render includes tier labels."""
        result = Scale5Variant().render(doc_tree)
        assert "(required)" in result or "(recommended)" in result or "(reference)" in result

    def test_render_empty_tree(self, empty_tree: MagicMock) -> None:
        """Scale-5 returns empty string for empty tree."""
        assert Scale5Variant().render(empty_tree) == ""

    def test_render_fewer_than_limit(self) -> None:
        """Scale-5 renders all files when tree has fewer than 5."""
        tree = _make_doc_tree(file_count=3)
        result = Scale5Variant().render(tree)
        lines = [ln for ln in result.strip().splitlines() if ln.startswith("- ")]
        assert len(lines) == 3


class TestScale15Render:
    """Tests for Scale15Variant.render()."""

    def test_render_limits_to_15_files(self) -> None:
        """Scale-15 renders at most 15 files from a 20-file tree."""
        tree = _make_large_doc_tree(20)
        result = Scale15Variant().render(tree)
        lines = [ln for ln in result.strip().splitlines() if ln.startswith("- ")]
        assert len(lines) == 15

    def test_render_all_when_fewer(self, doc_tree: MagicMock) -> None:
        """Scale-15 renders all files when tree has fewer than 15."""
        result = Scale15Variant().render(doc_tree)
        lines = [ln for ln in result.strip().splitlines() if ln.startswith("- ")]
        assert len(lines) == 10  # our fixture has 10 files

    def test_render_empty_tree(self, empty_tree: MagicMock) -> None:
        """Scale-15 returns empty string for empty tree."""
        assert Scale15Variant().render(empty_tree) == ""


class TestScale50Render:
    """Tests for Scale50Variant.render()."""

    def test_render_limits_to_50_files(self) -> None:
        """Scale-50 renders at most 50 files from a 75-file tree."""
        tree = _make_large_doc_tree(75)
        result = Scale50Variant().render(tree)
        lines = [ln for ln in result.strip().splitlines() if ln.startswith("- ")]
        assert len(lines) == 50

    def test_render_all_when_fewer(self, doc_tree: MagicMock) -> None:
        """Scale-50 renders all files when tree has fewer than 50."""
        result = Scale50Variant().render(doc_tree)
        lines = [ln for ln in result.strip().splitlines() if ln.startswith("- ")]
        assert len(lines) == 10

    def test_render_empty_tree(self, empty_tree: MagicMock) -> None:
        """Scale-50 returns empty string for empty tree."""
        assert Scale50Variant().render(empty_tree) == ""


class TestScale100Render:
    """Tests for Scale100Variant.render()."""

    def test_render_limits_to_100_files(self) -> None:
        """Scale-100 renders at most 100 files from a 150-file tree."""
        tree = _make_large_doc_tree(150)
        result = Scale100Variant().render(tree)
        lines = [ln for ln in result.strip().splitlines() if ln.startswith("- ")]
        assert len(lines) == 100

    def test_render_all_when_fewer(self) -> None:
        """Scale-100 renders all files when tree has fewer than 100."""
        tree = _make_large_doc_tree(60)
        result = Scale100Variant().render(tree)
        lines = [ln for ln in result.strip().splitlines() if ln.startswith("- ")]
        assert len(lines) == 60

    def test_render_empty_tree(self, empty_tree: MagicMock) -> None:
        """Scale-100 returns empty string for empty tree."""
        assert Scale100Variant().render(empty_tree) == ""


class TestScale200Render:
    """Tests for Scale200Variant.render()."""

    def test_render_limits_to_200_files(self) -> None:
        """Scale-200 renders at most 200 files from a 250-file tree."""
        tree = _make_large_doc_tree(250)
        result = Scale200Variant().render(tree)
        lines = [ln for ln in result.strip().splitlines() if ln.startswith("- ")]
        assert len(lines) == 200

    def test_render_all_when_fewer(self) -> None:
        """Scale-200 renders all files when tree has fewer than 200."""
        tree = _make_large_doc_tree(120)
        result = Scale200Variant().render(tree)
        lines = [ln for ln in result.strip().splitlines() if ln.startswith("- ")]
        assert len(lines) == 120

    def test_render_empty_tree(self, empty_tree: MagicMock) -> None:
        """Scale-200 returns empty string for empty tree."""
        assert Scale200Variant().render(empty_tree) == ""


# ---------------------------------------------------------------------------
# Scale variants -- sorted output
# ---------------------------------------------------------------------------


class TestScaleOutputOrdering:
    """Verify scale variant renders produce path-sorted output."""

    def test_scale_5_output_is_sorted(self, doc_tree: MagicMock) -> None:
        """Scale-5 output lines are sorted by file path."""
        result = Scale5Variant().render(doc_tree)
        lines = [ln for ln in result.splitlines() if ln.startswith("- ")]
        paths = [ln.split(" (")[0].lstrip("- ") for ln in lines]
        assert paths == sorted(paths)

    def test_scale_15_output_is_sorted(self, doc_tree: MagicMock) -> None:
        """Scale-15 output lines are sorted by file path."""
        result = Scale15Variant().render(doc_tree)
        lines = [ln for ln in result.splitlines() if ln.startswith("- ")]
        paths = [ln.split(" (")[0].lstrip("- ") for ln in lines]
        assert paths == sorted(paths)


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


class TestAxisRegistration:
    """Verify all 10 variants register correctly via @register_variant."""

    def test_all_axis_5_variants_register(self) -> None:
        """All five transform variants register on axis 5."""
        register_variant(TransformPassthroughVariant)
        register_variant(TransformAlgorithmicVariant)
        register_variant(TransformLlmCompressedVariant)
        register_variant(TransformRestructuredVariant)
        register_variant(TransformTaggedVariant)

        axis5 = get_variants_for_axis(5)
        assert len(axis5) == 5
        names = {v.metadata().name for v in axis5}
        assert names == {
            "transform-passthrough",
            "transform-algorithmic",
            "transform-llm-compressed",
            "transform-restructured",
            "transform-tagged",
        }

    def test_all_axis_6_variants_register(self) -> None:
        """All five scale variants register on axis 6."""
        register_variant(Scale5Variant)
        register_variant(Scale15Variant)
        register_variant(Scale50Variant)
        register_variant(Scale100Variant)
        register_variant(Scale200Variant)

        axis6 = get_variants_for_axis(6)
        assert len(axis6) == 5
        names = {v.metadata().name for v in axis6}
        assert names == {
            "scale-5",
            "scale-15",
            "scale-50",
            "scale-100",
            "scale-200",
        }

    def test_all_ten_variants_in_get_all(self) -> None:
        """All 10 variants appear in get_all_variants."""
        for cls in [
            TransformPassthroughVariant,
            TransformAlgorithmicVariant,
            TransformLlmCompressedVariant,
            TransformRestructuredVariant,
            TransformTaggedVariant,
            Scale5Variant,
            Scale15Variant,
            Scale50Variant,
            Scale100Variant,
            Scale200Variant,
        ]:
            register_variant(cls)

        all_v = get_all_variants()
        assert len(all_v) == 10

    def test_decorator_registration_is_idempotent(self) -> None:
        """Re-registering the same class does not create duplicates."""
        register_variant(TransformPassthroughVariant)
        register_variant(TransformPassthroughVariant)
        assert len(get_all_variants()) == 1
