"""Dataset adapter registry with auto-discovery.

Provides registration, lookup, and enumeration of dataset adapters.
Mirrors the variant registry pattern from ``agent_evals.variants.registry``.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_evals.datasets.base import DatasetAdapter

DATASET_REGISTRY: dict[str, type[DatasetAdapter]] = {}


def register_dataset(cls: type[DatasetAdapter]) -> type[DatasetAdapter]:
    """Register a dataset adapter class.

    Can be used as a decorator::

        @register_dataset
        class MyAdapter(DatasetAdapter):
            ...

    Args:
        cls: A concrete ``DatasetAdapter`` subclass.

    Returns:
        The same class, unmodified (enables decorator usage).
    """
    instance = cls()
    DATASET_REGISTRY[instance.name()] = cls
    return cls


def get_adapter(name: str) -> DatasetAdapter:
    """Return an instance of the named dataset adapter.

    Args:
        name: Dataset name as returned by adapter.name().

    Raises:
        KeyError: If no adapter with that name is registered.
    """
    if name not in DATASET_REGISTRY:
        msg = (
            f"No dataset adapter registered for '{name}'. "
            f"Available: {sorted(DATASET_REGISTRY.keys())}"
        )
        raise KeyError(msg)
    return DATASET_REGISTRY[name]()


def list_available() -> list[dict[str, str]]:
    """Return metadata for all registered dataset adapters."""
    result = []
    for name, cls in sorted(DATASET_REGISTRY.items()):
        adapter = cls()
        result.append({
            "name": adapter.name(),
            "hf_dataset_id": adapter.hf_dataset_id() or "",
            "task_type": adapter.task_type(),
            "domain": adapter.domain(),
            "license": adapter.license(),
            "contamination_risk": adapter.contamination_risk(),
        })
    return result


def load_all() -> None:
    """Auto-discover and import all adapter modules in this package."""
    import agent_evals.datasets as datasets_pkg

    for module_info in pkgutil.iter_modules(datasets_pkg.__path__):
        if not module_info.name.startswith("_"):
            importlib.import_module(f"agent_evals.datasets.{module_info.name}")
