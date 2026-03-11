"""Tests for Phase 3 RAG context strategy modules.

Tests cover:
- Fixed-size chunking produces correct chunk sizes
- Heading-based chunking splits on headers
- Embedder produces vectors (mock litellm.embedding)
- Embedder caching (same content -> cached, different -> new call)
- Vector store cosine similarity returns correct top-K
- RAGStrategy.setup() creates chunks and embeddings
- RAGStrategy.prepare() retrieves relevant chunks
- RAGStrategy.execute() wraps response correctly
- RAGStrategy metadata includes retrieval info
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from conftest import make_mock_client, make_mock_task


# ---------------------------------------------------------------------------
# Chunkers
# ---------------------------------------------------------------------------


class TestFixedSizeChunker:
    """Fixed-size chunker splits text by approximate token count."""

    def test_single_chunk_when_under_limit(self):
        from agent_evals.context.chunkers import fixed_size_chunks

        text = "Hello world this is a test."
        chunks = fixed_size_chunks(text, chunk_size=1000)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_splits_into_multiple_chunks(self):
        from agent_evals.context.chunkers import fixed_size_chunks

        # Create text with known word count; use a small chunk size
        words = ["word"] * 100
        text = " ".join(words)
        chunks = fixed_size_chunks(text, chunk_size=10)
        assert len(chunks) > 1
        # Reassembled content preserves all words
        reassembled = " ".join(chunks)
        assert reassembled.split() == text.split()

    def test_empty_text_returns_empty_list(self):
        from agent_evals.context.chunkers import fixed_size_chunks

        assert fixed_size_chunks("", chunk_size=100) == []

    def test_whitespace_only_returns_empty_list(self):
        from agent_evals.context.chunkers import fixed_size_chunks

        assert fixed_size_chunks("   \n\n  ", chunk_size=100) == []

    def test_respects_approximate_token_budget(self):
        from agent_evals.context.chunkers import fixed_size_chunks

        # Each "word" is ~1 token with the //4 heuristic (4 chars + space)
        words = [f"w{i:03d}" for i in range(200)]
        text = " ".join(words)
        chunks = fixed_size_chunks(text, chunk_size=50)
        # Each chunk should have roughly 50 tokens or less (with some tolerance)
        for chunk in chunks:
            # Approximate: each word is ~1 token
            word_count = len(chunk.split())
            assert word_count <= 60, f"Chunk too large: {word_count} words"

    def test_uses_count_tokens_not_word_count(self):
        """Fixed-size chunker must use count_tokens() for accurate token budgets."""
        from agent_evals.context.chunkers import fixed_size_chunks

        # "authentication" is 1 word but multiple tokens in most tokenizers.
        # With the len//4 fallback, "authentication" = 14 chars // 4 = 3 tokens.
        # A word-count approach would treat it as 1.
        # Build text where word count != token count significantly.
        words = ["authentication"] * 20  # 20 words, ~60 tokens (14*20//4)
        text = " ".join(words)

        with patch(
            "agent_evals.context.chunkers.count_tokens",
            side_effect=lambda t, **kw: len(t) // 4,
        ) as mock_ct:
            chunks = fixed_size_chunks(text, chunk_size=10)
            # count_tokens must have been called (not word counting)
            assert mock_ct.call_count > 0, (
                "fixed_size_chunks should use count_tokens(), not word counting"
            )


class TestHeadingBasedChunker:
    """Heading-based chunker splits on # and ## markers."""

    def test_splits_on_h1_headers(self):
        from agent_evals.context.chunkers import heading_chunks

        text = "# First\nContent 1\n# Second\nContent 2"
        chunks = heading_chunks(text)
        assert len(chunks) == 2
        assert "# First" in chunks[0]
        assert "Content 1" in chunks[0]
        assert "# Second" in chunks[1]
        assert "Content 2" in chunks[1]

    def test_splits_on_h2_headers(self):
        from agent_evals.context.chunkers import heading_chunks

        text = "## Section A\nText A\n## Section B\nText B"
        chunks = heading_chunks(text)
        assert len(chunks) == 2
        assert "## Section A" in chunks[0]
        assert "## Section B" in chunks[1]

    def test_preserves_heading_in_chunk(self):
        from agent_evals.context.chunkers import heading_chunks

        text = "# Title\nBody text here"
        chunks = heading_chunks(text)
        assert len(chunks) == 1
        assert chunks[0].startswith("# Title")

    def test_preamble_before_first_heading(self):
        from agent_evals.context.chunkers import heading_chunks

        text = "Preamble text\n# First Section\nContent"
        chunks = heading_chunks(text)
        assert len(chunks) == 2
        assert "Preamble text" in chunks[0]
        assert "# First Section" in chunks[1]

    def test_empty_text_returns_empty_list(self):
        from agent_evals.context.chunkers import heading_chunks

        assert heading_chunks("") == []

    def test_no_headings_returns_single_chunk(self):
        from agent_evals.context.chunkers import heading_chunks

        text = "Just plain text\nwith some lines."
        chunks = heading_chunks(text)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_mixed_heading_levels(self):
        from agent_evals.context.chunkers import heading_chunks

        text = "# H1\nContent\n## H2\nMore content\n# Another H1\nFinal"
        chunks = heading_chunks(text)
        assert len(chunks) == 3


# ---------------------------------------------------------------------------
# Embedder
# ---------------------------------------------------------------------------


class TestEmbedder:
    """Embedder wraps litellm.embedding() with content-hash caching."""

    def test_produces_embedding_vector(self):
        from agent_evals.context.embedder import Embedder

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]

        with patch("agent_evals.context.embedder.litellm.embedding", return_value=mock_response) as mock_embed:
            embedder = Embedder(model="text-embedding-3-small")
            vec = embedder.embed("hello world")

        mock_embed.assert_called_once()
        assert isinstance(vec, np.ndarray)
        assert vec.shape == (3,)
        np.testing.assert_array_almost_equal(vec, [0.1, 0.2, 0.3])

    def test_caching_same_content_no_repeat_call(self):
        from agent_evals.context.embedder import Embedder

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]

        with patch("agent_evals.context.embedder.litellm.embedding", return_value=mock_response) as mock_embed:
            embedder = Embedder(model="text-embedding-3-small")
            vec1 = embedder.embed("hello world")
            vec2 = embedder.embed("hello world")

        # Should only call the API once due to caching
        assert mock_embed.call_count == 1
        np.testing.assert_array_equal(vec1, vec2)

    def test_different_content_makes_separate_calls(self):
        from agent_evals.context.embedder import Embedder

        response1 = MagicMock()
        response1.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]
        response2 = MagicMock()
        response2.data = [MagicMock(embedding=[0.4, 0.5, 0.6])]

        with patch("agent_evals.context.embedder.litellm.embedding", side_effect=[response1, response2]) as mock_embed:
            embedder = Embedder(model="text-embedding-3-small")
            vec1 = embedder.embed("hello")
            vec2 = embedder.embed("world")

        assert mock_embed.call_count == 2
        assert not np.array_equal(vec1, vec2)

    def test_embed_batch(self):
        from agent_evals.context.embedder import Embedder

        mock_response = MagicMock()
        mock_response.data = [
            MagicMock(embedding=[0.1, 0.2]),
            MagicMock(embedding=[0.3, 0.4]),
        ]

        with patch("agent_evals.context.embedder.litellm.embedding", return_value=mock_response):
            embedder = Embedder(model="text-embedding-3-small")
            vecs = embedder.embed_batch(["hello", "world"])

        assert len(vecs) == 2
        assert vecs[0].shape == (2,)
        assert vecs[1].shape == (2,)

    def test_disk_cache_persistence(self, tmp_path):
        from agent_evals.context.embedder import Embedder

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1, 0.2, 0.3])]

        with patch("agent_evals.context.embedder.litellm.embedding", return_value=mock_response) as mock_embed:
            # First embedder instance
            embedder1 = Embedder(model="text-embedding-3-small", cache_dir=tmp_path)
            vec1 = embedder1.embed("hello")
            assert mock_embed.call_count == 1

        # New embedder instance with same cache dir should find cached result
        with patch("agent_evals.context.embedder.litellm.embedding", return_value=mock_response) as mock_embed2:
            embedder2 = Embedder(model="text-embedding-3-small", cache_dir=tmp_path)
            vec2 = embedder2.embed("hello")
            assert mock_embed2.call_count == 0

        np.testing.assert_array_equal(vec1, vec2)


# ---------------------------------------------------------------------------
# Vector Store
# ---------------------------------------------------------------------------


class TestInMemoryVectorStore:
    """InMemoryVectorStore stores chunks with embeddings and searches by cosine similarity."""

    def test_search_returns_top_k(self):
        from agent_evals.context.vector_store import InMemoryVectorStore

        chunks = ["chunk A", "chunk B", "chunk C"]
        embeddings = np.array([
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ])
        store = InMemoryVectorStore(chunks, embeddings)

        # Query most similar to chunk A
        query = np.array([0.9, 0.1, 0.0])
        results = store.search(query, top_k=2)

        assert len(results) == 2
        assert results[0][0] == "chunk A"  # Most similar
        assert results[0][1] > results[1][1]  # Scores descending

    def test_search_cosine_similarity_correctness(self):
        from agent_evals.context.vector_store import InMemoryVectorStore

        chunks = ["parallel", "orthogonal"]
        embeddings = np.array([
            [1.0, 0.0],
            [0.0, 1.0],
        ])
        store = InMemoryVectorStore(chunks, embeddings)

        # Query exactly parallel to first chunk
        query = np.array([1.0, 0.0])
        results = store.search(query, top_k=2)

        assert results[0][0] == "parallel"
        assert abs(results[0][1] - 1.0) < 1e-6  # cosine sim = 1.0
        assert abs(results[1][1] - 0.0) < 1e-6  # cosine sim = 0.0

    def test_top_k_larger_than_store(self):
        from agent_evals.context.vector_store import InMemoryVectorStore

        chunks = ["only one"]
        embeddings = np.array([[1.0, 0.0]])
        store = InMemoryVectorStore(chunks, embeddings)

        results = store.search(np.array([1.0, 0.0]), top_k=5)
        assert len(results) == 1

    def test_empty_store(self):
        from agent_evals.context.vector_store import InMemoryVectorStore

        store = InMemoryVectorStore([], np.empty((0, 3)))
        results = store.search(np.array([1.0, 0.0, 0.0]), top_k=3)
        assert len(results) == 0

    def test_returns_tuples_of_text_and_score(self):
        from agent_evals.context.vector_store import InMemoryVectorStore

        chunks = ["test"]
        embeddings = np.array([[1.0, 0.0]])
        store = InMemoryVectorStore(chunks, embeddings)

        results = store.search(np.array([1.0, 0.0]), top_k=1)
        assert len(results) == 1
        text, score = results[0]
        assert isinstance(text, str)
        assert isinstance(score, float)


# ---------------------------------------------------------------------------
# RAGStrategy
# ---------------------------------------------------------------------------


class TestRAGStrategy:
    """RAGStrategy orchestrates chunking, embedding, and retrieval."""

    def _make_rag_strategy(self, *, chunk_method="heading", top_k=3, model="text-embedding-3-small"):
        from agent_evals.context.rag import RAGStrategy

        return RAGStrategy(
            chunk_method=chunk_method,
            top_k=top_k,
            embedding_model=model,
        )

    def test_name(self):
        strategy = self._make_rag_strategy()
        assert strategy.name() == "rag"

    def test_supports_caching(self):
        strategy = self._make_rag_strategy()
        assert strategy.supports_caching() is True

    @patch("agent_evals.context.rag.Embedder")
    def test_setup_creates_chunks_and_embeddings(self, MockEmbedder):
        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [
            np.array([0.1, 0.2]),
            np.array([0.3, 0.4]),
        ]
        MockEmbedder.return_value = mock_embedder

        strategy = self._make_rag_strategy()
        rendered_index = "# Section 1\nContent 1\n# Section 2\nContent 2"
        doc_tree = MagicMock()

        strategy.setup(rendered_index, doc_tree)

        # Should have created chunks and embedded them
        mock_embedder.embed_batch.assert_called_once()
        chunks_arg = mock_embedder.embed_batch.call_args[0][0]
        assert len(chunks_arg) == 2

    @patch("agent_evals.context.rag.Embedder")
    def test_prepare_retrieves_relevant_chunks(self, MockEmbedder):
        mock_embedder = MagicMock()
        # Embeddings for 2 chunks
        mock_embedder.embed_batch.return_value = [
            np.array([1.0, 0.0, 0.0]),
            np.array([0.0, 1.0, 0.0]),
        ]
        # Query embedding similar to chunk 1
        mock_embedder.embed.return_value = np.array([0.9, 0.1, 0.0])
        MockEmbedder.return_value = mock_embedder

        strategy = self._make_rag_strategy(top_k=1)
        rendered_index = "# Section 1\nContent about dogs\n# Section 2\nContent about cats"
        doc_tree = MagicMock()
        strategy.setup(rendered_index, doc_tree)

        task = make_mock_task()
        prepared = strategy.prepare(rendered_index, task, doc_tree)

        # Should embed the task question
        mock_embedder.embed.assert_called()
        # Prepared context should have messages
        assert len(prepared.messages) > 0
        # Metadata should have retrieval info
        assert "chunks_retrieved" in prepared.strategy_metadata
        assert "total_chunks" in prepared.strategy_metadata

    @patch("agent_evals.context.rag.Embedder")
    def test_prepare_metadata_includes_chunk_scores(self, MockEmbedder):
        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [
            np.array([1.0, 0.0]),
            np.array([0.0, 1.0]),
        ]
        mock_embedder.embed.return_value = np.array([1.0, 0.0])
        MockEmbedder.return_value = mock_embedder

        strategy = self._make_rag_strategy(top_k=2)
        strategy.setup("# A\nText A\n# B\nText B", MagicMock())

        task = make_mock_task()
        prepared = strategy.prepare("index", task, MagicMock())

        assert "chunk_scores" in prepared.strategy_metadata
        assert len(prepared.strategy_metadata["chunk_scores"]) <= 2

    @patch("agent_evals.context.rag.Embedder")
    def test_execute_calls_client_and_wraps_result(self, MockEmbedder):
        from agent_evals.context.base import PreparedContext
        from agent_evals.llm.client import GenerationResult

        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [np.array([1.0, 0.0])]
        mock_embedder.embed.return_value = np.array([1.0, 0.0])
        MockEmbedder.return_value = mock_embedder

        strategy = self._make_rag_strategy(top_k=1)
        strategy.setup("# Section\nContent", MagicMock())

        messages = [{"role": "user", "content": "test"}]
        prepared = PreparedContext(
            messages=messages,
            tools=None,
            strategy_metadata={"chunks_retrieved": 1, "total_chunks": 1, "chunk_scores": [1.0]},
        )

        client = make_mock_client()
        gen = GenerationResult(
            content="answer",
            prompt_tokens=50,
            completion_tokens=25,
            total_tokens=75,
            cost=0.002,
            model="mock-model",
            generation_id="gen-1",
        )
        client.complete.return_value = gen

        task = make_mock_task()
        result = strategy.execute(prepared, task, client, max_tokens=1024, temperature=0.3)

        client.complete.assert_called_once_with(
            messages,
            max_tokens=1024,
            temperature=0.3,
        )
        assert result.final_response == "answer"
        assert result.total_tokens == 75
        assert len(result.generations) == 1

    @patch("agent_evals.context.rag.Embedder")
    def test_setup_with_fixed_size_chunking(self, MockEmbedder):
        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [
            np.array([0.1, 0.2]),
        ] * 5  # Multiple chunks expected
        MockEmbedder.return_value = mock_embedder

        strategy = self._make_rag_strategy(chunk_method="fixed")
        # Long text that should produce multiple fixed-size chunks
        text = "word " * 500
        strategy.setup(text, MagicMock())

        mock_embedder.embed_batch.assert_called_once()
        chunks_arg = mock_embedder.embed_batch.call_args[0][0]
        assert len(chunks_arg) >= 1

    @patch("agent_evals.context.rag.Embedder")
    def test_prepare_builds_prompt_with_retrieved_chunks(self, MockEmbedder):
        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [
            np.array([1.0, 0.0]),
            np.array([0.0, 1.0]),
        ]
        mock_embedder.embed.return_value = np.array([1.0, 0.0])
        MockEmbedder.return_value = mock_embedder

        strategy = self._make_rag_strategy(top_k=1)
        strategy.setup("# Dogs\nDog content\n# Cats\nCat content", MagicMock())

        task = make_mock_task()
        prepared = strategy.prepare("index", task, MagicMock())

        # build_prompt is called twice: once for question extraction, once with retrieved chunks.
        # The final call (for context injection) should have non-empty content.
        calls = task.build_prompt.call_args_list
        assert len(calls) == 2
        # First call extracts the question (empty string)
        assert calls[0][0][0] == ""
        # Second call injects retrieved chunks
        context_arg = calls[1][0][0]
        assert isinstance(context_arg, str)
        assert len(context_arg) > 0

    def test_teardown_clears_state(self):
        strategy = self._make_rag_strategy()
        # teardown should not raise even before setup
        strategy.teardown()


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


class TestRAGQueryEmbeddingCache:
    """Bug #188: RAG strategy recomputes question embedding for each trial."""

    @patch("agent_evals.context.rag.Embedder")
    def test_same_question_embeds_once(self, MockEmbedder):
        """Calling prepare() twice with the same task should only embed the question once."""
        from agent_evals.context.rag import RAGStrategy

        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [
            np.array([1.0, 0.0]),
            np.array([0.0, 1.0]),
        ]
        mock_embedder.embed.return_value = np.array([0.9, 0.1])
        MockEmbedder.return_value = mock_embedder

        strategy = RAGStrategy(top_k=1)
        strategy.setup("# A\nText A\n# B\nText B", MagicMock())

        task = make_mock_task()

        # Call prepare twice with the same task
        strategy.prepare("index", task, MagicMock())
        strategy.prepare("index", task, MagicMock())

        # Embedder.embed should be called only once (cached for same question)
        assert mock_embedder.embed.call_count == 1, (
            f"embed() called {mock_embedder.embed.call_count} times, expected 1 (bug #188)"
        )


class TestRAGRegistryIntegration:
    def test_rag_discoverable_via_registry(self):
        from agent_evals.context.registry import get_strategy_by_name, load_all

        load_all()
        strategy = get_strategy_by_name("rag")
        assert strategy is not None
        assert strategy.name() == "rag"
