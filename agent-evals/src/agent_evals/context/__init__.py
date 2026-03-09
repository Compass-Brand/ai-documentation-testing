"""Context strategy system for documentation access patterns.

Public API:
    - ``ContextStrategy`` -- ABC that all strategies must subclass.
    - ``PreparedContext`` -- Output of prepare(), input to execute().
    - ``StrategyResult`` -- Output of execute() wrapping generation results.
    - ``StrategyConfig`` -- Configuration for strategy construction.
    - ``FullContextStrategy`` -- Default strategy (full index injection).
    - ``SystemPromptStrategy`` -- Token-budget constrained strategy.
    - ``RAGStrategy`` -- Chunk, embed, retrieve context strategy.
    - ``ToolBasedStrategy`` -- Multi-turn agentic strategy with doc tools.
    - ``CompressionStrategy`` -- Compression strategy (algorithmic/format/LLM).
    - ``MCPNativeStrategy`` -- MCP-native strategy with resource catalog browsing.
"""

from agent_evals.context.base import (
    ContextStrategy,
    PreparedContext,
    StrategyConfig,
    StrategyResult,
)
from agent_evals.context.compression import CompressionStrategy
from agent_evals.context.full import FullContextStrategy
from agent_evals.context.mcp_native import MCPNativeStrategy
from agent_evals.context.rag import RAGStrategy
from agent_evals.context.system_prompt import SystemPromptStrategy
from agent_evals.context.tool_based import ToolBasedStrategy

__all__ = [
    "CompressionStrategy",
    "ContextStrategy",
    "FullContextStrategy",
    "MCPNativeStrategy",
    "PreparedContext",
    "RAGStrategy",
    "StrategyConfig",
    "StrategyResult",
    "SystemPromptStrategy",
    "ToolBasedStrategy",
]
