"""Context strategy registry with auto-discovery support.

Mirrors the pattern from ``variants/registry.py`` -- uses pkgutil to
auto-import all modules in the context package, triggering registration.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_evals.context.base import ContextStrategy

_registry: dict[type[ContextStrategy], ContextStrategy] = {}


def register_strategy(strategy_cls: type[ContextStrategy]) -> type[ContextStrategy]:
    """Register a strategy class. Usable as a decorator."""
    if strategy_cls not in _registry:
        _registry[strategy_cls] = strategy_cls()
    return strategy_cls


def get_all_strategies() -> list[ContextStrategy]:
    """Return every registered strategy instance."""
    return list(_registry.values())


def get_strategy_by_name(name: str) -> ContextStrategy | None:
    """Return a registered strategy by its name, or None."""
    for strategy in _registry.values():
        if strategy.name() == name:
            return strategy
    return None


def create_strategy_by_name(name: str) -> ContextStrategy | None:
    """Create a **new** strategy instance by name.

    Unlike ``get_strategy_by_name`` (which returns the cached singleton),
    this always instantiates a fresh object so that callers do not share
    mutable state.  Used by strategy factories that need per-row isolation.
    """
    for cls, strategy in _registry.items():
        if strategy.name() == name:
            return cls()
    return None


def clear_registry() -> None:
    """Remove all registered strategies."""
    _registry.clear()


def load_all() -> None:
    """Auto-discover and import all modules in the context package."""
    import agent_evals.context as context_pkg

    for module_info in pkgutil.iter_modules(context_pkg.__path__):
        importlib.import_module(f"agent_evals.context.{module_info.name}")

    # Re-register concrete subclasses missed when modules were already imported.
    from agent_evals.context.base import ContextStrategy

    for subclass in ContextStrategy.__subclasses__():
        if (
            subclass not in _registry
            and subclass.__module__.startswith("agent_evals.context.")
        ):
            try:
                _registry[subclass] = subclass()
            except TypeError:
                pass
