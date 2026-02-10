"""Token counting and cost estimation utilities using LiteLLM."""

from __future__ import annotations

import logging
from typing import Any

import litellm

logger = logging.getLogger(__name__)


def count_tokens(text: str, model: str = "openrouter/anthropic/claude-sonnet-4.5") -> int:
    """Count tokens using LiteLLM's token_counter.

    Falls back to ~4 chars/token heuristic if model not supported.

    Args:
        text: The text to count tokens for.
        model: The model name to use for tokenization.

    Returns:
        The estimated number of tokens.
    """
    try:
        return int(litellm.token_counter(model=model, text=text))
    except Exception:
        fallback_count = len(text) // 4
        logger.warning(
            "Token counting fallback: model '%s' not supported by litellm, "
            "using ~4 chars/token heuristic (%d tokens for %d chars)",
            model,
            fallback_count,
            len(text),
        )
        return fallback_count


def count_message_tokens(
    messages: list[dict[str, Any]], model: str = "openrouter/anthropic/claude-sonnet-4.5"
) -> int:
    """Count tokens in a list of chat messages.

    Includes message overhead (role, separators) when using litellm.
    Falls back to concatenating content fields with ~4 chars/token heuristic.

    Args:
        messages: A list of chat message dicts with 'role' and 'content' keys.
        model: The model name to use for tokenization.

    Returns:
        The estimated number of tokens.
    """
    try:
        return int(litellm.token_counter(model=model, messages=messages))
    except Exception:
        concatenated = "".join(msg.get("content", "") for msg in messages)
        fallback_count = len(concatenated) // 4
        logger.warning(
            "Message token counting fallback: model '%s' not supported by litellm, "
            "using ~4 chars/token heuristic (%d tokens for %d chars)",
            model,
            fallback_count,
            len(concatenated),
        )
        return fallback_count


def estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
) -> float:
    """Estimate cost in dollars for given token counts.

    Uses litellm.model_cost if available, else returns 0.0.

    Args:
        prompt_tokens: Number of prompt (input) tokens.
        completion_tokens: Number of completion (output) tokens.
        model: The model name to look up pricing for.

    Returns:
        Estimated cost in dollars, or 0.0 if pricing unavailable.
    """
    model_info: dict[str, Any] | None = litellm.model_cost.get(model)
    if not model_info:
        return 0.0

    raw_input_cost = model_info.get("input_cost_per_token")
    raw_output_cost = model_info.get("output_cost_per_token")

    # Use ``is None`` instead of truthiness to correctly handle free models
    # where cost per token is explicitly 0.0 (falsy but valid).
    if raw_input_cost is None and raw_output_cost is None:
        return 0.0

    input_cost_per_token: float = float(raw_input_cost or 0.0)
    output_cost_per_token: float = float(raw_output_cost or 0.0)

    return float(
        (prompt_tokens * input_cost_per_token)
        + (completion_tokens * output_cost_per_token)
    )
