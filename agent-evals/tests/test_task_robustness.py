"""Tests for the RobustnessTask type.

Tests cover:
- Valid construction from TaskDefinition with metadata
- Defaults for missing metadata
- Registration in TASK_TYPES
- build_prompt returns message list with index content and question
- score_response: exact match (1.0)
- score_response: alias match (1.0)
- score_response: no match (0.0)
- score_response: partial keyword match (between 0 and 1)
- Edge cases and score bounding
"""

from __future__ import annotations

from typing import Any

from agent_evals.tasks.base import TASK_TYPES, TaskDefinition
from agent_evals.tasks.robustness import RobustnessTask

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _robustness_task(**meta_overrides: Any) -> RobustnessTask:
    """Create a RobustnessTask with default metadata, with optional overrides."""
    meta: dict[str, Any] = {
        "base_task_id": "fact_extraction_001",
        "perturbation_type": "paraphrase",
        "expected_answer": "JSON Web Token",
        "answer_aliases": ["JWT"],
    }
    meta.update(meta_overrides)
    defn = TaskDefinition(
        task_id="robustness_001",
        type="robustness",
        question="Wat tokn format does the auth systm use?",
        domain="framework_api",
        difficulty="medium",
        metadata=meta,
    )
    return RobustnessTask(defn)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestRobustnessTaskConstruction:
    """Tests for RobustnessTask construction from TaskDefinition."""

    def test_constructs_from_valid_definition(self) -> None:
        """RobustnessTask accepts a TaskDefinition with valid metadata."""
        task = _robustness_task()
        assert task.base_task_id == "fact_extraction_001"
        assert task.perturbation_type == "paraphrase"
        assert task.expected_answer == "JSON Web Token"
        assert task.answer_aliases == ["JWT"]

    def test_defaults_for_missing_metadata(self) -> None:
        """RobustnessTask uses defaults when metadata keys are absent."""
        defn = TaskDefinition(
            task_id="robustness_002",
            type="robustness",
            question="Some question",
            domain="framework_api",
            difficulty="easy",
            metadata={},
        )
        task = RobustnessTask(defn)
        assert task.base_task_id == ""
        assert task.perturbation_type == ""
        assert task.expected_answer == ""
        assert task.answer_aliases == []

    def test_registered_in_task_types(self) -> None:
        """RobustnessTask is registered in TASK_TYPES for 'robustness'."""
        assert TASK_TYPES["robustness"] is RobustnessTask


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


class TestRobustnessTaskBuildPrompt:
    """Tests for RobustnessTask.build_prompt."""

    def test_returns_message_list(self) -> None:
        """build_prompt returns a list of message dicts."""
        task = _robustness_task()
        messages = task.build_prompt("# Index Content")
        assert isinstance(messages, list)
        assert len(messages) >= 2

    def test_includes_index_content(self) -> None:
        """build_prompt includes the index content in messages."""
        task = _robustness_task()
        messages = task.build_prompt("UNIQUE_ROBUSTNESS_INDEX")
        all_content = " ".join(m["content"] for m in messages)
        assert "UNIQUE_ROBUSTNESS_INDEX" in all_content

    def test_includes_question(self) -> None:
        """build_prompt includes the task question in messages."""
        task = _robustness_task()
        messages = task.build_prompt("index")
        all_content = " ".join(m["content"] for m in messages)
        assert "Wat tokn format does the auth systm use?" in all_content

    def test_system_message_mentions_factual(self) -> None:
        """build_prompt system message includes factual answering instruction."""
        task = _robustness_task()
        messages = task.build_prompt("index")
        system_content = messages[0]["content"].lower()
        assert "factual" in system_content or "accurate" in system_content


# ---------------------------------------------------------------------------
# score_response
# ---------------------------------------------------------------------------


class TestRobustnessTaskScoring:
    """Tests for RobustnessTask.score_response (same as FactExtractionTask scoring)."""

    def test_exact_match_returns_1(self) -> None:
        """Response containing exact expected_answer scores 1.0."""
        task = _robustness_task(expected_answer="JSON Web Token")
        score = task.score_response("The system uses JSON Web Token for auth.")
        assert score == 1.0

    def test_alias_match_returns_1(self) -> None:
        """Response containing an alias scores 1.0."""
        task = _robustness_task(
            expected_answer="JSON Web Token",
            answer_aliases=["JWT"],
        )
        score = task.score_response("The system uses JWT for authentication.")
        assert score == 1.0

    def test_no_match_returns_0(self) -> None:
        """Response with no matching keywords scores 0.0."""
        task = _robustness_task(
            expected_answer="JSON Web Token",
            answer_aliases=["JWT"],
        )
        score = task.score_response("I have no idea about this.")
        assert score == 0.0

    def test_partial_keyword_match(self) -> None:
        """Response with some keywords from expected_answer scores partially."""
        task = _robustness_task(
            expected_answer="JSON Web Token",
            answer_aliases=[],
        )
        # Contains "JSON" but not "Web" or "Token"
        score = task.score_response("The format is JSON based.")
        assert 0.0 < score < 1.0

    def test_case_insensitive_exact_match(self) -> None:
        """Exact matching is case-insensitive."""
        task = _robustness_task(expected_answer="JSON Web Token")
        score = task.score_response("It uses json web token for everything.")
        assert score == 1.0

    def test_case_insensitive_alias_match(self) -> None:
        """Alias matching is case-insensitive."""
        task = _robustness_task(
            expected_answer="JSON Web Token",
            answer_aliases=["JWT"],
        )
        score = task.score_response("The system uses jwt tokens.")
        assert score == 1.0

    def test_empty_expected_answer_returns_0(self) -> None:
        """Empty expected_answer gives 0.0 (no keywords to match)."""
        task = _robustness_task(expected_answer="", answer_aliases=[])
        score = task.score_response("Some response text.")
        assert score == 0.0

    def test_stopwords_filtered_from_keyword_matching(self) -> None:
        """Stopwords and short words are excluded from keyword matching."""
        task = _robustness_task(
            expected_answer="the use of middleware patterns",
            answer_aliases=[],
        )
        response = "the use of something else"
        score = task.score_response(response)
        assert score < 1.0

    def test_score_clamped_between_0_and_1(self) -> None:
        """Score is always between 0.0 and 1.0."""
        task = _robustness_task(expected_answer="test answer")
        for resp in ["test answer here", "nothing", "test something"]:
            score = task.score_response(resp)
            assert 0.0 <= score <= 1.0

    def test_perturbation_type_stored(self) -> None:
        """Perturbation type metadata is stored correctly."""
        for ptype in ["paraphrase", "typo", "reorder"]:
            task = _robustness_task(perturbation_type=ptype)
            assert task.perturbation_type == ptype

    def test_base_task_id_stored(self) -> None:
        """Base task ID metadata is stored correctly."""
        task = _robustness_task(base_task_id="fact_extraction_042")
        assert task.base_task_id == "fact_extraction_042"
