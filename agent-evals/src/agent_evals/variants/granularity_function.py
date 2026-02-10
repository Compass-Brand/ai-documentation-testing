"""Axis 8 granularity variant: function/class-level entries.

Scans content for ``def `` and ``class `` definitions and creates one
entry per definition.  Each entry shows ``file_path::function_name``
and a brief description.  Files with no definitions fall back to a
file-level entry.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from agent_evals.variants._utils import brief_summary as _brief_summary
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree

# Pattern matches lines like: def foo(...) or class Bar(...):
_DEF_PATTERN = re.compile(r"^(?:def|class)\s+(\w+)")


def _extract_definitions(content: str) -> list[tuple[str, str]]:
    """Extract function and class definitions from content.

    Returns:
        A list of ``(name, kind)`` pairs where *kind* is ``"function"``
        or ``"class"``.
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
class GranularityFunctionVariant(IndexVariant):
    """One entry per function/class definition.

    Scans content for ``def `` and ``class `` patterns.  Each entry
    shows ``file_path::name`` and a brief description.  Files without
    definitions fall back to a file-level entry.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the function-level granularity variant."""
        return VariantMetadata(
            name="granularity-function",
            axis=8,
            category="granularity",
            description="One index entry per function/class definition.",
            token_estimate=600,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render one entry per function/class definition.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            A newline-separated list of ``- path::name (kind)`` entries.
        """
        if not doc_tree.files:
            return ""

        lines: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            definitions = _extract_definitions(doc.content)
            if definitions:
                for name, kind in definitions:
                    lines.append(f"- {rel_path}::{name} ({kind})")
            else:
                # No definitions found -- fall back to file-level entry
                summary = _brief_summary(doc.content)
                lines.append(f"- {rel_path}: {summary}")
        return "\n".join(lines)
