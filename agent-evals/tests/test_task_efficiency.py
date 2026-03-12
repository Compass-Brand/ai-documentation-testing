"""Tests for the EfficiencyTask type.

Tests cover:
- Valid construction from TaskDefinition with metadata
- Defaults for missing metadata
- Registration in TASK_TYPES
- build_prompt returns message list with index content and question
- score_response: exact answer match within budget (1.0)
- score_response: alias match within budget (1.0)
- score_response: fuzzy match gets partial credit
- score_response: no match (0.0)
- score_response: keyword fraction scoring
- Length penalty when exceeding token_budget
- Score clamping to [0, 1]
- Edge cases: empty answer, zero token_budget
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from agent_evals.tasks.base import TASK_TYPES, TaskDefinition
from agent_evals.tasks.efficiency import EfficiencyTask

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _efficiency_task(**meta_overrides: Any) -> EfficiencyTask:
    """Create an EfficiencyTask with default metadata, with optional overrides."""
    meta: dict[str, Any] = {
        "expected_answer": "asyncio event loop",
        "answer_aliases": ["event loop", "async loop"],
        "token_budget": 50,
        "message_limit": 1,
    }
    meta.update(meta_overrides)
    defn = TaskDefinition(
        task_id="efficiency_001",
        type="efficiency",
        question="What runs async tasks in Python?",
        domain="framework_api",
        difficulty="easy",
        metadata=meta,
    )
    return EfficiencyTask(defn)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestEfficiencyTaskConstruction:
    """Tests for EfficiencyTask construction from TaskDefinition."""

    def test_constructs_from_valid_definition(self) -> None:
        """EfficiencyTask accepts a TaskDefinition with valid metadata."""
        task = _efficiency_task()
        assert task.expected_answer == "asyncio event loop"
        assert task.answer_aliases == ["event loop", "async loop"]
        assert task.token_budget == 50
        assert task.message_limit == 1

    def test_defaults_for_missing_metadata(self) -> None:
        """EfficiencyTask uses defaults when metadata keys are absent."""
        defn = TaskDefinition(
            task_id="efficiency_002",
            type="efficiency",
            question="What is X?",
            domain="framework_api",
            difficulty="easy",
            metadata={},
        )
        task = EfficiencyTask(defn)
        assert task.expected_answer == ""
        assert task.answer_aliases == []
        assert task.token_budget == 0
        assert task.message_limit == 0

    def test_registered_in_task_types(self) -> None:
        """EfficiencyTask is registered in TASK_TYPES for 'efficiency'."""
        assert TASK_TYPES["efficiency"] is EfficiencyTask


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


class TestEfficiencyTaskBuildPrompt:
    """Tests for EfficiencyTask.build_prompt."""

    def test_returns_message_list(self) -> None:
        """build_prompt returns a list of message dicts."""
        task = _efficiency_task()
        messages = task.build_prompt("# Documentation Index")
        assert isinstance(messages, list)
        assert len(messages) >= 2

    def test_includes_index_content(self) -> None:
        """build_prompt includes the index content in messages."""
        task = _efficiency_task()
        messages = task.build_prompt("UNIQUE_INDEX_CONTENT_EFFICIENCY")
        all_content = " ".join(m["content"] for m in messages)
        assert "UNIQUE_INDEX_CONTENT_EFFICIENCY" in all_content

    def test_includes_question(self) -> None:
        """build_prompt includes the task question in messages."""
        task = _efficiency_task()
        messages = task.build_prompt("index")
        all_content = " ".join(m["content"] for m in messages)
        assert "What runs async tasks in Python?" in all_content

    def test_system_message_mentions_concise(self) -> None:
        """build_prompt system message instructs concise answering."""
        task = _efficiency_task()
        messages = task.build_prompt("index")
        system_msgs = [m for m in messages if m["role"] == "system"]
        assert len(system_msgs) >= 1
        system_content = system_msgs[0]["content"].lower()
        assert "concise" in system_content


# ---------------------------------------------------------------------------
# score_response
# ---------------------------------------------------------------------------


class TestEfficiencyTaskScoring:
    """Tests for EfficiencyTask.score_response."""

    def test_exact_match_within_budget_returns_1(self) -> None:
        """Response containing exact answer within token budget scores 1.0."""
        task = _efficiency_task(token_budget=50)
        score = task.score_response("The asyncio event loop handles async tasks.")
        assert score == 1.0

    def test_alias_match_within_budget_returns_1(self) -> None:
        """Response containing an alias within budget scores 1.0."""
        task = _efficiency_task(token_budget=50)
        score = task.score_response("The event loop runs them.")
        assert score == 1.0

    def test_fuzzy_match_scores_higher_than_keywords_alone(self) -> None:
        """Fuzzy matching should give higher score than keyword fallback.

        "database connection pooling" vs "db connection pool management":
        - Keyword matching: only "connection" matches (1/3 ≈ 0.33)
        - Fuzzy matching: high token overlap should give >= 0.5
        """
        task = _efficiency_task(
            expected_answer="database connection pooling",
            answer_aliases=[],
            token_budget=100,
        )
        score = task.score_response("db connection pool management")
        # Without fuzzy: keyword match gives ~0.33 (only "connection")
        # With fuzzy: token_set_ratio should be >= 50, giving >= 0.5
        assert score >= 0.5, (
            f"fuzzy near-match should score >= 0.5, got {score}"
        )

    def test_fuzzy_match_with_length_penalty(self) -> None:
        """Fuzzy match score should still be subject to length penalty."""
        task = _efficiency_task(
            expected_answer="database connection pooling",
            answer_aliases=[],
            token_budget=5,
        )
        long_response = (
            "the db connection pool management requires a lot of "
            "additional context and explanation to fully understand"
        )
        score = task.score_response(long_response)
        # Fuzzy base score reduced by length penalty
        assert score < 0.5

    def test_no_match_returns_0(self) -> None:
        """Response with no matching keywords scores 0.0."""
        task = _efficiency_task()
        score = task.score_response("I have no idea about this.")
        assert score == 0.0

    def test_exact_match_case_insensitive(self) -> None:
        """Exact matching is case-insensitive."""
        task = _efficiency_task(token_budget=50)
        score = task.score_response("The ASYNCIO EVENT LOOP does it.")
        assert score == 1.0

    def test_length_penalty_reduces_score(self) -> None:
        """Exceeding token_budget reduces the score proportionally."""
        task = _efficiency_task(token_budget=10)
        # This response has ~20 words, double the 10-token budget
        long_response = (
            "The asyncio event loop is the core mechanism that manages "
            "and schedules all asynchronous tasks in the Python runtime."
        )
        score = task.score_response(long_response)
        # Base score 1.0 * (10 / ~20) = ~0.5
        assert 0.0 < score < 1.0

    def test_within_budget_no_penalty(self) -> None:
        """Response within token_budget gets no penalty."""
        task = _efficiency_task(token_budget=100)
        score = task.score_response("The asyncio event loop.")
        assert score == 1.0

    def test_partial_keyword_match(self) -> None:
        """Response with some keywords scores partially."""
        task = _efficiency_task(
            expected_answer="asyncio event loop",
            answer_aliases=[],
            token_budget=100,
        )
        # Contains "asyncio" but not "event" or "loop"
        score = task.score_response("Use asyncio for concurrency.")
        assert 0.0 < score < 1.0

    def test_empty_expected_answer_returns_0(self) -> None:
        """Empty expected_answer gives 0.0."""
        task = _efficiency_task(expected_answer="", answer_aliases=[])
        score = task.score_response("Some response text.")
        assert score == 0.0

    def test_zero_token_budget_no_penalty(self) -> None:
        """Zero token_budget means no length penalty is applied."""
        task = _efficiency_task(token_budget=0)
        score = task.score_response("The asyncio event loop handles everything.")
        assert score == 1.0

    def test_score_clamped_between_0_and_1(self) -> None:
        """Score is always between 0.0 and 1.0."""
        task = _efficiency_task()
        for resp in [
            "asyncio event loop",
            "nothing",
            "event loop is here " * 50,
        ]:
            score = task.score_response(resp)
            assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Token counting accuracy
# ---------------------------------------------------------------------------


class TestEfficiencyTokenCounting:
    """Tests that efficiency scoring uses a real tokenizer, not word split."""

    def test_score_uses_count_tokens_not_word_split(self) -> None:
        """score_response calls count_tokens for accurate token counting."""
        task = _efficiency_task(token_budget=10)
        response = "The asyncio event loop handles it."
        with patch(
            "agent_evals.tasks.efficiency.count_tokens",
            return_value=20,
        ) as mock_ct:
            score = task.score_response(response)
        # count_tokens was called with the response text
        mock_ct.assert_called_once_with(response)
        # With budget=10, tokens=20: base_score * (10/20) = 0.5
        assert score == 0.5

    def test_hyphenated_words_counted_as_multiple_tokens(self) -> None:
        """Hyphenated words get real token counts, not word-split counts."""
        task = _efficiency_task(token_budget=5)
        # "well-known event-driven asyncio event loop" is 5 words but ~8 tokens
        response = "well-known event-driven asyncio event loop"
        with patch(
            "agent_evals.tasks.efficiency.count_tokens",
            return_value=8,
        ):
            score = task.score_response(response)
        # base=1.0 * (5/8) = 0.625
        assert score == 0.625
