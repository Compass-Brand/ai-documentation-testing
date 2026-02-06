"""Axis 7 noise variant: 0% noise (pure signal).

Renders all files as a bulleted list with no distractors added.
Each entry shows the file path and a brief summary.
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
class Noise0Variant(IndexVariant):
    """Pure signal, no noise.

    Lists only real files from the doc tree with path and summary.
    No distractors are added.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the 0% noise variant."""
        return VariantMetadata(
            name="noise-0",
            axis=7,
            category="noise",
            description="Pure signal index with no distractor entries.",
            token_estimate=300,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render all files as a bulleted list with no noise.

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
            summary = _brief_summary(doc.content)
            lines.append(f"- {rel_path}: {summary}")
        return "\n".join(lines)
