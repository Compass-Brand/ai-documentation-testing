"""Tests for the doc transformation pipeline."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
from agent_index.models import DocFile, DocTree, TransformStep
from agent_index.transform import (
    TransformPipeline,
    TransformResult,
    TransformState,
    algorithmic_compress,
    llm_compress,
    llm_restructure,
    llm_tagged,
    load_state,
    passthrough,
    save_state,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_docfile(
    rel_path: str = "test.md",
    content: str = "# Hello\n\nWorld\n",
    *,
    tier: str = "",
    section: str = "",
) -> DocFile:
    """Create a minimal DocFile for testing."""
    encoded = content.encode("utf-8")
    return DocFile(
        rel_path=rel_path,
        content=content,
        size_bytes=len(encoded),
        tier=tier,
        section=section,
        content_hash=hashlib.sha256(encoded).hexdigest(),
    )


def _make_doctree(files: dict[str, DocFile] | None = None) -> DocTree:
    """Create a minimal DocTree for testing."""
    return DocTree(
        files=files or {},
        scanned_at=datetime.now(UTC),
        source="/tmp/test",
    )


# ===================================================================
# Strategy function tests
# ===================================================================


class TestPassthrough:
    """Tests for the passthrough strategy."""

    def test_returns_content_unchanged(self) -> None:
        """passthrough returns exactly the same string it receives."""
        content = "# Title\n\nSome content with   spaces\n"
        assert passthrough(content) == content

    def test_handles_empty_string(self) -> None:
        """passthrough works on an empty string."""
        assert passthrough("") == ""


class TestAlgorithmicCompress:
    """Tests for the algorithmic_compress strategy."""

    def test_removes_consecutive_blank_lines(self) -> None:
        """Consecutive blank lines are collapsed to a single blank line."""
        content = "Line 1\n\n\n\nLine 2"
        result = algorithmic_compress(content)
        assert result == "Line 1\n\nLine 2"

    def test_removes_html_comments(self) -> None:
        """HTML comments are stripped from the content."""
        content = "Before <!-- comment --> After"
        result = algorithmic_compress(content)
        assert "<!--" not in result
        assert "Before" in result
        assert "After" in result

    def test_removes_multiline_html_comments(self) -> None:
        """Multiline HTML comments are stripped."""
        content = "Before\n<!-- multi\nline\ncomment -->\nAfter"
        result = algorithmic_compress(content)
        assert "<!--" not in result
        assert "Before" in result
        assert "After" in result

    def test_normalizes_headings(self) -> None:
        """Markdown headings get a space after the # characters."""
        content = "#Title\n##Subtitle\n###Deep"
        result = algorithmic_compress(content)
        assert "# Title" in result
        assert "## Subtitle" in result
        assert "### Deep" in result

    def test_leaves_correct_headings_alone(self) -> None:
        """Headings that already have a space are unchanged."""
        content = "# Title\n## Subtitle"
        result = algorithmic_compress(content)
        assert "# Title" in result
        assert "## Subtitle" in result

    def test_removes_trailing_whitespace(self) -> None:
        """Trailing spaces/tabs on lines are removed."""
        content = "Line 1   \nLine 2\t\t\nLine 3"
        result = algorithmic_compress(content)
        lines = result.split("\n")
        for line in lines:
            assert line == line.rstrip(), f"Trailing whitespace found: {line!r}"

    def test_strips_leading_trailing_file_whitespace(self) -> None:
        """Leading and trailing whitespace of the entire file is stripped."""
        content = "\n\n  # Title\n\nBody\n\n  "
        result = algorithmic_compress(content)
        assert not result.startswith("\n")
        assert not result.startswith(" ")
        assert not result.endswith("\n")
        assert not result.endswith(" ")


class TestLlmPlaceholders:
    """Tests for LLM placeholder strategies."""

    def test_llm_compress_returns_non_empty(self) -> None:
        """llm_compress returns non-empty content containing the original."""
        content = "# Some doc\n\nBody text"
        result = llm_compress(content)
        assert len(result) > 0
        assert content in result

    def test_llm_compress_includes_model(self) -> None:
        """llm_compress includes the model name in its placeholder comment."""
        result = llm_compress("test", model="gpt-4o")
        assert "gpt-4o" in result

    def test_llm_restructure_returns_non_empty(self) -> None:
        """llm_restructure returns non-empty content containing the original."""
        content = "# Some doc\n\nBody text"
        result = llm_restructure(content)
        assert len(result) > 0
        assert content in result

    def test_llm_tagged_returns_non_empty(self) -> None:
        """llm_tagged returns non-empty content containing the original."""
        content = "# Some doc\n\nBody text"
        result = llm_tagged(content)
        assert len(result) > 0
        assert content in result


# ===================================================================
# TransformResult tests
# ===================================================================


class TestTransformResult:
    """Tests for the TransformResult dataclass."""

    def test_fields_present(self) -> None:
        """TransformResult stores all expected fields."""
        result = TransformResult(
            file_path="docs/readme.md",
            original_content="original",
            transformed_content="transformed",
            strategy_applied="passthrough",
            success=True,
            error=None,
        )
        assert result.file_path == "docs/readme.md"
        assert result.original_content == "original"
        assert result.transformed_content == "transformed"
        assert result.strategy_applied == "passthrough"
        assert result.success is True
        assert result.error is None

    def test_error_field_defaults_to_none(self) -> None:
        """TransformResult.error defaults to None."""
        result = TransformResult(
            file_path="f.md",
            original_content="a",
            transformed_content="b",
            strategy_applied="passthrough",
            success=True,
        )
        assert result.error is None

    def test_error_field_can_hold_message(self) -> None:
        """TransformResult.error can store an error message."""
        result = TransformResult(
            file_path="f.md",
            original_content="a",
            transformed_content="a",
            strategy_applied="passthrough(fallback)",
            success=True,
            error="LLM call failed",
        )
        assert result.error == "LLM call failed"


# ===================================================================
# TransformPipeline tests
# ===================================================================


class TestTransformPipelineSingleStep:
    """Tests for TransformPipeline with a single step."""

    def test_passthrough_step_returns_same_content(self) -> None:
        """Pipeline with a single passthrough step returns content unchanged."""
        doc = _make_docfile(content="# Hello\n\nWorld\n")
        pipeline = TransformPipeline(steps=[TransformStep(type="passthrough")])

        result = pipeline.transform_file(doc)

        assert result.transformed_content == doc.content
        assert result.success is True
        assert "passthrough" in result.strategy_applied

    def test_algorithmic_step_modifies_content(self) -> None:
        """Pipeline with an algorithmic step transforms the content."""
        doc = _make_docfile(content="#Title\n\n\n\nBody   \n")
        pipeline = TransformPipeline(steps=[TransformStep(type="algorithmic")])

        result = pipeline.transform_file(doc)

        assert result.transformed_content != doc.content
        assert "# Title" in result.transformed_content
        assert result.success is True


class TestTransformPipelineMultipleSteps:
    """Tests for TransformPipeline with multiple steps."""

    def test_passthrough_then_algorithmic(self) -> None:
        """Steps execute sequentially: passthrough then algorithmic."""
        doc = _make_docfile(content="#Title\n\n\n\nBody   \n")
        pipeline = TransformPipeline(
            steps=[
                TransformStep(type="passthrough"),
                TransformStep(type="algorithmic"),
            ]
        )

        result = pipeline.transform_file(doc)

        # The algorithmic step should have cleaned up the content
        assert "# Title" in result.transformed_content
        assert result.success is True
        assert "passthrough" in result.strategy_applied
        assert "algorithmic" in result.strategy_applied

    def test_algorithmic_then_passthrough_preserves_algorithmic_changes(self) -> None:
        """Algorithmic changes are preserved through a subsequent passthrough."""
        doc = _make_docfile(content="#Title\n\n\n\nBody   \n")
        pipeline = TransformPipeline(
            steps=[
                TransformStep(type="algorithmic"),
                TransformStep(type="passthrough"),
            ]
        )

        result = pipeline.transform_file(doc)

        assert "# Title" in result.transformed_content
        assert result.success is True


class TestTransformPipelineErrorHandling:
    """Tests for pipeline error handling and fallback."""

    def test_fallback_to_passthrough_on_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Pipeline falls back to passthrough when a strategy raises."""
        from agent_index import transform as transform_mod

        def _bad_strategy(content: str) -> str:
            raise RuntimeError("Simulated failure")

        monkeypatch.setattr(
            transform_mod,
            "_STRATEGY_MAP",
            {**transform_mod._STRATEGY_MAP, "algorithmic": _bad_strategy},
        )
        # Also need to patch _resolve_strategy to use the patched map
        original_resolve = transform_mod._resolve_strategy

        def _patched_resolve(step: TransformStep) -> tuple[object, str]:
            if step.type == "algorithmic":
                return _bad_strategy, "algorithmic"
            return original_resolve(step)

        monkeypatch.setattr(transform_mod, "_resolve_strategy", _patched_resolve)

        doc = _make_docfile(content="# Keep Me\n")
        pipeline = TransformPipeline(steps=[TransformStep(type="algorithmic")])

        result = pipeline.transform_file(doc)

        # Content should be unchanged (passthrough fallback)
        assert result.transformed_content == "# Keep Me\n"
        assert result.success is True
        assert "fallback" in result.strategy_applied


# ===================================================================
# Tree-level transform tests
# ===================================================================


class TestTransformTree:
    """Tests for TransformPipeline.transform_tree."""

    def test_processes_all_files(self) -> None:
        """transform_tree processes every file in the DocTree."""
        files = {
            "a.md": _make_docfile("a.md", "#A\n"),
            "b.md": _make_docfile("b.md", "#B\n"),
            "c.md": _make_docfile("c.md", "#C\n"),
        }
        tree = _make_doctree(files)
        pipeline = TransformPipeline(steps=[TransformStep(type="algorithmic")])

        new_tree, state = pipeline.transform_tree(tree)

        assert len(new_tree.files) == 3
        for rel_path in ("a.md", "b.md", "c.md"):
            assert rel_path in new_tree.files
            # Each heading should have been normalized
            assert "# " in new_tree.files[rel_path].content

    def test_empty_doctree(self) -> None:
        """transform_tree handles an empty DocTree gracefully."""
        tree = _make_doctree({})
        pipeline = TransformPipeline(steps=[TransformStep(type="passthrough")])

        new_tree, state = pipeline.transform_tree(tree)

        assert len(new_tree.files) == 0
        assert state.last_run is not None

    def test_state_tracks_file_hashes(self) -> None:
        """After transform, state.file_hashes contains entries for each file."""
        files = {
            "readme.md": _make_docfile("readme.md", "# Readme\n"),
        }
        tree = _make_doctree(files)
        pipeline = TransformPipeline(steps=[TransformStep(type="passthrough")])

        _, state = pipeline.transform_tree(tree)

        assert "readme.md" in state.file_hashes
        # Hash should match the original content hash (source detection)
        assert state.file_hashes["readme.md"] == files["readme.md"].content_hash


class TestIncrementalTransform:
    """Tests for incremental transform behavior (skipping unchanged files)."""

    def test_skips_unchanged_files(self) -> None:
        """Files whose hash matches state are skipped (content unchanged)."""
        doc = _make_docfile("unchanged.md", "# Stable\n")
        tree = _make_doctree({"unchanged.md": doc})

        # Simulate prior state where this file was already processed
        prior_state = TransformState(
            file_hashes={"unchanged.md": doc.content_hash},
        )

        pipeline = TransformPipeline(steps=[TransformStep(type="algorithmic")])
        new_tree, _ = pipeline.transform_tree(tree, state=prior_state)

        # Content should be the same as original (skipped)
        assert new_tree.files["unchanged.md"].content == doc.content

    def test_processes_changed_files(self) -> None:
        """Files whose hash differs from state are re-processed."""
        doc = _make_docfile("changed.md", "#Changed\n")
        tree = _make_doctree({"changed.md": doc})

        # Prior state has a different hash
        prior_state = TransformState(
            file_hashes={"changed.md": "old-hash-that-does-not-match"},
        )

        pipeline = TransformPipeline(steps=[TransformStep(type="algorithmic")])
        new_tree, state = pipeline.transform_tree(tree, state=prior_state)

        # Content should be transformed (heading normalized)
        assert "# Changed" in new_tree.files["changed.md"].content
        # State should be updated with current source hash
        assert state.file_hashes["changed.md"] == doc.content_hash

    def test_processes_new_files(self) -> None:
        """Files not in state are treated as new and processed."""
        doc = _make_docfile("new.md", "#New File\n")
        tree = _make_doctree({"new.md": doc})

        prior_state = TransformState(file_hashes={})
        pipeline = TransformPipeline(steps=[TransformStep(type="algorithmic")])
        new_tree, state = pipeline.transform_tree(tree, state=prior_state)

        assert "# New File" in new_tree.files["new.md"].content
        assert "new.md" in state.file_hashes


# ===================================================================
# State management tests
# ===================================================================


class TestStatePersistence:
    """Tests for save_state and load_state."""

    def test_roundtrip(self, tmp_path: Path) -> None:
        """save_state then load_state returns equivalent state."""
        state = TransformState(
            file_hashes={"a.md": "abc123", "b.md": "def456"},
            last_run=datetime(2025, 1, 15, 12, 0, 0, tzinfo=UTC),
            transform_config=[{"type": "passthrough", "strategy": "default", "model": None}],
        )
        state_file = tmp_path / ".agent-index-state.json"

        save_state(state, state_file)
        loaded = load_state(state_file)

        assert loaded is not None
        assert loaded.file_hashes == state.file_hashes
        assert loaded.last_run == state.last_run
        assert loaded.transform_config == state.transform_config

    def test_load_state_missing_file(self, tmp_path: Path) -> None:
        """load_state returns None when the file does not exist."""
        result = load_state(tmp_path / "nonexistent.json")
        assert result is None

    def test_load_state_corrupt_file(self, tmp_path: Path) -> None:
        """load_state returns None for a corrupt JSON file."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json {{{", encoding="utf-8")

        result = load_state(bad_file)
        assert result is None

    def test_save_state_creates_parent_dirs(self, tmp_path: Path) -> None:
        """save_state creates parent directories if they don't exist."""
        state = TransformState()
        nested = tmp_path / "deep" / "nested" / "state.json"

        save_state(state, nested)

        assert nested.exists()
        loaded = load_state(nested)
        assert loaded is not None
