"""Random position variant (Axis 4).

Files are placed in a shuffled random order using a deterministic seed
(``seed=42``) so that results are reproducible across runs.  This variant
controls for any ordering effects that might bias the evaluation.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from agent_evals.variants._utils import render_two_tier as _render_two_tier
from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocFile, DocTree


@register_variant
class PositionRandom(IndexVariant):
    """Files in deterministically shuffled random order (seed=42)."""

    def metadata(self) -> VariantMetadata:
        """Return metadata for the random position variant."""
        return VariantMetadata(
            name="position-random",
            axis=4,
            category="position",
            description="Shuffled random order (seed=42) to control for order effects.",
            token_estimate=400,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render the doc tree with files in random (deterministic) order.

        Args:
            doc_tree: Parsed documentation tree to render.

        Returns:
            Markdown string with files in shuffled order (seed=42).
        """
        rng = random.Random(42)  # noqa: S311
        docs = list(doc_tree.files.values())
        rng.shuffle(docs)
        return _render_two_tier(docs)
