"""Axis 6 scale variant: 5 files.

Renders only the first 5 files from the doc tree (sorted by path).
Tests minimal index behaviour.
"""

from __future__ import annotations

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


def _render_scale(doc_tree: DocTree, max_files: int) -> str:
    """Render a bulleted list of files up to *max_files*.

    Files are sorted by path.  Each entry shows path, tier, and a brief
    summary.
    """
    if not doc_tree.files:
        return ""

    sorted_paths = sorted(doc_tree.files)[:max_files]
    lines: list[str] = []
    for rel_path in sorted_paths:
        doc = doc_tree.files[rel_path]
        summary = _brief_summary(doc.content)
        lines.append(f"- {rel_path} ({doc.tier}): {summary}")
    return "\n".join(lines)


@register_variant
class Scale5Variant(IndexVariant):
    """Scale variant -- first 5 files only (minimal index)."""

    def metadata(self) -> VariantMetadata:
        """Return metadata for the scale-5 variant."""
        return VariantMetadata(
            name="scale-5",
            axis=6,
            category="scale",
            description="Minimal index: renders only the first 5 files by path.",
            token_estimate=100,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render the first 5 files as a bulleted list.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Bulleted list with path, tier, and summary for up to 5 files.
        """
        return _render_scale(doc_tree, max_files=5)
