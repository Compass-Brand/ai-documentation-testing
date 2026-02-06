"""Disk-based response cache for LLM API calls.

Caches responses keyed on SHA-256(model + temperature + max_tokens
+ messages + cache_version) to avoid redundant API calls during evaluation
runs.  System prompts are included as part of the messages list.

Thread-safe via atomic writes (write-to-temp-then-rename).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class CacheEntry:
    """A single cached LLM response."""

    key: str
    response: dict[str, Any]  # serialized LLM response
    created_at: float  # timestamp
    model: str
    tokens_used: int
    cache_version: int


class ResponseCache:
    """Disk-based LLM response cache with TTL and LRU eviction.

    Each cache entry is stored as an individual JSON file named ``{key}.json``
    inside *cache_dir*.  Atomic writes (write-to-temp-then-rename) provide
    thread-safety without external locking libraries.

    Parameters
    ----------
    cache_dir:
        Directory for cache files.  Created on first write.
    ttl_days:
        Time-to-live in days.  Entries older than this are treated as misses.
    max_size_mb:
        Maximum total size of cache files in megabytes.  ``evict_lru`` removes
        the oldest entries until the cache is under this limit.
    cache_version:
        Integer embedded in every cache key.  Bump to invalidate all existing
        entries without deleting files.
    enabled:
        When ``False`` the cache is a no-op: ``get`` always returns ``None``
        and ``put`` never writes.
    """

    def __init__(
        self,
        cache_dir: Path | str = ".agent-evals-cache",
        ttl_days: int = 30,
        max_size_mb: int = 500,
        cache_version: int = 1,
        enabled: bool = True,
    ) -> None:
        self._cache_dir = Path(cache_dir)
        self._ttl_seconds = ttl_days * 86_400
        self._max_size_bytes = max_size_mb * 1_024 * 1_024
        self._cache_version = cache_version
        self._enabled = enabled

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> CacheEntry | None:
        """Get a cached response.

        Returns ``None`` if the cache is disabled, the key is missing, or
        the entry has expired.
        """
        if not self._enabled:
            return None

        path = self._path_for(key)
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        entry = CacheEntry(**data)

        # Version mismatch -> treat as miss
        if entry.cache_version != self._cache_version:
            return None

        # TTL check
        if time.time() - entry.created_at > self._ttl_seconds:
            return None

        return entry

    def put(
        self, key: str, response: dict[str, Any], model: str, tokens_used: int
    ) -> None:
        """Store a response in the cache.

        Uses atomic write (write-to-temp-then-rename) for thread-safety.
        No-op when the cache is disabled.
        """
        if not self._enabled:
            return

        self._cache_dir.mkdir(parents=True, exist_ok=True)

        entry = CacheEntry(
            key=key,
            response=response,
            created_at=time.time(),
            model=model,
            tokens_used=tokens_used,
            cache_version=self._cache_version,
        )

        payload = json.dumps(asdict(entry), ensure_ascii=False, indent=2)
        target = self._path_for(key)

        # Atomic write: write to a temp file in the same directory, then
        # rename.  On POSIX ``os.replace`` is atomic; on Windows it is
        # atomic when src and dst are on the same volume (guaranteed here
        # because we use the same directory for the temp file).
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self._cache_dir), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(payload)
            os.replace(tmp_path, str(target))
        except BaseException:
            # Clean up temp file on any failure
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise

    def make_key(
        self,
        model: str,
        temperature: float,
        max_tokens: int,
        messages: list[dict[str, Any]],
    ) -> str:
        """Generate a deterministic SHA-256 cache key.

        The key is derived from the model version, temperature, max_tokens,
        the full messages list, and the current ``cache_version``.
        """
        blob = json.dumps(
            {
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "messages": messages,
                "cache_version": self._cache_version,
            },
            sort_keys=True,
            ensure_ascii=True,
        )
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def clear(self) -> int:
        """Remove all cache entries.  Returns the number of entries removed."""
        if not self._cache_dir.exists():
            return 0

        count = 0
        for path in self._cache_dir.glob("*.json"):
            try:
                path.unlink()
                count += 1
            except OSError:
                pass
        return count

    def evict_lru(self) -> int:
        """Evict least-recently-used entries to stay under ``max_size_mb``.

        Files are sorted by modification time (oldest first) and removed
        until the total size is within the limit.

        Returns the number of entries evicted.
        """
        if not self._cache_dir.exists():
            return 0

        files = sorted(
            self._cache_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
        )

        total = sum(p.stat().st_size for p in files)
        evicted = 0

        for path in files:
            if total <= self._max_size_bytes:
                break
            try:
                size = path.stat().st_size
                path.unlink()
                total -= size
                evicted += 1
            except OSError:
                pass

        return evicted

    @property
    def size_bytes(self) -> int:
        """Current total size of cache files on disk, in bytes."""
        if not self._cache_dir.exists():
            return 0
        return sum(p.stat().st_size for p in self._cache_dir.glob("*.json"))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _path_for(self, key: str) -> Path:
        """Return the file path for a given cache key."""
        return self._cache_dir / f"{key}.json"
