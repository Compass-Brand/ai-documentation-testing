"""Tests for beam search cascade module."""

from __future__ import annotations

from agent_evals.beam_search import (
    BeamAxisResult,
    BeamCandidate,
    BeamSearchResult,
    format_beam_report,
    run_beam_cascade,
    score_variants,
    select_beam,
)
from agent_evals.runner import TrialResult


def _make_trial(
    task_id: str = "retrieval_001",
    variant_name: str = "variant_a",
    score: float = 0.8,
    repetition: int = 1,
) -> TrialResult:
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
        response="test",
        cached=False,
    )


def _make_variant_trials(
    variant_name: str,
    base_score: float,
    n_tasks: int = 10,
    n_reps: int = 3,
) -> list[TrialResult]:
    """Create trials for a variant across multiple task types."""
    import random

    rng = random.Random(hash(variant_name))
    types = ["retrieval", "fact_extraction", "code_generation"]
    trials = []
    for i in range(n_tasks):
        task_type = types[i % len(types)]
        for rep in range(n_reps):
            score = max(0.0, min(1.0, base_score + rng.uniform(-0.05, 0.05)))
            trials.append(
                _make_trial(
                    task_id=f"{task_type}_{i + 1:03d}",
                    variant_name=variant_name,
                    score=score,
                    repetition=rep + 1,
                )
            )
    return trials


class TestScoreVariants:
    def test_single_variant(self) -> None:
        trials = _make_variant_trials("a", 0.8)
        candidates = score_variants(trials, n_bootstrap=100)
        assert len(candidates) == 1
        assert candidates[0].variant_name == "a"
        assert candidates[0].composite_score > 0

    def test_multiple_variants_sorted(self) -> None:
        trials = (
            _make_variant_trials("best", 0.9)
            + _make_variant_trials("worst", 0.3)
            + _make_variant_trials("mid", 0.6)
        )
        candidates = score_variants(trials, n_bootstrap=100)
        assert len(candidates) == 3
        assert candidates[0].variant_name == "best"
        assert candidates[0].composite_score >= candidates[1].composite_score
        assert candidates[1].composite_score >= candidates[2].composite_score

    def test_empty_trials(self) -> None:
        candidates = score_variants([])
        assert candidates == []

    def test_per_type_scores_populated(self) -> None:
        trials = _make_variant_trials("a", 0.8, n_tasks=9)
        candidates = score_variants(trials, n_bootstrap=100)
        assert len(candidates[0].per_type_scores) > 0

    def test_ci_computed(self) -> None:
        trials = _make_variant_trials("a", 0.8, n_tasks=10)
        candidates = score_variants(trials, n_bootstrap=100)
        assert candidates[0].ci is not None


class TestSelectBeam:
    def test_basic_selection(self) -> None:
        trials = (
            _make_variant_trials("a", 0.9)
            + _make_variant_trials("b", 0.7)
            + _make_variant_trials("c", 0.5)
        )
        candidates = score_variants(trials, n_bootstrap=100)
        result = select_beam(candidates, trials, beam_width=2)
        assert len(result.beam_retained) >= 2
        assert result.beam_retained[0].variant_name == "a"

    def test_empty_candidates(self) -> None:
        result = select_beam([], [], beam_width=3)
        assert len(result.beam_retained) == 0

    def test_single_candidate(self) -> None:
        trials = _make_variant_trials("only", 0.8)
        candidates = score_variants(trials, n_bootstrap=100)
        result = select_beam(candidates, trials, beam_width=3)
        assert len(result.beam_retained) == 1

    def test_parity_retains_close_candidates(self) -> None:
        # Two variants with very similar scores should both be retained
        trials = (
            _make_variant_trials("a", 0.80)
            + _make_variant_trials("b", 0.79)
        )
        candidates = score_variants(trials, n_bootstrap=100)
        result = select_beam(candidates, trials, beam_width=1, parity_alpha=0.10)
        # Both should be retained due to statistical parity
        assert len(result.beam_retained) >= 1


class TestRunBeamCascade:
    def test_single_axis(self) -> None:
        trials = (
            _make_variant_trials("a", 0.9)
            + _make_variant_trials("b", 0.7)
        )
        result = run_beam_cascade(
            {1: trials},
            axis_order=[1],
            beam_width=2,
            n_bootstrap=100,
        )
        assert len(result.axis_results) == 1
        assert result.axis_results[0].axis == 1
        assert len(result.final_beam) >= 1

    def test_multiple_axes(self) -> None:
        axis1_trials = _make_variant_trials("struct_a", 0.9) + _make_variant_trials(
            "struct_b", 0.7
        )
        axis2_trials = _make_variant_trials("meta_a", 0.8) + _make_variant_trials(
            "meta_b", 0.85
        )
        result = run_beam_cascade(
            {1: axis1_trials, 2: axis2_trials},
            axis_order=[1, 2],
            beam_width=2,
            n_bootstrap=100,
        )
        assert len(result.axis_results) == 2

    def test_empty_axis_skipped(self) -> None:
        trials = _make_variant_trials("a", 0.8)
        result = run_beam_cascade(
            {1: trials},
            axis_order=[1, 2, 3],
            beam_width=2,
            n_bootstrap=100,
        )
        assert len(result.axis_results) == 1

    def test_result_metadata(self) -> None:
        trials = _make_variant_trials("a", 0.8)
        result = run_beam_cascade(
            {1: trials},
            axis_order=[1],
            beam_width=3,
            parity_alpha=0.05,
            n_bootstrap=100,
        )
        assert result.beam_width == 3
        assert result.parity_alpha == 0.05
        assert result.axis_order == [1]


class TestFormatBeamReport:
    def test_report_contains_key_sections(self) -> None:
        result = BeamSearchResult(
            axis_results=[
                BeamAxisResult(
                    axis=1,
                    candidates_evaluated=[
                        BeamCandidate("a", 85.0),
                        BeamCandidate("b", 70.0),
                    ],
                    beam_retained=[BeamCandidate("a", 85.0)],
                ),
            ],
            final_beam=[BeamCandidate("a", 85.0)],
            axis_order=[1],
            beam_width=3,
            parity_alpha=0.10,
        )
        text = format_beam_report(result)
        assert "BEAM SEARCH CASCADE REPORT" in text
        assert "Axis 1" in text
        assert "85.00" in text
        assert "Final Beam" in text


class TestBeamCandidate:
    def test_defaults(self) -> None:
        c = BeamCandidate("test", 75.0)
        assert c.variant_name == "test"
        assert c.composite_score == 75.0
        assert c.ci is None
        assert c.per_type_scores == {}
        assert c.within_parity is True
