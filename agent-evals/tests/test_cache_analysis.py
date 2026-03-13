"""Tests for KV-cache friendliness analysis."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from agent_evals.reports.cache_analysis import (
    build_cache_report,
    cache_friendliness_score,
    compute_cache_hit_rate,
    correlate_format_with_cache,
    get_variant_format_properties,
    prefix_stability_score,
    run_sequential_cache_test,
)


class TestCacheHitRate:
    def test_compute_cache_hit_rate(self):
        result = compute_cache_hit_rate(400, 1000)
        assert result == pytest.approx(0.4)

    def test_zero_prompt_tokens(self):
        result = compute_cache_hit_rate(100, 0)
        assert result == 0.0


class TestCacheFriendlinessScore:
    def test_high_hit_rate_scores_well(self):
        trials = [
            {"cached_tokens": 800, "prompt_tokens": 1000},
            {"cached_tokens": 900, "prompt_tokens": 1000},
            {"cached_tokens": 850, "prompt_tokens": 1000},
        ]
        score = cache_friendliness_score(trials)
        assert score > 0.7

    def test_low_hit_rate_scores_poorly(self):
        trials = [
            {"cached_tokens": 50, "prompt_tokens": 1000},
            {"cached_tokens": 100, "prompt_tokens": 1000},
            {"cached_tokens": 30, "prompt_tokens": 1000},
        ]
        score = cache_friendliness_score(trials)
        assert score < 0.2

    def test_empty_trials_returns_zero(self):
        assert cache_friendliness_score([]) == 0.0


class TestCacheAnalysisReport:
    def test_build_report_groups_by_variant(self):
        trials = [
            {"variant_name": "yaml", "cached_tokens": 800, "prompt_tokens": 1000, "cache_write_tokens": 200},
            {"variant_name": "yaml", "cached_tokens": 900, "prompt_tokens": 1000, "cache_write_tokens": 100},
            {"variant_name": "json", "cached_tokens": 400, "prompt_tokens": 1000, "cache_write_tokens": 600},
        ]
        report = build_cache_report(trials)
        assert "yaml" in report
        assert "json" in report
        assert report["yaml"]["total_trials"] == 2
        assert report["json"]["total_trials"] == 1
        assert report["yaml"]["mean_hit_rate"] == pytest.approx(0.85)
        assert report["json"]["mean_hit_rate"] == pytest.approx(0.4)
        assert report["yaml"]["mean_write_tokens"] == pytest.approx(150.0)

    def test_empty_trials(self):
        assert build_cache_report([]) == {}


class TestSequentialCacheTest:
    def test_sequential_tasks_track_cache_growth(self):
        # Create mock tasks with question attributes
        tasks = []
        for i in range(3):
            task = MagicMock()
            task.definition.question = f"Question {i}"
            tasks.append(task)

        # Create mock variant
        variant = MagicMock()
        variant.metadata.return_value = SimpleNamespace(name="yaml")

        # Create mock client that returns increasing cached_tokens
        client = MagicMock()
        responses = [
            SimpleNamespace(
                content="Answer 0",
                cached_tokens=0,
                prompt_tokens=100,
                completion_tokens=20,
                total_tokens=120,
            ),
            SimpleNamespace(
                content="Answer 1",
                cached_tokens=80,
                prompt_tokens=200,
                completion_tokens=25,
                total_tokens=225,
            ),
            SimpleNamespace(
                content="Answer 2",
                cached_tokens=180,
                prompt_tokens=300,
                completion_tokens=30,
                total_tokens=330,
            ),
        ]
        client.complete.side_effect = responses

        results = run_sequential_cache_test(variant, tasks, client)

        assert len(results) == 3
        # Cache should grow across sequential calls
        assert results[0]["cached_tokens"] == 0
        assert results[1]["cached_tokens"] == 80
        assert results[2]["cached_tokens"] == 180
        assert results[0]["position"] == 0
        assert results[2]["position"] == 2
        assert results[0]["variant_name"] == "yaml"

    def test_prefix_stability_score(self):
        # Highly stable cache rates -> high score
        stable_trials = [
            {"cached_tokens": 800, "prompt_tokens": 1000},
            {"cached_tokens": 810, "prompt_tokens": 1000},
            {"cached_tokens": 790, "prompt_tokens": 1000},
            {"cached_tokens": 805, "prompt_tokens": 1000},
        ]
        score = prefix_stability_score(stable_trials)
        assert 0.0 <= score <= 1.0
        assert score > 0.9  # Very stable

        # Unstable cache rates -> lower score
        unstable_trials = [
            {"cached_tokens": 100, "prompt_tokens": 1000},
            {"cached_tokens": 800, "prompt_tokens": 1000},
            {"cached_tokens": 200, "prompt_tokens": 1000},
            {"cached_tokens": 700, "prompt_tokens": 1000},
        ]
        unstable_score = prefix_stability_score(unstable_trials)
        assert unstable_score < score

    def test_prefix_stability_empty(self):
        assert prefix_stability_score([]) == 0.0


class TestFormatCacheCorrelation:
    def test_format_cache_correlation(self):
        trials = [
            {"variant_name": "yaml", "cached_tokens": 900, "prompt_tokens": 1000},
            {"variant_name": "yaml", "cached_tokens": 850, "prompt_tokens": 1000},
            {"variant_name": "json", "cached_tokens": 880, "prompt_tokens": 1000},
            {"variant_name": "flat", "cached_tokens": 300, "prompt_tokens": 1000},
            {"variant_name": "flat", "cached_tokens": 350, "prompt_tokens": 1000},
            {"variant_name": "random", "cached_tokens": 100, "prompt_tokens": 1000},
        ]
        variant_metadata = {
            "yaml": {"positioning_stability": 1.0, "serialization_complexity": 1.0},
            "json": {"positioning_stability": 1.0, "serialization_complexity": 0.9},
            "flat": {"positioning_stability": 0.5, "serialization_complexity": 0.0},
            "random": {"positioning_stability": 0.0, "serialization_complexity": 0.1},
        }
        result = correlate_format_with_cache(trials, variant_metadata)
        assert "positioning_stability_correlation" in result
        assert "serialization_complexity_correlation" in result
        # Positioning stability should correlate positively with cache hit rate
        assert result["positioning_stability_correlation"] > 0

    def test_empty_trials(self):
        assert correlate_format_with_cache([]) == {}


class TestVariantFormatProperties:
    def test_variant_format_properties_maps_known_variants(self):
        props = get_variant_format_properties("yaml")
        assert "hierarchy_depth" in props
        assert "positioning_stability" in props
        assert "serialization_complexity" in props
        assert "metadata_richness" in props
        assert props["positioning_stability"] == 1.0
        assert props["serialization_complexity"] == 1.0

    def test_unknown_variant_returns_defaults(self):
        props = get_variant_format_properties("nonexistent_variant_xyz")
        assert "hierarchy_depth" in props
        assert "positioning_stability" in props
        # Should return defaults, not raise
        assert isinstance(props["hierarchy_depth"], (int, float))

    def test_correlate_format_with_cache_auto_maps(self):
        """correlate_format_with_cache auto-maps variant names when no metadata provided."""
        trials = [
            {"variant_name": "yaml", "cached_tokens": 900, "prompt_tokens": 1000},
            {"variant_name": "flat", "cached_tokens": 300, "prompt_tokens": 1000},
            {"variant_name": "random", "cached_tokens": 100, "prompt_tokens": 1000},
        ]
        # No variant_metadata passed -- should auto-map via get_variant_format_properties
        result = correlate_format_with_cache(trials)
        assert isinstance(result, dict)
        # Should have correlations for the standard properties
        assert any("correlation" in key for key in result)
