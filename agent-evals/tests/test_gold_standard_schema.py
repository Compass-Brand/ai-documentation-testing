"""Tests for gold standard schema and example validation.

Tests cover:
- schema.yaml loads correctly as valid YAML
- Schema structure contains required top-level keys
- Sample gold example files validate against the schema
- task_id patterns are valid
- domain, type, difficulty values are constrained to valid enums
- Annotation structure is correct (score range, required fields, timestamps)
- Difficulty distribution targets sum correctly
- Validation thresholds are within expected ranges
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

GOLD_STANDARD_DIR = Path(__file__).resolve().parent.parent / "gold_standard"
SCHEMA_PATH = GOLD_STANDARD_DIR / "schema.yaml"

# ---------------------------------------------------------------------------
# Constants (mirrored from agent_evals.tasks.base for test independence)
# ---------------------------------------------------------------------------

VALID_TASK_TYPES: set[str] = {
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
}

VALID_DOMAINS: set[str] = {
    "framework_api",
    "project_repo",
    "skills_workflows",
    # Public dataset domains
    "library_docs",
    "technical_qa",
    "code_repository",
    "news_articles",
    "synthetic_docs",
    "general_knowledge",
}

VALID_DIFFICULTIES: set[str] = {
    "easy",
    "medium",
    "hard",
    "edge",
}

TASK_ID_PATTERN: re.Pattern[str] = re.compile(
    r"^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*_\d+$"
)

ISO8601_PATTERN: re.Pattern[str] = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_schema() -> dict[str, Any]:
    """Load and return the schema.yaml as a dict."""
    text = SCHEMA_PATH.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    assert isinstance(data, dict), "schema.yaml must be a YAML mapping"
    return data


def _sample_gold_example(**overrides: Any) -> dict[str, Any]:
    """Return a minimal valid gold standard example dict."""
    example: dict[str, Any] = {
        "task": {
            "task_id": "retrieval_001",
            "type": "retrieval",
            "question": "What does the auth middleware do?",
            "domain": "framework_api",
            "difficulty": "easy",
            "tags": ["auth", "middleware"],
            "metadata": {"expected_files": ["src/auth.py"]},
        },
        "annotations": [
            {
                "annotator_id": "annotator_A",
                "timestamp": "2025-01-15T14:30:00Z",
                "response": (
                    "The auth middleware validates JWT tokens on each "
                    "request and attaches the user object to the context."
                ),
                "score": 0.85,
                "rationale": (
                    "Correctly identifies JWT validation and context "
                    "attachment. Misses rate-limiting detail."
                ),
                "criteria_scores": {
                    "correctness": 0.90,
                    "completeness": 0.75,
                    "conciseness": 0.90,
                },
            },
        ],
    }
    # Apply overrides using dot-path keys like "task.task_id"
    for key, value in overrides.items():
        parts = key.split(".")
        target = example
        for part in parts[:-1]:
            target = target[int(part)] if isinstance(target, list) else target[part]
        if isinstance(target, list):
            target[int(parts[-1])] = value
        else:
            target[parts[-1]] = value
    return example


def _validate_gold_example(example: dict[str, Any]) -> list[str]:
    """Validate a gold standard example dict against schema rules.

    Returns a list of error messages. An empty list means valid.
    """
    errors: list[str] = []

    # --- Task section ---
    task = example.get("task")
    if not isinstance(task, dict):
        errors.append("Missing or invalid 'task' section")
        return errors

    # Required task fields
    for field in ("task_id", "type", "question", "domain", "difficulty"):
        if field not in task:
            errors.append(f"Missing required task field: {field}")

    # task_id pattern
    task_id = task.get("task_id", "")
    if "task_id" in task and not TASK_ID_PATTERN.match(task_id):
        errors.append(
            f"task_id '{task_id}' does not match pattern "
            "{{type}}_{{digits}}"
        )

    # type enum
    task_type = task.get("type", "")
    if task_type and task_type not in VALID_TASK_TYPES:
        errors.append(f"type '{task_type}' not in valid task types")

    # domain enum
    domain = task.get("domain", "")
    if domain and domain not in VALID_DOMAINS:
        errors.append(f"domain '{domain}' not in valid domains")

    # difficulty enum
    difficulty = task.get("difficulty", "")
    if difficulty and difficulty not in VALID_DIFFICULTIES:
        errors.append(f"difficulty '{difficulty}' not in valid difficulties")

    # tags must be a list if present
    tags = task.get("tags")
    if tags is not None and not isinstance(tags, list):
        errors.append("tags must be a list")

    # metadata must be a dict if present
    metadata = task.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        errors.append("metadata must be a dict")

    # --- Annotations section ---
    annotations = example.get("annotations")
    if not isinstance(annotations, list) or len(annotations) < 1:
        errors.append("annotations must be a non-empty list")
        return errors

    for i, ann in enumerate(annotations):
        prefix = f"annotations[{i}]"

        if not isinstance(ann, dict):
            errors.append(f"{prefix}: must be a dict")
            continue

        # Required annotation fields
        for field in ("annotator_id", "timestamp", "response", "score", "rationale"):
            if field not in ann:
                errors.append(f"{prefix}: missing required field '{field}'")

        # annotator_id type
        if "annotator_id" in ann and not isinstance(ann["annotator_id"], str):
            errors.append(f"{prefix}: annotator_id must be a string")

        # timestamp format
        ts = ann.get("timestamp", "")
        if ts and not ISO8601_PATTERN.match(str(ts)):
            errors.append(f"{prefix}: timestamp must be ISO 8601 format")

        # score range
        score = ann.get("score")
        if score is not None:
            if not isinstance(score, (int, float)):
                errors.append(f"{prefix}: score must be a number")
            elif not (0.0 <= float(score) <= 1.0):
                errors.append(f"{prefix}: score must be between 0.0 and 1.0")

        # rationale type
        if "rationale" in ann and not isinstance(ann["rationale"], str):
            errors.append(f"{prefix}: rationale must be a string")

        # criteria_scores (optional)
        criteria = ann.get("criteria_scores")
        if criteria is not None:
            if not isinstance(criteria, dict):
                errors.append(f"{prefix}: criteria_scores must be a dict")
            else:
                valid_criteria = {"correctness", "completeness", "conciseness"}
                for crit_name, crit_val in criteria.items():
                    if crit_name not in valid_criteria:
                        errors.append(
                            f"{prefix}: unknown criterion '{crit_name}'"
                        )
                    if not isinstance(crit_val, (int, float)):
                        errors.append(
                            f"{prefix}: {crit_name} must be a number"
                        )
                    elif not (0.0 <= float(crit_val) <= 1.0):
                        errors.append(
                            f"{prefix}: {crit_name} must be between 0.0 and 1.0"
                        )

    return errors


# ---------------------------------------------------------------------------
# Schema YAML loading tests
# ---------------------------------------------------------------------------


class TestSchemaLoading:
    """Tests that schema.yaml exists and loads as valid YAML."""

    def test_schema_file_exists(self) -> None:
        """schema.yaml exists in the gold_standard directory."""
        assert SCHEMA_PATH.exists(), f"schema.yaml not found at {SCHEMA_PATH}"

    def test_schema_loads_as_yaml(self) -> None:
        """schema.yaml loads without YAML parse errors."""
        schema = _load_schema()
        assert isinstance(schema, dict)

    def test_schema_has_top_level_keys(self) -> None:
        """schema.yaml contains all required top-level sections."""
        schema = _load_schema()
        expected_keys = {"schema", "difficulty_distribution", "validation"}
        assert expected_keys.issubset(set(schema.keys())), (
            f"Missing top-level keys: {expected_keys - set(schema.keys())}"
        )

    def test_schema_section_has_task_and_annotations(self) -> None:
        """schema.schema section defines task and annotations sub-schemas."""
        schema = _load_schema()
        schema_def = schema["schema"]
        assert "task" in schema_def, "schema.schema missing 'task' definition"
        assert "annotations" in schema_def, "schema.schema missing 'annotations' definition"

    def test_schema_version_present(self) -> None:
        """schema.schema has a version field."""
        schema = _load_schema()
        assert "version" in schema["schema"]

    def test_task_schema_defines_all_required_fields(self) -> None:
        """Task sub-schema defines all 7 fields from TaskDefinition."""
        schema = _load_schema()
        task_schema = schema["schema"]["task"]
        expected_fields = {
            "task_id", "type", "question", "domain",
            "difficulty", "tags", "metadata",
        }
        assert expected_fields == set(task_schema.keys()), (
            f"Task schema fields mismatch. "
            f"Missing: {expected_fields - set(task_schema.keys())}. "
            f"Extra: {set(task_schema.keys()) - expected_fields}."
        )

    def test_task_type_enum_matches_codebase(self) -> None:
        """Task type enum in schema matches VALID_TASK_TYPES from base.py."""
        schema = _load_schema()
        schema_types = set(schema["schema"]["task"]["type"]["enum"])
        assert schema_types == VALID_TASK_TYPES, (
            f"Schema task types do not match codebase. "
            f"Schema-only: {schema_types - VALID_TASK_TYPES}. "
            f"Codebase-only: {VALID_TASK_TYPES - schema_types}."
        )

    def test_domain_enum_matches_codebase(self) -> None:
        """Domain enum in schema matches VALID_DOMAINS from base.py."""
        schema = _load_schema()
        schema_domains = set(schema["schema"]["task"]["domain"]["enum"])
        assert schema_domains == VALID_DOMAINS

    def test_difficulty_enum_matches_codebase(self) -> None:
        """Difficulty enum in schema matches VALID_DIFFICULTIES from base.py."""
        schema = _load_schema()
        schema_diffs = set(schema["schema"]["task"]["difficulty"]["enum"])
        assert schema_diffs == VALID_DIFFICULTIES


# ---------------------------------------------------------------------------
# Difficulty distribution tests
# ---------------------------------------------------------------------------


class TestDifficultyDistribution:
    """Tests for the difficulty_distribution section."""

    def test_distribution_targets_present(self) -> None:
        """Difficulty distribution defines target percentages."""
        schema = _load_schema()
        dist = schema["difficulty_distribution"]
        assert "target" in dist

    def test_distribution_targets_sum_to_one(self) -> None:
        """Difficulty distribution targets sum to 1.0."""
        schema = _load_schema()
        targets = schema["difficulty_distribution"]["target"]
        total = sum(targets.values())
        assert total == pytest.approx(1.0, abs=1e-10), (
            f"Distribution targets sum to {total}, expected 1.0"
        )

    def test_distribution_has_expected_levels(self) -> None:
        """Distribution targets include easy, medium, hard, edge."""
        schema = _load_schema()
        targets = schema["difficulty_distribution"]["target"]
        expected = {"easy", "medium", "hard", "edge"}
        assert set(targets.keys()) == expected


# ---------------------------------------------------------------------------
# Validation thresholds tests
# ---------------------------------------------------------------------------


class TestValidationThresholds:
    """Tests for the validation section thresholds."""

    def test_validation_section_present(self) -> None:
        """Validation section exists in schema."""
        schema = _load_schema()
        assert "validation" in schema

    def test_min_examples_per_type(self) -> None:
        """Minimum examples per type is 30."""
        schema = _load_schema()
        assert schema["validation"]["min_examples_per_type"] == 30

    def test_max_examples_per_type(self) -> None:
        """Maximum examples per type is 50."""
        schema = _load_schema()
        assert schema["validation"]["max_examples_per_type"] == 50

    def test_overlap_percentage(self) -> None:
        """Overlap percentage for inter-annotator agreement is 0.20."""
        schema = _load_schema()
        assert schema["validation"]["overlap_percentage"] == pytest.approx(0.20)

    def test_target_kappa(self) -> None:
        """Target Cohen's kappa is 0.70."""
        schema = _load_schema()
        assert schema["validation"]["target_kappa"] == pytest.approx(0.70)

    def test_target_spearman(self) -> None:
        """Target Spearman rho is 0.80."""
        schema = _load_schema()
        assert schema["validation"]["target_spearman"] == pytest.approx(0.80)

    def test_min_less_than_max_examples(self) -> None:
        """Minimum examples per type is less than maximum."""
        schema = _load_schema()
        v = schema["validation"]
        assert v["min_examples_per_type"] < v["max_examples_per_type"]


# ---------------------------------------------------------------------------
# Gold example validation tests
# ---------------------------------------------------------------------------


class TestGoldExampleValidation:
    """Tests that sample gold examples validate correctly."""

    def test_valid_example_passes(self) -> None:
        """A well-formed gold example produces no validation errors."""
        example = _sample_gold_example()
        errors = _validate_gold_example(example)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_valid_example_with_multiple_annotations(self) -> None:
        """Example with multiple annotators validates correctly."""
        example = _sample_gold_example()
        example["annotations"].append({
            "annotator_id": "annotator_B",
            "timestamp": "2025-01-16T09:00:00Z",
            "response": (
                "Auth middleware checks JWT tokens and sets user context."
            ),
            "score": 0.80,
            "rationale": "Concise but misses edge cases.",
            "criteria_scores": {
                "correctness": 0.85,
                "completeness": 0.70,
                "conciseness": 0.95,
            },
        })
        errors = _validate_gold_example(example)
        assert errors == [], f"Unexpected errors: {errors}"

    def test_valid_example_without_optional_fields(self) -> None:
        """Example without tags, metadata, and criteria_scores is valid."""
        example = _sample_gold_example()
        del example["task"]["tags"]
        del example["task"]["metadata"]
        del example["annotations"][0]["criteria_scores"]
        errors = _validate_gold_example(example)
        assert errors == [], f"Unexpected errors: {errors}"


# ---------------------------------------------------------------------------
# task_id pattern validation
# ---------------------------------------------------------------------------


class TestGoldTaskIdValidation:
    """Tests for task_id pattern in gold examples."""

    @pytest.mark.parametrize(
        "task_id",
        [
            "retrieval_001",
            "fact_extraction_042",
            "code_generation_python_001",
            "multi_hop_003",
            "negative_010",
        ],
    )
    def test_valid_task_ids_accepted(self, task_id: str) -> None:
        """Valid task_id patterns produce no errors."""
        example = _sample_gold_example(**{"task.task_id": task_id})
        errors = _validate_gold_example(example)
        assert errors == [], f"task_id '{task_id}' rejected: {errors}"

    @pytest.mark.parametrize(
        "task_id",
        [
            "",
            "retrieval",
            "retrieval-001",
            "001",
            "Retrieval_001",
            "retrieval_",
            "RETRIEVAL_001",
        ],
    )
    def test_invalid_task_ids_rejected(self, task_id: str) -> None:
        """Invalid task_id patterns produce validation errors."""
        example = _sample_gold_example(**{"task.task_id": task_id})
        errors = _validate_gold_example(example)
        assert any("task_id" in e for e in errors), (
            f"task_id '{task_id}' should have been rejected"
        )


# ---------------------------------------------------------------------------
# Type, domain, difficulty enum validation
# ---------------------------------------------------------------------------


class TestGoldEnumValidation:
    """Tests for type, domain, and difficulty enums in gold examples."""

    @pytest.mark.parametrize("task_type", sorted(VALID_TASK_TYPES))
    def test_all_valid_types_accepted(self, task_type: str) -> None:
        """Each of the 11 valid task types is accepted."""
        example = _sample_gold_example(
            **{
                "task.type": task_type,
                "task.task_id": f"{task_type}_001",
            }
        )
        errors = _validate_gold_example(example)
        assert errors == [], f"type '{task_type}' rejected: {errors}"

    def test_invalid_type_rejected(self) -> None:
        """Unknown task type produces a validation error."""
        example = _sample_gold_example(**{"task.type": "unknown_type"})
        errors = _validate_gold_example(example)
        assert any("type" in e for e in errors)

    @pytest.mark.parametrize("domain", sorted(VALID_DOMAINS))
    def test_all_valid_domains_accepted(self, domain: str) -> None:
        """Each valid domain is accepted."""
        example = _sample_gold_example(**{"task.domain": domain})
        errors = _validate_gold_example(example)
        assert errors == [], f"domain '{domain}' rejected: {errors}"

    def test_invalid_domain_rejected(self) -> None:
        """Unknown domain produces a validation error."""
        example = _sample_gold_example(**{"task.domain": "invalid_domain"})
        errors = _validate_gold_example(example)
        assert any("domain" in e for e in errors)

    @pytest.mark.parametrize("difficulty", sorted(VALID_DIFFICULTIES))
    def test_all_valid_difficulties_accepted(self, difficulty: str) -> None:
        """Each valid difficulty is accepted."""
        example = _sample_gold_example(**{"task.difficulty": difficulty})
        errors = _validate_gold_example(example)
        assert errors == [], f"difficulty '{difficulty}' rejected: {errors}"

    def test_invalid_difficulty_rejected(self) -> None:
        """Unknown difficulty produces a validation error."""
        example = _sample_gold_example(**{"task.difficulty": "extreme"})
        errors = _validate_gold_example(example)
        assert any("difficulty" in e for e in errors)


# ---------------------------------------------------------------------------
# Annotation structure validation
# ---------------------------------------------------------------------------


class TestGoldAnnotationValidation:
    """Tests for annotation structure in gold examples."""

    def test_missing_annotations_rejected(self) -> None:
        """Example without annotations section is rejected."""
        example = _sample_gold_example()
        del example["annotations"]
        errors = _validate_gold_example(example)
        assert any("annotations" in e for e in errors)

    def test_empty_annotations_rejected(self) -> None:
        """Example with empty annotations list is rejected."""
        example = _sample_gold_example()
        example["annotations"] = []
        errors = _validate_gold_example(example)
        assert any("annotations" in e for e in errors)

    def test_missing_annotator_id_rejected(self) -> None:
        """Annotation without annotator_id is rejected."""
        example = _sample_gold_example()
        del example["annotations"][0]["annotator_id"]
        errors = _validate_gold_example(example)
        assert any("annotator_id" in e for e in errors)

    def test_missing_timestamp_rejected(self) -> None:
        """Annotation without timestamp is rejected."""
        example = _sample_gold_example()
        del example["annotations"][0]["timestamp"]
        errors = _validate_gold_example(example)
        assert any("timestamp" in e for e in errors)

    def test_invalid_timestamp_format_rejected(self) -> None:
        """Annotation with non-ISO-8601 timestamp is rejected."""
        example = _sample_gold_example(
            **{"annotations.0.timestamp": "Jan 15 2025"}
        )
        errors = _validate_gold_example(example)
        assert any("timestamp" in e for e in errors)

    def test_missing_response_rejected(self) -> None:
        """Annotation without response text is rejected."""
        example = _sample_gold_example()
        del example["annotations"][0]["response"]
        errors = _validate_gold_example(example)
        assert any("response" in e for e in errors)

    def test_missing_score_rejected(self) -> None:
        """Annotation without score is rejected."""
        example = _sample_gold_example()
        del example["annotations"][0]["score"]
        errors = _validate_gold_example(example)
        assert any("score" in e for e in errors)

    def test_score_below_zero_rejected(self) -> None:
        """Score below 0.0 is rejected."""
        example = _sample_gold_example(**{"annotations.0.score": -0.1})
        errors = _validate_gold_example(example)
        assert any("score" in e for e in errors)

    def test_score_above_one_rejected(self) -> None:
        """Score above 1.0 is rejected."""
        example = _sample_gold_example(**{"annotations.0.score": 1.5})
        errors = _validate_gold_example(example)
        assert any("score" in e for e in errors)

    def test_score_at_boundaries_accepted(self) -> None:
        """Scores at 0.0 and 1.0 boundaries are accepted."""
        for score in (0.0, 1.0):
            example = _sample_gold_example(**{"annotations.0.score": score})
            errors = _validate_gold_example(example)
            assert errors == [], f"Score {score} rejected: {errors}"

    def test_missing_rationale_rejected(self) -> None:
        """Annotation without rationale is rejected."""
        example = _sample_gold_example()
        del example["annotations"][0]["rationale"]
        errors = _validate_gold_example(example)
        assert any("rationale" in e for e in errors)

    def test_criteria_score_below_zero_rejected(self) -> None:
        """Criteria score below 0.0 is rejected."""
        example = _sample_gold_example()
        example["annotations"][0]["criteria_scores"]["correctness"] = -0.5
        errors = _validate_gold_example(example)
        assert any("correctness" in e for e in errors)

    def test_criteria_score_above_one_rejected(self) -> None:
        """Criteria score above 1.0 is rejected."""
        example = _sample_gold_example()
        example["annotations"][0]["criteria_scores"]["completeness"] = 2.0
        errors = _validate_gold_example(example)
        assert any("completeness" in e for e in errors)

    def test_unknown_criterion_rejected(self) -> None:
        """Unknown criterion name is rejected."""
        example = _sample_gold_example()
        example["annotations"][0]["criteria_scores"]["novelty"] = 0.5
        errors = _validate_gold_example(example)
        assert any("novelty" in e for e in errors)


# ---------------------------------------------------------------------------
# Missing task fields
# ---------------------------------------------------------------------------


class TestGoldMissingTaskFields:
    """Tests for missing required task fields."""

    @pytest.mark.parametrize(
        "field",
        ["task_id", "type", "question", "domain", "difficulty"],
    )
    def test_missing_required_task_field_rejected(self, field: str) -> None:
        """Each required task field must be present."""
        example = _sample_gold_example()
        del example["task"][field]
        errors = _validate_gold_example(example)
        assert any(field in e for e in errors), (
            f"Missing '{field}' should have been caught"
        )

    def test_missing_task_section_rejected(self) -> None:
        """Example without task section entirely is rejected."""
        example = _sample_gold_example()
        del example["task"]
        errors = _validate_gold_example(example)
        assert any("task" in e for e in errors)


# ---------------------------------------------------------------------------
# Directory structure tests
# ---------------------------------------------------------------------------


class TestGoldStandardDirectoryStructure:
    """Tests that the gold_standard directory structure exists."""

    def test_gold_standard_root_exists(self) -> None:
        """gold_standard/ directory exists."""
        assert GOLD_STANDARD_DIR.is_dir()

    @pytest.mark.parametrize("task_type", sorted(VALID_TASK_TYPES))
    def test_task_type_subdirectory_exists(self, task_type: str) -> None:
        """Each of the 11 task type subdirectories exists."""
        subdir = GOLD_STANDARD_DIR / task_type
        assert subdir.is_dir(), f"Missing directory: {subdir}"

    def test_sentinels_directory_exists(self) -> None:
        """sentinels/ subdirectory exists."""
        assert (GOLD_STANDARD_DIR / "sentinels").is_dir()

    def test_canaries_directory_exists(self) -> None:
        """canaries/ subdirectory exists."""
        assert (GOLD_STANDARD_DIR / "canaries").is_dir()

    def test_init_py_exists(self) -> None:
        """__init__.py exists in gold_standard/."""
        assert (GOLD_STANDARD_DIR / "__init__.py").is_file()

    def test_schema_yaml_exists(self) -> None:
        """schema.yaml exists in gold_standard/."""
        assert (GOLD_STANDARD_DIR / "schema.yaml").is_file()


# Task 29 robustness base_task_id test
def test_all_robustness_tasks_have_base_task_id():
    from pathlib import Path
    from agent_evals.tasks.loader import load_tasks
    robustness_dir = Path("agent-evals/gold_standard/robustness/")
    tasks = load_tasks(robustness_dir)
    missing = [t.definition.task_id for t in tasks if "base_task_id" not in (t.definition.metadata or {})]
    assert not missing, f"Missing base_task_id in {len(missing)} tasks: {missing[:5]}"
