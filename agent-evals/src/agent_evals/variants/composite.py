"""CompositeVariant - combines one variant per axis into a single render.

Used by TaguchiRunner to create combined configurations from orthogonal
array rows, where each row specifies one variant level per axis.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata

if TYPE_CHECKING:
    from agent_index.models import DocTree


class CompositeVariant(IndexVariant):
    """Variant that delegates to one sub-variant per axis.

    Args:
        components: Mapping of axis number to variant instance.
            Must contain at least one entry.
    """

    def __init__(self, components: dict[int, IndexVariant]) -> None:
        if not components:
            raise ValueError("CompositeVariant requires at least one component")
        self._components = components
        self._sorted_axes = sorted(components.keys())

    def metadata(self) -> VariantMetadata:
        """Return composite metadata combining all component names."""
        names = [
            self._components[axis].metadata().name
            for axis in self._sorted_axes
        ]
        estimates = [
            self._components[axis].metadata().token_estimate
            for axis in self._sorted_axes
        ]
        return VariantMetadata(
            name="+".join(names),
            axis=0,
            category="composite",
            description=f"Composite of {len(self._components)} variants",
            token_estimate=sum(estimates),
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render each component in axis order and concatenate."""
        parts: list[str] = []
        for axis in self._sorted_axes:
            parts.append(self._components[axis].render(doc_tree))
        return "\n\n".join(parts)

    def setup(self, doc_tree: DocTree) -> None:
        """Delegate setup to all components in axis order."""
        for axis in self._sorted_axes:
            self._components[axis].setup(doc_tree)

    def teardown(self) -> None:
        """Delegate teardown to all components."""
        for axis in self._sorted_axes:
            self._components[axis].teardown()
