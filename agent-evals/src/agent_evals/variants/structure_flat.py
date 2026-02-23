"""Axis 1 structure variant: flat file listing.

Renders all files as a simple flat list with no hierarchy or grouping.
Each entry shows the file path and a brief summary derived from the
first line of content.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants._utils import brief_summary as _brief_summary
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


@register_variant
class StructureFlatVariant(IndexVariant):
    """Flat list of all files with brief summaries.

    No hierarchy or grouping -- every file appears at the same level.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the flat structure variant."""
        return VariantMetadata(
            name="structure-flat",
            axis=1,
            category="structure",
            description="Flat list of all files with brief summaries, no hierarchy.",
            token_estimate=300,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render all files as a flat bulleted list with tier and summary.

        Uses the ``doc.summary`` field (full summary from doc tree metadata)
        and includes tier classification to differentiate from the noise-0
        variant which uses only ``brief_summary`` (first content line).

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            A newline-separated flat list of
            ``- path (tier): summary`` entries.
        """
        if not doc_tree.files:
            return ""

        lines: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            summary = doc.summary if doc.summary else _brief_summary(doc.content)
            lines.append(f"- {rel_path} ({doc.tier}): {summary}")
        return "\n".join(lines)
