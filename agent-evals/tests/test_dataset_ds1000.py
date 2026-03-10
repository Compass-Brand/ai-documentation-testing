"""Tests for the DS-1000 dataset adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from agent_evals.datasets.base import DatasetAdapter


def _make_ds1000_record(
    prompt: str = "import numpy as np\ndef solve():\n    # ",
    reference_code: str = "return np.array([1,2,3])",
    code_context: str = "import numpy as np",
    library: str = "numpy",
    docs: list[dict] | None = None,
) -> dict:
    if docs is None:
        docs = [{"title": "numpy.array", "text": "Create an array.", "function": "numpy.array"}]
    return {
        "prompt": prompt,
        "reference_code": reference_code,
        "code_context": code_context,
        "metadata": {
            "problem_id": 0,
            "library_problem_id": 0,
            "library": library,
            "test_case_cnt": 1,
            "perturbation_type": "Origin",
            "perturbation_origin_id": 0,
        },
        "docs": docs,
    }


def _mock_dataset(records: list[dict]) -> MagicMock:
    ds = MagicMock()
    ds.__len__ = lambda self: len(records)
    ds.__iter__ = lambda self: iter(records)
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
            _make_ds1000_record(),
            _make_ds1000_record(library="pandas"),
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
                prompt="import numpy\ndef solve(): ...",
                reference_code="return np.array([1])",
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
        assert "forbidden_patterns" in task["metadata"]

    def test_limit_caps_output(self, tmp_path: Path) -> None:
        from agent_evals.datasets.ds1000 import DS1000Adapter

        records = [_make_ds1000_record() for _ in range(20)]
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
                docs=[{"title": "numpy.array", "text": "Create an array.", "function": "numpy.array"}],
            ),
            _make_ds1000_record(
                docs=[{"title": "pandas.DataFrame", "text": "2D data structure.", "function": "pandas.DataFrame"}],
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
