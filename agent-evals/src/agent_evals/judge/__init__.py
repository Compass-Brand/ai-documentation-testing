"""LLM-as-judge calibration and scoring for agent-evals."""

from __future__ import annotations

from agent_evals.judge.calibrator import (
    CalibrationResult,
    GoldExample,
    JudgeScore,
    build_judge_prompt,
    calibrate,
    compute_cohens_kappa,
    compute_kendall_tau,
    compute_mean_absolute_error,
    compute_spearman,
    parse_judge_response,
)
from agent_evals.judge.poll import (
    DEFAULT_PANEL,
    ROUTINE_MODEL,
    PanelScore,
    PollConfig,
    PollResult,
    aggregate_panel_scores,
    build_poll_result,
    format_poll_report,
    identify_disagreements,
    validate_panel_correlation,
)

__all__ = [
    # calibrator
    "CalibrationResult",
    "GoldExample",
    "JudgeScore",
    "build_judge_prompt",
    "calibrate",
    "compute_cohens_kappa",
    "compute_kendall_tau",
    "compute_mean_absolute_error",
    "compute_spearman",
    "parse_judge_response",
    # poll
    "DEFAULT_PANEL",
    "PanelScore",
    "PollConfig",
    "PollResult",
    "ROUTINE_MODEL",
    "aggregate_panel_scores",
    "build_poll_result",
    "format_poll_report",
    "identify_disagreements",
    "validate_panel_correlation",
]
