"""Markdown report renderer.

Generates a plain-text Markdown report from ReportData with tables
for variant, task-type, and source breakdowns.
"""

from __future__ import annotations

from agent_evals.reports.aggregator import ReportData


def render_markdown(data: ReportData) -> str:
    """Render ReportData into a Markdown report.

    Args:
        data: Aggregated report data.

    Returns:
        Complete Markdown document as a string.
    """
    sections: list[str] = []

    # Title
    sections.append("# Agent Evals Research Report\n")

    # 1. Executive Summary
    sections.append("## Executive Summary\n")
    sections.append(f"- **Total Trials:** {data.total_trials}")
    sections.append(f"- **Total Cost:** ${data.total_cost:.4f}")
    sections.append(f"- **Variants:** {len(data.by_variant)}")
    sections.append(f"- **Sources:** {len(data.by_source)}")
    if data.by_variant:
        best_name = max(
            data.by_variant, key=lambda k: data.by_variant[k].mean_score
        )
        best_score = data.by_variant[best_name].mean_score
        sections.append(
            f"\nBest performing variant: **{best_name}** "
            f"(mean score {best_score:.3f})"
        )
    sections.append("")

    # 2. Experimental Design
    sections.append("## Experimental Design\n")
    sections.append("| Parameter | Value |")
    sections.append("| --- | --- |")
    sections.append(f"| Repetitions | {data.config.repetitions} |")
    sections.append(f"| Temperature | {data.config.temperature} |")
    sections.append(f"| Max Tokens | {data.config.max_tokens} |")
    sections.append("")

    # 3. Variant Analysis
    sections.append("## Variant Analysis\n")
    sections.append("| Variant | Trials | Mean Score | Total Cost |")
    sections.append("| --- | ---: | ---: | ---: |")
    for name, summary in data.by_variant.items():
        sections.append(
            f"| {name} | {summary.count} | "
            f"{summary.mean_score:.3f} | "
            f"${summary.total_cost:.4f} |"
        )
    sections.append("")

    # 4. Task Type Analysis
    sections.append("## Task Type Analysis\n")
    sections.append("| Task Type | Trials | Mean Score |")
    sections.append("| --- | ---: | ---: |")
    for name, summary in data.by_task_type.items():
        sections.append(
            f"| {name} | {summary.count} | "
            f"{summary.mean_score:.3f} |"
        )
    sections.append("")

    # 5. Source Breakdown
    sections.append("## Source Breakdown\n")
    sections.append("| Source | Trials | Mean Score |")
    sections.append("| --- | ---: | ---: |")
    for name, summary in data.by_source.items():
        sections.append(
            f"| {name} | {summary.count} | "
            f"{summary.mean_score:.3f} |"
        )
    sections.append("")

    # 6. Model Versions
    sections.append("## Model Versions\n")
    if data.model_versions:
        sections.append("| Requested Model | API Version |")
        sections.append("| --- | --- |")
        for requested, actual in data.model_versions.items():
            sections.append(f"| {requested} | {actual} |")
    else:
        sections.append("No model version information available.")
    sections.append("")

    # 7. Cost Analysis
    sections.append("## Cost Analysis\n")
    sections.append(f"- **Total Cost:** ${data.total_cost:.4f}")
    if data.by_variant:
        sections.append("\n| Variant | Cost |")
        sections.append("| --- | ---: |")
        for name, summary in data.by_variant.items():
            sections.append(f"| {name} | ${summary.total_cost:.4f} |")
    sections.append("")

    # 8. Robustness Analysis
    scores = [s.mean_score for s in data.by_variant.values()]
    score_range = max(scores) - min(scores) if scores else 0.0
    sections.append("## Robustness Analysis\n")
    sections.append(
        f"Score variability across variants: "
        f"{'high' if score_range > 0.1 else 'low'} "
        f"(range: {score_range:.3f})"
    )
    sections.append("")

    # 9. Appendix
    sections.append("## Appendix\n")
    sections.append("### A.1 Methodology\n")
    sections.append(
        f"This report was generated from {data.total_trials} trials across "
        f"{len(data.by_variant)} variants and "
        f"{len(data.by_source)} task sources."
    )
    sections.append("")
    sections.append("### A.2 Configuration\n")
    sections.append("```json")
    sections.append("{")
    sections.append(f'  "repetitions": {data.config.repetitions},')
    sections.append(f'  "temperature": {data.config.temperature},')
    sections.append(f'  "max_tokens": {data.config.max_tokens}')
    sections.append("}")
    sections.append("```\n")

    return "\n".join(sections)
