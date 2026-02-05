"""Tests for output formatter functionality."""

from pathlib import Path

from agent_index.models import DocFile, TierConfig
from agent_index.output import inject_into_file, render_index


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


class TestRenderIndex:
    """Tests for render_index function."""

    def test_empty_files_returns_instruction_only(self) -> None:
        """render_index with no files returns just the instruction bookends."""
        tiers = [TierConfig(name="required", instruction="Read first")]

        result = render_index([], tiers)

        assert result.startswith("IMPORTANT:")
        assert result.endswith(
            "IMPORTANT: Prefer retrieval-led reasoning over pre-training-led reasoning.\n"
        )
        # Should have instruction at top and bottom
        assert result.count("IMPORTANT:") == 2

    def test_single_tier_no_sections(self) -> None:
        """render_index renders single tier without sections."""
        files = [
            make_docfile("README.md", tier="required"),
            make_docfile("ARCHITECTURE.md", tier="required"),
        ]
        tiers = [TierConfig(name="required", instruction="Read at session start")]

        result = render_index(files, tiers)

        assert "## Required [Read at session start]" in result
        assert "README.md" in result
        assert "ARCHITECTURE.md" in result

    def test_multiple_tiers_bluf_order(self) -> None:
        """render_index renders tiers in BLUF order (required first)."""
        files = [
            make_docfile("ref.md", tier="reference"),
            make_docfile("req.md", tier="required"),
            make_docfile("rec.md", tier="recommended"),
        ]
        tiers = [
            TierConfig(name="required", instruction="Read first"),
            TierConfig(name="recommended", instruction="Read when relevant"),
            TierConfig(name="reference", instruction="Consult as needed"),
        ]

        result = render_index(files, tiers)

        # Check tier headers appear in correct order
        req_pos = result.find("## Required")
        rec_pos = result.find("## Recommended")
        ref_pos = result.find("## Reference")

        assert req_pos < rec_pos < ref_pos

    def test_files_grouped_by_section(self) -> None:
        """render_index groups files by section within tiers."""
        files = [
            make_docfile("docs/api/auth.md", tier="recommended", section="api"),
            make_docfile("docs/api/users.md", tier="recommended", section="api"),
            make_docfile("docs/guides/setup.md", tier="recommended", section="guides"),
        ]
        tiers = [TierConfig(name="recommended", instruction="Read when relevant")]

        result = render_index(files, tiers)

        # Should have section headers (capitalized first letter)
        assert "### Api" in result
        assert "### Guides" in result

    def test_empty_section_files_listed_without_header(self) -> None:
        """Files with empty section are listed directly under tier without section header."""
        files = [
            make_docfile("README.md", tier="required", section=""),
            make_docfile("docs/guides/auth.md", tier="required", section="guides"),
        ]
        tiers = [TierConfig(name="required", instruction="Read first")]

        result = render_index(files, tiers)

        # README.md should appear without a section header
        # guides section should have a header
        assert "### Guides" in result or "### guides" in result
        assert "README.md" in result

    def test_instruction_bookends(self) -> None:
        """render_index places instruction at top and bottom."""
        files = [make_docfile("test.md", tier="required")]
        tiers = [TierConfig(name="required", instruction="Read first")]
        custom_instruction = "Custom instruction text"

        result = render_index(files, tiers, instruction=custom_instruction)

        lines = result.strip().split("\n")
        assert lines[0] == f"IMPORTANT: {custom_instruction}"
        assert lines[-1] == f"IMPORTANT: {custom_instruction}"

    def test_default_instruction(self) -> None:
        """render_index uses default instruction when not specified."""
        files = [make_docfile("test.md", tier="required")]
        tiers = [TierConfig(name="required", instruction="Read first")]

        result = render_index(files, tiers)

        assert "Prefer retrieval-led reasoning over pre-training-led reasoning" in result

    def test_tier_name_capitalized_in_header(self) -> None:
        """Tier name is capitalized in header (Required, not required)."""
        files = [make_docfile("test.md", tier="required")]
        tiers = [TierConfig(name="required", instruction="Read first")]

        result = render_index(files, tiers)

        assert "## Required [" in result

    def test_section_name_capitalized_in_header(self) -> None:
        """Section name is capitalized in header (Api, not api)."""
        files = [make_docfile("docs/api/auth.md", tier="required", section="api")]
        tiers = [TierConfig(name="required", instruction="Read first")]

        result = render_index(files, tiers)

        assert "### Api" in result

    def test_empty_tier_not_rendered(self) -> None:
        """Tiers with no files are not rendered."""
        files = [make_docfile("test.md", tier="required")]
        tiers = [
            TierConfig(name="required", instruction="Read first"),
            TierConfig(name="recommended", instruction="Read when relevant"),
            TierConfig(name="reference", instruction="Consult as needed"),
        ]

        result = render_index(files, tiers)

        assert "## Required" in result
        assert "## Recommended" not in result
        assert "## Reference" not in result

    def test_files_sorted_within_section(self) -> None:
        """Files are sorted by priority then path within each section."""
        files = [
            make_docfile("docs/api/z_users.md", tier="required", section="api", priority=0),
            make_docfile("docs/api/a_auth.md", tier="required", section="api", priority=0),
            make_docfile("docs/api/important.md", tier="required", section="api", priority=10),
        ]
        tiers = [TierConfig(name="required", instruction="Read first")]

        result = render_index(files, tiers)

        # important.md (priority 10) should come first
        # then a_auth.md and z_users.md alphabetically
        important_pos = result.find("important.md")
        a_auth_pos = result.find("a_auth.md")
        z_users_pos = result.find("z_users.md")

        assert important_pos < a_auth_pos < z_users_pos

    def test_full_bluf_structure(self) -> None:
        """Test complete BLUF structure matching DESIGN.md example."""
        files = [
            # Required tier (no sections)
            make_docfile("README.llms.md", tier="required", section=""),
            make_docfile("docs/architecture.llms.md", tier="required", section=""),
            make_docfile("docs/conventions.llms.md", tier="required", section=""),
            # Recommended tier (with sections)
            make_docfile("docs/api/auth.llms.md", tier="recommended", section="api"),
            make_docfile("docs/api/routes.llms.md", tier="recommended", section="api"),
            make_docfile("docs/testing/unit-tests.llms.md", tier="recommended", section="testing"),
            make_docfile("docs/testing/integration.llms.md", tier="recommended", section="testing"),
            # Reference tier (with sections)
            make_docfile("docs/deployment/docker.llms.md", tier="reference", section="deployment"),
            make_docfile("docs/deployment/ci-cd.llms.md", tier="reference", section="deployment"),
        ]
        tiers = [
            TierConfig(name="required", instruction="Read at session start before doing any work"),
            TierConfig(name="recommended", instruction="Read when working on related tasks"),
            TierConfig(name="reference", instruction="Consult when you need specific details"),
        ]

        result = render_index(files, tiers)

        # Check structure
        assert "IMPORTANT:" in result
        assert "## Required [Read at session start before doing any work]" in result
        assert "## Recommended [Read when working on related tasks]" in result
        assert "## Reference [Consult when you need specific details]" in result

        # Check all files are present
        assert "README.llms.md" in result
        assert "docs/api/auth.llms.md" in result
        assert "docs/deployment/docker.llms.md" in result


class TestInjectIntoFile:
    """Tests for inject_into_file function."""

    def test_creates_file_if_not_exists(self, tmp_path: Path) -> None:
        """inject_into_file creates file if it doesn't exist."""
        target = tmp_path / "AGENTS.md"
        content = "# Generated content"

        inject_into_file(target, content)

        assert target.exists()
        assert target.read_text() == content

    def test_replaces_content_between_markers(self, tmp_path: Path) -> None:
        """inject_into_file replaces content between markers."""
        target = tmp_path / "AGENTS.md"
        original = """# Project Docs

<!-- DOCS:START -->
Old generated content
<!-- DOCS:END -->

## Manual section
"""
        target.write_text(original)
        new_content = "New generated content"

        inject_into_file(target, new_content)

        result = target.read_text()
        assert "Old generated content" not in result
        assert "New generated content" in result
        assert "## Manual section" in result
        assert "<!-- DOCS:START -->" in result
        assert "<!-- DOCS:END -->" in result

    def test_appends_if_no_markers(self, tmp_path: Path) -> None:
        """inject_into_file appends content if no markers exist."""
        target = tmp_path / "AGENTS.md"
        original = "# Existing content\n"
        target.write_text(original)
        new_content = "Generated content"

        inject_into_file(target, new_content)

        result = target.read_text()
        assert "# Existing content" in result
        assert "Generated content" in result
        # Content should be at the end
        assert result.endswith(("Generated content\n", "Generated content"))

    def test_custom_marker_id(self, tmp_path: Path) -> None:
        """inject_into_file uses custom marker ID."""
        target = tmp_path / "AGENTS.md"
        original = """# Docs

<!-- INDEX:START -->
Old index
<!-- INDEX:END -->
"""
        target.write_text(original)
        new_content = "New index"

        inject_into_file(target, new_content, marker_id="INDEX")

        result = target.read_text()
        assert "Old index" not in result
        assert "New index" in result
        assert "<!-- INDEX:START -->" in result
        assert "<!-- INDEX:END -->" in result

    def test_preserves_content_outside_markers(self, tmp_path: Path) -> None:
        """inject_into_file preserves content before and after markers."""
        target = tmp_path / "AGENTS.md"
        original = """# Before

<!-- DOCS:START -->
Generated
<!-- DOCS:END -->

# After
"""
        target.write_text(original)
        new_content = "Updated"

        inject_into_file(target, new_content)

        result = target.read_text()
        assert "# Before" in result
        assert "# After" in result
        assert "Updated" in result

    def test_handles_empty_content(self, tmp_path: Path) -> None:
        """inject_into_file handles empty content string."""
        target = tmp_path / "AGENTS.md"

        inject_into_file(target, "")

        assert target.exists()
        assert target.read_text() == ""

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """inject_into_file creates parent directories if needed."""
        target = tmp_path / "nested" / "dir" / "AGENTS.md"
        content = "# Content"

        inject_into_file(target, content)

        assert target.exists()
        assert target.read_text() == content

    def test_marker_content_includes_newlines(self, tmp_path: Path) -> None:
        """inject_into_file properly handles content with newlines."""
        target = tmp_path / "AGENTS.md"
        original = """# Header

<!-- DOCS:START -->
old
<!-- DOCS:END -->
"""
        target.write_text(original)
        new_content = "Line 1\nLine 2\nLine 3"

        inject_into_file(target, new_content)

        result = target.read_text()
        assert "Line 1\nLine 2\nLine 3" in result

    def test_only_start_marker_appends(self, tmp_path: Path) -> None:
        """If only start marker exists, treat as no markers (append)."""
        target = tmp_path / "AGENTS.md"
        original = """# Header

<!-- DOCS:START -->
incomplete
"""
        target.write_text(original)
        new_content = "New content"

        inject_into_file(target, new_content)

        result = target.read_text()
        # Should append since markers are incomplete
        assert "# Header" in result
        assert "New content" in result


class TestIntegration:
    """Integration tests for output formatter."""

    def test_render_and_inject_workflow(self, tmp_path: Path) -> None:
        """Test complete workflow: render index then inject into file."""
        # Setup files
        files = [
            make_docfile("README.md", tier="required", section=""),
            make_docfile("docs/api/auth.md", tier="recommended", section="api"),
        ]
        tiers = [
            TierConfig(name="required", instruction="Read first"),
            TierConfig(name="recommended", instruction="Read when relevant"),
        ]

        # Render
        content = render_index(files, tiers)

        # Create existing file with markers
        target = tmp_path / "AGENTS.md"
        target.write_text("""# Project Documentation

<!-- DOCS:START -->
placeholder
<!-- DOCS:END -->

## Contributing
See CONTRIBUTING.md
""")

        # Inject
        inject_into_file(target, content)

        # Verify
        result = target.read_text()
        assert "## Required [Read first]" in result
        assert "README.md" in result
        assert "## Contributing" in result
        assert "placeholder" not in result
