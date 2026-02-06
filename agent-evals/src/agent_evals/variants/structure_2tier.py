"""Axis 1 structure variant: two-tier section grouping.

Groups files by their section (top-level group), then lists files
within each section.
"""

from __future__ import annotations

from collections import defaultdict
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
class Structure2TierVariant(IndexVariant):
    """Two-tier structure: section > files.

    Files are grouped under their section heading with brief summaries.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the 2-tier structure variant."""
        return VariantMetadata(
            name="structure-2tier",
            axis=1,
            category="structure",
            description="Two-tier grouping: section heading then file listing.",
            token_estimate=400,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render files grouped by section.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Markdown with ``## Section`` headings and bulleted file lists.
        """
        if not doc_tree.files:
            return ""

        # Group by section
        sections: dict[str, list[str]] = defaultdict(list)
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            sections[doc.section].append(rel_path)

        blocks: list[str] = []
        for section in sorted(sections):
            lines: list[str] = [f"## {section}"]
            for rel_path in sections[section]:
                doc = doc_tree.files[rel_path]
                summary = _brief_summary(doc.content)
                lines.append(f"- {rel_path}: {summary}")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)
