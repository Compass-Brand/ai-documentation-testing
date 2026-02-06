"""Multi-hop reasoning task type for evaluating multi-step question answering.

Scores responses by checking whether each decomposition step is addressed,
using keyword matching (non-stopword words with 3+ characters).
"""

from __future__ import annotations

from typing import Any

from agent_evals.tasks._utils import extract_keywords
from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type


class MultiHopTask(EvalTask):
    """Task type for evaluating multi-hop reasoning across evidence paragraphs.

    Checks if the response addresses each sub-question in the question
    decomposition by looking for keyword matches from each step.
    Score = fraction of decomposition steps with at least one keyword match.
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta: dict[str, Any] = definition.metadata
        self.paragraphs: list[dict[str, Any]] = meta.get("paragraphs", [])
        self.question_decomposition: list[str] = meta.get(
            "question_decomposition", [],
        )
        self.reasoning_chain: list[str] = meta.get("reasoning_chain", [])

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build messages for multi-hop reasoning evaluation.

        Args:
            index_content: The documentation index content.

        Returns:
            List of message dicts with system and user messages.
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that answers questions requiring "
                    "multi-step reasoning. Use the following documentation "
                    "index to find evidence across multiple sources and "
                    "connect them to reach your answer.\n\n"
                    f"{index_content}"
                ),
            },
            {
                "role": "user",
                "content": self.definition.question,
            },
        ]

    def score_response(self, response: str, **kwargs: object) -> float:
        """Score response by checking decomposition step coverage.

        For each step in question_decomposition, extract non-stopword
        keywords (3+ chars) and check if at least one appears in the
        response. Score = fraction of steps with at least one keyword match.

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (unused).

        Returns:
            Score between 0.0 and 1.0.
        """
        if not self.question_decomposition:
            return 1.0

        response_lower = response.lower()
        steps_matched = 0

        for step in self.question_decomposition:
            keywords = extract_keywords(step)
            if not keywords:
                # Step with no extractable keywords counts as matched
                steps_matched += 1
                continue
            if any(kw.lower() in response_lower for kw in keywords):
                steps_matched += 1

        score = steps_matched / len(self.question_decomposition)
        return max(0.0, min(1.0, score))


register_task_type("multi_hop", MultiHopTask)
