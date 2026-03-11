"""Tests for the SWE-bench dataset adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

# Realistic patch and test_patch content for test records
_SAMPLE_PATCH = (
    "diff --git a/django/db/models/base.py b/django/db/models/base.py\n"
    "--- a/django/db/models/base.py\n"
    "+++ b/django/db/models/base.py\n"
    "@@ -800,7 +800,7 @@\n"
    "-        old_code()\n"
    "+        new_code()\n"
)

_SAMPLE_TEST_PATCH = (
    "diff --git a/tests/model_tests/test_save.py b/tests/model_tests/test_save.py\n"
    "--- a/tests/model_tests/test_save.py\n"
    "+++ b/tests/model_tests/test_save.py\n"
    "@@ -10,0 +10,5 @@\n"
    "+def test_save_null():\n"
    "+    pass\n"
)

_MULTI_FILE_PATCH = (
    "diff --git a/src/alpha.py b/src/alpha.py\n"
    "--- a/src/alpha.py\n"
    "+++ b/src/alpha.py\n"
    "@@ -1 +1 @@\n"
    "-old\n"
    "+new\n"
    "diff --git a/src/beta.py b/src/beta.py\n"
    "--- a/src/beta.py\n"
    "+++ b/src/beta.py\n"
    "@@ -1 +1 @@\n"
    "-old\n"
    "+new\n"
)


def _make_swe_record(
    instance_id: str = "django__django-12345",
    problem_statement: str = "Bug: model save fails on NULL field.",
    repo: str = "django/django",
    base_commit: str = "abc123",
    hints_text: str = "Check models/base.py",
    FAIL_TO_PASS: str = '["test_save_null"]',
    PASS_TO_PASS: str = '["test_save_normal"]',
    patch_text: str = _SAMPLE_PATCH,
    test_patch_text: str = _SAMPLE_TEST_PATCH,
) -> dict:
    return {
        "instance_id": instance_id,
        "problem_statement": problem_statement,
        "repo": repo,
        "base_commit": base_commit,
        "hints_text": hints_text,
        "FAIL_TO_PASS": FAIL_TO_PASS,
        "PASS_TO_PASS": PASS_TO_PASS,
        "patch": patch_text,
        "test_patch": test_patch_text,
    }


def _mock_dataset(records: list[dict]) -> MagicMock:
    ds = MagicMock()
    ds.__len__ = lambda self: len(records)
    ds.__iter__ = lambda self: iter(records)
    ds.select = lambda indices: _mock_dataset([records[i] for i in indices])
    return ds


class TestExtractPatchFiles:
    """Tests for _extract_patch_files helper."""

    def test_extracts_single_file(self) -> None:
        from agent_evals.datasets.swe_bench import _extract_patch_files

        result = _extract_patch_files(_SAMPLE_PATCH)
        assert result == ["django/db/models/base.py"]

    def test_extracts_multiple_files(self) -> None:
        from agent_evals.datasets.swe_bench import _extract_patch_files

        result = _extract_patch_files(_MULTI_FILE_PATCH)
        assert result == ["src/alpha.py", "src/beta.py"]

    def test_deduplicates_files(self) -> None:
        from agent_evals.datasets.swe_bench import _extract_patch_files

        duplicated = _SAMPLE_PATCH + "\n" + _SAMPLE_PATCH
        result = _extract_patch_files(duplicated)
        assert result == ["django/db/models/base.py"]

    def test_empty_patch_returns_empty(self) -> None:
        from agent_evals.datasets.swe_bench import _extract_patch_files

        assert _extract_patch_files("") == []
        assert _extract_patch_files(None) == []

    def test_no_diff_headers_returns_empty(self) -> None:
        from agent_evals.datasets.swe_bench import _extract_patch_files

        assert _extract_patch_files("just some random text") == []


class TestSummarizeForFile:
    """Tests for _summarize_for_file helper."""

    def test_includes_problem_first_line(self) -> None:
        from agent_evals.datasets.swe_bench import _summarize_for_file

        result = _summarize_for_file("foo.py", "Bug in parser\nMore details", "")
        assert "Bug in parser" in result

    def test_includes_hints_when_present(self) -> None:
        from agent_evals.datasets.swe_bench import _summarize_for_file

        result = _summarize_for_file("foo.py", "Bug", "Check line 42")
        assert "Check line 42" in result

    def test_no_hints_omits_hint_section(self) -> None:
        from agent_evals.datasets.swe_bench import _summarize_for_file

        result = _summarize_for_file("foo.py", "Bug", "")
        assert "Hint:" not in result

    def test_truncates_long_problem(self) -> None:
        from agent_evals.datasets.swe_bench import _summarize_for_file

        long_problem = "A" * 200
        result = _summarize_for_file("foo.py", long_problem, "")
        # Should be truncated to 120 chars (117 + "...")
        assert "..." in result
        assert len(result) < 200


class TestSWEBenchMetadata:
    def test_name(self) -> None:
        from agent_evals.datasets.swe_bench import SWEBenchAdapter
        assert SWEBenchAdapter().name() == "swe-bench"

    def test_task_type(self) -> None:
        from agent_evals.datasets.swe_bench import SWEBenchAdapter
        assert SWEBenchAdapter().task_type() == "agentic"

    def test_domain(self) -> None:
        from agent_evals.datasets.swe_bench import SWEBenchAdapter
        assert SWEBenchAdapter().domain() == "code_repository"

    def test_contamination_risk(self) -> None:
        from agent_evals.datasets.swe_bench import SWEBenchAdapter
        assert SWEBenchAdapter().contamination_risk() == "high"


class TestSWEBenchConvertTasks:
    def test_converts_records_to_agentic_tasks(self, tmp_path: Path) -> None:
        from agent_evals.datasets.swe_bench import SWEBenchAdapter

        records = [_make_swe_record(), _make_swe_record(instance_id="x__y-999")]
        adapter = SWEBenchAdapter()
        with patch(
            "agent_evals.datasets.swe_bench.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            count = adapter.convert_tasks(tmp_path)
        assert count == 2

    def test_generated_yaml_has_correct_schema(self, tmp_path: Path) -> None:
        from agent_evals.datasets.swe_bench import SWEBenchAdapter

        records = [_make_swe_record()]
        adapter = SWEBenchAdapter()
        with patch(
            "agent_evals.datasets.swe_bench.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            adapter.convert_tasks(tmp_path)

        task = yaml.safe_load(list(tmp_path.glob("*.yaml"))[0].read_text())
        assert task["type"] == "agentic"
        assert task["domain"] == "code_repository"
        assert "files" in task["metadata"]
        assert "FAIL_TO_PASS" in task["metadata"]

    def test_files_contain_real_patch_paths(self, tmp_path: Path) -> None:
        from agent_evals.datasets.swe_bench import SWEBenchAdapter

        records = [_make_swe_record()]
        adapter = SWEBenchAdapter()
        with patch(
            "agent_evals.datasets.swe_bench.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            adapter.convert_tasks(tmp_path)

        task = yaml.safe_load(list(tmp_path.glob("*.yaml"))[0].read_text())
        files = task["metadata"]["files"]
        # Should have the real source file from the patch
        assert "django/db/models/base.py" in files
        # Should have the test file from test_patch
        assert "tests/model_tests/test_save.py" in files
        # Should NOT have the old bogus path
        assert "django/django/docs/README.md" not in files

    def test_files_have_meaningful_summaries(self, tmp_path: Path) -> None:
        from agent_evals.datasets.swe_bench import SWEBenchAdapter

        records = [_make_swe_record(
            problem_statement="Bug: model save fails on NULL field.",
            hints_text="Check models/base.py",
        )]
        adapter = SWEBenchAdapter()
        with patch(
            "agent_evals.datasets.swe_bench.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            adapter.convert_tasks(tmp_path)

        task = yaml.safe_load(list(tmp_path.glob("*.yaml"))[0].read_text())
        files = task["metadata"]["files"]
        source_summary = files["django/db/models/base.py"]
        # Summary should reference the problem, not be generic
        assert "model save fails" in source_summary.lower() or "NULL" in source_summary
        assert "Repository documentation" not in source_summary
        # Should include the hint
        assert "Check models/base.py" in source_summary

    def test_files_from_multi_file_patch(self, tmp_path: Path) -> None:
        from agent_evals.datasets.swe_bench import SWEBenchAdapter

        records = [_make_swe_record(patch_text=_MULTI_FILE_PATCH)]
        adapter = SWEBenchAdapter()
        with patch(
            "agent_evals.datasets.swe_bench.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            adapter.convert_tasks(tmp_path)

        task = yaml.safe_load(list(tmp_path.glob("*.yaml"))[0].read_text())
        files = task["metadata"]["files"]
        assert "src/alpha.py" in files
        assert "src/beta.py" in files

    def test_empty_patch_produces_empty_files(self, tmp_path: Path) -> None:
        from agent_evals.datasets.swe_bench import SWEBenchAdapter

        records = [_make_swe_record(patch_text="", test_patch_text="")]
        adapter = SWEBenchAdapter()
        with patch(
            "agent_evals.datasets.swe_bench.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            adapter.convert_tasks(tmp_path)

        task = yaml.safe_load(list(tmp_path.glob("*.yaml"))[0].read_text())
        assert task["metadata"]["files"] == {}

    def test_test_patch_files_not_duplicated(self, tmp_path: Path) -> None:
        """When the same file appears in both patch and test_patch, it's not duplicated."""
        from agent_evals.datasets.swe_bench import SWEBenchAdapter

        # Use a patch and test_patch that share a file
        shared_patch = (
            "diff --git a/src/foo.py b/src/foo.py\n"
            "--- a/src/foo.py\n"
            "+++ b/src/foo.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        )
        records = [_make_swe_record(patch_text=shared_patch, test_patch_text=shared_patch)]
        adapter = SWEBenchAdapter()
        with patch(
            "agent_evals.datasets.swe_bench.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            adapter.convert_tasks(tmp_path)

        task = yaml.safe_load(list(tmp_path.glob("*.yaml"))[0].read_text())
        files = task["metadata"]["files"]
        # Should only have one entry for src/foo.py (from patch, not duplicated by test_patch)
        assert list(files.keys()).count("src/foo.py") == 1

    def test_limit_caps_output(self, tmp_path: Path) -> None:
        from agent_evals.datasets.swe_bench import SWEBenchAdapter

        records = [_make_swe_record(instance_id=f"r__r-{i}") for i in range(20)]
        adapter = SWEBenchAdapter()
        with patch(
            "agent_evals.datasets.swe_bench.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            count = adapter.convert_tasks(tmp_path, limit=5)
        assert count == 5


class TestSWEBenchRegistration:
    def test_registered(self) -> None:
        from agent_evals.datasets import DATASET_REGISTRY
        import agent_evals.datasets.swe_bench  # noqa: F401
        assert "swe-bench" in DATASET_REGISTRY
