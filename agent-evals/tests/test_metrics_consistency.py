"""Tests for ConsistencyMetric."""

from __future__ import annotations

import pytest
from agent_evals.metrics.base import MetricContext
from agent_evals.metrics.consistency import ConsistencyMetric


def _make_context(
    prior_responses: list[str] | None = None,
) -> MetricContext:
    """Helper to build a MetricContext for consistency tests."""
    task_def: dict[str, object] = {"type": "lookup"}
    if prior_responses is not None:
        task_def["prior_responses"] = prior_responses
    return MetricContext(
        task_definition=task_def,
        index_content="",
        source_documents=[],
        tool_calls=[],
        attempt_number=1,
    )


class TestConsistencyMetric:
    """Tests for ConsistencyMetric."""

    def test_name(self) -> None:
        """Metric name should be 'consistency'."""
        metric = ConsistencyMetric()
        assert metric.name == "consistency"

    def test_no_prior_responses_returns_one(self) -> None:
        """No prior responses means first response -> 1.0."""
        ctx = _make_context(prior_responses=None)
        score = ConsistencyMetric().compute("some response", ctx)
        assert score == 1.0

    def test_empty_prior_responses_list_returns_one(self) -> None:
        """Empty prior_responses list -> 1.0."""
        ctx = _make_context(prior_responses=[])
        score = ConsistencyMetric().compute("some response", ctx)
        assert score == 1.0

    def test_identical_prior_response_returns_one(self) -> None:
        """Identical response to single prior -> 1.0."""
        response = "Python is a programming language"
        ctx = _make_context(prior_responses=[response])
        score = ConsistencyMetric().compute(response, ctx)
        assert score == pytest.approx(1.0)

    def test_completely_different_response_near_zero(self) -> None:
        """Completely different tokens -> close to 0.0."""
        response = "alpha beta gamma delta"
        ctx = _make_context(prior_responses=["epsilon zeta eta theta"])
        score = ConsistencyMetric().compute(response, ctx)
        assert score == pytest.approx(0.0)

    def test_partially_overlapping_response(self) -> None:
        """Partial overlap should produce a score between 0 and 1."""
        response = "alpha beta gamma delta"
        ctx = _make_context(prior_responses=["alpha beta epsilon zeta"])
        score = ConsistencyMetric().compute(response, ctx)
        assert 0.0 < score < 1.0

    def test_empty_response_and_empty_prior(self) -> None:
        """Both current and prior responses empty -> 1.0."""
        ctx = _make_context(prior_responses=[""])
        score = ConsistencyMetric().compute("", ctx)
        assert score == 1.0

    def test_multiple_prior_responses_averaged(self) -> None:
        """With multiple priors, result is the mean Jaccard similarity."""
        response = "alpha beta gamma"
        # Prior 1: identical -> Jaccard = 1.0
        # Prior 2: completely different -> Jaccard = 0.0
        ctx = _make_context(
            prior_responses=["alpha beta gamma", "delta epsilon zeta"]
        )
        score = ConsistencyMetric().compute(response, ctx)
        assert score == pytest.approx(0.5)

    def test_score_bounded_zero_to_one(self) -> None:
        """Score should always be in [0.0, 1.0]."""
        ctx = _make_context(prior_responses=["word1 word2", "word3 word4"])
        score = ConsistencyMetric().compute("word5 word6 word7", ctx)
        assert 0.0 <= score <= 1.0
