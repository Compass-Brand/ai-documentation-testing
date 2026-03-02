"""Compositional task type for evaluating multi-part question answering.

Scores responses by checking whether each sub-task's expected answer
appears (case-insensitive) in the response.  Score = fraction of
sub-tasks whose expected_answer is found.
"""

from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz, utils as fuzz_utils

from agent_evals.tasks._utils import extract_keywords
from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type

_FUZZY_CUTOFF = 80.0  # Minimum partial_ratio to count a keyword as matched


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
            self.sub_tasks = [
                {"question": q, "expected_answer": a}
                for q, a in zip(questions, answers)
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
        if expected_lower in response_lower:
            return 1.0
        keywords = extract_keywords(expected_lower)
        if not keywords:
            return 0.0
        matched = 0
        for kw in keywords:
            score = fuzz.partial_ratio(
                kw, response_lower,
                processor=fuzz_utils.default_process,
                score_cutoff=_FUZZY_CUTOFF,
            )
            if score > 0:
                matched += 1
        return matched / len(keywords)

    def score_response(self, response: str, **kwargs: object) -> float:
        """Score response by checking sub-task answer coverage.

        For each sub-task with a non-empty expected_answer, checks whether
        the answer appears (case-insensitive) in the response, falling back
        to fuzzy keyword matching via rapidfuzz.
        Score = total_score / scored_count (only non-empty sub-tasks count).

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (unused).

        Returns:
            Score between 0.0 and 1.0.
        """
        if not self.sub_tasks:
            return 1.0

        response_lower = response.lower()
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
        score = total_score / scored_count
        return max(0.0, min(1.0, score))


register_task_type("compositional", CompositionalTask)
