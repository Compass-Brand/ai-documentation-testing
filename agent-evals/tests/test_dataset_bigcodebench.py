"""Tests for the BigCodeBench dataset adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from agent_evals.datasets.base import DatasetAdapter


def _make_bigcodebench_record(
    task_id: str = "BigCodeBench/0",
    instruct_prompt: str = "Write a function that uses pandas and numpy to process data.",
    canonical_solution: str = "import pandas as pd\ndef solve(): return pd.DataFrame()",
    test: str = "assert solve() is not None",
    libs: list[str] | None = None,
) -> dict:
    if libs is None:
        libs = ["pandas", "numpy"]
    return {
        "task_id": task_id,
        "instruct_prompt": instruct_prompt,
        "canonical_solution": canonical_solution,
        "test": test,
        "libs": libs,
        "complete_prompt": instruct_prompt,
        "doc_struct": "{}",
    }


def _mock_dataset(records: list[dict]) -> MagicMock:
    ds = MagicMock()
    ds.__len__ = lambda self: len(records)
    ds.__iter__ = lambda self: iter(records)
    ds.filter = lambda fn: _mock_dataset([r for r in records if fn(r)])
    ds.select = lambda indices: _mock_dataset([records[i] for i in indices])
    return ds


class TestBigCodeBenchMetadata:
    def test_name(self) -> None:
        from agent_evals.datasets.bigcodebench import BigCodeBenchAdapter

        assert BigCodeBenchAdapter().name() == "bigcodebench"

    def test_task_type(self) -> None:
        from agent_evals.datasets.bigcodebench import BigCodeBenchAdapter

        assert BigCodeBenchAdapter().task_type() == "compositional"

    def test_domain(self) -> None:
        from agent_evals.datasets.bigcodebench import BigCodeBenchAdapter

        assert BigCodeBenchAdapter().domain() == "library_docs"

    def test_contamination_risk(self) -> None:
        from agent_evals.datasets.bigcodebench import BigCodeBenchAdapter

        assert BigCodeBenchAdapter().contamination_risk() == "moderate"


class TestBigCodeBenchConvertTasks:
    def test_converts_multi_lib_records_to_compositional_tasks(
        self, tmp_path: Path,
    ) -> None:
        from agent_evals.datasets.bigcodebench import BigCodeBenchAdapter

        records = [
            _make_bigcodebench_record(
                task_id="BigCodeBench/0",
                libs=["pandas", "numpy"],
            ),
            _make_bigcodebench_record(
                task_id="BigCodeBench/1",
                libs=["os"],  # single lib, might be skipped
            ),
        ]
        adapter = BigCodeBenchAdapter()
        with patch(
            "agent_evals.datasets.bigcodebench.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            count = adapter.convert_tasks(tmp_path)

        # At least the multi-lib record should be converted
        assert count >= 1

    def test_generated_yaml_has_correct_schema(self, tmp_path: Path) -> None:
        from agent_evals.datasets.bigcodebench import BigCodeBenchAdapter

        records = [
            _make_bigcodebench_record(
                task_id="BigCodeBench/0",
                instruct_prompt="Use pandas and numpy to compute stats.",
                libs=["pandas", "numpy"],
            ),
        ]
        adapter = BigCodeBenchAdapter()
        with patch(
            "agent_evals.datasets.bigcodebench.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            adapter.convert_tasks(tmp_path)

        yaml_files = list(tmp_path.glob("*.yaml"))
        assert len(yaml_files) >= 1

        task = yaml.safe_load(yaml_files[0].read_text(encoding="utf-8"))
        assert task["task_id"].startswith("bigcodebench_compositional_")
        assert task["type"] == "compositional"
        assert task["domain"] == "library_docs"
        meta = task["metadata"]
        # Compositional tasks need sub_questions + expected_answers
        assert "sub_questions" in meta or "sub_tasks" in meta
        assert "expected_answers" in meta or "sub_tasks" in meta

    def test_limit_caps_output(self, tmp_path: Path) -> None:
        from agent_evals.datasets.bigcodebench import BigCodeBenchAdapter

        records = [
            _make_bigcodebench_record(task_id=f"BigCodeBench/{i}", libs=["a", "b"])
            for i in range(20)
        ]
        adapter = BigCodeBenchAdapter()
        with patch(
            "agent_evals.datasets.bigcodebench.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            count = adapter.convert_tasks(tmp_path, limit=5)

        assert count == 5


class TestBigCodeBenchBuildDocTree:
    def test_builds_doc_tree(self) -> None:
        from agent_evals.datasets.bigcodebench import BigCodeBenchAdapter

        records = [
            _make_bigcodebench_record(
                task_id="BigCodeBench/0",
                libs=["pandas", "numpy"],
                canonical_solution="import pandas as pd\nimport numpy as np\ndef solve(): pass",
            ),
        ]
        adapter = BigCodeBenchAdapter()
        with patch(
            "agent_evals.datasets.bigcodebench.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            doc_tree = adapter.build_doc_tree()

        assert len(doc_tree.files) >= 1


class TestBigCodeBenchRegistration:
    def test_registered(self) -> None:
        from agent_evals.datasets import DATASET_REGISTRY

        import agent_evals.datasets.bigcodebench  # noqa: F401

        assert "bigcodebench" in DATASET_REGISTRY
