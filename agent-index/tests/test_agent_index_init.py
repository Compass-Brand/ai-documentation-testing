"""Tests for agent-index package initialization."""

import agent_index


def test_version_exists() -> None:
    """Package version should be defined."""
    assert hasattr(agent_index, "__version__")
    assert agent_index.__version__ == "0.1.0"
