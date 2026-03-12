"""Compositional task type for evaluating multi-part question answering.

Scores responses using 3 weighted axes: completeness (50%),
integration quality (30%), and organization (20%).
"""

from __future__ import annotations

import re
from typing import Any

from rapidfuzz import fuzz, utils as fuzz_utils

from agent_evals.tasks._utils import contains_text, extract_keywords
from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type

_FUZZY_CUTOFF = 80.0  # Minimum partial_ratio to count a keyword as matched

# Axis weights for multi-axis scoring (must sum to 1.0)
_W_COMPLETENESS = 0.50
_W_INTEGRATION = 0.30
_W_ORGANIZATION = 0.20


class CompositionalTask(EvalTask):
    """Task type for evaluating compositional reasoning.

    A compositional question is decomposed into sub-tasks, each with a
    question and expected answer.  The score is the fraction of sub-tasks
    whose expected answer appears in the LLM response.
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta: dict[str, Any] = definition.metadata
        self.composition_type: str = meta.get("composition_type", "")

        # Support both formats:
        # 1. sub_tasks: [{question, expected_answer}, ...]
        # 2. sub_questions: [...] + expected_answers: [...] (parallel lists)
        raw_sub_tasks = meta.get("sub_tasks", [])
        if raw_sub_tasks:
            self.sub_tasks: list[dict[str, Any]] = raw_sub_tasks
        else:
            questions = meta.get("sub_questions", [])
            answers = meta.get("expected_answers", [])
            if len(questions) != len(answers):
                msg = (
                    f"sub_questions ({len(questions)}) and "
                    f"expected_answers ({len(answers)}) must have the "
                    f"same length"
                )
                raise ValueError(msg)
            self.sub_tasks = [
                {"question": q, "expected_answer": a}
                for q, a in zip(questions, answers, strict=True)
            ]

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build messages for compositional reasoning evaluation.

        Args:
            index_content: The documentation index content.

        Returns:
            List of message dicts with system and user messages.
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that answers compositional "
                    "questions. Break the question into sub-parts, answer "
                    "each sub-part using the documentation index, then "
                    "combine the answers.\n\n"
                    f"{index_content}"
                ),
            },
            {
                "role": "user",
                "content": self.definition.question,
            },
        ]

    def _score_sub_answer(self, expected_lower: str, response_lower: str) -> float:
        """Score one sub-answer using exact containment, then fuzzy keyword coverage."""
        if contains_text(expected_lower, response_lower):
            return 1.0
        keywords = extract_keywords(expected_lower)
        if not keywords:
            return 0.0
        matched = 0
        for kw in keywords:
            # Short keywords (<=4 chars) are prone to partial_ratio inflation
            # (e.g., "port" matches inside "transportation").  Use word-boundary
            # matching instead to avoid false positives.
            if len(kw) <= 4:
                if contains_text(kw, response_lower):
                    matched += 1
            else:
                score = fuzz.partial_ratio(
                    kw, response_lower,
                    processor=fuzz_utils.default_process,
                    score_cutoff=_FUZZY_CUTOFF,
                )
                if score > 0:
                    matched += 1
        return matched / len(keywords)

    def score_response(self, response: str, **kwargs: object) -> float:
        """Score response using 3-axis weighted scoring.

        Axes:
        - Completeness (50%): fraction of sub-tasks whose expected answer is found
        - Integration quality (30%): cross-sub-task keyword co-occurrence in sentences
        - Organization (20%): structural markers (First/Second, numbered lists, headers)

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (unused).

        Returns:
            Score between 0.0 and 1.0.
        """
        if not self.sub_tasks:
            return 1.0

        # No scorable sub-tasks (all empty expected_answer) → vacuous truth
        has_scorable = any(
            sub.get("expected_answer", "").strip() for sub in self.sub_tasks
        )
        if not has_scorable:
            return 1.0

        response_lower = response.lower()

        completeness = self._score_completeness(response_lower)
        integration = self._score_integration(response_lower)
        organization = self._score_organization(response_lower)

        score = (
            completeness * _W_COMPLETENESS
            + integration * _W_INTEGRATION
            + organization * _W_ORGANIZATION
        )
        return max(0.0, min(1.0, score))

    def _score_completeness(self, response_lower: str) -> float:
        """Axis 1: Sub-task completeness — wraps existing sub-answer scoring."""
        total_score = 0.0
        scored_count = 0

        for sub_task in self.sub_tasks:
            expected: str = sub_task.get("expected_answer", "")
            if not expected:
                continue
            scored_count += 1
            total_score += self._score_sub_answer(expected.lower(), response_lower)

        if scored_count == 0:
            return 1.0
        return total_score / scored_count

    def _score_integration(self, response_lower: str) -> float:
        """Axis 2: Integration quality — cross-sub-task keyword co-occurrence.

        For each pair of adjacent sub-tasks, checks whether keywords from
        both appear within the same sentence (split on ". ").
        """
        scorable = [
            sub for sub in self.sub_tasks
            if sub.get("expected_answer", "").strip()
        ]
        if len(scorable) < 2:
            return 0.0

        sentences = [s.strip() for s in response_lower.split(". ") if s.strip()]
        if not sentences:
            return 0.0

        # Extract keywords per sub-task
        sub_keywords: list[list[str]] = []
        for sub in scorable:
            kws = extract_keywords(sub["expected_answer"])
            sub_keywords.append([kw.lower() for kw in kws])

        # Check adjacent pair co-occurrence
        pairs_found = 0
        total_pairs = len(scorable) - 1

        for i in range(total_pairs):
            kws_a = sub_keywords[i]
            kws_b = sub_keywords[i + 1]
            if not kws_a or not kws_b:
                continue
            for sentence in sentences:
                has_a = any(kw in sentence for kw in kws_a)
                has_b = any(kw in sentence for kw in kws_b)
                if has_a and has_b:
                    pairs_found += 1
                    break

        return pairs_found / total_pairs if total_pairs > 0 else 0.0

    _ORDINAL_PATTERN: re.Pattern[str] = re.compile(
        r"\b(first|second|third|fourth|fifth)\b"
    )
    _NUMBERED_PATTERN: re.Pattern[str] = re.compile(r"^\s*\d+[\.\)]\s", re.MULTILINE)
    _HEADER_PATTERN: re.Pattern[str] = re.compile(r"^#{1,6}\s", re.MULTILINE)

    def _score_organization(self, response_lower: str) -> float:
        """Axis 3: Response organization — structural markers."""
        markers = 0
        if self._ORDINAL_PATTERN.search(response_lower):
            markers += 1
        if self._NUMBERED_PATTERN.search(response_lower):
            markers += 1
        if self._HEADER_PATTERN.search(response_lower):
            markers += 1
        # Any marker present = partial credit, 2+ = full credit
        if markers >= 2:
            return 1.0
        if markers == 1:
            return 0.5
        return 0.0


register_task_type("compositional", CompositionalTask)
