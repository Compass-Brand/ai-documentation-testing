"""Tests for task scoring utilities (_utils module).

Tests cover:
- Basic keyword extraction from text
- Stopword filtering
- Punctuation stripping (commas, periods, parentheses, etc.)
- Single-quote stripping from keywords
- Double-quote stripping from keywords
- Minimum word length (3+ characters)
- fuzzy_to_continuous_score piecewise linear interpolation
"""

from __future__ import annotations

from agent_evals.tasks._utils import STOPWORDS, extract_keywords, fuzzy_to_continuous_score


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


class TestFuzzyToContinuousScore:
    """Tests for fuzzy_to_continuous_score piecewise linear interpolation."""

    def test_below_50_returns_none(self) -> None:
        """Scores below 50 return None (caller falls back to keyword layer)."""
        assert fuzzy_to_continuous_score(49.9) is None
        assert fuzzy_to_continuous_score(0.0) is None
        assert fuzzy_to_continuous_score(30.0) is None

    def test_exact_100_returns_1(self) -> None:
        """Score of 100.0 maps to 1.0."""
        assert fuzzy_to_continuous_score(100.0) == 1.0

    def test_exact_85_returns_0_9(self) -> None:
        """Score of 85.0 maps to 0.9 (bottom of top tier)."""
        assert fuzzy_to_continuous_score(85.0) == 0.9

    def test_exact_70_returns_0_7(self) -> None:
        """Score of 70.0 maps to 0.7 (bottom of middle tier)."""
        assert fuzzy_to_continuous_score(70.0) == 0.7

    def test_exact_50_returns_0_5(self) -> None:
        """Score of 50.0 maps to 0.5 (bottom of low tier)."""
        assert fuzzy_to_continuous_score(50.0) == 0.5

    def test_mid_top_tier(self) -> None:
        """92.5 is midpoint of [85,100] -> midpoint of [0.9,1.0] = 0.95."""
        result = fuzzy_to_continuous_score(92.5)
        assert abs(result - 0.95) < 1e-9

    def test_mid_middle_tier(self) -> None:
        """77.5 is midpoint of [70,85) -> midpoint of [0.7,0.9) = 0.8."""
        result = fuzzy_to_continuous_score(77.5)
        assert abs(result - 0.8) < 1e-9

    def test_mid_low_tier(self) -> None:
        """60.0 is midpoint of [50,70) -> midpoint of [0.5,0.7) = 0.6."""
        result = fuzzy_to_continuous_score(60.0)
        assert abs(result - 0.6) < 1e-9

    def test_monotonically_increasing(self) -> None:
        """Higher fuzzy scores always produce higher continuous scores."""
        scores = [50.0, 55.0, 60.0, 65.0, 70.0, 75.0, 80.0, 85.0, 90.0, 95.0, 100.0]
        results = [fuzzy_to_continuous_score(s) for s in scores]
        for i in range(len(results) - 1):
            assert results[i] < results[i + 1], (
                f"Not monotonic: f({scores[i]})={results[i]} >= f({scores[i+1]})={results[i+1]}"
            )

    def test_output_range(self) -> None:
        """All valid outputs are in [0.5, 1.0]."""
        for s in range(50, 101):
            result = fuzzy_to_continuous_score(float(s))
            assert result is not None
            assert 0.5 <= result <= 1.0, f"f({s})={result} out of range"
