"""Tests for agent-evals metrics module."""

from __future__ import annotations

import pytest
from agent_evals.metrics.base import Metric, MetricContext
from agent_evals.metrics.faithfulness import FaithfulnessMetric
from agent_evals.metrics.first_attempt import FirstAttemptMetric
from agent_evals.metrics.tool_calls import ToolCallMetric

# ---------------------------------------------------------------------------
# MetricContext tests
# ---------------------------------------------------------------------------


class TestMetricContext:
    """Tests for MetricContext dataclass."""

    def test_create_with_all_fields(self) -> None:
        """MetricContext can be created with all fields populated."""
        ctx = MetricContext(
            task_definition={"type": "lookup", "question": "What does foo do?"},
            index_content="# Module Foo\nFoo handles bar.",
            source_documents=["doc1 content", "doc2 content"],
            tool_calls=[{"tool": "read_file", "path": "foo.py"}],
            attempt_number=1,
            task_score=0.9,
        )
        assert ctx.task_definition == {"type": "lookup", "question": "What does foo do?"}
        assert ctx.index_content == "# Module Foo\nFoo handles bar."
        assert ctx.source_documents == ["doc1 content", "doc2 content"]
        assert ctx.tool_calls == [{"tool": "read_file", "path": "foo.py"}]
        assert ctx.attempt_number == 1
        assert ctx.task_score == 0.9

    def test_create_with_defaults(self) -> None:
        """MetricContext should default task_score to None."""
        ctx = MetricContext(
            task_definition={},
            index_content="",
            source_documents=[],
            tool_calls=[],
            attempt_number=1,
        )
        assert ctx.task_score is None

    def test_attempt_number_is_one_based(self) -> None:
        """attempt_number should be 1-based (first attempt = 1)."""
        ctx = MetricContext(
            task_definition={},
            index_content="",
            source_documents=[],
            tool_calls=[],
            attempt_number=1,
        )
        assert ctx.attempt_number == 1


# ---------------------------------------------------------------------------
# Metric ABC tests
# ---------------------------------------------------------------------------


class TestMetricABC:
    """Tests for the abstract Metric base class."""

    def test_cannot_instantiate_abc(self) -> None:
        """Metric ABC cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Metric()  # type: ignore[abstract]

    def test_subclass_must_implement_name(self) -> None:
        """Subclass without name property should fail to instantiate."""

        class Incomplete(Metric):
            def compute(self, response: str, context: MetricContext) -> float:
                return 0.0

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_subclass_must_implement_compute(self) -> None:
        """Subclass without compute should fail to instantiate."""

        class Incomplete(Metric):
            @property
            def name(self) -> str:
                return "incomplete"

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_valid_subclass_instantiates(self) -> None:
        """A fully implemented subclass should instantiate."""

        class Complete(Metric):
            @property
            def name(self) -> str:
                return "complete"

            def compute(self, response: str, context: MetricContext) -> float:
                return 0.5

        metric = Complete()
        assert metric.name == "complete"


# ---------------------------------------------------------------------------
# FaithfulnessMetric tests
# ---------------------------------------------------------------------------


def _make_context(
    source_documents: list[str],
    *,
    tool_calls: list[dict[str, str]] | None = None,
    attempt_number: int = 1,
    task_score: float | None = None,
) -> MetricContext:
    """Helper to build a MetricContext with sensible defaults."""
    return MetricContext(
        task_definition={"type": "lookup"},
        index_content="index content",
        source_documents=source_documents,
        tool_calls=tool_calls or [],
        attempt_number=attempt_number,
        task_score=task_score,
    )


class TestFaithfulnessMetric:
    """Tests for FaithfulnessMetric (keyword-overlap approximation)."""

    def test_name(self) -> None:
        """Metric name should be 'faithfulness'."""
        metric = FaithfulnessMetric()
        assert metric.name == "faithfulness"

    def test_response_matching_sources_high_score(self) -> None:
        """Response whose words overlap heavily with sources gets high score."""
        sources = [
            "Python is a programming language. It supports multiple paradigms.",
            "Django is a web framework written in Python.",
        ]
        response = "Python is a programming language that supports multiple paradigms."
        ctx = _make_context(source_documents=sources)
        score = FaithfulnessMetric().compute(response, ctx)
        assert score >= 0.7, f"Expected high score, got {score}"

    def test_response_not_matching_sources_low_score(self) -> None:
        """Response with words not in sources gets low score."""
        sources = [
            "Python is a programming language.",
        ]
        response = "Kubernetes orchestrates containerized microservices across cloud infrastructure."
        ctx = _make_context(source_documents=sources)
        score = FaithfulnessMetric().compute(response, ctx)
        assert score <= 0.3, f"Expected low score, got {score}"

    def test_empty_response_returns_zero(self) -> None:
        """Empty response should score 0.0."""
        ctx = _make_context(source_documents=["some content here"])
        score = FaithfulnessMetric().compute("", ctx)
        assert score == 0.0

    def test_empty_sources_returns_zero(self) -> None:
        """No source documents should score 0.0."""
        ctx = _make_context(source_documents=[])
        score = FaithfulnessMetric().compute("some response text", ctx)
        assert score == 0.0

    def test_score_bounded_zero_to_one(self) -> None:
        """Score should always be between 0.0 and 1.0."""
        sources = ["alpha beta gamma"]
        response = "alpha beta gamma delta epsilon"
        ctx = _make_context(source_documents=sources)
        score = FaithfulnessMetric().compute(response, ctx)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# ToolCallMetric tests
# ---------------------------------------------------------------------------


class TestToolCallMetric:
    """Tests for ToolCallMetric."""

    def test_name(self) -> None:
        """Metric name should be 'tool_calls'."""
        metric = ToolCallMetric()
        assert metric.name == "tool_calls"

    def test_zero_calls_returns_one(self) -> None:
        """Zero tool calls means perfect efficiency => 1.0."""
        ctx = _make_context(source_documents=[], tool_calls=[])
        score = ToolCallMetric(max_expected=10).compute("response", ctx)
        assert score == 1.0

    def test_max_expected_calls_returns_zero(self) -> None:
        """Exactly max_expected calls => 0.0."""
        calls = [{"tool": "read_file", "path": f"file{i}.py"} for i in range(10)]
        ctx = _make_context(source_documents=[], tool_calls=calls)
        score = ToolCallMetric(max_expected=10).compute("response", ctx)
        assert score == 0.0

    def test_calls_above_max_capped_at_zero(self) -> None:
        """More than max_expected calls should still be 0.0 (not negative)."""
        calls = [{"tool": "search", "query": f"q{i}"} for i in range(20)]
        ctx = _make_context(source_documents=[], tool_calls=calls)
        score = ToolCallMetric(max_expected=10).compute("response", ctx)
        assert score == 0.0

    def test_half_calls_returns_half(self) -> None:
        """Half of max_expected calls => 0.5."""
        calls = [{"tool": "read_file"} for _ in range(5)]
        ctx = _make_context(source_documents=[], tool_calls=calls)
        score = ToolCallMetric(max_expected=10).compute("response", ctx)
        assert score == pytest.approx(0.5)

    def test_default_max_expected(self) -> None:
        """Default max_expected should be 10."""
        metric = ToolCallMetric()
        assert metric.max_expected == 10

    def test_score_bounded_zero_to_one(self) -> None:
        """Score should always be between 0.0 and 1.0."""
        calls = [{"tool": "read"} for _ in range(3)]
        ctx = _make_context(source_documents=[], tool_calls=calls)
        score = ToolCallMetric(max_expected=7).compute("response", ctx)
        assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# FirstAttemptMetric tests
# ---------------------------------------------------------------------------


class TestFirstAttemptMetric:
    """Tests for FirstAttemptMetric."""

    def test_name(self) -> None:
        """Metric name should be 'first_attempt'."""
        metric = FirstAttemptMetric()
        assert metric.name == "first_attempt"

    def test_first_attempt_good_score_returns_one(self) -> None:
        """First attempt with task_score >= threshold => 1.0."""
        ctx = _make_context(
            source_documents=[],
            attempt_number=1,
            task_score=0.8,
        )
        score = FirstAttemptMetric(success_threshold=0.5).compute("response", ctx)
        assert score == 1.0

    def test_second_attempt_returns_zero(self) -> None:
        """Non-first attempt always => 0.0, regardless of score."""
        ctx = _make_context(
            source_documents=[],
            attempt_number=2,
            task_score=1.0,
        )
        score = FirstAttemptMetric().compute("response", ctx)
        assert score == 0.0

    def test_first_attempt_bad_score_returns_zero(self) -> None:
        """First attempt with task_score below threshold => 0.0."""
        ctx = _make_context(
            source_documents=[],
            attempt_number=1,
            task_score=0.3,
        )
        score = FirstAttemptMetric(success_threshold=0.5).compute("response", ctx)
        assert score == 0.0

    def test_first_attempt_no_task_score_returns_zero(self) -> None:
        """First attempt with no task_score (None) => 0.0."""
        ctx = _make_context(
            source_documents=[],
            attempt_number=1,
            task_score=None,
        )
        score = FirstAttemptMetric().compute("response", ctx)
        assert score == 0.0

    def test_default_threshold(self) -> None:
        """Default success_threshold should be 0.5."""
        metric = FirstAttemptMetric()
        assert metric.success_threshold == 0.5

    def test_first_attempt_score_at_threshold_returns_one(self) -> None:
        """First attempt with task_score exactly at threshold => 1.0."""
        ctx = _make_context(
            source_documents=[],
            attempt_number=1,
            task_score=0.5,
        )
        score = FirstAttemptMetric(success_threshold=0.5).compute("response", ctx)
        assert score == 1.0


# ---------------------------------------------------------------------------
# Public exports tests
# ---------------------------------------------------------------------------


class TestPublicExports:
    """Tests for the metrics package public exports."""

    def test_can_import_from_metrics_package(self) -> None:
        """All public classes should be importable from agent_evals.metrics."""
        from agent_evals.metrics import (
            FaithfulnessMetric,
            FirstAttemptMetric,
            Metric,
            MetricContext,
            ToolCallMetric,
        )

        assert Metric is not None
        assert MetricContext is not None
        assert FaithfulnessMetric is not None
        assert ToolCallMetric is not None
        assert FirstAttemptMetric is not None
