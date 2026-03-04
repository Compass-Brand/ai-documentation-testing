"""CompositeVariant - combines one variant per axis into a single render.

Used by TaguchiRunner to create combined configurations from orthogonal
array rows, where each row specifies one variant level per axis.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata

if TYPE_CHECKING:
    from agent_index.models import DocTree

_H1_RE = re.compile(r"^# .+$", re.MULTILINE)


def _dedup_h1(text: str, seen: set[str]) -> str:
    """Remove leading H1 header from *text* if already in *seen*.

    Updates *seen* in place with any new header found.
    """
    match = _H1_RE.match(text)
    if match is None:
        return text
    header = match.group(0)
    if header in seen:
        # Strip the duplicate header and any trailing blank line
        return text[match.end():].lstrip("\n")
    seen.add(header)
    return text


class CompositeVariant(IndexVariant):
    """Variant that delegates to one sub-variant per axis.

    Args:
        components: Mapping of axis number to variant instance.
            Must contain at least one entry.
    """

    def __init__(self, components: dict[int, IndexVariant]) -> None:
        if not components:
            raise ValueError("CompositeVariant requires at least one component")
        self._components = components
        self._sorted_axes = sorted(components.keys())

    def metadata(self) -> VariantMetadata:
        """Return composite metadata combining all component names."""
        names = [
            self._components[axis].metadata().name
            for axis in self._sorted_axes
        ]
        estimates = [
            self._components[axis].metadata().token_estimate
            for axis in self._sorted_axes
        ]
        return VariantMetadata(
            name="+".join(names),
            axis=0,
            category="composite",
            description=f"Composite of {len(self._components)} variants",
            token_estimate=sum(estimates),
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render each component in axis order and concatenate.

        Duplicate H1 markdown headers across components are collapsed so that
        only the first occurrence is kept.
        """
        parts: list[str] = []
        seen_headers: set[str] = set()
        for axis in self._sorted_axes:
            text = self._components[axis].render(doc_tree)
            text = _dedup_h1(text, seen_headers)
            parts.append(text)
        return "\n\n".join(parts)

    def setup(self, doc_tree: DocTree) -> None:
        """Delegate setup to all components in axis order."""
        for axis in self._sorted_axes:
            self._components[axis].setup(doc_tree)

    def teardown(self) -> None:
        """Delegate teardown to all components."""
        for axis in self._sorted_axes:
            self._components[axis].teardown()
