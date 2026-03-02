"""Tests for the CodeGenerationTask type.

Tests cover:
- Valid construction from TaskDefinition with metadata
- build_prompt includes question and index content
- score_response: all patterns match, no violations (1.0)
- score_response: no patterns match (0.0)
- score_response: partial pattern match (between 0 and 1)
- Forbidden pattern penalty
- Edge cases: empty patterns, empty forbidden, multiline test field
"""

from __future__ import annotations

from typing import Any

from agent_evals.tasks.base import TASK_TYPES, TaskDefinition
from agent_evals.tasks.code_generation import CodeGenerationTask

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _codegen_task(**meta_overrides: Any) -> CodeGenerationTask:
    """Create a CodeGenerationTask with default metadata, with optional overrides."""
    meta: dict[str, Any] = {
        "expected_answer": "def add(a, b): return a + b",
        "test": r"def\s+add\s*\(.*\)\s*:" + "\n" + r"return\s+.*\+",
        "entry_point": "add",
        "canonical_solution": "def add(a, b):\n    return a + b",
        "libs": [],
        "doc_struct": {},
        "forbidden_patterns": [r"eval\s*\(", r"exec\s*\("],
    }
    meta.update(meta_overrides)
    defn = TaskDefinition(
        task_id="code_generation_001",
        type="code_generation",
        question="Write a function that adds two numbers.",
        domain="framework_api",
        difficulty="easy",
        metadata=meta,
    )
    return CodeGenerationTask(defn)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestCodeGenerationTaskConstruction:
    """Tests for CodeGenerationTask construction from TaskDefinition."""

    def test_constructs_from_valid_definition(self) -> None:
        """CodeGenerationTask accepts a TaskDefinition with valid metadata."""
        task = _codegen_task()
        assert task.expected_answer == "def add(a, b): return a + b"
        assert task.entry_point == "add"
        assert task.forbidden_patterns == [r"eval\s*\(", r"exec\s*\("]

    def test_defaults_for_missing_metadata(self) -> None:
        """CodeGenerationTask uses defaults when metadata keys are absent."""
        defn = TaskDefinition(
            task_id="code_generation_002",
            type="code_generation",
            question="Write code",
            domain="framework_api",
            difficulty="easy",
            metadata={},
        )
        task = CodeGenerationTask(defn)
        assert task.expected_answer == ""
        assert task.test == ""
        assert task.entry_point == ""
        assert task.canonical_solution == ""
        assert task.libs == []
        assert task.doc_struct == {}
        assert task.forbidden_patterns == []

    def test_registered_in_task_types(self) -> None:
        """CodeGenerationTask is registered in TASK_TYPES for 'code_generation'."""
        assert TASK_TYPES["code_generation"] is CodeGenerationTask


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------


class TestCodeGenerationTaskBuildPrompt:
    """Tests for CodeGenerationTask.build_prompt."""

    def test_returns_message_list(self) -> None:
        """build_prompt returns a list of message dicts."""
        task = _codegen_task()
        messages = task.build_prompt("# API Reference")
        assert isinstance(messages, list)
        assert len(messages) >= 2

    def test_includes_index_content(self) -> None:
        """build_prompt includes the index content in messages."""
        task = _codegen_task()
        messages = task.build_prompt("UNIQUE_CODE_INDEX")
        all_content = " ".join(m["content"] for m in messages)
        assert "UNIQUE_CODE_INDEX" in all_content

    def test_includes_question(self) -> None:
        """build_prompt includes the task question in messages."""
        task = _codegen_task()
        messages = task.build_prompt("index")
        all_content = " ".join(m["content"] for m in messages)
        assert "Write a function that adds two numbers." in all_content


# ---------------------------------------------------------------------------
# score_response
# ---------------------------------------------------------------------------


class TestCodeGenerationTaskScoring:
    """Tests for CodeGenerationTask.score_response."""

    def test_all_patterns_match_no_violations_near_1(self) -> None:
        """Response matching all required patterns with no violations scores ~1.0."""
        task = _codegen_task(
            test="def\\s+add\nreturn",
            forbidden_patterns=[],
        )
        response = "def add(a, b):\n    return a + b"
        score = task.score_response(response)
        assert score >= 0.99

    def test_no_patterns_match_scores_low(self) -> None:
        """Response matching no required patterns scores 0.2 (no violations, no syntax bonus).

        Formula: 0.0 * 0.7 + (1.0 - 0.0) * 0.2 + 0.0 * 0.1 = 0.2
        No patterns matched, no forbidden violations, invalid syntax (plain text).
        """
        task = _codegen_task(
            test="def\\s+add\nreturn\\s+.*\\+",
            forbidden_patterns=[],
        )
        response = "I don't know how to write this function."
        score = task.score_response(response)
        assert abs(score - 0.2) < 0.01

    def test_partial_pattern_match(self) -> None:
        """Response matching some but not all patterns scores partially."""
        task = _codegen_task(
            test="def\\s+add\nreturn\\s+.*\\+\ntype\\s+hints",
            forbidden_patterns=[],
        )
        # Matches first two patterns but not the third
        response = "def add(a, b):\n    return a + b"
        score = task.score_response(response)
        assert 0.0 < score < 1.0

    def test_forbidden_pattern_penalizes_score(self) -> None:
        """Forbidden patterns reduce the score."""
        task = _codegen_task(
            test="def\\s+add",
            forbidden_patterns=[r"eval\s*\("],
        )
        clean_response = "def add(a, b):\n    return a + b"
        dirty_response = "def add(a, b):\n    return eval('a + b')"

        clean_score = task.score_response(clean_response)
        dirty_score = task.score_response(dirty_response)

        assert clean_score > dirty_score

    def test_empty_test_patterns_scores_based_on_violations_only(self) -> None:
        """When no test patterns, score depends on violation rate."""
        task = _codegen_task(test="", forbidden_patterns=[r"eval\s*\("])
        # match_rate=1.0 (vacuously satisfied), but violation penalty applies
        clean = task.score_response("def add(a, b): return a + b")
        dirty = task.score_response("result = eval('1+2')")
        # Both have match_rate=1.0, but dirty has violation
        assert clean >= dirty

    def test_empty_test_and_forbidden_returns_high(self) -> None:
        """When no test patterns and no forbidden, match rate defaults to 1.0."""
        task = _codegen_task(test="", forbidden_patterns=[])
        score = task.score_response("def add(a, b): return a + b")
        # 1.0 * 0.7 + 1.0 * 0.2 + 1.0 * 0.1 = 1.0 (vacuously satisfied, no violations, valid syntax)
        assert abs(score - 1.0) < 0.01

    def test_all_forbidden_violated(self) -> None:
        """Violating all forbidden patterns maximizes penalty."""
        task = _codegen_task(
            test=".",  # single pattern that matches anything
            forbidden_patterns=[r"eval", r"exec"],
        )
        response = "eval(exec('code'))"
        score = task.score_response(response)
        # match_rate=1.0, violation_rate=1.0, syntax_bonus=1.0 (valid Python expression)
        # 1.0*0.7 + (1-1.0)*0.2 + 1.0*0.1 = 0.8
        assert abs(score - 0.8) < 0.01

    def test_score_clamped_between_0_and_1(self) -> None:
        """Score is always between 0.0 and 1.0."""
        task = _codegen_task()
        for resp in [
            "def add(a, b):\n    return a + b",
            "nothing",
            "eval(exec('bad'))",
        ]:
            score = task.score_response(resp)
            assert 0.0 <= score <= 1.0

    def test_multiline_test_field_splits_into_patterns(self) -> None:
        """The test field with multiple lines produces multiple regex patterns."""
        task = _codegen_task(
            test="pattern_one\npattern_two\npattern_three",
            forbidden_patterns=[],
        )
        response = "pattern_one and pattern_two and pattern_three"
        score = task.score_response(response)
        assert score >= 0.99


# ---------------------------------------------------------------------------
# Step 3.2: Syntax validation, case normalization, partial credit
# ---------------------------------------------------------------------------


class TestCodeGenerationSyntaxValidation:
    """Tests for syntax validation via ast.parse."""

    def test_valid_python_syntax_not_penalized(self) -> None:
        """Response with valid Python syntax is not penalized."""
        task = _codegen_task(
            test="def\\s+add",
            forbidden_patterns=[],
        )
        response = "```python\ndef add(a, b):\n    return a + b\n```"
        score = task.score_response(response)
        assert score >= 0.8

    def test_invalid_python_syntax_penalized(self) -> None:
        """Response with invalid Python syntax receives a penalty."""
        task = _codegen_task(
            test="def\\s+add",
            forbidden_patterns=[],
        )
        valid_response = "def add(a, b):\n    return a + b"
        invalid_response = "def add(a, b)\n    return a + b"  # missing colon
        valid_score = task.score_response(valid_response)
        invalid_score = task.score_response(invalid_response)
        assert valid_score > invalid_score

    def test_non_python_code_not_crashed(self) -> None:
        """Non-Python code responses don't crash the scorer."""
        task = _codegen_task(
            test="function",
            forbidden_patterns=[],
        )
        response = "function add(a, b) { return a + b; }"
        score = task.score_response(response)
        assert 0.0 <= score <= 1.0


class TestCodeGenerationCaseNormalization:
    """Tests for case-insensitive keyword matching."""

    def test_case_insensitive_pattern_matching(self) -> None:
        """Pattern matching is case-insensitive for literal patterns."""
        task = _codegen_task(
            test="JWTConfig\nHS256",
            forbidden_patterns=[],
        )
        response = "jwtconfig with hs256 algorithm"
        score = task.score_response(response)
        # Both patterns should match case-insensitively
        assert score >= 0.8


class TestCodeGenerationPartialCredit:
    """Tests for partial credit scaling."""

    def test_partial_credit_proportional(self) -> None:
        """Score scales proportionally with matched patterns."""
        task = _codegen_task(
            test="pattern_a\npattern_b\npattern_c\npattern_d",
            forbidden_patterns=[],
        )
        # Match 1 of 4 patterns
        response_1 = "pattern_a only"
        # Match 2 of 4 patterns
        response_2 = "pattern_a and pattern_b"
        # Match 3 of 4 patterns
        response_3 = "pattern_a and pattern_b and pattern_c"

        score_1 = task.score_response(response_1)
        score_2 = task.score_response(response_2)
        score_3 = task.score_response(response_3)

        assert score_1 < score_2 < score_3



def test_no_test_patterns_does_not_cap_score_at_0_3():
    """With no test patterns, score should exceed 0.3."""
    defn = TaskDefinition(
        task_id="code_generation_001", type="code_generation", question="Write a function",
        domain="framework_api", difficulty="easy",
        metadata={"test": "", "forbidden_patterns": []},
    )
    task = CodeGenerationTask(defn)
    score = task.score_response("def add(a, b):\n    return a + b")
    assert score > 0.3, f"Expected > 0.3, got {score}"
