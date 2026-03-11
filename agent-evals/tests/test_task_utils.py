"""Tests for task scoring utilities (_utils module).

Tests cover:
- Basic keyword extraction from text
- Stopword filtering
- Punctuation stripping (commas, periods, parentheses, etc.)
- Single-quote stripping from keywords
- Double-quote stripping from keywords
- Minimum word length (3+ characters)
"""

from __future__ import annotations

from agent_evals.tasks._utils import STOPWORDS, extract_keywords


class TestExtractKeywords:
    """Tests for extract_keywords utility function."""

    def test_extracts_basic_keywords(self) -> None:
        """Basic words are extracted as keywords."""
        result = extract_keywords("maximum connection timeout")
        assert result == ["maximum", "connection", "timeout"]

    def test_filters_stopwords(self) -> None:
        """Common stopwords are excluded from results."""
        result = extract_keywords("the use of middleware patterns")
        assert "the" not in result
        assert "use" not in result
        assert "middleware" in result
        assert "patterns" in result

    def test_filters_short_words(self) -> None:
        """Words shorter than 3 characters are excluded."""
        result = extract_keywords("it is an ok day")
        assert result == ["day"]

    def test_strips_trailing_punctuation(self) -> None:
        """Trailing punctuation is stripped from tokens."""
        result = extract_keywords("timeout, connection. value!")
        assert "timeout" in result
        assert "connection" in result
        assert "value" in result

    def test_strips_parentheses(self) -> None:
        """Parentheses are stripped from tokens."""
        result = extract_keywords("install (recommended) package")
        assert "recommended" in result

    def test_strips_single_quotes(self) -> None:
        """Single quotes are stripped from keyword tokens."""
        result = extract_keywords("install -e '.[dev]' for development")
        keywords_lower = [k.lower() for k in result]
        # After stripping quotes and dots, '.[dev]' becomes '[dev]'
        assert "[dev]" in keywords_lower

    def test_single_quoted_word_extracted(self) -> None:
        """A single-quoted word like 'config' yields config."""
        result = extract_keywords("use 'config' file")
        assert "config" in result
        # The quotes should be stripped
        assert "'config'" not in result

    def test_strips_double_quotes(self) -> None:
        """Double quotes are stripped from keyword tokens."""
        result = extract_keywords('the "timeout" setting')
        assert "timeout" in result
        assert '"timeout"' not in result

    def test_empty_string_returns_empty(self) -> None:
        """Empty string returns empty list."""
        assert extract_keywords("") == []

    def test_all_stopwords_returns_empty(self) -> None:
        """String of only stopwords returns empty list."""
        assert extract_keywords("the and for are but") == []

    def test_preserves_case(self) -> None:
        """Keywords preserve their original case."""
        result = extract_keywords("DataForge Configuration")
        assert "DataForge" in result
        assert "Configuration" in result


class TestStopwords:
    """Tests for the STOPWORDS constant."""

    def test_stopwords_is_frozenset(self) -> None:
        """STOPWORDS is a frozenset for immutability and fast lookups."""
        assert isinstance(STOPWORDS, frozenset)

    def test_common_words_in_stopwords(self) -> None:
        """Common English words are in the stopwords set."""
        for word in ("the", "and", "for", "with", "from"):
            assert word in STOPWORDS
