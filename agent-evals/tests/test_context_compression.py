"""Tests for the compression context strategy.

Tests cover:
- CompressionStrategy registration in the strategy registry
- Algorithmic compression (stopword removal, whitespace collapse)
- Format conversion (markdown -> compact key-value)
- LLM-summarized compression (algorithmic fallback in prepare, LLM in execute)
- execute() wraps client response correctly
- execute() replaces system message content with LLM summary for llm_summarized
- render_compression_tradeoff_table() produces correct tabular output
- Structured vs prose compaction comparison
"""

from __future__ import annotations

from unittest.mock import MagicMock

from conftest import make_mock_client, make_mock_task

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestCompressionRegistration:
    """CompressionStrategy should register in the context strategy registry."""

    def test_registry_contains_compression(self):
        from agent_evals.context.registry import get_strategy_by_name, load_all

        load_all()
        strategy = get_strategy_by_name("compression")
        assert strategy is not None
        assert strategy.name() == "compression"

    def test_name_returns_compression(self):
        from agent_evals.context.compression import CompressionStrategy

        assert CompressionStrategy().name() == "compression"

    def test_supports_caching_returns_true(self):
        from agent_evals.context.compression import CompressionStrategy

        assert CompressionStrategy().supports_caching() is True

    def test_default_method_is_algorithmic(self):
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy()
        assert strategy._method == "algorithmic"

    def test_custom_method(self):
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy(method="format_conversion")
        assert strategy._method == "format_conversion"


# ---------------------------------------------------------------------------
# Algorithmic compression
# ---------------------------------------------------------------------------


class TestAlgorithmicCompression:
    """Algorithmic compression removes stopwords, collapses whitespace."""

    def test_removes_stopwords(self):
        from agent_evals.context.compression import _algorithmic_compress

        text = "The quick brown fox is a great animal"
        result = _algorithmic_compress(text)
        # "The", "is", "a" should be removed
        assert "quick" in result
        assert "brown" in result
        assert "fox" in result
        assert "great" in result
        assert "animal" in result

    def test_collapses_multiple_spaces(self):
        from agent_evals.context.compression import _algorithmic_compress

        text = "hello    world     test"
        result = _algorithmic_compress(text)
        assert "  " not in result

    def test_collapses_multiple_newlines(self):
        from agent_evals.context.compression import _algorithmic_compress

        text = "line one\n\n\n\n\nline two"
        result = _algorithmic_compress(text)
        # Should be at most two consecutive newlines
        assert "\n\n\n" not in result
        assert "line one" in result
        assert "line two" in result

    def test_strips_empty_lines(self):
        from agent_evals.context.compression import _algorithmic_compress

        text = "hello\n   \n\nworld"
        result = _algorithmic_compress(text)
        lines = result.splitlines()
        assert all(line.strip() for line in lines)

    def test_reduces_token_count(self):
        from agent_evals.context.compression import _algorithmic_compress

        text = (
            "The documentation is a comprehensive guide that was written "
            "to be used by the developers. It has been designed to provide "
            "the most useful information for all of the users."
        )
        compressed = _algorithmic_compress(text)
        assert len(compressed) < len(text)

    def test_empty_input(self):
        from agent_evals.context.compression import _algorithmic_compress

        assert _algorithmic_compress("") == ""

    def test_prepare_uses_algorithmic_by_default(self):
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy(method="algorithmic")
        task = make_mock_task()
        doc_tree = MagicMock()

        rendered = "The quick brown fox is a great animal in the forest"
        prepared = strategy.prepare(rendered, task, doc_tree)

        assert prepared.strategy_metadata["compression_method"] == "algorithmic"
        assert prepared.strategy_metadata["original_tokens"] > 0
        assert prepared.strategy_metadata["compressed_tokens"] > 0
        assert prepared.strategy_metadata["compression_ratio"] <= 1.0

    def test_prepare_metadata_has_required_keys(self):
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy()
        task = make_mock_task()
        doc_tree = MagicMock()

        prepared = strategy.prepare("Some documentation text here", task, doc_tree)

        required_keys = {
            "compression_method",
            "original_tokens",
            "compressed_tokens",
            "compression_ratio",
        }
        assert required_keys.issubset(prepared.strategy_metadata.keys())


# ---------------------------------------------------------------------------
# Format conversion
# ---------------------------------------------------------------------------


class TestFormatConversion:
    """Format conversion transforms markdown to compact key-value format."""

    def test_headings_become_sections(self):
        from agent_evals.context.compression import _format_convert

        text = "# Introduction\nSome content here"
        result = _format_convert(text)
        assert "[Introduction]" in result

    def test_nested_headings(self):
        from agent_evals.context.compression import _format_convert

        text = "## API Reference\nDetails here"
        result = _format_convert(text)
        assert "[API Reference]" in result

    def test_bullet_points_converted(self):
        from agent_evals.context.compression import _format_convert

        text = "- First item\n- Second item"
        result = _format_convert(text)
        assert "* First item" in result
        assert "* Second item" in result

    def test_plain_text_indented(self):
        from agent_evals.context.compression import _format_convert

        text = "Plain text line"
        result = _format_convert(text)
        assert result.strip() == "Plain text line"

    def test_empty_lines_stripped(self):
        from agent_evals.context.compression import _format_convert

        text = "# Title\n\nContent"
        result = _format_convert(text)
        lines = result.splitlines()
        # Empty lines should be skipped (stripped lines that are empty)
        assert all(line == "" or line.strip() for line in lines)

    def test_prepare_with_format_conversion(self):
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy(method="format_conversion")
        task = make_mock_task()
        doc_tree = MagicMock()

        rendered = "# Title\nSome docs\n- Item 1\n- Item 2"
        prepared = strategy.prepare(rendered, task, doc_tree)

        assert prepared.strategy_metadata["compression_method"] == "format_conversion"


# ---------------------------------------------------------------------------
# LLM summarized compression
# ---------------------------------------------------------------------------


class TestLLMSummarizedCompression:
    """LLM summarized mode uses algorithmic fallback in prepare()."""

    def test_prepare_uses_algorithmic_fallback(self):
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy(method="llm_summarized")
        task = make_mock_task()
        doc_tree = MagicMock()

        rendered = "The documentation is a comprehensive guide for the developers"
        prepared = strategy.prepare(rendered, task, doc_tree)

        # In prepare, llm_summarized falls back to algorithmic compression
        assert prepared.strategy_metadata["compression_method"] == "llm_summarized"
        assert prepared.strategy_metadata["original_tokens"] > 0

    def test_prepare_metadata_records_llm_summarized(self):
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy(method="llm_summarized")
        task = make_mock_task()
        doc_tree = MagicMock()

        prepared = strategy.prepare("Some text content", task, doc_tree)
        assert prepared.strategy_metadata["compression_method"] == "llm_summarized"


class TestLLMSummarizedCompressionComplete:
    """LLM summarized mode can use _llm_summarize() with a client."""

    def test_llm_summarize_calls_client(self):
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy(method="llm_summarized")
        client = make_mock_client(content="summarized text")

        result = strategy._llm_summarize("long documentation text", client)
        assert result == "summarized text"
        client.complete.assert_called_once()

    def test_llm_summarize_uses_compression_prompt(self):
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy(method="llm_summarized")
        client = make_mock_client(content="compressed")

        strategy._llm_summarize("some docs", client)

        call_args = client.complete.call_args
        messages = call_args[0][0]
        assert any("compressor" in msg.get("content", "").lower() for msg in messages)

    def test_llm_summarize_fallback_on_empty_response(self):
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy(method="llm_summarized")
        client = make_mock_client(content="")  # empty content

        # When content is empty string (falsy), should fall back to original text
        result = strategy._llm_summarize("original text", client)
        assert result == "original text"

    def test_set_summary_client(self):
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy(method="llm_summarized")
        summary_client = make_mock_client(content="summary")
        strategy.set_summary_client(summary_client)
        assert strategy._summary_client is summary_client


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


class TestCompressionExecute:
    """execute() wraps client response into StrategyResult."""

    def test_execute_calls_client_complete(self):
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy()
        messages = [{"role": "user", "content": "test question"}]
        prepared = PreparedContext(
            messages=messages,
            tools=None,
            strategy_metadata={
                "compression_method": "algorithmic",
                "original_tokens": 100,
                "compressed_tokens": 70,
                "compression_ratio": 0.7,
            },
        )

        client = make_mock_client()
        task = make_mock_task()
        result = strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        client.complete.assert_called_once_with(
            messages,
            tools=None,
            max_tokens=2048,
            temperature=0.3,
        )

    def test_execute_passes_tools_to_client_complete(self):
        """Bug #281: execute() must pass tools=prepared.tools to client.complete().

        When PreparedContext has tools, execute() must forward them so the LLM
        can use function calling.
        """
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.compression import CompressionStrategy
        from agent_evals.llm.client import GenerationResult

        strategy = CompressionStrategy()
        tools = [{"type": "function", "function": {"name": "test_tool"}}]
        messages = [{"role": "user", "content": "test question"}]
        prepared = PreparedContext(
            messages=messages,
            tools=tools,
            strategy_metadata={
                "compression_method": "algorithmic",
                "original_tokens": 100,
                "compressed_tokens": 70,
                "compression_ratio": 0.7,
            },
        )

        client = make_mock_client()
        gen = GenerationResult(
            content="response",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost=0.001,
            model="mock-model",
            generation_id="gen-1",
        )
        client.complete.return_value = gen

        task = make_mock_task()
        strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        client.complete.assert_called_once_with(
            messages,
            tools=tools,
            max_tokens=2048,
            temperature=0.3,
        )

    def test_execute_passes_none_tools_to_client_complete(self):
        """Bug #281: execute() must pass tools=None when PreparedContext has no tools."""
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.compression import CompressionStrategy
        from agent_evals.llm.client import GenerationResult

        strategy = CompressionStrategy()
        messages = [{"role": "user", "content": "test question"}]
        prepared = PreparedContext(
            messages=messages,
            tools=None,
            strategy_metadata={
                "compression_method": "algorithmic",
                "original_tokens": 100,
                "compressed_tokens": 70,
                "compression_ratio": 0.7,
            },
        )

        client = make_mock_client()
        gen = GenerationResult(
            content="response",
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost=0.001,
            model="mock-model",
            generation_id="gen-1",
        )
        client.complete.return_value = gen

        task = make_mock_task()
        strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        client.complete.assert_called_once_with(
            messages,
            tools=None,
            max_tokens=2048,
            temperature=0.3,
        )

    def test_execute_returns_strategy_result(self):
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.compression import CompressionStrategy
        from agent_evals.llm.client import GenerationResult

        strategy = CompressionStrategy()
        messages = [{"role": "user", "content": "test"}]
        metadata = {
            "compression_method": "algorithmic",
            "original_tokens": 100,
            "compressed_tokens": 70,
            "compression_ratio": 0.7,
        }
        prepared = PreparedContext(
            messages=messages,
            tools=None,
            strategy_metadata=metadata,
        )

        gen = GenerationResult(
            content="response text",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.005,
            model="mock-model",
            generation_id="gen-1",
        )
        client = make_mock_client()
        client.complete.return_value = gen

        task = make_mock_task()
        result = strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        assert result.final_response == "response text"
        assert result.total_prompt_tokens == 100
        assert result.total_completion_tokens == 50
        assert result.total_tokens == 150
        assert result.total_cost == 0.005
        assert len(result.generations) == 1
        assert result.generations[0] is gen
        assert result.strategy_metadata == metadata

    def test_execute_preserves_strategy_metadata(self):
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy()
        metadata = {
            "compression_method": "algorithmic",
            "original_tokens": 200,
            "compressed_tokens": 120,
            "compression_ratio": 0.6,
        }
        prepared = PreparedContext(
            messages=[{"role": "user", "content": "q"}],
            tools=None,
            strategy_metadata=metadata,
        )

        client = make_mock_client()
        task = make_mock_task()
        result = strategy.execute(prepared, task, client, max_tokens=1024, temperature=0.0)

        assert result.strategy_metadata["compression_method"] == "algorithmic"
        assert result.strategy_metadata["original_tokens"] == 200
        assert result.strategy_metadata["compressed_tokens"] == 120
        assert result.strategy_metadata["compression_ratio"] == 0.6


# ---------------------------------------------------------------------------
# execute() with LLM summarized replaces system message
# ---------------------------------------------------------------------------


class TestExecuteReplacesContentWithLLMSummary:
    """For llm_summarized method, execute() replaces long system messages."""

    def test_replaces_long_system_message(self):
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy(method="llm_summarized")
        long_content = "x" * 300  # > 200 chars threshold
        messages = [
            {"role": "system", "content": long_content},
            {"role": "user", "content": "question"},
        ]
        prepared = PreparedContext(
            messages=messages,
            tools=None,
            strategy_metadata={"compression_method": "llm_summarized"},
        )

        summary_client = make_mock_client(content="summarized system content")
        strategy.set_summary_client(summary_client)

        main_client = make_mock_client(content="final answer")
        task = make_mock_task()
        result = strategy.execute(prepared, task, main_client, max_tokens=2048, temperature=0.3)

        # Summary client should have been called for the system message
        summary_client.complete.assert_called_once()
        # Main client should have been called for the final generation
        main_client.complete.assert_called_once()

    def test_does_not_replace_short_system_message(self):
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy(method="llm_summarized")
        short_content = "Brief system prompt"  # < 200 chars
        messages = [
            {"role": "system", "content": short_content},
            {"role": "user", "content": "question"},
        ]
        prepared = PreparedContext(
            messages=messages,
            tools=None,
            strategy_metadata={"compression_method": "llm_summarized"},
        )

        summary_client = make_mock_client(content="summarized")
        strategy.set_summary_client(summary_client)

        main_client = make_mock_client(content="final answer")
        task = make_mock_task()
        result = strategy.execute(prepared, task, main_client, max_tokens=2048, temperature=0.3)

        # Summary client should NOT have been called for short content
        summary_client.complete.assert_not_called()

    def test_non_llm_method_skips_summarization(self):
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy(method="algorithmic")
        long_content = "x" * 300
        messages = [
            {"role": "system", "content": long_content},
            {"role": "user", "content": "question"},
        ]
        prepared = PreparedContext(
            messages=messages,
            tools=None,
            strategy_metadata={"compression_method": "algorithmic"},
        )

        client = make_mock_client(content="answer")
        task = make_mock_task()
        result = strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        # Only one call to client.complete (the main call, no summarization)
        client.complete.assert_called_once()

    def test_uses_main_client_when_no_summary_client_set(self):
        from agent_evals.context.base import PreparedContext
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy(method="llm_summarized")
        # Don't set summary_client - should fall back to main client
        long_content = "x" * 300
        messages = [
            {"role": "system", "content": long_content},
            {"role": "user", "content": "question"},
        ]
        prepared = PreparedContext(
            messages=messages,
            tools=None,
            strategy_metadata={"compression_method": "llm_summarized"},
        )

        client = make_mock_client(content="answer")
        task = make_mock_task()
        result = strategy.execute(prepared, task, client, max_tokens=2048, temperature=0.3)

        # Client should be called twice: once for summarization, once for final
        assert client.complete.call_count == 2


# ---------------------------------------------------------------------------
# Tradeoff table
# ---------------------------------------------------------------------------


class TestCompressionTradeoffTable:
    """render_compression_tradeoff_table() produces formatted output."""

    def test_renders_header(self):
        from agent_evals.context.compression import render_compression_tradeoff_table

        table = render_compression_tradeoff_table([])
        assert "VARIANT" in table
        assert "COMPRESSION_RATIO" in table
        assert "ACCURACY" in table
        assert "COST_SAVINGS" in table
        assert "NET_BENEFIT" in table

    def test_renders_single_trial(self):
        from agent_evals.context.compression import render_compression_tradeoff_table

        trials = [
            {
                "variant_name": "algorithmic_v1",
                "compression_ratio": 0.65,
                "accuracy": 0.85,
                "cost": 0.002,
                "baseline_cost": 0.005,
            },
        ]
        table = render_compression_tradeoff_table(trials)
        assert "algorithmic_v1" in table
        assert "0.6500" in table  # compression_ratio
        assert "0.8500" in table  # accuracy

    def test_renders_multiple_trials(self):
        from agent_evals.context.compression import render_compression_tradeoff_table

        trials = [
            {
                "variant_name": "method_a",
                "compression_ratio": 0.5,
                "accuracy": 0.9,
                "cost": 0.001,
                "baseline_cost": 0.01,
            },
            {
                "variant_name": "method_b",
                "compression_ratio": 0.7,
                "accuracy": 0.8,
                "cost": 0.003,
                "baseline_cost": 0.01,
            },
        ]
        table = render_compression_tradeoff_table(trials)
        lines = table.strip().splitlines()
        # Header + separator + 2 data rows
        assert len(lines) == 4

    def test_cost_savings_calculation(self):
        from agent_evals.context.compression import render_compression_tradeoff_table

        trials = [
            {
                "variant_name": "test",
                "compression_ratio": 0.5,
                "accuracy": 1.0,
                "cost": 0.005,
                "baseline_cost": 0.01,
            },
        ]
        table = render_compression_tradeoff_table(trials)
        # cost_savings = (0.01 - 0.005) / 0.01 = 0.5
        assert "0.5000" in table

    def test_zero_baseline_cost_no_division_error(self):
        from agent_evals.context.compression import render_compression_tradeoff_table

        trials = [
            {
                "variant_name": "zero_base",
                "compression_ratio": 0.5,
                "accuracy": 0.8,
                "cost": 0.0,
                "baseline_cost": 0.0,
            },
        ]
        # Should not raise ZeroDivisionError
        table = render_compression_tradeoff_table(trials)
        assert "zero_base" in table

    def test_missing_fields_use_defaults(self):
        from agent_evals.context.compression import render_compression_tradeoff_table

        trials = [{}]  # All fields missing
        table = render_compression_tradeoff_table(trials)
        assert "unknown" in table

    def test_net_benefit_is_accuracy_times_savings(self):
        from agent_evals.context.compression import render_compression_tradeoff_table

        trials = [
            {
                "variant_name": "net_test",
                "compression_ratio": 0.6,
                "accuracy": 0.8,
                "cost": 0.002,
                "baseline_cost": 0.01,
            },
        ]
        table = render_compression_tradeoff_table(trials)
        # cost_savings = (0.01 - 0.002) / 0.01 = 0.8
        # net_benefit = 0.8 * 0.8 = 0.64
        assert "0.6400" in table


# ---------------------------------------------------------------------------
# Structured vs prose compaction
# ---------------------------------------------------------------------------


class TestStructuredVsProseCompaction:
    """Compare compression on structured markdown vs plain prose."""

    def test_structured_markdown_compresses_with_format_conversion(self):
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy(method="format_conversion")
        task = make_mock_task()
        doc_tree = MagicMock()

        structured = (
            "# API Reference\n"
            "## Authentication\n"
            "- Bearer token required\n"
            "- API key in header\n"
            "## Endpoints\n"
            "- GET /users\n"
            "- POST /users\n"
        )
        prepared = strategy.prepare(structured, task, doc_tree)
        assert prepared.strategy_metadata["compression_method"] == "format_conversion"
        assert prepared.strategy_metadata["compressed_tokens"] > 0

    def test_prose_compresses_with_algorithmic(self):
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy(method="algorithmic")
        task = make_mock_task()
        doc_tree = MagicMock()

        prose = (
            "The authentication system is designed to be used with bearer "
            "tokens that are passed in the authorization header of each "
            "request. The tokens should be kept secure and should not be "
            "shared with any unauthorized parties."
        )
        prepared = strategy.prepare(prose, task, doc_tree)
        assert prepared.strategy_metadata["compression_method"] == "algorithmic"
        # Algorithmic should reduce tokens on verbose prose
        assert prepared.strategy_metadata["compressed_tokens"] <= prepared.strategy_metadata["original_tokens"]

    def test_algorithmic_on_structured_still_works(self):
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy(method="algorithmic")
        task = make_mock_task()
        doc_tree = MagicMock()

        structured = "# Title\n- Item one\n- Item two\nSome text here"
        prepared = strategy.prepare(structured, task, doc_tree)
        assert prepared.strategy_metadata["compressed_tokens"] > 0

    def test_unknown_method_returns_text_unchanged(self):
        from agent_evals.context.compression import CompressionStrategy

        strategy = CompressionStrategy(method="unknown_method")
        # _compress should return text unchanged for unknown method
        result = strategy._compress("original text")
        assert result == "original text"


# ---------------------------------------------------------------------------
# StrategyConfig has compression_method field
# ---------------------------------------------------------------------------


class TestStrategyConfigCompressionField:
    """StrategyConfig should include compression_method field."""

    def test_default_compression_method(self):
        from agent_evals.context.base import StrategyConfig

        cfg = StrategyConfig()
        assert cfg.compression_method == "algorithmic"

    def test_custom_compression_method(self):
        from agent_evals.context.base import StrategyConfig

        cfg = StrategyConfig(compression_method="llm_summarized")
        assert cfg.compression_method == "llm_summarized"


class TestLLMSummarizeMaxTokens:
    """Bug #221: _llm_summarize should use token count, not character count."""

    def test_max_tokens_uses_token_estimate_not_char_count(self):
        """max_tokens should be ~len(text)//4//2 (token estimate / 2), not len(text)//2."""
        from unittest.mock import MagicMock

        from agent_evals.context.compression import CompressionStrategy
        from agent_evals.llm.client import GenerationResult

        strategy = CompressionStrategy(method="llm_summarized")

        # 1000 chars -> ~250 tokens -> max_tokens should be ~125
        # Bug: len(text)//2 = 500 (way too high)
        text = "x" * 1000
        mock_client = MagicMock()
        mock_client.complete.return_value = GenerationResult(
            content="summary",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.01,
            model="test",
            generation_id="test-id",
        )

        strategy._llm_summarize(text, mock_client)

        call_kwargs = mock_client.complete.call_args
        actual_max_tokens = call_kwargs.kwargs.get(
            "max_tokens", call_kwargs[1].get("max_tokens")
        )
        # With the bug: max_tokens = 1000 // 2 = 500
        # After fix: max_tokens = 1000 // 4 // 2 = 125
        # The value should be well below 250 (half of char-based estimate)
        assert actual_max_tokens < 250, (
            f"max_tokens={actual_max_tokens} is based on character count, "
            f"not token count. Should be ~125, not 500."
        )


# ---------------------------------------------------------------------------
# Bug #284: _llm_summarize must pass timeout to client.complete
# ---------------------------------------------------------------------------


class TestLLMSummarizeTimeout:
    """Bug #284: _llm_summarize must pass timeout to prevent hung connections."""

    def test_llm_summarize_passes_timeout(self):
        """_llm_summarize() must pass timeout=120.0 to client.complete()."""
        from unittest.mock import MagicMock

        from agent_evals.context.compression import CompressionStrategy
        from agent_evals.llm.client import GenerationResult

        strategy = CompressionStrategy(method="llm_summarized")

        mock_client = MagicMock()
        mock_client.complete.return_value = GenerationResult(
            content="summary",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.01,
            model="test",
            generation_id="test-id",
        )

        strategy._llm_summarize("some documentation text", mock_client)

        call_kwargs = mock_client.complete.call_args
        actual_timeout = call_kwargs.kwargs.get(
            "timeout", call_kwargs[1].get("timeout") if len(call_kwargs) > 1 else None
        )
        assert actual_timeout == 120.0, (
            f"_llm_summarize must pass timeout=120.0 to client.complete(), "
            f"got timeout={actual_timeout} (Bug #284)"
        )
