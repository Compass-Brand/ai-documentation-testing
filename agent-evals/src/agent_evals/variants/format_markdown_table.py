"""Markdown table format variant (Axis 3).

Renders the documentation index as a Markdown table with a header row,
separator, and one row per file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


def _summarise(content: str) -> str:
    """Return first line or first ~100 chars of content as a summary."""
    first_line = content.split("\n", 1)[0].strip()
    if len(first_line) > 100:
        return first_line[:97] + "..."
    return first_line


@register_variant
class FormatMarkdownTable(IndexVariant):
    """Render the documentation index as a Markdown table.

    Example output::

        # Documentation Index

        | Path | Section | Tier | Tokens | Summary |
        |------|---------|------|--------|---------|
        | api/auth.md | API | required | 450 | JWT authentication |
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the Markdown table format variant."""
        return VariantMetadata(
            name="format-markdown-table",
            axis=3,
            category="format",
            description="Markdown table format for tabular index display.",
            token_estimate=400,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render the doc tree as a Markdown table.

        Args:
            doc_tree: Parsed documentation tree to render.

        Returns:
            Markdown table string with header, separator, and data rows.
        """
        lines: list[str] = [
            "# Documentation Index",
            "",
            "| Path | Section | Tier | Tokens | Summary |",
            "|------|---------|------|--------|---------|",
        ]
        for _key, doc in sorted(doc_tree.files.items()):
            summary = doc.summary if doc.summary else _summarise(doc.content)
            tokens = doc.token_count if doc.token_count is not None else 0
            lines.append(
                f"| {doc.rel_path} | {doc.section} | {doc.tier} "
                f"| {tokens} | {summary} |"
            )
        return "\n".join(lines)
