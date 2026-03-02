"""Disambiguation task type for evaluating interpretation selection.

Scores responses by checking whether the model correctly identified the
expected interpretation from a set of ambiguous alternatives.
Score: continuous keyword coverage (0.0-1.0) with optional ambiguity bonus,
0.5 for label match (underscore-normalized), max of both paths.
"""

from __future__ import annotations

from typing import Any

from agent_evals.tasks._utils import extract_keywords
from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type


class DisambiguationTask(EvalTask):
    """Task type for evaluating disambiguation accuracy.

    Given a set of possible interpretations (each with a label and answer),
    checks whether the model selected and answered with the correct one.
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta = definition.metadata
        self.interpretations: list[dict[str, Any]] = meta.get("interpretations", [])
        self.expected_interpretation: str = meta.get("expected_interpretation", "")

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build messages for disambiguation evaluation.

        Args:
            index_content: The documentation index content.

        Returns:
            List of message dicts with system and user messages.
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that disambiguates questions "
                    "using a documentation index. Identify the correct "
                    "interpretation and provide the corresponding answer.\n\n"
                    f"{index_content}"
                ),
            },
            {
                "role": "user",
                "content": self.definition.question,
            },
        ]

    def score_response(self, response: str, **kwargs: object) -> float:
        """Score response by keyword coverage and label matching.

        Scoring logic:
        - Continuous keyword coverage (0.0-1.0) plus optional 0.1
          ambiguity bonus (capped at 1.0)
        - 0.5 if the expected interpretation label (or its underscore-
          normalized form) appears in the response
        - Returns the max of answer score and label score
        - 0.0 if neither matches

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (unused).

        Returns:
            Score between 0.0 and 1.0.
        """
        if not self.expected_interpretation or not self.interpretations:
            return 0.0

        # Find the expected interpretation dict
        expected: dict[str, Any] | None = None
        for interp in self.interpretations:
            if interp.get("label") == self.expected_interpretation:
                expected = interp
                break

        if expected is None:
            return 0.0

        response_lower = response.lower()
        expected_answer: str = expected.get("answer", "")

        # --- Answer keyword coverage scoring (continuous) ---
        answer_score = 0.0
        if expected_answer:
            keywords = extract_keywords(expected_answer)
            if keywords:
                hits = sum(1 for kw in keywords if kw.lower() in response_lower)
                coverage = hits / len(keywords)
                ambiguity_bonus = 0.1 if any(
                    p in response_lower
                    for p in ["ambiguous", "multiple interpretations", "could mean"]
                ) else 0.0
                answer_score = min(1.0, coverage + ambiguity_bonus)

        # --- Label match scoring (underscore-normalized) ---
        label_score = 0.0
        label = self.expected_interpretation.lower()
        label_normalized = label.replace("_", " ")
        if label in response_lower or label_normalized in response_lower:
            label_score = 0.5

        return max(answer_score, label_score)


register_task_type("disambiguation", DisambiguationTask)
