"""Tests for sample documentation fixtures and DocTree loader."""

from __future__ import annotations

import json

from agent_evals.fixtures import (
    load_sample_doc_tree,
    sample_docs_directory,
)
from agent_index.models import DocFile, DocTree

_VALID_TIERS = {"required", "recommended", "reference"}


# ---------------------------------------------------------------------------
# DocTree loader tests
# ---------------------------------------------------------------------------


class TestLoadSampleDocTree:
    """Tests for the load_sample_doc_tree function."""

    def test_load_sample_doc_tree_returns_doc_tree(self) -> None:
        """load_sample_doc_tree returns a DocTree instance."""
        tree = load_sample_doc_tree()
        assert isinstance(tree, DocTree)

    def test_sample_doc_tree_has_expected_file_count(self) -> None:
        """The fixture contains between 50 and 80 files."""
        tree = load_sample_doc_tree()
        count = len(tree.files)
        assert 50 <= count <= 80, f"Expected 50-80 files, got {count}"

    def test_sample_doc_tree_files_have_content(self) -> None:
        """Every file in the tree has non-empty content."""
        tree = load_sample_doc_tree()
        for rel_path, doc_file in tree.files.items():
            assert isinstance(doc_file, DocFile)
            assert len(doc_file.content) > 0, (
                f"File {rel_path!r} has empty content"
            )

    def test_sample_doc_tree_has_multiple_domains(self) -> None:
        """The fixture includes files across api/, repo/, and workflows/ sections."""
        tree = load_sample_doc_tree()
        sections = {doc_file.section for doc_file in tree.files.values()}
        assert "api" in sections, "Missing api section"
        assert "repo" in sections, "Missing repo section"
        assert "workflows" in sections, "Missing workflows section"

    def test_sample_doc_tree_files_have_valid_tiers(self) -> None:
        """Every file has a tier of required, recommended, or reference."""
        tree = load_sample_doc_tree()
        for rel_path, doc_file in tree.files.items():
            assert doc_file.tier in _VALID_TIERS, (
                f"File {rel_path!r} has invalid tier {doc_file.tier!r}"
            )

    def test_sample_doc_tree_files_have_summaries(self) -> None:
        """Every file has a non-empty summary."""
        tree = load_sample_doc_tree()
        for rel_path, doc_file in tree.files.items():
            assert doc_file.summary is not None and len(doc_file.summary) > 0, (
                f"File {rel_path!r} has no summary"
            )

    def test_sample_doc_tree_files_have_token_counts(self) -> None:
        """Every file has a positive token_count."""
        tree = load_sample_doc_tree()
        for rel_path, doc_file in tree.files.items():
            assert doc_file.token_count is not None and doc_file.token_count > 0, (
                f"File {rel_path!r} has no positive token_count"
            )


# ---------------------------------------------------------------------------
# Sample docs directory tests
# ---------------------------------------------------------------------------


class TestSampleDocsDirectory:
    """Tests for the on-disk sample_docs directory."""

    def test_sample_docs_directory_exists(self) -> None:
        """The sample_docs directory exists on disk."""
        docs_dir = sample_docs_directory()
        assert docs_dir.is_dir(), f"Directory does not exist: {docs_dir}"

    def test_doc_tree_json_matches_sample_docs(self) -> None:
        """The keys in doc_tree.json match the .md files under sample_docs/."""
        docs_dir = sample_docs_directory()
        on_disk = {
            str(p.relative_to(docs_dir)).replace("\\", "/")
            for p in docs_dir.rglob("*.md")
        }

        json_path = docs_dir.parent / "doc_tree.json"
        raw = json_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        in_json = set(data["files"].keys())

        assert on_disk == in_json, (
            f"Mismatch between disk and JSON.\n"
            f"  On disk only: {on_disk - in_json}\n"
            f"  In JSON only: {in_json - on_disk}"
        )


# ---------------------------------------------------------------------------
# Fixture quality tests (timestamp + size distribution)
# ---------------------------------------------------------------------------


class TestFixtureTimestamps:
    """Tests for last_modified timestamp distribution in the fixture."""

    def test_most_files_have_timestamps(self) -> None:
        """At least 80% of files should have non-null last_modified."""
        tree = load_sample_doc_tree()
        with_ts = sum(
            1 for doc in tree.files.values() if doc.last_modified is not None
        )
        ratio = with_ts / len(tree.files)
        assert ratio >= 0.80, (
            f"Only {with_ts}/{len(tree.files)} files have timestamps ({ratio:.0%})"
        )

    def test_some_files_have_null_timestamps(self) -> None:
        """3-5 files should have null last_modified for fallback testing."""
        tree = load_sample_doc_tree()
        null_count = sum(
            1 for doc in tree.files.values() if doc.last_modified is None
        )
        assert 3 <= null_count <= 5, (
            f"Expected 3-5 null timestamps, got {null_count}"
        )


class TestFixtureSizeDistribution:
    """Tests for file size distribution enabling granularity-mixed."""

    def test_has_small_files(self) -> None:
        """At least 4 files should be <500 bytes (small bucket)."""
        tree = load_sample_doc_tree()
        small = [
            p for p, doc in tree.files.items() if doc.size_bytes < 500
        ]
        assert len(small) >= 4, (
            f"Expected >=4 small files (<500 bytes), got {len(small)}: {small}"
        )

    def test_has_large_files(self) -> None:
        """At least 4 files should be >2000 bytes (large bucket)."""
        tree = load_sample_doc_tree()
        large = [
            p for p, doc in tree.files.items() if doc.size_bytes > 2000
        ]
        assert len(large) >= 4, (
            f"Expected >=4 large files (>2000 bytes), got {len(large)}: {large}"
        )

    def test_has_medium_files(self) -> None:
        """At least 10 files should be 500-2000 bytes (medium bucket)."""
        tree = load_sample_doc_tree()
        medium = [
            p for p, doc in tree.files.items()
            if 500 <= doc.size_bytes <= 2000
        ]
        assert len(medium) >= 10, (
            f"Expected >=10 medium files (500-2000 bytes), got {len(medium)}"
        )

    def test_large_files_contain_code_definitions(self) -> None:
        """Large files (>2000 bytes) should contain def or class definitions."""
        tree = load_sample_doc_tree()
        large_files = [
            (p, doc) for p, doc in tree.files.items() if doc.size_bytes > 2000
        ]
        has_defs = sum(
            1
            for _, doc in large_files
            if "def " in doc.content or "class " in doc.content
        )
        assert has_defs >= 3, (
            f"Expected >=3 large files with def/class, got {has_defs}"
        )
