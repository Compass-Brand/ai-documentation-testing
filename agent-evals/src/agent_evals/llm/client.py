"""Thin wrapper around litellm.completion() with generation metadata."""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Any

import litellm

litellm.suppress_debug_info = True

logger = logging.getLogger(__name__)

# Typed exception classes for retry decisions.  Using these instead of
# fragile string matching (e.g. ``"429" in str(exc)``) makes the retry
# logic robust regardless of how the provider formats error messages.
_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    litellm.RateLimitError,
    litellm.InternalServerError,
    litellm.ServiceUnavailableError,
    litellm.BadGatewayError,
)


@dataclass
class GenerationResult:
    """Result of an LLM completion call with metadata."""

    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float | None
    model: str
    generation_id: str | None
    api_call_ms: float = 0.0
    retry_count: int = 0
    total_api_ms: float = 0.0
    tool_calls: list | None = None
    cached_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    provider: str | None = None


class LLMClientError(Exception):
    """Raised when an LLM completion call fails."""


class LLMClient:
    """Thin wrapper around litellm for standardized LLM access.

    Supports OpenRouter provider configuration via ``extra_body`` and returns
    structured :class:`GenerationResult` objects with token counts and cost.
    """

    MAX_RETRIES: int = 3
    RETRY_BASE_DELAY: float = 5.0
    REQUEST_TIMEOUT: float = 120.0  # seconds; prevents hung connections blocking threads

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        provider_config: dict[str, Any] | None = None,
        temperature: float = 0.3,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.provider_config = provider_config
        self.temperature = temperature

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        tools: list[dict] | None = None,
        **kwargs: object,
    ) -> GenerationResult:
        """Send a completion request and return a result with metadata.

        Parameters
        ----------
        messages:
            Chat messages in the OpenAI format (list of role/content dicts).
        tools:
            Optional list of tool definitions in OpenAI function calling
            format. When provided, the model may return tool_calls instead
            of text content.
        **kwargs:
            Extra keyword arguments forwarded to ``litellm.completion()``
            (e.g. ``max_tokens``, ``top_p``).

        Returns
        -------
        GenerationResult
            Structured result containing the response text and metadata.

        Raises
        ------
        LLMClientError
            If the underlying API call fails for any reason.
        """
        call_kwargs: dict[str, object] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "timeout": self.REQUEST_TIMEOUT,
            "stream": False,  # MUST be False — LiteLLM streaming cost bug #16021
            **kwargs,
        }

        if tools is not None:
            call_kwargs["tools"] = tools

        if self.api_key is not None:
            call_kwargs["api_key"] = self.api_key

        if self.provider_config is not None:
            call_kwargs["extra_body"] = {"provider": self.provider_config}

        last_exc: Exception | None = None
        retry_count = 0
        total_api_start = time.monotonic()
        api_call_ms = 0.0

        for attempt in range(self.MAX_RETRIES):
            logger.debug(
                "LLM API call starting (model=%s, attempt=%d/%d)",
                self.model, attempt + 1, self.MAX_RETRIES,
            )
            attempt_start = time.monotonic()
            try:
                response = litellm.completion(**call_kwargs)
                attempt_ms = (time.monotonic() - attempt_start) * 1000
                # Detect silent 429: litellm swallows OpenRouter rate
                # limit errors and returns content=None instead of raising.
                # Tool call responses legitimately have content=None with
                # tool_calls populated — do not treat those as rate limits.
                message = response.choices[0].message
                content = message.content
                tool_calls = getattr(message, "tool_calls", None)
                if content is None and not tool_calls:
                    logger.debug(
                        "Silent rate limit (model=%s, attempt_ms=%.0f)",
                        self.model, attempt_ms,
                    )
                    if attempt < self.MAX_RETRIES - 1:
                        retry_count += 1
                        delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                        logger.warning(
                            "LLM returned empty content (attempt %d/%d, possible rate limit). "
                            "Retrying in %.1fs...",
                            attempt + 1, self.MAX_RETRIES, delay,
                        )
                        time.sleep(delay)
                        continue
                    raise LLMClientError(
                        f"LLM returned empty content for '{self.model}' "
                        f"(possible silent rate limit)"
                    )
                api_call_ms = attempt_ms
                logger.debug(
                    "LLM API call succeeded (model=%s, attempt=%d, call_ms=%.0f, tokens=%d)",
                    self.model, attempt + 1, attempt_ms,
                    response.usage.total_tokens,
                )
                break
            except LLMClientError:
                raise
            except Exception as exc:
                attempt_ms = (time.monotonic() - attempt_start) * 1000
                last_exc = exc
                is_retryable = isinstance(exc, _RETRYABLE_EXCEPTIONS)
                if is_retryable and attempt < self.MAX_RETRIES - 1:
                    retry_count += 1
                    logger.debug(
                        "LLM API call failed (model=%s, attempt=%d, call_ms=%.0f, error=%s)",
                        self.model, attempt + 1, attempt_ms, exc,
                    )
                    # Exponential backoff with jitter: random delay in
                    # (0, base_delay * 2^attempt] to avoid thundering herd.
                    max_delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    delay = random.uniform(0, max_delay)  # noqa: S311
                    logger.warning(
                        "LLM call failed (attempt %d/%d): %s. Retrying in %.1fs...",
                        attempt + 1, self.MAX_RETRIES, exc, delay,
                    )
                    time.sleep(delay)
                    continue
                msg = (
                    f"LLM completion failed for model '{self.model}': {exc}"
                )
                raise LLMClientError(msg) from exc
        else:
            msg = f"LLM completion failed after {self.MAX_RETRIES} retries: {last_exc}"
            raise LLMClientError(msg) from last_exc

        total_api_ms = (time.monotonic() - total_api_start) * 1000

        # Extract cost from litellm hidden params if available.
        cost: float | None = None
        hidden_params = getattr(response, "_hidden_params", None)
        if isinstance(hidden_params, dict):
            cost = hidden_params.get("response_cost")

        # Extract tool_calls from the response message when present.
        response_tool_calls = getattr(
            response.choices[0].message, "tool_calls", None,
        )
        serialized_tool_calls: list | None = None
        if response_tool_calls:
            serialized_tool_calls = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in response_tool_calls
            ]

        # Extract extended OpenRouter metadata
        usage = getattr(response, "usage", None)
        cached_tokens = 0
        cache_write_tokens = 0
        reasoning_tokens = 0

        if usage:
            prompt_details = getattr(usage, "prompt_tokens_details", None)
            if prompt_details:
                cached_tokens = getattr(prompt_details, "cached_tokens", 0) or 0
                cache_write_tokens = getattr(prompt_details, "cache_write_tokens", 0) or 0

            completion_details = getattr(usage, "completion_tokens_details", None)
            if completion_details:
                reasoning_tokens = getattr(completion_details, "reasoning_tokens", 0) or 0

        # Extract provider from response (OpenRouter includes this)
        provider = getattr(response, "provider", None)

        return GenerationResult(
            content=response.choices[0].message.content or "",
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            cost=cost,
            model=response.model,
            generation_id=response.id,
            api_call_ms=api_call_ms,
            retry_count=retry_count,
            total_api_ms=total_api_ms,
            tool_calls=serialized_tool_calls,
            cached_tokens=cached_tokens,
            cache_write_tokens=cache_write_tokens,
            reasoning_tokens=reasoning_tokens,
            provider=provider,
        )
