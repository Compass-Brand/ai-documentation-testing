"""Tests for OpenRouter generation stats fetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agent_evals.llm.generation_stats import GenerationStats, fetch_generation_stats


class TestGenerationStats:
    def test_dataclass_fields(self):
        stats = GenerationStats(
            generation_id="gen-123",
            latency_ms=450.0,
            generation_time_ms=380.0,
            cache_discount=0.003,
            provider_name="Anthropic",
            provider_fallbacks=0,
            native_tokens_cached=80,
            native_tokens_reasoning=10,
            streamed=False,
        )
        assert stats.latency_ms == 450.0
        assert stats.provider_name == "Anthropic"
        assert stats.provider_fallbacks == 0

    def test_provider_fallbacks_counted(self):
        stats = GenerationStats(
            generation_id="gen-123",
            latency_ms=900.0,
            generation_time_ms=400.0,
            cache_discount=None,
            provider_name="Google",
            provider_fallbacks=2,
            native_tokens_cached=0,
            native_tokens_reasoning=0,
            streamed=False,
        )
        assert stats.provider_fallbacks == 2


class TestFetchGenerationStats:
    def test_returns_stats_on_success(self):
        mock_response_data = {
            "data": {
                "id": "gen-123",
                "latency": 450,
                "generation_time": 380,
                "cache_discount": 0.003,
                "provider_name": "Anthropic",
                "provider_responses": [
                    {"status": 200, "latency": 380},
                ],
                "native_tokens_cached": 80,
                "native_tokens_reasoning": 10,
                "streamed": False,
            }
        }

        with patch("agent_evals.llm.generation_stats.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response_data
            mock_httpx.get.return_value = mock_resp

            stats = fetch_generation_stats("gen-123", api_key="fake-key")
            assert stats is not None
            assert stats.latency_ms == 450.0
            assert stats.provider_fallbacks == 0

    def test_counts_fallbacks_from_provider_responses(self):
        mock_response_data = {
            "data": {
                "id": "gen-456",
                "latency": 900,
                "generation_time": 400,
                "cache_discount": None,
                "provider_name": "Google",
                "provider_responses": [
                    {"status": 503, "latency": 200},
                    {"status": 429, "latency": 100},
                    {"status": 200, "latency": 400},
                ],
                "native_tokens_cached": 0,
                "native_tokens_reasoning": 0,
                "streamed": False,
            }
        }

        with patch("agent_evals.llm.generation_stats.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response_data
            mock_httpx.get.return_value = mock_resp

            stats = fetch_generation_stats("gen-456", api_key="fake-key")
            assert stats.provider_fallbacks == 2

    def test_returns_none_on_http_error(self):
        with patch("agent_evals.llm.generation_stats.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_resp.raise_for_status.side_effect = Exception("Not Found")
            mock_httpx.get.return_value = mock_resp

            stats = fetch_generation_stats("gen-bad", api_key="fake-key")
            assert stats is None

    def test_returns_none_when_generation_id_is_none(self):
        stats = fetch_generation_stats(None, api_key="fake-key")
        assert stats is None


class TestFetchRateSampling:
    def test_fetch_rate_sampling(self):
        """When fetch_rate < 1.0, some fetches are skipped."""
        fetched_count = 0
        total_attempts = 100

        with patch("agent_evals.llm.generation_stats.httpx") as mock_httpx, \
             patch("agent_evals.llm.generation_stats.random") as mock_random:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "data": {
                    "id": "gen-123",
                    "latency": 450,
                    "generation_time": 380,
                    "cache_discount": None,
                    "provider_name": "Anthropic",
                    "provider_responses": [],
                    "native_tokens_cached": 0,
                    "native_tokens_reasoning": 0,
                    "streamed": False,
                }
            }
            mock_httpx.get.return_value = mock_resp

            # Simulate 50% sample rate: random returns 0.0-0.99 alternating
            mock_random.random.side_effect = [
                i / total_attempts for i in range(total_attempts)
            ]

            for _ in range(total_attempts):
                result = fetch_generation_stats(
                    "gen-123", api_key="fake-key", fetch_rate=0.5
                )
                if result is not None:
                    fetched_count += 1

            # With fetch_rate=0.5, roughly half should be fetched
            assert fetched_count == 50

    def test_fetch_rate_1_always_fetches(self):
        """Default fetch_rate=1.0 always fetches."""
        with patch("agent_evals.llm.generation_stats.httpx") as mock_httpx:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "data": {
                    "id": "gen-123",
                    "latency": 450,
                    "generation_time": 380,
                    "cache_discount": None,
                    "provider_name": "Anthropic",
                    "provider_responses": [],
                    "native_tokens_cached": 0,
                    "native_tokens_reasoning": 0,
                    "streamed": False,
                }
            }
            mock_httpx.get.return_value = mock_resp

            result = fetch_generation_stats(
                "gen-123", api_key="fake-key", fetch_rate=1.0
            )
            assert result is not None
