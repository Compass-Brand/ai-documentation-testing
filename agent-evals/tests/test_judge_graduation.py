"""Tests for judge score graduation into composite scoring."""

from __future__ import annotations

import pytest

from agent_evals.judge_graduation import (
    JudgeGraduationConfig,
    blend_scores,
    should_graduate,
)


class TestJudgeGraduationConfig:
    def test_defaults(self):
        config = JudgeGraduationConfig()
        assert config.enabled is False
        assert config.kappa_threshold == 0.70
        assert config.spearman_threshold == 0.80

    def test_custom_thresholds(self):
        config = JudgeGraduationConfig(
            enabled=True,
            kappa_threshold=0.60,
            spearman_threshold=0.75,
        )
        assert config.enabled is True
        assert config.kappa_threshold == 0.60


class TestShouldGraduate:
    def test_graduate_judge_score_when_calibrated(self):
        """Task type graduates when both kappa and spearman exceed thresholds."""
        calibration_results = {
            "code_generation": {"kappa": 0.85, "spearman": 0.90},
            "summarization": {"kappa": 0.50, "spearman": 0.60},
        }
        config = JudgeGraduationConfig(
            enabled=True,
            kappa_threshold=0.70,
            spearman_threshold=0.80,
        )

        assert should_graduate("code_generation", calibration_results, config) is True

    def test_no_graduation_below_threshold(self):
        """Task type does not graduate when kappa or spearman is below threshold."""
        calibration_results = {
            "summarization": {"kappa": 0.50, "spearman": 0.60},
        }
        config = JudgeGraduationConfig(
            enabled=True,
            kappa_threshold=0.70,
            spearman_threshold=0.80,
        )

        assert should_graduate("summarization", calibration_results, config) is False

    def test_graduation_config_flag(self):
        """When config.enabled is False, no task type graduates regardless of scores."""
        calibration_results = {
            "code_generation": {"kappa": 0.95, "spearman": 0.99},
        }
        config = JudgeGraduationConfig(enabled=False)

        assert should_graduate("code_generation", calibration_results, config) is False

    def test_unknown_task_type_does_not_graduate(self):
        """Task types not present in calibration results do not graduate."""
        calibration_results = {
            "code_generation": {"kappa": 0.85, "spearman": 0.90},
        }
        config = JudgeGraduationConfig(enabled=True)

        assert should_graduate("unknown_type", calibration_results, config) is False


class TestBlendScores:
    def test_blend_scores_default_weight(self):
        """Default blend weight is 0.3 (30% judge, 70% programmatic)."""
        result = blend_scores(programmatic=0.80, judge=1.0)
        # 0.80 * 0.7 + 1.0 * 0.3 = 0.56 + 0.30 = 0.86
        assert result == pytest.approx(0.86)

    def test_blend_scores_custom_weight(self):
        """Custom blend weight overrides default."""
        result = blend_scores(programmatic=0.80, judge=1.0, weight=0.5)
        # 0.80 * 0.5 + 1.0 * 0.5 = 0.40 + 0.50 = 0.90
        assert result == pytest.approx(0.90)

    def test_blend_scores_zero_weight(self):
        """Weight=0.0 means 100% programmatic."""
        result = blend_scores(programmatic=0.80, judge=1.0, weight=0.0)
        assert result == pytest.approx(0.80)

    def test_blend_scores_full_weight(self):
        """Weight=1.0 means 100% judge."""
        result = blend_scores(programmatic=0.80, judge=1.0, weight=1.0)
        assert result == pytest.approx(1.0)
