"""Bug #187: Noise variants at different levels must produce different distractors.

All noise variants (25%, 50%, 75%) used seed=42, producing identical distractor
paths regardless of noise level. Each level should use a distinct seed.
"""

from __future__ import annotations

from unittest.mock import MagicMock


def _make_doc_tree(num_files: int = 6) -> MagicMock:
    """Create a minimal mock DocTree with the given number of files."""
    from agent_index.models import DocFile

    tree = MagicMock()
    files = {}
    for i in range(num_files):
        rel_path = f"docs/file_{i}.md"
        doc = MagicMock(spec=DocFile)
        doc.content = f"# File {i}\n\nContent for file {i}."
        files[rel_path] = doc
    tree.files = files
    return tree


def _extract_distractor_paths(output: str) -> set[str]:
    """Extract distractor paths (docs/internal/generated_*) from rendered output."""
    paths = set()
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("- docs/internal/generated_"):
            path = line.split(":")[0].lstrip("- ").strip()
            paths.add(path)
    return paths


class TestNoiseVariantDistinctSeeds:
    """Bug #187: Different noise levels must produce different distractor sequences."""

    def test_noise_25_and_50_produce_different_distractors(self) -> None:
        from agent_evals.variants.noise_25 import Noise25Variant
        from agent_evals.variants.noise_50 import Noise50Variant

        doc_tree = _make_doc_tree(6)

        output_25 = Noise25Variant().render(doc_tree)
        output_50 = Noise50Variant().render(doc_tree)

        distractors_25 = _extract_distractor_paths(output_25)
        distractors_50 = _extract_distractor_paths(output_50)

        # Both should have distractors
        assert len(distractors_25) > 0
        assert len(distractors_50) > 0

        # The distractor counts differ (25% has fewer), but the paths are
        # generated deterministically — with same seed they'd overlap fully.
        # With different seeds, the summaries assigned should differ.
        # Since paths are sequential (generated_001, etc.), we check summaries instead.

    def test_noise_25_50_75_produce_different_summary_sequences(self) -> None:
        """The summary text assigned to distractors must differ across levels."""
        from agent_evals.variants.noise_25 import Noise25Variant
        from agent_evals.variants.noise_50 import Noise50Variant
        from agent_evals.variants.noise_75 import Noise75Variant

        doc_tree = _make_doc_tree(6)

        output_25 = Noise25Variant().render(doc_tree)
        output_50 = Noise50Variant().render(doc_tree)
        output_75 = Noise75Variant().render(doc_tree)

        def distractor_summaries(output: str) -> list[str]:
            """Extract summaries of distractor entries in order."""
            summaries = []
            for line in sorted(output.splitlines()):
                if "docs/internal/generated_" in line:
                    # Format: "- docs/internal/generated_001.md: Summary text"
                    parts = line.split(": ", 1)
                    if len(parts) == 2:
                        summaries.append(parts[1])
            return summaries

        sums_25 = distractor_summaries(output_25)
        sums_50 = distractor_summaries(output_50)
        sums_75 = distractor_summaries(output_75)

        # All should have distractors
        assert len(sums_25) > 0
        assert len(sums_50) > 0
        assert len(sums_75) > 0

        # Compare the overlapping prefix (shortest list length)
        min_len = min(len(sums_25), len(sums_50), len(sums_75))
        prefix_25 = sums_25[:min_len]
        prefix_50 = sums_50[:min_len]
        prefix_75 = sums_75[:min_len]

        # With distinct seeds, at least one pair should differ
        assert not (prefix_25 == prefix_50 == prefix_75), (
            "All noise levels produced identical distractor summaries — "
            "they likely share the same random seed"
        )
