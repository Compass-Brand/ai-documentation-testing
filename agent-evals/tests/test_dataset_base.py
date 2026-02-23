"""Tests for the dataset adapter ABC, registry, and auto-discovery."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from agent_index.models import DocFile, DocTree


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_doc_tree() -> DocTree:
    """Create a minimal DocTree for testing."""
    return DocTree(
        files={
            "doc.md": DocFile(
                rel_path="doc.md",
                content="Test doc",
                size_bytes=8,
                token_count=2,
                tier="required",
                section="test",
            ),
        },
        source="test",
        total_tokens=2,
        scanned_at="2025-01-01T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# DatasetAdapter ABC contract tests
# ---------------------------------------------------------------------------


class TestDatasetAdapterABC:
    """Verify the DatasetAdapter ABC enforces its contract."""

    def test_cannot_instantiate_abstract_class(self) -> None:
        """DatasetAdapter cannot be instantiated directly."""
        from agent_evals.datasets.base import DatasetAdapter

        with pytest.raises(TypeError):
            DatasetAdapter()  # type: ignore[abstract]

    def test_concrete_adapter_must_implement_all_methods(self) -> None:
        """A subclass missing abstract methods cannot be instantiated."""
        from agent_evals.datasets.base import DatasetAdapter

        class IncompleteAdapter(DatasetAdapter):
            def name(self) -> str:
                return "incomplete"

        with pytest.raises(TypeError):
            IncompleteAdapter()  # type: ignore[abstract]

    def test_concrete_adapter_with_all_methods(self) -> None:
        """A fully implemented subclass can be instantiated."""
        from agent_evals.datasets.base import DatasetAdapter

        class FullAdapter(DatasetAdapter):
            def name(self) -> str:
                return "full"

            def hf_dataset_id(self) -> str | None:
                return "org/dataset"

            def task_type(self) -> str:
                return "retrieval"

            def domain(self) -> str:
                return "library_docs"

            def license(self) -> str:
                return "MIT"

            def contamination_risk(self) -> str:
                return "low"

            def convert_tasks(self, output_dir: Path, limit: int | None = None) -> int:
                return 0

            def build_doc_tree(self, limit: int | None = None) -> DocTree:
                return _make_minimal_doc_tree()

        adapter = FullAdapter()
        assert adapter.name() == "full"
        assert adapter.hf_dataset_id() == "org/dataset"
        assert adapter.task_type() == "retrieval"
        assert adapter.domain() == "library_docs"
        assert adapter.license() == "MIT"
        assert adapter.contamination_risk() == "low"

    def test_generate_task_id_helper(self) -> None:
        """The _generate_task_id helper produces namespaced IDs."""
        from agent_evals.datasets.base import DatasetAdapter

        class TestAdapter(DatasetAdapter):
            def name(self) -> str:
                return "testds"

            def hf_dataset_id(self) -> str | None:
                return None

            def task_type(self) -> str:
                return "retrieval"

            def domain(self) -> str:
                return "library_docs"

            def license(self) -> str:
                return "MIT"

            def contamination_risk(self) -> str:
                return "low"

            def convert_tasks(self, output_dir: Path, limit: int | None = None) -> int:
                return 0

            def build_doc_tree(self, limit: int | None = None) -> DocTree:
                return _make_minimal_doc_tree()

        adapter = TestAdapter()
        assert adapter._generate_task_id("retrieval", 1) == "testds_retrieval_001"
        assert adapter._generate_task_id("negative", 42) == "testds_negative_042"

    def test_requires_returns_empty_list_by_default(self) -> None:
        """The default requires() returns an empty list."""
        from agent_evals.datasets.base import DatasetAdapter

        class MinimalAdapter(DatasetAdapter):
            def name(self) -> str:
                return "minimal"

            def hf_dataset_id(self) -> str | None:
                return None

            def task_type(self) -> str:
                return "retrieval"

            def domain(self) -> str:
                return "library_docs"

            def license(self) -> str:
                return "MIT"

            def contamination_risk(self) -> str:
                return "low"

            def convert_tasks(self, output_dir: Path, limit: int | None = None) -> int:
                return 0

            def build_doc_tree(self, limit: int | None = None) -> DocTree:
                return _make_minimal_doc_tree()

        assert MinimalAdapter().requires() == []


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestDatasetRegistry:
    """Tests for dataset adapter registration and discovery."""

    def test_register_dataset_adds_to_registry(self) -> None:
        """@register_dataset adds the adapter class to DATASET_REGISTRY."""
        from agent_evals.datasets import DATASET_REGISTRY, register_dataset
        from agent_evals.datasets.base import DatasetAdapter

        initial_count = len(DATASET_REGISTRY)

        @register_dataset
        class DummyAdapter(DatasetAdapter):
            def name(self) -> str:
                return "dummy_test"

            def hf_dataset_id(self) -> str | None:
                return None

            def task_type(self) -> str:
                return "retrieval"

            def domain(self) -> str:
                return "library_docs"

            def license(self) -> str:
                return "MIT"

            def contamination_risk(self) -> str:
                return "low"

            def convert_tasks(self, output_dir: Path, limit: int | None = None) -> int:
                return 0

            def build_doc_tree(self, limit: int | None = None) -> DocTree:
                return _make_minimal_doc_tree()

        assert "dummy_test" in DATASET_REGISTRY
        assert DATASET_REGISTRY["dummy_test"] is DummyAdapter

        # Cleanup
        del DATASET_REGISTRY["dummy_test"]

    def test_get_adapter_returns_instance(self) -> None:
        """get_adapter returns an instance of the registered adapter."""
        from agent_evals.datasets import DATASET_REGISTRY, get_adapter, register_dataset
        from agent_evals.datasets.base import DatasetAdapter

        @register_dataset
        class GetTestAdapter(DatasetAdapter):
            def name(self) -> str:
                return "get_test"

            def hf_dataset_id(self) -> str | None:
                return None

            def task_type(self) -> str:
                return "retrieval"

            def domain(self) -> str:
                return "library_docs"

            def license(self) -> str:
                return "MIT"

            def contamination_risk(self) -> str:
                return "low"

            def convert_tasks(self, output_dir: Path, limit: int | None = None) -> int:
                return 0

            def build_doc_tree(self, limit: int | None = None) -> DocTree:
                return _make_minimal_doc_tree()

        adapter = get_adapter("get_test")
        assert isinstance(adapter, GetTestAdapter)

        # Cleanup
        del DATASET_REGISTRY["get_test"]

    def test_get_adapter_raises_for_unknown(self) -> None:
        """get_adapter raises KeyError for unregistered names."""
        from agent_evals.datasets import get_adapter

        with pytest.raises(KeyError, match="nonexistent"):
            get_adapter("nonexistent")

    def test_list_available_returns_dicts(self) -> None:
        """list_available returns a list of dicts with name and metadata."""
        from agent_evals.datasets import DATASET_REGISTRY, list_available, register_dataset
        from agent_evals.datasets.base import DatasetAdapter

        @register_dataset
        class ListTestAdapter(DatasetAdapter):
            def name(self) -> str:
                return "list_test"

            def hf_dataset_id(self) -> str | None:
                return "org/ds"

            def task_type(self) -> str:
                return "negative"

            def domain(self) -> str:
                return "synthetic_docs"

            def license(self) -> str:
                return "CC-BY-4.0"

            def contamination_risk(self) -> str:
                return "low"

            def convert_tasks(self, output_dir: Path, limit: int | None = None) -> int:
                return 0

            def build_doc_tree(self, limit: int | None = None) -> DocTree:
                return _make_minimal_doc_tree()

        available = list_available()
        entry = [e for e in available if e["name"] == "list_test"]
        assert len(entry) == 1
        assert entry[0]["task_type"] == "negative"
        assert entry[0]["contamination_risk"] == "low"
        assert entry[0]["license"] == "CC-BY-4.0"

        # Cleanup
        del DATASET_REGISTRY["list_test"]
