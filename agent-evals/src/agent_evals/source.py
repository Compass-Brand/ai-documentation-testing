"""Source-aware loading of tasks and doc_tree.

Centralises the gold_standard vs dataset-cache routing used by both
the CLI and the dashboard RunManager.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent_evals.datasets.gold_standard import GoldStandardManager

logger = logging.getLogger(__name__)

DEFAULT_SOURCE = "gold_standard"

_GOLD_STANDARD_DIR = (
    Path(__file__).resolve().parent.parent.parent / "gold_standard_legacy"
)


class SourceNotPreparedError(Exception):
    """Raised when a dataset source has not been prepared."""


def load_tasks_for_source(source: str = DEFAULT_SOURCE) -> list[Any]:
    """Load evaluation tasks for the given *source*.

    Args:
        source: ``"gold_standard"`` (loads HF datasets, falls back to
            legacy), ``"legacy"`` (hand-crafted YAMLs), a dataset
            adapter name (e.g. ``"repliqa"``), or a comma-separated
            list of dataset names (e.g. ``"repliqa,ambigqa"``).

    Returns:
        List of loaded ``EvalTask`` objects.

    Raises:
        FileNotFoundError: gold_standard directory missing.
        SourceNotPreparedError: dataset not yet prepared.
    """
    from agent_evals.tasks.loader import load_tasks

    if source == "legacy":
        if not _GOLD_STANDARD_DIR.is_dir():
            raise FileNotFoundError(
                f"Legacy gold standard directory not found: {_GOLD_STANDARD_DIR}"
            )
        return load_tasks(_GOLD_STANDARD_DIR)

    if source == DEFAULT_SOURCE:
        from agent_evals.datasets.gold_standard import GoldStandardManager

        mgr = GoldStandardManager()
        if mgr.is_prepared():
            return _load_gold_standard_tasks(mgr)
        # Fall back to legacy when datasets not prepared
        missing = mgr.missing_adapters()
        logger.warning(
            "HF datasets not prepared (missing: %s). Falling back to legacy. "
            "Run: agent-evals --prepare-datasets all",
            ", ".join(missing),
        )
        if not _GOLD_STANDARD_DIR.is_dir():
            raise FileNotFoundError(
                f"Gold standard directory not found: {_GOLD_STANDARD_DIR}"
            )
        return load_tasks(_GOLD_STANDARD_DIR)

    names = [n.strip() for n in source.split(",")]

    from agent_evals.datasets import load_all as _load_all_datasets
    from agent_evals.datasets.cache import DatasetCache

    _load_all_datasets()
    cache = DatasetCache()

    all_tasks: list[Any] = []
    for name in names:
        if not cache.is_prepared(name):
            raise SourceNotPreparedError(
                f"Dataset '{name}' has not been prepared. "
                f"Run: agent-evals --prepare-datasets {name}"
            )
        all_tasks.extend(load_tasks(cache.task_dir(name)))

    return all_tasks


def load_doc_tree_for_source(source: str = DEFAULT_SOURCE) -> Any:
    """Load the doc_tree for the given *source*.

    For ``"gold_standard"`` loads merged HF dataset doc trees (or falls
    back to built-in sample).  For ``"legacy"`` returns the built-in
    sample doc tree.  For other sources reads the cached JSON doc tree.
    When *source* is a comma-separated list, doc trees are merged.

    Args:
        source: ``"gold_standard"``, ``"legacy"``, a dataset adapter
            name, or a comma-separated list of dataset names.

    Returns:
        A ``DocTree`` instance.
    """
    if source == "legacy":
        from agent_evals.fixtures import load_sample_doc_tree

        return load_sample_doc_tree()

    if source == DEFAULT_SOURCE:
        from agent_evals.datasets.gold_standard import GoldStandardManager

        mgr = GoldStandardManager()
        if mgr.is_prepared():
            return _load_gold_standard_doc_tree(mgr)
        # Fall back to legacy fixture
        from agent_evals.fixtures import load_sample_doc_tree

        return load_sample_doc_tree()

    from datetime import UTC, datetime

    from agent_evals.datasets import load_all as _load_all_datasets
    from agent_evals.datasets.cache import DatasetCache
    from agent_index.models import DocTree

    _load_all_datasets()
    cache = DatasetCache()

    names = [n.strip() for n in source.split(",")]

    if len(names) == 1:
        return DocTree.model_validate_json(
            cache.doc_tree_path(names[0]).read_text(encoding="utf-8")
        )

    merged_files: dict[str, Any] = {}
    total_tokens = 0
    for name in names:
        dt = DocTree.model_validate_json(
            cache.doc_tree_path(name).read_text(encoding="utf-8")
        )
        for rel_path, doc_file in dt.files.items():
            merged_files[f"{name}/{rel_path}"] = doc_file
        total_tokens += dt.total_tokens or 0

    return DocTree(
        files=merged_files,
        scanned_at=datetime.now(tz=UTC),
        source=",".join(names),
        total_tokens=total_tokens,
    )


def _load_gold_standard_tasks(mgr: GoldStandardManager) -> list[Any]:
    """Load tasks from all prepared adapters (9 HF + 2 synthetic)."""
    from agent_evals.tasks.loader import load_tasks

    all_tasks: list[Any] = []
    for name in mgr.all_adapters():
        if not mgr.is_adapter_prepared(name):
            continue
        all_tasks.extend(load_tasks(mgr.task_dir(name)))
    return all_tasks


def _load_gold_standard_doc_tree(mgr: GoldStandardManager) -> Any:
    """Merge DocTrees from all prepared adapters, namespacing files."""
    from datetime import UTC, datetime

    from agent_index.models import DocTree

    merged_files: dict[str, Any] = {}
    total_tokens = 0

    for name in mgr.all_adapters():
        if not mgr.is_adapter_prepared(name):
            continue
        dt_path = mgr.doc_tree_path(name)
        dt = DocTree.model_validate_json(
            dt_path.read_text(encoding="utf-8")
        )
        for rel_path, doc_file in dt.files.items():
            merged_files[f"{name}/{rel_path}"] = doc_file
        total_tokens += dt.total_tokens or 0

    return DocTree(
        files=merged_files,
        scanned_at=datetime.now(tz=UTC),
        source="gold_standard",
        total_tokens=total_tokens,
    )
