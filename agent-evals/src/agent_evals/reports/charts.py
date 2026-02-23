"""Shared chart library for Plotly JSON generation.

All functions return lists of Plotly-compatible trace dicts that can be
serialized to JSON and rendered by Plotly.js in HTML reports.
"""

from __future__ import annotations

from typing import Any


def generate_main_effects_plotly(
    data: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    """Generate bar chart traces for main effects per factor.

    Args:
        data: Mapping of factor name to {level: mean_score}.

    Returns:
        One bar trace per factor.
    """
    traces: list[dict[str, Any]] = []
    for factor, levels in data.items():
        traces.append({
            "x": list(levels.keys()),
            "y": list(levels.values()),
            "type": "bar",
            "name": factor,
        })
    return traces


def generate_interaction_plot(
    data: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    """Generate line traces for interaction effects.

    Args:
        data: Mapping of level_a -> {level_b: score}.

    Returns:
        One scatter trace per level of the first factor.
    """
    traces: list[dict[str, Any]] = []
    for level_name, points in data.items():
        traces.append({
            "x": list(points.keys()),
            "y": list(points.values()),
            "type": "scatter",
            "mode": "lines+markers",
            "name": level_name,
        })
    return traces


def generate_radar_chart(
    data: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    """Generate radar (scatterpolar) traces for model comparison.

    Args:
        data: Mapping of model_name -> {task_type: score}.

    Returns:
        One scatterpolar trace per model.
    """
    traces: list[dict[str, Any]] = []
    for model, scores in data.items():
        categories = list(scores.keys())
        values = list(scores.values())
        # Close the polygon
        traces.append({
            "type": "scatterpolar",
            "r": values + [values[0]],
            "theta": categories + [categories[0]],
            "fill": "toself",
            "name": model,
        })
    return traces


def generate_box_plots(
    data: dict[str, list[float]],
) -> list[dict[str, Any]]:
    """Generate box plot traces for score distributions.

    Args:
        data: Mapping of variant_name -> list of scores.

    Returns:
        One box trace per variant.
    """
    traces: list[dict[str, Any]] = []
    for name, scores in data.items():
        traces.append({
            "type": "box",
            "y": scores,
            "name": name,
        })
    return traces


def generate_burn_chart(
    data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate cost burn line chart with budget cap.

    Args:
        data: Dict with "costs" (cumulative list) and "budget" (cap).

    Returns:
        Line trace for costs and horizontal line for budget.
    """
    costs = data["costs"]
    budget = data.get("budget")
    traces: list[dict[str, Any]] = [
        {
            "type": "scatter",
            "y": costs,
            "x": list(range(len(costs))),
            "mode": "lines",
            "name": "Cumulative Cost",
        },
    ]
    if budget is not None:
        traces.append({
            "type": "scatter",
            "y": [budget] * max(2, len(costs)),
            "x": list(range(max(2, len(costs)))),
            "mode": "lines",
            "name": "Budget",
            "line": {"dash": "dash", "color": "red"},
        })
    return traces


def generate_sn_response_table(
    data: dict[str, dict[str, float]],
) -> dict[str, dict[str, Any]]:
    """Generate S/N response table data per factor.

    Args:
        data: Mapping of factor_name -> {level: sn_ratio}.

    Returns:
        Dict per factor with levels, values, and delta (max - min).
    """
    result: dict[str, dict[str, Any]] = {}
    for factor, levels in data.items():
        values = list(levels.values())
        result[factor] = {
            "levels": levels,
            "delta": max(values) - min(values) if values else 0.0,
        }
    return result


def generate_confirmation_chart(
    data: dict[str, float],
) -> list[dict[str, Any]]:
    """Generate predicted vs observed confirmation chart.

    Args:
        data: Dict with "predicted", "observed", "ci_half_width".

    Returns:
        Traces for predicted and observed values with CI band.
    """
    predicted = data["predicted"]
    observed = data["observed"]
    ci = data.get("ci_half_width", 0.0)

    traces: list[dict[str, Any]] = [
        {
            "type": "bar",
            "x": ["S/N Ratio"],
            "y": [predicted],
            "name": "Predicted",
            "error_y": {"type": "data", "array": [ci], "visible": True},
        },
        {
            "type": "bar",
            "x": ["S/N Ratio"],
            "y": [observed],
            "name": "Observed",
        },
    ]
    return traces
