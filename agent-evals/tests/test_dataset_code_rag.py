"""Tests for the CodeRAG-Bench dataset adapter."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from agent_evals.datasets.base import DatasetAdapter


# ---------------------------------------------------------------------------
# Mock HF record helpers
# ---------------------------------------------------------------------------


def _make_humaneval_record(
    task_id: str = "HumanEval/0",
    prompt: str = "def has_close(numbers): ...",
    entry_point: str = "has_close",
    docs: list[dict] | None = None,
) -> dict:
    if docs is None:
        docs = [{"title": "math.isclose", "text": "Return True if values are close."}]
    return {
        "task_id": task_id,
        "prompt": prompt,
        "canonical_solution": "return True",
        "test": "assert has_close([1,2]) == True",
        "entry_point": entry_point,
        "docs": docs,
    }


def _make_lib_doc_record(
    doc_id: str = "numpy.array",
    doc_content: str = "numpy.array: Create an array.",
) -> dict:
    return {"doc_id": doc_id, "doc_content": doc_content}


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


class TestCodeRAGMetadata:
    """Verify adapter metadata methods."""

    def test_adapter_is_dataset_adapter_subclass(self) -> None:
        from agent_evals.datasets.code_rag_bench import CodeRAGBenchAdapter

        assert issubclass(CodeRAGBenchAdapter, DatasetAdapter)

    def test_name(self) -> None:
        from agent_evals.datasets.code_rag_bench import CodeRAGBenchAdapter

        assert CodeRAGBenchAdapter().name() == "code-rag-bench"

    def test_hf_dataset_id(self) -> None:
        from agent_evals.datasets.code_rag_bench import CodeRAGBenchAdapter

        assert CodeRAGBenchAdapter().hf_dataset_id() == "code-rag-bench/humaneval"

    def test_task_type(self) -> None:
        from agent_evals.datasets.code_rag_bench import CodeRAGBenchAdapter

        assert CodeRAGBenchAdapter().task_type() == "retrieval"

    def test_domain(self) -> None:
        from agent_evals.datasets.code_rag_bench import CodeRAGBenchAdapter

        assert CodeRAGBenchAdapter().domain() == "library_docs"

    def test_license(self) -> None:
        from agent_evals.datasets.code_rag_bench import CodeRAGBenchAdapter

        assert CodeRAGBenchAdapter().license() == "CC-BY-SA-4.0"

    def test_contamination_risk(self) -> None:
        from agent_evals.datasets.code_rag_bench import CodeRAGBenchAdapter

        assert CodeRAGBenchAdapter().contamination_risk() == "moderate"


# ---------------------------------------------------------------------------
# convert_tasks
# ---------------------------------------------------------------------------


class TestCodeRAGConvertTasks:
    """Verify task YAML generation from mocked HF data."""

    def test_converts_records_to_retrieval_tasks(self, tmp_path: Path) -> None:
        from agent_evals.datasets.code_rag_bench import CodeRAGBenchAdapter

        records = [
            _make_humaneval_record(
                task_id="HumanEval/0",
                prompt="def has_close(numbers): ...",
                docs=[
                    {"title": "math.isclose", "text": "Return True if close."},
                    {"title": "numpy.allclose", "text": "Check array closeness."},
                ],
            ),
            _make_humaneval_record(
                task_id="HumanEval/1",
                prompt="def sort_list(lst): ...",
                docs=[{"title": "list.sort", "text": "Sort a list in place."}],
            ),
        ]
        mock_ds = _mock_dataset(records)

        adapter = CodeRAGBenchAdapter()
        with patch(
            "agent_evals.datasets.code_rag_bench.load_hf_dataset",
            return_value=mock_ds,
        ):
            count = adapter.convert_tasks(tmp_path)

        assert count == 2

    def test_generated_yaml_has_correct_schema(self, tmp_path: Path) -> None:
        from agent_evals.datasets.code_rag_bench import CodeRAGBenchAdapter

        records = [
            _make_humaneval_record(
                task_id="HumanEval/0",
                prompt="def has_close(numbers, threshold): ...",
                docs=[{"title": "math.isclose", "text": "Return True if close."}],
            ),
        ]
        mock_ds = _mock_dataset(records)

        adapter = CodeRAGBenchAdapter()
        with patch(
            "agent_evals.datasets.code_rag_bench.load_hf_dataset",
            return_value=mock_ds,
        ):
            adapter.convert_tasks(tmp_path)

        yaml_files = list(tmp_path.glob("*.yaml"))
        assert len(yaml_files) == 1

        task = yaml.safe_load(yaml_files[0].read_text(encoding="utf-8"))
        assert task["task_id"].startswith("coderagbench_retrieval_")
        assert task["type"] == "retrieval"
        assert "has_close" in task["question"]
        assert task["domain"] == "library_docs"
        assert task["difficulty"] in ("easy", "medium", "hard", "edge")
        assert isinstance(task["metadata"]["expected_files"], list)
        assert len(task["metadata"]["expected_files"]) >= 1

    def test_records_without_docs_are_skipped(self, tmp_path: Path) -> None:
        from agent_evals.datasets.code_rag_bench import CodeRAGBenchAdapter

        records = [
            _make_humaneval_record(task_id="HumanEval/0", docs=[]),
            _make_humaneval_record(
                task_id="HumanEval/1",
                docs=[{"title": "math.isclose", "text": "Close check."}],
            ),
        ]
        mock_ds = _mock_dataset(records)

        adapter = CodeRAGBenchAdapter()
        with patch(
            "agent_evals.datasets.code_rag_bench.load_hf_dataset",
            return_value=mock_ds,
        ):
            count = adapter.convert_tasks(tmp_path)

        assert count == 1

    def test_limit_parameter_caps_output(self, tmp_path: Path) -> None:
        from agent_evals.datasets.code_rag_bench import CodeRAGBenchAdapter

        records = [
            _make_humaneval_record(task_id=f"HumanEval/{i}")
            for i in range(20)
        ]
        mock_ds = _mock_dataset(records)

        adapter = CodeRAGBenchAdapter()
        with patch(
            "agent_evals.datasets.code_rag_bench.load_hf_dataset",
            return_value=mock_ds,
        ):
            count = adapter.convert_tasks(tmp_path, limit=5)

        assert count == 5


# ---------------------------------------------------------------------------
# build_doc_tree
# ---------------------------------------------------------------------------


class TestCodeRAGBuildDocTree:
    """Verify DocTree construction from mocked library-documentation corpus."""

    def test_builds_doc_tree_from_library_docs(self) -> None:
        from agent_evals.datasets.code_rag_bench import CodeRAGBenchAdapter

        lib_records = [
            _make_lib_doc_record("numpy.array", "Create an array object."),
            _make_lib_doc_record("pandas.dataframe", "Two-dimensional data structure."),
        ]
        mock_ds = _mock_dataset(lib_records)

        adapter = CodeRAGBenchAdapter()
        with patch(
            "agent_evals.datasets.code_rag_bench.load_hf_dataset",
            return_value=mock_ds,
        ):
            doc_tree = adapter.build_doc_tree()

        assert len(doc_tree.files) == 2

    def test_doc_tree_files_have_required_fields(self) -> None:
        from agent_evals.datasets.code_rag_bench import CodeRAGBenchAdapter

        lib_records = [
            _make_lib_doc_record(
                "numpy.array",
                "numpy.array: Create an array from data. Supports dtype parameter.",
            ),
        ]
        mock_ds = _mock_dataset(lib_records)

        adapter = CodeRAGBenchAdapter()
        with patch(
            "agent_evals.datasets.code_rag_bench.load_hf_dataset",
            return_value=mock_ds,
        ):
            doc_tree = adapter.build_doc_tree()

        doc = list(doc_tree.files.values())[0]
        assert doc.content.startswith("numpy.array")
        assert doc.tier in ("required", "recommended", "reference")
        assert doc.section  # non-empty
        assert doc.size_bytes > 0

    def test_limit_parameter_caps_documents(self) -> None:
        from agent_evals.datasets.code_rag_bench import CodeRAGBenchAdapter

        lib_records = [
            _make_lib_doc_record(f"lib.func{i}", f"Function {i} docs.")
            for i in range(20)
        ]
        mock_ds = _mock_dataset(lib_records)

        adapter = CodeRAGBenchAdapter()
        with patch(
            "agent_evals.datasets.code_rag_bench.load_hf_dataset",
            return_value=mock_ds,
        ):
            doc_tree = adapter.build_doc_tree(limit=5)

        assert len(doc_tree.files) <= 5


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


class TestCodeRAGRegistration:
    def test_registered_in_dataset_registry(self) -> None:
        from agent_evals.datasets import DATASET_REGISTRY

        import agent_evals.datasets.code_rag_bench  # noqa: F401

        assert "code-rag-bench" in DATASET_REGISTRY
