"""Axis 2 metadata variant: path with content summary.

Each file entry includes the path followed by a brief summary
derived from the first ~100 characters of its content.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


def _content_summary(content: str, max_chars: int = 100) -> str:
    """Build a brief summary from the first *max_chars* of content.

    Strips leading markdown heading markers and collapses whitespace
    so the summary fits on a single line.
    """
    text = " ".join(content.split())  # collapse whitespace
    text = text.lstrip("# ").strip()
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "..."
    return text


@register_variant
class MetadataWithSummaryVariant(IndexVariant):
    """Path plus a brief content summary for each file.

    Provides slightly richer pointers than path-only, giving the agent
    a hint about what each file contains.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the path-with-summary variant."""
        return VariantMetadata(
            name="metadata-with-summary",
            axis=2,
            category="metadata",
            description="Path plus first ~100 chars of content as summary.",
            token_estimate=400,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render paths with content summaries.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            A newline-separated list of ``- path -- summary`` entries.
        """
        if not doc_tree.files:
            return ""

        lines: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            summary = _content_summary(doc.content)
            lines.append(f"- {rel_path} \u2014 {summary}")
        return "\n".join(lines)
