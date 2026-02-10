"""Tests for shared variant utility functions in _utils.py.

TDD: These tests are written FIRST, before the implementation.
Each test verifies behavior that matches the inline implementations
previously duplicated across 30+ variant files.
"""

from __future__ import annotations

import random
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# _brief_summary tests
# ---------------------------------------------------------------------------


class TestBriefSummary:
    """Tests for _brief_summary() -- extracts first non-empty line."""

    def test_returns_first_non_empty_line(self) -> None:
        """Should return the first non-empty line (after stripping # prefix)."""
        from agent_evals.variants._utils import brief_summary

        content = "# Heading\n\nFirst real line here."
        # The heading line becomes "Heading" after lstrip("# "), which is non-empty
        assert brief_summary(content) == "Heading"

    def test_strips_leading_hashes(self) -> None:
        """Should strip leading '# ' from lines."""
        from agent_evals.variants._utils import brief_summary

        content = "# My Title"
        assert brief_summary(content) == "My Title"

    def test_strips_whitespace(self) -> None:
        """Should strip leading/trailing whitespace from lines."""
        from agent_evals.variants._utils import brief_summary

        content = "   Some content   "
        assert brief_summary(content) == "Some content"

    def test_truncates_to_max_chars(self) -> None:
        """Should truncate result to max_chars."""
        from agent_evals.variants._utils import brief_summary

        content = "A" * 200
        result = brief_summary(content, max_chars=80)
        assert len(result) == 80

    def test_default_max_chars_is_80(self) -> None:
        """Default max_chars should be 80."""
        from agent_evals.variants._utils import brief_summary

        content = "B" * 200
        result = brief_summary(content)
        assert len(result) == 80

    def test_custom_max_chars(self) -> None:
        """Custom max_chars should be respected."""
        from agent_evals.variants._utils import brief_summary

        content = "C" * 200
        result = brief_summary(content, max_chars=50)
        assert len(result) == 50

    def test_returns_empty_for_empty_content(self) -> None:
        """Should return empty string for empty content."""
        from agent_evals.variants._utils import brief_summary

        assert brief_summary("") == ""

    def test_returns_empty_for_whitespace_only(self) -> None:
        """Should return empty string for whitespace-only content."""
        from agent_evals.variants._utils import brief_summary

        assert brief_summary("   \n  \n  ") == ""

    def test_skips_blank_lines(self) -> None:
        """Should skip blank lines to find first real content."""
        from agent_evals.variants._utils import brief_summary

        content = "\n\n\nActual content here"
        assert brief_summary(content) == "Actual content here"

    def test_handles_multiple_hash_levels(self) -> None:
        """Should strip multiple levels of # headings."""
        from agent_evals.variants._utils import brief_summary

        content = "## Sub Heading"
        # The lstrip("# ") strips all leading '#' and ' '
        assert brief_summary(content) == "Sub Heading"

    def test_short_content_not_truncated(self) -> None:
        """Content shorter than max_chars should not be truncated."""
        from agent_evals.variants._utils import brief_summary

        content = "Short"
        assert brief_summary(content) == "Short"


# ---------------------------------------------------------------------------
# _summarise tests
# ---------------------------------------------------------------------------


class TestSummarise:
    """Tests for _summarise() -- first line or first ~100 chars."""

    def test_returns_first_line(self) -> None:
        """Should return the first line of content."""
        from agent_evals.variants._utils import summarise

        content = "First line\nSecond line\nThird line"
        assert summarise(content) == "First line"

    def test_strips_first_line(self) -> None:
        """Should strip leading/trailing whitespace from first line."""
        from agent_evals.variants._utils import summarise

        content = "  Padded line  \nMore content"
        assert summarise(content) == "Padded line"

    def test_truncates_long_lines(self) -> None:
        """Lines over 100 chars should be truncated to 97 + '...'."""
        from agent_evals.variants._utils import summarise

        content = "X" * 150
        result = summarise(content)
        assert len(result) == 100
        assert result.endswith("...")
        assert result == "X" * 97 + "..."

    def test_exactly_100_chars_not_truncated(self) -> None:
        """A line of exactly 100 chars should not be truncated."""
        from agent_evals.variants._utils import summarise

        content = "Y" * 100
        result = summarise(content)
        assert result == "Y" * 100

    def test_101_chars_is_truncated(self) -> None:
        """A line of 101 chars should be truncated."""
        from agent_evals.variants._utils import summarise

        content = "Z" * 101
        result = summarise(content)
        assert result == "Z" * 97 + "..."

    def test_single_line_content(self) -> None:
        """Single-line content returns that line."""
        from agent_evals.variants._utils import summarise

        content = "Only one line"
        assert summarise(content) == "Only one line"

    def test_empty_content(self) -> None:
        """Empty content returns empty string."""
        from agent_evals.variants._utils import summarise

        assert summarise("") == ""


# ---------------------------------------------------------------------------
# _render_two_tier tests
# ---------------------------------------------------------------------------


def _make_mock_doc(
    rel_path: str,
    section: str,
    tier: str,
    content: str,
    summary: str | None = None,
    token_count: int | None = None,
    priority: int = 0,
) -> MagicMock:
    """Create a mock DocFile for testing."""
    doc = MagicMock()
    doc.rel_path = rel_path
    doc.section = section
    doc.tier = tier
    doc.content = content
    doc.summary = summary
    doc.token_count = token_count
    doc.priority = priority
    return doc


class TestRenderTwoTier:
    """Tests for _render_two_tier() -- two-tier section rendering."""

    def test_starts_with_documentation_index_heading(self) -> None:
        """Output should start with '# Documentation Index'."""
        from agent_evals.variants._utils import render_two_tier

        docs = [_make_mock_doc("api/auth.md", "API", "required", "Auth guide")]
        result = render_two_tier(docs)
        assert result.startswith("# Documentation Index")

    def test_groups_by_section(self) -> None:
        """Files should be grouped under their section headings."""
        from agent_evals.variants._utils import render_two_tier

        docs = [
            _make_mock_doc("api/auth.md", "API", "required", "Auth"),
            _make_mock_doc("guides/setup.md", "Guides", "required", "Setup"),
        ]
        result = render_two_tier(docs)
        assert "## API" in result
        assert "## Guides" in result

    def test_preserves_first_appearance_order(self) -> None:
        """Section order should follow first-appearance order of docs."""
        from agent_evals.variants._utils import render_two_tier

        docs = [
            _make_mock_doc("guides/setup.md", "Guides", "required", "Setup"),
            _make_mock_doc("api/auth.md", "API", "required", "Auth"),
        ]
        result = render_two_tier(docs)
        guides_pos = result.index("## Guides")
        api_pos = result.index("## API")
        assert guides_pos < api_pos

    def test_includes_tier_and_tokens(self) -> None:
        """Each entry should include tier and token count."""
        from agent_evals.variants._utils import render_two_tier

        docs = [
            _make_mock_doc(
                "api/auth.md", "API", "required", "Auth",
                token_count=100,
            ),
        ]
        result = render_two_tier(docs)
        assert "(required, ~100 tokens)" in result

    def test_uses_summary_field_when_available(self) -> None:
        """Should use doc.summary if set, not _summarise(content)."""
        from agent_evals.variants._utils import render_two_tier

        docs = [
            _make_mock_doc(
                "api/auth.md", "API", "required", "Long content here",
                summary="Custom summary",
            ),
        ]
        result = render_two_tier(docs)
        assert "Custom summary" in result
        assert "Long content here" not in result

    def test_falls_back_to_summarise_when_no_summary(self) -> None:
        """Should use _summarise(content) when summary is None."""
        from agent_evals.variants._utils import render_two_tier

        docs = [
            _make_mock_doc(
                "api/auth.md", "API", "required", "First line content",
                summary=None,
            ),
        ]
        result = render_two_tier(docs)
        assert "First line content" in result

    def test_null_token_count_defaults_to_zero(self) -> None:
        """When token_count is None, should display ~0 tokens."""
        from agent_evals.variants._utils import render_two_tier

        docs = [
            _make_mock_doc(
                "api/auth.md", "API", "required", "Auth",
                token_count=None,
            ),
        ]
        result = render_two_tier(docs)
        assert "~0 tokens" in result

    def test_empty_list_returns_just_heading(self) -> None:
        """An empty list should return only the heading."""
        from agent_evals.variants._utils import render_two_tier

        result = render_two_tier([])
        assert result == "# Documentation Index"

    def test_entry_format(self) -> None:
        """Each entry should follow the expected format."""
        from agent_evals.variants._utils import render_two_tier

        docs = [
            _make_mock_doc(
                "api/auth.md", "API", "required", "JWT auth",
                token_count=42,
            ),
        ]
        result = render_two_tier(docs)
        assert "- api/auth.md (required, ~42 tokens) -- JWT auth" in result

    def test_multiple_files_same_section(self) -> None:
        """Multiple files in the same section appear under one heading."""
        from agent_evals.variants._utils import render_two_tier

        docs = [
            _make_mock_doc("api/auth.md", "API", "required", "Auth"),
            _make_mock_doc("api/cache.md", "API", "recommended", "Cache"),
        ]
        result = render_two_tier(docs)
        # Should only have one ## API heading
        assert result.count("## API") == 1
        assert "api/auth.md" in result
        assert "api/cache.md" in result


# ---------------------------------------------------------------------------
# generate_distractors tests
# ---------------------------------------------------------------------------


class TestGenerateDistractors:
    """Tests for generate_distractors() -- fake distractor entries."""

    def test_returns_correct_count(self) -> None:
        """Should generate exactly the requested number of distractors."""
        from agent_evals.variants._utils import generate_distractors

        rng = random.Random(42)
        result = generate_distractors(5, rng)
        assert len(result) == 5

    def test_returns_tuples_of_path_and_summary(self) -> None:
        """Each entry should be a (path, summary) tuple."""
        from agent_evals.variants._utils import generate_distractors

        rng = random.Random(42)
        result = generate_distractors(3, rng)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2
            path, summary = item
            assert isinstance(path, str)
            assert isinstance(summary, str)

    def test_paths_follow_expected_format(self) -> None:
        """Paths should be docs/internal/generated_NNN.md format."""
        from agent_evals.variants._utils import generate_distractors

        rng = random.Random(42)
        result = generate_distractors(3, rng)
        assert result[0][0] == "docs/internal/generated_001.md"
        assert result[1][0] == "docs/internal/generated_002.md"
        assert result[2][0] == "docs/internal/generated_003.md"

    def test_summaries_from_known_list(self) -> None:
        """Summaries should come from the DISTRACTOR_SUMMARIES list."""
        from agent_evals.variants._utils import (
            DISTRACTOR_SUMMARIES,
            generate_distractors,
        )

        rng = random.Random(42)
        result = generate_distractors(10, rng)
        for _path, summary in result:
            assert summary in DISTRACTOR_SUMMARIES

    def test_zero_count_returns_empty(self) -> None:
        """Requesting 0 distractors should return empty list."""
        from agent_evals.variants._utils import generate_distractors

        rng = random.Random(42)
        result = generate_distractors(0, rng)
        assert result == []

    def test_deterministic_with_same_seed(self) -> None:
        """Same seed should produce same distractors."""
        from agent_evals.variants._utils import generate_distractors

        result1 = generate_distractors(5, random.Random(42))
        result2 = generate_distractors(5, random.Random(42))
        assert result1 == result2

    def test_different_seeds_produce_different_results(self) -> None:
        """Different seeds should produce different summaries."""
        from agent_evals.variants._utils import generate_distractors

        result1 = generate_distractors(10, random.Random(42))
        result2 = generate_distractors(10, random.Random(99))
        # Paths are the same (index-based) but summaries differ
        summaries1 = [s for _, s in result1]
        summaries2 = [s for _, s in result2]
        assert summaries1 != summaries2


# ---------------------------------------------------------------------------
# DISTRACTOR_SUMMARIES constant
# ---------------------------------------------------------------------------


class TestDistractorSummaries:
    """Tests for the DISTRACTOR_SUMMARIES constant."""

    def test_is_list_of_strings(self) -> None:
        """Should be a list of strings."""
        from agent_evals.variants._utils import DISTRACTOR_SUMMARIES

        assert isinstance(DISTRACTOR_SUMMARIES, list)
        for item in DISTRACTOR_SUMMARIES:
            assert isinstance(item, str)

    def test_has_ten_entries(self) -> None:
        """Should have exactly 10 entries (matching the original)."""
        from agent_evals.variants._utils import DISTRACTOR_SUMMARIES

        assert len(DISTRACTOR_SUMMARIES) == 10

    def test_contains_known_entries(self) -> None:
        """Should contain key entries from the original list."""
        from agent_evals.variants._utils import DISTRACTOR_SUMMARIES

        assert "Internal reference document" in DISTRACTOR_SUMMARIES
        assert "Legacy migration notes" in DISTRACTOR_SUMMARIES
        assert "Archived design decision log" in DISTRACTOR_SUMMARIES
