"""Axis 10 temporal variant: deprecation markers.

Scans file content for deprecation signals (``@deprecated``, ``DEPRECATED``,
``obsolete``, ``legacy``, ``no longer supported``) and tags each entry as
either ``[DEPRECATED]`` or ``[CURRENT]``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from agent_evals.variants._utils import brief_summary as _brief_summary
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree

# Pattern that matches common deprecation signals (case-insensitive).
_DEPRECATION_PATTERN: re.Pattern[str] = re.compile(
    r"@deprecated|DEPRECATED|obsolete|legacy|no longer supported",
    re.IGNORECASE,
)


def _is_deprecated(content: str) -> bool:
    """Check whether content contains deprecation signals."""
    return bool(_DEPRECATION_PATTERN.search(content))


@register_variant
class TemporalDeprecatedVariant(IndexVariant):
    """Deprecation markers based on content scanning.

    Files whose content matches deprecation signals are tagged
    ``[DEPRECATED]``; all others receive ``[CURRENT]``.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the deprecated-temporal variant."""
        return VariantMetadata(
            name="temporal-deprecated",
            axis=10,
            category="temporal",
            description="Adds deprecation markers detected from content signals.",
            token_estimate=350,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render files with deprecation status tags.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            A bulleted list with ``[DEPRECATED]`` or ``[CURRENT]`` tags.
        """
        if not doc_tree.files:
            return ""

        lines: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            summary = doc.summary or _brief_summary(doc.content)
            tag = "[DEPRECATED]" if _is_deprecated(doc.content) else "[CURRENT]"
            lines.append(f"- {rel_path} {tag}: {summary}")
        return "\n".join(lines)
