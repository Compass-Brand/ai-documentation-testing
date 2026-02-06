"""Axis 8 granularity variant: file-level entries.

The standard/default granularity -- one entry per file.  Each entry
shows the file path and a brief summary derived from the first line
of content.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


def _brief_summary(content: str, max_chars: int = 80) -> str:
    """Extract a brief summary from content."""
    for line in content.splitlines():
        stripped = line.strip().lstrip("# ")
        if stripped:
            return stripped[:max_chars]
    return ""


@register_variant
class GranularityFileVariant(IndexVariant):
    """One entry per file (standard granularity).

    Each entry shows the file path and a brief summary.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the file-level granularity variant."""
        return VariantMetadata(
            name="granularity-file",
            axis=8,
            category="granularity",
            description="One index entry per file with brief summary.",
            token_estimate=300,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render one entry per file.

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
            summary = _brief_summary(doc.content)
            lines.append(f"- {rel_path}: {summary}")
        return "\n".join(lines)
