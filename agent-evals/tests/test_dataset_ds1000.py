"""Tests for the DS-1000 dataset adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from agent_evals.datasets.base import DatasetAdapter


def _make_ds1000_record(
    task_id: int = 0,
    prompt: str = "import numpy as np\ndef solve():\n    # ",
    canonical_solution: str = "return np.array([1,2,3])",
    test: str = "assert solve().shape == (3,)",
    entry_point: str = "solve",
    library: list[str] | None = None,
    docs: list[dict] | None = None,
) -> dict:
    if library is None:
        library = ["numpy"]
    if docs is None:
        docs = [{"title": "numpy.array", "text": "Create an array."}]
    return {
        "task_id": task_id,
        "prompt": prompt,
        "canonical_solution": canonical_solution,
        "test_start": "",
        "test": [test] if isinstance(test, str) else test,
        "entry_point": entry_point,
        "intent": prompt,
        "library": library,
        "docs": docs,
        "suffix": "",
    }


def _mock_dataset(records: list[dict]) -> MagicMock:
    ds = MagicMock()
    ds.__len__ = lambda self: len(records)
    ds.__iter__ = lambda self: iter(records)
    ds.filter = lambda fn: _mock_dataset([r for r in records if fn(r)])
    ds.select = lambda indices: _mock_dataset([records[i] for i in indices])
    return ds


class TestDS1000Metadata:
    def test_name(self) -> None:
        from agent_evals.datasets.ds1000 import DS1000Adapter

        assert DS1000Adapter().name() == "ds1000"

    def test_task_type(self) -> None:
        from agent_evals.datasets.ds1000 import DS1000Adapter

        assert DS1000Adapter().task_type() == "code_generation"

    def test_domain(self) -> None:
        from agent_evals.datasets.ds1000 import DS1000Adapter

        assert DS1000Adapter().domain() == "library_docs"

    def test_contamination_risk(self) -> None:
        from agent_evals.datasets.ds1000 import DS1000Adapter

        assert DS1000Adapter().contamination_risk() == "moderate"


class TestDS1000ConvertTasks:
    def test_converts_records_to_code_generation_tasks(self, tmp_path: Path) -> None:
        from agent_evals.datasets.ds1000 import DS1000Adapter

        records = [
            _make_ds1000_record(task_id=0),
            _make_ds1000_record(task_id=1),
        ]
        adapter = DS1000Adapter()
        with patch(
            "agent_evals.datasets.ds1000.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            count = adapter.convert_tasks(tmp_path)

        assert count == 2

    def test_generated_yaml_has_correct_schema(self, tmp_path: Path) -> None:
        from agent_evals.datasets.ds1000 import DS1000Adapter

        records = [
            _make_ds1000_record(
                task_id=0,
                prompt="import numpy\ndef solve(): ...",
                canonical_solution="return np.array([1])",
                test="assert len(solve()) == 1",
                entry_point="solve",
            ),
        ]
        adapter = DS1000Adapter()
        with patch(
            "agent_evals.datasets.ds1000.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            adapter.convert_tasks(tmp_path)

        yaml_files = list(tmp_path.glob("*.yaml"))
        assert len(yaml_files) == 1

        task = yaml.safe_load(yaml_files[0].read_text(encoding="utf-8"))
        assert task["task_id"].startswith("ds1000_code_generation_")
        assert task["type"] == "code_generation"
        assert task["domain"] == "library_docs"
        assert "test" in task["metadata"]
        assert "canonical_solution" in task["metadata"]
        assert "entry_point" in task["metadata"]
        assert "forbidden_patterns" in task["metadata"]

    def test_limit_caps_output(self, tmp_path: Path) -> None:
        from agent_evals.datasets.ds1000 import DS1000Adapter

        records = [_make_ds1000_record(task_id=i) for i in range(20)]
        adapter = DS1000Adapter()
        with patch(
            "agent_evals.datasets.ds1000.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            count = adapter.convert_tasks(tmp_path, limit=5)

        assert count == 5


class TestDS1000BuildDocTree:
    def test_builds_doc_tree(self) -> None:
        from agent_evals.datasets.ds1000 import DS1000Adapter

        records = [
            _make_ds1000_record(
                task_id=0,
                docs=[{"title": "numpy.array", "text": "Create an array."}],
            ),
            _make_ds1000_record(
                task_id=1,
                docs=[{"title": "pandas.DataFrame", "text": "2D data structure."}],
            ),
        ]
        adapter = DS1000Adapter()
        with patch(
            "agent_evals.datasets.ds1000.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            doc_tree = adapter.build_doc_tree()

        assert len(doc_tree.files) == 2


class TestDS1000Registration:
    def test_registered(self) -> None:
        from agent_evals.datasets import DATASET_REGISTRY

        import agent_evals.datasets.ds1000  # noqa: F401

        assert "ds1000" in DATASET_REGISTRY
