"""Full context strategy -- passes rendered index directly to the LLM.

The rendered index IS the variant-specific content produced by the
variant pipeline. Using it directly (rather than appending raw doc
content) ensures that Taguchi axis effects are preserved.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.context.base import ContextStrategy, PreparedContext, StrategyResult
from agent_evals.context.registry import register_strategy

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.llm.client import LLMClient
    from agent_evals.tasks.base import EvalTask

DEFAULT_MAX_CONTENT_TOKENS = 50_000


@register_strategy
class FullContextStrategy(ContextStrategy):
    """Passes the variant-rendered index directly to the LLM."""

    def __init__(self, max_content_tokens: int = DEFAULT_MAX_CONTENT_TOKENS) -> None:
        self._max_content_tokens = max_content_tokens

    def name(self) -> str:
        return "full_context"

    def prepare(
        self, rendered_index: str, task: EvalTask, doc_tree: DocTree,
    ) -> PreparedContext:
        # Guard against None from variant.render() returning None (#268).
        rendered_index = rendered_index or ""
        # Use the rendered index directly — it IS the variant-specific content.
        # Appending raw doc_tree content would be identical for all variants,
        # diluting Taguchi axis effects.
        messages = task.build_prompt(rendered_index)
        return PreparedContext(
            messages=messages,
            tools=None,
            strategy_metadata={
                "index_tokens": self._estimate_tokens(rendered_index),
            },
        )

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Cheap ~4 chars/token heuristic to avoid litellm dependency."""
        return len(text) // 4

    def execute(
        self,
        prepared: PreparedContext,
        task: EvalTask,
        client: LLMClient,
        max_tokens: int,
        temperature: float,
    ) -> StrategyResult:
        generation = client.complete(
            prepared.messages,
            tools=prepared.tools,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return StrategyResult(
            final_response=generation.content,
            generations=[generation],
            total_prompt_tokens=generation.prompt_tokens,
            total_completion_tokens=generation.completion_tokens,
            total_tokens=generation.total_tokens,
            total_cost=generation.cost,
            messages=prepared.messages,
            strategy_metadata=prepared.strategy_metadata,
        )
