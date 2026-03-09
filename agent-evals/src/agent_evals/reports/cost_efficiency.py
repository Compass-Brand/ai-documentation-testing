"""Cost-efficiency analysis and Pareto frontier computation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CostEfficiencyRow:
    """A single variant's cost-efficiency profile."""

    variant: str
    accuracy: float
    cost: float
    stability: float
    cache_hit_rate: float = 0.0
    pareto: bool = False
    strategy: str | None = None


def compute_pareto_frontier(
    rows: list[CostEfficiencyRow],
    *,
    strategy: str | None = None,
) -> list[CostEfficiencyRow]:
    """Identify Pareto-optimal variants (higher accuracy, lower cost).

    A variant is Pareto-optimal if no other variant has both
    higher accuracy AND lower cost.
    """
    if strategy is not None:
        rows = [r for r in rows if r.strategy == strategy]

    if not rows:
        return []

    frontier = []
    for candidate in rows:
        dominated = False
        for other in rows:
            if other is candidate:
                continue
            if (
                other.accuracy >= candidate.accuracy
                and other.cost <= candidate.cost
                and (
                    other.accuracy > candidate.accuracy
                    or other.cost < candidate.cost
                )
            ):
                dominated = True
                break
        if not dominated:
            candidate.pareto = True
            frontier.append(candidate)

    return frontier


def _render_single_table(rows: list[CostEfficiencyRow]) -> str:
    """Render a single cost-efficiency table section."""
    if not rows:
        return "No data available."

    sorted_rows = sorted(rows, key=lambda r: r.accuracy, reverse=True)

    header = (
        f"{'VARIANT':<25s} {'ACCURACY':>10s} {'COST/TRIAL':>12s} "
        f"{'CACHE HIT':>10s} {'VARIANCE':>10s} {'STATUS':>16s}"
    )
    sep = "-" * len(header)
    lines = [header, sep]

    for r in sorted_rows:
        status = "Pareto optimal" if r.pareto else ""
        lines.append(
            f"{r.variant:<25s} {r.accuracy:>9.1f}% "
            f"${r.cost:>10.4f} {r.cache_hit_rate:>9.0f}% "
            f"{r.stability:>9.1f}% {status:>16s}"
        )

    return "\n".join(lines)


def render_cost_efficiency_table(
    rows: list[CostEfficiencyRow],
    *,
    group_by_strategy: bool = False,
) -> str:
    """Render a cost-efficiency comparison table."""
    if not rows:
        return "No data available."

    if group_by_strategy:
        strategies = sorted({r.strategy for r in rows if r.strategy})
        sections = []
        for strat in strategies:
            strat_rows = [r for r in rows if r.strategy == strat]
            sections.append(f"\n### Strategy: {strat}\n")
            sections.append(_render_single_table(strat_rows))
        return "\n".join(sections)

    return _render_single_table(rows)
