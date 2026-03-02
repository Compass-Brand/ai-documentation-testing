"""Markdown table format variant (Axis 3).

Renders the documentation index as a Markdown table with a header row,
separator, and one row per file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants._utils import escape_pipe as _escape_pipe
from agent_evals.variants._utils import summarise as _summarise
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


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
                f"| {_escape_pipe(doc.rel_path)} "
                f"| {_escape_pipe(doc.section)} "
                f"| {_escape_pipe(doc.tier)} "
                f"| {tokens} "
                f"| {_escape_pipe(summary)} |"
            )
        return "\n".join(lines)
