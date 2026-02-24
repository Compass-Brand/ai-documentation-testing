"""Observatory CLI subcommand functions.

Provides formatted text output for observatory operations:
list runs, compare runs, detect regressions, cost trends, model ranking.
"""

from __future__ import annotations

from agent_evals.observatory.history import (
    compare_runs,
    cost_trend as _cost_trend,
    detect_regressions,
    model_ranking as _model_ranking,
)
from agent_evals.observatory.store import ObservatoryStore


def cli_list_runs(store: ObservatoryStore) -> str:
    """List all runs with summary statistics.

    Returns:
        Formatted table string of all runs.
    """
    runs = store.list_runs()
    if not runs:
        return "No runs found."

    header = (
        f"{'Run ID':<20} {'Type':<10} {'Status':<10} "
        f"{'Trials':>8} {'Cost':>10} {'Avg Lat':>8}"
    )
    lines = [header, "-" * len(header)]
    for r in runs:
        cost_str = f"${r.total_cost:.4f}"
        lat_str = f"{r.avg_latency:.2f}s"
        lines.append(
            f"{r.run_id:<20} {r.run_type:<10} {r.status:<10} "
            f"{r.total_trials:>8} {cost_str:>10} {lat_str:>8}"
        )
    return "\n".join(lines)


def cli_compare_runs(
    store: ObservatoryStore,
    run_ids: list[str],
) -> str:
    """Compare runs side by side.

    Returns:
        Formatted comparison table.
    """
    results = compare_runs(store, run_ids)
    if not results:
        return "No runs to compare."

    header = (
        f"{'Run ID':<20} {'Trials':>8} {'Avg Score':>10} "
        f"{'Total Cost':>12} {'Delta':>8}"
    )
    lines = [header, "-" * len(header)]
    for r in results:
        delta_str = f"{r['score_delta']:+.4f}" if r["score_delta"] else ""
        cost_str = f"${r['total_cost']:.4f}"
        lines.append(
            f"{r['run_id']:<20} {r['total_trials']:>8} "
            f"{r['avg_score']:>10.4f} {cost_str:>12} {delta_str:>8}"
        )
    return "\n".join(lines)


def cli_regressions(
    store: ObservatoryStore,
    baseline_run_id: str,
    comparison_run_id: str,
    *,
    threshold: float = 0.05,
) -> str:
    """Detect and format regressions between two runs.

    Returns:
        Formatted regression report.
    """
    regressions = detect_regressions(
        store, baseline_run_id, comparison_run_id, threshold=threshold
    )
    if not regressions:
        return (
            f"No regressions detected between {baseline_run_id} "
            f"and {comparison_run_id} (threshold={threshold})."
        )

    header = (
        f"{'Variant':<20} {'Baseline':>10} {'Current':>10} {'Delta':>10}"
    )
    lines = [
        f"Regressions ({baseline_run_id} -> {comparison_run_id}):",
        header,
        "-" * len(header),
    ]
    for r in regressions:
        lines.append(
            f"{r['variant']:<20} {r['baseline_score']:>10.4f} "
            f"{r['comparison_score']:>10.4f} {r['delta']:>+10.4f}"
        )
    return "\n".join(lines)


def cli_cost_trend(
    store: ObservatoryStore,
    run_ids: list[str],
) -> str:
    """Show cost trends across runs.

    Returns:
        Formatted cost trend table.
    """
    trend = _cost_trend(store, run_ids)
    if not trend:
        return "No cost data available."

    header = f"{'Run ID':<20} {'Total Cost':>12} {'Avg/Trial':>12}"
    lines = [header, "-" * len(header)]
    for entry in trend:
        total = f"${entry['total_cost']:.4f}"
        avg = f"${entry['avg_cost_per_trial']:.4f}"
        lines.append(f"{entry['run_id']:<20} {total:>12} {avg:>12}")
    return "\n".join(lines)


def cli_model_ranking(
    store: ObservatoryStore,
    run_ids: list[str],
) -> str:
    """Rank models by performance across runs.

    Returns:
        Formatted model ranking table.
    """
    ranking = _model_ranking(store, run_ids)
    if not ranking:
        return "No model data available."

    header = (
        f"{'#':>3} {'Model':<30} {'Avg Score':>10} "
        f"{'Trials':>8} {'Avg Cost':>10}"
    )
    lines = [header, "-" * len(header)]
    for i, r in enumerate(ranking, 1):
        cost_str = f"${r['avg_cost']:.4f}"
        lines.append(
            f"{i:>3} {r['model']:<30} {r['avg_score']:>10.4f} "
            f"{r['total_trials']:>8} {cost_str:>10}"
        )
    return "\n".join(lines)
