"""Agentic task type for evaluating multi-step coding agent behaviour.

Composite score with 3 text-based components:
- File mention (0.4): Do expected file paths appear in the response text?
- Content (0.4): Do key facts from file content summaries appear in the response?
- Correctness (0.2): Bonus if FAIL_TO_PASS test names appear (not penalised if absent).
"""

from __future__ import annotations

import json
from typing import Any

from agent_evals.tasks._utils import extract_keywords
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

    Scores responses purely from text, using file-path mentions,
    content-keyword overlap, and optional FAIL_TO_PASS test-name
    mentions as a bonus.
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
        """Score response purely from text using file, content, and correctness signals.

        Args:
            response: The raw text response from the LLM.
            **kwargs: Accepted for interface compatibility but unused.

        Returns:
            Composite score between 0.0 and 1.0.
        """
        file_mention_score = self._score_file_mentions(response)
        content_score = self._score_content(response)
        correctness_score = self._score_correctness(response)

        composite = (
            file_mention_score * 0.4
            + content_score * 0.4
            + correctness_score * 0.2
        )
        return max(0.0, min(1.0, composite))

    def _score_file_mentions(self, response: str) -> float:
        """Score whether expected file paths appear in the response text.

        Args:
            response: The raw text response from the LLM.

        Returns:
            Fraction of expected file paths mentioned in the response.
        """
        if not self.files:
            return 0.0

        response_lower = response.lower()
        expected_paths = list(self.files.keys())
        matched = sum(
            1 for path in expected_paths
            if path.lower() in response_lower
        )
        return matched / len(expected_paths)

    def _score_content(self, response: str) -> float:
        """Score keyword overlap between file content summaries and response.

        Extracts keywords from the value strings in ``self.files`` and
        checks how many appear in the response text.

        Args:
            response: The raw text response from the LLM.

        Returns:
            Fraction of content keywords found in the response.
        """
        if not self.files:
            return 0.0

        all_keywords: list[str] = []
        for summary in self.files.values():
            all_keywords.extend(extract_keywords(summary))

        if not all_keywords:
            return 0.0

        response_lower = response.lower()
        matched = sum(
            1 for kw in all_keywords
            if kw.lower() in response_lower
        )
        return matched / len(all_keywords)

    def _score_correctness(self, response: str) -> float:
        """Bonus score if FAIL_TO_PASS test names appear in the response.

        This is treated as a bonus signal rather than a hard requirement
        because LLM responses rarely contain literal pytest test names.

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
