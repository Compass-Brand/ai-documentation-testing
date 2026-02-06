"""Agentic task type for evaluating multi-step coding agent behaviour.

Composite score with 3 components:
- Tool invocation (0.3): Did the agent invoke expected tools?
- File selection (0.3): Did the agent access the right files?
- Correctness (0.4): Heuristic check for FAIL_TO_PASS test names in response.
"""

from __future__ import annotations

import json
from typing import Any

from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type


def _parse_json_or_list(value: object) -> list[str]:
    """Parse a value that is either a JSON string or already a list.

    Args:
        value: A JSON string, a list, or any other value.

    Returns:
        A list of strings.
    """
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value.strip():
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        return [str(parsed)]
    return []


class AgenticTask(EvalTask):
    """Task type for evaluating agentic coding behaviour.

    Scores responses using a composite of tool invocation accuracy,
    file selection accuracy, and correctness heuristics based on
    FAIL_TO_PASS test names.
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta = definition.metadata
        self.expected_tools: list[dict[str, Any]] = meta.get("expected_tools", [])
        self.files: dict[str, str] = meta.get("files", {})
        self.setup_script: str = meta.get("setup_script", "")
        self.fail_to_pass: list[str] = _parse_json_or_list(
            meta.get("FAIL_TO_PASS", "")
        )
        self.pass_to_pass: list[str] = _parse_json_or_list(
            meta.get("PASS_TO_PASS", "")
        )
        self.message_limit: int = meta.get("message_limit", 0)
        self.token_limit: int = meta.get("token_limit", 0)

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build messages for agentic task evaluation.

        Args:
            index_content: The documentation index content.

        Returns:
            List of message dicts with system and user messages.
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an AI coding agent. Use the following "
                    "documentation index and project context to solve "
                    "the coding problem. You may use tools to read files, "
                    "search code, and make changes.\n\n"
                    f"{index_content}"
                ),
            },
            {
                "role": "user",
                "content": self.definition.question,
            },
        ]

    def score_response(self, response: str, **kwargs: object) -> float:
        """Score response using composite of tool, file, and correctness metrics.

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context:
                - tool_calls: list[dict] of tool invocations
                - accessed_files: list[str] of accessed file paths

        Returns:
            Composite score between 0.0 and 1.0.
        """
        tool_score = self._score_tools(kwargs.get("tool_calls", []))
        file_score = self._score_files(kwargs.get("accessed_files", []))
        correctness_score = self._score_correctness(response)

        composite = tool_score * 0.3 + file_score * 0.3 + correctness_score * 0.4
        return max(0.0, min(1.0, composite))

    def _score_tools(self, tool_calls: object) -> float:
        """Score tool invocation accuracy.

        Args:
            tool_calls: List of tool call dicts with 'name' keys.

        Returns:
            Fraction of expected tools that were invoked.
        """
        if not self.expected_tools:
            return 0.0

        if not isinstance(tool_calls, list):
            return 0.0

        invoked_names: set[str] = set()
        for call in tool_calls:
            if isinstance(call, dict) and "name" in call:
                invoked_names.add(call["name"])

        expected_names = {t["name"] for t in self.expected_tools if "name" in t}
        if not expected_names:
            return 0.0

        matched = len(expected_names & invoked_names)
        return matched / len(expected_names)

    def _score_files(self, accessed_files: object) -> float:
        """Score file selection accuracy.

        Args:
            accessed_files: List of file paths accessed by the agent.

        Returns:
            Fraction of expected files that were accessed.
        """
        if not self.files:
            return 0.0

        if not isinstance(accessed_files, list):
            return 0.0

        expected_paths = set(self.files.keys())
        accessed_set: set[str] = set()
        for f in accessed_files:
            if isinstance(f, str):
                accessed_set.add(f)

        matched = len(expected_paths & accessed_set)
        return matched / len(expected_paths)

    def _score_correctness(self, response: str) -> float:
        """Score correctness by checking if FAIL_TO_PASS test names appear in response.

        Args:
            response: The raw text response from the LLM.

        Returns:
            Fraction of FAIL_TO_PASS test names mentioned in the response.
        """
        if not self.fail_to_pass:
            return 0.0

        response_lower = response.lower()
        matched = sum(
            1 for test_name in self.fail_to_pass
            if test_name.lower() in response_lower
        )
        return matched / len(self.fail_to_pass)


register_task_type("agentic", AgenticTask)
