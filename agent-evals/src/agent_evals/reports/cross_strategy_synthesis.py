"""Cross-strategy synthesis report -- Phase C exit criteria."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def find_concordant_factors(
    results: dict[str, dict[str, Any]],
    threshold: float = 0.5,
) -> dict[str, dict[str, Any]]:
    """Find factors where strategies agree on the optimal level.

    Parameters
    ----------
    results:
        Mapping of strategy_name -> {"optimal_levels": {factor: level, ...}, ...}
    threshold:
        Minimum fraction of strategies that must agree for concordance.

    Returns
    -------
    dict mapping factor_name to
        {"level", "agreement", "strategies", "total_strategies"}.
    """
    factor_votes: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for strategy_name, result in results.items():
        for factor, level in result.get("optimal_levels", {}).items():
            factor_votes[factor].append((strategy_name, level))

    concordant: dict[str, dict[str, Any]] = {}
    for factor, votes in factor_votes.items():
        levels = [level for _, level in votes]
        counter = Counter(levels)
        most_common_level, count = counter.most_common(1)[0]
        agreement = count / len(votes)
        if agreement >= threshold:
            concordant[factor] = {
                "level": most_common_level,
                "agreement": round(agreement, 4),
                "strategies": [s for s, l in votes if l == most_common_level],
                "total_strategies": len(votes),
            }
    return concordant


def find_disagreement_factors(
    results: dict[str, dict[str, Any]],
    threshold: float = 0.5,
) -> dict[str, dict[str, Any]]:
    """Find factors where strategies *disagree* on the optimal level.

    Parameters
    ----------
    results:
        Same shape as *find_concordant_factors*.
    threshold:
        Factors with agreement strictly below this are considered
        disagreements.

    Returns
    -------
    dict mapping factor_name to
        {"levels" (Counter dict), "per_strategy", "agreement"}.
    """
    factor_votes: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for strategy_name, result in results.items():
        for factor, level in result.get("optimal_levels", {}).items():
            factor_votes[factor].append((strategy_name, level))

    disagreements: dict[str, dict[str, Any]] = {}
    for factor, votes in factor_votes.items():
        levels = [level for _, level in votes]
        counter = Counter(levels)
        _, count = counter.most_common(1)[0]
        agreement = count / len(votes)
        if agreement < threshold:
            disagreements[factor] = {
                "levels": dict(counter),
                "per_strategy": {s: l for s, l in votes},
                "agreement": round(agreement, 4),
            }
    return disagreements


def format_optimal_combination(optimal_levels: dict[str, str]) -> str:
    """Return a human-readable string of optimal factor/level pairs."""
    if not optimal_levels:
        return "no recommendation (no data)"
    parts = []
    for factor, level in sorted(optimal_levels.items()):
        parts.append(f"{level} ({factor})")
    return ", ".join(parts)


def rank_format_recommendations(
    strategy_phase_results: dict[str, dict[str, Any]],
) -> dict[str, str]:
    """Return per-strategy recommendation strings."""
    recommendations: dict[str, str] = {}
    for strategy, results in strategy_phase_results.items():
        optimal_levels = results.get("optimal_levels", {})
        recommendations[strategy] = format_optimal_combination(optimal_levels)
    return recommendations


def generate_cross_strategy_recommendation(
    phase_results_by_strategy: dict[str, dict[str, Any]],
) -> str:
    """Build the full cross-strategy synthesis report (Markdown).

    Parameters
    ----------
    phase_results_by_strategy:
        Mapping of strategy_name -> {
            "optimal_levels": {factor: level},
            "factor_rankings": [(factor, importance), ...],
            "mean_score": float,
        }

    Returns
    -------
    Markdown-formatted report string.
    """
    concordant = find_concordant_factors(phase_results_by_strategy)
    disagreements = find_disagreement_factors(phase_results_by_strategy)

    lines: list[str] = [
        "# Cross-Strategy Synthesis Report",
        "",
        f"**Strategies analyzed:** {len(phase_results_by_strategy)}",
        (
            f"**Strategies:** "
            f"{', '.join(sorted(phase_results_by_strategy.keys()))}"
        ),
        "",
        "## Strategy Performance",
        "",
    ]

    for strategy, result in sorted(
        phase_results_by_strategy.items(),
        key=lambda x: x[1].get("mean_score", 0),
        reverse=True,
    ):
        score = result.get("mean_score", 0)
        lines.append(f"- **{strategy}**: mean_score={score:.4f}")

    # --- Universal recommendations ---
    lines.extend([
        "",
        "## Universal Recommendations (agree across strategies)",
        "",
    ])
    if concordant:
        for factor, info in sorted(concordant.items()):
            agreement_pct = info["agreement"] * 100
            lines.append(
                f"- **{factor}**: Use `{info['level']}` "
                f"({agreement_pct:.0f}% agreement across "
                f"{info['total_strategies']} strategies)"
            )
    else:
        lines.append("- No factors showed universal agreement.")

    # --- Disagreements ---
    lines.extend([
        "",
        "## Strategy-Specific Recommendations (disagree across strategies)",
        "",
    ])
    if disagreements:
        for factor, info in sorted(disagreements.items()):
            lines.append(f"- **{factor}**: {info['levels']}")
            for strategy, level in sorted(info["per_strategy"].items()):
                lines.append(f"  - {strategy}: `{level}`")
    else:
        lines.append("- All factors agree across strategies.")

    # --- Final recommendation ---
    lines.extend(["", "## Final Recommendation", ""])
    if concordant:
        recs = [
            f"{factor}=`{info['level']}`"
            for factor, info in sorted(concordant.items())
        ]
        lines.append(
            "For an MCP-based agent reading compressed docs through "
            f"dynamic tools, use: {', '.join(recs)}."
        )
    else:
        lines.append(
            "No universal format recommendation possible -- optimal "
            "format depends on the context delivery strategy."
        )

    # --- Per-strategy optimal formats ---
    per_strategy_recs = rank_format_recommendations(
        phase_results_by_strategy,
    )
    lines.extend(["", "## Per-Strategy Optimal Formats", ""])
    for strategy, rec in sorted(per_strategy_recs.items()):
        lines.append(f"- **{strategy}**: {rec}")

    return "\n".join(lines)
