"""Axis 9 cross-reference variant: light cross-references.

After each file entry, adds a "See also:" line listing 1-2 files from the
same section.  Uses section matching to find related files.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


def _brief_summary(content: str, max_chars: int = 80) -> str:
    """Extract a brief summary from content.

    Takes the first non-empty line and truncates to *max_chars*.
    """
    for line in content.splitlines():
        stripped = line.strip().lstrip("# ")
        if stripped:
            return stripped[:max_chars]
    return ""


@register_variant
class XrefLightVariant(IndexVariant):
    """Light cross-references via section matching.

    After each file entry, adds a "See also:" line listing up to 2 other
    files from the same section.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the light-xref variant."""
        return VariantMetadata(
            name="xref-light",
            axis=9,
            category="xref",
            description="Light cross-references; 1-2 same-section files listed as See also.",
            token_estimate=400,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render files with light section-based cross-references.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            A bulleted list where each file has an optional indented
            "See also:" sub-item listing 1-2 same-section files.
        """
        if not doc_tree.files:
            return ""

        # Build section -> sorted paths mapping
        section_map: dict[str, list[str]] = defaultdict(list)
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            section_map[doc.section].append(rel_path)

        lines: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            summary = doc.summary or _brief_summary(doc.content)
            lines.append(f"- {rel_path}: {summary}")

            # Find same-section peers (exclude self), take up to 2
            peers = [p for p in section_map[doc.section] if p != rel_path][:2]
            if peers:
                lines.append(f"  See also: {', '.join(peers)}")

        return "\n".join(lines)
