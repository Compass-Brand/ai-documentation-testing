"""Tests for the DisambiguationTask type.

Tests cover:
- Valid construction from TaskDefinition with metadata
- Defaults for missing metadata
- Registration in TASK_TYPES
- build_prompt returns message list with index content and question
- Three-axis scoring: coverage, correctness, awareness
- Full disambiguation responses score high; single-interpretation responses score lower
- Case-insensitive matching
- Edge cases: empty interpretations, empty expected_interpretation
- Partial keyword coverage produces proportional scores
- Scoring produces meaningful variance (no trivial 1.0 for all responses)
"""

from __future__ import annotations

from typing import Any

import pytest
from agent_evals.tasks.base import TASK_TYPES, TaskDefinition
from agent_evals.tasks.disambiguation import (
    _W_CORRECTNESS,
    _W_COVERAGE,
    DisambiguationTask,
)

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

    def test_system_message_asks_for_all_interpretations(self) -> None:
        """build_prompt system message instructs to list ALL interpretations."""
        task = _disambiguation_task()
        messages = task.build_prompt("index")
        system_content = messages[0]["content"].lower()
        assert "all" in system_content


# ---------------------------------------------------------------------------
# score_response: Three-axis scoring
# ---------------------------------------------------------------------------


class TestDisambiguationTaskScoring:
    """Tests for DisambiguationTask.score_response three-axis scoring."""

    def test_full_disambiguation_scores_high(self) -> None:
        """Response addressing all interpretations and acknowledging ambiguity scores ~1.0."""
        task = _disambiguation_task()
        score = task.score_response(
            "This question is ambiguous and could mean two things. "
            "Connection pooling for databases is the database_pool interpretation. "
            "Thread pool for parallel execution is the thread_pool interpretation. "
            "The correct interpretation is database_pool."
        )
        # coverage: 2/2=1.0, correctness: high, awareness: yes
        assert score >= 0.90

    def test_single_interpretation_no_disambiguation_scores_lower(self) -> None:
        """Response answering correctly but not disambiguating scores < 0.7."""
        task = _disambiguation_task()
        score = task.score_response(
            "The pool refers to Connection pooling for databases."
        )
        # coverage: 1/2, correctness: 1.0, awareness: 0.0
        # = 0.4*0.5 + 0.4*1.0 + 0.2*0.0 = 0.60
        assert score < 0.70
        assert score > 0.0

    def test_answer_match_case_insensitive(self) -> None:
        """Answer matching is case-insensitive."""
        task = _disambiguation_task()
        score1 = task.score_response(
            "The pool refers to Connection pooling for databases."
        )
        score2 = task.score_response(
            "It means connection pooling for databases in this context."
        )
        assert score1 == pytest.approx(score2, abs=0.05)

    def test_label_only_match_gives_partial(self) -> None:
        """Response mentioning only the label scores based on label match."""
        task = _disambiguation_task()
        score = task.score_response(
            "This refers to the database_pool concept."
        )
        # coverage: label hit for database_pool (1/2), correctness: label=0.5
        # awareness: 0 => 0.4*0.5 + 0.4*0.5 = 0.40
        assert 0.30 <= score <= 0.50

    def test_no_match_returns_0(self) -> None:
        """Response with no matching answer or label scores 0.0."""
        task = _disambiguation_task()
        score = task.score_response("I have no relevant information about this.")
        assert score == 0.0

    def test_wrong_interpretation_only_scores_low(self) -> None:
        """Response with wrong interpretation's answer scores low (coverage but no correctness)."""
        task = _disambiguation_task()
        score = task.score_response(
            "Thread pool for parallel execution is the meaning here."
        )
        # coverage: 1/2=0.5, correctness: 0.0, awareness: 0.0
        # = 0.4*0.5 + 0.4*0.0 = 0.20
        assert score < 0.30
        assert score > 0.0

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
        score_underscore = task.score_response(
            "This refers to the database_pool concept."
        )
        score_space = task.score_response(
            "This refers to the database pool concept."
        )
        assert score_underscore == pytest.approx(score_space, abs=0.01)

    def test_partial_keyword_coverage_produces_proportional_score(self) -> None:
        """Response with partial keyword coverage scores proportionally."""
        task = _disambiguation_task()
        score = task.score_response(
            "It uses connection pooling to manage resources."
        )
        # coverage: interp0 has 2/3>=0.30 so addressed=1, interp1 not. coverage=0.5
        # correctness: 2/3=0.667
        # awareness: 0.0
        expected = _W_COVERAGE * 0.5 + _W_CORRECTNESS * (2 / 3)
        assert score == pytest.approx(expected, abs=0.05)

    def test_low_keyword_coverage_produces_partial_score(self) -> None:
        """Response with low keyword coverage scores proportionally (continuous)."""
        task = _disambiguation_task()
        score = task.score_response(
            "It opens a connection to the server."
        )
        # "connection" hits interp0 (1/3=0.33>=0.30 -> addressed). coverage=0.5
        # correctness: 1/3=0.333
        # awareness: 0
        assert 0.0 < score < 0.5

    def test_score_clamped_between_0_and_1(self) -> None:
        """Score is always between 0.0 and 1.0."""
        task = _disambiguation_task()
        for resp in [
            "Connection pooling for databases",
            "nothing relevant",
            "database_pool is the one",
            "ambiguous: could mean connection pooling for databases "
            "or thread pool for parallel execution. database_pool is correct.",
        ]:
            score = task.score_response(resp)
            assert 0.0 <= score <= 1.0

    def test_awareness_bonus_increases_score(self) -> None:
        """Mentioning ambiguity phrases adds awareness bonus."""
        task = _disambiguation_task()
        without_awareness = task.score_response(
            "Connection pooling for databases."
        )
        with_awareness = task.score_response(
            "This is ambiguous. Connection pooling for databases."
        )
        assert with_awareness > without_awareness

    def test_both_interpretations_scores_higher_than_one(self) -> None:
        """Covering both interpretations scores higher than covering one."""
        task = _disambiguation_task()
        one_interp = task.score_response(
            "Connection pooling for databases is the answer."
        )
        both_interps = task.score_response(
            "Connection pooling for databases is one option. "
            "Thread pool for parallel execution is another."
        )
        assert both_interps > one_interp


# ---------------------------------------------------------------------------
# Variance: the core fix
# ---------------------------------------------------------------------------


class TestDisambiguationVariance:
    """Verify disambiguation scoring produces meaningful variance."""

    def test_different_quality_responses_produce_different_scores(self) -> None:
        """Responses of varying quality should NOT all score 1.0."""
        task = _disambiguation_task()
        scores = [
            # Excellent: full disambiguation
            task.score_response(
                "This question is ambiguous. It could refer to either "
                "Connection pooling for databases (database_pool) or "
                "Thread pool for parallel execution (thread_pool). "
                "The correct interpretation is database_pool."
            ),
            # Good: correct answer, no disambiguation
            task.score_response(
                "Connection pooling for databases."
            ),
            # Partial: wrong interpretation only
            task.score_response(
                "Thread pool for parallel execution."
            ),
            # Bad: no match
            task.score_response(
                "I don't know."
            ),
        ]
        # Must have at least 3 distinct score levels
        unique_scores = set()
        for s in scores:
            unique_scores.add(round(s, 2))
        assert len(unique_scores) >= 3, (
            f"Expected >= 3 distinct scores but got {unique_scores}"
        )

    def test_no_trivial_1_0_for_simple_answer(self) -> None:
        """A response that just answers without disambiguating should NOT score 1.0."""
        task = _disambiguation_task()
        score = task.score_response(
            "The pool refers to Connection pooling for databases."
        )
        assert score < 1.0, (
            "Simple answer without disambiguation should not score 1.0"
        )

    def test_monotonic_quality_ordering(self) -> None:
        """Better disambiguation responses should score higher."""
        task = _disambiguation_task()
        no_match = task.score_response("irrelevant text")
        wrong_only = task.score_response(
            "Thread pool for parallel execution."
        )
        correct_only = task.score_response(
            "Connection pooling for databases."
        )
        full_disambig = task.score_response(
            "This is ambiguous. Connection pooling for databases is the "
            "database_pool interpretation. Thread pool for parallel "
            "execution is the thread_pool interpretation."
        )
        assert no_match < wrong_only < correct_only < full_disambig


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
        correct = task.score_response(
            "This is ambiguous and could mean several things. "
            "Database connection pooling with 10 max connections (connection_pool). "
            "Worker thread pool with 4 threads (thread_pool). "
            "Memory allocation pool for buffers (memory_pool). "
            "The correct one is connection_pool."
        )
        wrong = task.score_response("This uses worker thread pool with 4 threads.")
        assert correct > wrong
        assert correct >= 0.85
        # Wrong interpretation alone should score low
        assert wrong < 0.30


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


def test_single_interpretation_task_still_works():
    """Tasks with only 1 interpretation (singleAnswer) still score correctly."""
    defn = TaskDefinition(
        task_id="disambiguation_001", type="disambiguation", question="Q",
        domain="framework_api", difficulty="easy",
        metadata={"expected_interpretation": "option_a", "interpretations": [
            {"label": "option_a", "answer": "The quick brown fox jumps"}
        ]},
    )
    task = DisambiguationTask(defn)
    # With 1 interp, coverage is always 1/1 if keywords match
    score = task.score_response("The quick brown fox jumps over the lazy dog.")
    # coverage: 1/1, correctness: 4/4=1.0, awareness: 0
    # = 0.4*1.0 + 0.4*1.0 = 0.80
    assert score >= 0.70
