"""Tests for the dataset download/cache management."""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# DatasetCache tests
# ---------------------------------------------------------------------------


class TestDatasetCache:
    """Tests for DatasetCache directory management."""

    def test_cache_creates_base_dir(self, tmp_path: Path) -> None:
        """Cache initializes its base directory if missing."""
        from agent_evals.datasets.cache import DatasetCache

        cache_dir = tmp_path / "datasets"
        cache = DatasetCache(cache_dir=cache_dir)
        assert cache_dir.is_dir()

    def test_task_dir_returns_correct_path(self, tmp_path: Path) -> None:
        """task_dir returns {cache_dir}/{name}/tasks/."""
        from agent_evals.datasets.cache import DatasetCache

        cache = DatasetCache(cache_dir=tmp_path)
        result = cache.task_dir("repliqa")
        assert result == tmp_path / "repliqa" / "tasks"

    def test_task_dir_creates_directory(self, tmp_path: Path) -> None:
        """task_dir creates the directory if it doesn't exist."""
        from agent_evals.datasets.cache import DatasetCache

        cache = DatasetCache(cache_dir=tmp_path)
        result = cache.task_dir("repliqa")
        assert result.is_dir()

    def test_doc_tree_path_returns_correct_path(self, tmp_path: Path) -> None:
        """doc_tree_path returns {cache_dir}/{name}/doc_tree.json."""
        from agent_evals.datasets.cache import DatasetCache

        cache = DatasetCache(cache_dir=tmp_path)
        result = cache.doc_tree_path("repliqa")
        assert result == tmp_path / "repliqa" / "doc_tree.json"

    def test_is_prepared_false_initially(self, tmp_path: Path) -> None:
        """A fresh dataset is not prepared."""
        from agent_evals.datasets.cache import DatasetCache

        cache = DatasetCache(cache_dir=tmp_path)
        assert cache.is_prepared("repliqa") is False

    def test_mark_prepared_creates_marker(self, tmp_path: Path) -> None:
        """mark_prepared creates a .prepared marker file."""
        from agent_evals.datasets.cache import DatasetCache

        cache = DatasetCache(cache_dir=tmp_path)
        cache.mark_prepared("repliqa", task_count=50)
        assert cache.is_prepared("repliqa") is True
        marker = tmp_path / "repliqa" / ".prepared"
        assert marker.exists()
        content = marker.read_text()
        assert "50" in content

    def test_clear_specific_dataset(self, tmp_path: Path) -> None:
        """clear(name) removes that dataset's directory."""
        from agent_evals.datasets.cache import DatasetCache

        cache = DatasetCache(cache_dir=tmp_path)
        cache.mark_prepared("repliqa", task_count=10)
        assert cache.is_prepared("repliqa")

        cache.clear("repliqa")
        assert not cache.is_prepared("repliqa")
        assert not (tmp_path / "repliqa").exists()

    def test_clear_all_datasets(self, tmp_path: Path) -> None:
        """clear() without name removes all dataset directories."""
        from agent_evals.datasets.cache import DatasetCache

        cache = DatasetCache(cache_dir=tmp_path)
        cache.mark_prepared("repliqa", task_count=10)
        cache.mark_prepared("techqa", task_count=20)

        cache.clear()
        assert not cache.is_prepared("repliqa")
        assert not cache.is_prepared("techqa")

    def test_default_cache_dir(self) -> None:
        """Default cache dir is ~/.agent-evals/datasets/."""
        from agent_evals.datasets.cache import DatasetCache

        cache = DatasetCache()
        expected = Path.home() / ".agent-evals" / "datasets"
        assert cache.cache_dir == expected
