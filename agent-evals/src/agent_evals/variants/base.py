"""Abstract base class and metadata model for index variants.

Every index variant must subclass ``IndexVariant`` and implement at minimum
the ``metadata()`` and ``render()`` methods.  Optional hooks ``setup()`` and
``teardown()`` are available for pre-/post-processing around render.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from agent_index.models import DocTree


class VariantMetadata(BaseModel):
    """Identity and classification data for a single index variant.

    Attributes:
        name: Human-readable unique identifier for the variant.
        axis: Evaluation axis this variant belongs to (0-10, 0 = baseline).
        category: Broad grouping label (e.g. "structure", "ordering").
        description: Short prose description of what the variant does.
        token_estimate: Estimated output token count for a typical render.
    """

    name: str
    axis: int = Field(ge=0, le=10)
    category: str
    description: str
    token_estimate: int = Field(default=0, ge=0)


class IndexVariant(ABC):
    """Abstract base class that every index variant must implement.

    Subclasses *must* override ``metadata`` and ``render``.  The optional
    ``setup`` and ``teardown`` hooks default to no-ops.
    """

    @abstractmethod
    def metadata(self) -> VariantMetadata:
        """Return variant identity and axis membership.

        Returns:
            A ``VariantMetadata`` instance describing this variant.
        """
        ...

    @abstractmethod
    def render(self, doc_tree: DocTree) -> str:
        """Generate the full index content from a documentation tree.

        Args:
            doc_tree: Parsed documentation tree to render.

        Returns:
            The complete index content as a string.
        """
        ...

    def setup(self, doc_tree: DocTree) -> None:  # noqa: B027
        """Optional: pre-processing before render.

        Args:
            doc_tree: Parsed documentation tree available for inspection.
        """

    def teardown(self) -> None:  # noqa: B027
        """Optional: cleanup after all tasks complete."""
