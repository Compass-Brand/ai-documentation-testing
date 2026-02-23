"""Variant registry with auto-discovery support.

Provides functions to register, discover, and query ``IndexVariant``
subclasses.  ``load_all()`` walks the ``variants`` package with ``pkgutil``
so that every module in the package is imported (triggering any
``@register_variant`` decorators or explicit ``register_variant()`` calls).
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_evals.variants.base import IndexVariant

# Internal storage: maps variant class to its singleton instance.
_registry: dict[type[IndexVariant], IndexVariant] = {}


def register_variant(variant_cls: type[IndexVariant]) -> type[IndexVariant]:
    """Register a variant class with the global registry.

    Can be used as a decorator or called directly::

        @register_variant
        class MyVariant(IndexVariant):
            ...

        # -- or --
        register_variant(MyVariant)

    Registering the same class more than once is idempotent.

    Args:
        variant_cls: A concrete ``IndexVariant`` subclass to register.

    Returns:
        The same class, unmodified (enables decorator usage).
    """
    if variant_cls not in _registry:
        _registry[variant_cls] = variant_cls()
    return variant_cls


def get_all_variants() -> list[IndexVariant]:
    """Return every registered variant instance.

    Returns:
        List of all registered ``IndexVariant`` instances.
    """
    return list(_registry.values())


def get_variants_for_axis(axis: int) -> list[IndexVariant]:
    """Return registered variants belonging to the given evaluation axis.

    Args:
        axis: The evaluation axis number (1-10) to filter by.

    Returns:
        List of ``IndexVariant`` instances whose metadata axis matches.
    """
    return [v for v in _registry.values() if v.metadata().axis == axis]


def clear_registry() -> None:
    """Remove all registered variants.

    Useful for resetting state between evaluation runs or in tests.
    """
    _registry.clear()


def load_all() -> None:
    """Auto-discover and import all modules in the variants package.

    This triggers module-level ``register_variant`` calls so that every
    variant defined in the package is available via the registry queries.

    If modules were already imported (e.g. after ``clear_registry()``),
    the import is a no-op and decorators don't re-fire.  In that case
    we scan for concrete ``IndexVariant`` subclasses that are missing
    from the registry and register them directly.
    """
    import agent_evals.variants as variants_pkg

    package_path = variants_pkg.__path__
    for module_info in pkgutil.iter_modules(package_path):
        importlib.import_module(f"agent_evals.variants.{module_info.name}")

    # Re-register concrete subclasses missed when modules were already
    # imported (clear_registry + load_all pattern).  Only include classes
    # defined in the variants package to exclude test stubs.
    from agent_evals.variants.base import IndexVariant

    for subclass in IndexVariant.__subclasses__():
        if (
            subclass not in _registry
            and subclass.__module__.startswith("agent_evals.variants.")
        ):
            try:
                _registry[subclass] = subclass()
            except TypeError:
                pass  # Skip classes requiring constructor args
