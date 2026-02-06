"""Tests for CI validation mode."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from agent_index.models import DocFile, DocTree
from agent_index.validate import ValidationResult, validate_index


def _make_doc_tree(root: Path, files: dict[str, str]) -> DocTree:
    """Helper to create a DocTree from a dict of rel_path -> content."""
    doc_files = {}
    for rel_path, content in files.items():
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        doc_files[rel_path] = DocFile(
            rel_path=rel_path,
            content=content,
            size_bytes=len(content.encode("utf-8")),
            tier="recommended",
            section="",
            content_hash=content_hash,
        )
    return DocTree(
        files=doc_files,
        scanned_at=datetime.now(UTC),
        source=str(root),
    )


class TestValidateIndex:
    """Tests for the validate_index function."""

    def test_passes_when_index_matches_disk(self, tmp_path: Path) -> None:
        """Validation passes when all indexed files exist on disk with matching hashes."""
        (tmp_path / "readme.md").write_text("# Hello")
        (tmp_path / "guide.md").write_text("# Guide")

        doc_tree = _make_doc_tree(tmp_path, {
            "readme.md": "# Hello",
            "guide.md": "# Guide",
        })

        result = validate_index(doc_tree, "some index content", tmp_path)

        assert result.valid is True
        assert result.missing_files == []
        assert result.extra_files == []
        assert result.stale_entries == []

    def test_detects_missing_files(self, tmp_path: Path) -> None:
        """Validation detects files in index but not on disk."""
        (tmp_path / "readme.md").write_text("# Hello")
        # "guide.md" is in the index but NOT on disk

        doc_tree = _make_doc_tree(tmp_path, {
            "readme.md": "# Hello",
            "guide.md": "# Guide",
        })

        result = validate_index(doc_tree, "some index content", tmp_path)

        assert result.valid is False
        assert "guide.md" in result.missing_files

    def test_detects_extra_files(self, tmp_path: Path) -> None:
        """Validation detects files on disk but not in index."""
        (tmp_path / "readme.md").write_text("# Hello")
        (tmp_path / "extra.md").write_text("# Extra file")

        doc_tree = _make_doc_tree(tmp_path, {
            "readme.md": "# Hello",
        })

        result = validate_index(doc_tree, "some index content", tmp_path)

        assert result.valid is False
        assert "extra.md" in result.extra_files

    def test_detects_stale_entries(self, tmp_path: Path) -> None:
        """Validation detects files whose content hash has changed."""
        # Write a file with different content than what's indexed
        (tmp_path / "readme.md").write_text("# Updated content")

        doc_tree = _make_doc_tree(tmp_path, {
            "readme.md": "# Original content",
        })

        result = validate_index(doc_tree, "some index content", tmp_path)

        assert result.valid is False
        assert "readme.md" in result.stale_entries

    def test_valid_is_false_when_issues_found(self, tmp_path: Path) -> None:
        """ValidationResult.valid is False when any issue exists."""
        # Missing file
        doc_tree = _make_doc_tree(tmp_path, {
            "missing.md": "# Missing",
        })

        result = validate_index(doc_tree, "some index content", tmp_path)

        assert result.valid is False

    def test_empty_index(self, tmp_path: Path) -> None:
        """Validation with empty doc_tree and files on disk detects extras."""
        (tmp_path / "readme.md").write_text("# Hello")

        doc_tree = DocTree(
            files={},
            scanned_at=datetime.now(UTC),
            source=str(tmp_path),
        )

        result = validate_index(doc_tree, "", tmp_path)

        assert result.valid is False
        assert "readme.md" in result.extra_files

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Validation with empty directory and empty index passes."""
        doc_tree = DocTree(
            files={},
            scanned_at=datetime.now(UTC),
            source=str(tmp_path),
        )

        result = validate_index(doc_tree, "", tmp_path)

        assert result.valid is True
        assert result.missing_files == []
        assert result.extra_files == []
        assert result.stale_entries == []


class TestValidationResult:
    """Tests for the ValidationResult dataclass."""

    def test_default_is_valid(self) -> None:
        """Default ValidationResult is valid."""
        result = ValidationResult()
        assert result.valid is True
        assert result.missing_files == []
        assert result.extra_files == []
        assert result.stale_entries == []

    def test_with_issues(self) -> None:
        """ValidationResult can be constructed with issues."""
        result = ValidationResult(
            valid=False,
            missing_files=["a.md"],
            extra_files=["b.md"],
            stale_entries=["c.md"],
        )
        assert result.valid is False
        assert result.missing_files == ["a.md"]
        assert result.extra_files == ["b.md"]
        assert result.stale_entries == ["c.md"]
