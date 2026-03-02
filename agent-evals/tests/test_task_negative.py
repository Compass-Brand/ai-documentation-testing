"""Tests for the NegativeTask type.

Tests cover:
- Valid construction from TaskDefinition with metadata
- Defaults for missing metadata
- Registration in TASK_TYPES
- build_prompt returns message list with index content and question
- score_response: abstention phrases detected (1.0)
- score_response: no abstention (0.0)
- All recognized abstention phrases
- Edge cases and score bounding
"""

from __future__ import annotations

from typing import Any

from agent_evals.tasks.base import TASK_TYPES, TaskDefinition
from agent_evals.tasks.negative import NegativeTask

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _negative_task(**meta_overrides: Any) -> NegativeTask:
    """Create a NegativeTask with default metadata, with optional overrides."""
    meta: dict[str, Any] = {
        "expected_answer": "unanswerable",
        "reason": "Not covered in documentation.",
        "nearest_doc": "docs/auth.md",
        "nearest_content": "Auth docs covering JWT tokens.",
        "answerable": False,
        "distractor_files": ["docs/auth.md", "src/utils.py"],
    }
    meta.update(meta_overrides)
    defn = TaskDefinition(
        task_id="negative_001",
        type="negative",
        question="What color is the database logo?",
        domain="framework_api",
        difficulty="medium",
        metadata=meta,
    )
    return NegativeTask(defn)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestNegativeTaskConstruction:
    """Tests for NegativeTask construction from TaskDefinition."""

    def test_constructs_from_valid_definition(self) -> None:
        """NegativeTask accepts a TaskDefinition with valid metadata."""
        task = _negative_task()
        assert task.answerable is False
        assert task.distractor_files == ["docs/auth.md", "src/utils.py"]

    def test_defaults_for_missing_metadata(self) -> None:
        """NegativeTask uses defaults when metadata keys are absent."""
        defn = TaskDefinition(
            task_id="negative_002",
            type="negative",
            question="Unanswerable question",
            domain="framework_api",
            difficulty="easy",
            metadata={},
        )
        task = NegativeTask(defn)
        assert task.answerable is False
        assert task.distractor_files == []

    def test_registered_in_task_types(self) -> None:
        """NegativeTask is registered in TASK_TYPES for 'negative'."""
        assert TASK_TYPES["negative"] is NegativeTask


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


class TestNegativeTaskBuildPrompt:
    """Tests for NegativeTask.build_prompt."""

    def test_returns_message_list(self) -> None:
        """build_prompt returns a list of message dicts."""
        task = _negative_task()
        messages = task.build_prompt("# Index Content")
        assert isinstance(messages, list)
        assert len(messages) >= 2

    def test_includes_index_content(self) -> None:
        """build_prompt includes the index content in messages."""
        task = _negative_task()
        messages = task.build_prompt("UNIQUE_NEGATIVE_INDEX")
        all_content = " ".join(m["content"] for m in messages)
        assert "UNIQUE_NEGATIVE_INDEX" in all_content

    def test_includes_question(self) -> None:
        """build_prompt includes the task question in messages."""
        task = _negative_task()
        messages = task.build_prompt("index")
        all_content = " ".join(m["content"] for m in messages)
        assert "What color is the database logo?" in all_content

    def test_system_message_mentions_abstain(self) -> None:
        """build_prompt system message includes instruction to abstain if needed."""
        task = _negative_task()
        messages = task.build_prompt("index")
        system_content = messages[0]["content"].lower()
        assert "abstain" in system_content or "cannot" in system_content


# ---------------------------------------------------------------------------
# score_response
# ---------------------------------------------------------------------------


class TestNegativeTaskScoring:
    """Tests for NegativeTask.score_response."""

    def test_abstention_phrase_cannot_be_determined(self) -> None:
        """Response with 'cannot be determined' scores 1.0."""
        task = _negative_task()
        score = task.score_response("This cannot be determined from the docs.")
        assert score == 1.0

    def test_abstention_phrase_not_available(self) -> None:
        """Response with 'not available' scores 1.0."""
        task = _negative_task()
        score = task.score_response("That information is not available.")
        assert score == 1.0

    def test_abstention_phrase_no_information(self) -> None:
        """Response with 'no information' scores 1.0."""
        task = _negative_task()
        score = task.score_response("There is no information about this topic.")
        assert score == 1.0

    def test_abstention_phrase_not_found(self) -> None:
        """Response with 'not found' scores 1.0."""
        task = _negative_task()
        score = task.score_response("The answer was not found in the docs.")
        assert score == 1.0

    def test_abstention_phrase_dont_know(self) -> None:
        """Response with "don't know" scores 1.0."""
        task = _negative_task()
        score = task.score_response("I don't know the answer to that.")
        assert score == 1.0

    def test_abstention_phrase_unable_to_find(self) -> None:
        """Response with 'unable to find' scores 1.0."""
        task = _negative_task()
        score = task.score_response("I am unable to find that information.")
        assert score == 1.0

    def test_abstention_phrase_not_in_documentation(self) -> None:
        """Response with 'not in the documentation' scores 1.0."""
        task = _negative_task()
        score = task.score_response("This is not in the documentation.")
        assert score == 1.0

    def test_abstention_phrase_unanswerable(self) -> None:
        """Response with 'unanswerable' scores 1.0."""
        task = _negative_task()
        score = task.score_response("This question is unanswerable.")
        assert score == 1.0

    def test_abstention_phrase_cannot_answer(self) -> None:
        """Response with 'cannot answer' scores 1.0."""
        task = _negative_task()
        score = task.score_response("I cannot answer this question.")
        assert score == 1.0

    def test_no_abstention_returns_0(self) -> None:
        """Response without abstention phrases scores 0.0."""
        task = _negative_task()
        score = task.score_response("The database logo is blue and round.")
        assert score == 0.0

    def test_case_insensitive_abstention(self) -> None:
        """Abstention phrase matching is case-insensitive."""
        task = _negative_task()
        score = task.score_response("CANNOT BE DETERMINED from the provided info.")
        assert score == 1.0

    def test_empty_response_returns_0(self) -> None:
        """Empty response scores 0.0."""
        task = _negative_task()
        score = task.score_response("")
        assert score == 0.0

    def test_hedge_with_caveat_scores_exactly_0_7(self) -> None:
        """'I'm not certain...' must score exactly 0.7 (hedge tier)."""
        defn = TaskDefinition(
            task_id="negative_002",
            type="negative",
            question="Q",
            domain="framework_api",
            difficulty="easy",
            metadata={},
        )
        task = NegativeTask(defn)
        score = task.score_response("I'm not certain about this, but it might be X.")
        assert score == 0.7, f"Expected 0.7 for hedge tier, got {score}"

    def test_confident_hallucination_scores_zero(self) -> None:
        defn = TaskDefinition(
            task_id="negative_003",
            type="negative",
            question="Q",
            domain="framework_api",
            difficulty="easy",
            metadata={},
        )
        task = NegativeTask(defn)
        assert task.score_response("The answer is definitely 42.") == 0.0

    def test_firm_refusal_scores_one(self) -> None:
        defn = TaskDefinition(
            task_id="negative_004",
            type="negative",
            question="Q",
            domain="framework_api",
            difficulty="easy",
            metadata={},
        )
        task = NegativeTask(defn)
        assert task.score_response("I cannot answer — no information available.") == 1.0


# ---------------------------------------------------------------------------
# Step 3.1: Metadata field mismatch fix
# ---------------------------------------------------------------------------


class TestNegativeTaskMetadataFields:
    """Tests that NegativeTask uses the actual YAML field names."""

    def test_uses_correct_yaml_metadata_fields(self) -> None:
        """NegativeTask reads expected_answer, reason, nearest_doc, nearest_content from metadata."""
        meta = {
            "expected_answer": "unanswerable",
            "reason": "The docs never mention connection timeout.",
            "nearest_doc": "api/caching.md",
            "nearest_content": "Covers CacheConfig with default_ttl=300.",
        }
        defn = TaskDefinition(
            task_id="negative_003",
            type="negative",
            question="What is the default connection timeout?",
            domain="framework_api",
            difficulty="easy",
            metadata=meta,
        )
        task = NegativeTask(defn)
        assert task.expected_answer == "unanswerable"
        assert task.reason == "The docs never mention connection timeout."
        assert task.nearest_doc == "api/caching.md"
        assert task.nearest_content == "Covers CacheConfig with default_ttl=300."

    def test_defaults_for_yaml_metadata_fields(self) -> None:
        """NegativeTask defaults for YAML metadata fields when absent."""
        defn = TaskDefinition(
            task_id="negative_004",
            type="negative",
            question="Some question",
            domain="framework_api",
            difficulty="easy",
            metadata={},
        )
        task = NegativeTask(defn)
        assert task.expected_answer == ""
        assert task.reason == ""
        assert task.nearest_doc == ""
        assert task.nearest_content == ""

    def test_confident_answer_not_scored_as_abstention(self) -> None:
        """'Based on the available documentation, the answer is X' must NOT score 1.0."""
        defn = TaskDefinition(
            task_id="negative_001",
            type="negative",
            question="What is the version?",
            domain="framework_api",
            difficulty="easy",
            metadata={},
        )
        task = NegativeTask(defn)
        score = task.score_response(
            "Based on the available documentation, the answer is Python 3.11."
        )
        assert score < 1.0, f"False positive — confident answer scored {score}"

    def test_backward_compat_answerable_still_works(self) -> None:
        """NegativeTask still supports legacy answerable/distractor_files fields."""
        meta = {
            "answerable": False,
            "distractor_files": ["docs/auth.md"],
        }
        defn = TaskDefinition(
            task_id="negative_005",
            type="negative",
            question="Legacy question",
            domain="framework_api",
            difficulty="easy",
            metadata=meta,
        )
        task = NegativeTask(defn)
        assert task.answerable is False
        assert task.distractor_files == ["docs/auth.md"]
