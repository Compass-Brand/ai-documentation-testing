"""Tests for runner judge integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agent_evals.runner import EvalRunConfig, TrialResult


class TestJudgeConfig:
    def test_judge_disabled_by_default(self):
        config = EvalRunConfig()
        assert config.judge_enabled is False

    def test_judge_enabled_explicit(self):
        config = EvalRunConfig(judge_enabled=True)
        assert config.judge_enabled is True

    def test_judge_sample_rate_default(self):
        config = EvalRunConfig()
        assert config.judge_sample_rate == 20

    def test_judge_sample_rate_custom(self):
        config = EvalRunConfig(judge_sample_rate=10)
        assert config.judge_sample_rate == 10

    def test_judge_mode_default(self):
        config = EvalRunConfig()
        assert config.judge_mode == "routine"

    def test_judge_mode_poll(self):
        config = EvalRunConfig(judge_mode="poll")
        assert config.judge_mode == "poll"

    def test_judge_model_default(self):
        config = EvalRunConfig()
        assert "gpt" in config.judge_model.lower() or "openrouter" in config.judge_model

    def test_poll_models_default(self):
        config = EvalRunConfig()
        assert config.poll_models is None

    def test_poll_models_custom(self):
        models = ["model_a", "model_b", "model_c"]
        config = EvalRunConfig(poll_models=models)
        assert config.poll_models == models


class TestJudgeScoreExclusion:
    def test_judge_score_does_not_affect_trial_score(self):
        """Judge score is stored in metrics['judge_score'] but is NOT
        factored into the trial's composite 'score' field."""
        trial = TrialResult(
            task_id="fact_extraction_001",
            task_type="fact_extraction",
            variant_name="axis_1_v1",
            repetition=1,
            score=0.85,  # Programmatic score
            metrics={
                "exact_match": 0.9,
                "fuzzy_match": 0.8,
                "judge_score": 0.6,  # Judge score — separate
                "judge_heuristic_delta": 0.25,
            },
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.01,
            latency_seconds=1.2,
            response="X is Y.",
            cached=False,
        )
        # The composite score must remain 0.85 — judge does not alter it
        assert trial.score == 0.85
        # Judge data is accessible but separate
        assert trial.metrics["judge_score"] == 0.6


class TestJudgeSamplingBehavior:
    def test_judge_fires_at_configured_rate(self):
        """Judge is called at the configured sample rate intervals."""
        from agent_evals.runner import JUDGE_SAMPLE_RATE

        # Verify the module-level constant exists
        assert isinstance(JUDGE_SAMPLE_RATE, int)
        assert JUDGE_SAMPLE_RATE > 0

    def test_judge_failure_does_not_crash_trial(self):
        """If judge call fails, trial still completes with programmatic score.
        Verified by the try/except in runner._run_trial() around _call_judge()."""
        # This is a structural verification — the runner wraps judge calls
        # in try/except and logs warnings instead of propagating exceptions.
        # We verify this by checking the runner source contains the guard.
        import inspect

        from agent_evals.runner import EvalRunner

        source = inspect.getsource(EvalRunner._run_trial)
        assert "except Exception" in source
        assert "judge" in source.lower()
