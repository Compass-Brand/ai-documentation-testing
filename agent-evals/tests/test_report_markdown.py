"""Tests for Markdown Report Renderer."""

from __future__ import annotations

from agent_evals.reports.aggregator import ReportData, VariantSummary
from agent_evals.reports.md_renderer import render_markdown
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
            "gold_standard": VariantSummary(
                count=80, mean_score=0.80, total_cost=1.20
            ),
            "repliqa": VariantSummary(count=20, mean_score=0.76, total_cost=0.30),
        },
        "model_versions": {"claude-sonnet-4.5": "claude-3-5-sonnet-20241022"},
    }
    defaults.update(overrides)
    return ReportData(**defaults)


# ---------------------------------------------------------------------------
# TestMarkdownStructure
# ---------------------------------------------------------------------------


class TestMarkdownStructure:
    """Valid markdown output structure."""

    def test_starts_with_heading(self) -> None:
        md = render_markdown(_report_data())
        assert md.strip().startswith("# ")

    def test_is_nonempty(self) -> None:
        md = render_markdown(_report_data())
        assert len(md) > 100

    def test_returns_string(self) -> None:
        md = render_markdown(_report_data())
        assert isinstance(md, str)


# ---------------------------------------------------------------------------
# TestSections
# ---------------------------------------------------------------------------


class TestSections:
    """All report sections present."""

    def test_executive_summary_present(self) -> None:
        md = render_markdown(_report_data())
        assert "Executive Summary" in md

    def test_experimental_design_present(self) -> None:
        md = render_markdown(_report_data())
        assert "Experimental Design" in md

    def test_variant_analysis_present(self) -> None:
        md = render_markdown(_report_data())
        assert "Variant" in md

    def test_task_type_analysis_present(self) -> None:
        md = render_markdown(_report_data())
        assert "Task Type" in md

    def test_source_breakdown_present(self) -> None:
        md = render_markdown(_report_data())
        assert "Source" in md

    def test_model_versions_present(self) -> None:
        md = render_markdown(_report_data())
        assert "claude-sonnet-4.5" in md

    def test_appendix_present(self) -> None:
        md = render_markdown(_report_data())
        assert "Appendix" in md


# ---------------------------------------------------------------------------
# TestDataContent
# ---------------------------------------------------------------------------


class TestDataContent:
    """Report contains correct data values."""

    def test_total_trials_shown(self) -> None:
        md = render_markdown(_report_data())
        assert "100" in md

    def test_total_cost_shown(self) -> None:
        md = render_markdown(_report_data())
        assert "1.50" in md

    def test_variant_names_shown(self) -> None:
        md = render_markdown(_report_data())
        assert "flat" in md
        assert "3tier" in md

    def test_variant_scores_shown(self) -> None:
        md = render_markdown(_report_data())
        assert "0.82" in md

    def test_task_type_names_shown(self) -> None:
        md = render_markdown(_report_data())
        assert "retrieval" in md
        assert "code_gen" in md

    def test_source_names_shown(self) -> None:
        md = render_markdown(_report_data())
        assert "gold_standard" in md
        assert "repliqa" in md

    def test_model_version_mapping_shown(self) -> None:
        md = render_markdown(_report_data())
        assert "claude-3-5-sonnet-20241022" in md

    def test_config_values_in_appendix(self) -> None:
        md = render_markdown(_report_data())
        assert "repetitions" in md.lower()


# ---------------------------------------------------------------------------
# TestMarkdownTables
# ---------------------------------------------------------------------------


class TestMarkdownTables:
    """Markdown tables are well-formed."""

    def test_contains_table_separators(self) -> None:
        md = render_markdown(_report_data())
        # Markdown tables use |---| separator rows
        assert "---" in md

    def test_contains_pipe_characters(self) -> None:
        md = render_markdown(_report_data())
        assert "|" in md
