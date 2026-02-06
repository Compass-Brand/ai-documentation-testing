"""Axis 6 scale variant: 15 files.

Renders the first 15 files from the doc tree (sorted by path).
A small but realistic index.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant
from agent_evals.variants.scale_5 import _render_scale

if TYPE_CHECKING:
    from agent_index.models import DocTree


@register_variant
class Scale15Variant(IndexVariant):
    """Scale variant -- first 15 files (small realistic index)."""

    def metadata(self) -> VariantMetadata:
        """Return metadata for the scale-15 variant."""
        return VariantMetadata(
            name="scale-15",
            axis=6,
            category="scale",
            description="Small index: renders the first 15 files by path.",
            token_estimate=250,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render the first 15 files as a bulleted list.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Bulleted list with path, tier, and summary for up to 15 files.
        """
        return _render_scale(doc_tree, max_files=15)
