"""BLUF (Bottom Line Up Front) position variant (Axis 4).

Required-tier files appear first, then recommended, then reference.
Within each tier, files are sorted by priority descending, then
alphabetically by ``rel_path`` as a tiebreaker.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants._utils import render_two_tier as _render_two_tier
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocFile, DocTree

# Tier ordering: lower number = appears earlier in the index.
_TIER_ORDER = {"required": 0, "recommended": 1, "reference": 2}


@register_variant
class PositionBluf(IndexVariant):
    """BLUF ordering: required first, then recommended, then reference.

    Within each tier files are sorted by descending priority, then
    alphabetically by ``rel_path``.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the BLUF position variant."""
        return VariantMetadata(
            name="position-bluf",
            axis=4,
            category="position",
            description="Bottom Line Up Front: required-tier files first, then recommended, then reference.",
            token_estimate=400,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render the doc tree with BLUF file ordering.

        Args:
            doc_tree: Parsed documentation tree to render.

        Returns:
            Markdown string with files ordered by tier importance.
        """
        docs = list(doc_tree.files.values())
        docs.sort(
            key=lambda d: (
                _TIER_ORDER.get(d.tier, 99),
                -d.priority,
                d.rel_path,
            )
        )
        return _render_two_tier(docs)
