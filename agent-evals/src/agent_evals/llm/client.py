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
        self, messages: list[dict[str, str]], **kwargs: object
    ) -> GenerationResult:
        """Send a completion request and return a result with metadata.

        Parameters
        ----------
        messages:
            Chat messages in the OpenAI format (list of role/content dicts).
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
            **kwargs,
        }

        if self.api_key is not None:
            call_kwargs["api_key"] = self.api_key

        if self.provider_config is not None:
            call_kwargs["extra_body"] = {"provider": self.provider_config}

        last_exc: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = litellm.completion(**call_kwargs)
                # Detect silent 429: litellm swallows OpenRouter rate
                # limit errors and returns content=None instead of raising.
                content = response.choices[0].message.content
                if content is None:
                    if attempt < self.MAX_RETRIES - 1:
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
                break
            except LLMClientError:
                raise
            except Exception as exc:
                last_exc = exc
                is_retryable = isinstance(exc, _RETRYABLE_EXCEPTIONS)
                if is_retryable and attempt < self.MAX_RETRIES - 1:
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

        # Extract cost from litellm hidden params if available.
        cost: float | None = None
        hidden_params = getattr(response, "_hidden_params", None)
        if isinstance(hidden_params, dict):
            cost = hidden_params.get("response_cost")

        return GenerationResult(
            content=response.choices[0].message.content or "",
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            cost=cost,
            model=response.model,
            generation_id=response.id,
        )
