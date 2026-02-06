"""Shared utilities for task scoring.

Provides stopword filtering and keyword extraction used by multiple
task types for keyword-based response scoring.
"""

from __future__ import annotations

# Common English stopwords to exclude from keyword matching.
STOPWORDS: frozenset[str] = frozenset({
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "had",
    "her", "was", "one", "our", "out", "has", "have", "been", "some", "them",
    "than", "its", "over", "such", "that", "this", "with", "will", "each",
    "from", "they", "said", "into", "more", "other", "which", "their",
    "about", "would", "make", "just", "should", "could", "also", "after",
    "use", "two", "how", "when", "what", "where", "who", "may", "did", "get",
    "does", "any", "being", "between", "same", "she", "him", "his", "only",
    "see", "now", "way", "very", "most", "these", "those", "then", "first",
    "were", "there", "through",
})


def extract_keywords(text: str) -> list[str]:
    """Extract non-stopword keywords from text.

    Filters to words with 3+ characters that are not common
    English stopwords.

    Args:
        text: The text to extract keywords from.

    Returns:
        List of keyword strings.
    """
    words = text.split()
    return [
        w for w in words
        if len(w) >= 3 and w.lower() not in STOPWORDS
    ]
