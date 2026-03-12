"""Efficiency task type for evaluating concise answering ability.

Scores responses on correctness (exact/alias/fuzzy/keyword match) and then
applies a length penalty when the response exceeds the token budget.
Token count uses LiteLLM's tokenizer via count_tokens().
"""

from __future__ import annotations

from rapidfuzz import fuzz
from rapidfuzz import utils as fuzz_utils

from agent_evals.llm.token_counter import count_tokens
from agent_evals.tasks._utils import contains_text, extract_keywords, fuzzy_to_continuous_score
from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type


class EfficiencyTask(EvalTask):
    """Task type for evaluating answer efficiency (correctness + conciseness).

    Checks if the expected answer or any alias appears in the response
    (exact match = 1.0 base score). Uses fuzzy matching for near-matches.
    Falls back to keyword fraction. Then applies a length penalty if the
    response exceeds the token budget.
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta = definition.metadata
        self.expected_answer: str = meta.get("expected_answer", "")
        self.answer_aliases: list[str] = meta.get("answer_aliases", [])
        self.token_budget: int = meta.get("token_budget", 0)
        self.message_limit: int = meta.get("message_limit", 0)
        self._expected_lower: str = self.expected_answer.lower()

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

        Base score: 1.0 for exact/alias match, [0.5, 1.0] for fuzzy match,
        else keyword fraction. Length penalty: if word count > token_budget,
        multiply by token_budget / actual_tokens. Clamped to [0, 1].

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
        if contains_text(self._expected_lower, response_lower):
            base_score = 1.0
        else:
            # Check alias matches
            alias_matched = False
            for alias in self.answer_aliases:
                if contains_text(alias.lower(), response_lower):
                    alias_matched = True
                    break

            if alias_matched:
                base_score = 1.0
            else:
                # Fuzzy matching — catches paraphrases and abbreviations
                fuzzy_score = fuzz.token_set_ratio(
                    self._expected_lower,
                    response_lower,
                    processor=fuzz_utils.default_process,
                )
                continuous = fuzzy_to_continuous_score(fuzzy_score)
                if continuous is not None:
                    base_score = continuous
                else:
                    # Fallback: keyword matching
                    keywords = extract_keywords(self.expected_answer)
                    if not keywords:
                        base_score = 0.0
                    else:
                        matched = sum(
                            1 for kw in keywords
                            if contains_text(kw.lower(), response_lower)
                        )
                        base_score = matched / len(keywords)

        # Apply length penalty
        if self.token_budget > 0:
            actual_tokens = count_tokens(response)
            if actual_tokens > self.token_budget:
                base_score = base_score * (self.token_budget / actual_tokens)

        return max(0.0, min(1.0, base_score))

register_task_type("efficiency", EfficiencyTask)
