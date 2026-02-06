"""Negative (unanswerable) task type for evaluating abstention behaviour.

Scores responses by checking for the presence of recognised abstention
phrases.  A correct response to an unanswerable question should contain
one of these phrases and therefore receives a score of 1.0.

The abstention phrase list covers 30+ common LLM refusal and uncertainty
wordings grouped into categories: explicit refusal, information absence,
search failure, uncertainty hedging, and scope limitation.
"""

from __future__ import annotations

from typing import Any

from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type

# ---------------------------------------------------------------------------
# Abstention phrases — checked case-insensitively via ``phrase in response``.
# Grouped by category so maintainers can easily spot gaps.
# ---------------------------------------------------------------------------
_ABSTENTION_PHRASES: tuple[str, ...] = (
    # -- Explicit refusal / inability --
    "cannot be determined",
    "cannot answer",
    "cannot determine",
    "unable to find",
    "unable to determine",
    "unanswerable",
    # -- "don't / do not" variants --
    "don't know",
    "do not know",
    "don't have enough",
    "do not have enough",
    "doesn't contain",
    "does not contain",
    "doesn't include",
    "does not include",
    # -- Information absence --
    "no information",
    "no relevant information",
    "no mention",
    "no data",
    "not available",
    "not found",
    "not mentioned",
    "not provided",
    "not specified",
    "not documented",
    "not covered",
    "not addressed",
    "not explicitly stated",
    # -- Search / lookup failure --
    "couldn't find",
    "could not find",
    "not in the documentation",
    "the documentation does not specify",
    # -- Uncertainty hedging --
    "i'm not sure",
    "i am not sure",
    "not clear from",
    "insufficient information",
    # -- Scope limitation --
    "based on the available",
    "the provided documentation",
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
