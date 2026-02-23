"""Download and cache management for public datasets.

Manages ``~/.agent-evals/datasets/`` directory structure:

    {cache_dir}/
        {dataset_name}/
            .prepared           # marker with task count + timestamp
            doc_tree.json       # serialized DocTree
            tasks/
                {task_id}.yaml  # individual task YAML files
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path


class DatasetCache:
    """Manages dataset download cache at ``~/.agent-evals/datasets/``."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        if cache_dir is None:
            cache_dir = Path.home() / ".agent-evals" / "datasets"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def task_dir(self, dataset_name: str) -> Path:
        """Return (and create) the task YAML directory for a dataset."""
        d = self.cache_dir / dataset_name / "tasks"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def doc_tree_path(self, dataset_name: str) -> Path:
        """Return the path for the cached DocTree JSON."""
        return self.cache_dir / dataset_name / "doc_tree.json"

    def is_prepared(self, dataset_name: str) -> bool:
        """Check if a dataset has been prepared (downloaded + converted)."""
        marker = self.cache_dir / dataset_name / ".prepared"
        return marker.exists()

    def mark_prepared(self, dataset_name: str, task_count: int) -> None:
        """Mark a dataset as prepared with task count and timestamp."""
        ds_dir = self.cache_dir / dataset_name
        ds_dir.mkdir(parents=True, exist_ok=True)
        marker = ds_dir / ".prepared"
        now = datetime.now(tz=UTC).isoformat()
        marker.write_text(
            f"task_count={task_count}\nprepared_at={now}\n",
            encoding="utf-8",
        )

    def clear(self, dataset_name: str | None = None) -> None:
        """Remove cached data for one or all datasets."""
        if dataset_name is not None:
            ds_dir = self.cache_dir / dataset_name
            if ds_dir.exists():
                shutil.rmtree(ds_dir)
        else:
            for child in self.cache_dir.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
