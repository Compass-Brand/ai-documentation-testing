"""Tests for the RepLiQA dataset adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from agent_evals.datasets.base import DatasetAdapter


# ---------------------------------------------------------------------------
# Mock HF record helpers
# ---------------------------------------------------------------------------

def _make_repliqa_record(
    doc_id: str = "abc12345",
    topic: str = "Small and Medium Enterprises",
    question: str = "What is the revenue?",
    answer: str = "UNANSWERABLE",
    long_answer: str = "NA",
    document_extracted: str = "WeTech Solutions was founded in 2020.",
) -> dict[str, str]:
    return {
        "document_id": doc_id,
        "document_topic": topic,
        "document_path": f"pdfs/{doc_id}.pdf",
        "document_extracted": document_extracted,
        "question_id": f"{doc_id}-q1",
        "question": question,
        "answer": answer,
        "long_answer": long_answer,
    }


def _mock_dataset(records: list[dict]) -> MagicMock:
    """Build a MagicMock that behaves like a HF Dataset."""
    ds = MagicMock()
    ds.__len__ = lambda self: len(records)
    ds.__iter__ = lambda self: iter(records)
    ds.filter = lambda fn: _mock_dataset([r for r in records if fn(r)])
    ds.select = lambda indices: _mock_dataset([records[i] for i in indices])
    return ds


# ---------------------------------------------------------------------------
# Adapter metadata
# ---------------------------------------------------------------------------


class TestRepliQAMetadata:
    """Verify adapter metadata methods."""

    def test_adapter_is_dataset_adapter_subclass(self) -> None:
        from agent_evals.datasets.repliqa import RepliQAAdapter

        assert issubclass(RepliQAAdapter, DatasetAdapter)

    def test_name(self) -> None:
        from agent_evals.datasets.repliqa import RepliQAAdapter

        assert RepliQAAdapter().name() == "repliqa"

    def test_hf_dataset_id(self) -> None:
        from agent_evals.datasets.repliqa import RepliQAAdapter

        assert RepliQAAdapter().hf_dataset_id() == "ServiceNow/repliqa"

    def test_task_type(self) -> None:
        from agent_evals.datasets.repliqa import RepliQAAdapter

        assert RepliQAAdapter().task_type() == "negative"

    def test_domain(self) -> None:
        from agent_evals.datasets.repliqa import RepliQAAdapter

        assert RepliQAAdapter().domain() == "synthetic_docs"

    def test_license(self) -> None:
        from agent_evals.datasets.repliqa import RepliQAAdapter

        assert RepliQAAdapter().license() == "CC-BY-4.0"

    def test_contamination_risk(self) -> None:
        from agent_evals.datasets.repliqa import RepliQAAdapter

        assert RepliQAAdapter().contamination_risk() == "low"


# ---------------------------------------------------------------------------
# convert_tasks
# ---------------------------------------------------------------------------


class TestRepliQAConvertTasks:
    """Verify task YAML generation from mocked HF data."""

    def test_converts_unanswerable_records_to_negative_tasks(
        self, tmp_path: Path,
    ) -> None:
        from agent_evals.datasets.repliqa import RepliQAAdapter

        records = [
            _make_repliqa_record(
                doc_id="doc001",
                question="What is the revenue?",
                answer="UNANSWERABLE",
                long_answer="NA",
            ),
            _make_repliqa_record(
                doc_id="doc002",
                question="Who founded it?",
                answer="Jane Smith founded the company.",
                long_answer="Jane Smith founded the company in 2019.",
            ),
            _make_repliqa_record(
                doc_id="doc003",
                question="What is the budget?",
                answer="UNANSWERABLE",
                long_answer="NA",
            ),
        ]
        mock_ds = _mock_dataset(records)

        adapter = RepliQAAdapter()
        with patch(
            "agent_evals.datasets.repliqa.load_hf_dataset",
            return_value=mock_ds,
        ):
            count = adapter.convert_tasks(tmp_path)

        # Only unanswerable records (2 of 3)
        assert count == 2

    def test_generated_yaml_has_correct_schema(self, tmp_path: Path) -> None:
        from agent_evals.datasets.repliqa import RepliQAAdapter

        records = [
            _make_repliqa_record(
                doc_id="doc001",
                question="What is the revenue?",
                answer="UNANSWERABLE",
                long_answer="NA",
                document_extracted="WeTech Solutions: A case study.",
            ),
        ]
        mock_ds = _mock_dataset(records)

        adapter = RepliQAAdapter()
        with patch(
            "agent_evals.datasets.repliqa.load_hf_dataset",
            return_value=mock_ds,
        ):
            adapter.convert_tasks(tmp_path)

        yaml_files = list(tmp_path.glob("*.yaml"))
        assert len(yaml_files) == 1

        task = yaml.safe_load(yaml_files[0].read_text(encoding="utf-8"))
        assert task["task_id"].startswith("repliqa_negative_")
        assert task["type"] == "negative"
        assert task["question"] == "What is the revenue?"
        assert task["domain"] == "synthetic_docs"
        assert task["difficulty"] in ("easy", "medium", "hard", "edge")
        assert isinstance(task["tags"], list)
        assert task["metadata"]["expected_answer"] == "unanswerable"
        assert "nearest_doc" in task["metadata"]

    def test_limit_parameter_caps_output(self, tmp_path: Path) -> None:
        from agent_evals.datasets.repliqa import RepliQAAdapter

        records = [
            _make_repliqa_record(doc_id=f"doc{i:03d}", answer="UNANSWERABLE")
            for i in range(20)
        ]
        mock_ds = _mock_dataset(records)

        adapter = RepliQAAdapter()
        with patch(
            "agent_evals.datasets.repliqa.load_hf_dataset",
            return_value=mock_ds,
        ):
            count = adapter.convert_tasks(tmp_path, limit=5)

        assert count == 5
        assert len(list(tmp_path.glob("*.yaml"))) == 5

    def test_task_ids_are_sequential(self, tmp_path: Path) -> None:
        from agent_evals.datasets.repliqa import RepliQAAdapter

        records = [
            _make_repliqa_record(doc_id=f"doc{i:03d}", answer="UNANSWERABLE")
            for i in range(3)
        ]
        mock_ds = _mock_dataset(records)

        adapter = RepliQAAdapter()
        with patch(
            "agent_evals.datasets.repliqa.load_hf_dataset",
            return_value=mock_ds,
        ):
            adapter.convert_tasks(tmp_path)

        yaml_files = sorted(tmp_path.glob("*.yaml"))
        ids = []
        for f in yaml_files:
            task = yaml.safe_load(f.read_text(encoding="utf-8"))
            ids.append(task["task_id"])
        assert ids == [
            "repliqa_negative_000",
            "repliqa_negative_001",
            "repliqa_negative_002",
        ]


# ---------------------------------------------------------------------------
# build_doc_tree
# ---------------------------------------------------------------------------


class TestRepliQABuildDocTree:
    """Verify DocTree construction from mocked HF data."""

    def test_builds_doc_tree_with_unique_documents(self) -> None:
        from agent_evals.datasets.repliqa import RepliQAAdapter

        # Same doc_id appears twice (as in the real dataset: 5 questions per doc)
        records = [
            _make_repliqa_record(
                doc_id="doc001",
                question="Q1?",
                document_extracted="Document one content.",
            ),
            _make_repliqa_record(
                doc_id="doc001",
                question="Q2?",
                document_extracted="Document one content.",
            ),
            _make_repliqa_record(
                doc_id="doc002",
                question="Q3?",
                document_extracted="Document two content.",
            ),
        ]
        mock_ds = _mock_dataset(records)

        adapter = RepliQAAdapter()
        with patch(
            "agent_evals.datasets.repliqa.load_hf_dataset",
            return_value=mock_ds,
        ):
            doc_tree = adapter.build_doc_tree()

        # 2 unique documents, not 3
        assert len(doc_tree.files) == 2

    def test_doc_tree_files_have_required_fields(self) -> None:
        from agent_evals.datasets.repliqa import RepliQAAdapter

        records = [
            _make_repliqa_record(
                doc_id="doc001",
                topic="News Stories",
                document_extracted="Breaking news: Market trends shift dramatically.",
            ),
        ]
        mock_ds = _mock_dataset(records)

        adapter = RepliQAAdapter()
        with patch(
            "agent_evals.datasets.repliqa.load_hf_dataset",
            return_value=mock_ds,
        ):
            doc_tree = adapter.build_doc_tree()

        assert len(doc_tree.files) == 1
        doc = list(doc_tree.files.values())[0]
        assert doc.content == "Breaking news: Market trends shift dramatically."
        assert doc.tier in ("required", "recommended", "reference")
        assert doc.section  # non-empty
        assert doc.size_bytes > 0

    def test_limit_parameter_caps_documents(self) -> None:
        from agent_evals.datasets.repliqa import RepliQAAdapter

        records = [
            _make_repliqa_record(doc_id=f"doc{i:03d}")
            for i in range(10)
        ]
        mock_ds = _mock_dataset(records)

        adapter = RepliQAAdapter()
        with patch(
            "agent_evals.datasets.repliqa.load_hf_dataset",
            return_value=mock_ds,
        ):
            doc_tree = adapter.build_doc_tree(limit=3)

        assert len(doc_tree.files) <= 3


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


class TestRepliQARegistration:
    """Verify the adapter registers itself."""

    def test_registered_in_dataset_registry(self) -> None:
        from agent_evals.datasets import DATASET_REGISTRY

        # Import the module to trigger registration
        import agent_evals.datasets.repliqa  # noqa: F401

        assert "repliqa" in DATASET_REGISTRY
