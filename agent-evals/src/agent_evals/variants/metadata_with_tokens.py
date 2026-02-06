"""Axis 2 metadata variant: path with token count and tier.

Each file entry shows the path alongside its tier classification
and estimated token count.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


@register_variant
class MetadataWithTokensVariant(IndexVariant):
    """Path plus token count and tier label for each file.

    Helps the agent estimate the cost of reading each file.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the path-with-tokens variant."""
        return VariantMetadata(
            name="metadata-with-tokens",
            axis=2,
            category="metadata",
            description="Path with token count and tier classification.",
            token_estimate=300,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render paths with token counts and tiers.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            A newline-separated list of
            ``- path [tier: X, ~N tokens]`` entries.
        """
        if not doc_tree.files:
            return ""

        lines: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            tokens = doc.token_count if doc.token_count is not None else 0
            lines.append(f"- {rel_path} [tier: {doc.tier}, ~{tokens} tokens]")
        return "\n".join(lines)
