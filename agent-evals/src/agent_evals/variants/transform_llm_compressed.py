"""Axis 5 transform variant: LLM-compressed (simulated).

Simulates LLM-compressed content by extracting key sentences -- the first
sentence of each paragraph.  In practice this would call an LLM, but for
the variant implementation we use the algorithmic heuristic of taking the
first line of each paragraph as a "summary paragraph".
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


def _extract_paragraph_leads(content: str) -> str:
    """Extract the first line of each paragraph.

    Paragraphs are separated by one or more blank lines.  The leading
    (non-empty) line of each paragraph is taken as a representative
    summary sentence.
    """
    paragraphs: list[str] = []
    current_paragraph: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            if current_paragraph:
                paragraphs.append(current_paragraph[0])
                current_paragraph = []
        else:
            current_paragraph.append(stripped)

    # Capture the last paragraph if file doesn't end with a blank line
    if current_paragraph:
        paragraphs.append(current_paragraph[0])

    return "\n".join(paragraphs)


@register_variant
class TransformLlmCompressedVariant(IndexVariant):
    """Simulated LLM compression via paragraph-lead extraction.

    Takes the first line of each paragraph as a representative summary,
    approximating what an LLM summarisation pass would produce.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the LLM-compressed transform variant."""
        return VariantMetadata(
            name="transform-llm-compressed",
            axis=5,
            category="transform",
            description=(
                "Simulated LLM compression: first line of each paragraph "
                "extracted as summary."
            ),
            token_estimate=600,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render all files with paragraph-lead extracted content.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Markdown string with extracted summary lines under path headings.
        """
        if not doc_tree.files:
            return ""

        sections: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            summary = _extract_paragraph_leads(doc.content)
            sections.append(f"## {rel_path}\n\n{summary}")
        return "\n\n".join(sections)
