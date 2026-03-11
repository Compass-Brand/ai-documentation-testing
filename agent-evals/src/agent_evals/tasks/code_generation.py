"""Code generation task type for evaluating generated code quality.

Scores responses by checking literal substring patterns and forbidden pattern
violations, with syntax validation via ast.parse.  Case-insensitive
matching is used for all pattern comparisons.

Test patterns (from the ``test`` field) are matched as literal substrings,
not regex, because they typically contain code snippets with characters
like ``[]``, ``()``, and ``.`` that would be misinterpreted as regex
metacharacters (see bug #169).

When the response contains fenced code blocks, patterns are matched against
extracted code only (not LLM prose) to prevent generic keywords from
inflating scores (bug #247).  When no code blocks are present the full
response is used as a fallback.

Score formula: match_rate * 0.7 + (1 - violation_rate) * 0.2 + syntax_bonus * 0.1
"""

from __future__ import annotations

import ast
import re

from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type


def _match_pattern(pattern: str, text: str) -> bool:
    """Match a pattern against text using case-insensitive literal substring matching.

    Uses literal matching (``in`` operator) rather than regex because test
    patterns are typically code snippets containing regex metacharacters
    such as ``[]``, ``()``, and ``.`` that would silently match the wrong
    things instead of raising ``re.error`` (bug #169).
    """
    return pattern.lower() in text.lower()


def _match_regex(pattern: str, text: str) -> bool:
    """Match a pattern as regex, falling back to literal if invalid.

    Used for forbidden_patterns where regex semantics (e.g. ``eval\\s*\\(``)
    are intentional.
    """
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


_PYTHON_INDICATORS: frozenset[str] = frozenset({
    "python", "python3", "py", "py3",
})


def _detect_language(response: str) -> str | None:
    """Detect the language from fenced code blocks in the response.

    Returns the lowercased language tag from the first fenced code block,
    or None if no language tag is found.
    """
    match = re.search(r"```(\w+)\n", response)
    if match:
        return match.group(1).lower()
    return None


def _check_syntax_all_blocks(response: str) -> bool:
    """Check syntax of each code block independently with its own language.

    When multiple fenced code blocks are present, each block is validated
    using its own language tag instead of concatenating all blocks and
    detecting the language from only the first block (bug #211).
    """
    matches = re.findall(r"```(\w*)\n(.*?)```", response, re.DOTALL)
    if not matches:
        return _check_syntax(response)
    return all(
        _check_syntax(code, lang.lower() if lang else None)
        for lang, code in matches
    )


def _check_syntax(code: str, language: str | None = None) -> bool:
    """Check whether the code is syntactically valid.

    Only validates Python code via ``ast.parse``. When a non-Python
    language tag is detected (e.g. ``javascript``, ``go``), returns
    True (no penalty) since we cannot validate those languages.

    When no language tag is present, falls back to Python validation
    as before -- this preserves the penalty for clearly broken Python.

    Args:
        code: The code string to check.
        language: Optional detected language tag (e.g. "python", "js").

    Returns:
        True if valid or non-Python; False only for invalid Python.
    """
    if not code.strip():
        return True
    # If language is detected and it's not Python, skip validation
    if language is not None and language not in _PYTHON_INDICATORS:
        return True
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


class CodeGenerationTask(EvalTask):
    """Task type for evaluating code generation quality.

    Parses the ``test`` field into literal substring patterns (one per line)
    and checks each against the response.  Also checks ``forbidden_patterns``
    (which support regex) for violations.  Score formula:
        match_rate * 0.7 + (1 - violation_rate) * 0.2 + syntax_bonus * 0.1
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
        """Score response using literal pattern matching, violation checks, and syntax validation.

        Scoring formula:
            base = match_rate * 0.7 + (1 - violation_rate) * 0.2 + syntax_bonus * 0.1
        where syntax_bonus is 1.0 if the code parses as valid Python, 0.0 otherwise.
        Test patterns are matched against extracted code blocks only (not LLM
        prose) to prevent generic keywords from inflating scores (bug #247).
        When no fenced code blocks are present, the full response is used as
        a fallback (the response is assumed to be pure code).
        Forbidden patterns use regex (with literal fallback) against the full
        response.
        Clamped to [0, 1].

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (unused).

        Returns:
            Score between 0.0 and 1.0.
        """
        # Extract code blocks for pattern matching (bug #247).
        # Patterns are matched against code only, not LLM prose, to avoid
        # generic keywords like "service", "id", "db" matching explanatory
        # text and inflating scores to 1.0 across all trials.
        # When no code blocks are present, _extract_code_blocks returns
        # the full response (assumed to be pure code).
        code_text = _extract_code_blocks(response)

        # Parse test patterns (one per line, skip empty)
        test_str = self.test if isinstance(self.test, str) else ""
        patterns = [
            line for line in test_str.split("\n") if line.strip()
        ]

        # Compute required match rate (case-insensitive via _match_pattern)
        if patterns:
            matched = sum(
                1 for pat in patterns if _match_pattern(pat, code_text)
            )
            match_rate = matched / len(patterns)
        else:
            # No patterns -> can't verify correctness; cap at 0.5 so empty
            # test fields don't vacuously produce near-perfect scores (bug #204).
            match_rate = 0.5

        # Compute violation rate (patterns may be literal strings or regex)
        if self.forbidden_patterns:
            violations = sum(
                1 for pat in self.forbidden_patterns
                if _match_regex(pat, response)
            )
            violation_rate = violations / len(self.forbidden_patterns)
        else:
            violation_rate = 0.0

        # Syntax validation bonus (each code block checked independently)
        syntax_bonus = 1.0 if _check_syntax_all_blocks(response) else 0.0

        score = match_rate * 0.7 + (1.0 - violation_rate) * 0.2 + syntax_bonus * 0.1
        return max(0.0, min(1.0, score))


register_task_type("code_generation", CodeGenerationTask)
