"""Faithfulness metric: keyword-overlap approximation.

The real NLI-based implementation will decompose the response into claims
and verify each against source documents using an LLM.  This placeholder
uses token-level overlap as a cheap proxy until the LLM client (Story 2.9)
is integrated.
"""

from __future__ import annotations

import re

from agent_evals.metrics.base import Metric, MetricContext

# Words that carry little semantic weight and should be excluded from overlap.
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "about",
        "between",
        "through",
        "and",
        "but",
        "or",
        "nor",
        "not",
        "so",
        "yet",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "i",
        "we",
        "you",
        "he",
        "she",
        "they",
        "me",
        "him",
        "her",
        "us",
        "them",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    """Lowercase tokenization, keeping only alphanumeric tokens."""
    return _TOKEN_RE.findall(text.lower())


class FaithfulnessMetric(Metric):
    """Fraction of response content words found in source documents.

    This is a keyword-overlap approximation.  The real implementation will
    use NLI-based claim decomposition via the LLM client.

    Score semantics:
        1.0 = every content word in the response appears in the sources.
        0.0 = no overlap, or empty input.
    """

    @property
    def name(self) -> str:  # noqa: D102
        return "faithfulness"

    def compute(self, response: str, context: MetricContext) -> float:
        """Compute keyword-overlap faithfulness score.

        Args:
            response: The agent's textual response.
            context: Must contain ``source_documents``.

        Returns:
            Float in ``[0.0, 1.0]``.
        """
        response_tokens = [
            t for t in _tokenize(response) if t not in _STOP_WORDS
        ]
        if not response_tokens:
            return 0.0

        if not context.source_documents:
            return 0.0

        source_tokens: set[str] = set()
        for doc in context.source_documents:
            source_tokens.update(_tokenize(doc))

        supported = sum(1 for t in response_tokens if t in source_tokens)
        return supported / len(response_tokens)
