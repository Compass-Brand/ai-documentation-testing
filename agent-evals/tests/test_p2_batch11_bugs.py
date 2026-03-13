"""Tests for P2 batch 11 bugs: #206, #207, #208, #209, #210, #211, #212, #213."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from agent_evals.judge.hallucination import parse_hallucination_result
from agent_evals.metrics.navigation import _extract_file_reads
from agent_evals.metrics.operational import TurnMetrics, aggregate_turn_metrics
from agent_evals.tasks.base import TaskDefinition
from agent_evals.tasks.code_generation import CodeGenerationTask
from agent_evals.tasks.compositional import CompositionalTask
from agent_evals.tasks.disambiguation import _AMBIGUITY_PHRASES, DisambiguationTask
from agent_evals.tasks.loader import load_tasks
from agent_evals.tasks.retrieval import _FILE_PATH_PATTERN

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_disambig_task() -> DisambiguationTask:
    return DisambiguationTask(TaskDefinition(
        task_id="disambiguation_001", type="disambiguation",
        question="What does pool mean?", domain="framework_api", difficulty="medium",
        metadata={
            "interpretations": [
                {"label": "db_pool", "answer": "Connection pooling for databases"},
                {"label": "thread_pool", "answer": "Thread pool for parallel execution"},
            ],
            "expected_interpretation": "db_pool",
        },
    ))


def _task_data(task_id: str) -> dict[str, Any]:
    return {
        "task_id": task_id, "type": "retrieval",
        "question": "Q", "domain": "framework_api", "difficulty": "easy",
    }


def _yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.dump(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# Bug #206: "interpret" in _AMBIGUITY_PHRASES is overly broad
# ---------------------------------------------------------------------------


class TestBug206InterpretFalsePositive:
    """Bug #206: bare 'interpret' matches normal usage, inflating awareness."""

    def test_should_not_contain_bare_interpret(self) -> None:
        """The bare word 'interpret' should not be in _AMBIGUITY_PHRASES."""
        assert "interpret" not in _AMBIGUITY_PHRASES

    def test_normal_interpret_no_awareness_bonus(self) -> None:
        """Normal usage of 'interpret' should not trigger awareness bonus."""
        task = _make_disambig_task()
        without = task.score_response(
            "Let me interpret the connection pooling for databases concept."
        )
        with_amb = task.score_response(
            "This is ambiguous. Let me interpret the connection pooling "
            "for databases concept."
        )
        assert with_amb > without

    def test_interpreted_as_phrase_still_triggers(self) -> None:
        """Specific phrases like 'can be interpreted as' should still work."""
        task = _make_disambig_task()
        score = task.score_response(
            "This can be interpreted as connection pooling for databases "
            "or thread pool for parallel execution."
        )
        assert score >= 0.80


# ---------------------------------------------------------------------------
# Bug #207: aggregate_turn_metrics converts unknown cost to 0
# ---------------------------------------------------------------------------


class TestBug207AllNoneCostReturnsNone:
    """Bug #207: all-None costs should aggregate to None, not 0."""

    def test_all_none_costs_returns_none(self) -> None:
        """When all turn costs are None, total_cost_usd should be None."""
        turns = [
            TurnMetrics(1, 50, 25, None, 200.0),
            TurnMetrics(2, 80, 30, None, 300.0),
        ]
        assert aggregate_turn_metrics(turns).total_cost_usd is None

    def test_some_known_costs_returns_sum(self) -> None:
        """When some costs are known, total_cost_usd sums the known ones."""
        turns = [
            TurnMetrics(1, 50, 25, 0.001, 200.0),
            TurnMetrics(2, 80, 30, None, 300.0),
            TurnMetrics(3, 100, 40, 0.002, 250.0),
        ]
        assert aggregate_turn_metrics(turns).total_cost_usd == pytest.approx(0.003)


# ---------------------------------------------------------------------------
# Bug #208: loader duplicate ID check misaligns with schema.yaml skip
# ---------------------------------------------------------------------------


class TestBug208LoaderSchemaMisalignment:
    """Bug #208: schema.yaml skip causes task-to-path misalignment."""

    def test_duplicate_id_reports_correct_path_not_schema(
        self, tmp_path: Path,
    ) -> None:
        """Duplicate error should cite the actual file, not schema.yaml."""
        _yaml(tmp_path / "first.yaml", _task_data("retrieval_001"))
        _yaml(tmp_path / "schema.yaml", {"schema": {"version": "1.0"}})
        _yaml(tmp_path / "second.yaml", _task_data("retrieval_001"))

        with pytest.raises(ValueError, match="second\\.yaml"):
            load_tasks(tmp_path)

    def test_schema_between_tasks_no_misalignment(self, tmp_path: Path) -> None:
        """Tasks load correctly even with schema.yaml sorted between them."""
        _yaml(tmp_path / "first.yaml", _task_data("retrieval_001"))
        _yaml(tmp_path / "schema.yaml", {"schema": {"version": "1.0"}})
        _yaml(tmp_path / "second.yaml", _task_data("retrieval_002"))

        tasks = load_tasks(tmp_path)
        assert len(tasks) == 2
        ids = {t.definition.task_id for t in tasks}
        assert ids == {"retrieval_001", "retrieval_002"}


# ---------------------------------------------------------------------------
# Bug #209: CompositionalTask zip silently truncates mismatched lists
# ---------------------------------------------------------------------------


class TestBug209CompositionalZipTruncation:
    """Bug #209: mismatched sub_questions/expected_answers should raise."""

    def test_mismatched_lengths_raises(self) -> None:
        """zip(questions, answers) should error on length mismatch."""
        with pytest.raises(ValueError):
            CompositionalTask(TaskDefinition(
                task_id="compositional_001", type="compositional",
                question="Q", domain="framework_api", difficulty="medium",
                metadata={
                    "sub_questions": ["Q1", "Q2", "Q3"],
                    "expected_answers": ["A1", "A2"],
                },
            ))

    def test_matched_lengths_still_work(self) -> None:
        """Equal-length parallel lists should still construct fine."""
        task = CompositionalTask(TaskDefinition(
            task_id="compositional_001", type="compositional",
            question="Q", domain="framework_api", difficulty="medium",
            metadata={
                "sub_questions": ["Q1", "Q2"],
                "expected_answers": ["A1", "A2"],
            },
        ))
        assert len(task.sub_tasks) == 2


# ---------------------------------------------------------------------------
# Bug #210: parse_hallucination_result doesn't clamp score
# ---------------------------------------------------------------------------


class TestBug210HallucinationScoreClamping:
    """Bug #210: LLM-generated score should be clamped to [0.0, 1.0]."""

    def test_clamps_above_one(self) -> None:
        raw = json.dumps({"hallucination_score": 1.5, "type": "fabrication"})
        assert parse_hallucination_result(raw).score == 1.0

    def test_clamps_below_zero(self) -> None:
        raw = json.dumps({"hallucination_score": -0.3, "type": "grounded"})
        assert parse_hallucination_result(raw).score == 0.0

    def test_valid_score_unchanged(self) -> None:
        raw = json.dumps({"hallucination_score": 0.7, "type": "extrapolation"})
        assert parse_hallucination_result(raw).score == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# Bug #211: CodeGenerationTask concatenates ALL code blocks before check
# ---------------------------------------------------------------------------


class TestBug211MultiLanguageCodeBlocks:
    """Bug #211: multi-language blocks should be syntax-checked independently."""

    def test_multi_language_checked_independently(self) -> None:
        """Python + JS blocks should not fail by concatenation."""
        task = CodeGenerationTask(TaskDefinition(
            task_id="code_generation_001", type="code_generation",
            question="Write code", domain="framework_api", difficulty="easy",
            metadata={"test": "def add\nfunction", "forbidden_patterns": []},
        ))
        response = (
            "Python:\n```python\ndef add(a, b):\n    return a + b\n```\n"
            "JavaScript:\n```javascript\n"
            "function add(a, b) { return a + b; }\n```"
        )
        score = task.score_response(response)
        # match=1.0*0.7 + no_violations=0.2 + syntax=0.1 = 1.0
        assert score >= 0.95, (
            f"Multi-language blocks concatenated and failed syntax: {score}"
        )

    def test_single_language_still_works(self) -> None:
        """Single Python block still gets syntax checked correctly."""
        task = CodeGenerationTask(TaskDefinition(
            task_id="code_generation_001", type="code_generation",
            question="Write code", domain="framework_api", difficulty="easy",
            metadata={"test": "def add", "forbidden_patterns": []},
        ))
        valid = task.score_response("```python\ndef add(a, b):\n    return a + b\n```")
        invalid = task.score_response("```python\ndef add(a, b)\n    return a + b\n```")
        assert valid > invalid


# ---------------------------------------------------------------------------
# Bug #212: NavigationPathMetric matches write/delete/create as reads
# ---------------------------------------------------------------------------


class TestBug212ReadToolPatternFalsePositives:
    """Bug #212: write_file, delete_file, create_file should NOT match."""

    def test_write_file_not_read(self) -> None:
        assert _extract_file_reads(
            [{"tool": "write_file", "arguments": {"path": "a.py"}}],
        ) == []

    def test_delete_file_not_read(self) -> None:
        assert _extract_file_reads(
            [{"tool": "delete_file", "arguments": {"path": "a.py"}}],
        ) == []

    def test_create_file_not_read(self) -> None:
        assert _extract_file_reads(
            [{"tool": "create_file", "arguments": {"path": "a.py"}}],
        ) == []

    def test_read_file_still_works(self) -> None:
        assert _extract_file_reads(
            [{"tool": "read_file", "arguments": {"path": "a.py"}}],
        ) == ["a.py"]

    def test_file_reader_still_works(self) -> None:
        assert _extract_file_reads(
            [{"tool": "file_reader", "arguments": {"path": "a.py"}}],
        ) == ["a.py"]

    def test_open_document_still_works(self) -> None:
        assert _extract_file_reads(
            [{"tool": "open_document", "arguments": {"path": "a.py"}}],
        ) == ["a.py"]

    def test_get_content_still_works(self) -> None:
        assert _extract_file_reads(
            [{"tool": "get_content", "arguments": {"file_path": "a.py"}}],
        ) == ["a.py"]


# ---------------------------------------------------------------------------
# Bug #213: Retrieval regex matches version numbers and decimals
# ---------------------------------------------------------------------------


class TestBug213VersionDecimalFalsePositives:
    """Bug #213: 'e.g', 'i.e', 'releases/v2.2.0' should not match as paths."""

    def test_eg_not_matched(self) -> None:
        matches = _FILE_PATH_PATTERN.findall("e.g. this is an example")
        assert not any("e.g" in m for m in matches)

    def test_ie_not_matched(self) -> None:
        matches = _FILE_PATH_PATTERN.findall("i.e. the first option")
        assert not any("i.e" in m for m in matches)

    def test_version_in_path_not_matched(self) -> None:
        """'releases/v2.2.0' should not match (numeric extension)."""
        matches = _FILE_PATH_PATTERN.findall("See releases/v2.2.0 for details")
        assert not any("v2.2.0" in m for m in matches)

    def test_real_paths_still_work(self) -> None:
        matches = set(_FILE_PATH_PATTERN.findall(
            "Check src/auth.py and docs/readme.md"
        ))
        assert "src/auth.py" in matches
        assert "docs/readme.md" in matches
