"""Tests for the RetrievalTask type.

Tests cover:
- Valid construction from TaskDefinition with metadata
- build_prompt includes question and index content
- score_response: perfect match (1.0)
- score_response: no match (0.0)
- score_response: partial match (between 0 and 1)
- F-beta scoring favors recall over precision
- Edge cases: empty expected_files, various file path formats
"""

from __future__ import annotations

from typing import Any

from agent_evals.tasks.base import TASK_TYPES, TaskDefinition
from agent_evals.tasks.retrieval import RetrievalTask

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _retrieval_task(**meta_overrides: Any) -> RetrievalTask:
    """Create a RetrievalTask with default metadata, with optional overrides."""
    meta: dict[str, Any] = {
        "expected_files": ["src/auth.py", "docs/auth.md"],
        "evidence_passage": "The auth middleware validates JWT tokens.",
    }
    meta.update(meta_overrides)
    defn = TaskDefinition(
        task_id="retrieval_001",
        type="retrieval",
        question="Which files handle authentication?",
        domain="framework_api",
        difficulty="easy",
        metadata=meta,
    )
    return RetrievalTask(defn)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestRetrievalTaskConstruction:
    """Tests for RetrievalTask construction from TaskDefinition."""

    def test_constructs_from_valid_definition(self) -> None:
        """RetrievalTask accepts a TaskDefinition with valid metadata."""
        task = _retrieval_task()
        assert task.expected_files == ["src/auth.py", "docs/auth.md"]
        assert task.evidence_passage == "The auth middleware validates JWT tokens."

    def test_defaults_for_missing_metadata(self) -> None:
        """RetrievalTask uses defaults when metadata keys are absent."""
        defn = TaskDefinition(
            task_id="retrieval_002",
            type="retrieval",
            question="Find files",
            domain="framework_api",
            difficulty="easy",
            metadata={},
        )
        task = RetrievalTask(defn)
        assert task.expected_files == []
        assert task.evidence_passage == ""

    def test_registered_in_task_types(self) -> None:
        """RetrievalTask is registered in TASK_TYPES for 'retrieval'."""
        assert TASK_TYPES["retrieval"] is RetrievalTask


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


class TestRetrievalTaskBuildPrompt:
    """Tests for RetrievalTask.build_prompt."""

    def test_returns_message_list(self) -> None:
        """build_prompt returns a list of message dicts."""
        task = _retrieval_task()
        messages = task.build_prompt("# Index\n- src/auth.py\n- docs/auth.md")
        assert isinstance(messages, list)
        assert len(messages) >= 2

    def test_includes_index_content(self) -> None:
        """build_prompt includes the index content in messages."""
        task = _retrieval_task()
        messages = task.build_prompt("MY_UNIQUE_INDEX_CONTENT")
        all_content = " ".join(m["content"] for m in messages)
        assert "MY_UNIQUE_INDEX_CONTENT" in all_content

    def test_includes_question(self) -> None:
        """build_prompt includes the task question in messages."""
        task = _retrieval_task()
        messages = task.build_prompt("index")
        all_content = " ".join(m["content"] for m in messages)
        assert "Which files handle authentication?" in all_content


# ---------------------------------------------------------------------------
# score_response
# ---------------------------------------------------------------------------


class TestRetrievalTaskScoring:
    """Tests for RetrievalTask.score_response (F-beta with beta=2)."""

    def test_perfect_match_returns_1(self) -> None:
        """Response mentioning all expected files and no extras scores 1.0."""
        task = _retrieval_task(expected_files=["src/auth.py", "docs/auth.md"])
        response = "The relevant files are src/auth.py and docs/auth.md."
        score = task.score_response(response)
        assert score == 1.0

    def test_no_match_returns_0(self) -> None:
        """Response mentioning no expected files scores 0.0."""
        task = _retrieval_task(expected_files=["src/auth.py", "docs/auth.md"])
        response = "I don't know which files are relevant."
        score = task.score_response(response)
        assert score == 0.0

    def test_partial_recall_scores_between_0_and_1(self) -> None:
        """Response mentioning some but not all expected files scores partially."""
        task = _retrieval_task(expected_files=["src/auth.py", "docs/auth.md"])
        response = "The relevant file is src/auth.py."
        score = task.score_response(response)
        assert 0.0 < score < 1.0

    def test_fbeta_favors_recall_over_precision(self) -> None:
        """F-beta(2) gives higher score to high-recall result than high-precision result.

        High recall: finds 2/2 expected but includes 2 extras (recall=1.0, precision=0.5)
        High precision: finds 1/2 expected, no extras (recall=0.5, precision=1.0)
        With beta=2, recall matters more, so high-recall should score higher.
        """
        task = _retrieval_task(expected_files=["src/auth.py", "docs/auth.md"])

        # High recall: mentions both expected + extras
        high_recall_response = (
            "Files: src/auth.py, docs/auth.md, src/utils.py, config/settings.yaml"
        )
        # High precision: mentions 1 expected, no extras
        high_precision_response = "File: src/auth.py"

        recall_score = task.score_response(high_recall_response)
        precision_score = task.score_response(high_precision_response)

        assert recall_score > precision_score

    def test_empty_expected_files_returns_1_for_empty_response(self) -> None:
        """When no files are expected and none found, score is 1.0 (vacuous truth)."""
        task = _retrieval_task(expected_files=[])
        score = task.score_response("No files are relevant.")
        assert score == 1.0

    def test_empty_expected_files_returns_0_when_files_found(self) -> None:
        """When no files are expected but files are found, score is 0.0."""
        task = _retrieval_task(expected_files=[])
        score = task.score_response("Check src/auth.py for details.")
        assert score == 0.0

    def test_extracts_various_file_extensions(self) -> None:
        """score_response extracts paths with various common extensions."""
        task = _retrieval_task(
            expected_files=[
                "src/config.yaml",
                "docs/README.md",
                "tests/test_auth.py",
            ]
        )
        response = (
            "Look at src/config.yaml for configuration, "
            "docs/README.md for docs, and tests/test_auth.py for tests."
        )
        score = task.score_response(response)
        assert score == 1.0

    def test_score_clamped_between_0_and_1(self) -> None:
        """Score is always between 0.0 and 1.0."""
        task = _retrieval_task(expected_files=["src/auth.py"])
        for resp in ["src/auth.py", "nothing here", "src/auth.py extra.py"]:
            score = task.score_response(resp)
            assert 0.0 <= score <= 1.0
