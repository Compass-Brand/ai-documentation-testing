"""Tests for the CompositionalTask type.

Tests cover:
- Valid construction from TaskDefinition with metadata
- Defaults for missing metadata
- Registration in TASK_TYPES
- build_prompt returns message list with index content and question
- score_response: all sub-task answers found (1.0)
- score_response: no sub-task answers found (0.0)
- score_response: partial sub-task answers (between 0 and 1)
- Edge cases and score bounding
- Fuzzy matching via rapidfuzz
"""

from __future__ import annotations

from typing import Any

from agent_evals.tasks.base import TASK_TYPES, TaskDefinition
from agent_evals.tasks.compositional import CompositionalTask

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compositional_task(**meta_overrides: Any) -> CompositionalTask:
    """Create a CompositionalTask with default metadata, with optional overrides."""
    meta: dict[str, Any] = {
        "sub_tasks": [
            {"question": "What language is Flask written in?", "expected_answer": "Python"},
            {"question": "What is Flask's default port?", "expected_answer": "5000"},
        ],
        "composition_type": "sequential",
    }
    meta.update(meta_overrides)
    defn = TaskDefinition(
        task_id="compositional_001",
        type="compositional",
        question="What language is Flask written in, and what is its default port?",
        domain="framework_api",
        difficulty="medium",
        metadata=meta,
    )
    return CompositionalTask(defn)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestCompositionalTaskConstruction:
    """Tests for CompositionalTask construction from TaskDefinition."""

    def test_constructs_from_valid_definition(self) -> None:
        """CompositionalTask accepts a TaskDefinition with valid metadata."""
        task = _compositional_task()
        assert len(task.sub_tasks) == 2
        assert task.composition_type == "sequential"

    def test_defaults_for_missing_metadata(self) -> None:
        """CompositionalTask uses defaults when metadata keys are absent."""
        defn = TaskDefinition(
            task_id="compositional_002",
            type="compositional",
            question="Some question",
            domain="framework_api",
            difficulty="easy",
            metadata={},
        )
        task = CompositionalTask(defn)
        assert task.sub_tasks == []
        assert task.composition_type == ""

    def test_registered_in_task_types(self) -> None:
        """CompositionalTask is registered in TASK_TYPES for 'compositional'."""
        assert TASK_TYPES["compositional"] is CompositionalTask


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


class TestCompositionalTaskBuildPrompt:
    """Tests for CompositionalTask.build_prompt."""

    def test_returns_message_list(self) -> None:
        """build_prompt returns a list of message dicts."""
        task = _compositional_task()
        messages = task.build_prompt("# Index Content")
        assert isinstance(messages, list)
        assert len(messages) >= 2

    def test_includes_index_content(self) -> None:
        """build_prompt includes the index content in messages."""
        task = _compositional_task()
        messages = task.build_prompt("UNIQUE_COMPOSITIONAL_INDEX")
        all_content = " ".join(m["content"] for m in messages)
        assert "UNIQUE_COMPOSITIONAL_INDEX" in all_content

    def test_includes_question(self) -> None:
        """build_prompt includes the task question in messages."""
        task = _compositional_task()
        messages = task.build_prompt("index")
        all_content = " ".join(m["content"] for m in messages)
        assert "What language is Flask written in" in all_content

    def test_system_message_mentions_compositional(self) -> None:
        """build_prompt system message includes compositional reasoning instruction."""
        task = _compositional_task()
        messages = task.build_prompt("index")
        system_content = messages[0]["content"].lower()
        assert "compos" in system_content or "sub" in system_content


# ---------------------------------------------------------------------------
# score_response
# ---------------------------------------------------------------------------


class TestCompositionalTaskScoring:
    """Tests for CompositionalTask.score_response."""

    def test_all_sub_task_answers_found_high_score(self) -> None:
        """Response containing all sub-task answers in one sentence scores high."""
        task = _compositional_task(
            sub_tasks=[
                {"question": "Language?", "expected_answer": "Python"},
                {"question": "Port?", "expected_answer": "5000"},
            ],
        )
        response = "Flask is written in Python and runs on port 5000."
        score = task.score_response(response)
        # completeness=1.0, integration=1.0 (co-occurrence), organization=0
        assert score == 0.8

    def test_no_sub_task_answers_found_returns_0(self) -> None:
        """Response containing no sub-task expected answers scores 0.0."""
        task = _compositional_task(
            sub_tasks=[
                {"question": "Language?", "expected_answer": "Python"},
                {"question": "Port?", "expected_answer": "5000"},
            ],
        )
        response = "I have no idea about this framework."
        score = task.score_response(response)
        assert score == 0.0

    def test_partial_sub_task_answers(self) -> None:
        """Response containing some sub-task answers scores partially."""
        task = _compositional_task(
            sub_tasks=[
                {"question": "Language?", "expected_answer": "Python"},
                {"question": "Port?", "expected_answer": "5000"},
            ],
        )
        response = "Flask is written in Python."
        score = task.score_response(response)
        # completeness=0.5 (1 of 2), integration=0, organization=0
        assert score == 0.25

    def test_empty_sub_tasks_returns_1(self) -> None:
        """Empty sub_tasks list returns 1.0 (vacuous truth)."""
        task = _compositional_task(sub_tasks=[])
        score = task.score_response("Any response")
        assert score == 1.0

    def test_case_insensitive_matching(self) -> None:
        """Sub-task answer matching is case-insensitive (completeness axis)."""
        task = _compositional_task(
            sub_tasks=[
                {"question": "Language?", "expected_answer": "Python"},
            ],
        )
        response = "It is written in PYTHON."
        score = task.score_response(response)
        # Single sub-task: uses completeness only (integration/org N/A)
        assert score == 1.0

    def test_score_clamped_between_0_and_1(self) -> None:
        """Score is always between 0.0 and 1.0."""
        task = _compositional_task()
        for resp in ["Python and 5000", "nothing", "", "Python only"]:
            score = task.score_response(resp)
            assert 0.0 <= score <= 1.0

    def test_three_sub_tasks_partial_score(self) -> None:
        """Three sub-tasks with one answered gives completeness weight * 1/3."""
        task = _compositional_task(
            sub_tasks=[
                {"question": "Q1?", "expected_answer": "Alpha"},
                {"question": "Q2?", "expected_answer": "Beta"},
                {"question": "Q3?", "expected_answer": "Gamma"},
            ],
        )
        response = "The answer is Alpha."
        score = task.score_response(response)
        # completeness = 1/3, integration=0, organization=0
        expected = (1.0 / 3.0) * 0.5
        assert abs(score - expected) < 0.01

    def test_sub_task_answer_as_substring(self) -> None:
        """Sub-task answer found as substring in response still matches."""
        task = _compositional_task(
            sub_tasks=[
                {"question": "Port?", "expected_answer": "5000"},
            ],
        )
        response = "The service runs on port 5000/tcp."
        score = task.score_response(response)
        # Single sub-task: uses completeness only (integration/org N/A)
        assert score == 1.0

    def test_missing_expected_answer_key_skipped(self) -> None:
        """Sub-task without expected_answer key is skipped during scoring."""
        task = _compositional_task(
            sub_tasks=[
                {"question": "Q1?"},
            ],
        )
        # Sub-task with no expected_answer is skipped; no scorable sub-tasks -> 1.0 (vacuous truth)
        score = task.score_response("Any response")
        assert score == 1.0


def test_empty_sub_task_excluded_from_denominator():
    """Empty sub-task excluded from completeness denominator."""
    defn = TaskDefinition(
        task_id="compositional_001", type="compositional", question="Q",
        domain="framework_api", difficulty="easy",
        metadata={"sub_tasks": [
            {"question": "A", "expected_answer": "Python 3.11"},
            {"question": "B", "expected_answer": ""},
        ]},
    )
    task = CompositionalTask(defn)
    score = task.score_response("The version is Python 3.11 and nothing else.")
    # Single scorable sub-task: uses completeness only (integration/org N/A)
    assert score == 1.0, f"Expected 1.0 (completeness only), got {score}"


def test_fuzzy_match_catches_paraphrase():
    """'Python version 3.11' must score > 0 for expected 'Python 3.11'."""
    defn = TaskDefinition(
        task_id="compositional_002", type="compositional", question="Q",
        domain="framework_api", difficulty="easy",
        metadata={"sub_tasks": [{"question": "version?", "expected_answer": "Python 3.11"}]},
    )
    task = CompositionalTask(defn)
    score = task.score_response("The runtime uses Python version 3.11 as its base.")
    assert score > 0.0, f"Expected > 0.0 for paraphrase, got {score}"


def test_exact_match_still_scores_one():
    defn = TaskDefinition(
        task_id="compositional_003", type="compositional", question="Q",
        domain="framework_api", difficulty="easy",
        metadata={"sub_tasks": [{"question": "version?", "expected_answer": "Python 3.11"}]},
    )
    task = CompositionalTask(defn)
    # Completeness axis (50%) = 1.0, integration/organization may add more
    assert task.score_response("Python 3.11 is used.") >= 0.5


# ---------------------------------------------------------------------------
# Multi-axis scoring
# ---------------------------------------------------------------------------


class TestCompositionalMultiAxis:
    """Tests for 3-axis scoring: completeness (50%), integration (30%), organization (20%)."""

    def test_integrated_response_scores_higher(self) -> None:
        """Response weaving sub-answers together scores strictly higher than segregated."""
        task = _compositional_task(sub_tasks=[
            {"question": "What is X?", "expected_answer": "alpha beta"},
            {"question": "What is Y?", "expected_answer": "gamma delta"},
        ])
        # Segregated: keywords in separate sentences, no co-occurrence
        segregated = task.score_response("alpha beta. gamma delta.")
        # Integrated: keywords from both sub-tasks in same sentence
        integrated = task.score_response(
            "alpha beta relates to gamma delta through their shared properties."
        )
        assert integrated > segregated

    def test_organized_response_scores_higher(self) -> None:
        """Response with structure indicators scores strictly higher than flat text."""
        task = _compositional_task(sub_tasks=[
            {"question": "Q1", "expected_answer": "answer one"},
            {"question": "Q2", "expected_answer": "answer two"},
        ])
        flat = task.score_response("answer one answer two")
        organized = task.score_response(
            "First, answer one. Second, answer two."
        )
        assert organized > flat

    def test_completeness_still_dominates(self) -> None:
        """Missing sub-answers score low even with good organization."""
        task = _compositional_task(sub_tasks=[
            {"question": "Q1", "expected_answer": "alpha"},
            {"question": "Q2", "expected_answer": "beta"},
        ])
        organized_but_incomplete = task.score_response(
            "First, alpha is the answer. Second, I don't know."
        )
        flat_but_complete = task.score_response("alpha and beta")
        assert flat_but_complete >= organized_but_incomplete

    def test_numbered_list_gets_organization_credit(self) -> None:
        """Numbered list format gets organization axis credit."""
        task = _compositional_task(sub_tasks=[
            {"question": "Q1", "expected_answer": "alpha"},
            {"question": "Q2", "expected_answer": "beta"},
        ])
        # Both use separated sentences (no integration co-occurrence)
        no_org = task.score_response("alpha. beta.")
        with_org = task.score_response("1. alpha. 2. beta.")
        assert with_org > no_org

    def test_header_markers_get_organization_credit(self) -> None:
        """Markdown headers get organization axis credit."""
        task = _compositional_task(sub_tasks=[
            {"question": "Q1", "expected_answer": "alpha"},
            {"question": "Q2", "expected_answer": "beta"},
        ])
        no_headers = task.score_response("alpha and beta")
        with_headers = task.score_response("## Part 1\nalpha\n## Part 2\nbeta")
        assert with_headers >= no_headers

    def test_perfect_response_near_1(self) -> None:
        """Response with all sub-answers, integration, and structure scores near 1.0."""
        task = _compositional_task(sub_tasks=[
            {"question": "What is X?", "expected_answer": "alpha beta"},
            {"question": "What is Y?", "expected_answer": "gamma delta"},
        ])
        score = task.score_response(
            "First, alpha beta is important. Second, gamma delta matters. "
            "Together, alpha beta and gamma delta form a complete picture."
        )
        assert score >= 0.8

    def test_empty_sub_tasks_still_returns_1(self) -> None:
        """Empty sub_tasks list returns 1.0 (vacuous truth, unchanged)."""
        task = _compositional_task(sub_tasks=[])
        assert task.score_response("Any response") == 1.0
