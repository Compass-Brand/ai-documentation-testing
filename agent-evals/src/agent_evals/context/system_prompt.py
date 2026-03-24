"""System prompt strategy -- truncates rendered index to a token budget.

Supports one truncation method:
- "hard": Simple token-count cutoff (binary search).

Note: "priority" truncation was removed (#267) — it was dead code that
delegated entirely to hard truncation. Any config with truncation="priority"
now falls through to hard truncation automatically.
"""

from __future__ import annotations

import logging
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

_log = logging.getLogger(__name__)


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
        # Guard against None from variant.render() returning None (#268).
        rendered_index = rendered_index or ""

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
        else:
            # Both "hard" and "priority" use hard truncation.
            # _priority_truncate was removed (#267) -- it was identical to hard.
            truncated, original_tokens, truncated_tokens = self._hard_truncate(
                rendered_index, budget,
            )

        messages = task.build_prompt(truncated)

        # Validate that output contains a system-role message (#262).
        # The strategy's purpose is to deliver doc context via the system prompt;
        # warn if the task's build_prompt did not produce one.
        has_system = any(
            isinstance(m, dict) and m.get("role") == "system"
            for m in messages
        )
        if not has_system:
            _log.warning(
                "SystemPromptStrategy: build_prompt output contains no "
                "system-role message. Doc context may not be in the system "
                "prompt. Task: %s",
                getattr(getattr(task, "definition", None), "task_id", "<unknown>"),
            )

        return PreparedContext(
            messages=messages,
            tools=None,
            strategy_metadata={
                "original_tokens": original_tokens,
                "truncated_tokens": truncated_tokens,
                "truncation_method": method,
                "token_budget": budget,
                "system_prompt_enforced": has_system,
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
