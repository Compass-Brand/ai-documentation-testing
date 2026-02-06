"""Axis 2 metadata variant: path with summary and cross-references.

Each file entry includes a brief summary and a list of related files
discovered by scanning for shared terms in paths and content.
"""

from __future__ import annotations

import posixpath
import re
from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocFile, DocTree


def _content_summary(content: str, max_chars: int = 100) -> str:
    """Build a brief summary from the first *max_chars* of content."""
    text = " ".join(content.split())
    text = text.lstrip("# ").strip()
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "..."
    return text


def _stem(rel_path: str) -> str:
    """Return the filename stem (no extension, no directory)."""
    base = posixpath.basename(rel_path)
    return posixpath.splitext(base)[0]


def _find_related(
    target_path: str,
    target_doc: DocFile,
    all_files: dict[str, DocFile],
    max_related: int = 3,
) -> list[str]:
    """Find files related to *target_path*.

    A file is considered related if:
    1. It shares the same section as the target, **or**
    2. Its content mentions the target file's stem (e.g. ``auth`` appears
       in another file's content).

    Results are sorted by path and capped at *max_related*.
    """
    target_stem = _stem(target_path)
    # Build a simple regex that matches the stem as a whole word
    stem_pattern = re.compile(rf"\b{re.escape(target_stem)}\b", re.IGNORECASE)

    related: set[str] = set()
    for other_path, other_doc in all_files.items():
        if other_path == target_path:
            continue
        # Same section is a signal of relatedness
        if other_doc.section == target_doc.section:
            related.add(other_path)
            continue
        # Mention of the target's stem in other file's content
        if stem_pattern.search(other_doc.content):
            related.add(other_path)

    return sorted(related)[:max_related]


@register_variant
class MetadataWithRelatedVariant(IndexVariant):
    """Path plus summary and cross-referenced related files.

    Gives the agent richer context about how files relate to each other.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the path-with-related variant."""
        return VariantMetadata(
            name="metadata-with-related",
            axis=2,
            category="metadata",
            description="Path with summary and cross-references to related files.",
            token_estimate=600,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render paths with summaries and related file lists.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            A newline-separated list of
            ``- path -- summary. Related: a, b`` entries.
        """
        if not doc_tree.files:
            return ""

        lines: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            summary = _content_summary(doc.content)
            related = _find_related(rel_path, doc, doc_tree.files)
            if related:
                related_str = ", ".join(related)
                lines.append(f"- {rel_path} \u2014 {summary}. Related: {related_str}")
            else:
                lines.append(f"- {rel_path} \u2014 {summary}")
        return "\n".join(lines)
