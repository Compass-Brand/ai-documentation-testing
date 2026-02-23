"""Tests for the AmbigQA dataset adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml


def _make_ambigqa_record(
    id: str = "q001",
    question: str = "When was the first Super Bowl?",
    annotations: dict | None = None,
) -> dict:
    if annotations is None:
        annotations = {
            "type": "multipleQAs",
            "qaPairs": [
                {"question": "When was Super Bowl I?", "answer": ["1967"]},
                {"question": "When was the first modern Super Bowl?", "answer": ["1967"]},
            ],
        }
    return {"id": id, "question": question, "annotations": annotations}


def _mock_dataset(records: list[dict]) -> MagicMock:
    ds = MagicMock()
    ds.__len__ = lambda self: len(records)
    ds.__iter__ = lambda self: iter(records)
    ds.select = lambda indices: _mock_dataset([records[i] for i in indices])
    return ds


class TestAmbigQAMetadata:
    def test_name(self) -> None:
        from agent_evals.datasets.ambigqa import AmbigQAAdapter
        assert AmbigQAAdapter().name() == "ambigqa"

    def test_task_type(self) -> None:
        from agent_evals.datasets.ambigqa import AmbigQAAdapter
        assert AmbigQAAdapter().task_type() == "disambiguation"

    def test_domain(self) -> None:
        from agent_evals.datasets.ambigqa import AmbigQAAdapter
        assert AmbigQAAdapter().domain() == "general_knowledge"

    def test_contamination_risk(self) -> None:
        from agent_evals.datasets.ambigqa import AmbigQAAdapter
        assert AmbigQAAdapter().contamination_risk() == "high"


class TestAmbigQAConvertTasks:
    def test_converts_records_to_disambiguation_tasks(self, tmp_path: Path) -> None:
        from agent_evals.datasets.ambigqa import AmbigQAAdapter

        records = [_make_ambigqa_record(), _make_ambigqa_record(id="q002")]
        adapter = AmbigQAAdapter()
        with patch(
            "agent_evals.datasets.ambigqa.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            count = adapter.convert_tasks(tmp_path)
        assert count == 2

    def test_generated_yaml_has_correct_schema(self, tmp_path: Path) -> None:
        from agent_evals.datasets.ambigqa import AmbigQAAdapter

        records = [_make_ambigqa_record()]
        adapter = AmbigQAAdapter()
        with patch(
            "agent_evals.datasets.ambigqa.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            adapter.convert_tasks(tmp_path)

        task = yaml.safe_load(list(tmp_path.glob("*.yaml"))[0].read_text())
        assert task["type"] == "disambiguation"
        assert task["domain"] == "general_knowledge"
        assert "interpretations" in task["metadata"]
        assert "expected_interpretation" in task["metadata"]

    def test_limit_caps_output(self, tmp_path: Path) -> None:
        from agent_evals.datasets.ambigqa import AmbigQAAdapter

        records = [_make_ambigqa_record(id=f"q{i:03d}") for i in range(20)]
        adapter = AmbigQAAdapter()
        with patch(
            "agent_evals.datasets.ambigqa.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            count = adapter.convert_tasks(tmp_path, limit=5)
        assert count == 5


class TestAmbigQARegistration:
    def test_registered(self) -> None:
        from agent_evals.datasets import DATASET_REGISTRY
        import agent_evals.datasets.ambigqa  # noqa: F401
        assert "ambigqa" in DATASET_REGISTRY
