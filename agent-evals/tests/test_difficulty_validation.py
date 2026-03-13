"""Tests for empirical difficulty validation."""

from __future__ import annotations

import pytest

from agent_evals.analysis.difficulty import (
    compute_empirical_difficulty,
    validate_difficulty_labels,
    DifficultyReport,
)


class TestComputeEmpiricalDifficulty:
    """Tests for computing difficulty from scores."""

    def test_high_scores_are_easy(self):
        result = compute_empirical_difficulty(scores=[0.95, 0.90, 0.92, 0.88])
        assert result == "easy"

    def test_medium_scores_are_medium(self):
        result = compute_empirical_difficulty(scores=[0.65, 0.70, 0.60, 0.72])
        assert result == "medium"

    def test_low_scores_are_hard(self):
        result = compute_empirical_difficulty(scores=[0.30, 0.25, 0.35, 0.20])
        assert result == "hard"

    def test_very_low_scores_are_edge(self):
        result = compute_empirical_difficulty(scores=[0.05, 0.10, 0.00, 0.08])
        assert result == "edge"

    def test_empty_scores_returns_unknown(self):
        result = compute_empirical_difficulty(scores=[])
        assert result == "unknown"

    def test_boundary_easy_medium(self):
        """Score exactly at 0.80 threshold is easy."""
        result = compute_empirical_difficulty(scores=[0.80])
        assert result == "easy"

    def test_boundary_medium_hard(self):
        """Score exactly at 0.50 threshold is medium."""
        result = compute_empirical_difficulty(scores=[0.50])
        assert result == "medium"

    def test_boundary_hard_edge(self):
        """Score exactly at 0.15 threshold is hard."""
        result = compute_empirical_difficulty(scores=[0.15])
        assert result == "hard"


class TestValidateDifficultyLabels:
    """Tests for label validation against empirical data."""

    def test_returns_difficulty_report(self):
        data = [("retrieval_001", "easy", [0.95, 0.90])]
        report = validate_difficulty_labels(data)
        assert isinstance(report, DifficultyReport)

    def test_report_contains_all_task_ids(self):
        data = [
            ("retrieval_001", "easy", [0.95, 0.90]),
            ("code_generation_001", "hard", [0.30, 0.25]),
        ]
        report = validate_difficulty_labels(data)
        task_ids = {entry.task_id for entry in report.entries}
        assert task_ids == {"retrieval_001", "code_generation_001"}

    def test_detects_mislabeled_easy_task(self):
        """A task labeled 'hard' that scores 0.95 should be flagged."""
        data = [("retrieval_001", "hard", [0.95, 0.92, 0.90])]
        report = validate_difficulty_labels(data)
        assert len(report.mismatches) == 1
        assert report.mismatches[0].task_id == "retrieval_001"
        assert report.mismatches[0].labeled == "hard"
        assert report.mismatches[0].empirical == "easy"

    def test_no_mismatch_for_correct_label(self):
        """A task labeled 'easy' that scores 0.90+ should not be flagged."""
        data = [("retrieval_001", "easy", [0.95, 0.92, 0.90])]
        report = validate_difficulty_labels(data)
        assert len(report.mismatches) == 0

    def test_report_summary_counts(self):
        data = [
            ("t1", "easy", [0.95, 0.90]),
            ("t2", "hard", [0.90, 0.88]),  # mismatch: labeled hard, scores easy
            ("t3", "medium", [0.65, 0.70]),
            ("t4", "edge", [0.05, 0.10]),
        ]
        report = validate_difficulty_labels(data)
        assert report.total == 4
        assert report.matched + report.mismatched == report.total

    def test_unknown_not_flagged_as_mismatch(self):
        """Tasks with no scores (empirical='unknown') are not mismatches."""
        data = [("retrieval_001", "easy", [])]
        report = validate_difficulty_labels(data)
        assert len(report.mismatches) == 0

    def test_empty_input(self):
        report = validate_difficulty_labels([])
        assert report.total == 0
        assert report.matched == 0
        assert report.mismatched == 0
