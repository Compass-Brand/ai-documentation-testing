"""Tests for cross-tool output format renderers."""

from __future__ import annotations

import pytest
from agent_index.models import DocFile, TierConfig
from agent_index.output import (
    render_claude_md,
    render_copilot_instructions,
    render_cursor_rules,
    render_for_target,
    render_index,
)


def make_docfile(
    rel_path: str,
    tier: str = "",
    section: str = "",
    priority: int = 0,
) -> DocFile:
    """Create a DocFile with minimal required fields for testing."""
    return DocFile(
        rel_path=rel_path,
        content="# Test content",
        size_bytes=100,
        tier=tier,
        section=section,
        priority=priority,
    )


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

DEFAULT_TIERS = [
    TierConfig(name="required", instruction="Read at session start"),
    TierConfig(name="recommended", instruction="Read when relevant"),
    TierConfig(name="reference", instruction="Consult as needed"),
]


SAMPLE_FILES = [
    make_docfile("README.md", tier="required", section=""),
    make_docfile("docs/architecture.md", tier="required", section=""),
    make_docfile("docs/api/auth.md", tier="recommended", section="api"),
    make_docfile("docs/api/routes.md", tier="recommended", section="api"),
    make_docfile("docs/deploy/docker.md", tier="reference", section="deploy"),
]


# ===========================================================================
# Story 8.2: CLAUDE.md output
# ===========================================================================


class TestRenderClaudeMd:
    """Tests for render_claude_md function."""

    def test_produces_claude_specific_format(self) -> None:
        """render_claude_md output starts with project context header."""
        result = render_claude_md(SAMPLE_FILES, DEFAULT_TIERS)

        assert result.startswith("# Project Documentation\n")
        assert "## Required" in result
        assert "## Recommended" in result
        assert "## Reference" in result

    def test_contains_claude_language(self) -> None:
        """render_claude_md uses Claude-appropriate verb phrasing."""
        result = render_claude_md(SAMPLE_FILES, DEFAULT_TIERS)

        assert "Read these files at the start of every task." in result
        assert "Read these files when working on related areas." in result
        assert "Consult these files when you need specific details." in result

    def test_files_listed_as_code_spans(self) -> None:
        """render_claude_md lists file paths as markdown code spans."""
        result = render_claude_md(SAMPLE_FILES, DEFAULT_TIERS)

        assert "- `README.md`" in result
        assert "- `docs/api/auth.md`" in result

    def test_contains_instruction(self) -> None:
        """render_claude_md places instruction near the top."""
        custom = "Always check docs first."
        result = render_claude_md(SAMPLE_FILES, DEFAULT_TIERS, custom)

        assert "Always check docs first." in result

    def test_empty_files(self) -> None:
        """render_claude_md handles empty file list gracefully."""
        result = render_claude_md([], DEFAULT_TIERS)

        assert "# Project Documentation" in result
        # No tier headers when there are no files
        assert "## Required" not in result

    def test_multiple_tiers(self) -> None:
        """render_claude_md renders multiple tiers in config order."""
        result = render_claude_md(SAMPLE_FILES, DEFAULT_TIERS)

        req_pos = result.find("## Required")
        rec_pos = result.find("## Recommended")
        ref_pos = result.find("## Reference")

        assert req_pos < rec_pos < ref_pos

    def test_custom_tier_falls_back_to_instruction(self) -> None:
        """Unknown tier names use the tier_config.instruction as the verb."""
        files = [make_docfile("guide.md", tier="bonus")]
        tiers = [TierConfig(name="bonus", instruction="Skim these for extra context")]

        result = render_claude_md(files, tiers)

        assert "Skim these for extra context" in result


# ===========================================================================
# Story 8.3: Cursor Rules output
# ===========================================================================


class TestRenderCursorRules:
    """Tests for render_cursor_rules function."""

    def test_returns_dict_with_mdc_filenames(self) -> None:
        """render_cursor_rules returns dict keyed by .mdc filenames."""
        result = render_cursor_rules(SAMPLE_FILES, DEFAULT_TIERS)

        assert isinstance(result, dict)
        assert "required-docs.mdc" in result
        assert "recommended-docs.mdc" in result
        assert "reference-docs.mdc" in result

    def test_yaml_frontmatter_has_description(self) -> None:
        """Each .mdc file has YAML frontmatter with description field."""
        result = render_cursor_rules(SAMPLE_FILES, DEFAULT_TIERS)

        for filename, content in result.items():
            assert content.startswith("---\n"), f"{filename} missing frontmatter"
            assert "description:" in content, f"{filename} missing description"

    def test_yaml_frontmatter_has_globs(self) -> None:
        """Each .mdc file has YAML frontmatter with globs field."""
        result = render_cursor_rules(SAMPLE_FILES, DEFAULT_TIERS)

        for filename, content in result.items():
            assert "globs:" in content, f"{filename} missing globs"

    def test_one_file_per_non_empty_tier(self) -> None:
        """render_cursor_rules produces exactly one .mdc per non-empty tier."""
        # Only required and recommended have files
        files = [
            make_docfile("a.md", tier="required"),
            make_docfile("b.md", tier="recommended"),
        ]
        result = render_cursor_rules(files, DEFAULT_TIERS)

        assert len(result) == 2
        assert "required-docs.mdc" in result
        assert "recommended-docs.mdc" in result
        assert "reference-docs.mdc" not in result

    def test_empty_files(self) -> None:
        """render_cursor_rules returns empty dict for empty file list."""
        result = render_cursor_rules([], DEFAULT_TIERS)

        assert result == {}

    def test_content_lists_tier_files(self) -> None:
        """Each .mdc body lists the files belonging to that tier."""
        result = render_cursor_rules(SAMPLE_FILES, DEFAULT_TIERS)

        required_content = result["required-docs.mdc"]
        assert "README.md" in required_content
        assert "docs/architecture.md" in required_content
        # Should not contain files from other tiers
        assert "docs/api/auth.md" not in required_content

    def test_frontmatter_description_matches_instruction(self) -> None:
        """Frontmatter description uses the tier's instruction text."""
        result = render_cursor_rules(SAMPLE_FILES, DEFAULT_TIERS)

        required_content = result["required-docs.mdc"]
        assert "description: Read at session start" in required_content

    def test_multiple_tiers(self) -> None:
        """render_cursor_rules handles all three default tiers."""
        result = render_cursor_rules(SAMPLE_FILES, DEFAULT_TIERS)

        assert len(result) == 3
        for filename in result:
            assert filename.endswith(".mdc")


# ===========================================================================
# Story 8.4: Copilot Instructions output
# ===========================================================================


class TestRenderCopilotInstructions:
    """Tests for render_copilot_instructions function."""

    def test_contains_instruction_and_tiers(self) -> None:
        """render_copilot_instructions has instruction and tier sections."""
        result = render_copilot_instructions(SAMPLE_FILES, DEFAULT_TIERS)

        assert "# Copilot Instructions" in result
        assert "## Required" in result
        assert "## Recommended" in result
        assert "## Reference" in result

    def test_instruction_near_top(self) -> None:
        """render_copilot_instructions places instruction below the title."""
        custom = "Follow the docs closely."
        result = render_copilot_instructions(SAMPLE_FILES, DEFAULT_TIERS, custom)

        # Instruction should appear before any tier header
        instr_pos = result.find("Follow the docs closely.")
        req_pos = result.find("## Required")
        assert instr_pos < req_pos

    def test_tier_instruction_in_italics(self) -> None:
        """Each tier shows its instruction in italics."""
        result = render_copilot_instructions(SAMPLE_FILES, DEFAULT_TIERS)

        assert "_Read at session start_" in result
        assert "_Read when relevant_" in result
        assert "_Consult as needed_" in result

    def test_files_listed_per_tier(self) -> None:
        """Each tier lists its files."""
        result = render_copilot_instructions(SAMPLE_FILES, DEFAULT_TIERS)

        assert "- README.md" in result
        assert "- docs/api/auth.md" in result
        assert "- docs/deploy/docker.md" in result

    def test_empty_files(self) -> None:
        """render_copilot_instructions handles empty file list gracefully."""
        result = render_copilot_instructions([], DEFAULT_TIERS)

        assert "# Copilot Instructions" in result
        assert "## Required" not in result

    def test_multiple_tiers_in_order(self) -> None:
        """render_copilot_instructions renders tiers in config order."""
        result = render_copilot_instructions(SAMPLE_FILES, DEFAULT_TIERS)

        req_pos = result.find("## Required")
        rec_pos = result.find("## Recommended")
        ref_pos = result.find("## Reference")

        assert req_pos < rec_pos < ref_pos


# ===========================================================================
# Story 8.5: Dispatch function
# ===========================================================================


class TestRenderForTarget:
    """Tests for render_for_target dispatch function."""

    def test_dispatches_agents_md(self) -> None:
        """render_for_target('agents.md') dispatches to render_index."""
        result = render_for_target("agents.md", SAMPLE_FILES, DEFAULT_TIERS)

        assert isinstance(result, str)
        assert "IMPORTANT:" in result
        assert "## Required [Read at session start]" in result

    def test_dispatches_claude_md(self) -> None:
        """render_for_target('claude.md') dispatches to render_claude_md."""
        result = render_for_target("claude.md", SAMPLE_FILES, DEFAULT_TIERS)

        assert isinstance(result, str)
        assert "# Project Documentation" in result

    def test_dispatches_cursor_rules(self) -> None:
        """render_for_target('cursor-rules') dispatches to render_cursor_rules."""
        result = render_for_target("cursor-rules", SAMPLE_FILES, DEFAULT_TIERS)

        assert isinstance(result, dict)
        assert "required-docs.mdc" in result

    def test_dispatches_copilot_instructions(self) -> None:
        """render_for_target('copilot-instructions') dispatches to render_copilot_instructions."""
        result = render_for_target(
            "copilot-instructions", SAMPLE_FILES, DEFAULT_TIERS
        )

        assert isinstance(result, str)
        assert "# Copilot Instructions" in result

    def test_unknown_target_raises_value_error(self) -> None:
        """render_for_target raises ValueError for unknown target."""
        with pytest.raises(ValueError, match="Unknown output target"):
            render_for_target("unknown-target", SAMPLE_FILES, DEFAULT_TIERS)

    def test_passes_instruction_through(self) -> None:
        """render_for_target passes custom instruction to renderer."""
        custom = "My custom instruction"

        result = render_for_target(
            "claude.md", SAMPLE_FILES, DEFAULT_TIERS, custom
        )
        assert isinstance(result, str)
        assert custom in result

        result2 = render_for_target(
            "copilot-instructions", SAMPLE_FILES, DEFAULT_TIERS, custom
        )
        assert isinstance(result2, str)
        assert custom in result2


# ===========================================================================
# Regression: render_index still works as before
# ===========================================================================


class TestRenderIndexRegression:
    """Regression tests to ensure render_index is not broken by refactoring."""

    def test_still_has_instruction_bookends(self) -> None:
        """render_index still places IMPORTANT instruction at top and bottom."""
        result = render_index(SAMPLE_FILES, DEFAULT_TIERS)

        lines = result.strip().split("\n")
        assert lines[0].startswith("IMPORTANT:")
        assert lines[-1].startswith("IMPORTANT:")

    def test_still_renders_tiers_with_brackets(self) -> None:
        """render_index still renders tier headers with [instruction] brackets."""
        result = render_index(SAMPLE_FILES, DEFAULT_TIERS)

        assert "## Required [Read at session start]" in result
        assert "## Recommended [Read when relevant]" in result
        assert "## Reference [Consult as needed]" in result

    def test_still_renders_section_headers(self) -> None:
        """render_index still renders section headers within tiers."""
        result = render_index(SAMPLE_FILES, DEFAULT_TIERS)

        assert "### Api" in result
        assert "### Deploy" in result

    def test_empty_files_still_works(self) -> None:
        """render_index with empty files still returns instruction bookends."""
        result = render_index([], DEFAULT_TIERS)

        assert result.count("IMPORTANT:") == 2

    def test_full_bluf_order_preserved(self) -> None:
        """render_index still maintains BLUF tier ordering."""
        result = render_index(SAMPLE_FILES, DEFAULT_TIERS)

        req_pos = result.find("## Required")
        rec_pos = result.find("## Recommended")
        ref_pos = result.find("## Reference")

        assert req_pos < rec_pos < ref_pos
