"""Tests for the AgenticTask type.

Tests cover:
- Valid construction from TaskDefinition with metadata
- build_prompt includes question and index content
- score_response: perfect composite score (1.0)
- score_response: no match (0.0)
- score_response: partial match (between 0 and 1)
- FAIL_TO_PASS / PASS_TO_PASS JSON parsing
- Composite scoring weights (tool=0.3, files=0.3, correctness=0.4)
- Edge cases: empty tools, missing kwargs, JSON string vs list
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
            "src/auth.py": "auth module",
            "src/middleware.py": "middleware module",
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
# score_response: composite scoring
# ---------------------------------------------------------------------------


class TestAgenticTaskScoring:
    """Tests for AgenticTask.score_response with composite scoring."""

    def test_perfect_score_all_components(self) -> None:
        """Response with all tools, all files, and all test names scores 1.0."""
        task = _agentic_task()
        response = (
            "I accessed src/auth.py and src/middleware.py. "
            "The fix resolves test_auth_login and test_auth_logout."
        )
        tool_calls = [
            {"name": "read_file", "args": {"path": "src/auth.py"}},
            {"name": "search", "args": {"query": "middleware"}},
        ]
        score = task.score_response(
            response,
            tool_calls=tool_calls,
            accessed_files=["src/auth.py", "src/middleware.py"],
        )
        assert score == 1.0

    def test_zero_score_no_components(self) -> None:
        """Response with no tools, no files, no test names scores 0.0."""
        task = _agentic_task()
        response = "I'm not sure how to fix this."
        score = task.score_response(response, tool_calls=[], accessed_files=[])
        assert score == 0.0

    def test_tool_invocation_component(self) -> None:
        """Tool invocation contributes 0.3 to the score."""
        task = _agentic_task()
        response = "test_auth_login test_auth_logout"  # correctness match
        # All tools matched, but no files
        tool_calls = [
            {"name": "read_file", "args": {}},
            {"name": "search", "args": {}},
        ]
        score_with_tools = task.score_response(
            response, tool_calls=tool_calls, accessed_files=[]
        )
        score_without_tools = task.score_response(
            response, tool_calls=[], accessed_files=[]
        )
        # Difference should be approximately 0.3 (tool weight)
        tool_contribution = score_with_tools - score_without_tools
        assert abs(tool_contribution - 0.3) < 0.01

    def test_file_selection_component(self) -> None:
        """File selection contributes 0.3 to the score."""
        task = _agentic_task()
        response = "test_auth_login test_auth_logout"  # correctness match
        score_with_files = task.score_response(
            response,
            tool_calls=[],
            accessed_files=["src/auth.py", "src/middleware.py"],
        )
        score_without_files = task.score_response(
            response, tool_calls=[], accessed_files=[]
        )
        file_contribution = score_with_files - score_without_files
        assert abs(file_contribution - 0.3) < 0.01

    def test_correctness_component(self) -> None:
        """Correctness (test name mention) contributes 0.4 to the score."""
        task = _agentic_task()
        response_with_tests = "Fixed test_auth_login and test_auth_logout."
        response_without_tests = "Fixed the bug."
        score_with = task.score_response(
            response_with_tests, tool_calls=[], accessed_files=[]
        )
        score_without = task.score_response(
            response_without_tests, tool_calls=[], accessed_files=[]
        )
        correctness_contribution = score_with - score_without
        assert abs(correctness_contribution - 0.4) < 0.01

    def test_partial_tool_match(self) -> None:
        """Partial tool invocation scores proportionally."""
        task = _agentic_task()
        response = "Something"
        # Only 1 of 2 expected tools
        tool_calls = [{"name": "read_file", "args": {}}]
        score = task.score_response(response, tool_calls=tool_calls, accessed_files=[])
        # Tool component: 0.5 * 0.3 = 0.15
        assert 0.0 < score < 0.3

    def test_missing_kwargs_defaults_to_empty(self) -> None:
        """score_response works without tool_calls or accessed_files kwargs."""
        task = _agentic_task()
        response = "test_auth_login test_auth_logout"
        # Only correctness component should contribute
        score = task.score_response(response)
        assert abs(score - 0.4) < 0.01

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
