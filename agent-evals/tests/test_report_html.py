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
