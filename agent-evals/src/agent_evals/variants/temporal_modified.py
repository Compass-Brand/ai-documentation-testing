"""Axis 10 temporal variant: last-modified timestamps.

Uses the ``doc.last_modified`` field to display a ``[modified: YYYY-MM-DD]``
tag next to each file entry.  Falls back to ``[modified: unknown]`` when the
field is ``None``.
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
class TemporalModifiedVariant(IndexVariant):
    """Last-modified timestamps from the ``DocFile.last_modified`` field.

    Shows ``[modified: YYYY-MM-DD]`` or ``[modified: unknown]`` next to
    each entry.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the modified-temporal variant."""
        return VariantMetadata(
            name="temporal-modified",
            axis=10,
            category="temporal",
            description="Adds last-modified timestamps from DocFile metadata.",
            token_estimate=350,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render files with last-modified date tags.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            A bulleted list with ``[modified: YYYY-MM-DD]`` tags.
        """
        if not doc_tree.files:
            return ""

        lines: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            summary = doc.summary or _brief_summary(doc.content)
            if doc.last_modified is not None:
                date_str = doc.last_modified.strftime("%Y-%m-%d")
            else:
                date_str = "unknown"
            lines.append(f"- {rel_path} [modified: {date_str}]: {summary}")
        return "\n".join(lines)
