"""Tests for the MultiHopTask type.

Tests cover:
- Valid construction from TaskDefinition with metadata
- Defaults for missing metadata
- Registration in TASK_TYPES
- build_prompt returns message list with index content and question
- score_response: perfect match (1.0)
- score_response: no match (0.0)
- score_response: partial matches (between 0 and 1)
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

    def test_all_decomposition_steps_answered_returns_1(self) -> None:
        """Response addressing all decomposition steps scores 1.0."""
        task = _multi_hop_task(
            question_decomposition=[
                "Who created Python?",
                "Where did the creator work?",
            ],
        )
        response = "Python was created by Guido. The creator worked at Google."
        score = task.score_response(response)
        assert score == 1.0

    def test_no_decomposition_steps_answered_returns_0(self) -> None:
        """Response addressing no decomposition steps scores 0.0."""
        task = _multi_hop_task(
            question_decomposition=[
                "Who created Python?",
                "Where did the creator work?",
            ],
        )
        response = "I have no idea about any of this."
        score = task.score_response(response)
        assert score == 0.0

    def test_partial_decomposition_steps_answered(self) -> None:
        """Response addressing some decomposition steps scores partially."""
        task = _multi_hop_task(
            question_decomposition=[
                "Who created Python?",
                "Where did the creator work?",
            ],
        )
        # Only the first step has keyword match ("created", "Python")
        response = "Python was created by someone unknown."
        score = task.score_response(response)
        assert 0.0 < score < 1.0

    def test_empty_decomposition_returns_1(self) -> None:
        """Empty decomposition list returns 1.0 (vacuous truth)."""
        task = _multi_hop_task(question_decomposition=[])
        score = task.score_response("Any response")
        assert score == 1.0

    def test_stopwords_excluded_from_keyword_matching(self) -> None:
        """Stopwords and short words are excluded from keyword extraction."""
        task = _multi_hop_task(
            question_decomposition=[
                "What is the main use of the system?",
            ],
        )
        # Only contains stopwords from the step, not keywords like "main", "system"
        response = "the use of it is that"
        score = task.score_response(response)
        assert score < 1.0

    def test_score_clamped_between_0_and_1(self) -> None:
        """Score is always between 0.0 and 1.0."""
        task = _multi_hop_task()
        for resp in ["complete answer with Python and Google", "nothing", ""]:
            score = task.score_response(resp)
            assert 0.0 <= score <= 1.0

    def test_case_insensitive_keyword_matching(self) -> None:
        """Keyword matching is case-insensitive."""
        task = _multi_hop_task(
            question_decomposition=[
                "Who created Python?",
            ],
        )
        response = "PYTHON was CREATED by Guido."
        score = task.score_response(response)
        assert score == 1.0
