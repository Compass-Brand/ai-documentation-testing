"""Axis 5 transform variant: passthrough (raw content unchanged).

Lists files with their raw content unchanged.  Shows each file as a
section heading with the full content below.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


@register_variant
class TransformPassthroughVariant(IndexVariant):
    """Passthrough transform -- raw content reproduced verbatim.

    Each file is rendered as a Markdown heading followed by its full,
    unmodified content.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the passthrough transform variant."""
        return VariantMetadata(
            name="transform-passthrough",
            axis=5,
            category="transform",
            description="Raw file content reproduced verbatim under path headings.",
            token_estimate=2000,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render all files with their raw content unchanged.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Markdown string with each file as a heading followed by full content.
        """
        if not doc_tree.files:
            return ""

        sections: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            sections.append(f"## {rel_path}\n\n{doc.content}")
        return "\n\n".join(sections)
