"""agent-index: AI documentation optimizer and tiered index generator."""

from agent_index.config import ConfigError, find_config, load_config
from agent_index.models import (
    DocFile,
    DocTree,
    IndexConfig,
    TierConfig,
    TransformStep,
)
from agent_index.scanner import GitHubError, scan_github, scan_local

__version__ = "0.1.0"

__all__ = [
    "ConfigError",
    "DocFile",
    "DocTree",
    "GitHubError",
    "IndexConfig",
    "TierConfig",
    "TransformStep",
    "find_config",
    "load_config",
    "scan_github",
    "scan_local",
    "__version__",
]
