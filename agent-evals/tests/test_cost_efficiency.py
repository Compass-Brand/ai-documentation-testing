"""Tests for cost-efficiency reporting."""

from __future__ import annotations

import pytest

from agent_evals.reports.cost_efficiency import (
    CostEfficiencyRow,
    compute_pareto_frontier,
    render_cost_efficiency_table,
)


class TestComputeParetoFrontier:
    def test_identifies_pareto_optimal_points(self):
        rows = [
            CostEfficiencyRow("A", accuracy=0.82, cost=0.004, stability=0.03),
            CostEfficiencyRow("B", accuracy=0.84, cost=0.009, stability=0.05),
            CostEfficiencyRow("C", accuracy=0.71, cost=0.003, stability=0.02),
            CostEfficiencyRow("D", accuracy=0.60, cost=0.010, stability=0.10),
        ]
        frontier = compute_pareto_frontier(rows)
        names = {r.variant for r in frontier}
        assert "D" not in names
        assert "A" in names
        assert "C" in names

    def test_single_row_is_pareto_optimal(self):
        rows = [CostEfficiencyRow("only", 0.8, 0.005, 0.02)]
        frontier = compute_pareto_frontier(rows)
        assert len(frontier) == 1

    def test_empty_returns_empty(self):
        assert compute_pareto_frontier([]) == []


class TestRenderCostEfficiencyTable:
    def test_renders_readable_table(self):
        rows = [
            CostEfficiencyRow("2-tier-md", 82.3, 0.0041, 3.0, pareto=True),
            CostEfficiencyRow("flat-md", 71.2, 0.0028, 2.0, pareto=False),
        ]
        text = render_cost_efficiency_table(rows)
        assert "2-tier-md" in text
        assert "Pareto" in text or "optimal" in text.lower()
        assert "flat-md" in text


class TestParetoPerStrategy:
    def test_pareto_per_strategy(self):
        """Pareto frontier can be computed per strategy."""
        rows = [
            CostEfficiencyRow("A", accuracy=82.0, cost=0.004, stability=3.0, strategy="full_context"),
            CostEfficiencyRow("B", accuracy=84.0, cost=0.009, stability=5.0, strategy="full_context"),
            CostEfficiencyRow("C", accuracy=71.0, cost=0.003, stability=2.0, strategy="tool_based"),
            CostEfficiencyRow("D", accuracy=75.0, cost=0.008, stability=4.0, strategy="tool_based"),
        ]

        frontier_fc = compute_pareto_frontier(rows, strategy="full_context")
        names_fc = {r.variant for r in frontier_fc}
        assert "A" in names_fc
        assert "B" in names_fc
        assert "C" not in names_fc
        assert "D" not in names_fc

        frontier_tb = compute_pareto_frontier(rows, strategy="tool_based")
        names_tb = {r.variant for r in frontier_tb}
        assert "C" in names_tb
        assert "D" in names_tb

    def test_render_grouped_by_strategy(self):
        """Render produces separate tables when group_by_strategy=True."""
        rows = [
            CostEfficiencyRow("A", accuracy=82.0, cost=0.004, stability=3.0, strategy="full_context"),
            CostEfficiencyRow("C", accuracy=71.0, cost=0.003, stability=2.0, strategy="tool_based"),
        ]
        text = render_cost_efficiency_table(rows, group_by_strategy=True)
        assert "full_context" in text
        assert "tool_based" in text
