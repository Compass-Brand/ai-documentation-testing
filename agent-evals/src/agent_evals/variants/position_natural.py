"""Natural (alphabetical) position variant (Axis 4).

Files are sorted alphabetically by ``rel_path`` -- the natural directory
order.  This is the default ordering most tools produce when listing files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants._utils import render_two_tier as _render_two_tier
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocFile, DocTree


@register_variant
class PositionNatural(IndexVariant):
    """Files sorted alphabetically by rel_path (natural directory order)."""

    def metadata(self) -> VariantMetadata:
        """Return metadata for the natural position variant."""
        return VariantMetadata(
            name="position-natural",
            axis=4,
            category="position",
            description="Files in alphabetical rel_path order (natural directory order).",
            token_estimate=400,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render the doc tree with files in alphabetical order.

        Args:
            doc_tree: Parsed documentation tree to render.

        Returns:
            Markdown string with files ordered alphabetically by path.
        """
        ordered = [doc_tree.files[k] for k in sorted(doc_tree.files)]
        return _render_two_tier(ordered)
