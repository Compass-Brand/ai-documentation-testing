"""Tests for saturation analysis module."""

from __future__ import annotations

from agent_evals.pilot.saturation import (
    LearningCurvePoint,
    SaturationReport,
    SaturationResult,
    analyze_saturation,
    compute_learning_curve,
    compute_ranking_stability,
    find_saturation_point,
    format_saturation_report,
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


def _make_trials_for_variant(
    variant_name: str,
    n_tasks: int = 30,
    base_score: float = 0.8,
    noise: float = 0.05,
) -> list[TrialResult]:
    """Create a set of trials for a variant across task types."""
    import random
    rng = random.Random(42)
    task_types = [
        "retrieval", "fact_extraction", "code_generation", "agentic",
        "multi_hop", "negative", "compositional", "robustness",
        "disambiguation", "conflicting", "efficiency",
    ]
    trials = []
    for i in range(n_tasks):
        task_type = task_types[i % len(task_types)]
        task_id = f"{task_type}_{i + 1:03d}"
        score = max(0.0, min(1.0, base_score + rng.uniform(-noise, noise)))
        for rep in range(1, 4):  # 3 repetitions
            trials.append(_make_trial(
                task_id=task_id,
                task_type=task_type,
                variant_name=variant_name,
                score=score + rng.uniform(-0.02, 0.02),
                repetition=rep,
            ))
    return trials


class TestComputeLearningCurve:
    def test_basic_curve(self) -> None:
        trials = _make_trials_for_variant("a", n_tasks=30, base_score=0.8)
        curve = compute_learning_curve(trials, "a", step_size=10, min_tasks=10, n_bootstrap=100)
        assert len(curve) > 0
        assert all(isinstance(p, LearningCurvePoint) for p in curve)
        assert all(p.variant_name == "a" for p in curve)

    def test_curve_task_counts_increasing(self) -> None:
        trials = _make_trials_for_variant("a", n_tasks=40)
        curve = compute_learning_curve(trials, "a", step_size=10, min_tasks=10, n_bootstrap=100)
        counts = [p.task_count for p in curve]
        assert counts == sorted(counts)

    def test_empty_trials(self) -> None:
        curve = compute_learning_curve([], "a")
        assert curve == []

    def test_wrong_variant_name(self) -> None:
        trials = _make_trials_for_variant("a")
        curve = compute_learning_curve(trials, "nonexistent")
        assert curve == []

    def test_curve_has_composite_scores(self) -> None:
        trials = _make_trials_for_variant("a", n_tasks=30)
        curve = compute_learning_curve(trials, "a", step_size=10, min_tasks=10, n_bootstrap=100)
        for point in curve:
            assert 0 <= point.composite_score <= 100


class TestFindSaturationPoint:
    def test_stable_curve_is_saturated(self) -> None:
        # All points have nearly the same score
        curve = [
            LearningCurvePoint(task_count=i * 10, variant_name="a", composite_score=75.0 + (i % 2) * 0.1)
            for i in range(2, 12)
        ]
        sat_point, is_sat, score_range = find_saturation_point(curve, stability_threshold=1.0)
        assert is_sat
        assert score_range < 1.0

    def test_unstable_curve_not_saturated(self) -> None:
        # Scores keep changing significantly
        curve = [
            LearningCurvePoint(task_count=i * 10, variant_name="a", composite_score=50.0 + i * 5)
            for i in range(10)
        ]
        _, is_sat, score_range = find_saturation_point(curve, stability_threshold=1.0)
        assert not is_sat
        assert score_range > 1.0

    def test_empty_curve(self) -> None:
        sat_point, is_sat, score_range = find_saturation_point([])
        assert sat_point is None
        assert not is_sat

    def test_short_curve(self) -> None:
        curve = [LearningCurvePoint(task_count=10, variant_name="a", composite_score=75.0)]
        sat_point, is_sat, _ = find_saturation_point(curve)
        assert not is_sat

    def test_saturation_point_value(self) -> None:
        # First 3 points unstable, then stable
        curve = [
            LearningCurvePoint(task_count=10, variant_name="a", composite_score=60.0),
            LearningCurvePoint(task_count=20, variant_name="a", composite_score=70.0),
            LearningCurvePoint(task_count=30, variant_name="a", composite_score=75.0),
            LearningCurvePoint(task_count=40, variant_name="a", composite_score=75.2),
            LearningCurvePoint(task_count=50, variant_name="a", composite_score=75.1),
            LearningCurvePoint(task_count=60, variant_name="a", composite_score=75.3),
            LearningCurvePoint(task_count=70, variant_name="a", composite_score=75.0),
            LearningCurvePoint(task_count=80, variant_name="a", composite_score=75.2),
            LearningCurvePoint(task_count=90, variant_name="a", composite_score=75.1),
            LearningCurvePoint(task_count=100, variant_name="a", composite_score=75.2),
        ]
        sat_point, is_sat, _ = find_saturation_point(curve, stability_threshold=1.0)
        assert is_sat
        assert sat_point is not None
        assert sat_point <= 40  # Should find stability starting around 30-40


class TestComputeRankingStability:
    def test_stable_rankings(self) -> None:
        curves = {
            "a": [
                LearningCurvePoint(task_count=10, variant_name="a", composite_score=80.0),
                LearningCurvePoint(task_count=20, variant_name="a", composite_score=80.0),
            ],
            "b": [
                LearningCurvePoint(task_count=10, variant_name="b", composite_score=70.0),
                LearningCurvePoint(task_count=20, variant_name="b", composite_score=70.0),
            ],
        }
        history = compute_ranking_stability(curves)
        assert len(history) == 2
        assert not history[0].ranking_changed  # First point never "changed"
        assert not history[1].ranking_changed
        assert history[0].rankings["a"] == 1
        assert history[0].rankings["b"] == 2

    def test_ranking_change_detected(self) -> None:
        curves = {
            "a": [
                LearningCurvePoint(task_count=10, variant_name="a", composite_score=80.0),
                LearningCurvePoint(task_count=20, variant_name="a", composite_score=65.0),
            ],
            "b": [
                LearningCurvePoint(task_count=10, variant_name="b", composite_score=70.0),
                LearningCurvePoint(task_count=20, variant_name="b", composite_score=75.0),
            ],
        }
        history = compute_ranking_stability(curves)
        assert any(rsp.ranking_changed for rsp in history)

    def test_empty_curves(self) -> None:
        history = compute_ranking_stability({})
        assert history == []

    def test_single_variant(self) -> None:
        curves = {
            "a": [
                LearningCurvePoint(task_count=10, variant_name="a", composite_score=80.0),
            ],
        }
        history = compute_ranking_stability(curves)
        assert len(history) == 1
        assert history[0].rankings["a"] == 1


class TestAnalyzeSaturation:
    def test_full_analysis(self) -> None:
        trials = (
            _make_trials_for_variant("a", n_tasks=30, base_score=0.8)
            + _make_trials_for_variant("b", n_tasks=30, base_score=0.7)
        )
        report = analyze_saturation(
            trials, step_size=10, min_tasks=10,
            stability_threshold=5.0, n_bootstrap=100,
        )
        assert isinstance(report, SaturationReport)
        assert len(report.variant_results) == 2
        assert report.total_tasks_analyzed > 0

    def test_empty_trials(self) -> None:
        report = analyze_saturation([])
        assert len(report.variant_results) == 0
        assert not report.overall_saturated

    def test_report_has_ranking_history(self) -> None:
        trials = _make_trials_for_variant("a", n_tasks=30) + _make_trials_for_variant("b", n_tasks=30)
        report = analyze_saturation(trials, step_size=10, min_tasks=10, n_bootstrap=100)
        assert len(report.ranking_history) > 0


class TestFormatSaturationReport:
    def test_report_contains_key_info(self) -> None:
        report = SaturationReport(
            variant_results=[
                SaturationResult(
                    variant_name="test_variant",
                    saturation_point=80,
                    is_saturated=True,
                    final_score=75.5,
                    score_range_last_20pct=0.3,
                ),
            ],
            ranking_history=[],
            overall_saturated=True,
            saturation_point=80,
            sufficient_tasks=True,
            stability_threshold=1.0,
            total_tasks_analyzed=110,
        )
        text = format_saturation_report(report)
        assert "SATURATION ANALYSIS REPORT" in text
        assert "test_variant" in text
        assert "SATURATED" in text
        assert "110" in text
        assert "80" in text

    def test_not_saturated_report(self) -> None:
        report = SaturationReport(
            variant_results=[
                SaturationResult(
                    variant_name="v",
                    saturation_point=None,
                    is_saturated=False,
                    final_score=60.0,
                    score_range_last_20pct=5.0,
                ),
            ],
            ranking_history=[],
            overall_saturated=False,
            saturation_point=None,
            sufficient_tasks=False,
            stability_threshold=1.0,
            total_tasks_analyzed=50,
        )
        text = format_saturation_report(report)
        assert "NOT SATURATED" in text
