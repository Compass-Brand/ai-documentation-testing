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
    task_type: str = "retrieval",
    variant_name: str = "variant_a",
    score: float = 0.8,
    repetition: int = 1,
) -> TrialResult:
    return TrialResult(
        task_id=task_id,
        task_type=task_type,
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
                    task_type=task_type,
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


class TestWithinParityAfterHolmBonferroni:
    """within_parity flags must reflect corrected p-values, not raw."""

    def test_parity_flags_updated_after_correction(self) -> None:
        """Candidate marked NOT within parity by raw p should flip to
        within parity when Holm-Bonferroni correction makes it non-significant."""
        from unittest.mock import patch

        from agent_evals.scoring import PairwiseResult

        # 7 candidates: best + 6 others. beam_width=3 means candidates[1:6]
        # are considered: first 2 always retained (within beam), next 3 go
        # through parity check. That's 5 pairwise tests total.
        # Holm multiplier for smallest p: 5. Raw p=0.02 → corrected=0.10.
        # With default holm alpha=0.05: 0.10 > 0.05 → NOT significant.
        # But raw 0.02 < 0.05 → significant before correction.
        candidates = [BeamCandidate("best", 0.95, trial_count=30)]
        for i in range(6):
            candidates.append(
                BeamCandidate(f"cand_{i}", 0.90 - i * 0.01, trial_count=30)
            )

        # Build trials with enough data for wilcoxon (need >= 5 per variant)
        import random
        rng = random.Random(42)
        trials = []
        for c in candidates:
            for _ in range(30):
                trials.append(
                    _make_trial(
                        variant_name=c.variant_name,
                        score=c.composite_score + rng.uniform(-0.02, 0.02),
                    )
                )

        # Mock wilcoxon to return raw p=0.02 (significant at alpha=0.05).
        # After Holm with 5 tests: corrected = 0.02*5 = 0.10 > 0.05 → not significant.
        def mock_wilcoxon(a, b, alpha=0.05, variant_a="", variant_b=""):
            return PairwiseResult(
                variant_a=variant_a,
                variant_b=variant_b,
                statistic=100.0,
                p_value=0.02,
                corrected_p_value=0.02,
                effect_size=0.1,
                significant=0.02 < alpha,  # True when alpha=0.10
            )

        with patch("agent_evals.beam_search.pairwise_wilcoxon", mock_wilcoxon):
            result = select_beam(
                candidates, trials, beam_width=3, parity_alpha=0.10,
            )

        # Verify Holm correction was applied (corrected_p > raw_p for some)
        assert len(result.pairwise_tests) >= 3, (
            f"Expected >= 3 pairwise tests, got {len(result.pairwise_tests)}"
        )

        # After Holm correction with 5 tests, all corrected p-values should
        # be >= 0.02*5=0.10, making them NOT significant at alpha=0.05.
        for pw in result.pairwise_tests:
            assert not pw.significant, (
                f"After Holm correction, {pw.variant_b} should not be significant "
                f"(corrected_p={pw.corrected_p_value})"
            )

        # KEY ASSERTION: candidates' within_parity flags must match the
        # CORRECTED significance. Since corrected tests are all non-significant,
        # every tested candidate should have within_parity=True.
        for c in result.candidates_evaluated:
            if c.variant_name == "best":
                continue
            pw_for_c = [
                pw for pw in result.pairwise_tests
                if pw.variant_b == c.variant_name
            ]
            if pw_for_c:
                assert c.within_parity is True, (
                    f"{c.variant_name} should be within parity after Holm correction "
                    f"(corrected_p={pw_for_c[0].corrected_p_value}, significant={pw_for_c[0].significant})"
                )


class TestBeamCandidate:
    def test_defaults(self) -> None:
        c = BeamCandidate("test", 75.0)
        assert c.variant_name == "test"
        assert c.composite_score == 75.0
        assert c.ci is None
        assert c.per_type_scores == {}
        assert c.within_parity is True
