"""Text chunking strategies for RAG context mode.

Provides:
- ``fixed_size_chunks``: Split by approximate token count at whitespace.
- ``heading_chunks``: Split on ``#``/``##`` markdown heading markers.
"""

from __future__ import annotations

import re


def fixed_size_chunks(text: str, chunk_size: int = 200) -> list[str]:
    """Split *text* into chunks of approximately *chunk_size* tokens.

    Uses whitespace splitting as a proxy for token boundaries
    (approximately 1 token per whitespace-delimited word).

    Returns an empty list for blank input.
    """
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_count = 0

    for word in words:
        current.append(word)
        current_count += 1
        if current_count >= chunk_size:
            chunks.append(" ".join(current))
            current = []
            current_count = 0

    if current:
        chunks.append(" ".join(current))

    return chunks


# Matches lines that start with one or more ``#`` followed by a space,
# at the beginning of a line (after optional leading whitespace).
_HEADING_RE = re.compile(r"^(?=#{1,6}\s)", re.MULTILINE)


def heading_chunks(text: str) -> list[str]:
    """Split *text* on markdown heading markers (``#`` through ``######``).

    Each heading starts a new chunk.  Content before the first heading
    (preamble) is returned as its own chunk.  Returns an empty list for
    blank input.
    """
    if not text or not text.strip():
        return []

    parts = _HEADING_RE.split(text)
    chunks = [p.strip() for p in parts if p.strip()]
    return chunks
