"""Robustness task type for evaluating answer stability under perturbation.

Reuses the same scoring cascade as FactExtractionTask: exact / alias match
yields 1.0, fuzzy match (rapidfuzz) yields 0.9 or 0.7, and keyword fallback
computes fraction of non-stopword keywords found.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from rapidfuzz import fuzz
from rapidfuzz import utils as fuzz_utils

from agent_evals.tasks._utils import contains_text, extract_keywords, fuzzy_to_continuous_score
from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type


def _strip_diacritics(text: str) -> str:
    """Normalize Unicode text by removing combining diacritical marks.

    Decomposes characters via NFD then strips combining marks, so that
    'cafe' becomes 'cafe' and 'resume' becomes 'resume'.
    """
    nfd = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")


class RobustnessTask(EvalTask):
    """Task type for evaluating answer stability under input perturbation.

    A perturbed version of a base task (e.g. paraphrased, with typos,
    or reordered).  Scoring mirrors FactExtractionTask: exact or alias
    match = 1.0, fuzzy match = 0.9/0.7, keyword-fraction fallback.
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta: dict[str, Any] = definition.metadata
        self.base_task_id: str = meta.get("base_task_id", "")
        self.perturbation_type: str = meta.get("perturbation_type", "")
        self.expected_answer: str = meta.get("expected_answer", "")
        self.answer_aliases: list[str] = meta.get("answer_aliases", [])
        self._expected_lower: str = self.expected_answer.lower()

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build messages for robustness evaluation.

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
        if contains_text(self._expected_lower, response_lower):
            return 1.0

        # Layer 2: Alias matches
        for alias in self.answer_aliases:
            if contains_text(alias.lower(), response_lower):
                return 1.0

        # Normalize diacritics for fuzzy and keyword layers
        norm_expected = _strip_diacritics(self._expected_lower)
        norm_response = _strip_diacritics(response_lower)

        # Layer 3: Fuzzy matching -- catches paraphrases and abbreviations
        fuzzy_score = fuzz.token_set_ratio(
            norm_expected,
            norm_response,
            processor=fuzz_utils.default_process,
        )
        continuous = fuzzy_to_continuous_score(fuzzy_score)
        if continuous is not None:
            return continuous

        # Layer 4: Keyword fallback
        keywords = extract_keywords(self.expected_answer)
        if not keywords:
            return 0.0

        matched = sum(
            1 for kw in keywords
            if contains_text(_strip_diacritics(kw.lower()), norm_response)
        )
        return max(0.0, min(1.0, matched / len(keywords)))


register_task_type("robustness", RobustnessTask)
