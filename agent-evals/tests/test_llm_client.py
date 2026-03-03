"""Tests for LLM client wrapper around litellm."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import litellm as _litellm
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


# ---------------------------------------------------------------------------
# Retry logic with typed litellm exceptions (Step 6.1)
# ---------------------------------------------------------------------------


class TestRetryWithTypedExceptions:
    """Tests that retry logic uses typed litellm exceptions, not string matching."""

    @patch("agent_evals.llm.client.time.sleep")
    @patch("agent_evals.llm.client.litellm")
    def test_retries_on_rate_limit_error(
        self, mock_litellm: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """RateLimitError should trigger a retry and succeed on next attempt."""
        rate_limit_exc = _litellm.RateLimitError(
            message="Rate limit exceeded",
            llm_provider="openrouter",
            model="openrouter/anthropic/claude-sonnet-4.5",
        )
        mock_litellm.completion.side_effect = [
            rate_limit_exc,
            _mock_litellm_response(),
        ]
        mock_litellm.RateLimitError = _litellm.RateLimitError
        mock_litellm.InternalServerError = _litellm.InternalServerError
        mock_litellm.ServiceUnavailableError = _litellm.ServiceUnavailableError
        mock_litellm.BadGatewayError = _litellm.BadGatewayError

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        result = client.complete(messages=[{"role": "user", "content": "hi"}])

        assert result.content == "Hello, world!"
        assert mock_litellm.completion.call_count == 2
        mock_sleep.assert_called_once()

    @patch("agent_evals.llm.client.time.sleep")
    @patch("agent_evals.llm.client.litellm")
    def test_retries_on_internal_server_error(
        self, mock_litellm: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """InternalServerError (500) should trigger a retry."""
        server_exc = _litellm.InternalServerError(
            message="Internal server error",
            llm_provider="openrouter",
            model="openrouter/anthropic/claude-sonnet-4.5",
        )
        mock_litellm.completion.side_effect = [
            server_exc,
            _mock_litellm_response(),
        ]
        mock_litellm.RateLimitError = _litellm.RateLimitError
        mock_litellm.InternalServerError = _litellm.InternalServerError
        mock_litellm.ServiceUnavailableError = _litellm.ServiceUnavailableError
        mock_litellm.BadGatewayError = _litellm.BadGatewayError

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        result = client.complete(messages=[{"role": "user", "content": "hi"}])

        assert result.content == "Hello, world!"
        assert mock_litellm.completion.call_count == 2

    @patch("agent_evals.llm.client.time.sleep")
    @patch("agent_evals.llm.client.litellm")
    def test_retries_on_service_unavailable_error(
        self, mock_litellm: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """ServiceUnavailableError (503) should trigger a retry."""
        svc_exc = _litellm.ServiceUnavailableError(
            message="Service unavailable",
            llm_provider="openrouter",
            model="openrouter/anthropic/claude-sonnet-4.5",
        )
        mock_litellm.completion.side_effect = [
            svc_exc,
            _mock_litellm_response(),
        ]
        mock_litellm.RateLimitError = _litellm.RateLimitError
        mock_litellm.InternalServerError = _litellm.InternalServerError
        mock_litellm.ServiceUnavailableError = _litellm.ServiceUnavailableError
        mock_litellm.BadGatewayError = _litellm.BadGatewayError

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        result = client.complete(messages=[{"role": "user", "content": "hi"}])

        assert result.content == "Hello, world!"
        assert mock_litellm.completion.call_count == 2

    @patch("agent_evals.llm.client.time.sleep")
    @patch("agent_evals.llm.client.litellm")
    def test_retries_on_bad_gateway_error(
        self, mock_litellm: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """BadGatewayError (502) should trigger a retry."""
        gw_exc = _litellm.BadGatewayError(
            message="Bad gateway",
            llm_provider="openrouter",
            model="openrouter/anthropic/claude-sonnet-4.5",
        )
        mock_litellm.completion.side_effect = [
            gw_exc,
            _mock_litellm_response(),
        ]
        mock_litellm.RateLimitError = _litellm.RateLimitError
        mock_litellm.InternalServerError = _litellm.InternalServerError
        mock_litellm.ServiceUnavailableError = _litellm.ServiceUnavailableError
        mock_litellm.BadGatewayError = _litellm.BadGatewayError

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        result = client.complete(messages=[{"role": "user", "content": "hi"}])

        assert result.content == "Hello, world!"
        assert mock_litellm.completion.call_count == 2

    @patch("agent_evals.llm.client.time.sleep")
    @patch("agent_evals.llm.client.litellm")
    def test_no_retry_on_non_retryable_exception(
        self, mock_litellm: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """Non-retryable exceptions should not be retried."""
        mock_litellm.completion.side_effect = ValueError("Invalid request")
        mock_litellm.RateLimitError = _litellm.RateLimitError
        mock_litellm.InternalServerError = _litellm.InternalServerError
        mock_litellm.ServiceUnavailableError = _litellm.ServiceUnavailableError
        mock_litellm.BadGatewayError = _litellm.BadGatewayError

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        with pytest.raises(LLMClientError, match="Invalid request"):
            client.complete(messages=[{"role": "user", "content": "hi"}])

        assert mock_litellm.completion.call_count == 1
        mock_sleep.assert_not_called()

    @patch("agent_evals.llm.client.time.sleep")
    @patch("agent_evals.llm.client.litellm")
    def test_exhausted_retries_raises_llm_client_error(
        self, mock_litellm: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """All retries exhausted on retryable error raises LLMClientError."""
        rate_limit_exc = _litellm.RateLimitError(
            message="Rate limit exceeded",
            llm_provider="openrouter",
            model="openrouter/anthropic/claude-sonnet-4.5",
        )
        mock_litellm.completion.side_effect = rate_limit_exc
        mock_litellm.RateLimitError = _litellm.RateLimitError
        mock_litellm.InternalServerError = _litellm.InternalServerError
        mock_litellm.ServiceUnavailableError = _litellm.ServiceUnavailableError
        mock_litellm.BadGatewayError = _litellm.BadGatewayError

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        with pytest.raises(LLMClientError, match="Rate limit exceeded"):
            client.complete(messages=[{"role": "user", "content": "hi"}])

        assert mock_litellm.completion.call_count == client.MAX_RETRIES


# ---------------------------------------------------------------------------
# Exponential backoff with jitter (Step 6.5)
# ---------------------------------------------------------------------------


class TestRetryBackoff:
    """Tests for configurable retry count and exponential backoff with jitter."""

    @patch("agent_evals.llm.client.random.uniform", side_effect=lambda a, b: b)
    @patch("agent_evals.llm.client.time.sleep")
    @patch("agent_evals.llm.client.litellm")
    def test_backoff_increases_exponentially(
        self, mock_litellm: MagicMock, mock_sleep: MagicMock, _mock_uniform: MagicMock
    ) -> None:
        """Sleep durations should increase exponentially between retries.

        Patches random.uniform to always return the upper bound so that
        delays are deterministic and strictly increasing.
        """
        rate_limit_exc = _litellm.RateLimitError(
            message="Rate limit exceeded",
            llm_provider="openrouter",
            model="openrouter/anthropic/claude-sonnet-4.5",
        )
        mock_litellm.completion.side_effect = rate_limit_exc
        mock_litellm.RateLimitError = _litellm.RateLimitError
        mock_litellm.InternalServerError = _litellm.InternalServerError
        mock_litellm.ServiceUnavailableError = _litellm.ServiceUnavailableError
        mock_litellm.BadGatewayError = _litellm.BadGatewayError

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        with pytest.raises(LLMClientError):
            client.complete(messages=[{"role": "user", "content": "hi"}])

        # Should have slept MAX_RETRIES - 1 times (no sleep after last attempt)
        assert mock_sleep.call_count == client.MAX_RETRIES - 1

        # Each delay should be larger than the previous (exponential backoff)
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        for i in range(1, len(delays)):
            assert delays[i] > delays[i - 1], (
                f"Delay {i} ({delays[i]}) should be greater than "
                f"delay {i-1} ({delays[i-1]})"
            )

    @patch("agent_evals.llm.client.time.sleep")
    @patch("agent_evals.llm.client.litellm")
    def test_backoff_has_jitter(
        self, mock_litellm: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """Backoff delays should include jitter (not exact powers of base)."""
        rate_limit_exc = _litellm.RateLimitError(
            message="Rate limit exceeded",
            llm_provider="openrouter",
            model="openrouter/anthropic/claude-sonnet-4.5",
        )
        mock_litellm.completion.side_effect = rate_limit_exc
        mock_litellm.RateLimitError = _litellm.RateLimitError
        mock_litellm.InternalServerError = _litellm.InternalServerError
        mock_litellm.ServiceUnavailableError = _litellm.ServiceUnavailableError
        mock_litellm.BadGatewayError = _litellm.BadGatewayError

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")

        # Run multiple times to collect delays -- jitter means they should
        # not all be identical for the same attempt index.
        all_first_delays: list[float] = []
        for _ in range(5):
            mock_sleep.reset_mock()
            mock_litellm.completion.side_effect = rate_limit_exc
            with pytest.raises(LLMClientError):
                client.complete(messages=[{"role": "user", "content": "hi"}])
            if mock_sleep.call_args_list:
                all_first_delays.append(mock_sleep.call_args_list[0].args[0])

        # With jitter, not all first delays should be identical
        # (probabilistically this is extremely likely with 5 samples)
        assert len(set(all_first_delays)) > 1, (
            f"Expected jitter but all first delays were identical: {all_first_delays}"
        )

    @patch("agent_evals.llm.client.time.sleep")
    @patch("agent_evals.llm.client.litellm")
    def test_backoff_bounded_by_base_delay(
        self, mock_litellm: MagicMock, mock_sleep: MagicMock
    ) -> None:
        """Each delay should be bounded by [0, base_delay * 2^attempt]."""
        rate_limit_exc = _litellm.RateLimitError(
            message="Rate limit exceeded",
            llm_provider="openrouter",
            model="openrouter/anthropic/claude-sonnet-4.5",
        )
        mock_litellm.completion.side_effect = rate_limit_exc
        mock_litellm.RateLimitError = _litellm.RateLimitError
        mock_litellm.InternalServerError = _litellm.InternalServerError
        mock_litellm.ServiceUnavailableError = _litellm.ServiceUnavailableError
        mock_litellm.BadGatewayError = _litellm.BadGatewayError

        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        with pytest.raises(LLMClientError):
            client.complete(messages=[{"role": "user", "content": "hi"}])

        delays = [call.args[0] for call in mock_sleep.call_args_list]
        for i, delay in enumerate(delays):
            max_delay = client.RETRY_BASE_DELAY * (2 ** i)
            assert 0 < delay <= max_delay, (
                f"Delay {delay} for attempt {i} should be in "
                f"(0, {max_delay}]"
            )

    def test_max_retries_is_configurable(self) -> None:
        """MAX_RETRIES class attribute can be overridden on instance."""
        client = LLMClient(model="openrouter/anthropic/claude-sonnet-4.5")
        assert client.MAX_RETRIES == 3  # default

        client.MAX_RETRIES = 5
        assert client.MAX_RETRIES == 5


# ---------------------------------------------------------------------------
# Retry logging (Step 6.6)
# ---------------------------------------------------------------------------


class TestRetryLogging:
    """Tests that retry attempts produce warning logs for observability."""

    @patch("agent_evals.llm.client.time.sleep")
    @patch("agent_evals.llm.client.litellm")
    def test_retryable_error_logs_warning(
        self,
        mock_litellm: MagicMock,
        mock_sleep: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Each retry attempt should produce a warning log."""
        rate_limit_exc = _litellm.RateLimitError(
            message="rate limited",
            llm_provider="openrouter",
            model="test/model",
        )
        mock_litellm.completion.side_effect = [
            rate_limit_exc,
            _mock_litellm_response(),
        ]
        mock_litellm.RateLimitError = _litellm.RateLimitError
        mock_litellm.InternalServerError = _litellm.InternalServerError
        mock_litellm.ServiceUnavailableError = _litellm.ServiceUnavailableError
        mock_litellm.BadGatewayError = _litellm.BadGatewayError

        client = LLMClient(model="test/model", api_key="test-key")
        with caplog.at_level(logging.WARNING, logger="agent_evals"):
            result = client.complete([{"role": "user", "content": "test"}])
        assert "Retrying" in caplog.text
        assert result.content == "Hello, world!"

    @patch("agent_evals.llm.client.time.sleep")
    @patch("agent_evals.llm.client.litellm")
    def test_silent_429_logs_warning(
        self,
        mock_litellm: MagicMock,
        mock_sleep: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Silent 429 (empty content) should produce a warning log."""
        empty_response = MagicMock()
        empty_response.choices = [MagicMock()]
        empty_response.choices[0].message.content = None

        mock_litellm.completion.side_effect = [
            empty_response,
            _mock_litellm_response(),
        ]
        mock_litellm.RateLimitError = _litellm.RateLimitError
        mock_litellm.InternalServerError = _litellm.InternalServerError
        mock_litellm.ServiceUnavailableError = _litellm.ServiceUnavailableError
        mock_litellm.BadGatewayError = _litellm.BadGatewayError

        client = LLMClient(model="test/model", api_key="test-key")
        with caplog.at_level(logging.WARNING, logger="agent_evals"):
            result = client.complete([{"role": "user", "content": "test"}])
        assert "empty content" in caplog.text.lower() or "rate limit" in caplog.text.lower()


class TestRequestTimeout:
    """LLMClient must pass a request timeout to litellm to prevent hung threads."""

    @patch("agent_evals.llm.client.litellm")
    def test_timeout_passed_to_litellm(self, mock_litellm: MagicMock) -> None:
        """litellm.completion must receive a 'timeout' kwarg on every call."""
        mock_litellm.completion.return_value = _mock_litellm_response()
        mock_litellm.RateLimitError = _litellm.RateLimitError
        mock_litellm.InternalServerError = _litellm.InternalServerError
        mock_litellm.ServiceUnavailableError = _litellm.ServiceUnavailableError
        mock_litellm.BadGatewayError = _litellm.BadGatewayError

        client = LLMClient(model="test/model", api_key="key")
        client.complete([{"role": "user", "content": "hi"}])

        call_kwargs = mock_litellm.completion.call_args.kwargs
        assert "timeout" in call_kwargs, (
            "No timeout passed to litellm.completion — hung connections will block threads forever"
        )
        assert isinstance(call_kwargs["timeout"], (int, float))
        assert call_kwargs["timeout"] > 0

    @patch("agent_evals.llm.client.litellm")
    def test_default_timeout_is_reasonable(self, mock_litellm: MagicMock) -> None:
        """Default timeout should be at least 30s but no more than 5 minutes."""
        mock_litellm.completion.return_value = _mock_litellm_response()
        mock_litellm.RateLimitError = _litellm.RateLimitError
        mock_litellm.InternalServerError = _litellm.InternalServerError
        mock_litellm.ServiceUnavailableError = _litellm.ServiceUnavailableError
        mock_litellm.BadGatewayError = _litellm.BadGatewayError

        client = LLMClient(model="test/model", api_key="key")
        client.complete([{"role": "user", "content": "hi"}])

        timeout = mock_litellm.completion.call_args.kwargs["timeout"]
        assert 30 <= timeout <= 300, f"Timeout {timeout}s is outside reasonable range [30, 300]"
