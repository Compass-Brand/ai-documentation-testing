"""Tests for HTML Report Renderer."""

from __future__ import annotations

import pytest
from agent_evals.reports.aggregator import ReportData, VariantSummary
from agent_evals.reports.html_renderer import render_html
from agent_evals.runner import EvalRunConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _report_data(**overrides) -> ReportData:
    """Create a minimal ReportData for testing."""
    defaults = {
        "config": EvalRunConfig(),
        "total_trials": 100,
        "total_cost": 1.50,
        "by_variant": {
            "flat": VariantSummary(count=50, mean_score=0.82, total_cost=0.75),
            "3tier": VariantSummary(count=50, mean_score=0.78, total_cost=0.75),
        },
        "by_task_type": {
            "retrieval": VariantSummary(count=60, mean_score=0.80, total_cost=0.90),
            "code_gen": VariantSummary(count=40, mean_score=0.75, total_cost=0.60),
        },
        "by_source": {
            "gold_standard": VariantSummary(count=80, mean_score=0.80, total_cost=1.20),
            "repliqa": VariantSummary(count=20, mean_score=0.76, total_cost=0.30),
        },
        "model_versions": {"claude-sonnet-4.5": "claude-3-5-sonnet-20241022"},
    }
    defaults.update(overrides)
    return ReportData(**defaults)


def _taguchi_report_data() -> ReportData:
    """Create a ReportData with Taguchi phase_results for testing."""
    phase_results = {
        "main_effects": {
            "structure": {"flat": 8.5, "nested": 12.3, "hierarchical": 11.0},
            "transform": {"raw": 7.2, "summary": 11.8, "compressed": 9.5},
        },
        "anova": {
            "structure": {
                "ss": 12.34,
                "df": 2,
                "ms": 6.17,
                "f_ratio": 8.72,
                "p_value": 0.001,
                "eta_squared": 0.12,
                "omega_squared": 0.089,
            },
            "transform": {
                "ss": 11.89,
                "df": 2,
                "ms": 5.95,
                "f_ratio": 8.41,
                "p_value": 0.001,
                "eta_squared": 0.11,
                "omega_squared": 0.084,
            },
            "granularity": {
                "ss": 2.1,
                "df": 2,
                "ms": 1.05,
                "f_ratio": 1.48,
                "p_value": 0.24,
                "eta_squared": 0.03,
                "omega_squared": 0.008,
            },
        },
        "optimal": {"structure": "nested", "transform": "summary"},
        "significant_factors": ["structure", "transform"],
        "quality_type": "larger_is_better",
        "sn_ratios": {0: 10.5, 1: 11.2, 2: 9.8},
        "prediction_interval": [10.0, 13.5],
        "predicted_sn": 12.3,
    }
    return _report_data(phase_results=phase_results)


# ---------------------------------------------------------------------------
# TestHTMLStructure
# ---------------------------------------------------------------------------


class TestHTMLStructure:
    """Valid HTML output structure."""

    def test_starts_with_doctype(self) -> None:
        html = render_html(_report_data())
        assert html.strip().startswith("<!DOCTYPE html>")

    def test_contains_html_tags(self) -> None:
        html = render_html(_report_data())
        assert "<html" in html
        assert "<body>" in html
        assert "</html>" in html

    def test_is_nonempty(self) -> None:
        html = render_html(_report_data())
        assert len(html) > 100


# ---------------------------------------------------------------------------
# TestSections
# ---------------------------------------------------------------------------


class TestSections:
    """All 9 report sections present."""

    def test_executive_summary_present(self) -> None:
        html = render_html(_report_data())
        assert "Executive Summary" in html

    def test_experimental_design_present(self) -> None:
        html = render_html(_report_data())
        assert "Experimental Design" in html

    def test_variant_analysis_present(self) -> None:
        html = render_html(_report_data())
        assert "Variant" in html

    def test_task_type_analysis_present(self) -> None:
        html = render_html(_report_data())
        assert "Task Type" in html

    def test_source_breakdown_present(self) -> None:
        html = render_html(_report_data())
        assert "Source" in html

    def test_model_versions_present(self) -> None:
        html = render_html(_report_data())
        assert "claude-sonnet-4.5" in html

    def test_appendix_present(self) -> None:
        html = render_html(_report_data())
        assert "Appendix" in html


# ---------------------------------------------------------------------------
# TestCharts
# ---------------------------------------------------------------------------


class TestCharts:
    """Plotly chart integration."""

    def test_plotly_script_included(self) -> None:
        html = render_html(_report_data())
        assert "plotly" in html.lower()

    def test_chart_data_embedded(self) -> None:
        html = render_html(_report_data())
        assert "Plotly.newPlot" in html


# ---------------------------------------------------------------------------
# TestSelfContained
# ---------------------------------------------------------------------------


class TestSelfContained:
    """Report is self-contained."""

    def test_css_is_inline(self) -> None:
        html = render_html(_report_data())
        assert "<style>" in html

    def test_no_external_css_links(self) -> None:
        html = render_html(_report_data())
        # Should not have external stylesheet links
        assert 'rel="stylesheet"' not in html


# ---------------------------------------------------------------------------
# TestTaguchiSections (Sections 10-14)
# ---------------------------------------------------------------------------


class TestTaguchiSections:
    """Taguchi statistical sections 10-14 when phase_results present."""

    def test_html_renders_main_effects_section(self) -> None:
        """HTML report includes Main Effects Analysis when phase_results present."""
        html = render_html(_taguchi_report_data())
        assert "Main Effects" in html
        assert "structure" in html

    def test_html_renders_main_effects_delta(self) -> None:
        """Main effects table shows delta (max - min) for each factor."""
        html = render_html(_taguchi_report_data())
        # structure: max=12.3, min=8.5, delta=3.8
        assert "3.80" in html or "3.8" in html

    def test_html_renders_anova_table(self) -> None:
        """HTML report includes ANOVA table with p-values."""
        html = render_html(_taguchi_report_data())
        assert "ANOVA" in html
        assert "0.001" in html

    def test_html_renders_significance_markers(self) -> None:
        """Significant factors (p < 0.05) are marked in HTML."""
        html = render_html(_taguchi_report_data())
        assert "***" in html  # p=0.001 < 0.001

    def test_html_renders_non_significant_factor(self) -> None:
        """Non-significant factors have no significance marker."""
        html = render_html(_taguchi_report_data())
        # granularity p=0.24, should show "ns"
        assert "n.s." in html

    def test_html_renders_assumptions_section(self) -> None:
        """HTML report shows statistical assumptions section."""
        html = render_html(_taguchi_report_data())
        assert "Statistical Assumptions" in html or "Assumptions" in html
        assert "larger_is_better" in html or "Larger is Better" in html

    def test_html_renders_post_hoc_section(self) -> None:
        """HTML report shows post-hoc comparisons section."""
        html = render_html(_taguchi_report_data())
        assert "Post-Hoc" in html or "Post Hoc" in html
        assert "structure" in html
        assert "transform" in html

    def test_html_renders_optimal_prediction(self) -> None:
        """HTML report shows the optimal configuration prediction."""
        html = render_html(_taguchi_report_data())
        assert "Optimal" in html or "optimal" in html
        assert "nested" in html
        assert "summary" in html

    def test_html_renders_prediction_interval(self) -> None:
        """HTML report shows the prediction interval."""
        html = render_html(_taguchi_report_data())
        assert "10.0" in html or "10.00" in html
        assert "13.5" in html or "13.50" in html

    def test_html_skips_taguchi_sections_without_phase_results(self) -> None:
        """Non-Taguchi reports do not render Taguchi sections."""
        data = _report_data()  # No phase_results
        html = render_html(data)
        assert "Main Effects" not in html
        assert "ANOVA" not in html
        assert "Post-Hoc" not in html
        assert "Optimal" not in html
