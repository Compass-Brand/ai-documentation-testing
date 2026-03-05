"""RAG context strategy -- chunk, embed, retrieve, inject.

Chunks the rendered index at setup time, embeds all chunks once,
then retrieves top-K similar chunks per task question at prepare time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from agent_evals.context.base import ContextStrategy, PreparedContext, StrategyResult
from agent_evals.context.chunkers import fixed_size_chunks, heading_chunks
from agent_evals.context.embedder import Embedder
from agent_evals.context.vector_store import InMemoryVectorStore

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.llm.client import LLMClient
    from agent_evals.tasks.base import EvalTask


class RAGStrategy(ContextStrategy):
    """Retrieve top-K chunks from an embedded index for each task."""

    def __init__(
        self,
        chunk_method: str = "heading",
        top_k: int = 5,
        embedding_model: str = "text-embedding-3-small",
    ) -> None:
        self._chunk_method = chunk_method
        self._top_k = top_k
        self._embedding_model = embedding_model
        self._embedder: Embedder | None = None
        self._store: InMemoryVectorStore | None = None
        self._total_chunks: int = 0

    def name(self) -> str:
        return "rag"

    def setup(self, rendered_index: str, doc_tree: DocTree) -> None:
        if self._chunk_method == "fixed":
            chunks = fixed_size_chunks(rendered_index)
        else:
            chunks = heading_chunks(rendered_index)

        if not chunks:
            self._store = InMemoryVectorStore([], np.empty((0, 0)))
            self._total_chunks = 0
            return

        self._embedder = Embedder(model=self._embedding_model)
        vectors = self._embedder.embed_batch(chunks)
        embeddings = np.stack(vectors)
        self._store = InMemoryVectorStore(chunks, embeddings)
        self._total_chunks = len(chunks)

    def teardown(self) -> None:
        self._store = None
        self._embedder = None
        self._total_chunks = 0

    def prepare(
        self, rendered_index: str, task: EvalTask, doc_tree: DocTree,
    ) -> PreparedContext:
        if self._store is None or self._embedder is None:
            messages = task.build_prompt("")
            return PreparedContext(
                messages=messages,
                tools=None,
                strategy_metadata={
                    "chunks_retrieved": 0,
                    "total_chunks": 0,
                    "chunk_scores": [],
                },
            )

        # Embed the task question
        question = self._extract_question(task)
        query_vec = self._embedder.embed(question)

        # Retrieve top-K chunks
        results = self._store.search(query_vec, top_k=self._top_k)
        chunk_texts = [text for text, _ in results]
        chunk_scores = [score for _, score in results]

        # Build prompt with retrieved context
        context = "\n\n".join(chunk_texts)
        messages = task.build_prompt(context)

        return PreparedContext(
            messages=messages,
            tools=None,
            strategy_metadata={
                "chunks_retrieved": len(results),
                "total_chunks": self._total_chunks,
                "chunk_scores": chunk_scores,
            },
        )

    def execute(
        self,
        prepared: PreparedContext,
        task: EvalTask,
        client: LLMClient,
        max_tokens: int,
        temperature: float,
    ) -> StrategyResult:
        generation = client.complete(
            prepared.messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return StrategyResult(
            final_response=generation.content,
            generations=[generation],
            total_prompt_tokens=generation.prompt_tokens,
            total_completion_tokens=generation.completion_tokens,
            total_tokens=generation.total_tokens,
            total_cost=generation.cost,
            messages=prepared.messages,
            strategy_metadata=prepared.strategy_metadata,
        )

    def supports_caching(self) -> bool:
        return True

    @staticmethod
    def _extract_question(task: EvalTask) -> str:
        messages = task.build_prompt("")
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""
