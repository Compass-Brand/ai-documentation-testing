"""Axis 7 noise variant: 25% noise.

For every 3 real files, generates 1 distractor entry with a plausible
path and generic summary.  Distractors are interspersed with real entries
and the combined list is sorted alphabetically by path.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from agent_evals.variants._utils import brief_summary as _brief_summary
from agent_evals.variants._utils import generate_distractors as _generate_distractors
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


@register_variant
class Noise25Variant(IndexVariant):
    """25% noise: 1 distractor per 3 real files.

    Distractors are fake file entries with plausible paths and generic
    summaries, interspersed among real entries and sorted alphabetically.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the 25% noise variant."""
        return VariantMetadata(
            name="noise-25",
            axis=7,
            category="noise",
            description="Index with 25% distractor entries mixed in.",
            token_estimate=400,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render files plus 25% noise distractors.

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

        # Generate distractors: 1 per 3 real files (rounded up)
        num_distractors = max(1, len(entries) // 3)
        distractors = _generate_distractors(num_distractors, rng)
        entries.extend(distractors)

        # Sort alphabetically and render
        entries.sort(key=lambda e: e[0])
        return "\n".join(f"- {path}: {summary}" for path, summary in entries)
