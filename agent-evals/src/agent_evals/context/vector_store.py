"""In-memory vector store with cosine similarity search.

Read-only after construction -- thread-safe for concurrent searches.
"""

from __future__ import annotations

import numpy as np


class InMemoryVectorStore:
    """Stores (chunk_text, embedding_vector) pairs for similarity search.

    Parameters
    ----------
    chunks:
        List of chunk text strings.
    embeddings:
        2-D numpy array of shape ``(len(chunks), dim)``.  Each row is
        the embedding vector for the corresponding chunk.
    """

    def __init__(self, chunks: list[str], embeddings: np.ndarray) -> None:
        self._chunks = list(chunks)
        self._embeddings = np.array(embeddings, dtype=np.float64)

        # Pre-compute norms for cosine similarity
        if self._embeddings.size > 0:
            norms = np.linalg.norm(self._embeddings, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1.0, norms)
            self._normed = self._embeddings / norms
        else:
            self._normed = self._embeddings

    def search(
        self, query_embedding: np.ndarray, top_k: int = 5,
    ) -> list[tuple[str, float]]:
        """Return the *top_k* most similar chunks to *query_embedding*.

        Returns a list of ``(chunk_text, cosine_similarity)`` tuples
        sorted by descending similarity.
        """
        if len(self._chunks) == 0:
            return []

        query = np.array(query_embedding, dtype=np.float64)
        query_norm = np.linalg.norm(query)
        if query_norm == 0:
            return [(c, 0.0) for c in self._chunks[:top_k]]

        normed_query = query / query_norm
        similarities = self._normed @ normed_query

        k = min(top_k, len(self._chunks))
        top_indices = np.argsort(similarities)[::-1][:k]

        return [
            (self._chunks[i], float(similarities[i]))
            for i in top_indices
        ]
