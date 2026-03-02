"""Tests for the AgenticTask type.

Tests cover:
- Valid construction from TaskDefinition with metadata
- build_prompt includes question and index content
- score_response: perfect composite score (1.0)
- score_response: no match (0.0)
- score_response: partial match (between 0 and 1)
- FAIL_TO_PASS / PASS_TO_PASS JSON parsing
- Composite scoring weights (file_mention=0.4, content=0.4, correctness=0.2)
- Edge cases: empty files, missing metadata, JSON string vs list
"""

from __future__ import annotations

import json
from typing import Any

from agent_evals.tasks.agentic import AgenticTask
from agent_evals.tasks.base import TASK_TYPES, TaskDefinition

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _agentic_task(**meta_overrides: Any) -> AgenticTask:
    """Create an AgenticTask with default metadata, with optional overrides."""
    meta: dict[str, Any] = {
        "expected_tools": [
            {"name": "read_file", "args": {"path": "src/auth.py"}},
            {"name": "search", "args": {"query": "middleware"}},
        ],
        "files": {
            "src/auth.py": "auth module AuthMiddleware JWTConfig",
            "src/middleware.py": "middleware module RequestHandler",
        },
        "setup_script": "pip install -r requirements.txt",
        "FAIL_TO_PASS": json.dumps(["test_auth_login", "test_auth_logout"]),
        "PASS_TO_PASS": json.dumps(["test_utils_helper"]),
        "message_limit": 10,
        "token_limit": 4096,
    }
    meta.update(meta_overrides)
    defn = TaskDefinition(
        task_id="agentic_001",
        type="agentic",
        question="Fix the authentication bug in the auth module.",
        domain="project_repo",
        difficulty="hard",
        metadata=meta,
    )
    return AgenticTask(defn)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestAgenticTaskConstruction:
    """Tests for AgenticTask construction from TaskDefinition."""

    def test_constructs_from_valid_definition(self) -> None:
        """AgenticTask accepts a TaskDefinition with valid metadata."""
        task = _agentic_task()
        assert len(task.expected_tools) == 2
        assert task.expected_tools[0]["name"] == "read_file"
        assert "src/auth.py" in task.files
        assert task.message_limit == 10
        assert task.token_limit == 4096

    def test_fail_to_pass_parsed_from_json_string(self) -> None:
        """FAIL_TO_PASS JSON string is parsed into a list."""
        task = _agentic_task()
        assert task.fail_to_pass == ["test_auth_login", "test_auth_logout"]

    def test_pass_to_pass_parsed_from_json_string(self) -> None:
        """PASS_TO_PASS JSON string is parsed into a list."""
        task = _agentic_task()
        assert task.pass_to_pass == ["test_utils_helper"]

    def test_fail_to_pass_handles_list_input(self) -> None:
        """FAIL_TO_PASS also works if metadata provides a list directly."""
        task = _agentic_task(FAIL_TO_PASS=["test_direct_list"])
        assert task.fail_to_pass == ["test_direct_list"]

    def test_defaults_for_missing_metadata(self) -> None:
        """AgenticTask uses defaults when metadata keys are absent."""
        defn = TaskDefinition(
            task_id="agentic_002",
            type="agentic",
            question="Fix a bug",
            domain="project_repo",
            difficulty="medium",
            metadata={},
        )
        task = AgenticTask(defn)
        assert task.expected_tools == []
        assert task.files == {}
        assert task.setup_script == ""
        assert task.fail_to_pass == []
        assert task.pass_to_pass == []
        assert task.message_limit == 0
        assert task.token_limit == 0

    def test_registered_in_task_types(self) -> None:
        """AgenticTask is registered in TASK_TYPES for 'agentic'."""
        assert TASK_TYPES["agentic"] is AgenticTask


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


class TestAgenticTaskBuildPrompt:
    """Tests for AgenticTask.build_prompt."""

    def test_returns_message_list(self) -> None:
        """build_prompt returns a list of message dicts."""
        task = _agentic_task()
        messages = task.build_prompt("# Project Index")
        assert isinstance(messages, list)
        assert len(messages) >= 2

    def test_includes_index_content(self) -> None:
        """build_prompt includes the index content in messages."""
        task = _agentic_task()
        messages = task.build_prompt("UNIQUE_AGENTIC_INDEX")
        all_content = " ".join(m["content"] for m in messages)
        assert "UNIQUE_AGENTIC_INDEX" in all_content

    def test_includes_question(self) -> None:
        """build_prompt includes the task question in messages."""
        task = _agentic_task()
        messages = task.build_prompt("index")
        all_content = " ".join(m["content"] for m in messages)
        assert "Fix the authentication bug" in all_content


# ---------------------------------------------------------------------------
# score_response: text-based composite scoring
# ---------------------------------------------------------------------------


class TestAgenticTaskScoring:
    """Tests for AgenticTask.score_response with text-based composite scoring."""

    def test_perfect_score_all_components(self) -> None:
        """Response mentioning all files, content keywords, tools, and test names scores 1.0."""
        task = _agentic_task()
        # Mention both file paths, all content keywords, both tool names, and both test names
        response = (
            "I used read_file on src/auth.py and search on src/middleware.py. "
            "The auth module uses AuthMiddleware and JWTConfig. "
            "The middleware module uses RequestHandler. "
            "The fix resolves test_auth_login and test_auth_logout."
        )
        score = task.score_response(response)
        assert score == 1.0

    def test_zero_score_no_components(self) -> None:
        """Response with no file paths, no keywords, no test names scores 0.0."""
        task = _agentic_task()
        response = "I'm not sure how to fix this."
        score = task.score_response(response)
        assert score == 0.0

    def test_file_mention_component(self) -> None:
        """File path mentions contribute to the score via 0.3 weight (with tools present)."""
        task = _agentic_task()
        # Use file paths that also leak some content keywords ("auth", "middleware")
        response = "I looked at src/auth.py and src/middleware.py but found nothing."
        score = task.score_response(response)
        # File mention: 2/2 * 0.3 = 0.3
        # Content: "auth" and "middleware" leak as keyword matches (2/7) * 0.3 ~ 0.086
        # Total ~ 0.386
        assert score > 0.3

    def test_content_component(self) -> None:
        """Content keyword overlap contributes 0.4 to the score."""
        task = _agentic_task()
        # Mention all content keywords but no file paths or test names
        response = (
            "The auth module uses AuthMiddleware and JWTConfig. "
            "The middleware module uses RequestHandler."
        )
        score_with_content = task.score_response(response)
        score_without_content = task.score_response("nothing relevant here")
        content_contribution = score_with_content - score_without_content
        # Content keywords should contribute roughly 0.4
        assert content_contribution > 0.2

    def test_correctness_component(self) -> None:
        """Correctness (test name mention) contributes 0.2 to the score."""
        task = _agentic_task()
        # Both responses share the same keyword leakage ("auth" appears in test names)
        # so the difference isolates correctness weight
        response_with_tests = "Fixed test_auth_login and test_auth_logout."
        response_without_tests = "Fixed the bug."
        score_with = task.score_response(response_with_tests)
        score_without = task.score_response(response_without_tests)
        correctness_contribution = score_with - score_without
        # Correctness: 0.2 weight. Also "auth" keyword leaks in with_tests,
        # so difference includes content bonus: (1/7)*0.4 ~ 0.057
        # Total difference ~ 0.257
        assert 0.2 < correctness_contribution < 0.3

    def test_partial_file_mention(self) -> None:
        """Partial file path mention scores proportionally."""
        task = _agentic_task()
        # Only 1 of 2 expected files
        response = "I checked src/auth.py only."
        score = task.score_response(response)
        # File mention: 1/2 * 0.4 = 0.2, rest roughly 0
        assert 0.0 < score < 0.4

    def test_kwargs_accepted_but_unused(self) -> None:
        """score_response accepts kwargs for interface compatibility but ignores them."""
        task = _agentic_task()
        response = "test_auth_login test_auth_logout"
        # Passing kwargs should not change the score
        score_with_kwargs = task.score_response(
            response,
            tool_calls=[{"name": "read_file"}],
            accessed_files=["src/auth.py"],
        )
        score_without_kwargs = task.score_response(response)
        assert score_with_kwargs == score_without_kwargs

    def test_score_without_kwargs(self) -> None:
        """score_response works without any kwargs."""
        task = _agentic_task()
        response = "test_auth_login test_auth_logout"
        # Correctness: 2/2 * 0.2 = 0.2
        # Content: "auth" keyword leaks as substring match (1/7) * 0.4 ~ 0.057
        # Total ~ 0.257
        score = task.score_response(response)
        assert 0.2 < score < 0.3

    def test_score_clamped_between_0_and_1(self) -> None:
        """Score is always between 0.0 and 1.0."""
        task = _agentic_task()
        for resp in [
            "test_auth_login test_auth_logout src/auth.py",
            "nothing",
            "",
        ]:
            score = task.score_response(resp)
            assert 0.0 <= score <= 1.0

    def test_empty_files_metadata(self) -> None:
        """When files metadata is empty, file and content scores are 0.0."""
        task = _agentic_task(files={})
        response = "test_auth_login test_auth_logout"
        score = task.score_response(response)
        # Only correctness: 1.0 * 0.2 = 0.2
        assert abs(score - 0.2) < 0.01

    def test_case_insensitive_file_matching(self) -> None:
        """File path matching is case-insensitive."""
        task = _agentic_task()
        response = "I looked at SRC/AUTH.PY and SRC/MIDDLEWARE.PY."
        score = task.score_response(response)
        # Both files matched via case-insensitive check
        assert score >= 0.35  # at least file_mention component

    def test_case_insensitive_keyword_matching(self) -> None:
        """Content keyword matching is case-insensitive."""
        task = _agentic_task()
        response = "The AUTH MODULE uses AUTHMIDDLEWARE and JWTCONFIG."
        score = task.score_response(response)
        # Content keywords matched via case-insensitive check
        assert score > 0.0


# ---------------------------------------------------------------------------
# Step 3.3: Tool ordering validation and extra step penalty
# ---------------------------------------------------------------------------


class TestAgenticToolOrdering:
    """Tests for tool ordering validation in agentic scoring."""

    def test_correct_tool_order_not_penalized(self) -> None:
        """Response mentioning tools in the expected order is not penalized."""
        task = _agentic_task(
            expected_tools=[
                {"name": "read_file"},
                {"name": "search"},
            ],
            files={},
            FAIL_TO_PASS=[],
        )
        response = "First I used read_file to check the code, then search to find references."
        score = task.score_response(response)
        assert score > 0.0

    def test_wrong_tool_order_penalized(self) -> None:
        """Response mentioning tools in wrong order scores lower than correct order."""
        task = _agentic_task(
            expected_tools=[
                {"name": "read_file"},
                {"name": "search"},
            ],
            files={},
            FAIL_TO_PASS=[],
        )
        correct_order = "First I used read_file to check the code, then search to find references."
        wrong_order = "First I used search to find references, then read_file to check."
        correct_score = task.score_response(correct_order)
        wrong_score = task.score_response(wrong_order)
        assert correct_score > wrong_score

    def test_extra_tools_penalized(self) -> None:
        """Response mentioning tools not in expected_tools is penalized."""
        task = _agentic_task(
            expected_tools=[
                {"name": "read_file"},
            ],
            files={},
            FAIL_TO_PASS=[],
        )
        clean_response = "I used read_file to check the file."
        extra_response = "I used read_file and then execute_code and deploy_app to fix it."
        clean_score = task.score_response(clean_response)
        extra_score = task.score_response(extra_response)
        assert clean_score >= extra_score


def test_space_separated_test_names_parsed_correctly():
    """test_foo test_bar must parse as two items."""
    from agent_evals.tasks.agentic import _parse_json_or_list
    result = _parse_json_or_list("test_foo test_bar")
    assert result == ["test_foo", "test_bar"], f"Got: {result}"

