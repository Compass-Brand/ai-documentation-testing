"""Markdown bulleted-list format variant (Axis 3).

Renders the documentation index as a Markdown document with section headings
and bulleted lists, one bullet per file.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from agent_evals.variants._utils import summarise as _summarise
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocFile, DocTree


@register_variant
class FormatMarkdownList(IndexVariant):
    """Render the documentation index as a Markdown bulleted list.

    Example output::

        # Documentation Index

        ## API
        - **api/auth.md** (required, ~450 tokens) -- JWT authentication
        - **api/caching.md** (recommended, ~300 tokens) -- Response caching

        ## Guides
        - **guides/setup.md** (required, ~200 tokens) -- Getting started guide
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the Markdown list format variant."""
        return VariantMetadata(
            name="format-markdown-list",
            axis=3,
            category="format",
            description="Markdown bulleted list grouped by section.",
            token_estimate=400,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render the doc tree as a Markdown bulleted list.

        Args:
            doc_tree: Parsed documentation tree to render.

        Returns:
            Markdown string with section headings and bullet items.
        """
        # Group files by section
        sections: dict[str, list[DocFile]] = defaultdict(list)
        for _key, doc in sorted(doc_tree.files.items()):
            sections[doc.section].append(doc)

        lines: list[str] = ["# Documentation Index"]

        for section_name in sorted(sections):
            lines.append("")
            lines.append(f"## {section_name}")
            for doc in sections[section_name]:
                summary = doc.summary if doc.summary else _summarise(doc.content)
                tokens = doc.token_count if doc.token_count is not None else 0
                lines.append(
                    f"- **{doc.rel_path}** ({doc.tier}, ~{tokens} tokens) "
                    f"\u2014 {summary}"
                )

        return "\n".join(lines)
