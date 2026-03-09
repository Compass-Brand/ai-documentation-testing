"""KV-cache friendliness analysis."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def compute_cache_hit_rate(cached_tokens: int, prompt_tokens: int) -> float:
    """Compute cache hit rate as ratio of cached to prompt tokens.

    Returns 0.0 when prompt_tokens is zero to avoid division by zero.
    """
    if prompt_tokens == 0:
        return 0.0
    return cached_tokens / prompt_tokens


def cache_friendliness_score(trials: list[dict[str, Any]]) -> float:
    """Average cache hit rate across all trials."""
    if not trials:
        return 0.0
    rates = [
        compute_cache_hit_rate(
            t.get("cached_tokens", 0),
            t.get("prompt_tokens", 0),
        )
        for t in trials
    ]
    return sum(rates) / len(rates)


def build_cache_report(
    trials: list[dict[str, Any]],
) -> dict[str, dict[str, float]]:
    """Group trials by variant and compute per-variant cache metrics."""
    if not trials:
        return {}

    by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trial in trials:
        by_variant[trial.get("variant_name", "unknown")].append(trial)

    report: dict[str, dict[str, float]] = {}
    for variant, variant_trials in sorted(by_variant.items()):
        hit_rates = [
            compute_cache_hit_rate(
                t.get("cached_tokens", 0),
                t.get("prompt_tokens", 0),
            )
            for t in variant_trials
        ]
        write_tokens = [
            t.get("cache_write_tokens", 0) for t in variant_trials
        ]
        report[variant] = {
            "mean_hit_rate": sum(hit_rates) / len(hit_rates),
            "mean_write_tokens": sum(write_tokens) / len(write_tokens),
            "total_trials": len(variant_trials),
        }
    return report


def run_sequential_cache_test(
    variant: Any,
    tasks: list[Any],
    client: Any,
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> list[dict[str, Any]]:
    """Run tasks sequentially to track KV-cache token growth.

    Builds a growing conversation so the provider can cache the shared
    prefix, then records how ``cached_tokens`` increases over time.
    """
    results: list[dict[str, Any]] = []
    messages: list[dict[str, str]] = [
        {"role": "system", "content": "Answer based on documentation."},
    ]

    for i, task in enumerate(tasks):
        question = getattr(task.definition, "question", f"Task {i}")
        messages.append({"role": "user", "content": question})

        generation = client.complete(
            messages, max_tokens=max_tokens, temperature=temperature,
        )
        content = generation.content or ""
        messages.append({"role": "assistant", "content": content})

        results.append({
            "position": i,
            "cached_tokens": getattr(generation, "cached_tokens", 0),
            "prompt_tokens": generation.prompt_tokens,
            "completion_tokens": generation.completion_tokens,
            "total_tokens": generation.total_tokens,
            "variant_name": (
                variant.metadata().name
                if hasattr(variant, "metadata")
                else "unknown"
            ),
        })

    return results


def prefix_stability_score(trials: list[dict[str, Any]]) -> float:
    """Score how stable cache hit rates are (1 - CV, clamped 0..1).

    A score near 1.0 means the prefix is very consistently cached;
    near 0.0 means cache behaviour is erratic.
    """
    if not trials:
        return 0.0

    cache_rates = [
        compute_cache_hit_rate(
            t.get("cached_tokens", 0),
            t.get("prompt_tokens", 0),
        )
        for t in trials
    ]
    if not cache_rates:
        return 0.0

    mean = sum(cache_rates) / len(cache_rates)
    if mean == 0:
        return 0.0

    variance = sum((r - mean) ** 2 for r in cache_rates) / len(cache_rates)
    std_dev = variance ** 0.5
    cv = std_dev / mean if mean > 0 else 1.0
    return max(0.0, min(1.0, 1.0 - cv))


def get_variant_format_properties(variant_name: str) -> dict[str, float]:
    """Map a variant name to numeric format properties.

    Known variants get hand-tuned values; unknown variants get defaults.
    """
    properties: dict[str, dict[str, float]] = {
        "flat": {
            "hierarchy_depth": 0,
            "positioning_stability": 0.5,
            "serialization_complexity": 0.0,
            "metadata_richness": 0.2,
        },
        "2-tier": {
            "hierarchy_depth": 2,
            "positioning_stability": 0.8,
            "serialization_complexity": 0.2,
            "metadata_richness": 0.4,
        },
        "3-tier": {
            "hierarchy_depth": 3,
            "positioning_stability": 0.8,
            "serialization_complexity": 0.3,
            "metadata_richness": 0.5,
        },
        "4-tier": {
            "hierarchy_depth": 4,
            "positioning_stability": 0.9,
            "serialization_complexity": 0.3,
            "metadata_richness": 0.6,
        },
        "yaml": {
            "hierarchy_depth": 2,
            "positioning_stability": 1.0,
            "serialization_complexity": 1.0,
            "metadata_richness": 0.7,
        },
        "json": {
            "hierarchy_depth": 2,
            "positioning_stability": 1.0,
            "serialization_complexity": 0.9,
            "metadata_richness": 0.7,
        },
        "xml": {
            "hierarchy_depth": 2,
            "positioning_stability": 1.0,
            "serialization_complexity": 0.8,
            "metadata_richness": 0.6,
        },
        "markdown": {
            "hierarchy_depth": 2,
            "positioning_stability": 0.7,
            "serialization_complexity": 0.3,
            "metadata_richness": 0.5,
        },
        "random": {
            "hierarchy_depth": 1,
            "positioning_stability": 0.0,
            "serialization_complexity": 0.1,
            "metadata_richness": 0.2,
        },
        "alphabetical": {
            "hierarchy_depth": 1,
            "positioning_stability": 1.0,
            "serialization_complexity": 0.1,
            "metadata_richness": 0.2,
        },
        "path-only": {
            "hierarchy_depth": 1,
            "positioning_stability": 0.5,
            "serialization_complexity": 0.0,
            "metadata_richness": 0.0,
        },
        "summary": {
            "hierarchy_depth": 1,
            "positioning_stability": 0.5,
            "serialization_complexity": 0.2,
            "metadata_richness": 0.6,
        },
        "detailed": {
            "hierarchy_depth": 2,
            "positioning_stability": 0.7,
            "serialization_complexity": 0.4,
            "metadata_richness": 1.0,
        },
    }
    default = {
        "hierarchy_depth": 1,
        "positioning_stability": 0.5,
        "serialization_complexity": 0.3,
        "metadata_richness": 0.3,
    }
    return properties.get(variant_name, default)


def correlate_format_with_cache(
    trials: list[dict[str, Any]],
    variant_metadata: dict[str, dict[str, Any]] | None = None,
) -> dict[str, float]:
    """Pearson correlation between numeric format properties and cache rate.

    When *variant_metadata* is ``None``, properties are auto-mapped via
    :func:`get_variant_format_properties`.
    """
    if not trials:
        return {}

    if variant_metadata is None:
        variant_names = {
            t.get("variant_name", "unknown") for t in trials
        }
        variant_metadata = {
            name: get_variant_format_properties(name)
            for name in variant_names
        }

    variant_rates: dict[str, list[float]] = defaultdict(list)
    for trial in trials:
        vname = trial.get("variant_name", "unknown")
        rate = compute_cache_hit_rate(
            trial.get("cached_tokens", 0),
            trial.get("prompt_tokens", 0),
        )
        variant_rates[vname].append(rate)

    mean_rates: dict[str, float] = {
        v: sum(rates) / len(rates)
        for v, rates in variant_rates.items()
        if rates
    }

    all_props: set[str] = set()
    for meta in variant_metadata.values():
        for k, v in meta.items():
            if isinstance(v, (int, float)):
                all_props.add(k)

    result: dict[str, float] = {}
    for prop in sorted(all_props):
        x_vals: list[float] = []
        y_vals: list[float] = []
        for vname, rate in mean_rates.items():
            if vname in variant_metadata and prop in variant_metadata[vname]:
                val = variant_metadata[vname][prop]
                if isinstance(val, (int, float)):
                    x_vals.append(float(val))
                    y_vals.append(rate)

        if len(x_vals) >= 2:
            n = len(x_vals)
            mean_x = sum(x_vals) / n
            mean_y = sum(y_vals) / n
            cov = sum(
                (x - mean_x) * (y - mean_y)
                for x, y in zip(x_vals, y_vals)
            ) / n
            std_x = (sum((x - mean_x) ** 2 for x in x_vals) / n) ** 0.5
            std_y = (sum((y - mean_y) ** 2 for y in y_vals) / n) ** 0.5
            if std_x > 0 and std_y > 0:
                result[f"{prop}_correlation"] = round(
                    cov / (std_x * std_y), 4,
                )
            else:
                result[f"{prop}_correlation"] = 0.0

    return result
