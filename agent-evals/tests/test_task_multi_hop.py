"""Tests for the MultiHopTask type.

Tests cover:
- Valid construction from TaskDefinition with metadata
- Defaults for missing metadata
- Registration in TASK_TYPES
- build_prompt returns message list with index content and question
- score_response: perfect match (1.0)
- score_response: no match (0.0)
- score_response: partial matches (between 0 and 1)
- score_response: uses reasoning_chain over question_decomposition
- score_response: falls back to question_decomposition when needed
- score_response: empty-keyword steps excluded from denominator
- score_response: word-boundary matching for short keywords
- score_response: punctuation stripping in keywords
- Edge cases and score bounding
"""

from __future__ import annotations

from typing import Any

from agent_evals.tasks.base import TASK_TYPES, TaskDefinition
from agent_evals.tasks.multi_hop import MultiHopTask

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _multi_hop_task(**meta_overrides: Any) -> MultiHopTask:
    """Create a MultiHopTask with default metadata, with optional overrides."""
    meta: dict[str, Any] = {
        "paragraphs": [
            {"id": "p1", "text": "Python was created by Guido van Rossum."},
            {"id": "p2", "text": "Guido van Rossum worked at Google."},
        ],
        "question_decomposition": [
            "Who created Python?",
            "Where did the creator of Python work?",
        ],
        "reasoning_chain": [
            "Python was created by Guido van Rossum.",
            "Guido van Rossum worked at Google.",
        ],
    }
    meta.update(meta_overrides)
    defn = TaskDefinition(
        task_id="multi_hop_001",
        type="multi_hop",
        question="Where did the creator of Python work?",
        domain="framework_api",
        difficulty="medium",
        metadata=meta,
    )
    return MultiHopTask(defn)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestMultiHopTaskConstruction:
    """Tests for MultiHopTask construction from TaskDefinition."""

    def test_constructs_from_valid_definition(self) -> None:
        """MultiHopTask accepts a TaskDefinition with valid metadata."""
        task = _multi_hop_task()
        assert len(task.paragraphs) == 2
        assert len(task.question_decomposition) == 2
        assert len(task.reasoning_chain) == 2

    def test_defaults_for_missing_metadata(self) -> None:
        """MultiHopTask uses defaults when metadata keys are absent."""
        defn = TaskDefinition(
            task_id="multi_hop_002",
            type="multi_hop",
            question="Some question",
            domain="framework_api",
            difficulty="easy",
            metadata={},
        )
        task = MultiHopTask(defn)
        assert task.paragraphs == []
        assert task.question_decomposition == []
        assert task.reasoning_chain == []

    def test_registered_in_task_types(self) -> None:
        """MultiHopTask is registered in TASK_TYPES for 'multi_hop'."""
        assert TASK_TYPES["multi_hop"] is MultiHopTask


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


class TestMultiHopTaskBuildPrompt:
    """Tests for MultiHopTask.build_prompt."""

    def test_returns_message_list(self) -> None:
        """build_prompt returns a list of message dicts."""
        task = _multi_hop_task()
        messages = task.build_prompt("# Index Content")
        assert isinstance(messages, list)
        assert len(messages) >= 2

    def test_includes_index_content(self) -> None:
        """build_prompt includes the index content in messages."""
        task = _multi_hop_task()
        messages = task.build_prompt("UNIQUE_MULTI_HOP_INDEX")
        all_content = " ".join(m["content"] for m in messages)
        assert "UNIQUE_MULTI_HOP_INDEX" in all_content

    def test_includes_question(self) -> None:
        """build_prompt includes the task question in messages."""
        task = _multi_hop_task()
        messages = task.build_prompt("index")
        all_content = " ".join(m["content"] for m in messages)
        assert "Where did the creator of Python work?" in all_content

    def test_system_message_mentions_multi_step(self) -> None:
        """build_prompt system message includes multi-step reasoning instruction."""
        task = _multi_hop_task()
        messages = task.build_prompt("index")
        system_content = messages[0]["content"]
        assert "multi" in system_content.lower() or "step" in system_content.lower()


# ---------------------------------------------------------------------------
# score_response
# ---------------------------------------------------------------------------


class TestMultiHopTaskScoring:
    """Tests for MultiHopTask.score_response."""

    def test_all_reasoning_chain_steps_matched_returns_1(self) -> None:
        """Response addressing all reasoning-chain steps scores 1.0."""
        task = _multi_hop_task(
            reasoning_chain=[
                "Python was created by Guido van Rossum.",
                "Guido van Rossum worked at Google.",
            ],
        )
        response = "Python was created by Guido. He worked at Google."
        score = task.score_response(response)
        assert score == 1.0

    def test_no_reasoning_chain_steps_matched_returns_0(self) -> None:
        """Response addressing no reasoning-chain steps scores 0.0."""
        task = _multi_hop_task(
            reasoning_chain=[
                "Python was created by Guido van Rossum.",
                "Guido van Rossum worked at Google.",
            ],
        )
        response = "I have no idea about any of this."
        score = task.score_response(response)
        assert score == 0.0

    def test_partial_reasoning_chain_steps_matched(self) -> None:
        """Response addressing some reasoning-chain steps scores partially."""
        task = _multi_hop_task(
            reasoning_chain=[
                "Python was created by Guido van Rossum.",
                "The annual revenue was 5 billion dollars.",
            ],
        )
        # Matches step 1 keywords ("Python", "created", "Guido") but
        # not step 2 keywords ("annual", "revenue", "billion", "dollars")
        response = "Python was created by Guido but I don't know the finances."
        score = task.score_response(response)
        assert 0.0 < score < 1.0

    def test_uses_reasoning_chain_over_question_decomposition(self) -> None:
        """Scorer prefers reasoning_chain when it exists and is same length."""
        task = _multi_hop_task(
            question_decomposition=[
                "What is the default TTL?",
                "Which env var configures Redis?",
            ],
            reasoning_chain=[
                "caching.md states default_ttl=300",
                "config.md states REDIS_URL is the env var",
            ],
        )
        # Response echoes question terms but NOT answer terms
        response = "The default TTL for cached responses is configured via Redis."
        score = task.score_response(response)
        # Should NOT be 1.0 because "300", "default_ttl", "REDIS_URL" are missing
        assert score < 1.0

    def test_falls_back_to_decomposition_when_chain_empty(self) -> None:
        """Falls back to question_decomposition when reasoning_chain is empty."""
        task = _multi_hop_task(
            question_decomposition=[
                "Who created Python?",
                "Where did the creator work?",
            ],
            reasoning_chain=[],
        )
        response = "Python was created by someone. The creator worked somewhere."
        score = task.score_response(response)
        assert score == 1.0

    def test_falls_back_to_decomposition_when_chain_shorter(self) -> None:
        """Falls back to question_decomposition when reasoning_chain is shorter."""
        task = _multi_hop_task(
            question_decomposition=[
                "Who created Python?",
                "Where did the creator work?",
            ],
            reasoning_chain=[
                "Python was created by Guido.",
            ],
        )
        # Should use question_decomposition (2 steps) since reasoning_chain has only 1
        # "created" and "Python" match step 1; "creator" and "work" match step 2
        response = "Python was created by someone. The creator did work."
        score = task.score_response(response)
        assert score == 1.0

    def test_empty_both_returns_1(self) -> None:
        """Empty reasoning_chain and question_decomposition returns 1.0."""
        task = _multi_hop_task(question_decomposition=[], reasoning_chain=[])
        score = task.score_response("Any response")
        assert score == 1.0

    def test_empty_keyword_steps_excluded_from_denominator(self) -> None:
        """Steps with no extractable keywords are excluded from scoring."""
        task = _multi_hop_task(
            reasoning_chain=[
                "the and for",  # All stopwords, no extractable keywords
                "Python was created by Guido van Rossum.",
            ],
            question_decomposition=[],
        )
        # Only 1 scorable step (the second). Response matches it.
        response = "Python was created by Guido."
        score = task.score_response(response)
        assert score == 1.0

    def test_all_empty_keyword_steps_returns_1(self) -> None:
        """If every step has no extractable keywords, return 1.0."""
        task = _multi_hop_task(
            reasoning_chain=[
                "the and for",
                "but not all",
            ],
            question_decomposition=[],
        )
        score = task.score_response("anything")
        assert score == 1.0

    def test_stopwords_excluded_from_keyword_matching(self) -> None:
        """Stopwords and short words are excluded from keyword extraction."""
        task = _multi_hop_task(
            reasoning_chain=[
                "The main system performs the critical role.",
            ],
            question_decomposition=[],
        )
        # Only contains stopwords, not keywords like "main", "system", "performs"
        response = "the use of it is that"
        score = task.score_response(response)
        assert score < 1.0

    def test_score_clamped_between_0_and_1(self) -> None:
        """Score is always between 0.0 and 1.0."""
        task = _multi_hop_task()
        for resp in ["Guido van Rossum created Python at Google", "nothing", ""]:
            score = task.score_response(resp)
            assert 0.0 <= score <= 1.0

    def test_case_insensitive_keyword_matching(self) -> None:
        """Keyword matching is case-insensitive."""
        task = _multi_hop_task(
            reasoning_chain=[
                "Python was created by Guido van Rossum.",
            ],
            question_decomposition=[],
        )
        response = "PYTHON was CREATED by GUIDO."
        score = task.score_response(response)
        assert score == 1.0

    def test_word_boundary_matching_for_short_keywords(self) -> None:
        """Short keywords (3-4 chars) use word boundaries to avoid substrings."""
        task = _multi_hop_task(
            reasoning_chain=[
                "The TTL value is 300.",
            ],
            question_decomposition=[],
        )
        # "TTL" should NOT match inside "throttle" or "battle"
        response = "The throttle battles are fierce."
        score = task.score_response(response)
        assert score < 1.0

    def test_word_boundary_matching_allows_exact_short_keyword(self) -> None:
        """Short keywords match when they appear as whole words."""
        task = _multi_hop_task(
            reasoning_chain=[
                "The TTL value is 300.",
            ],
            question_decomposition=[],
        )
        response = "The TTL is set to 300 seconds."
        score = task.score_response(response)
        assert score == 1.0

    def test_punctuation_stripped_from_keywords(self) -> None:
        """Keywords with trailing punctuation are properly stripped."""
        task = _multi_hop_task(
            reasoning_chain=[
                "The default_ttl value is 300.",
                "REDIS_URL is the required env var.",
            ],
            question_decomposition=[],
        )
        # "300" should match even though source had "300." (trailing period)
        # "REDIS_URL" should match even though source had "var." (trailing period)
        response = "The default_ttl is 300 and REDIS_URL must be set."
        score = task.score_response(response)
        assert score == 1.0
