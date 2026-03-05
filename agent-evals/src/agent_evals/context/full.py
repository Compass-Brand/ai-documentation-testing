"""Full context strategy -- injects entire rendered index into the prompt.

This is the default strategy and produces identical results to the
pre-strategy pipeline: variant.render() -> task.build_prompt(index) ->
client.complete(messages).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.context.base import ContextStrategy, PreparedContext, StrategyResult

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.llm.client import LLMClient
    from agent_evals.tasks.base import EvalTask


class FullContextStrategy(ContextStrategy):
    """Stuffs the entire rendered index into the prompt (current behavior)."""

    def name(self) -> str:
        return "full_context"

    def prepare(
        self, rendered_index: str, task: EvalTask, doc_tree: DocTree,
    ) -> PreparedContext:
        messages = task.build_prompt(rendered_index)
        return PreparedContext(
            messages=messages,
            tools=None,
            strategy_metadata={},
        )

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
