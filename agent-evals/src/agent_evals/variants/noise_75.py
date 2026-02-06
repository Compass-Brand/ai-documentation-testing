"""Axis 7 noise variant: 75% noise.

For every real file, generates 3 distractor entries.  The index is
heavily diluted with fake entries.  Distractors are interspersed with
real entries and the combined list is sorted alphabetically by path.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


def _brief_summary(content: str, max_chars: int = 80) -> str:
    """Extract a brief summary from content."""
    for line in content.splitlines():
        stripped = line.strip().lstrip("# ")
        if stripped:
            return stripped[:max_chars]
    return ""


_DISTRACTOR_SUMMARIES = [
    "Internal reference document",
    "Auto-generated configuration stub",
    "Legacy migration notes",
    "Temporary scaffolding overview",
    "Deprecated helper utilities",
    "Build system integration notes",
    "Draft specification placeholder",
    "Compatibility shim documentation",
    "Generated type definitions",
    "Archived design decision log",
]


def _generate_distractors(count: int, rng: random.Random) -> list[tuple[str, str]]:
    """Generate *count* distractor entries as (path, summary) pairs."""
    distractors: list[tuple[str, str]] = []
    for i in range(count):
        path = f"docs/internal/generated_{i + 1:03d}.md"
        summary = rng.choice(_DISTRACTOR_SUMMARIES)
        distractors.append((path, summary))
    return distractors


@register_variant
class Noise75Variant(IndexVariant):
    """75% noise: 3 distractors per real file.

    Heavily diluted index where only 25% of entries are real files.
    Distractors are fake file entries with plausible paths and generic
    summaries, interspersed among real entries and sorted alphabetically.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the 75% noise variant."""
        return VariantMetadata(
            name="noise-75",
            axis=7,
            category="noise",
            description="Heavily diluted index with 75% distractor entries.",
            token_estimate=1200,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render files plus 75% noise distractors.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            A newline-separated bulleted list mixing real and fake entries.
        """
        if not doc_tree.files:
            return ""

        rng = random.Random(42)  # noqa: S311

        # Build real entries
        entries: list[tuple[str, str]] = []
        for rel_path in doc_tree.files:
            doc = doc_tree.files[rel_path]
            entries.append((rel_path, _brief_summary(doc.content)))

        # Generate distractors: 3 per real file
        num_distractors = len(entries) * 3
        distractors = _generate_distractors(num_distractors, rng)
        entries.extend(distractors)

        # Sort alphabetically and render
        entries.sort(key=lambda e: e[0])
        return "\n".join(f"- {path}: {summary}" for path, summary in entries)
