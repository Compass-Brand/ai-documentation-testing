"""Multi-objective Taguchi analysis for cost, latency, and accuracy."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agent_evals.taguchi.analysis import (
    ANOVAResult,
    compute_main_effects,
    compute_sn_ratios,
    run_anova,
)

if TYPE_CHECKING:
    from agent_evals.taguchi.factors import TaguchiDesign


def run_multi_objective_analysis(
    design: TaguchiDesign,
    row_scores: dict[int, list[float]],
    row_costs: dict[int, list[float]],
    row_latencies: dict[int, list[float]],
) -> dict[str, dict]:
    """Run Taguchi analysis on accuracy, cost, and latency simultaneously.

    Each objective uses the appropriate S/N quality type:
    - accuracy: larger_is_better (higher scores are better)
    - cost: smaller_is_better (lower cost is better)
    - latency: smaller_is_better (lower latency is better)

    Args:
        design: The Taguchi experimental design.
        row_scores: Mapping of row_id to list of accuracy scores.
        row_costs: Mapping of row_id to list of cost observations.
        row_latencies: Mapping of row_id to list of latency observations.

    Returns:
        Dict keyed by objective name ("accuracy", "cost", "latency") with
        sub-keys "sn_ratios", "main_effects", and "anova" for each.
        Objectives with empty row data are omitted.
    """
    objectives: dict[str, tuple[str, dict[int, list[float]]]] = {
        "accuracy": ("larger_is_better", row_scores),
        "cost": ("smaller_is_better", row_costs),
        "latency": ("smaller_is_better", row_latencies),
    }

    results: dict[str, dict] = {}
    for name, (quality_type, row_data) in objectives.items():
        if not row_data:
            continue
        sn = compute_sn_ratios(row_data, quality_type=quality_type)
        effects = compute_main_effects(design, sn)
        anova = run_anova(design, sn)
        results[name] = {
            "sn_ratios": sn,
            "main_effects": effects,
            "anova": anova,
        }

    return results
