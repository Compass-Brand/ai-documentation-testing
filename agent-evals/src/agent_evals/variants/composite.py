"""CompositeVariant - combines one variant per axis into a single render.

Uses a pipeline pattern to produce ONE coherent rendering instead of
concatenating N independent full renderings.  Components are classified
by their ``pipeline_role()``:

1. **PRE_RENDER** -- modify the DocTree (e.g., scale/filter, noise, position)
2. **PRIMARY** -- produce the main rendered text (exactly one is selected)
3. **POST_RENDER** -- transform the rendered text (e.g., tags, xrefs, temporal)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, PipelineRole, VariantMetadata

if TYPE_CHECKING:
    from agent_index.models import DocTree

# Sentinel axis for the injected fallback when no PRIMARY component exists.
_FALLBACK_AXIS = -1


class _FallbackPrimaryVariant(IndexVariant):
    """Passthrough renderer used when no real PRIMARY component is present.

    Renders the DocTree's file paths as a simple listing so that the
    pipeline always has a PRIMARY to delegate to.
    """

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name="fallback-primary",
            axis=0,
            category="format",
            description="Auto-injected passthrough when no PRIMARY component",
            token_estimate=0,
        )

    def render(self, doc_tree: DocTree) -> str:
        if doc_tree.files:
            return "\n".join(doc_tree.files.keys())
        return ""


class CompositeVariant(IndexVariant):
    """Variant that delegates to one sub-variant per axis.

    Uses a pipeline pattern: pre-render components modify the DocTree,
    one primary component renders the output, and post-render components
    transform the rendered text.

    Args:
        components: Mapping of axis number to variant instance.
            Must contain at least one entry.
    """

    def __init__(self, components: dict[int, IndexVariant]) -> None:
        if not components:
            raise ValueError("CompositeVariant requires at least one component")
        self._components = components
        self._sorted_axes = sorted(components.keys())
        self._classify_components()

    def _classify_components(self) -> None:
        """Sort components into pre-render, primary, and post-render lists.

        When no component has PRIMARY role (e.g. format axis excluded as
        DUMMY_LEVEL in Taguchi), injects a ``_FallbackPrimaryVariant`` so
        the pipeline always has a renderer.
        """
        self._pre_render: list[int] = []
        self._primary: list[int] = []
        self._post_render: list[int] = []

        for axis in self._sorted_axes:
            role = self._components[axis].pipeline_role()
            if role == PipelineRole.PRE_RENDER:
                self._pre_render.append(axis)
            elif role == PipelineRole.POST_RENDER:
                self._post_render.append(axis)
            else:
                self._primary.append(axis)

        if not self._primary:
            self._components[_FALLBACK_AXIS] = _FallbackPrimaryVariant()
            self._primary.append(_FALLBACK_AXIS)

    def _select_primary(self) -> int:
        """Select the single primary renderer axis.

        When multiple PRIMARY components exist, picks the first one
        (lowest axis number) to avoid concatenating multiple full renders.
        A fallback is always injected by ``_classify_components`` when no
        real PRIMARY exists, so this should never be empty.

        Returns:
            The axis number of the selected primary renderer.
        """
        return self._primary[0]

    def metadata(self) -> VariantMetadata:
        """Return composite metadata combining all component names."""
        names = [
            self._components[axis].metadata().name
            for axis in self._sorted_axes
        ]
        primary_axis = self._select_primary()
        primary_estimate = self._components[primary_axis].metadata().token_estimate
        return VariantMetadata(
            name="+".join(names),
            axis=0,
            category="composite",
            description=f"Composite of {len(self._components)} variants",
            token_estimate=primary_estimate,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render using the pipeline: pre-render -> primary -> post-render.

        Pre-render components modify the DocTree in axis order, the selected
        primary component renders the modified DocTree, and post-render
        components transform the output text in axis order.

        Args:
            doc_tree: Parsed documentation tree to render.

        Returns:
            A single coherent rendered document.
        """
        # Phase 1: pre-render components modify the doc_tree
        current_tree = doc_tree
        for axis in self._pre_render:
            current_tree = self._components[axis].pre_render(current_tree)

        # Phase 2: primary renderer produces the output
        primary_axis = self._select_primary()
        output = self._components[primary_axis].render(current_tree)

        # Phase 3: post-render components transform the output
        for axis in self._post_render:
            output = self._components[axis].post_render(
                output, current_tree
            )

        return output

    def setup(self, doc_tree: DocTree) -> None:
        """Delegate setup to all components in axis order."""
        for axis in self._sorted_axes:
            self._components[axis].setup(doc_tree)

    def teardown(self) -> None:
        """Delegate teardown to all components."""
        for axis in self._sorted_axes:
            self._components[axis].teardown()
