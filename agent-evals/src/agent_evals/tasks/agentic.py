"""Agentic task type for evaluating multi-step coding agent behaviour.

Composite score with dynamic weight redistribution based on available metadata:
- File mention: Do expected file paths appear in the response text?
- Content: Do key facts from file content summaries appear in the response?
- Tool usage: Are expected tools mentioned in the correct order, penalising extras?
- Correctness: Bonus if FAIL_TO_PASS test names appear.

Weights are redistributed proportionally when some metadata is missing,
so components that are present get a larger share of the total score.
"""

from __future__ import annotations

import json
import re
from typing import Any

from agent_evals.tasks._utils import extract_keywords
from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type

# Common tool name patterns for hallucination detection
_TOOL_NAME_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:read_file|write_file|search|grep_files|execute_code|run_tests|"
    r"create_file|delete_file|list_files|edit_file|deploy_app|"
    r"install_package|run_command|open_browser|debug|lint|format_code)\b",
    re.IGNORECASE,
)


def _parse_json_or_list(value: object) -> list[str]:
    """Parse a value that is either a JSON string or already a list.

    Falls back to whitespace splitting if the string is not valid JSON.

    Args:
        value: A JSON string, a list, or any other value.

    Returns:
        A list of strings.
    """
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
            return [str(parsed)]
        except json.JSONDecodeError:
            return [token for token in value.strip().split() if token]
    return []


class AgenticTask(EvalTask):
    """Task type for evaluating agentic coding behaviour.

    Scores responses purely from text, using file-path mentions,
    content-keyword overlap, and optional FAIL_TO_PASS test-name
    mentions as a bonus. Weights are dynamically redistributed
    based on which metadata fields are present.
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
        """Score response using dynamic weight redistribution.

        Builds a list of (score, base_weight) for each present metadata
        component, then normalises weights so they sum to 1.0. This
        ensures that tasks with partial metadata still use the full
        [0.0, 1.0] score range.

        Args:
            response: The raw text response from the LLM.
            **kwargs: Accepted for interface compatibility but unused.

        Returns:
            Composite score between 0.0 and 1.0.
        """
        # Collect (score, base_weight) for each available component
        components: list[tuple[float, float]] = []
        if self.files:
            components.append((self._score_file_mentions(response), 0.4))
            components.append((self._score_content(response), 0.4))
        if self.fail_to_pass:
            components.append((self._score_correctness(response), 0.2))
        if self.expected_tools:
            components.append((self._score_tool_usage(response), 0.2))

        if not components:
            return 0.5

        # Redistribute weights proportionally so they sum to 1.0
        total_weight = sum(w for _, w in components)
        return max(0.0, min(1.0, sum(s * (w / total_weight) for s, w in components)))

    def _score_file_mentions(self, response: str) -> float:
        """Score whether expected file paths appear in the response text."""
        if not self.files:
            return 0.0
        response_lower = response.lower()
        expected_paths = list(self.files.keys())
        matched = sum(
            1 for path in expected_paths if path.lower() in response_lower
        )
        return matched / len(expected_paths)

    def _score_content(self, response: str) -> float:
        """Score keyword overlap between file content summaries and response."""
        if not self.files:
            return 0.0
        all_keywords: list[str] = []
        for summary in self.files.values():
            all_keywords.extend(extract_keywords(summary))
        if not all_keywords:
            return 0.0
        response_lower = response.lower()
        matched = sum(
            1 for kw in all_keywords if kw.lower() in response_lower
        )
        return matched / len(all_keywords)

    def _score_correctness(self, response: str) -> float:
        """Bonus score if FAIL_TO_PASS test names appear in the response."""
        if not self.fail_to_pass:
            return 0.0
        response_lower = response.lower()
        matched = sum(
            1 for test_name in self.fail_to_pass
            if test_name.lower() in response_lower
        )
        return matched / len(self.fail_to_pass)

    def _score_tool_usage(self, response: str) -> float:
        """Score tool usage: mention coverage, ordering, and extra-tool penalty."""
        if not self.expected_tools:
            return 0.0
        response_lower = response.lower()
        expected_names = [
            tool.get("name", "").lower() for tool in self.expected_tools
            if tool.get("name")
        ]
        if not expected_names:
            return 0.0
        mentioned_expected = [
            name for name in expected_names if name in response_lower
        ]
        coverage = len(mentioned_expected) / len(expected_names)
        if not mentioned_expected:
            return 0.0
        if len(mentioned_expected) >= 2:
            positions = [response_lower.index(name) for name in mentioned_expected]
            ordering = 1.0 if positions == sorted(positions) else 0.0
        else:
            ordering = 1.0
        all_mentioned = set(
            m.group().lower() for m in _TOOL_NAME_PATTERN.finditer(response_lower)
        )
        expected_set = set(expected_names)
        extra_tools = all_mentioned - expected_set
        if all_mentioned:
            precision = 1.0 - len(extra_tools) / max(len(all_mentioned), 1)
        else:
            precision = 1.0
        return coverage * 0.5 + ordering * 0.3 + precision * 0.2


register_task_type("agentic", AgenticTask)
