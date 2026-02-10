"""Axis 10 temporal variant: version markers.

Scans file content for version patterns (e.g. ``v1.0``, ``version 2.3``,
``@since 1.5``) and displays the detected version next to each file entry.
If no version is found, shows "unversioned".
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from agent_evals.variants._utils import brief_summary as _brief_summary
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree

# Patterns to detect version strings in content.
_VERSION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"@since\s+([\d]+(?:\.[\d]+)*)", re.IGNORECASE),
    re.compile(r"version\s+([\d]+(?:\.[\d]+)*)", re.IGNORECASE),
    re.compile(r"\bv([\d]+(?:\.[\d]+)+)\b", re.IGNORECASE),
]


def _detect_version(content: str) -> str:
    """Scan content for version patterns.

    Returns the first version string found, or ``"unversioned"`` if none
    is detected.
    """
    for pattern in _VERSION_PATTERNS:
        match = pattern.search(content)
        if match:
            return f"v{match.group(1)}"
    return "unversioned"


@register_variant
class TemporalVersionVariant(IndexVariant):
    """Version markers extracted from file content.

    Scans each file for version patterns and displays the detected
    version alongside the file entry.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the version-temporal variant."""
        return VariantMetadata(
            name="temporal-version",
            axis=10,
            category="temporal",
            description="Adds version markers detected from content patterns.",
            token_estimate=350,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render files with detected version markers.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            A bulleted list with ``[vX.Y]`` or ``[unversioned]`` tags.
        """
        if not doc_tree.files:
            return ""

        lines: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            summary = doc.summary or _brief_summary(doc.content)
            version = _detect_version(doc.content)
            lines.append(f"- {rel_path} [{version}]: {summary}")
        return "\n".join(lines)
