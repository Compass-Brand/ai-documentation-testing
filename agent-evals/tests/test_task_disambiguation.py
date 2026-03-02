"""Tests for the DisambiguationTask type.

Tests cover:
- Valid construction from TaskDefinition with metadata
- Defaults for missing metadata
- Registration in TASK_TYPES
- build_prompt returns message list with index content and question
- score_response: keyword coverage answer match (1.0)
- score_response: label-only match with underscore normalization (0.5)
- score_response: no match (0.0)
- Case-insensitive matching
- Continuous keyword coverage scoring
- Edge cases: empty interpretations, empty expected_interpretation
"""

from __future__ import annotations

from typing import Any

import pytest

from agent_evals.tasks.base import TASK_TYPES, TaskDefinition
from agent_evals.tasks.disambiguation import DisambiguationTask

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _disambiguation_task(**meta_overrides: Any) -> DisambiguationTask:
    """Create a DisambiguationTask with default metadata, with optional overrides."""
    meta: dict[str, Any] = {
        "interpretations": [
            {"label": "database_pool", "answer": "Connection pooling for databases"},
            {"label": "thread_pool", "answer": "Thread pool for parallel execution"},
        ],
        "expected_interpretation": "database_pool",
    }
    meta.update(meta_overrides)
    defn = TaskDefinition(
        task_id="disambiguation_001",
        type="disambiguation",
        question="What does 'pool' refer to in this context?",
        domain="framework_api",
        difficulty="medium",
        metadata=meta,
    )
    return DisambiguationTask(defn)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestDisambiguationTaskConstruction:
    """Tests for DisambiguationTask construction from TaskDefinition."""

    def test_constructs_from_valid_definition(self) -> None:
        """DisambiguationTask accepts a TaskDefinition with valid metadata."""
        task = _disambiguation_task()
        assert len(task.interpretations) == 2
        assert task.expected_interpretation == "database_pool"

    def test_defaults_for_missing_metadata(self) -> None:
        """DisambiguationTask uses defaults when metadata keys are absent."""
        defn = TaskDefinition(
            task_id="disambiguation_002",
            type="disambiguation",
            question="What is X?",
            domain="framework_api",
            difficulty="easy",
            metadata={},
        )
        task = DisambiguationTask(defn)
        assert task.interpretations == []
        assert task.expected_interpretation == ""

    def test_registered_in_task_types(self) -> None:
        """DisambiguationTask is registered in TASK_TYPES for 'disambiguation'."""
        assert TASK_TYPES["disambiguation"] is DisambiguationTask


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


class TestDisambiguationTaskBuildPrompt:
    """Tests for DisambiguationTask.build_prompt."""

    def test_returns_message_list(self) -> None:
        """build_prompt returns a list of message dicts."""
        task = _disambiguation_task()
        messages = task.build_prompt("# Documentation Index")
        assert isinstance(messages, list)
        assert len(messages) >= 2

    def test_includes_index_content(self) -> None:
        """build_prompt includes the index content in messages."""
        task = _disambiguation_task()
        messages = task.build_prompt("UNIQUE_INDEX_CONTENT_DISAMBIG")
        all_content = " ".join(m["content"] for m in messages)
        assert "UNIQUE_INDEX_CONTENT_DISAMBIG" in all_content

    def test_includes_question(self) -> None:
        """build_prompt includes the task question in messages."""
        task = _disambiguation_task()
        messages = task.build_prompt("index")
        all_content = " ".join(m["content"] for m in messages)
        assert "What does 'pool' refer to in this context?" in all_content

    def test_system_message_mentions_interpretation(self) -> None:
        """build_prompt system message instructs about disambiguation."""
        task = _disambiguation_task()
        messages = task.build_prompt("index")
        system_msgs = [m for m in messages if m["role"] == "system"]
        assert len(system_msgs) >= 1
        system_content = system_msgs[0]["content"].lower()
        assert "interpret" in system_content or "disambigu" in system_content


# ---------------------------------------------------------------------------
# score_response
# ---------------------------------------------------------------------------


class TestDisambiguationTaskScoring:
    """Tests for DisambiguationTask.score_response."""

    def test_answer_match_returns_1(self) -> None:
        """Response containing the expected interpretation's answer scores 1.0."""
        task = _disambiguation_task()
        score = task.score_response(
            "The pool refers to Connection pooling for databases."
        )
        assert score == 1.0

    def test_answer_match_case_insensitive(self) -> None:
        """Answer matching is case-insensitive."""
        task = _disambiguation_task()
        score = task.score_response(
            "It means connection pooling for databases in this context."
        )
        assert score == 1.0

    def test_label_only_match_returns_half(self) -> None:
        """Response mentioning only the label (not the answer) scores 0.5."""
        task = _disambiguation_task()
        score = task.score_response(
            "This refers to the database_pool concept."
        )
        assert score == 0.5

    def test_no_match_returns_0(self) -> None:
        """Response with no matching answer or label scores 0.0."""
        task = _disambiguation_task()
        score = task.score_response("I have no relevant information about this.")
        assert score == 0.0

    def test_wrong_interpretation_answer_only(self) -> None:
        """Response with wrong interpretation's answer but not the expected one scores 0.0."""
        task = _disambiguation_task()
        score = task.score_response(
            "Thread pool for parallel execution is the meaning here."
        )
        assert score == 0.0

    def test_empty_interpretations_returns_0(self) -> None:
        """Empty interpretations list gives 0.0."""
        task = _disambiguation_task(interpretations=[], expected_interpretation="x")
        score = task.score_response("Some response text.")
        assert score == 0.0

    def test_empty_expected_interpretation_returns_0(self) -> None:
        """Empty expected_interpretation gives 0.0."""
        task = _disambiguation_task(expected_interpretation="")
        score = task.score_response("Connection pooling for databases")
        assert score == 0.0

    def test_label_normalized_underscore_to_space(self) -> None:
        """Label with underscores matches when response uses spaces instead."""
        task = _disambiguation_task()
        score = task.score_response(
            "This refers to the database pool concept."
        )
        assert score == 0.5

    def test_partial_keyword_coverage_above_threshold(self) -> None:
        """Response with >= 50% keyword coverage scores proportionally."""
        task = _disambiguation_task()
        score = task.score_response(
            "It uses connection pooling to manage resources."
        )
        assert score == pytest.approx(2 / 3, abs=0.01)

    def test_partial_keyword_coverage_below_threshold(self) -> None:
        """Response with low keyword coverage scores proportionally (continuous)."""
        task = _disambiguation_task()
        score = task.score_response(
            "It opens a connection to the server."
        )
        assert score == pytest.approx(1 / 3, abs=0.01)

    def test_score_clamped_between_0_and_1(self) -> None:
        """Score is always between 0.0 and 1.0."""
        task = _disambiguation_task()
        for resp in [
            "Connection pooling for databases",
            "nothing relevant",
            "database_pool is the one",
        ]:
            score = task.score_response(resp)
            assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Step 3.4: Verify dedicated scorer (not GenericTask)
# ---------------------------------------------------------------------------


class TestDisambiguationDedicatedScorer:
    """Verify disambiguation has proper scoring beyond GenericTask."""

    def test_not_generic_task(self) -> None:
        """DisambiguationTask is NOT GenericTask -- it has custom scoring."""
        from agent_evals.tasks.base import GenericTask
        assert TASK_TYPES["disambiguation"] is not GenericTask
        assert TASK_TYPES["disambiguation"] is DisambiguationTask

    def test_ambiguity_detection_scores_correctly(self) -> None:
        """Scorer detects and scores correct interpretation among ambiguous options."""
        task = _disambiguation_task(
            interpretations=[
                {"label": "connection_pool", "answer": "Database connection pooling with 10 max connections"},
                {"label": "thread_pool", "answer": "Worker thread pool with 4 threads"},
                {"label": "memory_pool", "answer": "Memory allocation pool for buffers"},
            ],
            expected_interpretation="connection_pool",
        )
        correct = task.score_response("This uses database connection pooling with 10 max connections.")
        wrong = task.score_response("This uses worker thread pool with 4 threads.")
        assert correct > wrong
        assert correct == 1.0
        assert wrong == 0.0


def test_49_percent_keyword_coverage_not_binary():
    """Coverage below 50% must produce a partial score, not 0.0."""
    defn = TaskDefinition(
        task_id="disambiguation_001", type="disambiguation", question="Q",
        domain="framework_api", difficulty="easy",
        metadata={"expected_interpretation": "option_a", "interpretations": [
            {"label": "option_a", "answer": "alpha beta gamma delta"}
        ]},
    )
    task = DisambiguationTask(defn)
    score = task.score_response("Only alpha is mentioned here.")
    assert 0.0 < score < 1.0, f"Expected partial score for 25% coverage, got {score}"
