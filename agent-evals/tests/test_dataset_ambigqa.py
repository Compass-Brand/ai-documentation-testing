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
        # Real HF schema: type/answer/qaPairs are lists; qaPairs contains
        # one container dict with parallel question[] and answer[][] arrays.
        annotations = {
            "type": ["multipleQAs"],
            "answer": [[]],
            "qaPairs": [
                {
                    "question": [
                        "When was Super Bowl I?",
                        "When was the first modern Super Bowl?",
                    ],
                    "answer": [["1967"], ["1967"]],
                },
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


class TestAmbigQASingleAnswerFiltering:
    """Bug #179: singleAnswer records have 1 interpretation, trivially scoring 1.0."""

    def test_single_answer_records_are_skipped(self, tmp_path: Path) -> None:
        """singleAnswer records should be filtered out of disambiguation tasks."""
        from agent_evals.datasets.ambigqa import AmbigQAAdapter

        single_answer_record = _make_ambigqa_record(
            id="single01",
            question="When did the US enter WW2?",
            annotations={
                "type": ["singleAnswer"],
                "answer": [["1941"]],
                "qaPairs": [{}],
            },
        )
        multi_qa_record = _make_ambigqa_record(id="multi01")

        records = [single_answer_record, multi_qa_record]
        adapter = AmbigQAAdapter()
        with patch(
            "agent_evals.datasets.ambigqa.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            count = adapter.convert_tasks(tmp_path)

        # Only the multipleQAs record should be emitted
        assert count == 1
        task = yaml.safe_load(list(tmp_path.glob("*.yaml"))[0].read_text())
        assert len(task["metadata"]["interpretations"]) >= 2

    def test_only_single_answer_records_produces_zero_tasks(self, tmp_path: Path) -> None:
        """Dataset with only singleAnswer records should produce 0 tasks."""
        from agent_evals.datasets.ambigqa import AmbigQAAdapter

        records = [
            _make_ambigqa_record(
                id="s1",
                annotations={
                    "type": ["singleAnswer"],
                    "answer": [["1941"]],
                    "qaPairs": [{}],
                },
            ),
            _make_ambigqa_record(
                id="s2",
                annotations={
                    "type": ["singleAnswer"],
                    "answer": [["1776"]],
                    "qaPairs": [{}],
                },
            ),
        ]
        adapter = AmbigQAAdapter()
        with patch(
            "agent_evals.datasets.ambigqa.load_hf_dataset",
            return_value=_mock_dataset(records),
        ):
            count = adapter.convert_tasks(tmp_path)

        assert count == 0


class TestAmbigQARegistration:
    def test_registered(self) -> None:
        import agent_evals.datasets.ambigqa  # noqa: F401
        from agent_evals.datasets import DATASET_REGISTRY
        assert "ambigqa" in DATASET_REGISTRY
