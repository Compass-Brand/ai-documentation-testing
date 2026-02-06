"""Tests for axis ordering sensitivity test module."""

from __future__ import annotations

from agent_evals.pilot.ordering_test import (
    AxisResult,
    BeamCandidate,
    OrderingResult,
    SensitivityReport,
    compare_orderings,
    format_sensitivity_report,
    select_beam,
)
from agent_evals.runner import TrialResult


def _make_trial(
    task_id: str = "retrieval_001",
    variant_name: str = "variant_a",
    score: float = 0.8,
    repetition: int = 1,
) -> TrialResult:
    """Helper to create a TrialResult for testing."""
    return TrialResult(
        task_id=task_id,
        variant_name=variant_name,
        repetition=repetition,
        score=score,
        metrics={},
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost=0.001,
        latency_seconds=1.0,
        response="test response",
        cached=False,
    )


class TestSelectBeam:
    def test_selects_top_candidates(self) -> None:
        trials = [
            _make_trial(variant_name="best", score=0.9, task_id="retrieval_001"),
            _make_trial(variant_name="best", score=0.85, task_id="retrieval_002"),
            _make_trial(variant_name="best", score=0.88, task_id="retrieval_003"),
            _make_trial(variant_name="mid", score=0.6, task_id="retrieval_001"),
            _make_trial(variant_name="mid", score=0.65, task_id="retrieval_002"),
            _make_trial(variant_name="mid", score=0.62, task_id="retrieval_003"),
            _make_trial(variant_name="worst", score=0.3, task_id="retrieval_001"),
            _make_trial(variant_name="worst", score=0.35, task_id="retrieval_002"),
            _make_trial(variant_name="worst", score=0.32, task_id="retrieval_003"),
        ]
        beam = select_beam(trials, beam_width=2)
        assert len(beam) == 2
        assert beam[0].variant_name == "best"
        assert beam[1].variant_name == "mid"

    def test_beam_width_respected(self) -> None:
        trials = [
            _make_trial(variant_name=f"v{i}", score=0.5 + i * 0.1, task_id="retrieval_001")
            for i in range(5)
        ]
        beam = select_beam(trials, beam_width=3)
        assert len(beam) == 3

    def test_single_variant(self) -> None:
        trials = [
            _make_trial(variant_name="only", score=0.7, task_id="retrieval_001"),
        ]
        beam = select_beam(trials, beam_width=3)
        assert len(beam) == 1
        assert beam[0].variant_name == "only"

    def test_empty_trials(self) -> None:
        beam = select_beam([], beam_width=3)
        assert len(beam) == 0

    def test_beam_candidates_have_scores(self) -> None:
        trials = [
            _make_trial(variant_name="a", score=0.8, task_id="retrieval_001"),
            _make_trial(variant_name="a", score=0.9, task_id="retrieval_002"),
        ]
        beam = select_beam(trials, beam_width=1)
        assert beam[0].mean_score > 0


class TestCompareOrderings:
    def _make_ordering(
        self,
        name: str,
        winners: list[str],
        axis_order: list[int] | None = None,
    ) -> OrderingResult:
        return OrderingResult(
            ordering_name=name,
            axis_order=axis_order or [1, 2, 3],
            axis_results=[
                AxisResult(
                    axis=1,
                    candidates_tested=winners + ["other"],
                    beam_retained=winners,
                    scores={w: 0.8 for w in winners},
                ),
            ],
            final_winners=winners,
            total_cost=0.1,
        )

    def test_same_winners_no_difference(self) -> None:
        results = [
            self._make_ordering("default", ["a", "b"]),
            self._make_ordering("alt", ["a", "b"]),
        ]
        report = compare_orderings(results)
        assert not report.winners_differ
        assert report.recommendation == "proceed"

    def test_different_winners_flagged(self) -> None:
        results = [
            self._make_ordering("default", ["a", "b"]),
            self._make_ordering("alt", ["c", "d"]),
        ]
        report = compare_orderings(results)
        assert report.winners_differ
        assert report.recommendation == "expand_interaction_validation"

    def test_single_ordering(self) -> None:
        results = [self._make_ordering("only", ["a"])]
        report = compare_orderings(results)
        assert not report.winners_differ
        assert report.recommendation == "proceed"

    def test_partial_overlap(self) -> None:
        results = [
            self._make_ordering("default", ["a", "b"]),
            self._make_ordering("alt", ["a", "c"]),
        ]
        report = compare_orderings(results)
        assert report.winners_differ

    def test_differing_axes_detected(self) -> None:
        r1 = OrderingResult(
            ordering_name="default",
            axis_order=[1, 2],
            axis_results=[
                AxisResult(axis=1, candidates_tested=["a", "b"], beam_retained=["a"], scores={"a": 0.9}),
                AxisResult(axis=2, candidates_tested=["c", "d"], beam_retained=["c"], scores={"c": 0.8}),
            ],
            final_winners=["a", "c"],
        )
        r2 = OrderingResult(
            ordering_name="alt",
            axis_order=[2, 1],
            axis_results=[
                AxisResult(axis=2, candidates_tested=["c", "d"], beam_retained=["d"], scores={"d": 0.85}),
                AxisResult(axis=1, candidates_tested=["a", "b"], beam_retained=["b"], scores={"b": 0.88}),
            ],
            final_winners=["d", "b"],
        )
        report = compare_orderings([r1, r2])
        assert report.winners_differ
        assert len(report.differing_axes) > 0


class TestFormatSensitivityReport:
    def test_report_contains_key_info(self) -> None:
        report = SensitivityReport(
            ordering_results=[
                OrderingResult(
                    ordering_name="default",
                    axis_order=[1, 2, 3],
                    axis_results=[],
                    final_winners=["variant_a"],
                    total_cost=0.5,
                ),
            ],
            winners_differ=False,
            differing_axes=[],
            recommendation="proceed",
        )
        text = format_sensitivity_report(report)
        assert "AXIS ORDERING SENSITIVITY REPORT" in text
        assert "default" in text
        assert "proceed" in text
        assert "variant_a" in text

    def test_report_shows_differences(self) -> None:
        report = SensitivityReport(
            ordering_results=[],
            winners_differ=True,
            differing_axes=[3, 5],
            recommendation="expand_interaction_validation",
        )
        text = format_sensitivity_report(report)
        assert "True" in text
        assert "expand_interaction_validation" in text


class TestBeamCandidate:
    def test_dataclass_fields(self) -> None:
        bc = BeamCandidate(variant_name="test", axis=1, mean_score=0.85)
        assert bc.variant_name == "test"
        assert bc.axis == 1
        assert bc.mean_score == 0.85
        assert bc.ci is None


class TestAxisResult:
    def test_dataclass_fields(self) -> None:
        ar = AxisResult(
            axis=1,
            candidates_tested=["a", "b", "c"],
            beam_retained=["a", "b"],
            scores={"a": 0.9, "b": 0.8},
        )
        assert ar.axis == 1
        assert len(ar.candidates_tested) == 3
        assert len(ar.beam_retained) == 2
        assert ar.pairwise_tests == []
