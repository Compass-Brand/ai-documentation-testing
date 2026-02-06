"""Tests for the ConflictingTask type.

Tests cover:
- Valid construction from TaskDefinition with metadata
- Defaults for missing metadata
- Registration in TASK_TYPES
- build_prompt returns message list with index content and question
- score_response: exact resolution match (1.0)
- score_response: no match (0.0)
- score_response: partial keyword match (between 0 and 1)
- Case-insensitive matching
- Edge cases: empty expected_resolution, stopword filtering
"""

from __future__ import annotations

from typing import Any

from agent_evals.tasks.base import TASK_TYPES, TaskDefinition
from agent_evals.tasks.conflicting import ConflictingTask

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _conflicting_task(**meta_overrides: Any) -> ConflictingTask:
    """Create a ConflictingTask with default metadata, with optional overrides."""
    meta: dict[str, Any] = {
        "sources": [
            {
                "content": "The timeout is 30 seconds",
                "authority_level": 3,
                "file": "docs/config.md",
            },
            {
                "content": "The timeout is 60 seconds",
                "authority_level": 5,
                "file": "docs/api-reference.md",
            },
        ],
        "expected_resolution": "The timeout is 60 seconds",
        "resolution_strategy": "highest_authority",
    }
    meta.update(meta_overrides)
    defn = TaskDefinition(
        task_id="conflicting_001",
        type="conflicting",
        question="What is the default timeout?",
        domain="framework_api",
        difficulty="hard",
        metadata=meta,
    )
    return ConflictingTask(defn)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConflictingTaskConstruction:
    """Tests for ConflictingTask construction from TaskDefinition."""

    def test_constructs_from_valid_definition(self) -> None:
        """ConflictingTask accepts a TaskDefinition with valid metadata."""
        task = _conflicting_task()
        assert len(task.sources) == 2
        assert task.expected_resolution == "The timeout is 60 seconds"
        assert task.resolution_strategy == "highest_authority"

    def test_defaults_for_missing_metadata(self) -> None:
        """ConflictingTask uses defaults when metadata keys are absent."""
        defn = TaskDefinition(
            task_id="conflicting_002",
            type="conflicting",
            question="What is X?",
            domain="framework_api",
            difficulty="easy",
            metadata={},
        )
        task = ConflictingTask(defn)
        assert task.sources == []
        assert task.expected_resolution == ""
        assert task.resolution_strategy == ""

    def test_registered_in_task_types(self) -> None:
        """ConflictingTask is registered in TASK_TYPES for 'conflicting'."""
        assert TASK_TYPES["conflicting"] is ConflictingTask


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


class TestConflictingTaskBuildPrompt:
    """Tests for ConflictingTask.build_prompt."""

    def test_returns_message_list(self) -> None:
        """build_prompt returns a list of message dicts."""
        task = _conflicting_task()
        messages = task.build_prompt("# Documentation Index")
        assert isinstance(messages, list)
        assert len(messages) >= 2

    def test_includes_index_content(self) -> None:
        """build_prompt includes the index content in messages."""
        task = _conflicting_task()
        messages = task.build_prompt("UNIQUE_INDEX_CONTENT_CONFLICT")
        all_content = " ".join(m["content"] for m in messages)
        assert "UNIQUE_INDEX_CONTENT_CONFLICT" in all_content

    def test_includes_question(self) -> None:
        """build_prompt includes the task question in messages."""
        task = _conflicting_task()
        messages = task.build_prompt("index")
        all_content = " ".join(m["content"] for m in messages)
        assert "What is the default timeout?" in all_content

    def test_system_message_mentions_conflicting(self) -> None:
        """build_prompt system message instructs about resolving conflicts."""
        task = _conflicting_task()
        messages = task.build_prompt("index")
        system_msgs = [m for m in messages if m["role"] == "system"]
        assert len(system_msgs) >= 1
        system_content = system_msgs[0]["content"].lower()
        assert "conflict" in system_content


# ---------------------------------------------------------------------------
# score_response
# ---------------------------------------------------------------------------


class TestConflictingTaskScoring:
    """Tests for ConflictingTask.score_response."""

    def test_exact_match_returns_1(self) -> None:
        """Response containing exact expected_resolution scores 1.0."""
        task = _conflicting_task()
        score = task.score_response("The timeout is 60 seconds by default.")
        assert score == 1.0

    def test_exact_match_case_insensitive(self) -> None:
        """Exact matching is case-insensitive."""
        task = _conflicting_task()
        score = task.score_response("the timeout is 60 seconds according to docs.")
        assert score == 1.0

    def test_no_match_returns_0(self) -> None:
        """Response with no matching keywords scores 0.0."""
        task = _conflicting_task()
        score = task.score_response("I have no idea about this setting.")
        assert score == 0.0

    def test_partial_keyword_match(self) -> None:
        """Response with some keywords from expected_resolution scores partially."""
        task = _conflicting_task(
            expected_resolution="maximum connection timeout value",
        )
        # Contains "timeout" and "connection" but not "maximum" or "value"
        score = task.score_response("The connection timeout is configured here.")
        assert 0.0 < score < 1.0

    def test_empty_expected_resolution_returns_0(self) -> None:
        """Empty expected_resolution gives 0.0."""
        task = _conflicting_task(expected_resolution="")
        score = task.score_response("Some response text.")
        assert score == 0.0

    def test_stopwords_excluded_from_keyword_matching(self) -> None:
        """Stopwords are excluded from keyword fallback matching."""
        task = _conflicting_task(
            expected_resolution="the use of middleware patterns",
        )
        # Response only has stopwords from the answer
        score = task.score_response("the use of something else entirely")
        assert score < 1.0

    def test_score_clamped_between_0_and_1(self) -> None:
        """Score is always between 0.0 and 1.0."""
        task = _conflicting_task()
        for resp in [
            "The timeout is 60 seconds",
            "nothing relevant",
            "timeout setting",
        ]:
            score = task.score_response(resp)
            assert 0.0 <= score <= 1.0
