"""Compression context strategy -- reduces docs before injection.

Three compression methods:
- algorithmic: Remove stopwords, redundant whitespace, low-info lines.
- llm_summarized: Use a cheap LLM to summarize before injection.
- format_conversion: Convert markdown to compact key-value format.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from agent_evals.context.base import ContextStrategy, PreparedContext, StrategyResult
from agent_evals.context.registry import register_strategy
from agent_evals.llm.token_counter import count_tokens

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.llm.client import LLMClient
    from agent_evals.tasks.base import EvalTask

_STOPWORD_RE = re.compile(
    r"\b(the|a|an|is|are|was|were|be|been|being|have|has|had|"
    r"do|does|did|will|would|could|should|may|might|must|shall|"
    r"can|need|dare|ought|used|to|of|in|for|on|with|at|by|from|"
    r"that|this|these|those|it|its)\b",
    re.IGNORECASE,
)
_MULTI_SPACE_RE = re.compile(r"[ \t]+")
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def _algorithmic_compress(text: str) -> str:
    compressed = _STOPWORD_RE.sub("", text)
    compressed = _MULTI_SPACE_RE.sub(" ", compressed)
    compressed = _MULTI_NEWLINE_RE.sub("\n\n", compressed)
    lines = [line.strip() for line in compressed.splitlines()]
    return "\n".join(line for line in lines if line)


def _format_convert(text: str) -> str:
    lines = text.splitlines()
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            current_section = stripped.lstrip("#").strip()
            output.append(f"[{current_section}]")
        elif stripped.startswith("- "):
            output.append(f"  * {stripped[2:]}")
        elif stripped:
            output.append(f"  {stripped}")
    return "\n".join(output)


def render_compression_tradeoff_table(trials: list[dict]) -> str:
    header = (
        f"{'VARIANT':<25} {'COMPRESSION_RATIO':>18} "
        f"{'ACCURACY':>10} {'COST_SAVINGS':>13} {'NET_BENEFIT':>12}"
    )
    separator = "-" * len(header)
    rows = [header, separator]
    for trial in trials:
        variant = trial.get("variant_name", "unknown")
        ratio = trial.get("compression_ratio", 1.0)
        accuracy = trial.get("accuracy", 0.0)
        cost = trial.get("cost", 0.0)
        baseline_cost = trial.get("baseline_cost", cost)
        cost_savings = (
            (baseline_cost - cost) / baseline_cost if baseline_cost > 0 else 0.0
        )
        net_benefit = accuracy * cost_savings
        rows.append(
            f"{variant:<25} {ratio:>18.4f} {accuracy:>10.4f} "
            f"{cost_savings:>13.4f} {net_benefit:>12.4f}"
        )
    return "\n".join(rows)


@register_strategy
class CompressionStrategy(ContextStrategy):
    def __init__(
        self,
        method: str = "algorithmic",
        summary_model: str = "openrouter/openai/gpt-4o-mini",
    ) -> None:
        self._method = method
        self._summary_model = summary_model
        self._rendered_index: str = ""
        self._summary_client: LLMClient | None = None

    def name(self) -> str:
        return "compression"

    def supports_caching(self) -> bool:
        return True

    def setup(self, rendered_index: str, doc_tree: DocTree) -> None:
        self._rendered_index = rendered_index

    def set_summary_client(self, client: LLMClient) -> None:
        self._summary_client = client

    def prepare(
        self, rendered_index: str, task: EvalTask, doc_tree: DocTree,
    ) -> PreparedContext:
        original_tokens = count_tokens(rendered_index)
        compressed = self._compress(rendered_index)
        compressed_tokens = count_tokens(compressed)
        ratio = (
            compressed_tokens / original_tokens if original_tokens > 0 else 1.0
        )
        messages = task.build_prompt(compressed)
        return PreparedContext(
            messages=messages,
            tools=None,
            strategy_metadata={
                "compression_method": self._method,
                "original_tokens": original_tokens,
                "compressed_tokens": compressed_tokens,
                "compression_ratio": round(ratio, 4),
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
        messages = list(prepared.messages)
        if self._method == "llm_summarized":
            summary_client = self._summary_client or client
            for i, msg in enumerate(messages):
                if (
                    msg["role"] == "system"
                    and len(msg.get("content", "")) > 200
                ):
                    messages[i] = dict(msg)
                    messages[i]["content"] = self._llm_summarize(
                        msg["content"], summary_client,
                    )
                    break
        generation = client.complete(
            messages, tools=prepared.tools,
            max_tokens=max_tokens, temperature=temperature,
        )
        return StrategyResult(
            final_response=generation.content,
            generations=[generation],
            total_prompt_tokens=generation.prompt_tokens,
            total_completion_tokens=generation.completion_tokens,
            total_tokens=generation.total_tokens,
            total_cost=generation.cost,
            messages=messages,
            strategy_metadata=prepared.strategy_metadata,
        )

    def _compress(self, text: str) -> str:
        if self._method == "algorithmic":
            return _algorithmic_compress(text)
        if self._method == "format_conversion":
            return _format_convert(text)
        if self._method == "llm_summarized":
            return _algorithmic_compress(text)
        return text

    def _llm_summarize(self, text: str, client: LLMClient) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a documentation compressor. Condense the "
                    "following documentation into the most "
                    "information-dense format possible. Preserve all "
                    "technical facts, API names, and configuration "
                    "values. Remove redundancy, verbose explanations, "
                    "and filler text."
                ),
            },
            {"role": "user", "content": text},
        ]
        generation = client.complete(
            messages, max_tokens=len(text) // 4 // 2, temperature=0.0,
            timeout=120.0,
        )
        return generation.content or text
