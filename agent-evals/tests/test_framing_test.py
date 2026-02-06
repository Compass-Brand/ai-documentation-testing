"""Tests for prompt framing comparison module."""

from __future__ import annotations

import pytest
from agent_evals.pilot.framing_test import (
    CONSTANT_SYSTEM_PROMPT,
    FramingComparison,
    FramingReport,
    FramingVariantResult,
    aggregate_trials,
    build_adapted_prompt,
    build_constant_prompt,
    compare_framings,
    format_framing_report,
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


class TestBuildPrompts:
    def test_constant_prompt_structure(self) -> None:
        msgs = build_constant_prompt("What is X?", "index content")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        assert CONSTANT_SYSTEM_PROMPT in msgs[0]["content"]
        assert "What is X?" in msgs[1]["content"]
        assert "index content" in msgs[1]["content"]

    def test_adapted_prompt_structure(self) -> None:
        msgs = build_adapted_prompt("What is X?", "index content", "YAML format with hierarchical structure")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert "YAML format" in msgs[0]["content"]
        assert "What is X?" in msgs[1]["content"]

    def test_constant_prompt_same_for_all(self) -> None:
        msgs1 = build_constant_prompt("Q1", "idx1")
        msgs2 = build_constant_prompt("Q2", "idx2")
        assert msgs1[0]["content"] == msgs2[0]["content"]

    def test_adapted_prompt_varies(self) -> None:
        msgs1 = build_adapted_prompt("Q", "idx", "YAML format")
        msgs2 = build_adapted_prompt("Q", "idx", "Markdown table")
        assert msgs1[0]["content"] != msgs2[0]["content"]


class TestAggregateTrials:
    def test_single_variant(self) -> None:
        trials = [
            _make_trial(variant_name="a", score=0.8, task_id="retrieval_001"),
            _make_trial(variant_name="a", score=0.9, task_id="retrieval_002"),
        ]
        result = aggregate_trials(trials, "constant")
        assert "a" in result
        assert result["a"].framing == "constant"
        assert result["a"].mean_score == pytest.approx(0.85)
        assert result["a"].trial_count == 2

    def test_multiple_variants(self) -> None:
        trials = [
            _make_trial(variant_name="a", score=0.8),
            _make_trial(variant_name="b", score=0.6),
        ]
        result = aggregate_trials(trials, "adapted")
        assert len(result) == 2
        assert "a" in result
        assert "b" in result

    def test_empty_trials(self) -> None:
        result = aggregate_trials([], "constant")
        assert len(result) == 0

    def test_per_type_scores(self) -> None:
        trials = [
            _make_trial(variant_name="a", score=0.8, task_id="retrieval_001"),
            _make_trial(variant_name="a", score=0.9, task_id="retrieval_002"),
            _make_trial(variant_name="a", score=0.6, task_id="fact_extraction_001"),
        ]
        result = aggregate_trials(trials, "constant")
        assert "retrieval" in result["a"].per_type_scores
        assert "fact_extraction" in result["a"].per_type_scores
        assert result["a"].per_type_scores["retrieval"] == pytest.approx(0.85)


class TestCompareFramings:
    def test_same_scores_no_difference(self) -> None:
        constant = [_make_trial(variant_name="a", score=0.8, task_id=f"retrieval_{i:03d}") for i in range(10)]
        adapted = [_make_trial(variant_name="a", score=0.8, task_id=f"retrieval_{i:03d}") for i in range(10)]
        report = compare_framings(constant, adapted)
        assert len(report.comparisons) == 1
        assert report.comparisons[0].score_difference == pytest.approx(0.0, abs=0.01)

    def test_adapted_better(self) -> None:
        constant = [_make_trial(variant_name="a", score=0.5, task_id=f"retrieval_{i:03d}") for i in range(10)]
        adapted = [_make_trial(variant_name="a", score=0.9, task_id=f"retrieval_{i:03d}") for i in range(10)]
        report = compare_framings(constant, adapted)
        assert report.comparisons[0].score_difference > 0

    def test_multiple_variants(self) -> None:
        constant = (
            [_make_trial(variant_name="a", score=0.8, task_id=f"retrieval_{i:03d}") for i in range(5)]
            + [_make_trial(variant_name="b", score=0.6, task_id=f"retrieval_{i:03d}") for i in range(5)]
        )
        adapted = (
            [_make_trial(variant_name="a", score=0.85, task_id=f"retrieval_{i:03d}") for i in range(5)]
            + [_make_trial(variant_name="b", score=0.65, task_id=f"retrieval_{i:03d}") for i in range(5)]
        )
        report = compare_framings(constant, adapted)
        assert len(report.comparisons) == 2

    def test_empty_trials(self) -> None:
        report = compare_framings([], [])
        assert len(report.comparisons) == 0
        assert report.overall_better_framing == "mixed"

    def test_no_common_variants(self) -> None:
        constant = [_make_trial(variant_name="a", score=0.8)]
        adapted = [_make_trial(variant_name="b", score=0.9)]
        report = compare_framings(constant, adapted)
        assert len(report.comparisons) == 0


class TestFormatFramingReport:
    def test_report_contains_key_info(self) -> None:
        report = FramingReport(
            comparisons=[
                FramingComparison(
                    variant_name="test_variant",
                    constant_result=FramingVariantResult("test_variant", "constant", 0.8, composite=75.0),
                    adapted_result=FramingVariantResult("test_variant", "adapted", 0.85, composite=80.0),
                    score_difference=5.0,
                    better_framing="adapted",
                ),
            ],
            overall_better_framing="adapted",
            mean_difference=5.0,
            variants_favoring_constant=0,
            variants_favoring_adapted=1,
            variants_no_difference=0,
        )
        text = format_framing_report(report)
        assert "PROMPT FRAMING COMPARISON REPORT" in text
        assert "adapted" in text
        assert "test_variant" in text
        assert "75.00" in text
        assert "80.00" in text


class TestFramingVariantResult:
    def test_defaults(self) -> None:
        r = FramingVariantResult(variant_name="x", framing="constant", mean_score=0.5)
        assert r.per_type_scores == {}
        assert r.composite == 0.0
        assert r.trial_count == 0
        assert r.ci is None
