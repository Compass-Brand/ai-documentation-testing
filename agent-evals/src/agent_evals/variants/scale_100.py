"""Axis 6 scale variant: 100 files.

Renders the first 100 files from the doc tree (sorted by path).
Large-scale index.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant
from agent_evals.variants.scale_5 import _render_scale

if TYPE_CHECKING:
    from agent_index.models import DocTree


@register_variant
class Scale100Variant(IndexVariant):
    """Scale variant -- first 100 files (large-scale index)."""

    def metadata(self) -> VariantMetadata:
        """Return metadata for the scale-100 variant."""
        return VariantMetadata(
            name="scale-100",
            axis=6,
            category="scale",
            description="Large index: renders the first 100 files by path.",
            token_estimate=1500,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render the first 100 files as a bulleted list.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Bulleted list with path, tier, and summary for up to 100 files.
        """
        return _render_scale(doc_tree, max_files=100)
