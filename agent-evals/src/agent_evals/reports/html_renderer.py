"""HTML report renderer with embedded Plotly charts.

Generates a self-contained HTML report from ReportData with interactive
charts, inline CSS, and all 9 report sections.
"""

from __future__ import annotations

import json
from typing import Any

import jinja2

from agent_evals.reports.aggregator import ReportData

_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Agent Evals Research Report</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body { font-family: system-ui, sans-serif; max-width: 1200px; margin: 0 auto; padding: 2rem; color: #222; }
    h1 { border-bottom: 2px solid #333; padding-bottom: 0.5rem; }
    h2 { color: #1a5276; margin-top: 2rem; }
    table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
    th, td { border: 1px solid #ddd; padding: 0.5rem; text-align: left; }
    th { background: #f4f6f9; }
    tr:nth-child(even) { background: #fafafa; }
    .chart { width: 100%; height: 400px; margin: 1rem 0; }
    .metric { display: inline-block; background: #eef; padding: 0.75rem 1.5rem; margin: 0.5rem; border-radius: 6px; }
    .metric .value { font-size: 1.5rem; font-weight: bold; }
    .metric .label { font-size: 0.85rem; color: #666; }
    nav { background: #f4f6f9; padding: 1rem; border-radius: 6px; margin-bottom: 2rem; }
    nav a { margin-right: 1rem; color: #1a5276; text-decoration: none; }
    nav a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <h1>Agent Evals Research Report</h1>

  <nav>
    <a href="#executive-summary">Executive Summary</a>
    <a href="#experimental-design">Experimental Design</a>
    <a href="#variant-analysis">Variant Analysis</a>
    <a href="#task-type-analysis">Task Type Analysis</a>
    <a href="#source-breakdown">Source Breakdown</a>
    <a href="#model-versions">Model Versions</a>
    <a href="#charts">Charts</a>
    <a href="#appendix">Appendix</a>
  </nav>

  <!-- 1. Executive Summary -->
  <section id="executive-summary">
    <h2>Executive Summary</h2>
    <div>
      <div class="metric"><div class="value">{{ total_trials }}</div><div class="label">Total Trials</div></div>
      <div class="metric"><div class="value">${{ "%.4f"|format(total_cost) }}</div><div class="label">Total Cost</div></div>
      <div class="metric"><div class="value">{{ variant_count }}</div><div class="label">Variants</div></div>
      <div class="metric"><div class="value">{{ source_count }}</div><div class="label">Sources</div></div>
    </div>
    {% if best_variant %}
    <p>Best performing variant: <strong>{{ best_variant.name }}</strong> (mean score {{ "%.3f"|format(best_variant.score) }})</p>
    {% endif %}
  </section>

  <!-- 2. Experimental Design -->
  <section id="experimental-design">
    <h2>Experimental Design</h2>
    <table>
      <tr><th>Parameter</th><th>Value</th></tr>
      <tr><td>Repetitions</td><td>{{ config.repetitions }}</td></tr>
      <tr><td>Temperature</td><td>{{ config.temperature }}</td></tr>
      <tr><td>Max Tokens</td><td>{{ config.max_tokens }}</td></tr>
    </table>
  </section>

  <!-- 3. Variant Analysis -->
  <section id="variant-analysis">
    <h2>Variant Analysis</h2>
    <table>
      <tr><th>Variant</th><th>Trials</th><th>Mean Score</th><th>Total Cost</th></tr>
      {% for name, summary in by_variant.items() %}
      <tr>
        <td>{{ name }}</td>
        <td>{{ summary.count }}</td>
        <td>{{ "%.3f"|format(summary.mean_score) }}</td>
        <td>${{ "%.4f"|format(summary.total_cost) }}</td>
      </tr>
      {% endfor %}
    </table>
  </section>

  <!-- 4. Task Type Analysis -->
  <section id="task-type-analysis">
    <h2>Task Type Analysis</h2>
    <table>
      <tr><th>Task Type</th><th>Trials</th><th>Mean Score</th></tr>
      {% for name, summary in by_task_type.items() %}
      <tr>
        <td>{{ name }}</td>
        <td>{{ summary.count }}</td>
        <td>{{ "%.3f"|format(summary.mean_score) }}</td>
      </tr>
      {% endfor %}
    </table>
  </section>

  <!-- 5. Source Breakdown -->
  <section id="source-breakdown">
    <h2>Source Breakdown</h2>
    <table>
      <tr><th>Source</th><th>Trials</th><th>Mean Score</th></tr>
      {% for name, summary in by_source.items() %}
      <tr>
        <td>{{ name }}</td>
        <td>{{ summary.count }}</td>
        <td>{{ "%.3f"|format(summary.mean_score) }}</td>
      </tr>
      {% endfor %}
    </table>
  </section>

  <!-- 6. Model Versions -->
  <section id="model-versions">
    <h2>Model Versions</h2>
    {% if model_versions %}
    <table>
      <tr><th>Requested Model</th><th>API Version</th></tr>
      {% for requested, actual in model_versions.items() %}
      <tr><td>{{ requested }}</td><td>{{ actual }}</td></tr>
      {% endfor %}
    </table>
    {% else %}
    <p>No model version information available.</p>
    {% endif %}
  </section>

  <!-- 7. Charts -->
  <section id="charts">
    <h2>Performance Charts</h2>
    <div id="variant-chart" class="chart"></div>
    <div id="task-type-chart" class="chart"></div>
  </section>

  <script>
    // Variant scores bar chart
    Plotly.newPlot('variant-chart', [{{ variant_chart_json }}], {
      title: 'Mean Score by Variant',
      xaxis: {title: 'Variant'},
      yaxis: {title: 'Mean Score', range: [0, 1]}
    });

    // Task type scores bar chart
    Plotly.newPlot('task-type-chart', [{{ task_type_chart_json }}], {
      title: 'Mean Score by Task Type',
      xaxis: {title: 'Task Type'},
      yaxis: {title: 'Mean Score', range: [0, 1]}
    });
  </script>

  <!-- 8. Robustness Analysis -->
  <section id="robustness">
    <h2>Robustness Analysis</h2>
    <p>Score standard deviations across variants indicate
    {{ "high" if score_range > 0.1 else "low" }} variability
    (range: {{ "%.3f"|format(score_range) }}).</p>
  </section>

  {% if phase_results %}
  <!-- 10. Main Effects Analysis -->
  <section id="main-effects">
    <h2>Main Effects Analysis</h2>
    {% if phase_results.main_effects %}
    <table>
      <tr><th>Factor</th><th>Levels</th><th>Delta (max − min)</th></tr>
      {% for factor, levels in phase_results.main_effects.items() %}
      <tr>
        <td>{{ factor }}</td>
        <td>{% for level, val in levels.items() %}{{ level }}: {{ "%.2f"|format(val) }}{% if not loop.last %}, {% endif %}{% endfor %}</td>
        <td>{{ "%.2f"|format(levels.values()|list|max - levels.values()|list|min) }}</td>
      </tr>
      {% endfor %}
    </table>
    {% endif %}
  </section>

  <!-- 11. ANOVA Table -->
  <section id="anova">
    <h2>ANOVA Table</h2>
    {% if phase_results.anova %}
    <table>
      <tr><th>Factor</th><th>SS</th><th>df</th><th>MS</th><th>F-ratio</th><th>p-value</th><th>&omega;&sup2;</th><th>Significance</th></tr>
      {% for factor, a in phase_results.anova.items() %}
      <tr>
        <td>{{ factor }}</td>
        <td>{{ "%.3f"|format(a.ss) }}</td>
        <td>{{ a.df }}</td>
        <td>{{ "%.3f"|format(a.ms) }}</td>
        <td>{{ "%.3f"|format(a.f_ratio) }}</td>
        <td>{{ "%.4f"|format(a.p_value) }}</td>
        <td>{{ "%.4f"|format(a.omega_squared) }}</td>
        <td>{% if a.p_value <= 0.001 %}***{% elif a.p_value <= 0.01 %}**{% elif a.p_value <= 0.05 %}*{% else %}n.s.{% endif %}</td>
      </tr>
      {% endfor %}
    </table>
    <p><small>*** p &lt; 0.001, ** p &lt; 0.01, * p &lt; 0.05, n.s. = not significant</small></p>
    {% endif %}
  </section>

  <!-- 12. Statistical Assumptions & Power -->
  <section id="assumptions">
    <h2>Statistical Assumptions &amp; Power</h2>
    <table>
      <tr><th>Property</th><th>Value</th></tr>
      <tr><td>Quality Type</td><td>{{ phase_results.quality_type | default("not specified") }}</td></tr>
      <tr><td>Factors Analyzed</td><td>{{ phase_results.anova.keys()|list|length if phase_results.anova else 0 }}</td></tr>
      {% if phase_results.significant_factors %}
      <tr><td>Significant Factors</td><td>{{ phase_results.significant_factors|length }}</td></tr>
      {% endif %}
    </table>
  </section>

  <!-- 13. Post-Hoc Comparisons -->
  <section id="post-hoc">
    <h2>Post-Hoc Comparisons</h2>
    {% if phase_results.significant_factors %}
    <table>
      <tr><th>Factor</th><th>&omega;&sup2;</th><th>Interpretation</th></tr>
      {% for factor in phase_results.significant_factors %}
      {% set omega = phase_results.anova[factor].omega_squared if phase_results.anova and factor in phase_results.anova else 0.0 %}
      <tr>
        <td>{{ factor }}</td>
        <td>{{ "%.4f"|format(omega) }}</td>
        <td>{% if omega >= 0.14 %}large{% elif omega >= 0.06 %}medium{% elif omega >= 0.01 %}small{% else %}negligible{% endif %}</td>
      </tr>
      {% endfor %}
    </table>
    {% else %}
    <p>No significant factors identified.</p>
    {% endif %}
  </section>

  <!-- 14. Optimal Prediction & Confirmation -->
  <section id="optimal-prediction">
    <h2>Optimal Prediction &amp; Confirmation</h2>
    {% if phase_results.optimal %}
    <h3>Optimal Configuration</h3>
    <table>
      <tr><th>Factor</th><th>Best Level</th></tr>
      {% for factor, level in phase_results.optimal.items() %}
      <tr><td>{{ factor }}</td><td>{{ level }}</td></tr>
      {% endfor %}
    </table>
    {% endif %}
    {% if phase_results.predicted_sn is defined and phase_results.predicted_sn is not none %}
    <p>Predicted S/N Ratio: <strong>{{ "%.2f"|format(phase_results.predicted_sn) }}</strong></p>
    {% endif %}
    {% if phase_results.prediction_interval %}
    <p>Prediction Interval: [{{ "%.2f"|format(phase_results.prediction_interval[0]) }}, {{ "%.2f"|format(phase_results.prediction_interval[1]) }}]</p>
    {% endif %}
  </section>
  {% endif %}

  <!-- 9. Appendix -->
  <section id="appendix">
    <h2>Appendix</h2>
    <h3>A.1 Methodology</h3>
    <p>This report was generated from {{ total_trials }} trials across
    {{ variant_count }} variants and {{ source_count }} task sources.</p>
    <h3>A.2 Configuration</h3>
    <pre>{{ config_json }}</pre>
  </section>

</body>
</html>
"""


def render_html(data: ReportData) -> str:
    """Render ReportData into a self-contained HTML report.

    Args:
        data: Aggregated report data.

    Returns:
        Complete HTML document as a string.
    """
    # Find best variant
    best_variant: dict[str, Any] | None = None
    if data.by_variant:
        best_name = max(
            data.by_variant, key=lambda k: data.by_variant[k].mean_score
        )
        best_variant = {
            "name": best_name,
            "score": data.by_variant[best_name].mean_score,
        }

    # Compute score range for robustness
    scores = [s.mean_score for s in data.by_variant.values()]
    score_range = max(scores) - min(scores) if scores else 0.0

    # Build Plotly chart data
    variant_chart = _bar_chart_json(
        {k: v.mean_score for k, v in data.by_variant.items()}
    )
    task_type_chart = _bar_chart_json(
        {k: v.mean_score for k, v in data.by_task_type.items()}
    )

    # Config JSON for appendix
    config_json = json.dumps(
        {
            "repetitions": data.config.repetitions,
            "temperature": data.config.temperature,
            "max_tokens": data.config.max_tokens,
        },
        indent=2,
    )

    template = jinja2.Template(_TEMPLATE)
    return template.render(
        total_trials=data.total_trials,
        total_cost=data.total_cost,
        variant_count=len(data.by_variant),
        source_count=len(data.by_source),
        best_variant=best_variant,
        config=data.config,
        by_variant=data.by_variant,
        by_task_type=data.by_task_type,
        by_source=data.by_source,
        model_versions=data.model_versions,
        variant_chart_json=variant_chart,
        task_type_chart_json=task_type_chart,
        score_range=score_range,
        config_json=config_json,
        phase_results=data.phase_results,
    )


def _bar_chart_json(data: dict[str, float]) -> str:
    """Generate Plotly bar chart trace JSON."""
    trace = {
        "x": list(data.keys()),
        "y": list(data.values()),
        "type": "bar",
    }
    return json.dumps(trace)
