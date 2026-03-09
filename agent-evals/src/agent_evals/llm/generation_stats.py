"""Fetch post-hoc generation stats from OpenRouter API."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_GENERATION_URL = "https://openrouter.ai/api/v1/generation"


@dataclass
class GenerationStats:
    """Post-hoc metrics from OpenRouter's generation stats endpoint."""

    generation_id: str
    latency_ms: float | None
    generation_time_ms: float | None
    cache_discount: float | None
    provider_name: str | None
    provider_fallbacks: int
    native_tokens_cached: int
    native_tokens_reasoning: int
    streamed: bool | None


def fetch_generation_stats(
    generation_id: str | None,
    *,
    api_key: str,
    fetch_rate: float = 1.0,
) -> GenerationStats | None:
    """Fetch generation stats from OpenRouter.

    Returns None if generation_id is None, the request fails,
    or the fetch is skipped due to sampling.
    """
    if generation_id is None:
        return None

    if fetch_rate < 1.0 and random.random() >= fetch_rate:  # noqa: S311
        return None

    try:
        resp = httpx.get(
            OPENROUTER_GENERATION_URL,
            params={"id": generation_id},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
    except Exception:
        logger.warning(
            "Failed to fetch generation stats for %s", generation_id
        )
        return None

    provider_responses = data.get("provider_responses") or []
    fallbacks = sum(
        1 for pr in provider_responses if pr.get("status", 200) != 200
    )

    return GenerationStats(
        generation_id=generation_id,
        latency_ms=data.get("latency"),
        generation_time_ms=data.get("generation_time"),
        cache_discount=data.get("cache_discount"),
        provider_name=data.get("provider_name"),
        provider_fallbacks=fallbacks,
        native_tokens_cached=data.get("native_tokens_cached") or 0,
        native_tokens_reasoning=data.get("native_tokens_reasoning") or 0,
        streamed=data.get("streamed"),
    )
