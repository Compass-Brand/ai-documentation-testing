"""Tests for agent-evals package initialization."""

import agent_evals
import agent_index


def test_version_exists() -> None:
    """Package version should be defined."""
    assert hasattr(agent_evals, "__version__")
    assert agent_evals.__version__ == "0.1.0"


def test_can_import_agent_index() -> None:
    """agent-evals should be able to import from agent-index."""
    # Verify agent_index is importable from agent_evals context
    assert hasattr(agent_index, "__version__")
    assert agent_index.__version__ == "0.1.0"
