"""Compositional task type for evaluating multi-part question answering.

Scores responses by checking whether each sub-task's expected answer
appears (case-insensitive) in the response.  Score = fraction of
sub-tasks whose expected_answer is found.
"""

from __future__ import annotations

from typing import Any

from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type


class CompositionalTask(EvalTask):
    """Task type for evaluating compositional reasoning.

    A compositional question is decomposed into sub-tasks, each with a
    question and expected answer.  The score is the fraction of sub-tasks
    whose expected answer appears in the LLM response.
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta: dict[str, Any] = definition.metadata
        self.sub_tasks: list[dict[str, Any]] = meta.get("sub_tasks", [])
        self.composition_type: str = meta.get("composition_type", "")

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build messages for compositional reasoning evaluation.

        Args:
            index_content: The documentation index content.

        Returns:
            List of message dicts with system and user messages.
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that answers compositional "
                    "questions. Break the question into sub-parts, answer "
                    "each sub-part using the documentation index, then "
                    "combine the answers.\n\n"
                    f"{index_content}"
                ),
            },
            {
                "role": "user",
                "content": self.definition.question,
            },
        ]

    def score_response(self, response: str, **kwargs: object) -> float:
        """Score response by checking sub-task answer coverage.

        For each sub-task, checks whether the expected_answer appears
        (case-insensitive) in the response.  Score = fraction of sub-tasks
        matched.

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (unused).

        Returns:
            Score between 0.0 and 1.0.
        """
        if not self.sub_tasks:
            return 1.0

        response_lower = response.lower()
        matched = 0

        for sub_task in self.sub_tasks:
            expected: str = sub_task.get("expected_answer", "")
            if not expected:
                continue
            if expected.lower() in response_lower:
                matched += 1

        score = matched / len(self.sub_tasks)
        return max(0.0, min(1.0, score))


register_task_type("compositional", CompositionalTask)
