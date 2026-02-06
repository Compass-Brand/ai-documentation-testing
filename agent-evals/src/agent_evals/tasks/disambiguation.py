"""Disambiguation task type for evaluating interpretation selection.

Scores responses by checking whether the model correctly identified the
expected interpretation from a set of ambiguous alternatives.
Score: 1.0 for answer match, 0.5 for label-only match, 0.0 for neither.
"""

from __future__ import annotations

from typing import Any

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
        """Score response by checking interpretation answer and label matches.

        Scoring logic:
        - 1.0 if the expected interpretation's answer appears in the response
        - 0.5 if only the expected interpretation's label appears
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

        # Check answer match (case-insensitive)
        if expected_answer and expected_answer.lower() in response_lower:
            return 1.0

        # Check label match (case-insensitive)
        if self.expected_interpretation.lower() in response_lower:
            return 0.5

        return 0.0


register_task_type("disambiguation", DisambiguationTask)
