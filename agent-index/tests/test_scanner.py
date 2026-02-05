"""Tests for local file scanner functionality."""

from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent

import pytest
from agent_index.models import DocFile, DocTree
from agent_index.scanner import scan_local


class TestScanLocalBasic:
    """Basic tests for scan_local function."""

    def test_scans_single_markdown_file(self, tmp_path: Path) -> None:
        """scan_local finds a single markdown file."""
        doc_file = tmp_path / "readme.md"
        doc_file.write_text("# Hello World")

        result = scan_local(tmp_path)

        assert isinstance(result, DocTree)
        assert "readme.md" in result.files
        assert result.files["readme.md"].content == "# Hello World"

    def test_returns_doctree_with_metadata(self, tmp_path: Path) -> None:
        """scan_local returns DocTree with source and scanned_at."""
        doc_file = tmp_path / "test.md"
        doc_file.write_text("test")

        result = scan_local(tmp_path)

        assert result.source == str(tmp_path)
        assert isinstance(result.scanned_at, datetime)
        # scanned_at should be recent (within last minute)
        assert (datetime.now(UTC) - result.scanned_at).total_seconds() < 60

    def test_docfile_has_correct_rel_path(self, tmp_path: Path) -> None:
        """DocFile.rel_path is relative to root_path."""
        subdir = tmp_path / "docs" / "guides"
        subdir.mkdir(parents=True)
        doc_file = subdir / "auth.md"
        doc_file.write_text("# Auth Guide")

        result = scan_local(tmp_path)

        # Should use forward slashes for consistency
        assert "docs/guides/auth.md" in result.files

    def test_docfile_has_size_bytes(self, tmp_path: Path) -> None:
        """DocFile includes correct size_bytes."""
        content = "Hello, this is test content!"
        doc_file = tmp_path / "test.md"
        doc_file.write_text(content, encoding="utf-8")

        result = scan_local(tmp_path)

        # Size should match encoded byte length
        assert result.files["test.md"].size_bytes == len(content.encode("utf-8"))

    def test_docfile_has_content_hash(self, tmp_path: Path) -> None:
        """DocFile includes SHA-256 content hash."""
        content = "Test content for hashing"
        doc_file = tmp_path / "test.md"
        doc_file.write_text(content)

        result = scan_local(tmp_path)

        # Hash should be 64 hex characters (SHA-256)
        hash_value = result.files["test.md"].content_hash
        assert len(hash_value) == 64
        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_content_hash_is_deterministic(self, tmp_path: Path) -> None:
        """Same content produces same hash."""
        content = "Identical content"
        file1 = tmp_path / "file1.md"
        file2 = tmp_path / "file2.md"
        file1.write_text(content)
        file2.write_text(content)

        result = scan_local(tmp_path)

        assert result.files["file1.md"].content_hash == result.files["file2.md"].content_hash

    def test_docfile_has_last_modified(self, tmp_path: Path) -> None:
        """DocFile includes last_modified timestamp."""
        doc_file = tmp_path / "test.md"
        doc_file.write_text("content")

        result = scan_local(tmp_path)

        last_mod = result.files["test.md"].last_modified
        assert isinstance(last_mod, datetime)
        assert last_mod.tzinfo is not None  # Should be timezone-aware

    def test_docfile_tier_and_section_initially_empty(self, tmp_path: Path) -> None:
        """DocFile.tier and DocFile.section are empty string initially."""
        doc_file = tmp_path / "test.md"
        doc_file.write_text("content")

        result = scan_local(tmp_path)

        doc = result.files["test.md"]
        assert doc.tier == ""
        assert doc.section == ""

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """scan_local accepts string path as root_path."""
        doc_file = tmp_path / "test.md"
        doc_file.write_text("content")

        result = scan_local(str(tmp_path))

        assert "test.md" in result.files


class TestScanLocalFileExtensions:
    """Tests for file extension filtering."""

    def test_default_extensions_md(self, tmp_path: Path) -> None:
        """scan_local includes .md files by default."""
        (tmp_path / "readme.md").write_text("markdown")

        result = scan_local(tmp_path)

        assert "readme.md" in result.files

    def test_default_extensions_mdx(self, tmp_path: Path) -> None:
        """scan_local includes .mdx files by default."""
        (tmp_path / "component.mdx").write_text("mdx content")

        result = scan_local(tmp_path)

        assert "component.mdx" in result.files

    def test_default_extensions_rst(self, tmp_path: Path) -> None:
        """scan_local includes .rst files by default."""
        (tmp_path / "index.rst").write_text("rst content")

        result = scan_local(tmp_path)

        assert "index.rst" in result.files

    def test_default_extensions_txt(self, tmp_path: Path) -> None:
        """scan_local includes .txt files by default."""
        (tmp_path / "notes.txt").write_text("text content")

        result = scan_local(tmp_path)

        assert "notes.txt" in result.files

    def test_excludes_non_matching_extensions(self, tmp_path: Path) -> None:
        """scan_local excludes files with non-matching extensions."""
        (tmp_path / "script.py").write_text("python code")
        (tmp_path / "data.json").write_text("{}")
        (tmp_path / "readme.md").write_text("markdown")

        result = scan_local(tmp_path)

        assert "script.py" not in result.files
        assert "data.json" not in result.files
        assert "readme.md" in result.files

    def test_custom_file_extensions(self, tmp_path: Path) -> None:
        """scan_local respects custom file_extensions."""
        (tmp_path / "readme.md").write_text("markdown")
        (tmp_path / "script.py").write_text("python")

        result = scan_local(tmp_path, file_extensions={".py"})

        assert "script.py" in result.files
        assert "readme.md" not in result.files

    def test_file_extensions_case_insensitive(self, tmp_path: Path) -> None:
        """scan_local matches extensions case-insensitively."""
        (tmp_path / "README.MD").write_text("uppercase")
        (tmp_path / "guide.Md").write_text("mixed case")

        result = scan_local(tmp_path)

        # Both should be found regardless of case
        assert len(result.files) == 2


class TestScanLocalIgnorePatterns:
    """Tests for ignore pattern filtering."""

    def test_default_ignores_node_modules(self, tmp_path: Path) -> None:
        """scan_local ignores node_modules by default."""
        node_mods = tmp_path / "node_modules"
        node_mods.mkdir()
        (node_mods / "package" / "readme.md").parent.mkdir(parents=True)
        (node_mods / "package" / "readme.md").write_text("ignored")
        (tmp_path / "readme.md").write_text("included")

        result = scan_local(tmp_path)

        assert "readme.md" in result.files
        assert "node_modules/package/readme.md" not in result.files

    def test_default_ignores_pycache(self, tmp_path: Path) -> None:
        """scan_local ignores __pycache__ by default."""
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "cache.md").write_text("cached")

        result = scan_local(tmp_path)

        assert "__pycache__/cache.md" not in result.files

    def test_default_ignores_git(self, tmp_path: Path) -> None:
        """scan_local ignores .git by default."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config.md").write_text("git config")

        result = scan_local(tmp_path)

        assert ".git/config.md" not in result.files

    def test_default_ignores_venv(self, tmp_path: Path) -> None:
        """scan_local ignores .venv by default."""
        venv = tmp_path / ".venv"
        venv.mkdir()
        (venv / "readme.md").write_text("venv readme")

        result = scan_local(tmp_path)

        assert ".venv/readme.md" not in result.files

    def test_custom_ignore_patterns(self, tmp_path: Path) -> None:
        """scan_local respects custom ignore_patterns."""
        build = tmp_path / "build"
        build.mkdir()
        (build / "output.md").write_text("build output")
        (tmp_path / "readme.md").write_text("included")

        result = scan_local(tmp_path, ignore_patterns=["build"])

        assert "readme.md" in result.files
        assert "build/output.md" not in result.files

    def test_ignore_pattern_matches_anywhere_in_path(self, tmp_path: Path) -> None:
        """Ignore pattern matches component anywhere in path."""
        deep = tmp_path / "src" / "node_modules" / "pkg"
        deep.mkdir(parents=True)
        (deep / "readme.md").write_text("deep ignored")

        result = scan_local(tmp_path)

        assert "src/node_modules/pkg/readme.md" not in result.files

    def test_empty_ignore_patterns_includes_all(self, tmp_path: Path) -> None:
        """Empty ignore_patterns list includes normally-ignored directories."""
        node_mods = tmp_path / "node_modules"
        node_mods.mkdir()
        (node_mods / "readme.md").write_text("included")

        result = scan_local(tmp_path, ignore_patterns=[])

        assert "node_modules/readme.md" in result.files


class TestScanLocalRecursive:
    """Tests for recursive directory scanning."""

    def test_scans_subdirectories(self, tmp_path: Path) -> None:
        """scan_local scans subdirectories recursively."""
        (tmp_path / "root.md").write_text("root")
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "guide.md").write_text("guide")
        api = docs / "api"
        api.mkdir()
        (api / "reference.md").write_text("reference")

        result = scan_local(tmp_path)

        assert "root.md" in result.files
        assert "docs/guide.md" in result.files
        assert "docs/api/reference.md" in result.files

    def test_handles_empty_directories(self, tmp_path: Path) -> None:
        """scan_local handles empty directories gracefully."""
        (tmp_path / "empty_dir").mkdir()
        (tmp_path / "readme.md").write_text("content")

        result = scan_local(tmp_path)

        assert "readme.md" in result.files
        assert len(result.files) == 1

    def test_empty_root_returns_empty_files(self, tmp_path: Path) -> None:
        """scan_local returns empty files dict for empty directory."""
        result = scan_local(tmp_path)

        assert result.files == {}


class TestScanLocalSymlinks:
    """Tests for symlink handling."""

    @pytest.mark.skipif(
        not hasattr(__import__("os"), "symlink"),
        reason="symlinks not supported on this platform"
    )
    def test_follows_symlink_to_file(self, tmp_path: Path) -> None:
        """scan_local follows symlinks to files."""
        real_file = tmp_path / "real" / "doc.md"
        real_file.parent.mkdir()
        real_file.write_text("real content")
        link = tmp_path / "link.md"
        try:
            link.symlink_to(real_file)
        except OSError:
            pytest.skip("symlinks not supported")

        result = scan_local(tmp_path)

        assert "link.md" in result.files
        assert result.files["link.md"].content == "real content"

    @pytest.mark.skipif(
        not hasattr(__import__("os"), "symlink"),
        reason="symlinks not supported on this platform"
    )
    def test_skips_symlink_to_directory(self, tmp_path: Path) -> None:
        """scan_local does not follow symlinks to directories."""
        real_dir = tmp_path / "real_dir"
        real_dir.mkdir()
        (real_dir / "doc.md").write_text("content")
        link_dir = tmp_path / "link_dir"
        try:
            link_dir.symlink_to(real_dir)
        except OSError:
            pytest.skip("symlinks not supported")

        result = scan_local(tmp_path)

        # Should find file in real_dir but not through symlinked dir
        assert "real_dir/doc.md" in result.files
        assert "link_dir/doc.md" not in result.files

    @pytest.mark.skipif(
        not hasattr(__import__("os"), "symlink"),
        reason="symlinks not supported on this platform"
    )
    def test_handles_broken_symlink(self, tmp_path: Path) -> None:
        """scan_local handles broken symlinks gracefully."""
        link = tmp_path / "broken.md"
        try:
            link.symlink_to(tmp_path / "nonexistent.md")
        except OSError:
            pytest.skip("symlinks not supported")
        (tmp_path / "valid.md").write_text("valid")

        result = scan_local(tmp_path)

        # Should skip broken symlink without error
        assert "broken.md" not in result.files
        assert "valid.md" in result.files

    @pytest.mark.skipif(
        not hasattr(__import__("os"), "symlink"),
        reason="symlinks not supported on this platform"
    )
    def test_handles_symlink_loop(self, tmp_path: Path) -> None:
        """scan_local handles symlink loops safely."""
        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        (dir1 / "doc.md").write_text("content")
        try:
            # Create a loop: dir1/link -> dir1
            (dir1 / "link").symlink_to(dir1)
        except OSError:
            pytest.skip("symlinks not supported")

        # Should complete without infinite loop
        result = scan_local(tmp_path)

        assert "dir1/doc.md" in result.files


class TestScanLocalErrors:
    """Tests for error handling."""

    def test_nonexistent_path_raises_file_not_found(self, tmp_path: Path) -> None:
        """scan_local raises FileNotFoundError for nonexistent path."""
        nonexistent = tmp_path / "does_not_exist"

        with pytest.raises(FileNotFoundError):
            scan_local(nonexistent)

    def test_file_path_raises_not_a_directory(self, tmp_path: Path) -> None:
        """scan_local raises NotADirectoryError when given a file."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("not a directory")

        with pytest.raises(NotADirectoryError):
            scan_local(file_path)


class TestScanLocalEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_handles_unicode_filenames(self, tmp_path: Path) -> None:
        """scan_local handles unicode filenames."""
        unicode_file = tmp_path / "docs_\u4e2d\u6587.md"
        unicode_file.write_text("unicode content")

        result = scan_local(tmp_path)

        assert "docs_\u4e2d\u6587.md" in result.files

    def test_handles_unicode_content(self, tmp_path: Path) -> None:
        """scan_local handles unicode content."""
        doc_file = tmp_path / "test.md"
        content = "# Unicode \u4e2d\u6587 \u65e5\u672c\u8a9e \ud55c\uad6d\uc5b4"
        doc_file.write_text(content, encoding="utf-8")

        result = scan_local(tmp_path)

        assert result.files["test.md"].content == content

    def test_handles_empty_file(self, tmp_path: Path) -> None:
        """scan_local handles empty files."""
        empty_file = tmp_path / "empty.md"
        empty_file.write_text("")

        result = scan_local(tmp_path)

        doc = result.files["empty.md"]
        assert doc.content == ""
        assert doc.size_bytes == 0

    def test_handles_large_file(self, tmp_path: Path) -> None:
        """scan_local handles larger files."""
        content = "x" * 100000  # 100KB of content
        large_file = tmp_path / "large.md"
        large_file.write_text(content)

        result = scan_local(tmp_path)

        assert result.files["large.md"].content == content
        assert result.files["large.md"].size_bytes == 100000

    def test_handles_files_with_dots_in_name(self, tmp_path: Path) -> None:
        """scan_local handles files with multiple dots in name."""
        (tmp_path / "file.name.with.dots.md").write_text("content")

        result = scan_local(tmp_path)

        assert "file.name.with.dots.md" in result.files

    def test_hidden_files_included(self, tmp_path: Path) -> None:
        """scan_local includes hidden files (starting with dot)."""
        (tmp_path / ".hidden.md").write_text("hidden content")

        result = scan_local(tmp_path)

        assert ".hidden.md" in result.files
