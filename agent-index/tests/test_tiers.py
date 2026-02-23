"""Tests for tier system functionality."""

from datetime import UTC, datetime

from agent_index.models import DocFile, DocTree, TierConfig
from agent_index.tiers import assign_tiers, group_by_section, sort_files_bluf


def make_docfile(rel_path: str, tier: str = "", section: str = "", priority: int = 0) -> DocFile:
    """Create a DocFile with minimal required fields for testing."""
    return DocFile(
        rel_path=rel_path,
        content="# Test content",
        size_bytes=100,
        tier=tier,
        section=section,
        priority=priority,
    )


def make_doctree(files: list[DocFile]) -> DocTree:
    """Create a DocTree from a list of DocFiles."""
    return DocTree(
        files={f.rel_path: f for f in files},
        scanned_at=datetime.now(UTC),
        source="/test",
    )


class TestAssignTiers:
    """Tests for assign_tiers function."""

    def test_empty_tree_returns_empty_tree(self) -> None:
        """assign_tiers handles empty DocTree."""
        tree = make_doctree([])
        tiers = [TierConfig(name="required", instruction="Read first", patterns=["*.md"])]

        result = assign_tiers(tree, tiers)

        assert result.files == {}

    def test_matches_simple_glob_pattern(self) -> None:
        """assign_tiers matches files to tier patterns."""
        tree = make_doctree([make_docfile("README.md")])
        tiers = [
            TierConfig(name="required", instruction="Read first", patterns=["README.md"]),
        ]

        result = assign_tiers(tree, tiers)

        assert result.files["README.md"].tier == "required"

    def test_matches_wildcard_pattern(self) -> None:
        """assign_tiers matches wildcard patterns."""
        tree = make_doctree([
            make_docfile("readme.md"),
            make_docfile("guide.md"),
            make_docfile("api.txt"),
        ])
        tiers = [
            TierConfig(name="required", instruction="Read first", patterns=["*.md"]),
            TierConfig(name="reference", instruction="Fallback", patterns=[]),
        ]

        result = assign_tiers(tree, tiers)

        assert result.files["readme.md"].tier == "required"
        assert result.files["guide.md"].tier == "required"
        assert result.files["api.txt"].tier == "reference"  # Falls through to last tier

    def test_wildcard_does_not_match_across_path_separators(self) -> None:
        """A single * should not match across / path separators."""
        tree = make_doctree([
            make_docfile("file.md"),
            make_docfile("docs/file.md"),
        ])
        tiers = [
            TierConfig(name="required", instruction="Read first", patterns=["*.md"]),
            TierConfig(name="reference", instruction="Fallback", patterns=[]),
        ]

        result = assign_tiers(tree, tiers)

        assert result.files["file.md"].tier == "required"
        # docs/file.md should NOT match *.md (single * doesn't cross /)
        assert result.files["docs/file.md"].tier == "reference"

    def test_matches_double_star_pattern(self) -> None:
        """assign_tiers matches **/pattern for any directory depth."""
        tree = make_doctree([
            make_docfile("README.md"),
            make_docfile("docs/README.md"),
            make_docfile("src/lib/README.md"),
        ])
        tiers = [
            TierConfig(name="required", instruction="Read first", patterns=["**/README.md"]),
        ]

        result = assign_tiers(tree, tiers)

        assert result.files["README.md"].tier == "required"
        assert result.files["docs/README.md"].tier == "required"
        assert result.files["src/lib/README.md"].tier == "required"

    def test_matches_directory_wildcard_pattern(self) -> None:
        """assign_tiers matches docs/** for all files in directory tree."""
        tree = make_doctree([
            make_docfile("docs/guide.md"),
            make_docfile("docs/api/users.md"),
            make_docfile("src/readme.md"),
        ])
        tiers = [
            TierConfig(name="recommended", instruction="Read when relevant", patterns=["docs/**"]),
            TierConfig(name="reference", instruction="Fallback", patterns=[]),
        ]

        result = assign_tiers(tree, tiers)

        assert result.files["docs/guide.md"].tier == "recommended"
        assert result.files["docs/api/users.md"].tier == "recommended"
        assert result.files["src/readme.md"].tier == "reference"  # Falls through to last tier

    def test_first_matching_tier_wins(self) -> None:
        """assign_tiers uses the first tier that matches (order matters)."""
        tree = make_doctree([make_docfile("docs/README.md")])
        tiers = [
            TierConfig(name="required", instruction="Read first", patterns=["**/README.md"]),
            TierConfig(name="recommended", instruction="Read later", patterns=["docs/**"]),
        ]

        result = assign_tiers(tree, tiers)

        # README.md matches both patterns, but required tier comes first
        assert result.files["docs/README.md"].tier == "required"

    def test_unmatched_files_get_last_tier(self) -> None:
        """Files that match no pattern get assigned to the last tier."""
        tree = make_doctree([
            make_docfile("README.md"),
            make_docfile("random.txt"),
        ])
        tiers = [
            TierConfig(name="required", instruction="Read first", patterns=["README.md"]),
            TierConfig(name="reference", instruction="Consult as needed", patterns=[]),
        ]

        result = assign_tiers(tree, tiers)

        assert result.files["README.md"].tier == "required"
        assert result.files["random.txt"].tier == "reference"  # Falls through to last tier

    def test_empty_tier_configs_uses_empty_tier(self) -> None:
        """With no tier configs, files keep empty tier."""
        tree = make_doctree([make_docfile("README.md")])

        result = assign_tiers(tree, [])

        assert result.files["README.md"].tier == ""

    def test_multiple_patterns_in_tier(self) -> None:
        """Tier with multiple patterns matches any of them."""
        tree = make_doctree([
            make_docfile("README.md"),
            make_docfile("ARCHITECTURE.md"),
            make_docfile("CONVENTIONS.md"),
            make_docfile("other.md"),
        ])
        tiers = [
            TierConfig(
                name="required",
                instruction="Read first",
                patterns=["**/README.md", "**/ARCHITECTURE.md", "**/CONVENTIONS.md"],
            ),
            TierConfig(name="reference", instruction="Fallback", patterns=[]),
        ]

        result = assign_tiers(tree, tiers)

        assert result.files["README.md"].tier == "required"
        assert result.files["ARCHITECTURE.md"].tier == "required"
        assert result.files["CONVENTIONS.md"].tier == "required"
        assert result.files["other.md"].tier == "reference"  # Falls through to last tier

    def test_preserves_original_tree_metadata(self) -> None:
        """assign_tiers preserves source and scanned_at from original tree."""
        original = DocTree(
            files={"test.md": make_docfile("test.md")},
            scanned_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
            source="/original/path",
            total_tokens=500,
        )
        tiers = [TierConfig(name="required", instruction="Read first", patterns=["*.md"])]

        result = assign_tiers(original, tiers)

        assert result.source == "/original/path"
        assert result.scanned_at == datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        assert result.total_tokens == 500

    def test_preserves_file_content_and_metadata(self) -> None:
        """assign_tiers preserves file content and other metadata."""
        doc = DocFile(
            rel_path="test.md",
            content="# Preserved Content",
            size_bytes=200,
            tier="",
            section="",
            priority=5,
            content_hash="abc123",
            summary="A test file",
        )
        tree = DocTree(
            files={"test.md": doc},
            scanned_at=datetime.now(UTC),
            source="/test",
        )
        tiers = [TierConfig(name="required", instruction="Read first", patterns=["*.md"])]

        result = assign_tiers(tree, tiers)

        result_doc = result.files["test.md"]
        assert result_doc.content == "# Preserved Content"
        assert result_doc.size_bytes == 200
        assert result_doc.priority == 5
        assert result_doc.content_hash == "abc123"
        assert result_doc.summary == "A test file"


class TestAssignTiersSections:
    """Tests for section assignment in assign_tiers."""

    def test_top_level_file_gets_empty_section(self) -> None:
        """Top-level files get empty section."""
        tree = make_doctree([make_docfile("README.md")])
        tiers = [TierConfig(name="required", instruction="Read first", patterns=["*.md"])]

        result = assign_tiers(tree, tiers)

        assert result.files["README.md"].section == ""

    def test_single_directory_file_gets_empty_section(self) -> None:
        """Files one directory deep get empty section (first dir is root)."""
        tree = make_doctree([make_docfile("docs/setup.md")])
        tiers = [TierConfig(name="required", instruction="Read first", patterns=["**/*.md"])]

        result = assign_tiers(tree, tiers)

        # docs/setup.md - "docs" is root, so section is empty
        assert result.files["docs/setup.md"].section == ""

    def test_nested_file_gets_section_from_subdirectory(self) -> None:
        """Files in nested directories get section from first subdirectory."""
        tree = make_doctree([make_docfile("docs/guides/auth.md")])
        tiers = [TierConfig(name="required", instruction="Read first", patterns=["**/*.md"])]

        result = assign_tiers(tree, tiers)

        # docs/guides/auth.md - section is "guides"
        assert result.files["docs/guides/auth.md"].section == "guides"

    def test_deeply_nested_file_gets_section_from_second_directory(self) -> None:
        """Files in deeply nested paths get section from second directory component."""
        tree = make_doctree([make_docfile("docs/api/v2/users/create.md")])
        tiers = [TierConfig(name="required", instruction="Read first", patterns=["**/*.md"])]

        result = assign_tiers(tree, tiers)

        # docs/api/v2/users/create.md - section is "api"
        assert result.files["docs/api/v2/users/create.md"].section == "api"

    def test_multiple_files_get_appropriate_sections(self) -> None:
        """Multiple files get appropriate sections based on their paths."""
        tree = make_doctree([
            make_docfile("README.md"),
            make_docfile("docs/setup.md"),
            make_docfile("docs/guides/auth.md"),
            make_docfile("docs/api/users.md"),
        ])
        tiers = [TierConfig(name="required", instruction="Read first", patterns=["**/*.md"])]

        result = assign_tiers(tree, tiers)

        assert result.files["README.md"].section == ""
        assert result.files["docs/setup.md"].section == ""
        assert result.files["docs/guides/auth.md"].section == "guides"
        assert result.files["docs/api/users.md"].section == "api"


class TestSortFilesBluf:
    """Tests for sort_files_bluf function."""

    def test_empty_list_returns_empty(self) -> None:
        """sort_files_bluf handles empty list."""
        result = sort_files_bluf([], [])
        assert result == []

    def test_sorts_by_tier_order(self) -> None:
        """sort_files_bluf sorts files by tier order (first tier first)."""
        files = [
            make_docfile("reference.md", tier="reference"),
            make_docfile("required.md", tier="required"),
            make_docfile("recommended.md", tier="recommended"),
        ]
        tiers = [
            TierConfig(name="required", instruction="First"),
            TierConfig(name="recommended", instruction="Second"),
            TierConfig(name="reference", instruction="Third"),
        ]

        result = sort_files_bluf(files, tiers)

        assert [f.rel_path for f in result] == [
            "required.md",
            "recommended.md",
            "reference.md",
        ]

    def test_sorts_by_priority_within_tier(self) -> None:
        """sort_files_bluf sorts by priority (descending) within same tier."""
        files = [
            make_docfile("low.md", tier="required", priority=1),
            make_docfile("high.md", tier="required", priority=10),
            make_docfile("medium.md", tier="required", priority=5),
        ]
        tiers = [TierConfig(name="required", instruction="First")]

        result = sort_files_bluf(files, tiers)

        assert [f.rel_path for f in result] == ["high.md", "medium.md", "low.md"]

    def test_sorts_by_path_when_same_priority(self) -> None:
        """sort_files_bluf sorts alphabetically by path when priority is equal."""
        files = [
            make_docfile("zebra.md", tier="required", priority=0),
            make_docfile("alpha.md", tier="required", priority=0),
            make_docfile("beta.md", tier="required", priority=0),
        ]
        tiers = [TierConfig(name="required", instruction="First")]

        result = sort_files_bluf(files, tiers)

        assert [f.rel_path for f in result] == ["alpha.md", "beta.md", "zebra.md"]

    def test_combined_sort_order(self) -> None:
        """sort_files_bluf combines tier, priority, and path sorting."""
        files = [
            make_docfile("ref_low.md", tier="reference", priority=1),
            make_docfile("req_high.md", tier="required", priority=10),
            make_docfile("req_low_b.md", tier="required", priority=1),
            make_docfile("req_low_a.md", tier="required", priority=1),
            make_docfile("rec_med.md", tier="recommended", priority=5),
        ]
        tiers = [
            TierConfig(name="required", instruction="First"),
            TierConfig(name="recommended", instruction="Second"),
            TierConfig(name="reference", instruction="Third"),
        ]

        result = sort_files_bluf(files, tiers)

        assert [f.rel_path for f in result] == [
            "req_high.md",      # required, priority 10
            "req_low_a.md",     # required, priority 1, path a
            "req_low_b.md",     # required, priority 1, path b
            "rec_med.md",       # recommended, priority 5
            "ref_low.md",       # reference, priority 1
        ]

    def test_unknown_tier_sorts_last(self) -> None:
        """Files with unknown tiers sort after all known tiers."""
        files = [
            make_docfile("unknown.md", tier="custom"),
            make_docfile("required.md", tier="required"),
        ]
        tiers = [TierConfig(name="required", instruction="First")]

        result = sort_files_bluf(files, tiers)

        assert [f.rel_path for f in result] == ["required.md", "unknown.md"]

    def test_empty_tier_sorts_last(self) -> None:
        """Files with empty tier sort after all known tiers."""
        files = [
            make_docfile("no_tier.md", tier=""),
            make_docfile("required.md", tier="required"),
        ]
        tiers = [TierConfig(name="required", instruction="First")]

        result = sort_files_bluf(files, tiers)

        assert [f.rel_path for f in result] == ["required.md", "no_tier.md"]

    def test_no_tier_configs_sorts_by_priority_and_path(self) -> None:
        """With no tier configs, sort by priority then path only."""
        files = [
            make_docfile("b.md", tier="any", priority=5),
            make_docfile("a.md", tier="any", priority=5),
            make_docfile("c.md", tier="any", priority=10),
        ]

        result = sort_files_bluf(files, [])

        # All unknown tiers, so sort by priority desc, then path asc
        assert [f.rel_path for f in result] == ["c.md", "a.md", "b.md"]


class TestGroupBySection:
    """Tests for group_by_section function."""

    def test_empty_list_returns_empty_dict(self) -> None:
        """group_by_section handles empty list."""
        result = group_by_section([])
        assert result == {}

    def test_single_file_single_section(self) -> None:
        """group_by_section groups single file correctly."""
        files = [make_docfile("test.md", section="guides")]

        result = group_by_section(files)

        assert "guides" in result
        assert len(result["guides"]) == 1
        assert result["guides"][0].rel_path == "test.md"

    def test_multiple_files_same_section(self) -> None:
        """group_by_section groups multiple files in same section."""
        files = [
            make_docfile("auth.md", section="guides"),
            make_docfile("setup.md", section="guides"),
        ]

        result = group_by_section(files)

        assert len(result) == 1
        assert "guides" in result
        assert len(result["guides"]) == 2

    def test_files_in_different_sections(self) -> None:
        """group_by_section groups files into different sections."""
        files = [
            make_docfile("auth.md", section="guides"),
            make_docfile("users.md", section="api"),
            make_docfile("setup.md", section="guides"),
        ]

        result = group_by_section(files)

        assert len(result) == 2
        assert "guides" in result
        assert "api" in result
        assert len(result["guides"]) == 2
        assert len(result["api"]) == 1

    def test_empty_section_grouped_together(self) -> None:
        """Files with empty section are grouped together."""
        files = [
            make_docfile("readme.md", section=""),
            make_docfile("changelog.md", section=""),
            make_docfile("guide.md", section="guides"),
        ]

        result = group_by_section(files)

        assert "" in result
        assert len(result[""]) == 2
        assert "guides" in result
        assert len(result["guides"]) == 1

    def test_preserves_file_order_within_sections(self) -> None:
        """group_by_section preserves order of files within each section."""
        files = [
            make_docfile("first.md", section="guides"),
            make_docfile("second.md", section="guides"),
            make_docfile("third.md", section="guides"),
        ]

        result = group_by_section(files)

        paths = [f.rel_path for f in result["guides"]]
        assert paths == ["first.md", "second.md", "third.md"]


class TestIntegration:
    """Integration tests combining tier assignment, sorting, and grouping."""

    def test_full_workflow(self) -> None:
        """Test complete workflow: scan -> assign tiers -> sort -> group."""
        # Create files simulating scanner output
        files = [
            make_docfile("README.md"),
            make_docfile("docs/setup.md"),
            make_docfile("docs/guides/auth.md"),
            make_docfile("docs/guides/users.md"),
            make_docfile("docs/api/endpoints.md"),
            make_docfile("docs/api/errors.md"),
        ]
        tree = make_doctree(files)

        # Define tiers matching DESIGN.md defaults
        tiers = [
            TierConfig(
                name="required",
                instruction="Read these files at the start of every session.",
                patterns=["**/README.md"],
            ),
            TierConfig(
                name="recommended",
                instruction="Read these files when working on related tasks.",
                patterns=["docs/guides/**"],
            ),
            TierConfig(
                name="reference",
                instruction="Consult these files when you need specific details.",
                patterns=["docs/api/**", "docs/config/**"],
            ),
        ]

        # Step 1: Assign tiers
        assigned = assign_tiers(tree, tiers)

        assert assigned.files["README.md"].tier == "required"
        assert assigned.files["docs/guides/auth.md"].tier == "recommended"
        assert assigned.files["docs/api/endpoints.md"].tier == "reference"
        # docs/setup.md doesn't match any pattern, goes to last tier
        assert assigned.files["docs/setup.md"].tier == "reference"

        # Step 2: Sort BLUF
        sorted_files = sort_files_bluf(list(assigned.files.values()), tiers)

        # Verify order: required first, then recommended, then reference
        tier_order = [f.tier for f in sorted_files]
        assert tier_order[0] == "required"  # README.md
        # Next should be recommended files
        assert "recommended" in tier_order[1:3]
        # Then reference files
        assert all(t == "reference" for t in tier_order[-3:])

        # Step 3: Group by section
        grouped = group_by_section(sorted_files)

        # Check sections exist
        assert "" in grouped  # Root files
        assert "guides" in grouped
        assert "api" in grouped

    def test_priority_affects_sort_order(self) -> None:
        """Test that explicit priority values affect final sort order."""
        files = [
            DocFile(
                rel_path="important.md",
                content="# Important",
                size_bytes=100,
                tier="",
                section="",
                priority=100,  # High priority
            ),
            DocFile(
                rel_path="README.md",
                content="# Readme",
                size_bytes=100,
                tier="",
                section="",
                priority=0,  # Default priority
            ),
        ]
        tree = make_doctree(files)

        tiers = [
            TierConfig(
                name="required",
                instruction="Read first",
                patterns=["**/README.md", "important.md"],
            ),
        ]

        assigned = assign_tiers(tree, tiers)
        sorted_files = sort_files_bluf(list(assigned.files.values()), tiers)

        # important.md should come first due to higher priority
        assert sorted_files[0].rel_path == "important.md"
        assert sorted_files[1].rel_path == "README.md"
