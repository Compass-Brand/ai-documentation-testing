"""Thin wrapper around litellm.completion() with generation metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import litellm


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
            **kwargs,
        }

        if self.api_key is not None:
            call_kwargs["api_key"] = self.api_key

        if self.provider_config is not None:
            call_kwargs["extra_body"] = {"provider": self.provider_config}

        try:
            response = litellm.completion(**call_kwargs)
        except Exception as exc:
            msg = (
                f"LLM completion failed for model '{self.model}': {exc}"
            )
            raise LLMClientError(msg) from exc

        # Extract cost from litellm hidden params if available.
        cost: float | None = None
        hidden_params = getattr(response, "_hidden_params", None)
        if isinstance(hidden_params, dict):
            cost = hidden_params.get("response_cost")

        return GenerationResult(
            content=response.choices[0].message.content,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            cost=cost,
            model=response.model,
            generation_id=response.id,
        )
