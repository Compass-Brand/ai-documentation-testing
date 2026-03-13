"""Empirical validation of task difficulty labels.

Compares labeled difficulty (easy/medium/hard/edge) against actual
baseline scores to detect mislabeled tasks. Thresholds are based on
mean score across all repetitions of a task under the baseline variant.

Note: 5 of 11 task types produce binary scores (0.0 or 1.0), which means
mean scores cluster at specific fractions (0/N, 1/N, ..., N/N). The
thresholds below are set to work with both continuous and binary scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Difficulty thresholds based on mean baseline score.
# These thresholds work for both continuous scores and binary scores.
# For binary scoring with 10 reps: easy >= 8/10, medium >= 5/10, hard >= 2/10.
_THRESHOLDS = {
    "easy": 0.80,    # mean score >= 0.80
    "medium": 0.50,  # mean score >= 0.50
    "hard": 0.15,    # mean score >= 0.15
    "edge": 0.0,     # mean score < 0.15
}


@dataclass
class DifficultyEntry:
    """Per-task difficulty validation result."""

    task_id: str
    labeled: str
    empirical: str
    mean_score: float
    is_mismatch: bool


@dataclass
class DifficultyReport:
    """Aggregate difficulty validation report."""

    entries: list[DifficultyEntry] = field(default_factory=list)

    @property
    def mismatches(self) -> list[DifficultyEntry]:
        return [e for e in self.entries if e.is_mismatch]

    @property
    def total(self) -> int:
        return len(self.entries)

    @property
    def matched(self) -> int:
        return sum(1 for e in self.entries if not e.is_mismatch)

    @property
    def mismatched(self) -> int:
        return sum(1 for e in self.entries if e.is_mismatch)


def compute_empirical_difficulty(scores: list[float]) -> str:
    """Compute empirical difficulty level from observed scores.

    Args:
        scores: List of scores (0.0-1.0) from baseline variant runs.

    Returns:
        Difficulty label: "easy", "medium", "hard", "edge", or "unknown".
    """
    if not scores:
        return "unknown"

    mean = sum(scores) / len(scores)

    if mean >= _THRESHOLDS["easy"]:
        return "easy"
    if mean >= _THRESHOLDS["medium"]:
        return "medium"
    if mean >= _THRESHOLDS["hard"]:
        return "hard"
    return "edge"


def validate_difficulty_labels(
    trial_data: list[tuple[str, str, list[float]]],
) -> DifficultyReport:
    """Validate difficulty labels against empirical scores.

    Args:
        trial_data: List of (task_id, labeled_difficulty, scores) tuples.
            Scores should be from baseline variant runs.

    Returns:
        DifficultyReport with per-task entries and mismatch detection.
    """
    report = DifficultyReport()

    for task_id, labeled, scores in trial_data:
        empirical = compute_empirical_difficulty(scores)
        mean_score = sum(scores) / len(scores) if scores else 0.0
        is_mismatch = empirical != labeled and empirical != "unknown"

        report.entries.append(DifficultyEntry(
            task_id=task_id,
            labeled=labeled,
            empirical=empirical,
            mean_score=mean_score,
            is_mismatch=is_mismatch,
        ))

    return report
