"""YAML format variant (Axis 3).

Renders the documentation index as a YAML document with a ``files`` list,
one mapping per file.  Structured and human-readable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import yaml

from agent_evals.variants._utils import summarise as _summarise
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


def _yaml_safe_value(value: str) -> str:
    """Serialize a string so it is safe to embed as a YAML scalar value.

    Collapses newlines to spaces first since index values are single-line,
    then delegates to ``yaml.safe_dump`` for proper quoting of special
    characters (colons, hashes, etc.).
    """
    clean = value.replace("\n", " ")
    return yaml.safe_dump(clean).splitlines()[0]


@register_variant
class FormatYaml(IndexVariant):
    """Render the documentation index as YAML.

    Example output::

        files:
          - path: api/auth.md
            section: API
            tier: required
            tokens: 450
            summary: JWT authentication with AuthMiddleware
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the YAML format variant."""
        return VariantMetadata(
            name="format-yaml",
            axis=3,
            category="format",
            description="YAML format for structured, human-readable indexes.",
            token_estimate=500,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render the doc tree as a YAML document.

        Args:
            doc_tree: Parsed documentation tree to render.

        Returns:
            YAML string with a ``files`` list.
        """
        lines: list[str] = ["files:"]
        for _key, doc in sorted(doc_tree.files.items()):
            summary = doc.summary if doc.summary else _summarise(doc.content)
            tokens = doc.token_count if doc.token_count is not None else 0
            lines.append(f"  - path: {_yaml_safe_value(doc.rel_path)}")
            lines.append(f"    section: {_yaml_safe_value(doc.section)}")
            lines.append(f"    tier: {_yaml_safe_value(doc.tier)}")
            lines.append(f"    tokens: {tokens}")
            lines.append(f"    summary: {_yaml_safe_value(summary)}")
        return "\n".join(lines)
