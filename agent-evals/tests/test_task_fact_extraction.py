"""Tests for the FactExtractionTask type.

Tests cover:
- Valid construction from TaskDefinition with metadata
- build_prompt includes question and index content
- score_response: exact match (1.0)
- score_response: no match (0.0)
- score_response: partial keyword match (between 0 and 1)
- Alias matching
- Edge cases: empty answer, stopword filtering
"""

from __future__ import annotations

from typing import Any

from agent_evals.tasks.base import TASK_TYPES, TaskDefinition
from agent_evals.tasks.fact_extraction import FactExtractionTask

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fact_task(**meta_overrides: Any) -> FactExtractionTask:
    """Create a FactExtractionTask with default metadata, with optional overrides."""
    meta: dict[str, Any] = {
        "expected_answer": "JSON Web Token",
        "answer_aliases": ["JWT"],
        "source_location": "docs/auth.md",
        "fact_type": "definition",
    }
    meta.update(meta_overrides)
    defn = TaskDefinition(
        task_id="fact_extraction_001",
        type="fact_extraction",
        question="What token format does the auth system use?",
        domain="framework_api",
        difficulty="easy",
        metadata=meta,
    )
    return FactExtractionTask(defn)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestFactExtractionTaskConstruction:
    """Tests for FactExtractionTask construction from TaskDefinition."""

    def test_constructs_from_valid_definition(self) -> None:
        """FactExtractionTask accepts a TaskDefinition with valid metadata."""
        task = _fact_task()
        assert task.expected_answer == "JSON Web Token"
        assert task.answer_aliases == ["JWT"]
        assert task.source_location == "docs/auth.md"
        assert task.fact_type == "definition"

    def test_defaults_for_missing_metadata(self) -> None:
        """FactExtractionTask uses defaults when metadata keys are absent."""
        defn = TaskDefinition(
            task_id="fact_extraction_002",
            type="fact_extraction",
            question="What is X?",
            domain="framework_api",
            difficulty="easy",
            metadata={},
        )
        task = FactExtractionTask(defn)
        assert task.expected_answer == ""
        assert task.answer_aliases == []
        assert task.source_location == ""
        assert task.fact_type == ""

    def test_registered_in_task_types(self) -> None:
        """FactExtractionTask is registered in TASK_TYPES for 'fact_extraction'."""
        assert TASK_TYPES["fact_extraction"] is FactExtractionTask


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


class TestFactExtractionTaskBuildPrompt:
    """Tests for FactExtractionTask.build_prompt."""

    def test_returns_message_list(self) -> None:
        """build_prompt returns a list of message dicts."""
        task = _fact_task()
        messages = task.build_prompt("# Documentation Index")
        assert isinstance(messages, list)
        assert len(messages) >= 2

    def test_includes_index_content(self) -> None:
        """build_prompt includes the index content in messages."""
        task = _fact_task()
        messages = task.build_prompt("UNIQUE_INDEX_CONTENT_XYZ")
        all_content = " ".join(m["content"] for m in messages)
        assert "UNIQUE_INDEX_CONTENT_XYZ" in all_content

    def test_includes_question(self) -> None:
        """build_prompt includes the task question in messages."""
        task = _fact_task()
        messages = task.build_prompt("index")
        all_content = " ".join(m["content"] for m in messages)
        assert "What token format does the auth system use?" in all_content


# ---------------------------------------------------------------------------
# score_response
# ---------------------------------------------------------------------------


class TestFactExtractionTaskScoring:
    """Tests for FactExtractionTask.score_response."""

    def test_exact_match_returns_1(self) -> None:
        """Response containing exact expected_answer scores 1.0."""
        task = _fact_task(expected_answer="JSON Web Token")
        score = task.score_response("The system uses JSON Web Token for auth.")
        assert score == 1.0

    def test_alias_match_returns_1(self) -> None:
        """Response containing an alias scores 1.0."""
        task = _fact_task(expected_answer="JSON Web Token", answer_aliases=["JWT"])
        score = task.score_response("The system uses JWT for authentication.")
        assert score == 1.0

    def test_no_match_returns_0(self) -> None:
        """Response with no matching keywords scores 0.0."""
        task = _fact_task(expected_answer="JSON Web Token", answer_aliases=["JWT"])
        score = task.score_response("I have no idea about this.")
        assert score == 0.0

    def test_partial_keyword_match(self) -> None:
        """Response with some keywords from expected_answer scores partially."""
        task = _fact_task(
            expected_answer="JSON Web Token",
            answer_aliases=[],
        )
        # Contains "JSON" but not "Web" or "Token"
        score = task.score_response("The format is JSON based.")
        assert 0.0 < score < 1.0

    def test_case_insensitive_exact_match(self) -> None:
        """Exact matching is case-insensitive."""
        task = _fact_task(expected_answer="JSON Web Token")
        score = task.score_response("It uses json web token for everything.")
        assert score == 1.0

    def test_case_insensitive_alias_match(self) -> None:
        """Alias matching is case-insensitive."""
        task = _fact_task(expected_answer="JSON Web Token", answer_aliases=["JWT"])
        score = task.score_response("The system uses jwt tokens.")
        assert score == 1.0

    def test_empty_expected_answer_returns_0(self) -> None:
        """Empty expected_answer gives 0.0 (no keywords to match)."""
        task = _fact_task(expected_answer="", answer_aliases=[])
        score = task.score_response("Some response text.")
        assert score == 0.0

    def test_stopwords_filtered_from_keyword_matching(self) -> None:
        """Stopwords and short words are excluded from keyword matching."""
        # "the" and "of" are common stopwords; "use" is 3 chars but common
        task = _fact_task(
            expected_answer="the use of middleware patterns",
            answer_aliases=[],
        )
        # Response contains only stopwords from the answer, not keywords
        response = "the use of something else"
        score = task.score_response(response)
        # Should NOT score 1.0 because the real keywords are "middleware" and "patterns"
        assert score < 1.0

    def test_score_clamped_between_0_and_1(self) -> None:
        """Score is always between 0.0 and 1.0."""
        task = _fact_task(expected_answer="test answer")
        for resp in ["test answer here", "nothing", "test something"]:
            score = task.score_response(resp)
            assert 0.0 <= score <= 1.0

    def test_diacritics_cafe_vs_cafe_scores_high(self) -> None:
        """'cafe' vs 'café' should score >= 0.9 after diacritic normalization."""
        task = _fact_task(expected_answer="café", answer_aliases=[])
        score = task.score_response("The cafe serves espresso.")
        assert score >= 0.9, f"Expected >= 0.9 for cafe/café, got {score}"

    def test_diacritics_naive_vs_naive_scores_high(self) -> None:
        """'naive' vs 'naïve' should score >= 0.9 after diacritic normalization."""
        task = _fact_task(expected_answer="naïve", answer_aliases=[])
        score = task.score_response("A naive implementation would be slow.")
        assert score >= 0.9, f"Expected >= 0.9 for naive/naïve, got {score}"

    def test_diacritics_resume_vs_resume_scores_high(self) -> None:
        """'resume' vs 'résumé' should score >= 0.9 after diacritic normalization."""
        task = _fact_task(expected_answer="résumé", answer_aliases=[])
        score = task.score_response("Upload your resume to apply.")
        assert score >= 0.9, f"Expected >= 0.9 for resume/résumé, got {score}"

    def test_diacritics_exact_accented_still_matches(self) -> None:
        """Exact accented match still scores 1.0."""
        task = _fact_task(expected_answer="café", answer_aliases=[])
        score = task.score_response("The café is open now.")
        assert score == 1.0

    def test_fuzzy_paraphrase_scores_above_0_7(self) -> None:
        """Fuzzy match boosts score when keyword matching alone falls short."""
        defn = TaskDefinition(
            task_id="fact_extraction_001",
            type="fact_extraction",
            question="Q",
            domain="framework_api",
            difficulty="easy",
            metadata={
                "expected_answer": "dependency injection container",
                "answer_aliases": [],
            },
        )
        task = FactExtractionTask(defn)
        score = task.score_response(
            "The DI injection container manages services."
        )
        assert score >= 0.7, f"Expected >= 0.7 for fuzzy paraphrase, got {score}"


class TestFuzzyScoreContinuous:
    """Tests for linear interpolation within fuzzy-score bands.

    IMPORTANT: token_set_ratio returns 100.0 whenever ALL tokens of the
    expected string appear in the response. To test specific bands, the
    response must be MISSING at least one expected token (replaced with
    a synonym) so the fuzzy score lands in the desired range.

    All inputs below were verified empirically:
      - "database connection pooling strategy" vs "...pooling approach..."  -> 85.71
      - "distributed cache invalidation broadcast notification service handler"
        vs "...service processor"  -> 93.8
      - "database connection pooling strategy" vs "...pooling mechanism..." -> 75.0
    """

    def test_fuzzy_85_scores_above_0_9(self):
        """Fuzzy=85.71 should map to ~0.905 via [85,100] -> [0.9,1.0]."""
        task = _fact_task(
            expected_answer="database connection pooling strategy",
            answer_aliases=[],
        )
        # Missing "strategy", has "approach" instead -> fuzzy=85.71, no exact match
        score = task.score_response(
            "the database connection pooling approach handles resources"
        )
        assert score >= 0.9, f"Expected >= 0.9 for fuzzy=85.71, got {score}"

    def test_fuzzy_94_scores_between_0_9_and_1(self):
        """Fuzzy=93.8 should map to ~0.959, strictly between 0.9 and 1.0."""
        task = _fact_task(
            expected_answer=(
                "distributed cache invalidation broadcast notification service handler"
            ),
            answer_aliases=[],
        )
        # Missing "handler", has "processor" instead -> fuzzy=93.8, no exact match
        score = task.score_response(
            "the distributed cache invalidation broadcast notification service processor"
        )
        assert 0.9 < score < 1.0, (
            f"Expected strictly between 0.9 and 1.0 for fuzzy=93.8, got {score}"
        )

    def test_fuzzy_75_scores_between_0_7_and_0_9(self):
        """Fuzzy=75.0 should map to ~0.767 via [70,85) -> [0.7,0.9)."""
        task = _fact_task(
            expected_answer="database connection pooling strategy",
            answer_aliases=[],
        )
        # Missing "connection" and "strategy" -> fuzzy=75.0, no exact match
        score = task.score_response(
            "a database pooling mechanism for connections"
        )
        assert 0.7 <= score < 0.9, (
            f"Expected between 0.7 and 0.9 for fuzzy=75.0, got {score}"
        )

    def test_monotonic_with_fuzzy_score(self):
        """Higher fuzzy score always produces higher or equal final score."""
        task = _fact_task(
            expected_answer="database connection pooling strategy",
            answer_aliases=[],
        )
        # fuzzy=85.71 (missing "strategy") -> score ~0.905
        s_high = task.score_response(
            "the database connection pooling approach handles resources"
        )
        # fuzzy=75.0 (missing "connection" + "strategy") -> score ~0.767
        s_mid = task.score_response(
            "a database pooling mechanism for connections"
        )
        # fuzzy=65.38 (only 2/4 tokens match) -> score ~0.654
        s_low = task.score_response(
            "the database has a caching strategy"
        )
        assert s_low <= s_mid <= s_high, (
            f"Monotonicity violated: low={s_low}, mid={s_mid}, high={s_high}"
        )

