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


# ---------------------------------------------------------------------------
# Helpers – Taguchi phase_results
# ---------------------------------------------------------------------------


def _taguchi_report_data() -> ReportData:
    """Create ReportData with Taguchi DOE phase_results."""
    return _report_data(
        phase_results={
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
        },
    )


# ---------------------------------------------------------------------------
# TestTaguchiMainEffects
# ---------------------------------------------------------------------------


class TestTaguchiMainEffects:
    """Section 10: Main Effects Response Table."""

    def test_main_effects_heading_present(self) -> None:
        md = render_markdown(_taguchi_report_data())
        assert "Main Effects" in md

    def test_main_effects_shows_delta(self) -> None:
        md = render_markdown(_taguchi_report_data())
        assert "Delta" in md

    def test_main_effects_shows_factor_levels(self) -> None:
        md = render_markdown(_taguchi_report_data())
        assert "flat" in md
        assert "nested" in md
        assert "12.3" in md


# ---------------------------------------------------------------------------
# TestTaguchiAnova
# ---------------------------------------------------------------------------


class TestTaguchiAnova:
    """Section 11: ANOVA Table."""

    def test_anova_heading_present(self) -> None:
        md = render_markdown(_taguchi_report_data())
        assert "ANOVA" in md

    def test_anova_shows_p_value(self) -> None:
        md = render_markdown(_taguchi_report_data())
        assert "0.001" in md

    def test_anova_shows_omega_squared(self) -> None:
        md = render_markdown(_taguchi_report_data())
        # omega squared column header
        assert "\u03c9\u00b2" in md or "omega" in md.lower()

    def test_anova_shows_significance_stars(self) -> None:
        md = render_markdown(_taguchi_report_data())
        # p=0.001 should get *** marker
        assert "***" in md


# ---------------------------------------------------------------------------
# TestTaguchiAssumptions
# ---------------------------------------------------------------------------


class TestTaguchiAssumptions:
    """Section 12: Assumptions & Quality Type."""

    def test_assumptions_heading_present(self) -> None:
        md = render_markdown(_taguchi_report_data())
        assert "Assumptions" in md or "Quality" in md

    def test_quality_type_shown(self) -> None:
        md = render_markdown(_taguchi_report_data())
        assert "larger_is_better" in md or "Larger is Better" in md


# ---------------------------------------------------------------------------
# TestTaguchiSignificantFactors
# ---------------------------------------------------------------------------


class TestTaguchiSignificantFactors:
    """Section 13: Significant Factors."""

    def test_significant_factors_listed(self) -> None:
        md = render_markdown(_taguchi_report_data())
        assert "structure" in md
        assert "transform" in md

    def test_significant_factors_heading(self) -> None:
        md = render_markdown(_taguchi_report_data())
        assert "Significant" in md


# ---------------------------------------------------------------------------
# TestTaguchiOptimalConfig
# ---------------------------------------------------------------------------


class TestTaguchiOptimalConfig:
    """Section 14: Optimal Configuration."""

    def test_optimal_heading_present(self) -> None:
        md = render_markdown(_taguchi_report_data())
        assert "Optimal" in md

    def test_optimal_levels_shown(self) -> None:
        md = render_markdown(_taguchi_report_data())
        assert "nested" in md
        assert "summary" in md


# ---------------------------------------------------------------------------
# TestTaguchiSkippedWithoutPhaseResults
# ---------------------------------------------------------------------------


class TestTaguchiSkippedWithoutPhaseResults:
    """Taguchi sections omitted when phase_results is None."""

    def test_no_anova_without_phase_results(self) -> None:
        md = render_markdown(_report_data())
        assert "ANOVA" not in md

    def test_no_optimal_without_phase_results(self) -> None:
        md = render_markdown(_report_data())
        assert "Optimal Configuration" not in md

    def test_no_main_effects_without_phase_results(self) -> None:
        md = render_markdown(_report_data())
        assert "Main Effects" not in md
