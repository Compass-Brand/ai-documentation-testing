"""Multi-session persistence testing via simulated compaction."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from agent_evals.context.base import ContextStrategy, PreparedContext, StrategyResult

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.llm.client import LLMClient
    from agent_evals.tasks.base import EvalTask


def simulate_compaction(
    messages: list[dict[str, str]], target_ratio: float = 0.5,
) -> list[dict[str, str]]:
    """Simulate context-window compaction by truncating older messages.

    Preserves the system message (if present) and keeps the most recent
    messages up to ``target_ratio`` of the total conversation character count.
    Earlier messages are replaced with a summary stub.
    """
    if not messages:
        return messages

    result: list[dict[str, str]] = []

    if messages[0]["role"] == "system":
        result.append(messages[0])
        conversation = messages[1:]
    else:
        conversation = messages

    if not conversation:
        return result

    total_chars = sum(len(m["content"] or "") for m in conversation)
    target_chars = int(total_chars * target_ratio)

    kept: list[dict[str, str]] = []
    running = 0
    for msg in reversed(conversation):
        content = msg["content"] or ""
        running += len(content)
        if running <= target_chars:
            kept.insert(0, msg)
        else:
            remaining = [m for m in conversation if m not in kept]
            if remaining:
                summary_parts = []
                for m in remaining:
                    m_content = m["content"] or ""
                    summary_parts.append(f"[{m['role']}]: {m_content[:50]}...")
                summary = "Previous conversation summary:\n" + "\n".join(
                    summary_parts,
                )
                result.append({"role": "user", "content": summary})
            break

    result.extend(kept)
    return result


class CompactionModifier(ContextStrategy):
    """Wraps an inner strategy and applies compaction after execution.

    The compacted message history simulates what an agent would see after
    a context-window compaction event (e.g. between sessions).
    """

    def __init__(
        self, inner: ContextStrategy, compaction_ratio: float = 0.5,
    ) -> None:
        self._inner = inner
        self._compaction_ratio = compaction_ratio

    def name(self) -> str:
        return f"{self._inner.name()}+compaction"

    def supports_caching(self) -> bool:
        return False

    def setup(self, rendered_index: str, doc_tree: DocTree) -> None:
        self._inner.setup(rendered_index, doc_tree)

    def teardown(self) -> None:
        self._inner.teardown()

    def prepare(
        self, rendered_index: str, task: EvalTask, doc_tree: DocTree,
    ) -> PreparedContext:
        return self._inner.prepare(rendered_index, task, doc_tree)

    def execute(
        self,
        prepared: PreparedContext,
        task: EvalTask,
        client: LLMClient,
        max_tokens: int,
        temperature: float,
    ) -> StrategyResult:
        result = self._inner.execute(
            prepared, task, client, max_tokens, temperature,
        )
        compacted = simulate_compaction(result.messages, self._compaction_ratio)
        metadata = dict(result.strategy_metadata)
        metadata["compaction_applied"] = True
        metadata["compaction_ratio"] = self._compaction_ratio
        metadata["pre_compaction_messages"] = len(result.messages)
        metadata["post_compaction_messages"] = len(compacted)
        return StrategyResult(
            final_response=result.final_response,
            generations=result.generations,
            total_prompt_tokens=result.total_prompt_tokens,
            total_completion_tokens=result.total_completion_tokens,
            total_tokens=result.total_tokens,
            total_cost=result.total_cost,
            messages=compacted,
            strategy_metadata=metadata,
        )


def run_compacted_sequence(
    tasks: list[EvalTask],
    strategy: ContextStrategy,
    client: LLMClient,
    compaction_ratio: float = 0.5,
    max_tokens: int = 1024,
    temperature: float = 0.0,
    doc_tree: DocTree | None = None,
) -> list[StrategyResult]:
    """Run a sequence of tasks with compaction applied between each.

    Simulates multi-session persistence: after each task the conversation
    is compacted, and the compacted history carries over to the next task.
    """
    results: list[StrategyResult] = []
    carry_over_messages: list[dict[str, str]] | None = None

    for i, task in enumerate(tasks):
        prepared = strategy.prepare("", task, doc_tree)

        if carry_over_messages is not None:
            prepared.messages = carry_over_messages + prepared.messages[1:]

        result = strategy.execute(
            prepared, task, client, max_tokens, temperature,
        )
        carry_over_messages = simulate_compaction(
            result.messages, compaction_ratio,
        )

        metadata = dict(result.strategy_metadata)
        metadata["sequence_position"] = i
        metadata["compaction_applied"] = i > 0

        result = StrategyResult(
            final_response=result.final_response,
            generations=result.generations,
            total_prompt_tokens=result.total_prompt_tokens,
            total_completion_tokens=result.total_completion_tokens,
            total_tokens=result.total_tokens,
            total_cost=result.total_cost,
            messages=result.messages,
            strategy_metadata=metadata,
        )
        results.append(result)

    return results


def format_durability_score(results: list[dict[str, Any]]) -> float:
    """Measure accuracy degradation across a compacted sequence.

    Returns a score in ``[0, 1]`` where 1.0 means no degradation and
    0.0 means complete degradation.  Computed as the mean ratio of each
    subsequent score to the first score.
    """
    if not results or len(results) < 2:
        return 1.0

    sorted_results = sorted(results, key=lambda r: r["position"])
    first_score = sorted_results[0]["score"]

    if first_score == 0:
        return 0.0

    ratios = [r["score"] / first_score for r in sorted_results[1:]]
    return sum(ratios) / len(ratios)
