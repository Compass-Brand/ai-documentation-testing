"""Axis 1 structure variant: flat list with required-tier content inlined.

Required-tier files have their full content inlined under a heading.
All other files are listed with a brief summary and their tier label.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants._utils import brief_summary as _brief_summary
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


@register_variant
class StructureInlineRequiredVariant(IndexVariant):
    """Flat list with full content inlined for required-tier files.

    Required files get their complete content rendered under a heading.
    Other files are shown as a single-line summary with their tier.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the inline-required structure variant."""
        return VariantMetadata(
            name="structure-inline-required",
            axis=1,
            category="structure",
            description="Flat list with required-tier file content inlined, others summarised.",
            token_estimate=800,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render with required files inlined and others summarised.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Markdown where required files have full content and others
            are listed as ``- path (tier): summary``.
        """
        if not doc_tree.files:
            return ""

        blocks: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            if doc.tier == "required":
                blocks.append(f"## {rel_path} [REQUIRED]\n{doc.content}")
            else:
                summary = _brief_summary(doc.content)
                blocks.append(f"- {rel_path} ({doc.tier}): {summary}")
        return "\n\n".join(blocks)
