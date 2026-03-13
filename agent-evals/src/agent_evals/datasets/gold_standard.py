"""Gold standard dataset manager.

The gold standard is the union of all 9 HF dataset adapters.
Each adapter maps to one task type, providing battle-tested
evaluation criteria from established benchmarks.
"""

from __future__ import annotations

import logging
from pathlib import Path

from agent_evals.datasets import get_adapter, load_all
from agent_evals.datasets.cache import DatasetCache

logger = logging.getLogger(__name__)

# All non-synthetic HF adapters required for gold standard
_REQUIRED_ADAPTERS: tuple[str, ...] = (
    "ambigqa",
    "bigcodebench",
    "code-rag-bench",
    "ds1000",
    "ibm-techqa",
    "multihop-rag",
    "repliqa",
    "swe-bench",
    "wikicontradict",
)

# Per-adapter default limits (ibm-techqa needs capping)
_DEFAULT_LIMITS: dict[str, int] = {
    "ibm-techqa": 50,
}

# General default when no per-adapter limit specified
_GENERAL_DEFAULT_LIMIT: int = 100

# Synthetic adapters and their HF source adapters
_SYNTHETIC_SOURCES: tuple[tuple[str, str], ...] = (
    ("ibm-techqa", "synthetic-efficiency"),
    ("ibm-techqa", "perturbation"),
)

# All adapters: 9 HF + 2 synthetic
_ALL_ADAPTERS: tuple[str, ...] = _REQUIRED_ADAPTERS + tuple(
    name for _, name in _SYNTHETIC_SOURCES
)


class GoldStandardManager:
    """Manages HF dataset preparation and loading as gold standard."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        limits: dict[str, int] | None = None,
    ) -> None:
        self._cache = DatasetCache(cache_dir)
        self._limits = {**_DEFAULT_LIMITS, **(limits or {})}

    def required_adapters(self) -> tuple[str, ...]:
        """Return names of all required HF adapters (9 total)."""
        return _REQUIRED_ADAPTERS

    def all_adapters(self) -> tuple[str, ...]:
        """Return names of all adapters including synthetics (11 total)."""
        return _ALL_ADAPTERS

    def is_prepared(self) -> bool:
        """True if all required adapters have been prepared."""
        return len(self.missing_adapters()) == 0

    def missing_adapters(self) -> list[str]:
        """Return names of adapters that haven't been prepared."""
        return [
            name
            for name in _REQUIRED_ADAPTERS
            if not self._cache.is_prepared(name)
        ]

    def prepare_all(
        self,
        default_limit: int | None = None,
    ) -> dict[str, int]:
        """Prepare all required adapters. Returns {name: task_count}."""
        load_all()
        results: dict[str, int] = {}
        effective_default = default_limit if default_limit is not None else _GENERAL_DEFAULT_LIMIT

        for name in _REQUIRED_ADAPTERS:
            if self._cache.is_prepared(name):
                results[name] = 0  # already prepared
                continue

            try:
                adapter = get_adapter(name)
                limit = self._limits.get(name, effective_default)
                output_dir = self._cache.task_dir(name)
                count = adapter.convert_tasks(output_dir, limit=limit)

                doc_tree = adapter.build_doc_tree(limit=limit)
                dt_path = self._cache.doc_tree_path(name)
                dt_path.write_text(
                    doc_tree.model_dump_json(indent=2), encoding="utf-8",
                )

                self._cache.mark_prepared(name, task_count=count)
                results[name] = count
            except Exception as exc:
                logger.warning(
                    "Failed to prepare adapter '%s', skipping: %s",
                    name,
                    exc,
                )

        # Auto-generate synthetic tasks from prepared HF data
        results.update(self._generate_synthetic_tasks(effective_default))
        return results

    def _generate_synthetic_tasks(self, limit: int) -> dict[str, int]:
        """Generate synthetic adapter tasks from prepared HF data.

        Uses _SYNTHETIC_SOURCES mapping: each (source_adapter, target_adapter)
        pair generates target tasks from prepared source tasks.
        """
        load_all()
        results: dict[str, int] = {}
        for source_name, adapter_name in _SYNTHETIC_SOURCES:
            if not self._cache.is_prepared(source_name):
                continue
            try:
                source_dir = self._cache.task_dir(source_name)
                adapter = get_adapter(adapter_name)
                output_dir = self._cache.task_dir(adapter_name)
                count = adapter.convert_tasks(
                    output_dir, limit=limit, source_dir=source_dir,
                )

                doc_tree = adapter.build_doc_tree(limit=limit)
                dt_path = self._cache.doc_tree_path(adapter_name)
                dt_path.write_text(
                    doc_tree.model_dump_json(indent=2), encoding="utf-8",
                )

                self._cache.mark_prepared(adapter_name, task_count=count)
                results[adapter_name] = count
            except Exception as exc:
                logger.warning(
                    "Failed to generate synthetic adapter '%s', skipping: %s",
                    adapter_name,
                    exc,
                )
        return results

    def is_adapter_prepared(self, adapter_name: str) -> bool:
        """True if a specific adapter has been prepared."""
        return self._cache.is_prepared(adapter_name)

    def task_dir(self, adapter_name: str) -> Path:
        """Return the task YAML directory for a prepared adapter."""
        return self._cache.task_dir(adapter_name)

    def doc_tree_path(self, adapter_name: str) -> Path:
        """Return the doc_tree JSON path for a prepared adapter."""
        return self._cache.doc_tree_path(adapter_name)

    def limit_for(self, adapter_name: str) -> int:
        """Return the configured limit for an adapter."""
        return self._limits.get(adapter_name, _GENERAL_DEFAULT_LIMIT)
