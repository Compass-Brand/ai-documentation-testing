"""Axis 5 transform variant: algorithmic compression.

Applies simple algorithmic compression -- truncates each file's content
to the first N lines, strips blank lines, and collapses consecutive
whitespace to produce a compact version.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree

_DEFAULT_MAX_LINES = 20


def _compress(content: str, max_lines: int = _DEFAULT_MAX_LINES) -> str:
    """Algorithmically compress content.

    1. Take the first *max_lines* lines.
    2. Strip blank lines.
    3. Collapse runs of whitespace within each line.
    """
    lines = content.splitlines()[:max_lines]
    compressed: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Collapse consecutive whitespace
        compressed.append(re.sub(r"\s{2,}", " ", stripped))
    return "\n".join(compressed)


@register_variant
class TransformAlgorithmicVariant(IndexVariant):
    """Algorithmic compression -- truncation + whitespace normalisation.

    Each file is truncated to the first 20 lines, blank lines are removed,
    and consecutive whitespace is collapsed.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the algorithmic transform variant."""
        return VariantMetadata(
            name="transform-algorithmic",
            axis=5,
            category="transform",
            description=(
                "Algorithmic compression: first 20 lines, no blanks, "
                "collapsed whitespace."
            ),
            token_estimate=800,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render all files with algorithmically compressed content.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Markdown string with compressed content under path headings.
        """
        if not doc_tree.files:
            return ""

        sections: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            compressed = _compress(doc.content)
            sections.append(f"## {rel_path}\n\n{compressed}")
        return "\n\n".join(sections)
