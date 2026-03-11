"""Conflicting information task type for evaluating conflict resolution.

Scores responses by checking whether the model resolved conflicting
information correctly based on the expected resolution. Exact match
yields 1.0; fallback uses keyword fraction of non-stopword words found.
"""

from __future__ import annotations

import re
from typing import Any

from agent_evals.tasks._utils import extract_keywords
from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type


class ConflictingTask(EvalTask):
    """Task type for evaluating conflict resolution accuracy.

    Given multiple sources with varying authority levels, checks whether
    the model resolved conflicting information correctly using the
    expected resolution strategy (e.g., highest authority wins).
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta = definition.metadata
        self.sources: list[dict[str, Any]] = meta.get("sources", [])
        self.expected_resolution: str = meta.get("expected_resolution", "")
        self.resolution_strategy: str = meta.get("resolution_strategy", "")

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build messages for conflicting information evaluation.

        Args:
            index_content: The documentation index content.

        Returns:
            List of message dicts with system and user messages.
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that resolves conflicting "
                    "information from multiple documentation sources. "
                    "When sources conflict, determine the most authoritative "
                    "answer.\n\n"
                    f"{index_content}"
                ),
            },
            {
                "role": "user",
                "content": self.definition.question,
            },
        ]

    def score_response(self, response: str, **kwargs: object) -> float:
        """Score response by checking for expected resolution match.

        When expected_resolution contains ``|``, each segment is treated as
        an alternative correct answer — matching ANY alternative scores 1.0.
        Otherwise checks for exact match first, then falls back to keyword
        fraction scoring.

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (unused).

        Returns:
            Score between 0.0 and 1.0.
        """
        if not self.expected_resolution:
            return 0.0

        response_lower = response.lower()

        # Handle pipe-separated alternatives (e.g. "No.|Yes.")
        alternatives = [a.strip() for a in self.expected_resolution.split("|") if a.strip()]
        if len(alternatives) > 1:
            return self._score_alternatives(alternatives, response_lower)

        # Check exact match (case-insensitive)
        if self.expected_resolution.lower() in response_lower:
            return 1.0

        # Fallback: keyword matching
        keywords = extract_keywords(self.expected_resolution)
        if not keywords:
            return 0.0

        matched = sum(1 for kw in keywords if kw.lower() in response_lower)
        return max(0.0, min(1.0, matched / len(keywords)))

    def _score_alternatives(
        self, alternatives: list[str], response_lower: str,
    ) -> float:
        """Score against pipe-separated alternative answers.

        Returns the best score across all alternatives.
        """
        best = 0.0
        for alt in alternatives:
            alt_clean = alt.strip(".,:;!?")
            alt_lower = alt_clean.lower()
            if not alt_lower:
                continue
            # Word-boundary match to avoid false positives on short words
            pattern = r"\b" + re.escape(alt_lower) + r"\b"
            if re.search(pattern, response_lower):
                return 1.0
            # Keyword match for longer alternatives
            keywords = extract_keywords(alt)
            if keywords:
                matched = sum(1 for kw in keywords if kw.lower() in response_lower)
                score = matched / len(keywords)
                best = max(best, score)
        return max(0.0, min(1.0, best))

register_task_type("conflicting", ConflictingTask)
