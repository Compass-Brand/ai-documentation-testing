"""Axis 5 transform variant: restructured content.

Restructures content into a standardised format -- extracts headings from
Markdown, builds a table of contents with indented sub-headings, followed
by a brief excerpt from each section.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")
_EXCERPT_MAX_CHARS = 120


def _restructure(content: str) -> str:
    """Restructure Markdown content into TOC + excerpts.

    Extracts headings, builds an indented table of contents, and appends
    a brief excerpt (first non-heading, non-blank line) under each section.
    """
    lines = content.splitlines()
    toc_entries: list[str] = []
    excerpts: list[tuple[str, str]] = []  # (heading_text, excerpt)

    current_heading: str | None = None
    current_excerpt: str | None = None

    for line in lines:
        match = _HEADING_RE.match(line)
        if match:
            # Flush previous section's excerpt
            if current_heading is not None:
                excerpts.append((current_heading, current_excerpt or ""))

            level = len(match.group(1))
            heading_text = match.group(2).strip()
            indent = "  " * (level - 1)
            toc_entries.append(f"{indent}- {heading_text}")
            current_heading = heading_text
            current_excerpt = None
        elif current_excerpt is None and line.strip():
            # First non-blank, non-heading line is the excerpt
            current_excerpt = line.strip()[:_EXCERPT_MAX_CHARS]

    # Flush the last section
    if current_heading is not None:
        excerpts.append((current_heading, current_excerpt or ""))

    # If no headings found, return a brief excerpt of the raw content
    if not toc_entries:
        first_line = content.strip().split("\n", 1)[0].strip()
        return first_line[:_EXCERPT_MAX_CHARS] if first_line else ""

    parts: list[str] = ["### Table of Contents", ""]
    parts.extend(toc_entries)
    parts.append("")
    parts.append("### Excerpts")
    for heading_text, excerpt in excerpts:
        if excerpt:
            parts.append(f"- **{heading_text}**: {excerpt}")
        else:
            parts.append(f"- **{heading_text}**")

    return "\n".join(parts)


@register_variant
class TransformRestructuredVariant(IndexVariant):
    """Restructured content -- TOC + section excerpts.

    Extracts Markdown headings to build a table of contents, then appends
    a brief excerpt from each section for quick scanning.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the restructured transform variant."""
        return VariantMetadata(
            name="transform-restructured",
            axis=5,
            category="transform",
            description=(
                "Restructured: table of contents from headings plus "
                "brief section excerpts."
            ),
            token_estimate=700,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render all files with restructured TOC + excerpt format.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Markdown string with restructured content under path headings.
        """
        if not doc_tree.files:
            return ""

        sections: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            restructured = _restructure(doc.content)
            sections.append(f"## {rel_path}\n\n{restructured}")
        return "\n\n".join(sections)
