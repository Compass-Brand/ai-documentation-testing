"""Edges (sandwich) position variant (Axis 4).

Important (required-tier) files are placed at both the start AND the end
of the index, exploiting the primacy and recency effects in language model
attention.  Required files are split: the first half goes to the top, the
second half to the bottom.  Non-required files fill the middle.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocFile, DocTree


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
class PositionEdges(IndexVariant):
    """Sandwich pattern: required files at both start and end.

    Required files are sorted alphabetically, then split in half.  The first
    half appears at the top, the non-required files fill the middle (sorted
    alphabetically), and the second half of required files appears at the
    bottom.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the edges position variant."""
        return VariantMetadata(
            name="position-edges",
            axis=4,
            category="position",
            description="Sandwich pattern: required files at start and end for primacy/recency.",
            token_estimate=400,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render the doc tree with required files sandwiching the rest.

        Args:
            doc_tree: Parsed documentation tree to render.

        Returns:
            Markdown string with required files at edges, others in middle.
        """
        required: list[DocFile] = []
        non_required: list[DocFile] = []

        for _key, doc in sorted(doc_tree.files.items()):
            if doc.tier == "required":
                required.append(doc)
            else:
                non_required.append(doc)

        # Split required files in half
        midpoint = len(required) // 2
        # When odd count, first half gets the extra file
        if len(required) % 2 != 0:
            midpoint += 1

        top_required = required[:midpoint]
        bottom_required = required[midpoint:]

        ordered = top_required + non_required + bottom_required
        return _render_two_tier(ordered)
