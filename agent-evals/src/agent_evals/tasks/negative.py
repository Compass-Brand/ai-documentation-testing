"""Negative (unanswerable) task type for evaluating abstention behaviour.

Scores responses using a tiered rubric that checks for recognised abstention
phrases.  A correct response to an unanswerable question should contain
a firm refusal phrase (1.0), a hedge with caveat (0.7), or an answer
with a disclaimer (0.3).  Confident hallucinations score 0.0.

The phrase lists cover 35+ common LLM refusal and uncertainty wordings
grouped into three tiers: firm refusal, hedge with caveat, and answer
with disclaimer.
"""

from __future__ import annotations

from typing import Any

from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type

# ---------------------------------------------------------------------------
# Tiered abstention phrases — checked case-insensitively via
# ``phrase in response``.  Priority order: firm_refusal > hedge > disclaimer.
# ---------------------------------------------------------------------------
_FIRM_REFUSAL: frozenset[str] = frozenset([
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
])
_HEDGE_WITH_CAVEAT: frozenset[str] = frozenset([
    "i'm not certain", "i cannot confirm", "it's unclear",
    "the documentation doesn't explicitly",
])
_ANSWER_WITH_DISCLAIMER: frozenset[str] = frozenset([
    "based on limited information", "this may not be accurate",
    "i'm making an assumption",
])


class NegativeTask(EvalTask):
    """Task type for evaluating correct abstention on unanswerable questions.

    The question is intentionally unanswerable from the provided index.
    A good response should abstain (e.g. "cannot be determined") rather
    than hallucinate an answer.
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta: dict[str, Any] = definition.metadata
        # YAML-sourced fields (actual gold standard schema)
        self.expected_answer: str = meta.get("expected_answer", "")
        self.reason: str = meta.get("reason", "")
        self.nearest_doc: str = meta.get("nearest_doc", "")
        self.nearest_content: str = meta.get("nearest_content", "")
        # Legacy fields (backward compatibility)
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
        """Score response using tiered rubric for abstention quality.

        Tiers (checked in priority order):
        - 1.0: Firm refusal (e.g. "cannot be determined")
        - 0.7: Hedge with caveat (e.g. "I'm not certain")
        - 0.3: Answer with disclaimer (e.g. "based on limited information")
        - 0.0: Confident hallucination (no abstention phrases)

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (unused).

        Returns:
            Score between 0.0 and 1.0 based on abstention tier.
        """
        response_lower = response.lower()
        if any(p in response_lower for p in _FIRM_REFUSAL):
            return 1.0
        if any(p in response_lower for p in _HEDGE_WITH_CAVEAT):
            return 0.7
        if any(p in response_lower for p in _ANSWER_WITH_DISCLAIMER):
            return 0.3
        return 0.0


register_task_type("negative", NegativeTask)
