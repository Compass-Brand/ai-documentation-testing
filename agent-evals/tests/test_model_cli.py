"""Tests for CLI model browser with filtering, sorting, and output formats."""

from __future__ import annotations

import json

import pytest

from agent_evals.observatory.model_cli import (
    apply_cli_filters,
    format_model_detail,
    format_models_csv,
    format_models_json,
    format_models_table,
    fuzzy_search,
    sort_models,
)


SAMPLE_MODELS = [
    {"id": "a/cheap", "name": "Cheap", "prompt_price": 0.0,
     "completion_price": 0.0, "context_length": 4096, "created": 1700000000,
     "modality": "text", "tokenizer": "gpt",
     "supported_params": []},
    {"id": "b/mid", "name": "Mid", "prompt_price": 0.003,
     "completion_price": 0.015, "context_length": 100000, "created": 1710000000,
     "modality": "text+image", "tokenizer": "claude",
     "supported_params": ["tools", "json_mode"]},
    {"id": "c/premium", "name": "Premium", "prompt_price": 0.010,
     "completion_price": 0.030, "context_length": 200000, "created": 1720000000,
     "modality": "text+image", "tokenizer": "claude",
     "supported_params": ["tools"]},
]


class TestSortModels:
    """Sort model lists by various columns."""

    def test_sort_by_price_ascending(self):
        result = sort_models(SAMPLE_MODELS, "price")
        prices = [m["prompt_price"] for m in result]
        assert prices == sorted(prices)

    def test_sort_by_created_descending(self):
        result = sort_models(SAMPLE_MODELS, "-created")
        dates = [m["created"] for m in result]
        assert dates == sorted(dates, reverse=True)

    def test_sort_by_context(self):
        result = sort_models(SAMPLE_MODELS, "context")
        contexts = [m["context_length"] for m in result]
        assert contexts == sorted(contexts)

    def test_sort_by_name(self):
        result = sort_models(SAMPLE_MODELS, "name")
        names = [m["name"] for m in result]
        assert names == sorted(names)


class TestFuzzySearch:
    """Fuzzy text search across model fields."""

    def test_search_by_name(self):
        results = fuzzy_search(SAMPLE_MODELS, "premium")
        assert len(results) == 1
        assert results[0]["id"] == "c/premium"

    def test_search_by_id(self):
        results = fuzzy_search(SAMPLE_MODELS, "b/mid")
        assert len(results) == 1

    def test_search_case_insensitive(self):
        results = fuzzy_search(SAMPLE_MODELS, "CHEAP")
        assert len(results) == 1

    def test_search_no_match(self):
        results = fuzzy_search(SAMPLE_MODELS, "nonexistent")
        assert len(results) == 0


class TestOutputFormats:
    """Output models in different formats."""

    def test_json_output_valid(self):
        output = format_models_json(SAMPLE_MODELS)
        parsed = json.loads(output)
        assert len(parsed) == 3
        assert parsed[0]["id"] == "a/cheap"

    def test_csv_output_valid(self):
        output = format_models_csv(SAMPLE_MODELS)
        lines = output.strip().split("\n")
        assert len(lines) == 4  # header + 3 rows
        assert "id" in lines[0]

    def test_table_output_nonempty(self):
        output = format_models_table(SAMPLE_MODELS)
        assert len(output) > 0
        assert "Cheap" in output


class TestModelDetail:
    """Show detailed model information."""

    def test_show_model_returns_formatted_detail(self):
        detail = format_model_detail(SAMPLE_MODELS[1])
        assert "Mid" in detail
        assert "100000" in detail


class TestFilterCombination:
    """Combine multiple CLI filters."""

    def test_all_filters_combine(self):
        results = apply_cli_filters(
            SAMPLE_MODELS,
            free=False, max_price=0.010, min_context=100000,
            modality="text+image", tokenizer="claude",
        )
        assert len(results) == 2  # mid and premium

    def test_free_filter_only(self):
        results = apply_cli_filters(SAMPLE_MODELS, free=True)
        assert len(results) == 1
        assert results[0]["id"] == "a/cheap"

    def test_max_price_filter(self):
        results = apply_cli_filters(SAMPLE_MODELS, max_price=0.005)
        ids = [m["id"] for m in results]
        assert "a/cheap" in ids
        assert "b/mid" in ids
        assert "c/premium" not in ids

    def test_min_context_filter(self):
        results = apply_cli_filters(SAMPLE_MODELS, min_context=100000)
        assert len(results) == 2

    def test_modality_filter(self):
        results = apply_cli_filters(SAMPLE_MODELS, modality="text+image")
        assert len(results) == 2

    def test_tokenizer_filter(self):
        results = apply_cli_filters(SAMPLE_MODELS, tokenizer="claude")
        assert len(results) == 2
