"""Efficiency task type for evaluating concise answering ability.

Scores responses on correctness (exact/alias/keyword match) and then
applies a length penalty when the response exceeds the token budget.
Token count is approximated by word count.
"""

from __future__ import annotations

from agent_evals.tasks._utils import extract_keywords
from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type


class EfficiencyTask(EvalTask):
    """Task type for evaluating answer efficiency (correctness + conciseness).

    Checks if the expected answer or any alias appears in the response
    (exact match = 1.0 base score). Falls back to keyword fraction.
    Then applies a length penalty if the response exceeds the token budget.
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta = definition.metadata
        self.expected_answer: str = meta.get("expected_answer", "")
        self.answer_aliases: list[str] = meta.get("answer_aliases", [])
        self.token_budget: int = meta.get("token_budget", 0)
        self.message_limit: int = meta.get("message_limit", 0)

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build messages for efficiency evaluation.

        Args:
            index_content: The documentation index content.

        Returns:
            List of message dicts with system and user messages.
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that answers questions concisely "
                    "using a documentation index. Provide accurate, brief "
                    "answers without unnecessary detail.\n\n"
                    f"{index_content}"
                ),
            },
            {
                "role": "user",
                "content": self.definition.question,
            },
        ]

    def score_response(self, response: str, **kwargs: object) -> float:
        """Score response on correctness and conciseness.

        Base score: 1.0 for exact/alias match, else keyword fraction.
        Length penalty: if word count > token_budget, multiply by
        token_budget / actual_tokens. Clamped to [0, 1].

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (unused).

        Returns:
            Score between 0.0 and 1.0.
        """
        if not self.expected_answer:
            return 0.0

        response_lower = response.lower()

        # Check exact match
        base_score: float
        if self.expected_answer.lower() in response_lower:
            base_score = 1.0
        else:
            # Check alias matches
            alias_matched = False
            for alias in self.answer_aliases:
                if alias.lower() in response_lower:
                    alias_matched = True
                    break

            if alias_matched:
                base_score = 1.0
            else:
                # Fallback: keyword matching
                keywords = extract_keywords(self.expected_answer)
                if not keywords:
                    base_score = 0.0
                else:
                    matched = sum(
                        1 for kw in keywords if kw.lower() in response_lower
                    )
                    base_score = matched / len(keywords)

        # Apply length penalty
        if self.token_budget > 0:
            actual_tokens = len(response.split())
            if actual_tokens > self.token_budget:
                base_score = base_score * (self.token_budget / actual_tokens)

        return max(0.0, min(1.0, base_score))

register_task_type("efficiency", EfficiencyTask)
