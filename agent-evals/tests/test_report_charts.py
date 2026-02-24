"""Tests for the shared chart library."""

from __future__ import annotations

import pytest
from agent_evals.reports.charts import (
    generate_box_plots,
    generate_burn_chart,
    generate_confirmation_chart,
    generate_interaction_plot,
    generate_main_effects_plotly,
    generate_radar_chart,
    generate_sn_response_table,
)


# ---------------------------------------------------------------------------
# TestMainEffects
# ---------------------------------------------------------------------------


class TestMainEffects:
    """Main effects bar charts."""

    def test_returns_list_of_traces(self) -> None:
        data = {
            "axis_1": {"flat": 0.8, "3tier": 0.85},
            "axis_2": {"summary": 0.7, "full": 0.75},
        }
        traces = generate_main_effects_plotly(data)
        assert isinstance(traces, list)
        assert len(traces) == 2

    def test_trace_has_plotly_fields(self) -> None:
        data = {"axis_1": {"flat": 0.8, "3tier": 0.85}}
        traces = generate_main_effects_plotly(data)
        t = traces[0]
        assert "x" in t
        assert "y" in t
        assert t["type"] == "bar"

    def test_trace_values_correct(self) -> None:
        data = {"axis_1": {"flat": 0.8, "3tier": 0.85}}
        traces = generate_main_effects_plotly(data)
        assert traces[0]["x"] == ["flat", "3tier"]
        assert traces[0]["y"] == [0.8, 0.85]


# ---------------------------------------------------------------------------
# TestInteractionPlot
# ---------------------------------------------------------------------------


class TestInteractionPlot:
    """Interaction line plots."""

    def test_returns_traces(self) -> None:
        data = {
            "level_a": {"level_x": 0.8, "level_y": 0.7},
            "level_b": {"level_x": 0.75, "level_y": 0.85},
        }
        traces = generate_interaction_plot(data)
        assert isinstance(traces, list)
        assert len(traces) == 2

    def test_trace_is_line_type(self) -> None:
        data = {
            "level_a": {"level_x": 0.8, "level_y": 0.7},
        }
        traces = generate_interaction_plot(data)
        assert traces[0]["type"] == "scatter"
        assert traces[0]["mode"] == "lines+markers"


# ---------------------------------------------------------------------------
# TestRadarChart
# ---------------------------------------------------------------------------


class TestRadarChart:
    """Model comparison radar chart."""

    def test_returns_traces_per_model(self) -> None:
        data = {
            "claude": {"retrieval": 0.9, "code_gen": 0.8},
            "gpt": {"retrieval": 0.85, "code_gen": 0.75},
        }
        traces = generate_radar_chart(data)
        assert len(traces) == 2

    def test_trace_type_is_scatterpolar(self) -> None:
        data = {"claude": {"retrieval": 0.9, "code_gen": 0.8}}
        traces = generate_radar_chart(data)
        assert traces[0]["type"] == "scatterpolar"


# ---------------------------------------------------------------------------
# TestBoxPlots
# ---------------------------------------------------------------------------


class TestBoxPlots:
    """Score distribution box plots."""

    def test_returns_trace_per_variant(self) -> None:
        data = {
            "flat": [0.7, 0.8, 0.85, 0.9],
            "3tier": [0.75, 0.8, 0.82, 0.88],
        }
        traces = generate_box_plots(data)
        assert len(traces) == 2

    def test_trace_type_is_box(self) -> None:
        data = {"flat": [0.7, 0.8, 0.85]}
        traces = generate_box_plots(data)
        assert traces[0]["type"] == "box"


# ---------------------------------------------------------------------------
# TestBurnChart
# ---------------------------------------------------------------------------


class TestBurnChart:
    """Cost burn chart."""

    def test_returns_traces(self) -> None:
        data = {"costs": [0.01, 0.03, 0.06, 0.10], "budget": 0.50}
        traces = generate_burn_chart(data)
        assert isinstance(traces, list)
        assert len(traces) >= 1

    def test_includes_budget_line(self) -> None:
        data = {"costs": [0.01, 0.03], "budget": 0.50}
        traces = generate_burn_chart(data)
        budget_traces = [t for t in traces if t.get("name") == "Budget"]
        assert len(budget_traces) == 1


# ---------------------------------------------------------------------------
# TestSNResponseTable
# ---------------------------------------------------------------------------


class TestSNResponseTable:
    """S/N response table."""

    def test_returns_dict_per_factor(self) -> None:
        data = {
            "axis_1": {"flat": 5.2, "3tier": 4.8},
            "axis_2": {"summary": 6.0, "full": 5.5},
        }
        table = generate_sn_response_table(data)
        assert "axis_1" in table
        assert "axis_2" in table

    def test_includes_delta(self) -> None:
        data = {"axis_1": {"flat": 5.2, "3tier": 4.8}}
        table = generate_sn_response_table(data)
        assert "delta" in table["axis_1"]
        assert table["axis_1"]["delta"] == pytest.approx(0.4, abs=0.01)


# ---------------------------------------------------------------------------
# TestConfirmationChart
# ---------------------------------------------------------------------------


class TestConfirmationChart:
    """Confirmation run predicted vs actual chart."""

    def test_returns_traces(self) -> None:
        data = {"predicted": 5.2, "observed": 5.0, "ci_half_width": 0.5}
        traces = generate_confirmation_chart(data)
        assert isinstance(traces, list)
        assert len(traces) >= 2

    def test_includes_predicted_and_observed(self) -> None:
        data = {"predicted": 5.2, "observed": 5.0, "ci_half_width": 0.5}
        traces = generate_confirmation_chart(data)
        names = [t.get("name", "") for t in traces]
        assert "Predicted" in names
        assert "Observed" in names
