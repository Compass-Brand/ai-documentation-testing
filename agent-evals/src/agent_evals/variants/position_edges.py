"""Edges (sandwich) position variant (Axis 4).

Important (required-tier) files are placed at both the start AND the end
of the index, exploiting the primacy and recency effects in language model
attention.  Required files are split: the first half goes to the top, the
second half to the bottom.  Non-required files fill the middle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants._utils import render_two_tier as _render_two_tier
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocFile, DocTree


@register_variant
class PositionEdges(IndexVariant):
    """Sandwich pattern: required files at both start and end.

    Required files are sorted alphabetically, then split in half.  The first
    half appears at the top, the non-required files fill the middle (sorted
    alphabetically), and the second half of required files appears at the
    bottom.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the edges position variant."""
        return VariantMetadata(
            name="position-edges",
            axis=4,
            category="position",
            description="Sandwich pattern: required files at start and end for primacy/recency.",
            token_estimate=400,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render the doc tree with required files sandwiching the rest.

        Args:
            doc_tree: Parsed documentation tree to render.

        Returns:
            Markdown string with required files at edges, others in middle.
        """
        required: list[DocFile] = []
        non_required: list[DocFile] = []

        for _key, doc in sorted(doc_tree.files.items()):
            if doc.tier == "required":
                required.append(doc)
            else:
                non_required.append(doc)

        # Split required files in half
        midpoint = len(required) // 2
        # When odd count, first half gets the extra file
        if len(required) % 2 != 0:
            midpoint += 1

        top_required = required[:midpoint]
        bottom_required = required[midpoint:]

        ordered = top_required + non_required + bottom_required
        return _render_two_tier(ordered)
