"""Source routing for dataset-backed evaluation runs.

Provides load_from_source() for single-dataset runs and
MixedSourceLoader for interleaving tasks from multiple adapters.
"""

from __future__ import annotations

from datetime import UTC
from itertools import zip_longest
from pathlib import Path
from typing import TYPE_CHECKING

from agent_evals.datasets import get_adapter
from agent_evals.datasets.cache import DatasetCache
from agent_evals.tasks.loader import load_tasks

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.tasks.base import EvalTask

DEFAULT_CACHE_DIR = Path.home() / ".agent-evals" / "datasets"


def load_from_source(
    source: str,
    limit: int | None = None,
    cache_dir: Path | None = None,
) -> tuple[list[EvalTask], DocTree, str] | None:
    """Load tasks and DocTree from a dataset source.

    Returns None for 'gold_standard' (caller uses built-in tasks).
    Returns (tasks, doc_tree, source_name) for dataset sources.
    Raises KeyError for unknown sources.
    """
    if source == "gold_standard":
        return None

    adapter = get_adapter(source)  # Raises KeyError if unknown
    cache = DatasetCache(cache_dir or DEFAULT_CACHE_DIR)

    if not cache.is_prepared(source):
        task_dir = cache.task_dir(source)
        task_dir.mkdir(parents=True, exist_ok=True)
        count = adapter.convert_tasks(task_dir, limit=limit)
        cache.mark_prepared(source, task_count=count)

    tasks = load_tasks(cache.task_dir(source))
    doc_tree = adapter.build_doc_tree(limit=limit)

    return tasks, doc_tree, source


def parse_mixed_source_args(
    source: str,
    datasets_csv: str,
) -> tuple[str, list[str]]:
    """Parse --source mixed --datasets repliqa,ibm_techqa.

    Returns (source, dataset_names).
    Raises ValueError if fewer than 2 datasets are provided.
    """
    names = [n.strip() for n in datasets_csv.split(",") if n.strip()]
    if len(names) < 2:
        raise ValueError(
            f"--source mixed requires at least 2 datasets, got {len(names)}"
        )
    return source, names


class MixedSourceLoader:
    """Loads and merges tasks + DocTrees from multiple dataset adapters.

    Used by --source mixed --datasets repliqa,ibm_techqa to interleave
    tasks from several adapters in a single Taguchi screening.
    """

    def __init__(
        self,
        adapter_names: list[str],
        limit: int | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self._adapter_names = adapter_names
        self._limit = limit
        self._adapters = {name: get_adapter(name) for name in adapter_names}
        self._cache = DatasetCache(cache_dir or DEFAULT_CACHE_DIR)

    def build_merged_doc_tree(self) -> DocTree:
        """Merge DocTrees from all adapters, namespacing files.

        Each file is keyed as {adapter_name}/{original_rel_path} to
        avoid collisions between adapters.
        """
        from agent_index.models import DocTree as DocTreeModel

        merged_files = {}
        for name, adapter in self._adapters.items():
            tree = adapter.build_doc_tree(limit=self._limit)
            for rel_path, doc_file in tree.files.items():
                namespaced = f"{name}/{rel_path}"
                merged_files[namespaced] = doc_file

        return DocTreeModel(
            files=merged_files,
            scanned_at=_now_iso(),
            source=",".join(self._adapter_names),
            total_tokens=sum(f.size_bytes for f in merged_files.values()),
        )

    def load_interleaved_tasks(self) -> list[EvalTask]:
        """Load tasks from each adapter and interleave round-robin."""
        per_adapter_tasks: list[list] = []
        for name in self._adapter_names:
            adapter = self._adapters[name]
            if not self._cache.is_prepared(name):
                task_dir = self._cache.task_dir(name)
                task_dir.mkdir(parents=True, exist_ok=True)
                adapter.convert_tasks(task_dir, limit=self._limit)
                self._cache.mark_prepared(name, task_count=0)
            tasks = load_tasks(self._cache.task_dir(name))
            per_adapter_tasks.append(tasks)

        # Round-robin interleave
        interleaved = []
        for group in zip_longest(*per_adapter_tasks):
            for task in group:
                if task is not None:
                    interleaved.append(task)
        return interleaved


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now(UTC).isoformat()
