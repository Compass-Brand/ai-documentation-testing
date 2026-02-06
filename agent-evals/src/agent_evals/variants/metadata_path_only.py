"""Axis 2 metadata variant: path-only listing.

Lists just the file paths with no additional metadata, summaries,
or annotations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


@register_variant
class MetadataPathOnlyVariant(IndexVariant):
    """Path-only file listing with no metadata.

    The simplest pointer format: just the file paths.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the path-only variant."""
        return VariantMetadata(
            name="metadata-path-only",
            axis=2,
            category="metadata",
            description="Just file paths, no metadata or summaries.",
            token_estimate=200,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render a bare list of file paths.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            A newline-separated list of ``- path`` entries.
        """
        if not doc_tree.files:
            return ""

        lines: list[str] = []
        for rel_path in sorted(doc_tree.files):
            lines.append(f"- {rel_path}")
        return "\n".join(lines)
