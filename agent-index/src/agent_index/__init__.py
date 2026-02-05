"""agent-index: AI documentation optimizer and tiered index generator."""

from agent_index.models import (
    DocFile,
    DocTree,
    IndexConfig,
    TierConfig,
    TransformStep,
)

__version__ = "0.1.0"

__all__ = [
    "DocFile",
    "DocTree",
    "IndexConfig",
    "TierConfig",
    "TransformStep",
    "__version__",
]
