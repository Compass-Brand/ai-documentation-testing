"""Tests for sentinel and canary gold standard task YAML files.

Validates that:
- All sentinel and canary YAML files parse correctly via the task loader
- Sentinel task_ids follow the expected naming pattern
- All sentinels have difficulty "easy"
- Each domain has exactly 5 sentinels
- There are exactly 10 canaries
- Fact extraction sentinels have expected_answer values matching fixture docs
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import yaml
from agent_evals.fixtures import sample_docs_directory
from agent_evals.tasks.base import TASK_ID_PATTERN, TaskDefinition
from agent_evals.tasks.loader import load_task, load_tasks

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_GOLD_STANDARD_DIR = _PROJECT_ROOT / "gold_standard"
_SENTINELS_DIR = _GOLD_STANDARD_DIR / "sentinels"
_CANARIES_DIR = _GOLD_STANDARD_DIR / "canaries"

# Mapping from domain -> fixture subdirectory prefix
_DOMAIN_TO_FIXTURE_PREFIX: dict[str, str] = {
    "framework_api": "api",
    "project_repo": "repo",
    "skills_workflows": "workflows",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_fixture_doc(relative_path: str) -> str:
    """Load a fixture document by its relative path (e.g. 'api/caching.md')."""
    docs_dir = sample_docs_directory()
    full_path = docs_dir / relative_path
    return full_path.read_text(encoding="utf-8")


def _all_sentinel_paths() -> list[Path]:
    """Return sorted list of all sentinel YAML files."""
    return sorted(_SENTINELS_DIR.glob("sentinel_*.yaml"))


def _all_canary_paths() -> list[Path]:
    """Return sorted list of all canary YAML files."""
    return sorted(_CANARIES_DIR.glob("canary_*.yaml"))


# ---------------------------------------------------------------------------
# Sentinel loading and validation
# ---------------------------------------------------------------------------


class TestSentinelLoading:
    """Tests that all sentinel YAML files load and parse correctly."""

    def test_sentinels_directory_exists(self) -> None:
        """The sentinels directory exists."""
        assert _SENTINELS_DIR.is_dir(), f"Missing directory: {_SENTINELS_DIR}"

    def test_sentinel_count(self) -> None:
        """There are exactly 15 sentinel YAML files."""
        paths = _all_sentinel_paths()
        assert len(paths) == 15, f"Expected 15 sentinels, found {len(paths)}"

    def test_all_sentinels_load_via_task_loader(self) -> None:
        """Every sentinel YAML file loads successfully through load_task."""
        for path in _all_sentinel_paths():
            task = load_task(path)
            assert task is not None, f"Failed to load sentinel: {path.name}"

    def test_all_sentinels_parse_as_valid_task_definitions(self) -> None:
        """Every sentinel YAML parses into a valid TaskDefinition."""
        for path in _all_sentinel_paths():
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            defn = TaskDefinition(**raw)
            assert defn.task_id.startswith("sentinel_")


class TestSentinelTaskIdPattern:
    """Tests that sentinel task_ids follow the required naming pattern."""

    def test_sentinel_ids_match_task_id_pattern(self) -> None:
        """Every sentinel task_id matches the base TASK_ID_PATTERN regex."""
        for path in _all_sentinel_paths():
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            task_id = raw["task_id"]
            assert TASK_ID_PATTERN.match(task_id), (
                f"task_id '{task_id}' in {path.name} does not match pattern"
            )

    def test_sentinel_ids_start_with_sentinel_prefix(self) -> None:
        """Every sentinel task_id starts with 'sentinel_'."""
        for path in _all_sentinel_paths():
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            task_id = raw["task_id"]
            assert task_id.startswith("sentinel_"), (
                f"task_id '{task_id}' in {path.name} does not start with 'sentinel_'"
            )

    def test_sentinel_ids_are_sequential(self) -> None:
        """Sentinel task_ids use sequential numbering 001-015."""
        expected_ids = {f"sentinel_{i:03d}" for i in range(1, 16)}
        actual_ids = set()
        for path in _all_sentinel_paths():
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            actual_ids.add(raw["task_id"])
        assert actual_ids == expected_ids, (
            f"Missing: {expected_ids - actual_ids}, Extra: {actual_ids - expected_ids}"
        )


class TestSentinelDifficulty:
    """Tests that all sentinels are marked as easy difficulty."""

    def test_all_sentinels_are_easy(self) -> None:
        """Every sentinel has difficulty set to 'easy'."""
        for path in _all_sentinel_paths():
            task = load_task(path)
            assert task.definition.difficulty == "easy", (
                f"Sentinel {task.definition.task_id} has difficulty "
                f"'{task.definition.difficulty}', expected 'easy'"
            )


class TestSentinelDomainDistribution:
    """Tests that sentinels are evenly distributed across domains."""

    def test_each_domain_has_exactly_five_sentinels(self) -> None:
        """Each of the 3 domains has exactly 5 sentinel tasks."""
        domain_counts: Counter[str] = Counter()
        for path in _all_sentinel_paths():
            task = load_task(path)
            domain_counts[task.definition.domain] += 1

        for domain in ["framework_api", "project_repo", "skills_workflows"]:
            assert domain_counts[domain] == 5, (
                f"Domain '{domain}' has {domain_counts[domain]} sentinels, expected 5"
            )

    def test_all_three_domains_represented(self) -> None:
        """All 3 valid domains appear in the sentinels."""
        domains = set()
        for path in _all_sentinel_paths():
            task = load_task(path)
            domains.add(task.definition.domain)
        assert domains == {"framework_api", "project_repo", "skills_workflows"}


class TestSentinelTaskTypes:
    """Tests that sentinels use only the approved easy task types."""

    def test_sentinel_types_are_trivial(self) -> None:
        """Every sentinel uses retrieval, fact_extraction, or negative type."""
        allowed_types = {"retrieval", "fact_extraction", "negative"}
        for path in _all_sentinel_paths():
            task = load_task(path)
            assert task.definition.type in allowed_types, (
                f"Sentinel {task.definition.task_id} has type "
                f"'{task.definition.type}', expected one of {allowed_types}"
            )


# ---------------------------------------------------------------------------
# Sentinel fact verification against fixture docs
# ---------------------------------------------------------------------------


class TestSentinelFactVerification:
    """Tests that fact_extraction sentinels have answers matching fixture docs."""

    def _get_fact_extraction_sentinels(self) -> list[tuple[Path, dict]]:
        """Return (path, raw_data) for all fact_extraction sentinels."""
        results = []
        for path in _all_sentinel_paths():
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if raw["type"] == "fact_extraction":
                results.append((path, raw))
        return results

    def test_fact_extraction_sentinels_have_expected_answer(self) -> None:
        """Every fact_extraction sentinel has a non-empty expected_answer."""
        for _path, raw in self._get_fact_extraction_sentinels():
            metadata = raw.get("metadata", {})
            expected_answer = metadata.get("expected_answer", "")
            assert expected_answer, (
                f"Sentinel {raw['task_id']} missing expected_answer in metadata"
            )

    def test_sentinel_002_cache_ttl_in_fixture(self) -> None:
        """sentinel_002 expected_answer '300' appears in api/caching.md."""
        doc_content = _load_fixture_doc("api/caching.md")
        assert "300" in doc_content, (
            "Expected '300' (default TTL) not found in api/caching.md"
        )

    def test_sentinel_005_log_level_in_fixture(self) -> None:
        """sentinel_005 expected_answer 'INFO' appears in api/config.md."""
        doc_content = _load_fixture_doc("api/config.md")
        assert "INFO" in doc_content, (
            "Expected 'INFO' (default LOG_LEVEL) not found in api/config.md"
        )

    def test_sentinel_007_python_version_in_fixture(self) -> None:
        """sentinel_007 expected_answer '3.10' appears in repo/changelog.md."""
        doc_content = _load_fixture_doc("repo/changelog.md")
        assert "3.10" in doc_content, (
            "Expected '3.10' (minimum Python version) not found in repo/changelog.md"
        )

    def test_sentinel_010_license_in_fixture(self) -> None:
        """sentinel_010 expected_answer 'MIT' appears in repo/README.md."""
        doc_content = _load_fixture_doc("repo/README.md")
        assert "MIT" in doc_content, (
            "Expected 'MIT' (license) not found in repo/README.md"
        )

    def test_sentinel_012_ci_platform_in_fixture(self) -> None:
        """sentinel_012 expected_answer 'GitHub Actions' appears in workflows/ci-setup.md."""
        doc_content = _load_fixture_doc("workflows/ci-setup.md")
        assert "GitHub Actions" in doc_content, (
            "Expected 'GitHub Actions' not found in workflows/ci-setup.md"
        )

    def test_sentinel_015_coverage_threshold_in_fixture(self) -> None:
        """sentinel_015 expected_answer '90%' appears in workflows/release.md."""
        doc_content = _load_fixture_doc("workflows/release.md")
        assert "90%" in doc_content, (
            "Expected '90%' (coverage threshold) not found in workflows/release.md"
        )

    def test_all_fact_extraction_answers_in_fixtures(self) -> None:
        """Every fact_extraction sentinel's expected_answer appears in its source doc."""
        for _path, raw in self._get_fact_extraction_sentinels():
            metadata = raw.get("metadata", {})
            expected_answer = metadata.get("expected_answer", "")
            source_location = metadata.get("source_location", "")
            assert source_location, (
                f"Sentinel {raw['task_id']} missing source_location in metadata"
            )
            doc_content = _load_fixture_doc(source_location)
            assert expected_answer in doc_content, (
                f"Sentinel {raw['task_id']}: expected_answer '{expected_answer}' "
                f"not found in {source_location}"
            )


# ---------------------------------------------------------------------------
# Canary loading and validation
# ---------------------------------------------------------------------------


class TestCanaryLoading:
    """Tests that all canary YAML files load and parse correctly."""

    def test_canaries_directory_exists(self) -> None:
        """The canaries directory exists."""
        assert _CANARIES_DIR.is_dir(), f"Missing directory: {_CANARIES_DIR}"

    def test_canary_count(self) -> None:
        """There are exactly 10 canary YAML files."""
        paths = _all_canary_paths()
        assert len(paths) == 10, f"Expected 10 canaries, found {len(paths)}"

    def test_all_canaries_load_via_task_loader(self) -> None:
        """Every canary YAML file loads successfully through load_task."""
        for path in _all_canary_paths():
            task = load_task(path)
            assert task is not None, f"Failed to load canary: {path.name}"

    def test_all_canaries_parse_as_valid_task_definitions(self) -> None:
        """Every canary YAML parses into a valid TaskDefinition."""
        for path in _all_canary_paths():
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            defn = TaskDefinition(**raw)
            assert defn.task_id.startswith("canary_")


class TestCanaryTaskIdPattern:
    """Tests that canary task_ids follow the required naming pattern."""

    def test_canary_ids_match_task_id_pattern(self) -> None:
        """Every canary task_id matches the base TASK_ID_PATTERN regex."""
        for path in _all_canary_paths():
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            task_id = raw["task_id"]
            assert TASK_ID_PATTERN.match(task_id), (
                f"task_id '{task_id}' in {path.name} does not match pattern"
            )

    def test_canary_ids_are_sequential(self) -> None:
        """Canary task_ids use sequential numbering 001-010."""
        expected_ids = {f"canary_{i:03d}" for i in range(1, 11)}
        actual_ids = set()
        for path in _all_canary_paths():
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            actual_ids.add(raw["task_id"])
        assert actual_ids == expected_ids, (
            f"Missing: {expected_ids - actual_ids}, Extra: {actual_ids - expected_ids}"
        )


class TestCanaryTaskTypeMix:
    """Tests that canaries cover a mix of task types for scoring verification."""

    def test_canaries_include_retrieval(self) -> None:
        """At least one canary uses the retrieval task type."""
        types = set()
        for path in _all_canary_paths():
            task = load_task(path)
            types.add(task.definition.type)
        assert "retrieval" in types

    def test_canaries_include_fact_extraction(self) -> None:
        """At least one canary uses the fact_extraction task type."""
        types = set()
        for path in _all_canary_paths():
            task = load_task(path)
            types.add(task.definition.type)
        assert "fact_extraction" in types

    def test_canaries_include_negative(self) -> None:
        """At least one canary uses the negative task type."""
        types = set()
        for path in _all_canary_paths():
            task = load_task(path)
            types.add(task.definition.type)
        assert "negative" in types

    def test_canaries_include_code_generation(self) -> None:
        """At least one canary uses the code_generation task type."""
        types = set()
        for path in _all_canary_paths():
            task = load_task(path)
            types.add(task.definition.type)
        assert "code_generation" in types

    def test_canaries_include_disambiguation(self) -> None:
        """At least one canary uses the disambiguation task type."""
        types = set()
        for path in _all_canary_paths():
            task = load_task(path)
            types.add(task.definition.type)
        assert "disambiguation" in types

    def test_canaries_cover_at_least_four_task_types(self) -> None:
        """Canaries collectively cover at least 4 different task types."""
        types = set()
        for path in _all_canary_paths():
            task = load_task(path)
            types.add(task.definition.type)
        assert len(types) >= 4, (
            f"Expected at least 4 task types, found {len(types)}: {types}"
        )


# ---------------------------------------------------------------------------
# Combined load_tasks test
# ---------------------------------------------------------------------------


class TestBulkLoading:
    """Tests that load_tasks works with sentinel and canary directories."""

    def test_load_all_sentinels_via_load_tasks(self) -> None:
        """load_tasks on the sentinels directory returns 15 tasks."""
        tasks = load_tasks(_SENTINELS_DIR)
        assert len(tasks) == 15

    def test_load_all_canaries_via_load_tasks(self) -> None:
        """load_tasks on the canaries directory returns 10 tasks."""
        tasks = load_tasks(_CANARIES_DIR)
        assert len(tasks) == 10

    def test_sentinel_and_canary_ids_are_unique(self) -> None:
        """All task_ids across sentinels and canaries are unique."""
        sentinel_tasks = load_tasks(_SENTINELS_DIR)
        canary_tasks = load_tasks(_CANARIES_DIR)
        all_ids = [t.definition.task_id for t in sentinel_tasks + canary_tasks]
        assert len(all_ids) == len(set(all_ids)), (
            f"Duplicate task_ids found: {[x for x in all_ids if all_ids.count(x) > 1]}"
        )
