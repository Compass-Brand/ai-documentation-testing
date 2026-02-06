"""BLUF (Bottom Line Up Front) position variant (Axis 4).

Required-tier files appear first, then recommended, then reference.
Within each tier, files are sorted by priority descending, then
alphabetically by ``rel_path`` as a tiebreaker.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocFile, DocTree

# Tier ordering: lower number = appears earlier in the index.
_TIER_ORDER = {"required": 0, "recommended": 1, "reference": 2}


def _summarise(content: str) -> str:
    """Return first line or first ~100 chars of content as a summary."""
    first_line = content.split("\n", 1)[0].strip()
    if len(first_line) > 100:
        return first_line[:97] + "..."
    return first_line


def _render_two_tier(ordered_docs: list[DocFile]) -> str:
    """Render a list of DocFile objects using the 2-tier section format.

    Groups files by section and renders each group under a Markdown heading,
    preserving the order of first appearance.

    Args:
        ordered_docs: Files in the desired display order.

    Returns:
        Markdown string with section headings and file entries.
    """
    sections: dict[str, list[DocFile]] = defaultdict(list)
    section_order: list[str] = []
    for doc in ordered_docs:
        if doc.section not in sections:
            section_order.append(doc.section)
        sections[doc.section].append(doc)

    lines: list[str] = ["# Documentation Index"]
    for section_name in section_order:
        lines.append("")
        lines.append(f"## {section_name}")
        for doc in sections[section_name]:
            summary = doc.summary if doc.summary else _summarise(doc.content)
            tokens = doc.token_count if doc.token_count is not None else 0
            lines.append(
                f"- {doc.rel_path} ({doc.tier}, ~{tokens} tokens) -- {summary}"
            )

    return "\n".join(lines)


@register_variant
class PositionBluf(IndexVariant):
    """BLUF ordering: required first, then recommended, then reference.

    Within each tier files are sorted by descending priority, then
    alphabetically by ``rel_path``.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the BLUF position variant."""
        return VariantMetadata(
            name="position-bluf",
            axis=4,
            category="position",
            description="Bottom Line Up Front: required-tier files first, then recommended, then reference.",
            token_estimate=400,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render the doc tree with BLUF file ordering.

        Args:
            doc_tree: Parsed documentation tree to render.

        Returns:
            Markdown string with files ordered by tier importance.
        """
        docs = list(doc_tree.files.values())
        docs.sort(
            key=lambda d: (
                _TIER_ORDER.get(d.tier, 99),
                -d.priority,
                d.rel_path,
            )
        )
        return _render_two_tier(docs)
