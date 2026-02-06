"""Natural (alphabetical) position variant (Axis 4).

Files are sorted alphabetically by ``rel_path`` -- the natural directory
order.  This is the default ordering most tools produce when listing files.
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
class PositionNatural(IndexVariant):
    """Files sorted alphabetically by rel_path (natural directory order)."""

    def metadata(self) -> VariantMetadata:
        """Return metadata for the natural position variant."""
        return VariantMetadata(
            name="position-natural",
            axis=4,
            category="position",
            description="Files in alphabetical rel_path order (natural directory order).",
            token_estimate=400,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render the doc tree with files in alphabetical order.

        Args:
            doc_tree: Parsed documentation tree to render.

        Returns:
            Markdown string with files ordered alphabetically by path.
        """
        ordered = [doc_tree.files[k] for k in sorted(doc_tree.files)]
        return _render_two_tier(ordered)
