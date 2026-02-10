"""Code generation task type for evaluating generated code quality.

Scores responses by checking regex test patterns and forbidden pattern
violations, with syntax validation via ast.parse.  Case-insensitive
matching is used for literal fallback patterns.
"""

from __future__ import annotations

import ast
import re

from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type


def _match_pattern(pattern: str, text: str) -> bool:
    """Match a pattern against text, trying regex first, falling back to case-insensitive literal."""
    try:
        return bool(re.search(pattern, text, re.IGNORECASE))
    except re.error:
        return pattern.lower() in text.lower()


def _extract_code_blocks(response: str) -> str:
    """Extract code from fenced code blocks, or return the full response."""
    blocks = re.findall(r"```(?:\w*)\n(.*?)```", response, re.DOTALL)
    if blocks:
        return "\n".join(blocks)
    return response


def _check_syntax(code: str) -> bool:
    """Check whether the code is valid Python syntax via ast.parse.

    Returns True if the code parses successfully, False otherwise.
    Silently returns True for empty strings (no code to validate).
    """
    if not code.strip():
        return True
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


class CodeGenerationTask(EvalTask):
    """Task type for evaluating code generation quality.

    Parses the ``test`` field into regex patterns (one per line) and
    checks each against the response. Also checks ``forbidden_patterns``
    for violations. Score formula:
        required_match_rate * 0.8 + (1 - violation_rate) * 0.2
    Clamped to [0, 1].
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta = definition.metadata
        self.expected_answer: str = meta.get("expected_answer", "")
        self.test: str = meta.get("test", "")
        self.entry_point: str = meta.get("entry_point", "")
        self.canonical_solution: str = meta.get("canonical_solution", "")
        self.libs: list[str] = meta.get("libs", [])
        self.doc_struct: dict[str, object] = meta.get("doc_struct", {})
        self.forbidden_patterns: list[str] = meta.get("forbidden_patterns", [])

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build messages for code generation evaluation.

        Args:
            index_content: The documentation index content.

        Returns:
            List of message dicts with system and user messages.
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that writes code based on "
                    "documentation. Use the following documentation index "
                    "to write correct, well-structured code.\n\n"
                    f"{index_content}"
                ),
            },
            {
                "role": "user",
                "content": self.definition.question,
            },
        ]

    def score_response(self, response: str, **kwargs: object) -> float:
        """Score response using regex pattern matching, violation checks, and syntax validation.

        Scoring formula:
            base = match_rate * 0.7 + (1 - violation_rate) * 0.2 + syntax_bonus * 0.1
        where syntax_bonus is 1.0 if the code parses as valid Python, 0.0 otherwise.
        Pattern matching uses case-insensitive regex (or literal fallback).
        Clamped to [0, 1].

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (unused).

        Returns:
            Score between 0.0 and 1.0.
        """
        # Parse test patterns (one per line, skip empty)
        patterns = [
            line for line in self.test.split("\n") if line.strip()
        ]

        # Compute required match rate (case-insensitive via _match_pattern)
        if patterns:
            matched = sum(
                1 for pat in patterns if _match_pattern(pat, response)
            )
            match_rate = matched / len(patterns)
        else:
            match_rate = 0.0

        # Compute violation rate (patterns may be literal strings or regex)
        if self.forbidden_patterns:
            violations = sum(
                1 for pat in self.forbidden_patterns
                if _match_pattern(pat, response)
            )
            violation_rate = violations / len(self.forbidden_patterns)
        else:
            violation_rate = 0.0

        # Syntax validation bonus
        code = _extract_code_blocks(response)
        syntax_bonus = 1.0 if _check_syntax(code) else 0.0

        score = match_rate * 0.7 + (1.0 - violation_rate) * 0.2 + syntax_bonus * 0.1
        return max(0.0, min(1.0, score))


register_task_type("code_generation", CodeGenerationTask)
