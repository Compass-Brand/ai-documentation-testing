"""Fact extraction task type for evaluating factual accuracy.

Scores responses using keyword matching: exact/alias match yields 1.0,
fallback computes fraction of non-stopword keywords found in the response.
"""

from __future__ import annotations

from agent_evals.tasks.base import EvalTask, TaskDefinition, register_task_type

# Common English stopwords to exclude from keyword matching
_STOPWORDS: frozenset[str] = frozenset({
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


class FactExtractionTask(EvalTask):
    """Task type for evaluating factual answer accuracy.

    Checks if the expected answer or any alias appears in the response
    (exact match = 1.0). Falls back to computing the fraction of
    non-stopword keywords from the expected answer found in the response.
    """

    def __init__(self, definition: TaskDefinition) -> None:
        super().__init__(definition)
        meta = definition.metadata
        self.expected_answer: str = meta.get("expected_answer", "")
        self.answer_aliases: list[str] = meta.get("answer_aliases", [])
        self.source_location: str = meta.get("source_location", "")
        self.fact_type: str = meta.get("fact_type", "")

    def build_prompt(self, index_content: str) -> list[dict[str, str]]:
        """Build messages for fact extraction evaluation.

        Args:
            index_content: The documentation index content.

        Returns:
            List of message dicts with system and user messages.
        """
        return [
            {
                "role": "system",
                "content": (
                    "You are an AI assistant that answers factual questions "
                    "using information from a documentation index. Provide "
                    "concise, accurate answers.\n\n"
                    f"{index_content}"
                ),
            },
            {
                "role": "user",
                "content": self.definition.question,
            },
        ]

    def score_response(self, response: str, **kwargs: object) -> float:
        """Score response using keyword matching against expected answer.

        Checks for exact match of expected_answer or any alias first.
        Falls back to computing fraction of non-stopword keywords found.

        Args:
            response: The raw text response from the LLM.
            **kwargs: Additional scoring context (unused).

        Returns:
            Score between 0.0 and 1.0.
        """
        if not self.expected_answer:
            return 0.0

        response_lower = response.lower()

        # Check exact match of expected answer
        if self.expected_answer.lower() in response_lower:
            return 1.0

        # Check alias matches
        for alias in self.answer_aliases:
            if alias.lower() in response_lower:
                return 1.0

        # Fallback: keyword matching
        keywords = self._extract_keywords(self.expected_answer)
        if not keywords:
            return 0.0

        matched = sum(1 for kw in keywords if kw.lower() in response_lower)
        return max(0.0, min(1.0, matched / len(keywords)))

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
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
            if len(w) >= 3 and w.lower() not in _STOPWORDS
        ]


register_task_type("fact_extraction", FactExtractionTask)
