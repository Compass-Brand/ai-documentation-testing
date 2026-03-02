"""Pipe-delimited table format variant (Axis 3).

Renders the documentation index as a pipe-delimited table with a header row,
one file per line.  Compact and easy to parse programmatically.
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
class FormatPipeDelimited(IndexVariant):
    """Render the documentation index as a pipe-delimited table.

    Example output::

        path|section|tier|tokens|summary
        api/auth.md|API|required|450|JWT authentication with AuthMiddleware
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the pipe-delimited format variant."""
        return VariantMetadata(
            name="format-pipe-delimited",
            axis=3,
            category="format",
            description="Pipe-delimited table format for compact, parseable indexes.",
            token_estimate=300,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render the doc tree as a pipe-delimited table.

        Args:
            doc_tree: Parsed documentation tree to render.

        Returns:
            Pipe-delimited string with header and one row per file.
        """
        lines: list[str] = ["path|section|tier|tokens|summary"]
        for _key, doc in sorted(doc_tree.files.items()):
            summary = doc.summary if doc.summary else _summarise(doc.content)
            tokens = doc.token_count if doc.token_count is not None else 0
            lines.append(
                f"{_escape_pipe(doc.rel_path)}|{_escape_pipe(doc.section)}"
                f"|{_escape_pipe(doc.tier)}|{tokens}"
                f"|{_escape_pipe(summary)}"
            )
        return "\n".join(lines)
