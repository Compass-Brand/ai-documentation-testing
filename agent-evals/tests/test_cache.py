"""Tests for the LLM response cache."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from agent_evals.llm.cache import CacheEntry, ResponseCache


class TestCacheMiss:
    """Cache miss should return None."""

    def test_miss_on_empty_cache(self, tmp_path: Path) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        result = cache.get("nonexistent-key")
        assert result is None

    def test_miss_after_clear(self, tmp_path: Path) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        cache.put("key1", {"content": "hello"}, model="gpt-4o", tokens_used=10)
        cache.clear()
        assert cache.get("key1") is None


class TestCacheHit:
    """Cache hit should return stored entry."""

    def test_hit_returns_stored_entry(self, tmp_path: Path) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        response = {"content": "hello", "role": "assistant"}
        cache.put("key1", response, model="gpt-4o", tokens_used=42)

        entry = cache.get("key1")
        assert entry is not None
        assert isinstance(entry, CacheEntry)
        assert entry.key == "key1"
        assert entry.response == response
        assert entry.model == "gpt-4o"
        assert entry.tokens_used == 42
        assert entry.cache_version == 1

    def test_hit_preserves_complex_response(self, tmp_path: Path) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        response = {
            "choices": [{"message": {"role": "assistant", "content": "hi"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        cache.put("key2", response, model="claude-3-opus", tokens_used=15)

        entry = cache.get("key2")
        assert entry is not None
        assert entry.response == response


class TestTTLExpiration:
    """Expired entries should return None."""

    def test_expired_entry_returns_none(self, tmp_path: Path) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache", ttl_days=0)
        cache.put("key1", {"content": "old"}, model="gpt-4o", tokens_used=10)
        # TTL of 0 days means everything is immediately expired
        # We need a small sleep to ensure time has advanced
        time.sleep(0.01)
        assert cache.get("key1") is None

    def test_non_expired_entry_returns_value(self, tmp_path: Path) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache", ttl_days=30)
        cache.put("key1", {"content": "fresh"}, model="gpt-4o", tokens_used=10)
        entry = cache.get("key1")
        assert entry is not None
        assert entry.response == {"content": "fresh"}


class TestMakeKey:
    """make_key should produce consistent, deterministic hashes."""

    def test_consistent_hashes(self, tmp_path: Path) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        messages = [{"role": "user", "content": "Hello"}]
        key1 = cache.make_key(
            model="gpt-4o-2024-05-13",
            temperature=0.0,
            max_tokens=1000,
            messages=messages,
        )
        key2 = cache.make_key(
            model="gpt-4o-2024-05-13",
            temperature=0.0,
            max_tokens=1000,
            messages=messages,
        )
        assert key1 == key2

    def test_different_model_produces_different_key(self, tmp_path: Path) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        messages = [{"role": "user", "content": "Hello"}]
        key1 = cache.make_key(
            model="gpt-4o-2024-05-13",
            temperature=0.0,
            max_tokens=1000,
            messages=messages,
        )
        key2 = cache.make_key(
            model="claude-3-opus-20240229",
            temperature=0.0,
            max_tokens=1000,
            messages=messages,
        )
        assert key1 != key2

    def test_different_temperature_produces_different_key(
        self, tmp_path: Path
    ) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        messages = [{"role": "user", "content": "Hello"}]
        key1 = cache.make_key(
            model="gpt-4o", temperature=0.0, max_tokens=1000, messages=messages
        )
        key2 = cache.make_key(
            model="gpt-4o", temperature=0.7, max_tokens=1000, messages=messages
        )
        assert key1 != key2

    def test_different_max_tokens_produces_different_key(
        self, tmp_path: Path
    ) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        messages = [{"role": "user", "content": "Hello"}]
        key1 = cache.make_key(
            model="gpt-4o", temperature=0.0, max_tokens=1000, messages=messages
        )
        key2 = cache.make_key(
            model="gpt-4o", temperature=0.0, max_tokens=2000, messages=messages
        )
        assert key1 != key2

    def test_different_messages_produces_different_key(self, tmp_path: Path) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        key1 = cache.make_key(
            model="gpt-4o",
            temperature=0.0,
            max_tokens=1000,
            messages=[{"role": "user", "content": "Hello"}],
        )
        key2 = cache.make_key(
            model="gpt-4o",
            temperature=0.0,
            max_tokens=1000,
            messages=[{"role": "user", "content": "Goodbye"}],
        )
        assert key1 != key2

    def test_key_is_valid_sha256_hex(self, tmp_path: Path) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        key = cache.make_key(
            model="gpt-4o",
            temperature=0.0,
            max_tokens=1000,
            messages=[{"role": "user", "content": "test"}],
        )
        # SHA-256 hex digest is 64 characters
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_system_prompt_in_messages_affects_key(self, tmp_path: Path) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        key1 = cache.make_key(
            model="gpt-4o",
            temperature=0.0,
            max_tokens=1000,
            messages=[
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
            ],
        )
        key2 = cache.make_key(
            model="gpt-4o",
            temperature=0.0,
            max_tokens=1000,
            messages=[
                {"role": "system", "content": "You are terse."},
                {"role": "user", "content": "Hello"},
            ],
        )
        assert key1 != key2


class TestCacheVersionInvalidation:
    """Changing cache_version should invalidate all existing entries."""

    def test_version_change_invalidates(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache_v1 = ResponseCache(cache_dir=cache_dir, cache_version=1)
        cache_v1.put("key1", {"content": "v1"}, model="gpt-4o", tokens_used=10)

        # Same cache dir, different version
        cache_v2 = ResponseCache(cache_dir=cache_dir, cache_version=2)
        assert cache_v2.get("key1") is None

    def test_same_version_still_hits(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache1 = ResponseCache(cache_dir=cache_dir, cache_version=3)
        cache1.put("key1", {"content": "v3"}, model="gpt-4o", tokens_used=10)

        cache2 = ResponseCache(cache_dir=cache_dir, cache_version=3)
        entry = cache2.get("key1")
        assert entry is not None
        assert entry.response == {"content": "v3"}


class TestClear:
    """clear() should remove all entries and return count."""

    def test_clear_empty_cache(self, tmp_path: Path) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        count = cache.clear()
        assert count == 0

    def test_clear_returns_count(self, tmp_path: Path) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        cache.put("k1", {"a": 1}, model="m", tokens_used=1)
        cache.put("k2", {"b": 2}, model="m", tokens_used=2)
        cache.put("k3", {"c": 3}, model="m", tokens_used=3)
        count = cache.clear()
        assert count == 3

    def test_clear_removes_files(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache = ResponseCache(cache_dir=cache_dir)
        cache.put("k1", {"a": 1}, model="m", tokens_used=1)
        cache.clear()
        json_files = list(cache_dir.glob("*.json"))
        assert len(json_files) == 0


class TestEvictLRU:
    """evict_lru should remove least recently used entries to stay under max_size."""

    def test_evict_removes_oldest_entries(self, tmp_path: Path) -> None:
        cache = ResponseCache(
            cache_dir=tmp_path / "cache",
            max_size_mb=0,  # Force eviction of everything
        )
        cache.put("k1", {"a": 1}, model="m", tokens_used=1)
        cache.put("k2", {"b": 2}, model="m", tokens_used=2)

        evicted = cache.evict_lru()
        assert evicted >= 1

    def test_evict_keeps_recent_when_under_limit(self, tmp_path: Path) -> None:
        cache = ResponseCache(
            cache_dir=tmp_path / "cache",
            max_size_mb=500,  # Generous limit
        )
        cache.put("k1", {"a": 1}, model="m", tokens_used=1)
        evicted = cache.evict_lru()
        assert evicted == 0
        assert cache.get("k1") is not None

    def test_evict_returns_count(self, tmp_path: Path) -> None:
        cache = ResponseCache(
            cache_dir=tmp_path / "cache",
            max_size_mb=0,  # Force eviction
        )
        cache.put("k1", {"a": 1}, model="m", tokens_used=1)
        cache.put("k2", {"b": 2}, model="m", tokens_used=2)
        cache.put("k3", {"c": 3}, model="m", tokens_used=3)

        evicted = cache.evict_lru()
        assert evicted == 3


class TestDisabledCache:
    """When disabled, cache should be a no-op."""

    def test_disabled_get_returns_none(self, tmp_path: Path) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache", enabled=False)
        cache.put("k1", {"a": 1}, model="m", tokens_used=1)
        assert cache.get("k1") is None

    def test_disabled_put_does_not_write(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache = ResponseCache(cache_dir=cache_dir, enabled=False)
        cache.put("k1", {"a": 1}, model="m", tokens_used=1)
        # The cache dir should either not exist or have no JSON files
        if cache_dir.exists():
            json_files = list(cache_dir.glob("*.json"))
            assert len(json_files) == 0


class TestSizeBytes:
    """size_bytes should reflect actual disk usage."""

    def test_empty_cache_is_zero(self, tmp_path: Path) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        assert cache.size_bytes == 0

    def test_size_increases_after_put(self, tmp_path: Path) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        cache.put("k1", {"content": "hello world"}, model="gpt-4o", tokens_used=5)
        assert cache.size_bytes > 0

    def test_size_reflects_multiple_entries(self, tmp_path: Path) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        cache.put("k1", {"a": 1}, model="m", tokens_used=1)
        size_one = cache.size_bytes
        cache.put("k2", {"b": 2}, model="m", tokens_used=2)
        size_two = cache.size_bytes
        assert size_two > size_one

    def test_size_decreases_after_clear(self, tmp_path: Path) -> None:
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        cache.put("k1", {"a": 1}, model="m", tokens_used=1)
        assert cache.size_bytes > 0
        cache.clear()
        assert cache.size_bytes == 0


class TestCacheFileFormat:
    """Cache files should be stored as individual JSON files named by key."""

    def test_file_named_by_key(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache = ResponseCache(cache_dir=cache_dir)
        cache.put("abc123", {"x": 1}, model="m", tokens_used=1)
        assert (cache_dir / "abc123.json").exists()

    def test_file_is_valid_json(self, tmp_path: Path) -> None:
        cache_dir = tmp_path / "cache"
        cache = ResponseCache(cache_dir=cache_dir)
        cache.put("abc123", {"x": 1}, model="m", tokens_used=1)
        with open(cache_dir / "abc123.json", encoding="utf-8") as f:
            data = json.load(f)
        assert data["key"] == "abc123"
        assert data["response"] == {"x": 1}
        assert data["model"] == "m"
        assert data["tokens_used"] == 1
        assert "created_at" in data
        assert "cache_version" in data


class TestMakeKeyIncludesCacheVersion:
    """make_key should incorporate cache_version so bumping it changes keys."""

    def test_cache_version_in_key(self, tmp_path: Path) -> None:
        cache_v1 = ResponseCache(cache_dir=tmp_path / "c1", cache_version=1)
        cache_v2 = ResponseCache(cache_dir=tmp_path / "c2", cache_version=2)
        messages = [{"role": "user", "content": "test"}]

        key1 = cache_v1.make_key(
            model="gpt-4o", temperature=0.0, max_tokens=100, messages=messages
        )
        key2 = cache_v2.make_key(
            model="gpt-4o", temperature=0.0, max_tokens=100, messages=messages
        )
        assert key1 != key2


# ---------------------------------------------------------------------------
# Concurrent access safety (Step 6.3)
# ---------------------------------------------------------------------------


class TestConcurrentAccess:
    """Tests for thread-safe concurrent cache read/write operations."""

    def test_concurrent_writes_same_key(self, tmp_path: Path) -> None:
        """Multiple threads writing the same key should not corrupt data."""
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        key = "shared-key"
        num_threads = 10

        def write_entry(i: int) -> None:
            cache.put(
                key,
                {"content": f"response-{i}", "index": i},
                model="gpt-4o",
                tokens_used=i,
            )

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(write_entry, i) for i in range(num_threads)]
            for future in as_completed(futures):
                future.result()  # raises if any thread failed

        # The final entry should be valid JSON and parseable
        entry = cache.get(key)
        assert entry is not None
        assert isinstance(entry.response, dict)
        assert "content" in entry.response

    def test_concurrent_read_write(self, tmp_path: Path) -> None:
        """Concurrent reads and writes on the same key should not raise."""
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        key = "rw-key"

        # Seed an initial entry
        cache.put(key, {"content": "initial"}, model="gpt-4o", tokens_used=1)

        errors: list[Exception] = []

        def reader() -> None:
            for _ in range(20):
                try:
                    entry = cache.get(key)
                    # entry might be None if read during a write, but
                    # it should never be corrupted (partial JSON).
                    if entry is not None:
                        assert isinstance(entry.response, dict)
                except Exception as exc:
                    errors.append(exc)

        def writer(i: int) -> None:
            for j in range(20):
                try:
                    cache.put(
                        key,
                        {"content": f"response-{i}-{j}"},
                        model="gpt-4o",
                        tokens_used=j,
                    )
                except Exception as exc:
                    errors.append(exc)

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for i in range(4):
                futures.append(executor.submit(reader))
                futures.append(executor.submit(writer, i))
            for future in as_completed(futures):
                future.result()

        assert len(errors) == 0, f"Concurrent access errors: {errors}"

    def test_concurrent_writes_different_keys(self, tmp_path: Path) -> None:
        """Multiple threads writing different keys should all succeed."""
        cache = ResponseCache(cache_dir=tmp_path / "cache")
        num_threads = 10

        def write_entry(i: int) -> str:
            key = f"key-{i}"
            cache.put(
                key,
                {"content": f"response-{i}"},
                model="gpt-4o",
                tokens_used=i,
            )
            return key

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(write_entry, i) for i in range(num_threads)]
            keys = [f.result() for f in as_completed(futures)]

        # All entries should be readable
        for key in keys:
            entry = cache.get(key)
            assert entry is not None, f"Missing entry for {key}"
            assert isinstance(entry.response, dict)

    def test_cache_has_lock_attribute(self, tmp_path: Path) -> None:
        """ResponseCache should have a threading lock for thread safety."""
        import threading

        cache = ResponseCache(cache_dir=tmp_path / "cache")
        assert hasattr(cache, "_lock"), (
            "ResponseCache should have a _lock attribute for thread safety"
        )
        assert isinstance(cache._lock, type(threading.Lock()))
