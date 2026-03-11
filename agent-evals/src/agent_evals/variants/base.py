"""Abstract base class and metadata model for index variants.

Every index variant must subclass ``IndexVariant`` and implement at minimum
the ``metadata()`` and ``render()`` methods.  Optional hooks ``setup()`` and
``teardown()`` are available for pre-/post-processing around render.

The ``PipelineRole`` enum and ``pipeline_role()``, ``pre_render()``,
``post_render()`` methods support composable pipeline rendering in
``CompositeVariant`` so that multiple axes produce ONE coherent output
instead of N concatenated independent renders.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from agent_index.models import DocTree


class PipelineRole(Enum):
    """Role a variant plays in a composite rendering pipeline.

    - ``PRIMARY``: Produces the main rendered output (default).
    - ``PRE_RENDER``: Modifies the DocTree before the primary renders.
    - ``POST_RENDER``: Transforms the rendered text after the primary.
    """

    PRIMARY = "primary"
    PRE_RENDER = "pre_render"
    POST_RENDER = "post_render"


# Maps variant categories to their default pipeline role.
# Categories not listed here default to PRIMARY.
_ROLE_BY_CATEGORY: dict[str, PipelineRole] = {
    # PRIMARY -- produces the main rendered output
    "format": PipelineRole.PRIMARY,
    "baseline": PipelineRole.PRIMARY,
    # PRE_RENDER -- modifies the DocTree before the primary renders
    # (Variants with custom pre_render() should override pipeline_role().)
    "scale": PipelineRole.PRE_RENDER,
    # POST_RENDER -- appends variant-specific annotations/perspective
    "noise": PipelineRole.POST_RENDER,
    "position": PipelineRole.POST_RENDER,
    "structure": PipelineRole.POST_RENDER,
    "granularity": PipelineRole.POST_RENDER,
    "metadata": PipelineRole.POST_RENDER,
    "transform": PipelineRole.POST_RENDER,
    "xref": PipelineRole.POST_RENDER,
    "temporal": PipelineRole.POST_RENDER,
    "tool-description": PipelineRole.POST_RENDER,
    "tool-set-size": PipelineRole.POST_RENDER,
    "agent-instruction": PipelineRole.POST_RENDER,
}


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
    axis: int = Field(ge=0, le=13)
    category: str
    description: str
    token_estimate: int = Field(default=0, ge=0)


class IndexVariant(ABC):
    """Abstract base class that every index variant must implement.

    Subclasses *must* override ``metadata`` and ``render``.  The optional
    ``setup`` and ``teardown`` hooks default to no-ops.

    For composite pipeline support, subclasses may override
    ``pipeline_role()``, ``pre_render()``, and ``post_render()``.
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

    def pipeline_role(self) -> PipelineRole:
        """Return this variant's role in a composite pipeline.

        Infers the role from the variant's metadata category using the
        ``_ROLE_BY_CATEGORY`` mapping.  Defaults to ``PRIMARY`` for
        unknown categories.  Subclasses may override for explicit control.

        Returns:
            The pipeline role for this variant.
        """
        return _ROLE_BY_CATEGORY.get(
            self.metadata().category, PipelineRole.PRIMARY
        )

    def pre_render(self, doc_tree: DocTree) -> DocTree:
        """Modify the DocTree before the primary variant renders.

        Called only for variants with ``PipelineRole.PRE_RENDER``.
        For PRE_RENDER variants the default renders independently,
        identifies which file paths appear in the output, and filters
        the DocTree to only those files.  Subclasses should override
        for more specific behaviour (e.g. noise injection, reordering).

        For non-PRE_RENDER variants, returns the tree unchanged.

        Args:
            doc_tree: The documentation tree to modify.

        Returns:
            A (possibly modified) DocTree.
        """
        if self.pipeline_role() != PipelineRole.PRE_RENDER:
            return doc_tree
        rendered = self.render(doc_tree)
        included = [k for k in doc_tree.files if k in rendered]
        if included and len(included) < len(doc_tree.files):
            return doc_tree.model_copy(
                update={"files": {k: doc_tree.files[k] for k in included}}
            )
        return doc_tree

    def post_render(self, text: str, doc_tree: DocTree) -> str:
        """Transform rendered text after the primary variant produces it.

        Called only for variants with ``PipelineRole.POST_RENDER``.
        For POST_RENDER variants the default renders independently and
        appends the output as a labelled annotation section.  Subclasses
        may override for more compact or inline annotation strategies.

        For non-POST_RENDER variants, returns the text unchanged.

        Args:
            text: The rendered text from the primary variant.
            doc_tree: The documentation tree (for reference).

        Returns:
            The (possibly modified) rendered text.
        """
        if self.pipeline_role() != PipelineRole.POST_RENDER:
            return text
        rendered = self.render(doc_tree)
        meta = self.metadata()
        return f"{text}\n\n[{meta.category}: {meta.name}]\n{rendered}"

    def setup(self, doc_tree: DocTree) -> None:  # noqa: B027
        """Optional: pre-processing before render.

        Args:
            doc_tree: Parsed documentation tree available for inspection.
        """

    def teardown(self) -> None:  # noqa: B027
        """Optional: cleanup after all tasks complete."""
