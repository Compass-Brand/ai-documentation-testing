"""Robustness task type for evaluating answer stability under perturbation.

Reuses the same scoring logic as FactExtractionTask: exact / alias match
yields 1.0, fallback computes fraction of non-stopword keywords found.
"""

from __future__ import annotations

from typing import Any

from agent_evals.tasks._utils import extract_keywords
from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type


class RobustnessTask(EvalTask):
    """Task type for evaluating answer stability under input perturbation.

    A perturbed version of a base task (e.g. paraphrased, with typos,
    or reordered).  Scoring is identical to FactExtractionTask: exact
    or alias match = 1.0, otherwise keyword-fraction fallback.
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta: dict[str, Any] = definition.metadata
        self.base_task_id: str = meta.get("base_task_id", "")
        self.perturbation_type: str = meta.get("perturbation_type", "")
        self.expected_answer: str = meta.get("expected_answer", "")
        self.answer_aliases: list[str] = meta.get("answer_aliases", [])

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build messages for robustness evaluation.

        Args:
            index_content: The documentation index content.

        Returns:
            List of message dicts with system and user messages.
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that answers factual questions "
                    "using information from a documentation index. Provide "
                    "concise, accurate answers.\n\n"
                    f"{index_content}"
                ),
            },
            {
                "role": "user",
                "content": self.definition.question,
            },
        ]

    def score_response(self, response: str, **kwargs: object) -> float:
        """Score response using keyword matching against expected answer.

        Checks for exact match of expected_answer or any alias first.
        Falls back to computing fraction of non-stopword keywords found.

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (unused).

        Returns:
            Score between 0.0 and 1.0.
        """
        if not self.expected_answer:
            return 0.0

        response_lower = response.lower()

        # Check exact match of expected answer
        if self.expected_answer.lower() in response_lower:
            return 1.0

        # Check alias matches
        for alias in self.answer_aliases:
            if alias.lower() in response_lower:
                return 1.0

        # Fallback: keyword matching
        keywords = extract_keywords(self.expected_answer)
        if not keywords:
            return 0.0

        matched = sum(1 for kw in keywords if kw.lower() in response_lower)
        return max(0.0, min(1.0, matched / len(keywords)))


register_task_type("robustness", RobustnessTask)
