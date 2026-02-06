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

    def test_all_sub_task_answers_found_returns_1(self) -> None:
        """Response containing all sub-task expected answers scores 1.0."""
        task = _compositional_task(
            sub_tasks=[
                {"question": "Language?", "expected_answer": "Python"},
                {"question": "Port?", "expected_answer": "5000"},
            ],
        )
        response = "Flask is written in Python and runs on port 5000."
        score = task.score_response(response)
        assert score == 1.0

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
        assert score == 0.5

    def test_empty_sub_tasks_returns_1(self) -> None:
        """Empty sub_tasks list returns 1.0 (vacuous truth)."""
        task = _compositional_task(sub_tasks=[])
        score = task.score_response("Any response")
        assert score == 1.0

    def test_case_insensitive_matching(self) -> None:
        """Sub-task answer matching is case-insensitive."""
        task = _compositional_task(
            sub_tasks=[
                {"question": "Language?", "expected_answer": "Python"},
            ],
        )
        response = "It is written in PYTHON."
        score = task.score_response(response)
        assert score == 1.0

    def test_score_clamped_between_0_and_1(self) -> None:
        """Score is always between 0.0 and 1.0."""
        task = _compositional_task()
        for resp in ["Python and 5000", "nothing", "", "Python only"]:
            score = task.score_response(resp)
            assert 0.0 <= score <= 1.0

    def test_three_sub_tasks_partial_score(self) -> None:
        """Three sub-tasks with one answered gives ~0.333 score."""
        task = _compositional_task(
            sub_tasks=[
                {"question": "Q1?", "expected_answer": "Alpha"},
                {"question": "Q2?", "expected_answer": "Beta"},
                {"question": "Q3?", "expected_answer": "Gamma"},
            ],
        )
        response = "The answer is Alpha."
        score = task.score_response(response)
        assert abs(score - 1.0 / 3.0) < 0.01

    def test_sub_task_answer_as_substring(self) -> None:
        """Sub-task answer found as substring in response still matches."""
        task = _compositional_task(
            sub_tasks=[
                {"question": "Port?", "expected_answer": "5000"},
            ],
        )
        response = "The service runs on port 5000/tcp."
        score = task.score_response(response)
        assert score == 1.0

    def test_missing_expected_answer_key_skipped(self) -> None:
        """Sub-task without expected_answer key is skipped during scoring."""
        task = _compositional_task(
            sub_tasks=[
                {"question": "Q1?"},
            ],
        )
        # Sub-task with no expected_answer is skipped; no matchable sub-tasks → 0.0
        score = task.score_response("Any response")
        assert score == 0.0
