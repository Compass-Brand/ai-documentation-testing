"""Context strategy system for documentation access patterns.

Public API:
    - ``ContextStrategy`` -- ABC that all strategies must subclass.
    - ``PreparedContext`` -- Output of prepare(), input to execute().
    - ``StrategyResult`` -- Output of execute() wrapping generation results.
    - ``StrategyConfig`` -- Configuration for strategy construction.
    - ``FullContextStrategy`` -- Default strategy (full index injection).
"""

from agent_evals.context.base import (
    ContextStrategy,
    PreparedContext,
    StrategyConfig,
    StrategyResult,
)
from agent_evals.context.full import FullContextStrategy

__all__ = [
    "ContextStrategy",
    "FullContextStrategy",
    "PreparedContext",
    "StrategyConfig",
    "StrategyResult",
]
