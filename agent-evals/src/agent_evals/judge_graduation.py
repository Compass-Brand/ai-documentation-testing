"""Judge score graduation — blend judge scores with programmatic scores
when calibration thresholds are met."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class JudgeGraduationConfig:
    """Configuration for judge score graduation.

    Attributes:
        enabled: Master switch for judge graduation.
        kappa_threshold: Minimum Cohen's kappa for a task type to graduate.
        spearman_threshold: Minimum Spearman correlation for graduation.
    """

    enabled: bool = False
    kappa_threshold: float = 0.70
    spearman_threshold: float = 0.80


def should_graduate(
    task_type: str,
    calibration_results: dict[str, dict[str, float]],
    config: JudgeGraduationConfig,
) -> bool:
    """Check if a task type's judge scores should be graduated into composite scoring.

    Args:
        task_type: The task type to check (e.g., "code_generation").
        calibration_results: Map from task_type to {"kappa": float, "spearman": float}.
        config: Graduation configuration with thresholds.

    Returns:
        True if graduation is enabled AND the task type's calibration
        meets both kappa and spearman thresholds.
    """
    if not config.enabled:
        return False

    cal = calibration_results.get(task_type)
    if cal is None:
        return False

    return (
        cal.get("kappa", 0.0) >= config.kappa_threshold
        and cal.get("spearman", 0.0) >= config.spearman_threshold
    )


def blend_scores(
    programmatic: float,
    judge: float,
    weight: float = 0.3,
) -> float:
    """Blend programmatic and judge scores.

    Args:
        programmatic: The original programmatic score.
        judge: The LLM-judge score.
        weight: Weight for the judge score (0.0 = all programmatic, 1.0 = all judge).

    Returns:
        Blended score: programmatic * (1 - weight) + judge * weight.
    """
    return programmatic * (1.0 - weight) + judge * weight
