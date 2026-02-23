"""Axis 8 granularity variant: file-level entries.

The standard/default granularity -- one entry per file.  Each entry
uses a ``[FILE]`` prefix with the full summary from doc tree metadata
to differentiate from the noise-0 variant.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants._utils import brief_summary as _brief_summary
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


@register_variant
class GranularityFileVariant(IndexVariant):
    """One entry per file (standard granularity).

    Each entry shows the file path and a brief summary.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the file-level granularity variant."""
        return VariantMetadata(
            name="granularity-file",
            axis=8,
            category="granularity",
            description="One index entry per file with brief summary.",
            token_estimate=300,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render one entry per file with ``[FILE]`` prefix.

        Uses the ``doc.summary`` field (full summary from doc tree metadata)
        and a ``[FILE]`` prefix to differentiate from the noise-0 variant
        which uses ``brief_summary`` (first content line) without a prefix.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            A newline-separated list of ``[FILE] path: summary`` entries.
        """
        if not doc_tree.files:
            return ""

        lines: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            summary = doc.summary if doc.summary else _brief_summary(doc.content)
            lines.append(f"[FILE] {rel_path}: {summary}")
        return "\n".join(lines)
