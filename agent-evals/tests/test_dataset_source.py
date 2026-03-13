"""Tests for dataset source routing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agent_evals.datasets.source import load_from_source


class TestLoadFromSource:
    def test_gold_standard_returns_none(self):
        """source='gold_standard' returns None, signaling built-in tasks."""
        result = load_from_source("gold_standard")
        assert result is None

    def test_unknown_source_raises_key_error(self):
        with pytest.raises(KeyError, match="unknown_dataset"):
            load_from_source("unknown_dataset")

    def test_valid_source_returns_tasks_and_tree(self):
        """A registered adapter returns (tasks, doc_tree, source_name)."""
        mock_adapter = MagicMock()
        mock_adapter.name.return_value = "test_ds"
        mock_adapter.task_type.return_value = "fact_extraction"

        mock_tree = MagicMock()
        mock_adapter.build_doc_tree.return_value = mock_tree

        mock_task = MagicMock()
        mock_task.definition.task_id = "fact_extraction_001"

        with patch(
            "agent_evals.datasets.source.get_adapter",
            return_value=mock_adapter,
        ), patch(
            "agent_evals.datasets.source.load_tasks",
            return_value=[mock_task],
        ), patch(
            "agent_evals.datasets.source.DatasetCache",
        ) as mock_cache_cls:
            mock_cache = mock_cache_cls.return_value
            mock_cache.is_prepared.return_value = True
            mock_cache.task_dir.return_value = Path("/tmp/fake")
            mock_cache.doc_tree_path.return_value = Path("/tmp/fake/tree.json")

            tasks, tree, name = load_from_source("test_ds")
            assert name == "test_ds"
            assert len(tasks) > 0
            assert tree is not None

    def test_unprepared_source_triggers_prepare(self):
        """If cache miss, adapter.convert_tasks() is called first."""
        mock_adapter = MagicMock()
        mock_adapter.name.return_value = "test_ds"
        mock_adapter.convert_tasks.return_value = 5
        mock_adapter.build_doc_tree.return_value = MagicMock()

        with patch(
            "agent_evals.datasets.source.get_adapter",
            return_value=mock_adapter,
        ), patch(
            "agent_evals.datasets.source.load_tasks",
            return_value=[MagicMock()],
        ), patch(
            "agent_evals.datasets.source.DatasetCache",
        ) as mock_cache_cls:
            mock_cache = mock_cache_cls.return_value
            mock_cache.is_prepared.return_value = False
            mock_cache.task_dir.return_value = Path("/tmp/fake")
            mock_cache.doc_tree_path.return_value = Path("/tmp/fake/tree.json")

            load_from_source("test_ds")
            mock_adapter.convert_tasks.assert_called_once()


class TestMixedSourceLoader:
    def test_mixed_source_merges_doc_trees(self):
        """MixedSourceLoader merges DocTrees from multiple adapters,
        namespacing files as {adapter_name}/{rel_path}."""
        from agent_evals.datasets.source import MixedSourceLoader
        from agent_index.models import DocFile, DocTree

        tree_a = DocTree(
            files={
                "docs/a.md": DocFile(
                    rel_path="docs/a.md",
                    content="# A",
                    size_bytes=3,
                    section="docs",
                    tier="required",
                )
            },
            scanned_at="2026-03-06T00:00:00Z",
            source="adapter_a",
            total_tokens=5,
        )
        tree_b = DocTree(
            files={
                "docs/b.md": DocFile(
                    rel_path="docs/b.md",
                    content="# B",
                    size_bytes=3,
                    section="docs",
                    tier="required",
                )
            },
            scanned_at="2026-03-06T00:00:00Z",
            source="adapter_b",
            total_tokens=5,
        )

        mock_adapter_a = MagicMock()
        mock_adapter_a.name.return_value = "adapter_a"
        mock_adapter_a.build_doc_tree.return_value = tree_a
        mock_adapter_a.convert_tasks.return_value = 1

        mock_adapter_b = MagicMock()
        mock_adapter_b.name.return_value = "adapter_b"
        mock_adapter_b.build_doc_tree.return_value = tree_b
        mock_adapter_b.convert_tasks.return_value = 1

        with patch(
            "agent_evals.datasets.source.get_adapter",
            side_effect=lambda n: {
                "adapter_a": mock_adapter_a,
                "adapter_b": mock_adapter_b,
            }[n],
        ), patch("agent_evals.datasets.source.DatasetCache"), patch(
            "agent_evals.datasets.source.load_tasks",
            return_value=[MagicMock()],
        ):
            loader = MixedSourceLoader(["adapter_a", "adapter_b"])
            merged_tree = loader.build_merged_doc_tree()
            assert "adapter_a/docs/a.md" in merged_tree.files
            assert "adapter_b/docs/b.md" in merged_tree.files

    def test_mixed_source_interleaves_tasks(self):
        """Tasks from multiple adapters are interleaved round-robin."""
        from agent_evals.datasets.source import MixedSourceLoader

        task_a1 = MagicMock()
        task_a1.definition.task_id = "fact_extraction_001"
        task_a2 = MagicMock()
        task_a2.definition.task_id = "fact_extraction_002"
        task_b1 = MagicMock()
        task_b1.definition.task_id = "negative_001"
        task_b2 = MagicMock()
        task_b2.definition.task_id = "negative_002"

        mock_adapter_a = MagicMock()
        mock_adapter_a.name.return_value = "repliqa"
        mock_adapter_a.build_doc_tree.return_value = MagicMock()
        mock_adapter_a.convert_tasks.return_value = 2

        mock_adapter_b = MagicMock()
        mock_adapter_b.name.return_value = "ibm_techqa"
        mock_adapter_b.build_doc_tree.return_value = MagicMock()
        mock_adapter_b.convert_tasks.return_value = 2

        with patch(
            "agent_evals.datasets.source.get_adapter",
            side_effect=lambda n: {
                "repliqa": mock_adapter_a,
                "ibm_techqa": mock_adapter_b,
            }[n],
        ), patch(
            "agent_evals.datasets.source.DatasetCache",
        ) as mock_cache_cls, patch(
            "agent_evals.datasets.source.load_tasks",
            side_effect=[[task_a1, task_a2], [task_b1, task_b2]],
        ):
            mock_cache = mock_cache_cls.return_value
            mock_cache.is_prepared.return_value = True
            mock_cache.task_dir.return_value = Path("/tmp/fake")

            loader = MixedSourceLoader(["repliqa", "ibm_techqa"])
            tasks = loader.load_interleaved_tasks()
            ids = [t.definition.task_id for t in tasks]
            # Round-robin: a1, b1, a2, b2
            assert ids == [
                "fact_extraction_001",
                "negative_001",
                "fact_extraction_002",
                "negative_002",
            ]

    def test_mixed_source_cli_flag(self):
        """--source mixed --datasets repliqa,ibm_techqa parses correctly."""
        from agent_evals.datasets.source import parse_mixed_source_args

        source, datasets = parse_mixed_source_args("mixed", "repliqa,ibm_techqa")
        assert source == "mixed"
        assert datasets == ["repliqa", "ibm_techqa"]

    def test_mixed_source_cli_flag_single_dataset_raises(self):
        """--source mixed with a single dataset raises ValueError."""
        from agent_evals.datasets.source import parse_mixed_source_args

        with pytest.raises(ValueError, match="at least 2"):
            parse_mixed_source_args("mixed", "repliqa")

    def test_mixed_source_handles_imbalanced_adapters(self):
        """When adapters produce different task counts, round-robin
        continues until all adapters are exhausted."""
        from agent_evals.datasets.source import MixedSourceLoader

        task_a = [MagicMock() for _ in range(3)]
        for i, t in enumerate(task_a):
            t.definition.task_id = f"fact_{i:03d}"

        task_b = [MagicMock() for _ in range(7)]
        for i, t in enumerate(task_b):
            t.definition.task_id = f"retrieval_{i:03d}"

        with patch(
            "agent_evals.datasets.source.get_adapter",
        ), patch(
            "agent_evals.datasets.source.DatasetCache",
        ) as mock_cache_cls, patch(
            "agent_evals.datasets.source.load_tasks",
            side_effect=[task_a, task_b],
        ):
            mock_cache = mock_cache_cls.return_value
            mock_cache.is_prepared.return_value = True
            mock_cache.task_dir.return_value = Path("/tmp/fake")

            loader = MixedSourceLoader(["ds_a", "ds_b"])
            tasks = loader.load_interleaved_tasks()

            # All 10 tasks present (3 + 7), none dropped
            assert len(tasks) == 10

            # First 6 are interleaved (3 pairs), then 4 solo from ds_b
            ids = [t.definition.task_id for t in tasks]
            # Round-robin: a0, b0, a1, b1, a2, b2, b3, b4, b5, b6
            assert ids[0] == "fact_000"
            assert ids[1] == "retrieval_000"
            assert ids[6] == "retrieval_003"
