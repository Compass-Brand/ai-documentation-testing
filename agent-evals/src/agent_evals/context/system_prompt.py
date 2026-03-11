"""System prompt strategy -- truncates rendered index to a token budget.

Supports two truncation methods:
- "hard": Simple token-count cutoff.
- "priority": Uses doc_tree tier metadata and sort_files_bluf() to keep
  required-tier content first, filling remaining budget with lower-priority
  content.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.context.base import (
    ContextStrategy,
    PreparedContext,
    StrategyConfig,
    StrategyResult,
)
from agent_evals.llm.token_counter import count_tokens

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.llm.client import LLMClient
    from agent_evals.tasks.base import EvalTask


class SystemPromptStrategy(ContextStrategy):
    """Truncates the rendered index to fit within a token budget."""

    def __init__(self, config: StrategyConfig | None = None) -> None:
        self._config = config or StrategyConfig()

    def name(self) -> str:
        return "system_prompt"

    def supports_caching(self) -> bool:
        return True

    def prepare(
        self, rendered_index: str, task: EvalTask, doc_tree: DocTree,
    ) -> PreparedContext:
        budget = self._config.token_budget
        method = self._config.truncation

        if budget is None:
            # No budget constraint -- pass through like full context
            truncated = rendered_index
            original_tokens = count_tokens(rendered_index)
            truncated_tokens = original_tokens
        elif budget == 0:
            truncated = ""
            original_tokens = count_tokens(rendered_index)
            truncated_tokens = 0
        elif method == "priority" and doc_tree.files:
            truncated, original_tokens, truncated_tokens = self._priority_truncate(
                rendered_index, budget, doc_tree,
            )
        else:
            truncated, original_tokens, truncated_tokens = self._hard_truncate(
                rendered_index, budget,
            )

        messages = task.build_prompt(truncated)
        return PreparedContext(
            messages=messages,
            tools=None,
            strategy_metadata={
                "original_tokens": original_tokens,
                "truncated_tokens": truncated_tokens,
                "truncation_method": method,
                "token_budget": budget,
            },
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

    # ------------------------------------------------------------------
    # Truncation methods
    # ------------------------------------------------------------------

    @staticmethod
    def _hard_truncate(text: str, budget: int) -> tuple[str, int, int]:
        """Truncate text to fit within *budget* tokens via binary search."""
        original_tokens = count_tokens(text)
        if original_tokens <= budget:
            return text, original_tokens, original_tokens

        # Binary search for the longest prefix that fits
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if count_tokens(text[:mid]) <= budget:
                lo = mid
            else:
                hi = mid - 1

        truncated = text[:lo]
        truncated_tokens = count_tokens(truncated)
        return truncated, original_tokens, truncated_tokens

    def _priority_truncate(
        self, rendered_index: str, budget: int, doc_tree: DocTree,
    ) -> tuple[str, int, int]:
        """Truncate the rendered index using hard cutoff.

        Priority ordering is the responsibility of the variant renderer
        (which already sorts by tier/priority via sort_files_bluf). The
        strategy simply truncates the variant-rendered text to fit the
        budget, preserving whatever ordering the variant applied.

        Previous implementation assembled raw doc_tree content instead
        of truncating the rendered index, which meant all variants got
        identical content regardless of their axis settings (#183).
        """
        return self._hard_truncate(rendered_index, budget)
