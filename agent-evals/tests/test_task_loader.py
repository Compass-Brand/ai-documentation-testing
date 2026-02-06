"""Tests for task base classes and YAML loader.

Tests cover:
- TaskDefinition Pydantic model validation
- task_id pattern validation
- EvalTask ABC and GenericTask concrete implementation
- Task type registry (register + lookup)
- YAML loading (single file and directory)
- Error cases: invalid task_id, unknown type, missing fields
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from agent_evals.tasks.base import (
    TASK_TYPES,
    EvalTask,
    GenericTask,
    TaskDefinition,
    register_task_type,
)
from agent_evals.tasks.loader import load_task, load_tasks

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(path: Path, data: dict[str, Any]) -> Path:
    """Write a dict as YAML to the given path."""
    path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    return path


def _valid_task_data(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid task definition dict, with optional overrides."""
    base: dict[str, Any] = {
        "task_id": "retrieval_001",
        "type": "retrieval",
        "question": "What does the auth middleware do?",
        "domain": "framework_api",
        "difficulty": "easy",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# TaskDefinition model validation
# ---------------------------------------------------------------------------


class TestTaskDefinition:
    """Tests for the TaskDefinition Pydantic model."""

    def test_valid_minimal_definition(self) -> None:
        """TaskDefinition accepts all required fields with valid values."""
        td = TaskDefinition(**_valid_task_data())

        assert td.task_id == "retrieval_001"
        assert td.type == "retrieval"
        assert td.question == "What does the auth middleware do?"
        assert td.domain == "framework_api"
        assert td.difficulty == "easy"
        assert td.tags == []
        assert td.metadata == {}

    def test_valid_definition_with_optional_fields(self) -> None:
        """TaskDefinition accepts optional tags and metadata."""
        td = TaskDefinition(
            **_valid_task_data(
                tags=["auth", "middleware"],
                metadata={"source": "manual", "version": 2},
            )
        )

        assert td.tags == ["auth", "middleware"]
        assert td.metadata == {"source": "manual", "version": 2}

    def test_all_valid_types_accepted(self) -> None:
        """TaskDefinition accepts all 11 defined task types."""
        valid_types = [
            "retrieval",
            "fact_extraction",
            "code_generation",
            "agentic",
            "multi_hop",
            "negative",
            "compositional",
            "robustness",
            "disambiguation",
            "conflicting",
            "efficiency",
        ]
        for task_type in valid_types:
            td = TaskDefinition(
                **_valid_task_data(
                    type=task_type,
                    task_id=f"{task_type}_001",
                )
            )
            assert td.type == task_type

    def test_all_valid_domains_accepted(self) -> None:
        """TaskDefinition accepts all 3 defined domains."""
        for domain in ["framework_api", "project_repo", "skills_workflows"]:
            td = TaskDefinition(**_valid_task_data(domain=domain))
            assert td.domain == domain

    def test_all_valid_difficulties_accepted(self) -> None:
        """TaskDefinition accepts all 3 difficulty levels."""
        for difficulty in ["easy", "medium", "hard"]:
            td = TaskDefinition(**_valid_task_data(difficulty=difficulty))
            assert td.difficulty == difficulty

    def test_invalid_type_rejected(self) -> None:
        """TaskDefinition rejects unknown task types."""
        with pytest.raises(ValueError, match="type"):
            TaskDefinition(**_valid_task_data(type="unknown_type"))

    def test_invalid_domain_rejected(self) -> None:
        """TaskDefinition rejects unknown domains."""
        with pytest.raises(ValueError, match="domain"):
            TaskDefinition(**_valid_task_data(domain="invalid_domain"))

    def test_invalid_difficulty_rejected(self) -> None:
        """TaskDefinition rejects unknown difficulty levels."""
        with pytest.raises(ValueError, match="difficulty"):
            TaskDefinition(**_valid_task_data(difficulty="extreme"))

    def test_missing_required_field_rejected(self) -> None:
        """TaskDefinition rejects when required fields are missing."""
        data = _valid_task_data()
        del data["question"]
        with pytest.raises(ValueError):
            TaskDefinition(**data)

    def test_missing_task_id_rejected(self) -> None:
        """TaskDefinition rejects when task_id is missing."""
        data = _valid_task_data()
        del data["task_id"]
        with pytest.raises(ValueError):
            TaskDefinition(**data)


# ---------------------------------------------------------------------------
# task_id pattern validation
# ---------------------------------------------------------------------------


class TestTaskIdValidation:
    """Tests for task_id pattern matching."""

    def test_valid_simple_task_id(self) -> None:
        """task_id like 'retrieval_001' is accepted."""
        td = TaskDefinition(**_valid_task_data(task_id="retrieval_001"))
        assert td.task_id == "retrieval_001"

    def test_valid_task_id_with_larger_number(self) -> None:
        """task_id with multi-digit number like 'retrieval_042' is accepted."""
        td = TaskDefinition(**_valid_task_data(task_id="retrieval_042"))
        assert td.task_id == "retrieval_042"

    def test_valid_subtype_task_id(self) -> None:
        """task_id with subtype like 'code_generation_python_001' is accepted."""
        td = TaskDefinition(
            **_valid_task_data(
                type="code_generation",
                task_id="code_generation_python_001",
            )
        )
        assert td.task_id == "code_generation_python_001"

    def test_valid_multi_hop_task_id(self) -> None:
        """task_id for multi_hop type like 'multi_hop_042' is accepted."""
        td = TaskDefinition(
            **_valid_task_data(type="multi_hop", task_id="multi_hop_042")
        )
        assert td.task_id == "multi_hop_042"

    def test_valid_fact_extraction_task_id(self) -> None:
        """task_id for fact_extraction like 'fact_extraction_003' is accepted."""
        td = TaskDefinition(
            **_valid_task_data(type="fact_extraction", task_id="fact_extraction_003")
        )
        assert td.task_id == "fact_extraction_003"

    def test_invalid_task_id_no_number(self) -> None:
        """task_id without trailing digits is rejected."""
        with pytest.raises(ValueError, match="task_id"):
            TaskDefinition(**_valid_task_data(task_id="retrieval"))

    def test_invalid_task_id_no_underscore(self) -> None:
        """task_id without underscore separator is rejected."""
        with pytest.raises(ValueError, match="task_id"):
            TaskDefinition(**_valid_task_data(task_id="retrieval001"))

    def test_invalid_task_id_empty(self) -> None:
        """Empty task_id is rejected."""
        with pytest.raises(ValueError, match="task_id"):
            TaskDefinition(**_valid_task_data(task_id=""))

    def test_invalid_task_id_only_digits(self) -> None:
        """task_id with only digits is rejected."""
        with pytest.raises(ValueError, match="task_id"):
            TaskDefinition(**_valid_task_data(task_id="001"))

    def test_invalid_task_id_trailing_underscore(self) -> None:
        """task_id with trailing underscore (no digits) is rejected."""
        with pytest.raises(ValueError, match="task_id"):
            TaskDefinition(**_valid_task_data(task_id="retrieval_"))

    def test_invalid_task_id_special_characters(self) -> None:
        """task_id with special characters is rejected."""
        with pytest.raises(ValueError, match="task_id"):
            TaskDefinition(**_valid_task_data(task_id="retrieval-001"))


# ---------------------------------------------------------------------------
# EvalTask ABC and GenericTask
# ---------------------------------------------------------------------------


class TestEvalTask:
    """Tests for EvalTask ABC and GenericTask concrete implementation."""

    def test_generic_task_holds_definition(self) -> None:
        """GenericTask stores the TaskDefinition."""
        defn = TaskDefinition(**_valid_task_data())
        task = GenericTask(defn)

        assert task.definition is defn
        assert task.definition.task_id == "retrieval_001"

    def test_generic_task_build_prompt(self) -> None:
        """GenericTask.build_prompt returns a list of message dicts."""
        defn = TaskDefinition(**_valid_task_data())
        task = GenericTask(defn)

        messages = task.build_prompt("Some index content here")

        assert isinstance(messages, list)
        assert len(messages) > 0
        # Each message should have 'role' and 'content' keys
        for msg in messages:
            assert "role" in msg
            assert "content" in msg

    def test_generic_task_build_prompt_includes_question(self) -> None:
        """GenericTask.build_prompt includes the question in messages."""
        defn = TaskDefinition(**_valid_task_data(question="What is auth?"))
        task = GenericTask(defn)

        messages = task.build_prompt("Index content")

        # The question should appear somewhere in the messages
        all_content = " ".join(m["content"] for m in messages)
        assert "What is auth?" in all_content

    def test_generic_task_build_prompt_includes_index_content(self) -> None:
        """GenericTask.build_prompt includes the index content in messages."""
        defn = TaskDefinition(**_valid_task_data())
        task = GenericTask(defn)

        messages = task.build_prompt("My documentation index")

        all_content = " ".join(m["content"] for m in messages)
        assert "My documentation index" in all_content

    def test_generic_task_score_response(self) -> None:
        """GenericTask.score_response returns a float between 0.0 and 1.0."""
        defn = TaskDefinition(**_valid_task_data())
        task = GenericTask(defn)

        score = task.score_response("Some LLM response text")

        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_eval_task_is_abstract(self) -> None:
        """EvalTask cannot be instantiated directly."""
        defn = TaskDefinition(**_valid_task_data())
        with pytest.raises(TypeError):
            EvalTask(defn)  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Task type registry
# ---------------------------------------------------------------------------


class TestTaskTypeRegistry:
    """Tests for task type registration."""

    def test_register_and_lookup_task_type(self) -> None:
        """register_task_type adds a type to TASK_TYPES dict."""
        # Create a custom task class
        class CustomTask(EvalTask):
            def build_prompt(self, index_content: str) -> list[dict[str, str]]:
                return [{"role": "user", "content": index_content}]

            def score_response(self, response: str, **kwargs: object) -> float:
                return 1.0

        register_task_type("custom_test_type", CustomTask)

        assert "custom_test_type" in TASK_TYPES
        assert TASK_TYPES["custom_test_type"] is CustomTask

        # Clean up so other tests aren't affected
        del TASK_TYPES["custom_test_type"]

    def test_generic_task_registered_for_all_types(self) -> None:
        """GenericTask is the default registered for all 11 standard types."""
        standard_types = [
            "retrieval",
            "fact_extraction",
            "code_generation",
            "agentic",
            "multi_hop",
            "negative",
            "compositional",
            "robustness",
            "disambiguation",
            "conflicting",
            "efficiency",
        ]
        for type_name in standard_types:
            assert type_name in TASK_TYPES, f"{type_name} not in TASK_TYPES"
            # Specialized task types override GenericTask for types 1-4
            assert issubclass(TASK_TYPES[type_name], EvalTask)


# ---------------------------------------------------------------------------
# YAML task loader - single file
# ---------------------------------------------------------------------------


class TestLoadTask:
    """Tests for load_task (single YAML file)."""

    def test_load_valid_task(self, tmp_path: Path) -> None:
        """load_task loads a valid YAML file and returns an EvalTask."""
        yaml_path = _write_yaml(tmp_path / "task.yaml", _valid_task_data())

        task = load_task(yaml_path)

        assert isinstance(task, EvalTask)
        assert task.definition.task_id == "retrieval_001"
        assert task.definition.type == "retrieval"
        assert task.definition.question == "What does the auth middleware do?"

    def test_load_task_with_all_fields(self, tmp_path: Path) -> None:
        """load_task loads a YAML file with all optional fields."""
        data = _valid_task_data(
            tags=["auth", "middleware"],
            metadata={"source": "manual"},
        )
        yaml_path = _write_yaml(tmp_path / "task.yaml", data)

        task = load_task(yaml_path)

        assert task.definition.tags == ["auth", "middleware"]
        assert task.definition.metadata == {"source": "manual"}

    def test_load_task_returns_correct_type_class(self, tmp_path: Path) -> None:
        """load_task returns an instance of the registered class for the type."""
        yaml_path = _write_yaml(tmp_path / "task.yaml", _valid_task_data())

        task = load_task(yaml_path)

        # Retrieval type maps to RetrievalTask (or any EvalTask subclass)
        assert isinstance(task, EvalTask)

    def test_load_task_invalid_task_id_raises(self, tmp_path: Path) -> None:
        """load_task raises ValueError for invalid task_id in YAML."""
        data = _valid_task_data(task_id="bad-id")
        yaml_path = _write_yaml(tmp_path / "task.yaml", data)

        with pytest.raises(ValueError, match="task_id"):
            load_task(yaml_path)

    def test_load_task_unknown_type_raises(self, tmp_path: Path) -> None:
        """load_task raises ValueError for unregistered task type."""
        data = _valid_task_data(type="totally_unknown")
        yaml_path = _write_yaml(tmp_path / "task.yaml", data)

        with pytest.raises(ValueError):
            load_task(yaml_path)

    def test_load_task_missing_required_field_raises(self, tmp_path: Path) -> None:
        """load_task raises ValueError when required fields are missing."""
        data = _valid_task_data()
        del data["question"]
        yaml_path = _write_yaml(tmp_path / "task.yaml", data)

        with pytest.raises(ValueError):
            load_task(yaml_path)

    def test_load_task_file_not_found_raises(self, tmp_path: Path) -> None:
        """load_task raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            load_task(tmp_path / "nonexistent.yaml")

    def test_load_task_invalid_yaml_raises(self, tmp_path: Path) -> None:
        """load_task raises ValueError for malformed YAML."""
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("{{{{invalid yaml: [", encoding="utf-8")

        with pytest.raises(ValueError, match="[Yy]AML"):
            load_task(bad_yaml)

    def test_load_task_yml_extension(self, tmp_path: Path) -> None:
        """load_task handles .yml extension."""
        yaml_path = _write_yaml(tmp_path / "task.yml", _valid_task_data())

        task = load_task(yaml_path)

        assert task.definition.task_id == "retrieval_001"


# ---------------------------------------------------------------------------
# YAML task loader - directory
# ---------------------------------------------------------------------------


class TestLoadTasks:
    """Tests for load_tasks (directory of YAML files)."""

    def test_load_tasks_from_directory(self, tmp_path: Path) -> None:
        """load_tasks loads all YAML files from a directory."""
        _write_yaml(
            tmp_path / "task1.yaml",
            _valid_task_data(task_id="retrieval_001"),
        )
        _write_yaml(
            tmp_path / "task2.yaml",
            _valid_task_data(task_id="retrieval_002"),
        )
        _write_yaml(
            tmp_path / "task3.yml",
            _valid_task_data(task_id="retrieval_003"),
        )

        tasks = load_tasks(tmp_path)

        assert len(tasks) == 3
        task_ids = {t.definition.task_id for t in tasks}
        assert task_ids == {"retrieval_001", "retrieval_002", "retrieval_003"}

    def test_load_tasks_ignores_non_yaml_files(self, tmp_path: Path) -> None:
        """load_tasks skips non-YAML files in the directory."""
        _write_yaml(tmp_path / "task.yaml", _valid_task_data())
        (tmp_path / "readme.md").write_text("# Readme", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("Notes", encoding="utf-8")

        tasks = load_tasks(tmp_path)

        assert len(tasks) == 1

    def test_load_tasks_empty_directory(self, tmp_path: Path) -> None:
        """load_tasks returns empty list for a directory with no YAML files."""
        tasks = load_tasks(tmp_path)

        assert tasks == []

    def test_load_tasks_directory_not_found_raises(self, tmp_path: Path) -> None:
        """load_tasks raises FileNotFoundError for missing directory."""
        with pytest.raises(FileNotFoundError):
            load_tasks(tmp_path / "nonexistent_dir")

    def test_load_tasks_from_subdirectories(self, tmp_path: Path) -> None:
        """load_tasks recursively loads YAML files from subdirectories."""
        subdir = tmp_path / "retrieval"
        subdir.mkdir()
        _write_yaml(
            subdir / "task1.yaml",
            _valid_task_data(task_id="retrieval_001"),
        )
        _write_yaml(
            tmp_path / "task2.yaml",
            _valid_task_data(task_id="retrieval_002"),
        )

        tasks = load_tasks(tmp_path)

        assert len(tasks) == 2
        task_ids = {t.definition.task_id for t in tasks}
        assert task_ids == {"retrieval_001", "retrieval_002"}

    def test_load_tasks_sorted_by_task_id(self, tmp_path: Path) -> None:
        """load_tasks returns tasks sorted by task_id."""
        _write_yaml(
            tmp_path / "c.yaml",
            _valid_task_data(task_id="retrieval_003"),
        )
        _write_yaml(
            tmp_path / "a.yaml",
            _valid_task_data(task_id="retrieval_001"),
        )
        _write_yaml(
            tmp_path / "b.yaml",
            _valid_task_data(task_id="retrieval_002"),
        )

        tasks = load_tasks(tmp_path)

        task_ids = [t.definition.task_id for t in tasks]
        assert task_ids == ["retrieval_001", "retrieval_002", "retrieval_003"]
