"""Thin wrapper around litellm.embedding() with content-hash caching.

Caches embeddings keyed on SHA-256(text + model) to avoid redundant
API calls.  Cache is persisted to disk as individual ``.npy`` files
for cross-session reuse.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from pathlib import Path

import litellm
import numpy as np

logger = logging.getLogger(__name__)


class Embedder:
    """Produce embedding vectors via ``litellm.embedding()`` with caching.

    Parameters
    ----------
    model:
        Embedding model name (passed directly to litellm).
    cache_dir:
        Directory for persisted embedding cache.  ``None`` disables
        disk persistence (in-memory only).
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        cache_dir: Path | str | None = None,
    ) -> None:
        self._model = model
        self._memory_cache: dict[str, np.ndarray] = {}
        self._lock = threading.Lock()
        self._cache_dir: Path | None = None
        if cache_dir is not None:
            self._cache_dir = Path(cache_dir)
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._load_disk_cache()

    def embed(self, text: str) -> np.ndarray:
        """Return the embedding vector for *text*, using cache if available."""
        key = self._make_key(text)

        with self._lock:
            if key in self._memory_cache:
                return self._memory_cache[key]

        vec = self._call_api(text)

        with self._lock:
            self._memory_cache[key] = vec
            self._persist(key, vec)

        return vec

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Embed multiple texts in a single API call.

        Texts already in cache are skipped; only uncached texts are sent
        to the API.  Results are returned in the same order as *texts*.
        """
        keys = [self._make_key(t) for t in texts]
        results: list[np.ndarray | None] = [None] * len(texts)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        with self._lock:
            for i, key in enumerate(keys):
                if key in self._memory_cache:
                    results[i] = self._memory_cache[key]
                else:
                    uncached_indices.append(i)
                    uncached_texts.append(texts[i])

        if uncached_texts:
            vecs = self._call_api_batch(uncached_texts)
            with self._lock:
                for idx, vec, text in zip(uncached_indices, vecs, uncached_texts):
                    key = self._make_key(text)
                    self._memory_cache[key] = vec
                    self._persist(key, vec)
                    results[idx] = vec

        return [r for r in results if r is not None]

    def _make_key(self, text: str) -> str:
        blob = json.dumps(
            {"text": text, "model": self._model},
            sort_keys=True,
            ensure_ascii=True,
        )
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _call_api(self, text: str) -> np.ndarray:
        response = litellm.embedding(model=self._model, input=[text])
        return np.array(response.data[0].embedding, dtype=np.float64)

    def _call_api_batch(self, texts: list[str]) -> list[np.ndarray]:
        response = litellm.embedding(model=self._model, input=texts)
        return [
            np.array(item.embedding, dtype=np.float64)
            for item in response.data
        ]

    def _persist(self, key: str, vec: np.ndarray) -> None:
        if self._cache_dir is None:
            return
        path = self._cache_dir / f"{key}.npy"
        np.save(str(path), vec)

    def _load_disk_cache(self) -> None:
        if self._cache_dir is None:
            return
        for path in self._cache_dir.glob("*.npy"):
            key = path.stem
            try:
                self._memory_cache[key] = np.load(str(path))
            except Exception:
                logger.warning("Failed to load cached embedding: %s", path)
