"""Tests for Axis 7 (signal-to-noise) and Axis 8 (entry granularity) variants."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from agent_evals.variants.base import VariantMetadata
from agent_evals.variants.granularity_file import GranularityFileVariant
from agent_evals.variants.granularity_function import GranularityFunctionVariant
from agent_evals.variants.granularity_mixed import GranularityMixedVariant
from agent_evals.variants.granularity_section import GranularitySectionVariant
from agent_evals.variants.noise_0 import Noise0Variant
from agent_evals.variants.noise_25 import Noise25Variant
from agent_evals.variants.noise_50 import Noise50Variant
from agent_evals.variants.noise_75 import Noise75Variant
from agent_evals.variants.registry import (
    clear_registry,
    get_all_variants,
    get_variants_for_axis,
    register_variant,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MARKDOWN_CONTENT = """\
# Auth Guide

Introduction paragraph here.

## Installation

Run pip install auth-lib to get started.

## Configuration

Set AUTH_SECRET in your environment variables.

## Usage

Import and call authenticate().
"""

_CODE_CONTENT = """\
\"\"\"Authentication module.\"\"\"

class AuthMiddleware:
    \"\"\"Middleware for JWT authentication.\"\"\"

    def __init__(self, secret: str):
        self.secret = secret

    def authenticate(self, token: str) -> bool:
        return True

def validate_token(token: str) -> dict:
    \"\"\"Validate a JWT token and return claims.\"\"\"
    return {}

def refresh_token(old_token: str) -> str:
    \"\"\"Refresh an expired token.\"\"\"
    return "new_token"

class TokenStore:
    \"\"\"In-memory token storage.\"\"\"

    def __init__(self):
        self.tokens = {}
"""

_SMALL_CONTENT = "Short file with minimal content."

_MEDIUM_CONTENT = """\
# Caching Guide

This guide covers response caching strategies.

## Basic Caching

Use CacheConfig to enable basic response caching for your API endpoints.
Configure TTL and cache key generation.

## Advanced Caching

For more complex scenarios, implement custom cache backends.
""" + "x" * 250  # Pad to ensure > 500 chars

_LARGE_CODE_CONTENT = _CODE_CONTENT + "\n" * 50 + "x" * 1800  # > 2000 chars

_LARGE_MARKDOWN_CONTENT = _MARKDOWN_CONTENT + "\n" * 50 + "x" * 1800  # > 2000 chars, no code


def _make_doc_tree() -> MagicMock:
    """Create a mock DocTree with varied file types for testing."""
    tree = MagicMock()
    files: dict[str, MagicMock] = {}
    for path, section, tier, content in [
        ("api/auth.md", "API", "required", _MARKDOWN_CONTENT),
        ("api/caching.md", "API", "recommended", _SMALL_CONTENT),
        ("src/auth.py", "Source", "required", _CODE_CONTENT),
        ("guides/setup.md", "Guides", "required", "Getting started guide..."),
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


def _make_empty_tree() -> MagicMock:
    """Create an empty mock DocTree."""
    tree = MagicMock()
    tree.files = {}
    return tree


def _make_mixed_size_tree() -> MagicMock:
    """Create a mock DocTree with files of varied sizes for mixed granularity."""
    tree = MagicMock()
    files: dict[str, MagicMock] = {}
    for path, content in [
        ("small.md", _SMALL_CONTENT),
        ("medium.md", _MEDIUM_CONTENT),
        ("large_code.py", _LARGE_CODE_CONTENT),
        ("large_docs.md", _LARGE_MARKDOWN_CONTENT),
    ]:
        doc = MagicMock()
        doc.rel_path = path
        doc.content = content
        doc.size_bytes = len(content)
        doc.token_count = len(content) // 4
        doc.tier = "required"
        doc.section = "Mixed"
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
    """Provide a mock DocTree with varied content."""
    return _make_doc_tree()


@pytest.fixture()
def empty_tree() -> MagicMock:
    """Provide an empty mock DocTree."""
    return _make_empty_tree()


@pytest.fixture()
def mixed_size_tree() -> MagicMock:
    """Provide a mock DocTree with varied file sizes."""
    return _make_mixed_size_tree()


# ---------------------------------------------------------------------------
# Axis 7: Noise variants -- metadata tests
# ---------------------------------------------------------------------------


class TestNoiseMetadata:
    """Verify metadata() for all four Axis 7 noise variants."""

    @pytest.mark.parametrize(
        ("variant_cls", "expected_name"),
        [
            (Noise0Variant, "noise-0"),
            (Noise25Variant, "noise-25"),
            (Noise50Variant, "noise-50"),
            (Noise75Variant, "noise-75"),
        ],
    )
    def test_metadata_name(self, variant_cls: type, expected_name: str) -> None:
        """Each noise variant reports the correct name."""
        meta = variant_cls().metadata()
        assert meta.name == expected_name

    @pytest.mark.parametrize(
        "variant_cls",
        [Noise0Variant, Noise25Variant, Noise50Variant, Noise75Variant],
    )
    def test_metadata_axis(self, variant_cls: type) -> None:
        """All noise variants belong to axis 7."""
        meta = variant_cls().metadata()
        assert meta.axis == 7

    @pytest.mark.parametrize(
        "variant_cls",
        [Noise0Variant, Noise25Variant, Noise50Variant, Noise75Variant],
    )
    def test_metadata_category(self, variant_cls: type) -> None:
        """All noise variants have category 'noise'."""
        meta = variant_cls().metadata()
        assert meta.category == "noise"

    @pytest.mark.parametrize(
        "variant_cls",
        [Noise0Variant, Noise25Variant, Noise50Variant, Noise75Variant],
    )
    def test_metadata_returns_variant_metadata(self, variant_cls: type) -> None:
        """metadata() returns a VariantMetadata instance."""
        meta = variant_cls().metadata()
        assert isinstance(meta, VariantMetadata)


# ---------------------------------------------------------------------------
# Axis 8: Granularity variants -- metadata tests
# ---------------------------------------------------------------------------


class TestGranularityMetadata:
    """Verify metadata() for all four Axis 8 granularity variants."""

    @pytest.mark.parametrize(
        ("variant_cls", "expected_name"),
        [
            (GranularityFileVariant, "granularity-file"),
            (GranularitySectionVariant, "granularity-section"),
            (GranularityFunctionVariant, "granularity-function"),
            (GranularityMixedVariant, "granularity-mixed"),
        ],
    )
    def test_metadata_name(self, variant_cls: type, expected_name: str) -> None:
        """Each granularity variant reports the correct name."""
        meta = variant_cls().metadata()
        assert meta.name == expected_name

    @pytest.mark.parametrize(
        "variant_cls",
        [
            GranularityFileVariant,
            GranularitySectionVariant,
            GranularityFunctionVariant,
            GranularityMixedVariant,
        ],
    )
    def test_metadata_axis(self, variant_cls: type) -> None:
        """All granularity variants belong to axis 8."""
        meta = variant_cls().metadata()
        assert meta.axis == 8

    @pytest.mark.parametrize(
        "variant_cls",
        [
            GranularityFileVariant,
            GranularitySectionVariant,
            GranularityFunctionVariant,
            GranularityMixedVariant,
        ],
    )
    def test_metadata_category(self, variant_cls: type) -> None:
        """All granularity variants have category 'granularity'."""
        meta = variant_cls().metadata()
        assert meta.category == "granularity"

    @pytest.mark.parametrize(
        "variant_cls",
        [
            GranularityFileVariant,
            GranularitySectionVariant,
            GranularityFunctionVariant,
            GranularityMixedVariant,
        ],
    )
    def test_metadata_returns_variant_metadata(self, variant_cls: type) -> None:
        """metadata() returns a VariantMetadata instance."""
        meta = variant_cls().metadata()
        assert isinstance(meta, VariantMetadata)


# ---------------------------------------------------------------------------
# Axis 7: Noise variant render tests
# ---------------------------------------------------------------------------


class TestNoise0Render:
    """Tests for Noise0Variant.render()."""

    def test_render_contains_all_paths(self, doc_tree: MagicMock) -> None:
        """0% noise render includes every real file path."""
        result = Noise0Variant().render(doc_tree)
        assert "api/auth.md" in result
        assert "api/caching.md" in result
        assert "src/auth.py" in result
        assert "guides/setup.md" in result

    def test_render_no_distractors(self, doc_tree: MagicMock) -> None:
        """0% noise render has no distractor entries."""
        result = Noise0Variant().render(doc_tree)
        assert "docs/internal/generated_" not in result

    def test_render_entry_count(self, doc_tree: MagicMock) -> None:
        """0% noise render has exactly as many entries as real files."""
        result = Noise0Variant().render(doc_tree)
        lines = [line for line in result.splitlines() if line.startswith("- ")]
        assert len(lines) == 4

    def test_render_sorted_by_path(self, doc_tree: MagicMock) -> None:
        """0% noise render entries are sorted alphabetically by path."""
        result = Noise0Variant().render(doc_tree)
        lines = [line for line in result.splitlines() if line.startswith("- ")]
        paths = [line.split(":")[0].lstrip("- ") for line in lines]
        assert paths == sorted(paths)

    def test_render_empty_tree(self, empty_tree: MagicMock) -> None:
        """0% noise render returns empty string for empty tree."""
        assert Noise0Variant().render(empty_tree) == ""


class TestNoise25Render:
    """Tests for Noise25Variant.render()."""

    def test_render_contains_all_real_paths(self, doc_tree: MagicMock) -> None:
        """25% noise render still includes every real file path."""
        result = Noise25Variant().render(doc_tree)
        assert "api/auth.md" in result
        assert "api/caching.md" in result
        assert "src/auth.py" in result
        assert "guides/setup.md" in result

    def test_render_has_distractors(self, doc_tree: MagicMock) -> None:
        """25% noise render includes distractor entries."""
        result = Noise25Variant().render(doc_tree)
        assert "docs/internal/generated_" in result

    def test_render_distractor_count(self, doc_tree: MagicMock) -> None:
        """25% noise: 4 real files -> 1 distractor (4//3 = 1, min 1)."""
        result = Noise25Variant().render(doc_tree)
        lines = [line for line in result.splitlines() if line.startswith("- ")]
        real_count = 4
        distractor_count = max(1, real_count // 3)
        assert len(lines) == real_count + distractor_count

    def test_render_sorted_by_path(self, doc_tree: MagicMock) -> None:
        """25% noise render entries are sorted alphabetically."""
        result = Noise25Variant().render(doc_tree)
        lines = [line for line in result.splitlines() if line.startswith("- ")]
        paths = [line.split(":")[0].lstrip("- ") for line in lines]
        assert paths == sorted(paths)

    def test_render_deterministic(self, doc_tree: MagicMock) -> None:
        """25% noise render is deterministic across repeated calls."""
        v = Noise25Variant()
        result1 = v.render(doc_tree)
        result2 = v.render(doc_tree)
        assert result1 == result2

    def test_render_empty_tree(self, empty_tree: MagicMock) -> None:
        """25% noise render returns empty string for empty tree."""
        assert Noise25Variant().render(empty_tree) == ""


class TestNoise50Render:
    """Tests for Noise50Variant.render()."""

    def test_render_contains_all_real_paths(self, doc_tree: MagicMock) -> None:
        """50% noise render still includes every real file path."""
        result = Noise50Variant().render(doc_tree)
        assert "api/auth.md" in result
        assert "api/caching.md" in result
        assert "src/auth.py" in result
        assert "guides/setup.md" in result

    def test_render_distractor_count(self, doc_tree: MagicMock) -> None:
        """50% noise: 4 real files -> 4 distractors."""
        result = Noise50Variant().render(doc_tree)
        lines = [line for line in result.splitlines() if line.startswith("- ")]
        assert len(lines) == 8  # 4 real + 4 distractors

    def test_render_sorted_by_path(self, doc_tree: MagicMock) -> None:
        """50% noise render entries are sorted alphabetically."""
        result = Noise50Variant().render(doc_tree)
        lines = [line for line in result.splitlines() if line.startswith("- ")]
        paths = [line.split(":")[0].lstrip("- ") for line in lines]
        assert paths == sorted(paths)

    def test_render_deterministic(self, doc_tree: MagicMock) -> None:
        """50% noise render is deterministic across repeated calls."""
        v = Noise50Variant()
        result1 = v.render(doc_tree)
        result2 = v.render(doc_tree)
        assert result1 == result2

    def test_render_empty_tree(self, empty_tree: MagicMock) -> None:
        """50% noise render returns empty string for empty tree."""
        assert Noise50Variant().render(empty_tree) == ""


class TestNoise75Render:
    """Tests for Noise75Variant.render()."""

    def test_render_contains_all_real_paths(self, doc_tree: MagicMock) -> None:
        """75% noise render still includes every real file path."""
        result = Noise75Variant().render(doc_tree)
        assert "api/auth.md" in result
        assert "api/caching.md" in result
        assert "src/auth.py" in result
        assert "guides/setup.md" in result

    def test_render_distractor_count(self, doc_tree: MagicMock) -> None:
        """75% noise: 4 real files -> 12 distractors."""
        result = Noise75Variant().render(doc_tree)
        lines = [line for line in result.splitlines() if line.startswith("- ")]
        assert len(lines) == 16  # 4 real + 12 distractors

    def test_render_heavily_diluted(self, doc_tree: MagicMock) -> None:
        """75% noise: distractor entries outnumber real entries 3:1."""
        result = Noise75Variant().render(doc_tree)
        lines = [line for line in result.splitlines() if line.startswith("- ")]
        distractor_lines = [x for x in lines if "docs/internal/generated_" in x]
        real_lines = [x for x in lines if "docs/internal/generated_" not in x]
        assert len(distractor_lines) == len(real_lines) * 3

    def test_render_sorted_by_path(self, doc_tree: MagicMock) -> None:
        """75% noise render entries are sorted alphabetically."""
        result = Noise75Variant().render(doc_tree)
        lines = [line for line in result.splitlines() if line.startswith("- ")]
        paths = [line.split(":")[0].lstrip("- ") for line in lines]
        assert paths == sorted(paths)

    def test_render_deterministic(self, doc_tree: MagicMock) -> None:
        """75% noise render is deterministic across repeated calls."""
        v = Noise75Variant()
        result1 = v.render(doc_tree)
        result2 = v.render(doc_tree)
        assert result1 == result2

    def test_render_empty_tree(self, empty_tree: MagicMock) -> None:
        """75% noise render returns empty string for empty tree."""
        assert Noise75Variant().render(empty_tree) == ""


class TestNoiseScaling:
    """Cross-variant tests verifying noise levels scale correctly."""

    def test_noise_levels_increase_monotonically(self, doc_tree: MagicMock) -> None:
        """Higher noise levels produce more total entries."""
        counts = {}
        for variant_cls in [Noise0Variant, Noise25Variant, Noise50Variant, Noise75Variant]:
            result = variant_cls().render(doc_tree)
            lines = [line for line in result.splitlines() if line.startswith("- ")]
            counts[variant_cls] = len(lines)

        assert counts[Noise0Variant] < counts[Noise25Variant]
        assert counts[Noise25Variant] < counts[Noise50Variant]
        assert counts[Noise50Variant] < counts[Noise75Variant]

    def test_all_noise_variants_preserve_real_files(self, doc_tree: MagicMock) -> None:
        """Every noise level preserves all real file entries."""
        real_paths = {"api/auth.md", "api/caching.md", "src/auth.py", "guides/setup.md"}
        for variant_cls in [Noise0Variant, Noise25Variant, Noise50Variant, Noise75Variant]:
            result = variant_cls().render(doc_tree)
            for path in real_paths:
                assert path in result, f"{variant_cls.__name__} missing {path}"


# ---------------------------------------------------------------------------
# Axis 8: Granularity variant render tests
# ---------------------------------------------------------------------------


class TestGranularityFileRender:
    """Tests for GranularityFileVariant.render()."""

    def test_render_contains_all_paths(self, doc_tree: MagicMock) -> None:
        """File-level render includes every file path."""
        result = GranularityFileVariant().render(doc_tree)
        assert "api/auth.md" in result
        assert "api/caching.md" in result
        assert "src/auth.py" in result
        assert "guides/setup.md" in result

    def test_render_entry_count(self, doc_tree: MagicMock) -> None:
        """File-level render has exactly one entry per file."""
        result = GranularityFileVariant().render(doc_tree)
        lines = [line for line in result.splitlines() if line.startswith("- ")]
        assert len(lines) == 4

    def test_render_sorted_by_path(self, doc_tree: MagicMock) -> None:
        """File-level render entries are sorted alphabetically."""
        result = GranularityFileVariant().render(doc_tree)
        lines = [line for line in result.splitlines() if line.startswith("- ")]
        paths = [line.split(":")[0].lstrip("- ") for line in lines]
        assert paths == sorted(paths)

    def test_render_empty_tree(self, empty_tree: MagicMock) -> None:
        """File-level render returns empty string for empty tree."""
        assert GranularityFileVariant().render(empty_tree) == ""


class TestGranularitySectionRender:
    """Tests for GranularitySectionVariant.render()."""

    def test_render_splits_on_headings(self, doc_tree: MagicMock) -> None:
        """Section render splits files with ## headings into sections."""
        result = GranularitySectionVariant().render(doc_tree)
        # api/auth.md has ## Installation, ## Configuration, ## Usage
        assert "api/auth.md#Installation" in result
        assert "api/auth.md#Configuration" in result
        assert "api/auth.md#Usage" in result

    def test_render_no_heading_fallback(self, doc_tree: MagicMock) -> None:
        """Files without ## headings fall back to file-level entry."""
        result = GranularitySectionVariant().render(doc_tree)
        # api/caching.md has content "Short file..." -- no ## headings
        assert "- api/caching.md:" in result
        assert "#" not in [
            line for line in result.splitlines()
            if line.startswith("- api/caching.md")
        ][0].split("- api/caching.md")[1].split(":")[0]

    def test_render_more_entries_than_files(self, doc_tree: MagicMock) -> None:
        """Section render produces more entries than file-level for files with sections."""
        result = GranularitySectionVariant().render(doc_tree)
        lines = [line for line in result.splitlines() if line.startswith("- ")]
        # 4 files but api/auth.md has 3 sections, so > 4 entries
        assert len(lines) > 4

    def test_render_section_has_summary(self, doc_tree: MagicMock) -> None:
        """Section entries include a summary from the section content."""
        result = GranularitySectionVariant().render(doc_tree)
        # ## Installation section's first line is "Run pip install..."
        install_line = [
            line for line in result.splitlines()
            if "api/auth.md#Installation" in line
        ]
        assert len(install_line) == 1
        assert "pip install" in install_line[0]

    def test_render_empty_tree(self, empty_tree: MagicMock) -> None:
        """Section render returns empty string for empty tree."""
        assert GranularitySectionVariant().render(empty_tree) == ""


class TestGranularityFunctionRender:
    """Tests for GranularityFunctionVariant.render()."""

    def test_render_finds_class_definitions(self, doc_tree: MagicMock) -> None:
        """Function render finds class definitions."""
        result = GranularityFunctionVariant().render(doc_tree)
        assert "src/auth.py::AuthMiddleware (class)" in result
        assert "src/auth.py::TokenStore (class)" in result

    def test_render_finds_function_definitions(self, doc_tree: MagicMock) -> None:
        """Function render finds function definitions."""
        result = GranularityFunctionVariant().render(doc_tree)
        assert "src/auth.py::validate_token (function)" in result
        assert "src/auth.py::refresh_token (function)" in result

    def test_render_finds_methods(self, doc_tree: MagicMock) -> None:
        """Function render finds method definitions inside classes."""
        result = GranularityFunctionVariant().render(doc_tree)
        assert "src/auth.py::__init__ (function)" in result
        assert "src/auth.py::authenticate (function)" in result

    def test_render_no_definitions_fallback(self, doc_tree: MagicMock) -> None:
        """Files without def/class fall back to file-level entry."""
        result = GranularityFunctionVariant().render(doc_tree)
        # guides/setup.md has no code definitions
        setup_lines = [
            line for line in result.splitlines()
            if "guides/setup.md" in line
        ]
        assert len(setup_lines) == 1
        assert "::" not in setup_lines[0]

    def test_render_more_entries_for_code_files(self, doc_tree: MagicMock) -> None:
        """Function render produces multiple entries for code files."""
        result = GranularityFunctionVariant().render(doc_tree)
        auth_lines = [
            line for line in result.splitlines()
            if "src/auth.py::" in line
        ]
        # Should find multiple definitions in auth.py
        assert len(auth_lines) >= 4

    def test_render_empty_tree(self, empty_tree: MagicMock) -> None:
        """Function render returns empty string for empty tree."""
        assert GranularityFunctionVariant().render(empty_tree) == ""


class TestGranularityMixedRender:
    """Tests for GranularityMixedVariant.render()."""

    def test_small_file_gets_file_level(self, mixed_size_tree: MagicMock) -> None:
        """Small files (< 500 chars) get file-level entry."""
        result = GranularityMixedVariant().render(mixed_size_tree)
        small_lines = [
            line for line in result.splitlines()
            if "small.md" in line
        ]
        assert len(small_lines) == 1
        assert "#" not in small_lines[0].split("small.md")[1].split(":")[0]
        assert "::" not in small_lines[0]

    def test_medium_file_gets_section_level(self, mixed_size_tree: MagicMock) -> None:
        """Medium files (500-2000 chars) get section-level entries."""
        result = GranularityMixedVariant().render(mixed_size_tree)
        medium_lines = [
            line for line in result.splitlines()
            if "medium.md" in line
        ]
        # medium.md has ## Basic Caching and ## Advanced Caching
        assert len(medium_lines) >= 2
        assert any("#" in line.split("medium.md")[1].split(":")[0] for line in medium_lines)

    def test_large_code_gets_function_level(self, mixed_size_tree: MagicMock) -> None:
        """Large code files (> 2000 chars) with defs get function-level entries."""
        result = GranularityMixedVariant().render(mixed_size_tree)
        code_lines = [
            line for line in result.splitlines()
            if "large_code.py" in line
        ]
        assert len(code_lines) >= 2
        assert any("::" in line for line in code_lines)

    def test_large_markdown_gets_section_level(self, mixed_size_tree: MagicMock) -> None:
        """Large non-code files (> 2000 chars) without defs get section-level entries."""
        result = GranularityMixedVariant().render(mixed_size_tree)
        docs_lines = [
            line for line in result.splitlines()
            if "large_docs.md" in line
        ]
        assert len(docs_lines) >= 2
        assert any("#" in line.split("large_docs.md")[1].split(":")[0] for line in docs_lines)

    def test_render_empty_tree(self, empty_tree: MagicMock) -> None:
        """Mixed render returns empty string for empty tree."""
        assert GranularityMixedVariant().render(empty_tree) == ""


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------


class TestAxisRegistration:
    """Verify all 8 variants register correctly via @register_variant."""

    def test_all_axis_7_variants_register(self) -> None:
        """All four noise variants register on axis 7."""
        register_variant(Noise0Variant)
        register_variant(Noise25Variant)
        register_variant(Noise50Variant)
        register_variant(Noise75Variant)

        axis7 = get_variants_for_axis(7)
        assert len(axis7) == 4
        names = {v.metadata().name for v in axis7}
        assert names == {"noise-0", "noise-25", "noise-50", "noise-75"}

    def test_all_axis_8_variants_register(self) -> None:
        """All four granularity variants register on axis 8."""
        register_variant(GranularityFileVariant)
        register_variant(GranularitySectionVariant)
        register_variant(GranularityFunctionVariant)
        register_variant(GranularityMixedVariant)

        axis8 = get_variants_for_axis(8)
        assert len(axis8) == 4
        names = {v.metadata().name for v in axis8}
        assert names == {
            "granularity-file",
            "granularity-section",
            "granularity-function",
            "granularity-mixed",
        }

    def test_all_eight_variants_in_get_all(self) -> None:
        """All 8 variants appear in get_all_variants."""
        for cls in [
            Noise0Variant,
            Noise25Variant,
            Noise50Variant,
            Noise75Variant,
            GranularityFileVariant,
            GranularitySectionVariant,
            GranularityFunctionVariant,
            GranularityMixedVariant,
        ]:
            register_variant(cls)

        all_v = get_all_variants()
        assert len(all_v) == 8

    def test_decorator_registration_is_idempotent(self) -> None:
        """Re-registering the same class does not create duplicates."""
        register_variant(Noise0Variant)
        register_variant(Noise0Variant)
        assert len(get_all_variants()) == 1
