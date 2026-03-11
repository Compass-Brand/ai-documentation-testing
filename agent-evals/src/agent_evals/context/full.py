"""Full context strategy -- injects rendered index AND document content.

Appends actual document content from the doc_tree after the rendered
index so the LLM sees both the structured index metadata AND the full
text of each documentation file (up to a configurable token limit).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.context.base import ContextStrategy, PreparedContext, StrategyResult

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.llm.client import LLMClient
    from agent_evals.tasks.base import EvalTask

DEFAULT_MAX_CONTENT_TOKENS = 50_000


class FullContextStrategy(ContextStrategy):
    """Injects the rendered index plus actual document content."""

    def __init__(self, max_content_tokens: int = DEFAULT_MAX_CONTENT_TOKENS) -> None:
        self._max_content_tokens = max_content_tokens

    def name(self) -> str:
        return "full_context"

    def prepare(
        self, rendered_index: str, task: EvalTask, doc_tree: DocTree,
    ) -> PreparedContext:
        full_content = self._build_full_content(rendered_index, doc_tree)
        messages = task.build_prompt(full_content)
        return PreparedContext(
            messages=messages,
            tools=None,
            strategy_metadata={
                "index_tokens": self._estimate_tokens(rendered_index),
                "content_files_included": self._count_included_files(doc_tree),
                "max_content_tokens": self._max_content_tokens,
            },
        )

    def _build_full_content(
        self, rendered_index: str, doc_tree: DocTree,
    ) -> str:
        """Combine rendered index with actual document content."""
        if not doc_tree.files:
            return rendered_index

        content_sections: list[str] = []
        tokens_used = 0

        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            file_tokens = doc.token_count if doc.token_count is not None else self._estimate_tokens(doc.content)

            if tokens_used + file_tokens > self._max_content_tokens:
                break

            content_sections.append(f"### {rel_path}\n{doc.content}")
            tokens_used += file_tokens

        if not content_sections:
            return rendered_index

        doc_content = "\n\n".join(content_sections)
        return f"{rendered_index}\n\n---\n## Document Contents\n\n{doc_content}"

    def _count_included_files(self, doc_tree: DocTree) -> int:
        """Count how many files fit within the token budget."""
        if not doc_tree.files:
            return 0
        tokens_used = 0
        count = 0
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            file_tokens = doc.token_count if doc.token_count is not None else self._estimate_tokens(doc.content)
            if tokens_used + file_tokens > self._max_content_tokens:
                break
            tokens_used += file_tokens
            count += 1
        return count

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
