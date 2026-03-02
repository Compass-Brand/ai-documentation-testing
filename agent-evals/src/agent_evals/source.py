"""Source-aware loading of tasks and doc_tree.

Centralises the gold_standard vs dataset-cache routing used by both
the CLI and the dashboard RunManager.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_SOURCE = "gold_standard"

_GOLD_STANDARD_DIR = (
    Path(__file__).resolve().parent.parent.parent / "gold_standard"
)


class SourceNotPreparedError(Exception):
    """Raised when a dataset source has not been prepared."""


def load_tasks_for_source(source: str = DEFAULT_SOURCE) -> list[Any]:
    """Load evaluation tasks for the given *source*.

    Args:
        source: ``"gold_standard"`` for built-in fixtures, or a dataset
            adapter name (e.g. ``"repliqa"``).

    Returns:
        List of loaded ``EvalTask`` objects.

    Raises:
        FileNotFoundError: gold_standard directory missing.
        SourceNotPreparedError: dataset not yet prepared.
    """
    from agent_evals.tasks.loader import load_tasks

    if source == DEFAULT_SOURCE:
        if not _GOLD_STANDARD_DIR.is_dir():
            raise FileNotFoundError(
                f"Gold standard directory not found: {_GOLD_STANDARD_DIR}"
            )
        return load_tasks(_GOLD_STANDARD_DIR)

    from agent_evals.datasets import load_all as _load_all_datasets
    from agent_evals.datasets.cache import DatasetCache

    _load_all_datasets()
    cache = DatasetCache()
    if not cache.is_prepared(source):
        raise SourceNotPreparedError(
            f"Dataset \'{source}\' has not been prepared. "
            f"Run: agent-evals --prepare-datasets {source}"
        )
    return load_tasks(cache.task_dir(source))


def load_doc_tree_for_source(source: str = DEFAULT_SOURCE) -> Any:
    """Load the doc_tree for the given *source*.

    For ``"gold_standard"`` returns the built-in sample doc tree.
    For other sources reads the cached JSON doc tree.

    Args:
        source: ``"gold_standard"`` or a dataset adapter name.

    Returns:
        A ``DocTree`` instance.
    """
    if source == DEFAULT_SOURCE:
        from agent_evals.fixtures import load_sample_doc_tree

        return load_sample_doc_tree()

    from agent_evals.datasets import load_all as _load_all_datasets
    from agent_evals.datasets.cache import DatasetCache
    from agent_index.models import DocTree

    _load_all_datasets()
    cache = DatasetCache()
    return DocTree.model_validate_json(
        cache.doc_tree_path(source).read_text(encoding="utf-8")
    )
