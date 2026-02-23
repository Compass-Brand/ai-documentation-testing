"""Abstract base class for dataset adapters.

Each adapter knows how to download a specific public dataset,
convert its records into TaskDefinition-compatible YAML files,
and build a DocTree from the dataset's document corpus.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_index.models import DocTree


class DatasetAdapter(ABC):
    """Abstract base for public dataset adapters."""

    @abstractmethod
    def name(self) -> str:
        """Short identifier for this dataset (e.g. 'repliqa')."""
        ...

    @abstractmethod
    def hf_dataset_id(self) -> str | None:
        """HuggingFace dataset ID, or None for non-HF datasets."""
        ...

    @abstractmethod
    def task_type(self) -> str:
        """Primary task type this dataset maps to."""
        ...

    @abstractmethod
    def domain(self) -> str:
        """Documentation domain for generated tasks."""
        ...

    @abstractmethod
    def license(self) -> str:
        """License identifier for the dataset."""
        ...

    @abstractmethod
    def contamination_risk(self) -> str:
        """Return 'low', 'moderate', or 'high'."""
        ...

    @abstractmethod
    def convert_tasks(self, output_dir: Path, limit: int | None = None) -> int:
        """Download dataset and write YAML task files to output_dir.

        Each YAML file must conform to TaskDefinition schema.
        Returns the number of tasks written.
        """
        ...

    @abstractmethod
    def build_doc_tree(self, limit: int | None = None) -> DocTree:
        """Build a DocTree from the dataset's document corpus."""
        ...

    def requires(self) -> list[str]:
        """Extra pip packages needed beyond 'datasets'."""
        return []

    def _generate_task_id(self, task_type: str, index: int) -> str:
        """Generate namespaced task ID: {dataset}_{type}_{index:03d}.

        Hyphens in the dataset name are removed to conform to the
        task ID pattern ``^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*_\\d+$``.
        """
        prefix = self.name().replace("-", "")
        return f"{prefix}_{task_type}_{index:03d}"
