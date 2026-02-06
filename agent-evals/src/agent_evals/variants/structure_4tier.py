"""Axis 1 structure variant: four-tier section > tier > subdirectory > files.

Groups files by section, tier, and subdirectory (derived from the
file path), producing four levels of hierarchy.
"""

from __future__ import annotations

import posixpath
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


def _subdir(rel_path: str) -> str:
    """Extract the parent directory from a relative path.

    Returns the directory portion, or ``"(root)"`` if the file sits
    at the top level.
    """
    parent = posixpath.dirname(rel_path)
    return parent if parent else "(root)"


@register_variant
class Structure4TierVariant(IndexVariant):
    """Four-tier structure: section > tier > subdirectory > files.

    Adds a subdirectory grouping level derived from each file's path.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the 4-tier structure variant."""
        return VariantMetadata(
            name="structure-4tier",
            axis=1,
            category="structure",
            description="Four-tier grouping: section > tier > subdirectory > file listing.",
            token_estimate=600,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render files grouped by section, tier, and subdirectory.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Markdown with ``##``/``###``/``####`` headings and file lists.
        """
        if not doc_tree.files:
            return ""

        # Build nested grouping: section -> tier -> subdir -> [paths]
        grouped: dict[str, dict[str, dict[str, list[str]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            sub = _subdir(rel_path)
            grouped[doc.section][doc.tier][sub].append(rel_path)

        blocks: list[str] = []
        for section in sorted(grouped):
            section_lines: list[str] = [f"## {section}"]
            for tier in sorted(grouped[section]):
                section_lines.append(f"### {_tier_title(tier)}")
                for sub in sorted(grouped[section][tier]):
                    section_lines.append(f"#### {sub}")
                    for rel_path in grouped[section][tier][sub]:
                        doc = doc_tree.files[rel_path]
                        summary = _brief_summary(doc.content)
                        section_lines.append(f"- {rel_path}: {summary}")
            blocks.append("\n".join(section_lines))
        return "\n\n".join(blocks)
