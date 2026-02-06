"""Tests for AbstentionMetric."""

from __future__ import annotations

from agent_evals.metrics.abstention import AbstentionMetric
from agent_evals.metrics.base import MetricContext


def _make_context(
    answerable: bool | None = None,
) -> MetricContext:
    """Helper to build a MetricContext for abstention tests."""
    task_def: dict[str, object] = {"type": "lookup"}
    if answerable is not None:
        task_def["answerable"] = answerable
    return MetricContext(
        task_definition=task_def,
        index_content="",
        source_documents=[],
        tool_calls=[],
        attempt_number=1,
    )


class TestAbstentionMetric:
    """Tests for AbstentionMetric."""

    def test_name(self) -> None:
        """Metric name should be 'abstention'."""
        metric = AbstentionMetric()
        assert metric.name == "abstention"

    def test_unanswerable_correct_abstention(self) -> None:
        """Unanswerable task + correct abstention phrase -> 1.0."""
        ctx = _make_context(answerable=False)
        response = "This cannot be determined from the provided documentation."
        score = AbstentionMetric().compute(response, ctx)
        assert score == 1.0

    def test_unanswerable_incorrect_answer(self) -> None:
        """Unanswerable task + no abstention phrase -> 0.0."""
        ctx = _make_context(answerable=False)
        response = "The function returns an integer value of 42."
        score = AbstentionMetric().compute(response, ctx)
        assert score == 0.0

    def test_answerable_correct_answer(self) -> None:
        """Answerable task + no abstention phrase -> 1.0."""
        ctx = _make_context(answerable=True)
        response = "The function returns an integer value of 42."
        score = AbstentionMetric().compute(response, ctx)
        assert score == 1.0

    def test_answerable_incorrect_abstention(self) -> None:
        """Answerable task + abstention phrase -> 0.0."""
        ctx = _make_context(answerable=True)
        response = "I don't know the answer to this question."
        score = AbstentionMetric().compute(response, ctx)
        assert score == 0.0

    def test_no_answerable_field_correct_answer(self) -> None:
        """No answerable field (treated as answerable) + no abstention -> 1.0."""
        ctx = _make_context(answerable=None)
        response = "The function processes data efficiently."
        score = AbstentionMetric().compute(response, ctx)
        assert score == 1.0

    def test_no_answerable_field_incorrect_abstention(self) -> None:
        """No answerable field (treated as answerable) + abstention -> 0.0."""
        ctx = _make_context(answerable=None)
        response = "I am unable to find the relevant information."
        score = AbstentionMetric().compute(response, ctx)
        assert score == 0.0

    def test_various_abstention_phrases(self) -> None:
        """Various abstention phrases should all be detected."""
        phrases = [
            "This information is not available in the docs.",
            "It cannot be determined from the index.",
            "There is no information about this topic.",
            "The answer was not found in the documentation.",
            "I don't have enough context to answer.",
            "I was unable to find the relevant section.",
            "This is not in the documentation provided.",
            "This question is unanswerable given the context.",
            "I don't know the answer.",
            "I cannot answer this question.",
        ]
        ctx = _make_context(answerable=False)
        metric = AbstentionMetric()
        for phrase in phrases:
            score = metric.compute(phrase, ctx)
            assert score == 1.0, f"Failed to detect abstention in: {phrase!r}"

    def test_case_insensitive_detection(self) -> None:
        """Abstention phrase detection should be case-insensitive."""
        ctx = _make_context(answerable=False)
        response = "NOT AVAILABLE in the provided documentation."
        score = AbstentionMetric().compute(response, ctx)
        assert score == 1.0
