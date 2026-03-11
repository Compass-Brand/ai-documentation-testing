"""Tests for Bug #197: Strategy registry must return new instances, not singletons.

The context strategy registry stores singleton instances per class.
get_strategy_by_name() returns this singleton, so all callers share the
same mutable object.  TaguchiRunner calls the factory once per OA row,
expecting independent instances, but gets the same one -- state leaks.
"""

from __future__ import annotations

import pytest
from agent_evals.context.registry import (
    clear_registry,
    create_strategy_by_name,
    get_strategy_by_name,
    load_all,
)


@pytest.fixture(autouse=True)
def _fresh_registry():
    """Ensure a clean registry for each test."""
    clear_registry()
    load_all()
    yield
    clear_registry()


class TestStrategyRegistrySingleton:
    """Bug #197: factory must create NEW instances, not return singletons."""

    def test_get_strategy_by_name_returns_same_instance(self):
        """get_strategy_by_name (lookup) may return the same cached instance."""
        s1 = get_strategy_by_name("full_context")
        s2 = get_strategy_by_name("full_context")
        assert s1 is not None
        assert s2 is not None
        # Lookup CAN return the same instance (it's for discovery)
        assert s1 is s2

    def test_create_strategy_by_name_returns_new_instances(self):
        """create_strategy_by_name must return a fresh instance each call."""
        s1 = create_strategy_by_name("full_context")
        s2 = create_strategy_by_name("full_context")
        assert s1 is not None
        assert s2 is not None
        # These MUST be different objects so state doesn't leak
        assert s1 is not s2

    def test_create_strategy_by_name_returns_none_for_unknown(self):
        """create_strategy_by_name returns None for unregistered names."""
        assert create_strategy_by_name("nonexistent_strategy") is None

    def test_create_strategy_same_type_as_registered(self):
        """New instances from create have the same type as the registered one."""
        original = get_strategy_by_name("full_context")
        created = create_strategy_by_name("full_context")
        assert original is not None
        assert created is not None
        assert type(original) is type(created)

    def test_created_instances_have_independent_state(self):
        """Mutating one created instance must not affect the other."""
        s1 = create_strategy_by_name("full_context")
        s2 = create_strategy_by_name("full_context")
        assert s1 is not None
        assert s2 is not None
        # Add a marker attribute to s1
        s1._test_marker = "row_1"  # type: ignore[attr-defined]
        assert not hasattr(s2, "_test_marker")
