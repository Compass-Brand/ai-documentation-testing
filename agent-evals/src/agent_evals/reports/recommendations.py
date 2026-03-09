"""Generate plain-language recommendations from Taguchi analysis results."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StrategyBreakdown:
    """Per-strategy result for a single factor."""

    strategy: str
    best_level: str
    effect_size: float


@dataclass
class Finding:
    """A single actionable finding from Taguchi screening."""

    factor_name: str
    best_level: str
    worst_level: str
    effect_size: float
    p_value: float
    confidence_interval: tuple[float, float] | None = None
    strategy_breakdowns: list[StrategyBreakdown] = field(
        default_factory=list
    )


def generate_findings(
    anova_results: dict,
    main_effects: dict,
    strategy_results: dict | None = None,
) -> list[Finding]:
    """Generate findings from Taguchi ANOVA and main effects.

    Only produces findings for statistically significant factors.
    """
    findings = []
    for factor, anova in anova_results.items():
        if not anova.get("significant", False):
            continue

        effects = main_effects.get(factor, {})
        if not effects:
            continue

        best_level = max(effects, key=effects.get)
        worst_level = min(effects, key=effects.get)
        effect_size = effects[best_level] - effects[worst_level]

        breakdowns = []
        if strategy_results and factor in strategy_results:
            for strategy, strat_effects in strategy_results[factor].items():
                strat_best = max(strat_effects, key=strat_effects.get)
                strat_effect = (
                    strat_effects[strat_best]
                    - strat_effects[min(strat_effects, key=strat_effects.get)]
                )
                breakdowns.append(
                    StrategyBreakdown(strategy, strat_best, strat_effect)
                )

        findings.append(
            Finding(
                factor_name=factor,
                best_level=best_level,
                worst_level=worst_level,
                effect_size=effect_size,
                p_value=anova["p_value"],
                strategy_breakdowns=breakdowns,
            )
        )

    return sorted(findings, key=lambda f: f.effect_size, reverse=True)


def render_findings_text(findings: list[Finding]) -> str:
    """Render findings as plain-language text for documentation authors."""
    if not findings:
        return "No statistically significant findings."

    sections = []
    for i, f in enumerate(findings, 1):
        lines = [
            f"FINDING {i}: {_humanize_factor(f.factor_name)}",
            f"  Best:  {f.best_level}",
            f"  Worst: {f.worst_level}",
            f"  Effect size: +{f.effect_size:.1f} points",
        ]
        if f.confidence_interval:
            lo, hi = f.confidence_interval
            lines.append(f"  95% CI: [{lo:.1f}, {hi:.1f}]")
        lines.append(f"  p-value: {f.p_value:.4f}")

        if f.strategy_breakdowns:
            lines.append("")
            strategies_agree = len(
                {b.best_level for b in f.strategy_breakdowns}
            ) == 1
            lines.append(
                f"  Consistent across strategies: "
                f"{'yes' if strategies_agree else 'NO — strategies disagree'}"
            )
            for b in f.strategy_breakdowns:
                marker = " <-" if b.best_level != f.best_level else ""
                lines.append(
                    f"    {b.strategy:20s} {b.best_level} "
                    f"(+{b.effect_size:.1f} pts){marker}"
                )

        sections.append("\n".join(lines))

    return "\n\n".join(sections)


def render_anova_table(anova_results: dict) -> str:
    """Render ANOVA results as a markdown pipe-delimited table.

    Columns: Factor, Sum of Squares, df, Mean Square, F-statistic,
    p-value, Significant (after BH correction).
    """
    header = (
        "| Factor | Sum of Squares | df | Mean Square "
        "| F-statistic | p-value | Significant |"
    )
    separator = (
        "|--------|----------------|-----|-------------|"
        "-------------|---------|-------------|"
    )
    rows = []
    for factor, data in anova_results.items():
        sig = "Yes*" if data.get("significant") else "No"
        rows.append(
            f"| {factor} "
            f"| {data['sum_of_squares']:.2f} "
            f"| {data['df']} "
            f"| {data['mean_square']:.2f} "
            f"| {data['f_statistic']:.2f} "
            f"| {data['p_value']:.4f} "
            f"| {sig} |"
        )
    footnote = "* Significant after Benjamini-Hochberg correction"
    return "\n".join([header, separator, *rows, "", footnote])


def extract_strategy_breakdowns(
    strategy_phase_results: dict,
    factor: str,
) -> list[StrategyBreakdown]:
    """Extract per-strategy StrategyBreakdown objects for a given factor.

    Each strategy in strategy_phase_results is expected to have a
    'main_effects' dict mapping factor names to {level: score} dicts.
    """
    breakdowns = []
    for strategy, phase_data in strategy_phase_results.items():
        effects = phase_data.get("main_effects", {}).get(factor, {})
        if not effects:
            continue
        best = max(effects, key=effects.get)
        worst = min(effects, key=effects.get)
        breakdowns.append(
            StrategyBreakdown(
                strategy=strategy,
                best_level=best,
                effect_size=effects[best] - effects[worst],
            )
        )
    return breakdowns


def _humanize_factor(factor_name: str) -> str:
    """Convert axis_1_structure to 'Documentation structure'."""
    mapping = {
        "axis_1_structure": "Documentation hierarchy depth",
        "axis_2_metadata": "Metadata richness",
        "axis_3_format": "Serialization format",
        "axis_4_position": "Content positioning",
        "axis_5_scale": "Documentation scale",
        "axis_6_granularity": "Chunk granularity",
        "axis_7_noise": "Noise tolerance",
        "axis_8_xref": "Cross-references",
        "axis_9_transform": "Documentation transformation",
        "axis_10_temporal": "Temporal metadata",
    }
    return mapping.get(factor_name, factor_name.replace("_", " ").title())
