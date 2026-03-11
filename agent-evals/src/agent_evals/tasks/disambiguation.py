"""Disambiguation task type for evaluating interpretation selection.

Scores responses on three axes:
1. Coverage (40%): Did the response mention ALL interpretations?
2. Correctness (40%): Did it identify the expected interpretation?
3. Awareness (20%): Did it acknowledge the ambiguity explicitly?

A response that just answers the question without recognising ambiguity
scores low (~0.4 max), producing meaningful variance across trials.
"""

from __future__ import annotations

from typing import Any

from agent_evals.tasks._utils import extract_keywords
from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type

_AMBIGUITY_PHRASES = (
    "ambiguous",
    "multiple interpretations",
    "could mean",
    "could refer to",
    "depends on",
    "several meanings",
    "two possible",
    "different meanings",
    "interpret",
)

# Weights for the three scoring axes
_W_COVERAGE = 0.40
_W_CORRECTNESS = 0.40
_W_AWARENESS = 0.20


class DisambiguationTask(EvalTask):
    """Task type for evaluating disambiguation accuracy.

    Given a set of possible interpretations (each with a label and answer),
    checks whether the model:
    1. Recognised that the question is ambiguous (awareness)
    2. Addressed all interpretations (coverage)
    3. Correctly identified the expected interpretation (correctness)
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta = definition.metadata
        self.interpretations: list[dict[str, Any]] = meta.get("interpretations", [])
        self.expected_interpretation: str = meta.get("expected_interpretation", "")

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build messages for disambiguation evaluation.

        The prompt explicitly asks the model to identify all possible
        interpretations, explain each, and recommend the best one.

        Args:
            index_content: The documentation index content.

        Returns:
            List of message dicts with system and user messages.
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that disambiguates questions "
                    "using a documentation index. When a question could have "
                    "multiple interpretations, list ALL possible meanings, "
                    "explain each one, then recommend which interpretation "
                    "is most likely correct and why.\n\n"
                    f"{index_content}"
                ),
            },
            {
                "role": "user",
                "content": self.definition.question,
            },
        ]

    def _keyword_coverage(
        self, answer: str, response_lower: str,
    ) -> float:
        """Fraction of non-stopword keywords from *answer* found in *response_lower*."""
        keywords = extract_keywords(answer)
        if not keywords:
            return 0.0
        hits = sum(1 for kw in keywords if kw.lower() in response_lower)
        return hits / len(keywords)

    def _label_present(self, label: str, response_lower: str) -> bool:
        """Check if a label (or its space-normalised form) appears."""
        lbl = label.lower()
        return lbl in response_lower or lbl.replace("_", " ") in response_lower

    def score_response(self, response: str, **kwargs: object) -> float:
        """Score response on coverage, correctness, and awareness.

        Scoring axes
        ------------
        **Coverage (40%)** -- fraction of *all* interpretations whose
        keywords appear in the response (at >= 30% keyword hit rate) or
        whose label is mentioned.  A response that only addresses the
        expected interpretation scores coverage = 1/N.

        **Correctness (40%)** -- keyword coverage of the *expected*
        interpretation's answer in the response, combined with label
        detection.

        **Awareness (20%)** -- binary check for ambiguity-acknowledgement
        phrases (e.g. "could mean", "multiple interpretations").

        Final score = w_cov * coverage + w_cor * correctness + w_awa * awareness,
        clamped to [0.0, 1.0].

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (unused).

        Returns:
            Score between 0.0 and 1.0.
        """
        if not self.expected_interpretation or not self.interpretations:
            return 0.0

        # Find the expected interpretation dict
        expected: dict[str, Any] | None = None
        for interp in self.interpretations:
            if interp.get("label") == self.expected_interpretation:
                expected = interp
                break

        if expected is None:
            return 0.0

        response_lower = response.lower()
        n_interps = len(self.interpretations)

        # ---- 1. Coverage: how many interpretations are addressed? ----
        addressed = 0
        for interp in self.interpretations:
            answer = interp.get("answer", "")
            label = interp.get("label", "")
            kw_cov = self._keyword_coverage(answer, response_lower)
            label_hit = self._label_present(label, response_lower)
            if kw_cov >= 0.30 or label_hit:
                addressed += 1
        coverage_score = addressed / n_interps if n_interps > 0 else 0.0

        # ---- 2. Correctness: expected interpretation answered well? ----
        expected_answer: str = expected.get("answer", "")
        expected_label: str = expected.get("label", "")

        kw_score = self._keyword_coverage(expected_answer, response_lower)
        label_hit = self._label_present(expected_label, response_lower)
        # Label mention alone is worth 0.5 correctness
        correctness_score = max(kw_score, 0.5 if label_hit else 0.0)

        # ---- 3. Awareness: does the response acknowledge ambiguity? ----
        awareness_score = 1.0 if any(
            p in response_lower for p in _AMBIGUITY_PHRASES
        ) else 0.0

        total = (
            _W_COVERAGE * coverage_score
            + _W_CORRECTNESS * correctness_score
            + _W_AWARENESS * awareness_score
        )
        return min(1.0, max(0.0, total))


register_task_type("disambiguation", DisambiguationTask)
