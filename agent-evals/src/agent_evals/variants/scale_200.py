"""Axis 6 scale variant: 200 files.

Renders all files up to 200 from the doc tree (sorted by path).
Very large index.  If fewer than 200 files exist, renders all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant
from agent_evals.variants.scale_5 import _render_scale

if TYPE_CHECKING:
    from agent_index.models import DocTree


@register_variant
class Scale200Variant(IndexVariant):
    """Scale variant -- up to 200 files (very large index)."""

    def metadata(self) -> VariantMetadata:
        """Return metadata for the scale-200 variant."""
        return VariantMetadata(
            name="scale-200",
            axis=6,
            category="scale",
            description="Very large index: renders all files up to 200 by path.",
            token_estimate=3000,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render up to 200 files as a bulleted list.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Bulleted list with path, tier, and summary for up to 200 files.
        """
        return _render_scale(doc_tree, max_files=200)
