"""Axis 8 granularity variant: section-level entries.

Splits each file on ``## `` headings and creates one entry per section.
Each entry shows ``file_path#section_name`` and uses the section's first
line as a summary.  Files with no sections are treated as a single entry.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


def _extract_sections(content: str) -> list[tuple[str, str]]:
    """Split content on ``## `` headings.

    Returns:
        A list of ``(section_name, first_line_summary)`` pairs.
        If no ``## `` headings are found, returns an empty list.
    """
    sections: list[tuple[str, str]] = []
    # Split on lines that start with "## "
    parts = re.split(r"^(## .+)$", content, flags=re.MULTILINE)

    # parts alternates: [pre-heading text, heading, body, heading, body, ...]
    i = 1  # skip the pre-heading text
    while i < len(parts):
        heading = parts[i].lstrip("# ").strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        # First non-empty line of the body as summary
        summary = ""
        for line in body.splitlines():
            stripped = line.strip()
            if stripped:
                summary = stripped[:80]
                break
        sections.append((heading, summary))
        i += 2

    return sections


def _brief_summary(content: str, max_chars: int = 80) -> str:
    """Extract a brief summary from content."""
    for line in content.splitlines():
        stripped = line.strip().lstrip("# ")
        if stripped:
            return stripped[:max_chars]
    return ""


@register_variant
class GranularitySectionVariant(IndexVariant):
    """One entry per markdown section.

    Splits files on ``## `` headings.  Each entry shows
    ``file_path#section_name`` and the section's first line as summary.
    Files without sections are treated as a single file-level entry.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the section-level granularity variant."""
        return VariantMetadata(
            name="granularity-section",
            axis=8,
            category="granularity",
            description="One index entry per markdown section (## heading).",
            token_estimate=500,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render one entry per section.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            A newline-separated list of ``- path#section: summary`` entries.
        """
        if not doc_tree.files:
            return ""

        lines: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            sections = _extract_sections(doc.content)
            if sections:
                for section_name, summary in sections:
                    lines.append(f"- {rel_path}#{section_name}: {summary}")
            else:
                # No sections found -- fall back to file-level entry
                summary = _brief_summary(doc.content)
                lines.append(f"- {rel_path}: {summary}")
        return "\n".join(lines)
