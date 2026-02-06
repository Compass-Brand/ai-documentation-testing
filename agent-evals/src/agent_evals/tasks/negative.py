"""Negative (unanswerable) task type for evaluating abstention behaviour.

Scores responses by checking for the presence of recognised abstention
phrases.  A correct response to an unanswerable question should contain
one of these phrases and therefore receives a score of 1.0.
"""

from __future__ import annotations

from typing import Any

from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type

# Abstention phrases (same set as AbstentionMetric)
_ABSTENTION_PHRASES: tuple[str, ...] = (
    "cannot be determined",
    "not available",
    "no information",
    "not found",
    "don't know",
    "unable to find",
    "not in the documentation",
    "unanswerable",
    "cannot answer",
)


class NegativeTask(EvalTask):
    """Task type for evaluating correct abstention on unanswerable questions.

    The question is intentionally unanswerable from the provided index.
    A good response should abstain (e.g. "cannot be determined") rather
    than hallucinate an answer.
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta: dict[str, Any] = definition.metadata
        self.answerable: bool = meta.get("answerable", False)
        self.distractor_files: list[str] = meta.get("distractor_files", [])

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build messages for negative / unanswerable evaluation.

        Instructs the model to answer the question if the information is
        available, or to explicitly abstain if it cannot be determined.

        Args:
            index_content: The documentation index content.

        Returns:
            List of message dicts with system and user messages.
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant. Use the following documentation "
                    "index to answer the question. If the information needed "
                    "to answer the question is not available, you must abstain "
                    "and say that you cannot determine the answer.\n\n"
                    f"{index_content}"
                ),
            },
            {
                "role": "user",
                "content": self.definition.question,
            },
        ]

    def score_response(self, response: str, **kwargs: object) -> float:
        """Score response based on presence of abstention phrases.

        Returns 1.0 if the response contains any recognised abstention
        phrase (case-insensitive), otherwise 0.0.

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (unused).

        Returns:
            1.0 if abstention detected, 0.0 otherwise.
        """
        response_lower = response.lower()
        for phrase in _ABSTENTION_PHRASES:
            if phrase in response_lower:
                return 1.0
        return 0.0


register_task_type("negative", NegativeTask)
