"""Retrieval task type for evaluating file identification accuracy.

Scores responses using F-beta (beta=2) to weight recall over precision,
since missing a needed document costs more than including an extra one.
"""

from __future__ import annotations

import re

from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type

# Pattern to match file paths with common extensions
_FILE_PATH_PATTERN: re.Pattern[str] = re.compile(
    r"(?:[\w./-]+/)?[\w.-]+\.(?:md|py|yaml|yml|json|toml|txt|rst|html)"
)


class RetrievalTask(EvalTask):
    """Task type for evaluating file retrieval accuracy.

    Extracts file paths from the LLM response and computes F-beta (beta=2)
    against the expected file list. Beta=2 weights recall over precision.
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta = definition.metadata
        self.expected_files: list[str] = meta.get("expected_files", [])
        self.evidence_passage: str = meta.get("evidence_passage", "")

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build messages for file retrieval evaluation.

        Args:
            index_content: The documentation index content.

        Returns:
            List of message dicts with system and user messages.
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that identifies relevant files "
                    "from a documentation index. Given a question, list the "
                    "file paths that are most relevant to answering it.\n\n"
                    f"{index_content}"
                ),
            },
            {
                "role": "user",
                "content": self.definition.question,
            },
        ]

    def score_response(self, response: str, **kwargs: object) -> float:
        """Score response using F-beta (beta=2) against expected files.

        Extracts file paths from the response text using regex, then
        computes F-beta score comparing extracted paths to expected paths.

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (unused).

        Returns:
            F-beta score between 0.0 and 1.0.
        """
        extracted = set(_FILE_PATH_PATTERN.findall(response))
        expected = set(self.expected_files)

        # Edge cases
        if not expected and not extracted:
            return 1.0
        if not expected and extracted:
            return 0.0
        if expected and not extracted:
            return 0.0

        true_positives = len(expected & extracted)
        precision = true_positives / len(extracted) if extracted else 0.0
        recall = true_positives / len(expected) if expected else 0.0

        if precision + recall == 0.0:
            return 0.0

        beta = 2.0
        beta_sq = beta * beta
        fbeta = (1.0 + beta_sq) * precision * recall / (beta_sq * precision + recall)

        return max(0.0, min(1.0, fbeta))


register_task_type("retrieval", RetrievalTask)
