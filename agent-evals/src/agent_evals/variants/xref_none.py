"""Axis 9 cross-reference variant: no cross-references.

Renders each file as a standalone entry with path and summary.
No "see also" or "related" links are included.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants._utils import brief_summary as _brief_summary
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


@register_variant
class XrefNoneVariant(IndexVariant):
    """No cross-references -- each file is a standalone entry.

    Lists every file with its path and a brief summary.  No "see also"
    or "related" links are emitted.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the no-xref variant."""
        return VariantMetadata(
            name="xref-none",
            axis=9,
            category="xref",
            description="No cross-references; each file listed standalone with path and summary.",
            token_estimate=300,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render all files as a flat bulleted list with no cross-references.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            A newline-separated list of ``- path: summary`` entries.
        """
        if not doc_tree.files:
            return ""

        lines: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            summary = doc.summary or _brief_summary(doc.content)
            lines.append(f"- {rel_path}: {summary}")
        return "\n".join(lines)
