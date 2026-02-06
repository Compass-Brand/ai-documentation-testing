"""Axis 8 granularity variant: adaptive mixed granularity.

Adapts entry granularity based on file size:

- **Small** files (< 500 chars): file-level entry.
- **Medium** files (500--2000 chars): section-level entries (split on ``## ``).
- **Large** files (> 2000 chars): function-level entries if the file
  contains code definitions, otherwise section-level entries.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree

_DEF_PATTERN = re.compile(r"^(?:def|class)\s+(\w+)")

_SMALL_THRESHOLD = 500
_LARGE_THRESHOLD = 2000


def _brief_summary(content: str, max_chars: int = 80) -> str:
    """Extract a brief summary from content."""
    for line in content.splitlines():
        stripped = line.strip().lstrip("# ")
        if stripped:
            return stripped[:max_chars]
    return ""


def _extract_sections(content: str) -> list[tuple[str, str]]:
    """Split content on ``## `` headings.

    Returns:
        A list of ``(section_name, first_line_summary)`` pairs.
    """
    sections: list[tuple[str, str]] = []
    parts = re.split(r"^(## .+)$", content, flags=re.MULTILINE)

    i = 1
    while i < len(parts):
        heading = parts[i].lstrip("# ").strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        summary = ""
        for line in body.splitlines():
            stripped = line.strip()
            if stripped:
                summary = stripped[:80]
                break
        sections.append((heading, summary))
        i += 2

    return sections


def _extract_definitions(content: str) -> list[tuple[str, str]]:
    """Extract function and class definitions from content.

    Returns:
        A list of ``(name, kind)`` pairs.
    """
    definitions: list[tuple[str, str]] = []
    for line in content.splitlines():
        stripped = line.strip()
        match = _DEF_PATTERN.match(stripped)
        if match:
            name = match.group(1)
            kind = "class" if stripped.startswith("class ") else "function"
            definitions.append((name, kind))
    return definitions


@register_variant
class GranularityMixedVariant(IndexVariant):
    """Adaptive granularity based on file size.

    Small files get file-level entries, medium files get section-level,
    and large files get function-level (if code) or section-level.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the mixed granularity variant."""
        return VariantMetadata(
            name="granularity-mixed",
            axis=8,
            category="granularity",
            description="Adaptive granularity: file/section/function based on size.",
            token_estimate=500,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render with adaptive granularity per file.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            A newline-separated list of entries at varying granularity.
        """
        if not doc_tree.files:
            return ""

        lines: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            content_len = len(doc.content)

            if content_len < _SMALL_THRESHOLD:
                # Small file: file-level entry
                summary = _brief_summary(doc.content)
                lines.append(f"- {rel_path}: {summary}")

            elif content_len <= _LARGE_THRESHOLD:
                # Medium file: section-level entries
                sections = _extract_sections(doc.content)
                if sections:
                    for section_name, summary in sections:
                        lines.append(f"- {rel_path}#{section_name}: {summary}")
                else:
                    summary = _brief_summary(doc.content)
                    lines.append(f"- {rel_path}: {summary}")

            else:
                # Large file: function-level if code, else section-level
                definitions = _extract_definitions(doc.content)
                if definitions:
                    for name, kind in definitions:
                        lines.append(f"- {rel_path}::{name} ({kind})")
                else:
                    sections = _extract_sections(doc.content)
                    if sections:
                        for section_name, summary in sections:
                            lines.append(f"- {rel_path}#{section_name}: {summary}")
                    else:
                        summary = _brief_summary(doc.content)
                        lines.append(f"- {rel_path}: {summary}")

        return "\n".join(lines)
