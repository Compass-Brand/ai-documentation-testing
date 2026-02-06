"""Axis 6 scale variant: 50 files.

Renders the first 50 files from the doc tree (sorted by path).
Medium-scale index.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant
from agent_evals.variants.scale_5 import _render_scale

if TYPE_CHECKING:
    from agent_index.models import DocTree


@register_variant
class Scale50Variant(IndexVariant):
    """Scale variant -- first 50 files (medium-scale index)."""

    def metadata(self) -> VariantMetadata:
        """Return metadata for the scale-50 variant."""
        return VariantMetadata(
            name="scale-50",
            axis=6,
            category="scale",
            description="Medium index: renders the first 50 files by path.",
            token_estimate=800,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render the first 50 files as a bulleted list.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Bulleted list with path, tier, and summary for up to 50 files.
        """
        return _render_scale(doc_tree, max_files=50)
