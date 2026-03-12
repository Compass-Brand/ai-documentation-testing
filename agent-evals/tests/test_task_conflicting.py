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
            {"name": "config.md", "claim": "The timeout is 30 seconds", "authority": 3},
            {"name": "api-reference.md", "claim": "The timeout is 60 seconds", "authority": 5},
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

    def test_exact_match_returns_resolution_weight(self) -> None:
        """Bare exact match scores 0.5 (resolution axis only, no source/strategy)."""
        task = _conflicting_task()
        score = task.score_response("The timeout is 60 seconds by default.")
        assert score == 0.5

    def test_exact_match_case_insensitive(self) -> None:
        """Exact matching is case-insensitive (resolution axis)."""
        task = _conflicting_task()
        score = task.score_response("the timeout is 60 seconds according to docs.")
        assert score == 0.5

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


# ---------------------------------------------------------------------------
# Multi-axis scoring
# ---------------------------------------------------------------------------


class TestConflictingMultiAxis:
    """Tests for 3-axis scoring: resolution (50%), source awareness (30%), strategy (20%)."""

    def test_correct_resolution_plus_sources_scores_higher(self) -> None:
        """Response mentioning sources should score higher than bare answer."""
        task = _conflicting_task(
            expected_resolution="use version 2",
            sources=[
                {"name": "config.yaml", "claim": "version 1", "authority": 3},
                {"name": "README.md", "claim": "version 2", "authority": 5},
            ],
        )
        bare = task.score_response("use version 2")
        with_sources = task.score_response(
            "config.yaml says version 1 but README.md says version 2. use version 2"
        )
        assert with_sources > bare

    def test_wrong_resolution_with_sources_gets_partial(self) -> None:
        """Wrong answer but acknowledging sources gets partial credit."""
        task = _conflicting_task(
            expected_resolution="adopt the v2 endpoint",
            sources=[
                {"name": "config.yaml", "claim": "v1 endpoint", "authority": 3},
                {"name": "README.md", "claim": "v2 endpoint", "authority": 5},
            ],
        )
        # Wrong answer, mentions sources but no strategy phrases
        score = task.score_response(
            "config.yaml and README.md have different answers. I recommend v1."
        )
        # resolution=0 (neither "adopt" nor "endpoint" in response), sources=1.0, strategy=0
        # score = 0*0.5 + 1.0*0.3 + 0*0.2 = 0.3
        assert 0.0 < score < 0.5

    def test_source_awareness_checks_name_key(self) -> None:
        """Source awareness uses 'name' key from source metadata."""
        task = _conflicting_task(
            expected_resolution="answer",
            sources=[
                {"name": "alpha.md", "claim": "A", "authority": 3},
                {"name": "beta.md", "claim": "B", "authority": 5},
            ],
        )
        no_sources = task.score_response("answer")
        one_source = task.score_response("answer. See alpha.md for details")
        both_sources = task.score_response("alpha.md and beta.md both say answer")
        assert both_sources > one_source >= no_sources

    def test_strategy_recognition_phrases(self) -> None:
        """Response mentioning conflict/contradiction gets strategy credit."""
        task = _conflicting_task(expected_resolution="use version 2")
        no_strategy = task.score_response("use version 2")
        with_strategy = task.score_response(
            "The sources contradict each other. use version 2"
        )
        assert with_strategy > no_strategy

    def test_pipe_separated_alternatives_still_work(self) -> None:
        """Pipe-separated alternatives in expected_resolution still match."""
        task = _conflicting_task(
            expected_resolution="use v2|adopt version 2",
        )
        score_alt1 = task.score_response("You should use v2.")
        score_alt2 = task.score_response("I recommend you adopt version 2.")
        assert score_alt1 > 0.0
        assert score_alt2 > 0.0

    def test_perfect_response_near_1(self) -> None:
        """Response with correct answer, sources, and strategy phrases scores near 1.0."""
        task = _conflicting_task(
            expected_resolution="use version 2",
            sources=[
                {"name": "config.yaml", "claim": "version 1", "authority": 3},
                {"name": "README.md", "claim": "version 2", "authority": 5},
            ],
        )
        score = task.score_response(
            "config.yaml and README.md contradict each other. "
            "Since README.md has higher authority, use version 2."
        )
        assert score >= 0.9

    def test_empty_sources_no_source_axis(self) -> None:
        """With no sources metadata, source axis contributes 0."""
        task = _conflicting_task(expected_resolution="answer", sources=[])
        score = task.score_response("answer")
        # Only resolution (50%) + maybe strategy (20%) contribute
        assert 0.4 <= score <= 0.7
