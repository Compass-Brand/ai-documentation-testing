"""Plain prose Markdown format variant (Axis 3).

Renders the documentation index as flowing prose paragraphs grouped by
section.  Mirrors how a human might describe the documentation set in
natural language.
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
class FormatPlainMarkdown(IndexVariant):
    """Render the documentation index as flowing prose paragraphs.

    Example output::

        The documentation contains API references and guides. The API section
        includes auth.md (required) covering JWT authentication, and caching.md
        (recommended) covering response caching with CacheConfig...
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the plain Markdown prose variant."""
        return VariantMetadata(
            name="format-plain-markdown",
            axis=3,
            category="format",
            description="Flowing prose paragraphs describing the documentation set.",
            token_estimate=600,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render the doc tree as prose paragraphs grouped by section.

        Args:
            doc_tree: Parsed documentation tree to render.

        Returns:
            Natural-language description of the documentation set.
        """
        # Group files by section
        sections: dict[str, list[DocFile]] = defaultdict(list)
        for _key, doc in sorted(doc_tree.files.items()):
            sections[doc.section].append(doc)

        section_names = sorted(sections)
        if not section_names:
            return "The documentation set is empty."

        # Opening sentence
        section_labels = " and ".join(
            f"{name} references" if name != "Guides" else "guides"
            for name in section_names
        )
        paragraphs: list[str] = [
            f"The documentation contains {section_labels}."
        ]

        # One paragraph per section
        for section_name in section_names:
            docs = sections[section_name]
            parts: list[str] = []
            for doc in docs:
                summary = doc.summary if doc.summary else _summarise(doc.content)
                filename = doc.rel_path.rsplit("/", 1)[-1]
                parts.append(f"{filename} ({doc.tier}) covering {summary}")
            file_descriptions = ", and ".join(parts) if len(parts) <= 2 else ", ".join(
                parts[:-1]
            ) + f", and {parts[-1]}"
            paragraphs.append(
                f"The {section_name} section includes {file_descriptions}."
            )

        return "\n\n".join(paragraphs)
