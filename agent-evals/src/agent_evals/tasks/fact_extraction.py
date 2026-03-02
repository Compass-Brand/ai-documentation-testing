"""Fact extraction task type for evaluating factual accuracy.

Scores responses using a multi-layer matching cascade: exact match yields 1.0,
alias match yields 1.0, fuzzy match (rapidfuzz) yields 0.9 or 0.7, and
keyword fallback computes fraction of non-stopword keywords found.
"""

from __future__ import annotations

from rapidfuzz import fuzz, utils as fuzz_utils

from agent_evals.tasks._utils import extract_keywords
from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type


class FactExtractionTask(EvalTask):
    """Task type for evaluating factual answer accuracy.

    Checks if the expected answer or any alias appears in the response
    (exact match = 1.0). Uses fuzzy matching for paraphrases (0.9 or 0.7).
    Falls back to computing the fraction of non-stopword keywords from
    the expected answer found in the response.
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta = definition.metadata
        self.expected_answer: str = meta.get("expected_answer", "")
        self.answer_aliases: list[str] = meta.get("answer_aliases", [])
        self.source_location: str = meta.get("source_location", "")
        self.fact_type: str = meta.get("fact_type", "")

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build messages for fact extraction evaluation.

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
        """Score response using multi-layer matching against expected answer.

        Layers (in order of precedence):
        1. Exact match of expected_answer -> 1.0
        2. Alias match -> 1.0
        3. Fuzzy match (token_set_ratio >= 85) -> 0.9
        4. Fuzzy match (token_set_ratio >= 70) -> 0.7
        5. Keyword fallback -> fraction of keywords found

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (unused).

        Returns:
            Score between 0.0 and 1.0.
        """
        if not self.expected_answer:
            return 0.0

        response_lower = response.lower()

        # Layer 1: Exact match of expected answer
        if self.expected_answer.lower() in response_lower:
            return 1.0

        # Layer 2: Alias matches
        for alias in self.answer_aliases:
            if alias.lower() in response_lower:
                return 1.0

        # Layer 3: Fuzzy matching — catches paraphrases and abbreviations
        fuzzy_score = fuzz.token_set_ratio(
            self.expected_answer.lower(),
            response_lower,
            processor=fuzz_utils.default_process,
        )
        if fuzzy_score >= 85.0:
            return 0.9
        if fuzzy_score >= 70.0:
            return 0.7

        # Layer 4: Keyword fallback
        keywords = extract_keywords(self.expected_answer)
        if not keywords:
            return 0.0

        matched = sum(1 for kw in keywords if kw.lower() in response_lower)
        return max(0.0, min(1.0, matched / len(keywords)))


register_task_type("fact_extraction", FactExtractionTask)
