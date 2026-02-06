"""Axis 1 structure variant: three-tier section > tier > files.

Groups files by section, then by tier within each section,
producing three levels of hierarchy.
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


def _tier_title(tier: str) -> str:
    """Capitalize a tier name for display."""
    return tier.capitalize()


@register_variant
class Structure3TierVariant(IndexVariant):
    """Three-tier structure: section > tier > files.

    Provides a hierarchical view with section headings, tier subheadings,
    and bulleted file lists.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the 3-tier structure variant."""
        return VariantMetadata(
            name="structure-3tier",
            axis=1,
            category="structure",
            description="Three-tier grouping: section > tier > file listing.",
            token_estimate=500,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render files grouped by section and tier.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Markdown with ``## Section`` / ``### Tier`` headings and file lists.
        """
        if not doc_tree.files:
            return ""

        # Build nested grouping: section -> tier -> [paths]
        grouped: dict[str, dict[str, list[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            grouped[doc.section][doc.tier].append(rel_path)

        blocks: list[str] = []
        for section in sorted(grouped):
            section_lines: list[str] = [f"## {section}"]
            for tier in sorted(grouped[section]):
                section_lines.append(f"### {_tier_title(tier)}")
                for rel_path in grouped[section][tier]:
                    doc = doc_tree.files[rel_path]
                    summary = _brief_summary(doc.content)
                    section_lines.append(f"- {rel_path}: {summary}")
            blocks.append("\n".join(section_lines))
        return "\n\n".join(blocks)
