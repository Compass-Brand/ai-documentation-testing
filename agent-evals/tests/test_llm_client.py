"""Tests for LLM client wrapper around litellm."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from agent_evals.llm.client import GenerationResult, LLMClient, LLMClientError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mock_litellm_response(
    *,
    content: str = "Hello, world!",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    total_tokens: int = 15,
    model: str = "openrouter/anthropic/claude-sonnet-4.5",
    generation_id: str | None = "gen-abc123",
) -> MagicMock:
    """Build a mock that resembles a litellm ModelResponse."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.usage.prompt_tokens = prompt_tokens
    response.usage.completion_tokens = completion_tokens
    response.usage.total_tokens = total_tokens
    response.model = model
    response.id = generation_id
    # litellm cost helper
    response._hidden_params = {"response_cost": 0.00042}
    return response


# ---------------------------------------------------------------------------
# GenerationResult dataclass
# ---------------------------------------------------------------------------


class TestGenerationResult:
    """Tests for the GenerationResult dataclass."""

    def test_fields_are_stored(self) -> None:
        result = GenerationResult(
            content="hi",
            prompt_tokens=1,
            completion_tokens=2,
            total_tokens=3,
            cost=0.001,
            model="test-model",
            generation_id="gen-1",
        )
        assert result.content == "hi"
        assert result.prompt_tokens == 1
        assert result.completion_tokens == 2
        assert result.total_tokens == 3
        assert result.cost == 0.001
        assert result.model == "test-model"
        assert result.generation_id == "gen-1"

    def test_cost_can_be_none(self) -> None:
        result = GenerationResult(
            content="x",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost=None,
            model="m",
            generation_id=None,
        )
        assert result.cost is None
        assert result.generation_id is None


# ---------------------------------------------------------------------------
# LLMClient defaults
# ---------------------------------------------------------------------------


class TestLLMClientDefaults:
    """Tests for LLMClient default construction."""

    def test_default_temperature(self) -> None:
        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        assert client.temperature == 0.3

    def test_custom_temperature(self) -> None:
        client = LLMClient(
            model="openrouter/anthropic/claude-sonnet-4.5", temperature=0.7
        )
        assert client.temperature == 0.7

    def test_model_stored(self) -> None:
        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        assert client.model == "openrouter/anthropic/claude-sonnet-4.5"

    def test_api_key_stored(self) -> None:
        client = LLMClient(
            model="openrouter/anthropic/claude-sonnet-4.5", api_key="sk-test"
        )
        assert client.api_key == "sk-test"

    def test_api_key_defaults_none(self) -> None:
        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        assert client.api_key is None

    def test_provider_config_defaults_none(self) -> None:
        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        assert client.provider_config is None


# ---------------------------------------------------------------------------
# LLMClient.complete — successful path
# ---------------------------------------------------------------------------


class TestLLMClientComplete:
    """Tests for the complete() method with mocked litellm."""

    @patch("agent_evals.llm.client.litellm")
    def test_returns_generation_result(self, mock_litellm: MagicMock) -> None:
        mock_litellm.completion.return_value = _mock_litellm_response()

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        result = client.complete(messages=[{"role": "user", "content": "hi"}])

        assert isinstance(result, GenerationResult)
        assert result.content == "Hello, world!"
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 5
        assert result.total_tokens == 15
        assert result.model == "openrouter/anthropic/claude-sonnet-4.5"
        assert result.generation_id == "gen-abc123"

    @patch("agent_evals.llm.client.litellm")
    def test_cost_extracted_from_hidden_params(
        self, mock_litellm: MagicMock
    ) -> None:
        mock_litellm.completion.return_value = _mock_litellm_response()

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        result = client.complete(messages=[{"role": "user", "content": "hi"}])

        assert result.cost == 0.00042

    @patch("agent_evals.llm.client.litellm")
    def test_cost_none_when_not_available(
        self, mock_litellm: MagicMock
    ) -> None:
        resp = _mock_litellm_response()
        resp._hidden_params = {}
        mock_litellm.completion.return_value = resp

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        result = client.complete(messages=[{"role": "user", "content": "hi"}])

        assert result.cost is None

    @patch("agent_evals.llm.client.litellm")
    def test_temperature_passed_to_litellm(
        self, mock_litellm: MagicMock
    ) -> None:
        mock_litellm.completion.return_value = _mock_litellm_response()

        client = LLMClient(
            model="openrouter/anthropic/claude-sonnet-4.5", temperature=0.9
        )
        client.complete(messages=[{"role": "user", "content": "hi"}])

        call_kwargs = mock_litellm.completion.call_args
        assert call_kwargs.kwargs["temperature"] == 0.9

    @patch("agent_evals.llm.client.litellm")
    def test_default_temperature_passed(
        self, mock_litellm: MagicMock
    ) -> None:
        mock_litellm.completion.return_value = _mock_litellm_response()

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        client.complete(messages=[{"role": "user", "content": "hi"}])

        call_kwargs = mock_litellm.completion.call_args
        assert call_kwargs.kwargs["temperature"] == 0.3

    @patch("agent_evals.llm.client.litellm")
    def test_api_key_passed_to_litellm(
        self, mock_litellm: MagicMock
    ) -> None:
        mock_litellm.completion.return_value = _mock_litellm_response()

        client = LLMClient(
            model="openrouter/anthropic/claude-sonnet-4.5", api_key="sk-test-123"
        )
        client.complete(messages=[{"role": "user", "content": "hi"}])

        call_kwargs = mock_litellm.completion.call_args
        assert call_kwargs.kwargs["api_key"] == "sk-test-123"

    @patch("agent_evals.llm.client.litellm")
    def test_api_key_omitted_when_none(
        self, mock_litellm: MagicMock
    ) -> None:
        mock_litellm.completion.return_value = _mock_litellm_response()

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        client.complete(messages=[{"role": "user", "content": "hi"}])

        call_kwargs = mock_litellm.completion.call_args
        assert "api_key" not in call_kwargs.kwargs

    @patch("agent_evals.llm.client.litellm")
    def test_messages_passed_to_litellm(
        self, mock_litellm: MagicMock
    ) -> None:
        mock_litellm.completion.return_value = _mock_litellm_response()

        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        client.complete(messages=messages)

        call_kwargs = mock_litellm.completion.call_args
        assert call_kwargs.kwargs["messages"] == messages

    @patch("agent_evals.llm.client.litellm")
    def test_model_passed_to_litellm(
        self, mock_litellm: MagicMock
    ) -> None:
        mock_litellm.completion.return_value = _mock_litellm_response()

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        client.complete(messages=[{"role": "user", "content": "hi"}])

        call_kwargs = mock_litellm.completion.call_args
        assert call_kwargs.kwargs["model"] == "openrouter/anthropic/claude-sonnet-4.5"

    @patch("agent_evals.llm.client.litellm")
    def test_extra_kwargs_forwarded(self, mock_litellm: MagicMock) -> None:
        mock_litellm.completion.return_value = _mock_litellm_response()

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        client.complete(
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=500,
            top_p=0.95,
        )

        call_kwargs = mock_litellm.completion.call_args
        assert call_kwargs.kwargs["max_tokens"] == 500
        assert call_kwargs.kwargs["top_p"] == 0.95


# ---------------------------------------------------------------------------
# Provider config / extra_body
# ---------------------------------------------------------------------------


class TestProviderConfig:
    """Tests for OpenRouter provider configuration via extra_body."""

    @patch("agent_evals.llm.client.litellm")
    def test_provider_config_passed_as_extra_body(
        self, mock_litellm: MagicMock
    ) -> None:
        mock_litellm.completion.return_value = _mock_litellm_response()

        provider_config = {
            "order": ["Anthropic"],
            "allow_fallbacks": False,
            "require_parameters": True,
            "data_collection": "deny",
        }
        client = LLMClient(
            model="openrouter/anthropic/claude-sonnet-4.5",
            provider_config=provider_config,
        )
        client.complete(messages=[{"role": "user", "content": "hi"}])

        call_kwargs = mock_litellm.completion.call_args
        extra_body = call_kwargs.kwargs["extra_body"]
        assert extra_body == {"provider": provider_config}

    @patch("agent_evals.llm.client.litellm")
    def test_no_extra_body_when_no_provider_config(
        self, mock_litellm: MagicMock
    ) -> None:
        mock_litellm.completion.return_value = _mock_litellm_response()

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        client.complete(messages=[{"role": "user", "content": "hi"}])

        call_kwargs = mock_litellm.completion.call_args
        assert "extra_body" not in call_kwargs.kwargs

    @patch("agent_evals.llm.client.litellm")
    def test_provider_config_with_custom_order(
        self, mock_litellm: MagicMock
    ) -> None:
        mock_litellm.completion.return_value = _mock_litellm_response()

        provider_config = {
            "order": ["Anthropic", "Google"],
            "allow_fallbacks": True,
            "data_collection": "allow",
        }
        client = LLMClient(
            model="openrouter/anthropic/claude-sonnet-4.5",
            provider_config=provider_config,
        )
        client.complete(messages=[{"role": "user", "content": "hi"}])

        call_kwargs = mock_litellm.completion.call_args
        extra_body = call_kwargs.kwargs["extra_body"]
        assert extra_body["provider"]["order"] == ["Anthropic", "Google"]
        assert extra_body["provider"]["allow_fallbacks"] is True


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestLLMClientErrors:
    """Tests for error handling in the LLM client."""

    @patch("agent_evals.llm.client.litellm")
    def test_api_error_raises_llm_client_error(
        self, mock_litellm: MagicMock
    ) -> None:
        mock_litellm.completion.side_effect = Exception(
            "API rate limit exceeded"
        )

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        with pytest.raises(LLMClientError, match="API rate limit exceeded"):
            client.complete(messages=[{"role": "user", "content": "hi"}])

    @patch("agent_evals.llm.client.litellm")
    def test_llm_client_error_wraps_original(
        self, mock_litellm: MagicMock
    ) -> None:
        original = ValueError("bad model string")
        mock_litellm.completion.side_effect = original

        client = LLMClient(model="bad-model")
        with pytest.raises(LLMClientError) as exc_info:
            client.complete(messages=[{"role": "user", "content": "hi"}])

        assert exc_info.value.__cause__ is original

    @patch("agent_evals.llm.client.litellm")
    def test_llm_client_error_includes_model_in_message(
        self, mock_litellm: MagicMock
    ) -> None:
        mock_litellm.completion.side_effect = Exception("timeout")

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        with pytest.raises(LLMClientError, match="claude-sonnet-4.5"):
            client.complete(messages=[{"role": "user", "content": "hi"}])
