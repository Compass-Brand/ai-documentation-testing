"""Tests for token counter utility."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from agent_evals.llm.token_counter import count_message_tokens, count_tokens, estimate_cost


class TestCountTokens:
    """Tests for count_tokens function."""

    @patch("agent_evals.llm.token_counter.litellm")
    def test_known_model_returns_token_count(self, mock_litellm: MagicMock) -> None:
        """count_tokens with a known model delegates to litellm and returns count."""
        mock_litellm.token_counter.return_value = 15
        result = count_tokens("Hello, this is a test string.", model="gpt-4")
        mock_litellm.token_counter.assert_called_once_with(
            model="gpt-4", text="Hello, this is a test string."
        )
        assert result == 15

    @patch("agent_evals.llm.token_counter.litellm")
    def test_fallback_when_model_unsupported(self, mock_litellm: MagicMock) -> None:
        """count_tokens falls back to heuristic when litellm raises an exception."""
        mock_litellm.token_counter.side_effect = Exception("Model not supported")
        text = "a" * 100
        result = count_tokens(text, model="unknown-model-xyz")
        assert result == 25  # 100 / 4

    @patch("agent_evals.llm.token_counter.litellm")
    def test_fallback_returns_approximately_len_div_4(
        self, mock_litellm: MagicMock
    ) -> None:
        """Fallback heuristic returns len(text) / 4 (integer division)."""
        mock_litellm.token_counter.side_effect = Exception("unsupported")
        text = "The quick brown fox jumps over the lazy dog"  # 43 chars
        result = count_tokens(text, model="unsupported-model")
        assert result == len(text) // 4  # 43 // 4 = 10

    @patch("agent_evals.llm.token_counter.litellm")
    def test_fallback_logs_warning(
        self, mock_litellm: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Falling back to heuristic should log a warning."""
        mock_litellm.token_counter.side_effect = Exception("boom")
        import logging

        with caplog.at_level(logging.WARNING):
            count_tokens("some text", model="bad-model")
        assert any("fallback" in record.message.lower() for record in caplog.records)

    @patch("agent_evals.llm.token_counter.litellm")
    def test_empty_string_returns_zero(self, mock_litellm: MagicMock) -> None:
        """An empty string should return 0 tokens."""
        mock_litellm.token_counter.return_value = 0
        result = count_tokens("", model="gpt-4")
        assert result == 0

    @patch("agent_evals.llm.token_counter.litellm")
    def test_empty_string_fallback_returns_zero(
        self, mock_litellm: MagicMock
    ) -> None:
        """An empty string via fallback should also return 0."""
        mock_litellm.token_counter.side_effect = Exception("unsupported")
        result = count_tokens("", model="unknown-model")
        assert result == 0


class TestCountMessageTokens:
    """Tests for count_message_tokens function."""

    @patch("agent_evals.llm.token_counter.litellm")
    def test_multiple_messages(self, mock_litellm: MagicMock) -> None:
        """count_message_tokens should handle a list of chat messages."""
        mock_litellm.token_counter.return_value = 42
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        result = count_message_tokens(messages, model="gpt-4")
        mock_litellm.token_counter.assert_called_once_with(
            model="gpt-4", messages=messages
        )
        assert result == 42

    @patch("agent_evals.llm.token_counter.litellm")
    def test_empty_messages_returns_zero(self, mock_litellm: MagicMock) -> None:
        """An empty message list should return 0 tokens."""
        mock_litellm.token_counter.return_value = 0
        result = count_message_tokens([], model="gpt-4")
        assert result == 0

    @patch("agent_evals.llm.token_counter.litellm")
    def test_fallback_concatenates_content(self, mock_litellm: MagicMock) -> None:
        """Fallback for messages concatenates all content fields."""
        mock_litellm.token_counter.side_effect = Exception("unsupported")
        messages = [
            {"role": "user", "content": "Hello"},  # 5 chars
            {"role": "assistant", "content": "World"},  # 5 chars
        ]
        # Total content = "HelloWorld" = 10 chars => 10 // 4 = 2
        result = count_message_tokens(messages, model="unsupported-model")
        assert result == 10 // 4


class TestEstimateCost:
    """Tests for estimate_cost function."""

    @patch("agent_evals.llm.token_counter.litellm")
    def test_known_model_pricing(self, mock_litellm: MagicMock) -> None:
        """estimate_cost with known model returns correct cost calculation."""
        mock_litellm.model_cost = {
            "gpt-4": {
                "input_cost_per_token": 0.00003,
                "output_cost_per_token": 0.00006,
            }
        }
        # 1000 prompt tokens * 0.00003 = 0.03
        # 500 completion tokens * 0.00006 = 0.03
        # Total = 0.06
        result = estimate_cost(
            prompt_tokens=1000,
            completion_tokens=500,
            model="gpt-4",
        )
        assert result == pytest.approx(0.06)

    @patch("agent_evals.llm.token_counter.litellm")
    def test_unknown_model_returns_zero(self, mock_litellm: MagicMock) -> None:
        """estimate_cost returns 0.0 if model pricing is not available."""
        mock_litellm.model_cost = {}
        result = estimate_cost(
            prompt_tokens=1000,
            completion_tokens=500,
            model="unknown-model",
        )
        assert result == 0.0

    @patch("agent_evals.llm.token_counter.litellm")
    def test_prompt_vs_completion_tracked_separately(
        self, mock_litellm: MagicMock
    ) -> None:
        """Prompt and completion tokens have different rates, so cost differs."""
        mock_litellm.model_cost = {
            "gpt-4": {
                "input_cost_per_token": 0.00003,
                "output_cost_per_token": 0.00006,
            }
        }
        # Only prompt tokens, no completion
        cost_prompt_only = estimate_cost(
            prompt_tokens=1000, completion_tokens=0, model="gpt-4"
        )
        # Only completion tokens, no prompt
        cost_completion_only = estimate_cost(
            prompt_tokens=0, completion_tokens=1000, model="gpt-4"
        )
        assert cost_prompt_only == pytest.approx(0.03)
        assert cost_completion_only == pytest.approx(0.06)
        # Completion is more expensive per token, so these should differ
        assert cost_prompt_only != cost_completion_only

    @patch("agent_evals.llm.token_counter.litellm")
    def test_zero_tokens_returns_zero_cost(self, mock_litellm: MagicMock) -> None:
        """Zero tokens for both prompt and completion should return 0 cost."""
        mock_litellm.model_cost = {
            "gpt-4": {
                "input_cost_per_token": 0.00003,
                "output_cost_per_token": 0.00006,
            }
        }
        result = estimate_cost(
            prompt_tokens=0,
            completion_tokens=0,
            model="gpt-4",
        )
        assert result == 0.0

    @patch("agent_evals.llm.token_counter.litellm")
    def test_missing_cost_keys_returns_zero(self, mock_litellm: MagicMock) -> None:
        """If model exists in model_cost but lacks pricing keys, return 0.0."""
        mock_litellm.model_cost = {"gpt-4": {}}
        result = estimate_cost(
            prompt_tokens=1000,
            completion_tokens=500,
            model="gpt-4",
        )
        assert result == 0.0
