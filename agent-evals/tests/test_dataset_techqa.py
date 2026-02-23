"""Tests for the IBM TechQA dataset adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from agent_evals.datasets.base import DatasetAdapter


# ---------------------------------------------------------------------------
# Mock data helpers
# ---------------------------------------------------------------------------


def _make_techqa_record(
    question_id: str = "Q001",
    question_title: str = "Server fails to start",
    question_text: str = "After upgrading, the server fails with error.",
    document: str = "swg21695432",
    start_offset: int = 100,
    end_offset: int = 200,
    answerable: str = "Y",
    doc_ids: list[str] | None = None,
) -> dict:
    if doc_ids is None:
        doc_ids = [document, "swg21483790", "swg21502837"]
    return {
        "QUESTION_ID": question_id,
        "QUESTION_TITLE": question_title,
        "QUESTION_TEXT": question_text,
        "DOCUMENT": document,
        "START_OFFSET": start_offset,
        "END_OFFSET": end_offset,
        "DOC_IDS": doc_ids,
        "ANSWERABLE": answerable,
    }


def _make_technote(
    doc_id: str = "swg21695432",
    title: str = "Server fails to start after upgrade",
    text: str = "Technote: The server may fail to start. " + ("x" * 200) + "The fix is to clear the cache." + ("x" * 200),
) -> dict:
    return {"_id": doc_id, "title": title, "text": text}


def _mock_dataset(records: list[dict]) -> MagicMock:
    ds = MagicMock()
    ds.__len__ = lambda self: len(records)
    ds.__iter__ = lambda self: iter(records)
    ds.filter = lambda fn: _mock_dataset([r for r in records if fn(r)])
    ds.select = lambda indices: _mock_dataset([records[i] for i in indices])
    return ds


# ---------------------------------------------------------------------------
# Adapter metadata
# ---------------------------------------------------------------------------


class TestTechQAMetadata:
    """Verify adapter metadata methods."""

    def test_adapter_is_dataset_adapter_subclass(self) -> None:
        from agent_evals.datasets.ibm_techqa import IBMTechQAAdapter

        assert issubclass(IBMTechQAAdapter, DatasetAdapter)

    def test_name(self) -> None:
        from agent_evals.datasets.ibm_techqa import IBMTechQAAdapter

        assert IBMTechQAAdapter().name() == "ibm-techqa"

    def test_hf_dataset_id(self) -> None:
        from agent_evals.datasets.ibm_techqa import IBMTechQAAdapter

        assert IBMTechQAAdapter().hf_dataset_id() == "PrimeQA/TechQA"

    def test_task_type(self) -> None:
        from agent_evals.datasets.ibm_techqa import IBMTechQAAdapter

        assert IBMTechQAAdapter().task_type() == "fact_extraction"

    def test_domain(self) -> None:
        from agent_evals.datasets.ibm_techqa import IBMTechQAAdapter

        assert IBMTechQAAdapter().domain() == "technical_qa"

    def test_license(self) -> None:
        from agent_evals.datasets.ibm_techqa import IBMTechQAAdapter

        assert IBMTechQAAdapter().license() == "Apache-2.0"

    def test_contamination_risk(self) -> None:
        from agent_evals.datasets.ibm_techqa import IBMTechQAAdapter

        assert IBMTechQAAdapter().contamination_risk() == "low"


# ---------------------------------------------------------------------------
# convert_tasks
# ---------------------------------------------------------------------------


class TestTechQAConvertTasks:
    """Verify task YAML generation from mocked data."""

    def test_converts_answerable_records_to_fact_extraction(
        self, tmp_path: Path,
    ) -> None:
        from agent_evals.datasets.ibm_techqa import IBMTechQAAdapter

        # Create a document with known answer span
        doc_text = "A" * 100 + "The fix is to clear the cache." + "B" * 100
        qa_records = [
            _make_techqa_record(
                question_id="Q001",
                document="doc001",
                start_offset=100,
                end_offset=130,
                answerable="Y",
            ),
            _make_techqa_record(
                question_id="Q002",
                answerable="N",  # unanswerable, should be skipped
            ),
            _make_techqa_record(
                question_id="Q003",
                document="doc002",
                start_offset=0,
                end_offset=10,
                answerable="Y",
            ),
        ]
        technotes = {
            "doc001": _make_technote("doc001", "Doc 1", doc_text),
            "doc002": _make_technote("doc002", "Doc 2", "Short text."),
        }

        adapter = IBMTechQAAdapter()
        with patch.object(
            adapter, "_load_qa_records", return_value=qa_records,
        ), patch.object(
            adapter, "_load_technotes", return_value=technotes,
        ):
            count = adapter.convert_tasks(tmp_path)

        # Only answerable questions (2 of 3)
        assert count == 2

    def test_generated_yaml_has_correct_schema(self, tmp_path: Path) -> None:
        from agent_evals.datasets.ibm_techqa import IBMTechQAAdapter

        doc_text = "Start. The answer is 42. End."
        qa_records = [
            _make_techqa_record(
                question_id="Q001",
                question_title="What is the answer?",
                question_text="I need to know the answer.",
                document="doc001",
                start_offset=7,
                end_offset=24,
                answerable="Y",
            ),
        ]
        technotes = {
            "doc001": _make_technote("doc001", "Test Doc", doc_text),
        }

        adapter = IBMTechQAAdapter()
        with patch.object(
            adapter, "_load_qa_records", return_value=qa_records,
        ), patch.object(
            adapter, "_load_technotes", return_value=technotes,
        ):
            adapter.convert_tasks(tmp_path)

        yaml_files = list(tmp_path.glob("*.yaml"))
        assert len(yaml_files) == 1

        task = yaml.safe_load(yaml_files[0].read_text(encoding="utf-8"))
        assert task["task_id"].startswith("ibmtechqa_fact_extraction_")
        assert task["type"] == "fact_extraction"
        assert "What is the answer?" in task["question"]
        assert task["domain"] == "technical_qa"
        assert task["difficulty"] in ("easy", "medium", "hard", "edge")
        assert "expected_answer" in task["metadata"]
        assert task["metadata"]["expected_answer"] == "The answer is 42."
        assert isinstance(task["metadata"].get("answer_aliases", []), list)
        assert "source_location" in task["metadata"]

    def test_limit_parameter_caps_output(self, tmp_path: Path) -> None:
        from agent_evals.datasets.ibm_techqa import IBMTechQAAdapter

        doc_text = "x" * 200
        qa_records = [
            _make_techqa_record(
                question_id=f"Q{i:03d}",
                document=f"doc{i:03d}",
                start_offset=0,
                end_offset=10,
                answerable="Y",
            )
            for i in range(20)
        ]
        technotes = {
            f"doc{i:03d}": _make_technote(f"doc{i:03d}", f"Doc {i}", doc_text)
            for i in range(20)
        }

        adapter = IBMTechQAAdapter()
        with patch.object(
            adapter, "_load_qa_records", return_value=qa_records,
        ), patch.object(
            adapter, "_load_technotes", return_value=technotes,
        ):
            count = adapter.convert_tasks(tmp_path, limit=5)

        assert count == 5

    def test_missing_document_skips_record(self, tmp_path: Path) -> None:
        from agent_evals.datasets.ibm_techqa import IBMTechQAAdapter

        qa_records = [
            _make_techqa_record(
                question_id="Q001",
                document="missing_doc",
                answerable="Y",
            ),
        ]
        technotes = {}  # No documents

        adapter = IBMTechQAAdapter()
        with patch.object(
            adapter, "_load_qa_records", return_value=qa_records,
        ), patch.object(
            adapter, "_load_technotes", return_value=technotes,
        ):
            count = adapter.convert_tasks(tmp_path)

        assert count == 0


# ---------------------------------------------------------------------------
# build_doc_tree
# ---------------------------------------------------------------------------


class TestTechQABuildDocTree:
    """Verify DocTree construction from mocked technotes."""

    def test_builds_doc_tree_from_technotes(self) -> None:
        from agent_evals.datasets.ibm_techqa import IBMTechQAAdapter

        technotes = {
            "doc001": _make_technote("doc001", "Doc A", "Content of doc A."),
            "doc002": _make_technote("doc002", "Doc B", "Content of doc B."),
        }

        adapter = IBMTechQAAdapter()
        with patch.object(adapter, "_load_technotes", return_value=technotes):
            doc_tree = adapter.build_doc_tree()

        assert len(doc_tree.files) == 2

    def test_doc_tree_files_have_required_fields(self) -> None:
        from agent_evals.datasets.ibm_techqa import IBMTechQAAdapter

        technotes = {
            "doc001": _make_technote(
                "doc001", "Server Crash Fix", "Steps to resolve server crash issue.",
            ),
        }

        adapter = IBMTechQAAdapter()
        with patch.object(adapter, "_load_technotes", return_value=technotes):
            doc_tree = adapter.build_doc_tree()

        doc = list(doc_tree.files.values())[0]
        assert doc.content == "Steps to resolve server crash issue."
        assert doc.tier in ("required", "recommended", "reference")
        assert doc.section  # non-empty
        assert doc.size_bytes > 0

    def test_limit_parameter_caps_documents(self) -> None:
        from agent_evals.datasets.ibm_techqa import IBMTechQAAdapter

        technotes = {
            f"doc{i:03d}": _make_technote(f"doc{i:03d}", f"Doc {i}", f"Content {i}.")
            for i in range(20)
        }

        adapter = IBMTechQAAdapter()
        with patch.object(adapter, "_load_technotes", return_value=technotes):
            doc_tree = adapter.build_doc_tree(limit=5)

        assert len(doc_tree.files) <= 5


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


class TestTechQARegistration:
    def test_registered_in_dataset_registry(self) -> None:
        from agent_evals.datasets import DATASET_REGISTRY

        import agent_evals.datasets.ibm_techqa  # noqa: F401

        assert "ibm-techqa" in DATASET_REGISTRY
