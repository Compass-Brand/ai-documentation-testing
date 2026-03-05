"""Core abstractions for context delivery strategies.

Provides:
- ContextStrategy: ABC that all strategies must implement.
- PreparedContext: Output of prepare(), input to execute().
- StrategyResult: Output of execute() wrapping generation results.
- StrategyConfig: Configuration for strategy construction.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.llm.client import GenerationResult, LLMClient
    from agent_evals.tasks.base import EvalTask


class ContextStrategy(ABC):
    """Base class for all context delivery strategies."""

    @abstractmethod
    def name(self) -> str: ...

    def setup(self, rendered_index: str, doc_tree: DocTree) -> None:
        """One-time setup per variant/OA-row. Called before any trials."""

    def teardown(self) -> None:
        """Cleanup after all trials for this variant/row."""

    @abstractmethod
    def prepare(
        self, rendered_index: str, task: EvalTask, doc_tree: DocTree,
    ) -> PreparedContext:
        """Prepare context for a single trial. Must be thread-safe."""
        ...

    @abstractmethod
    def execute(
        self,
        prepared: PreparedContext,
        task: EvalTask,
        client: LLMClient,
        max_tokens: int,
        temperature: float,
    ) -> StrategyResult:
        """Execute the LLM interaction. Single-turn or multi-turn."""
        ...

    def supports_caching(self) -> bool:
        """Whether results from this strategy are deterministic and cacheable."""
        return True


@dataclass
class PreparedContext:
    """Output of prepare() -- input to execute()."""

    messages: list[dict]
    tools: list[dict] | None
    strategy_metadata: dict[str, Any]


@dataclass
class StrategyResult:
    """Output of execute() wrapping generation results."""

    final_response: str
    generations: list[GenerationResult]
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_cost: float | None
    messages: list[dict]
    strategy_metadata: dict[str, Any]


@dataclass
class StrategyConfig:
    """Configuration for context strategy construction."""

    strategy: str = "full_context"
    token_budget: int | None = None
    truncation: str = "hard"
    chunk_method: str = "heading"
    rag_top_k: int = 5
    embedding_model: str = "text-embedding-3-small"
    max_turns: int = 10
