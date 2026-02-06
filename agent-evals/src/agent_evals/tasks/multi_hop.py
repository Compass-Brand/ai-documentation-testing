"""Multi-hop reasoning task type for evaluating multi-step question answering.

Scores responses by checking whether each reasoning-chain step is addressed,
using keyword matching (non-stopword words with 3+ characters).  Keywords are
extracted from ``reasoning_chain`` (the expected answers) rather than
``question_decomposition`` (the sub-questions) so that matching tests for
specific factual content instead of generic question terms.

When a keyword is short (3-4 characters) word-boundary matching is used to
avoid false positives from substring collisions.
"""

from __future__ import annotations

import re
from typing import Any

from agent_evals.tasks._utils import extract_keywords
from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type


class MultiHopTask(EvalTask):
    """Task type for evaluating multi-hop reasoning across evidence paragraphs.

    Checks if the response addresses each reasoning-chain step by looking for
    keyword matches from the expected answers.  Falls back to
    question_decomposition only when reasoning_chain is empty or shorter.
    Score = fraction of scorable steps with at least one keyword match.
    Steps with no extractable keywords are excluded from the denominator.
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta: dict[str, Any] = definition.metadata
        self.paragraphs: list[dict[str, Any]] = meta.get("paragraphs", [])
        self.question_decomposition: list[str] = meta.get(
            "question_decomposition", [],
        )
        self.reasoning_chain: list[str] = meta.get("reasoning_chain", [])

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build messages for multi-hop reasoning evaluation.

        Args:
            index_content: The documentation index content.

        Returns:
            List of message dicts with system and user messages.
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that answers questions requiring "
                    "multi-step reasoning. Use the following documentation "
                    "index to find evidence across multiple sources and "
                    "connect them to reach your answer.\n\n"
                    f"{index_content}"
                ),
            },
            {
                "role": "user",
                "content": self.definition.question,
            },
        ]

    def score_response(self, response: str, **kwargs: object) -> float:
        """Score response by checking reasoning-chain step coverage.

        Keywords are extracted from ``reasoning_chain`` (the expected factual
        answers).  Falls back to ``question_decomposition`` only when the
        reasoning chain is empty or shorter.

        Steps with no extractable keywords are excluded from the denominator
        so they neither inflate nor deflate the score.  Short keywords (3-4
        chars) use word-boundary regex to avoid substring false positives.

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (unused).

        Returns:
            Score between 0.0 and 1.0.
        """
        # Choose the best source for expected-answer keywords.
        steps = self.reasoning_chain
        if not steps or (
            len(steps) < len(self.question_decomposition)
        ):
            steps = self.question_decomposition

        if not steps:
            return 1.0

        response_lower = response.lower()
        steps_matched = 0
        steps_counted = 0

        for step in steps:
            keywords = extract_keywords(step)
            if not keywords:
                # No extractable keywords -- skip from denominator entirely
                continue
            steps_counted += 1
            if any(self._keyword_in_response(kw, response_lower) for kw in keywords):
                steps_matched += 1

        if steps_counted == 0:
            return 1.0

        score = steps_matched / steps_counted
        return max(0.0, min(1.0, score))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _keyword_in_response(keyword: str, response_lower: str) -> bool:
        """Check whether *keyword* appears in the lowered response.

        Short keywords (3-4 characters) use word-boundary regex to avoid
        matching inside longer words (e.g. "TTL" inside "throttle").
        Longer keywords (5+ characters) use plain substring matching,
        which is faster and sufficient at that length.
        """
        kw_lower = keyword.lower()
        if len(kw_lower) <= 4:
            return bool(re.search(r"\b" + re.escape(kw_lower) + r"\b", response_lower))
        return kw_lower in response_lower


register_task_type("multi_hop", MultiHopTask)
