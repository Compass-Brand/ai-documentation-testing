"""Axis 10 temporal variant: no temporal information.

Renders each file with just its path and summary.  No timestamps,
version markers, or deprecation tags are included.  Serves as the
baseline for temporal-marker comparisons.
"""

from __future__ import annotations

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
class TemporalNoneVariant(IndexVariant):
    """No temporal information -- path and summary only.

    Baseline variant for Axis 10 temporal comparisons.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the no-temporal variant."""
        return VariantMetadata(
            name="temporal-none",
            axis=10,
            category="temporal",
            description="No temporal information; path and summary only.",
            token_estimate=300,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render all files with no temporal markers.

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
            summary = doc.summary or _brief_summary(doc.content)
            lines.append(f"- {rel_path}: {summary}")
        return "\n".join(lines)
