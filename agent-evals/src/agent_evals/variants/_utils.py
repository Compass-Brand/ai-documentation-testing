"""Shared utility functions for index variant implementations.

Extracted from duplicated inline helpers found across 30+ variant files.
These functions are the canonical implementations -- variant modules
should import from here instead of defining their own copies.
"""

from __future__ import annotations

import random
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_index.models import DocFile

# ---------------------------------------------------------------------------
# Distractor summaries (used by noise variants)
# ---------------------------------------------------------------------------

DISTRACTOR_SUMMARIES: list[str] = [
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


# ---------------------------------------------------------------------------
# brief_summary
# ---------------------------------------------------------------------------


def brief_summary(content: str, max_chars: int = 80) -> str:
    """Extract a brief summary from content.

    Takes the first non-empty line, strips leading ``#`` and whitespace,
    and truncates to *max_chars*.

    Args:
        content: Raw text content to summarise.
        max_chars: Maximum character length for the returned summary.

    Returns:
        A short summary string, or ``""`` if no non-empty line is found.
    """
    for line in content.splitlines():
        stripped = line.strip().lstrip("# ")
        if stripped:
            return stripped[:max_chars]
    return ""


# ---------------------------------------------------------------------------
# summarise
# ---------------------------------------------------------------------------


def summarise(content: str) -> str:
    """Return first line or first ~100 chars of content as a summary.

    If the first line exceeds 100 characters it is truncated to 97
    characters with a trailing ``...`` ellipsis.

    Args:
        content: Raw text content to summarise.

    Returns:
        A one-line summary string.
    """
    first_line = content.split("\n", 1)[0].strip()
    if len(first_line) > 100:
        return first_line[:97] + "..."
    return first_line


# ---------------------------------------------------------------------------
# render_two_tier
# ---------------------------------------------------------------------------


def render_two_tier(ordered_docs: list[DocFile]) -> str:
    """Render a list of DocFile objects using the 2-tier section format.

    Groups files by section and renders each group under a Markdown heading,
    preserving the order of first appearance.

    Args:
        ordered_docs: Files in the desired display order.

    Returns:
        Markdown string with section headings and file entries.
    """
    sections: dict[str, list[DocFile]] = defaultdict(list)
    section_order: list[str] = []
    for doc in ordered_docs:
        if doc.section not in sections:
            section_order.append(doc.section)
        sections[doc.section].append(doc)

    lines: list[str] = ["# Documentation Index"]
    for section_name in section_order:
        lines.append("")
        lines.append(f"## {section_name}")
        for doc in sections[section_name]:
            summary = doc.summary if doc.summary else summarise(doc.content)
            tokens = doc.token_count if doc.token_count is not None else 0
            lines.append(
                f"- {doc.rel_path} ({doc.tier}, ~{tokens} tokens) -- {summary}"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# generate_distractors
# ---------------------------------------------------------------------------


def generate_distractors(
    count: int, rng: random.Random
) -> list[tuple[str, str]]:
    """Generate *count* distractor entries as ``(path, summary)`` pairs.

    Paths follow the pattern ``docs/internal/generated_NNN.md`` with
    1-based zero-padded indices.  Summaries are randomly selected from
    :data:`DISTRACTOR_SUMMARIES`.

    Args:
        count: Number of distractor entries to generate.
        rng: Seeded :class:`random.Random` instance for reproducibility.

    Returns:
        A list of ``(path, summary)`` tuples.
    """
    distractors: list[tuple[str, str]] = []
    for i in range(count):
        path = f"docs/internal/generated_{i + 1:03d}.md"
        summary = rng.choice(DISTRACTOR_SUMMARIES)
        distractors.append((path, summary))
    return distractors
