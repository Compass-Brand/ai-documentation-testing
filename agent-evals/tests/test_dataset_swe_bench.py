"""Tests for the SWE-bench dataset adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml


def _make_swe_record(
    instance_id: str = "django__django-12345",
    problem_statement: str = "Bug: model save fails on NULL field.",
    repo: str = "django/django",
    base_commit: str = "abc123",
    hints_text: str = "Check models/base.py",
    FAIL_TO_PASS: str = '["test_save_null"]',
    PASS_TO_PASS: str = '["test_save_normal"]',
) -> dict:
    return {
        "instance_id": instance_id,
        "problem_statement": problem_statement,
        "repo": repo,
        "base_commit": base_commit,
        "hints_text": hints_text,
        "FAIL_TO_PASS": FAIL_TO_PASS,
        "PASS_TO_PASS": PASS_TO_PASS,
    }


def _mock_dataset(records: list[dict]) -> MagicMock:
    ds = MagicMock()
    ds.__len__ = lambda self: len(records)
    ds.__iter__ = lambda self: iter(records)
    ds.select = lambda indices: _mock_dataset([records[i] for i in indices])
    return ds


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
