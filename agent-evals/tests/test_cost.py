"""Tests for cost estimation and budget guardrails."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from agent_evals.cost import (
    AxisCostReport,
    CostEstimate,
    CostTracker,
    build_axis_report,
    estimate_run_cost,
    estimate_trial_cost,
    format_cost_summary,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task(task_id: str = "retrieval_001") -> MagicMock:
    """Create a mock EvalTask."""
    task = MagicMock()
    task.definition.task_id = task_id
    task.build_prompt.return_value = [
        {"role": "system", "content": "You are a helpful assistant.\n\nIndex content."},
        {"role": "user", "content": "What is the auth flow?"},
    ]
    return task


def _make_variant(name: str = "baseline", axis: int = 0) -> MagicMock:
    """Create a mock IndexVariant."""
    variant = MagicMock()
    variant.metadata.return_value.name = name
    variant.metadata.return_value.axis = axis
    variant.render.return_value = "# Rendered index content"
    return variant


def _make_doc_tree() -> MagicMock:
    """Create a mock DocTree."""
    return MagicMock()


# ---------------------------------------------------------------------------
# CostEstimate dataclass
# ---------------------------------------------------------------------------


class TestCostEstimate:
    """Tests for the CostEstimate dataclass."""

    def test_defaults(self) -> None:
        """CostEstimate has sensible defaults for optional fields."""
        est = CostEstimate(
            variant_name="v1",
            task_id="retrieval_001",
            estimated_prompt_tokens=100,
        )
        assert est.variant_name == "v1"
        assert est.task_id == "retrieval_001"
        assert est.estimated_prompt_tokens == 100
        assert est.estimated_completion_tokens == 500  # default
        assert est.estimated_cost == 0.0
        assert est.model == ""

    def test_explicit_values(self) -> None:
        """CostEstimate stores explicitly provided values."""
        est = CostEstimate(
            variant_name="v2",
            task_id="code_generation_001",
            estimated_prompt_tokens=2000,
            estimated_completion_tokens=800,
            estimated_cost=0.15,
            model="gpt-4",
        )
        assert est.estimated_completion_tokens == 800
        assert est.estimated_cost == 0.15
        assert est.model == "gpt-4"


# ---------------------------------------------------------------------------
# AxisCostReport dataclass
# ---------------------------------------------------------------------------


class TestAxisCostReport:
    """Tests for the AxisCostReport dataclass."""

    def test_defaults(self) -> None:
        """AxisCostReport has empty/zero defaults."""
        report = AxisCostReport(axis=1)
        assert report.axis == 1
        assert report.variant_costs == {}
        assert report.total_cost == 0.0
        assert report.task_count == 0
        assert report.repetitions == 0
        assert report.prompt_token_total == 0
        assert report.completion_token_total == 0


# ---------------------------------------------------------------------------
# estimate_trial_cost
# ---------------------------------------------------------------------------


class TestEstimateTrialCost:
    """Tests for estimate_trial_cost function."""

    @patch("agent_evals.cost.estimate_cost", return_value=0.05)
    @patch("agent_evals.cost.count_message_tokens", return_value=1000)
    def test_basic_estimate(
        self, mock_count: MagicMock, mock_cost: MagicMock
    ) -> None:
        """Estimate builds prompt, counts tokens, and calculates cost."""
        task = _make_task()
        variant = _make_variant(name="flat_index")
        doc_tree = _make_doc_tree()

        result = estimate_trial_cost(
            task=task,
            variant=variant,
            doc_tree=doc_tree,
            model="gpt-4",
            repetitions=1,
            estimated_completion_tokens=500,
        )

        variant.render.assert_called_once_with(doc_tree)
        task.build_prompt.assert_called_once_with("# Rendered index content")
        mock_count.assert_called_once()
        mock_cost.assert_called_once_with(
            prompt_tokens=1000, completion_tokens=500, model="gpt-4"
        )

        assert result.variant_name == "flat_index"
        assert result.task_id == "retrieval_001"
        assert result.estimated_prompt_tokens == 1000
        assert result.estimated_completion_tokens == 500
        assert result.estimated_cost == pytest.approx(0.05)
        assert result.model == "gpt-4"

    @patch("agent_evals.cost.estimate_cost", return_value=0.02)
    @patch("agent_evals.cost.count_message_tokens", return_value=800)
    def test_repetitions_multiply_cost(
        self, mock_count: MagicMock, mock_cost: MagicMock
    ) -> None:
        """Repetitions multiply the single-trial cost and token counts."""
        task = _make_task()
        variant = _make_variant(name="tiered_index")
        doc_tree = _make_doc_tree()

        result = estimate_trial_cost(
            task=task,
            variant=variant,
            doc_tree=doc_tree,
            model="gpt-4",
            repetitions=10,
            estimated_completion_tokens=300,
        )

        assert result.estimated_cost == pytest.approx(0.02 * 10)
        assert result.estimated_prompt_tokens == 800 * 10
        assert result.estimated_completion_tokens == 300 * 10

    @patch("agent_evals.cost.estimate_cost", return_value=0.0)
    @patch("agent_evals.cost.count_message_tokens", return_value=500)
    def test_zero_cost_model(
        self, mock_count: MagicMock, mock_cost: MagicMock
    ) -> None:
        """When estimate_cost returns 0.0 (unknown model), result cost is 0."""
        task = _make_task()
        variant = _make_variant()
        doc_tree = _make_doc_tree()

        result = estimate_trial_cost(
            task=task,
            variant=variant,
            doc_tree=doc_tree,
            model="unknown-model",
        )
        assert result.estimated_cost == 0.0


# ---------------------------------------------------------------------------
# estimate_run_cost
# ---------------------------------------------------------------------------


class TestEstimateRunCost:
    """Tests for estimate_run_cost function."""

    @patch("agent_evals.cost.estimate_cost", return_value=0.01)
    @patch("agent_evals.cost.count_message_tokens", return_value=400)
    def test_multiple_tasks_and_variants(
        self, mock_count: MagicMock, mock_cost: MagicMock
    ) -> None:
        """Returns one CostEstimate per (task, variant) pair."""
        tasks = [_make_task("retrieval_001"), _make_task("retrieval_002")]
        variants = [_make_variant("v_a"), _make_variant("v_b"), _make_variant("v_c")]
        doc_tree = _make_doc_tree()

        results = estimate_run_cost(
            tasks=tasks,
            variants=variants,
            doc_tree=doc_tree,
            model="gpt-4",
            repetitions=5,
        )

        assert len(results) == 6  # 2 tasks * 3 variants
        # Each estimate should be repetitions * single cost
        for est in results:
            assert est.estimated_cost == pytest.approx(0.01 * 5)

    @patch("agent_evals.cost.estimate_cost", return_value=0.01)
    @patch("agent_evals.cost.count_message_tokens", return_value=400)
    def test_empty_tasks(
        self, mock_count: MagicMock, mock_cost: MagicMock
    ) -> None:
        """Empty task list returns no estimates."""
        results = estimate_run_cost(
            tasks=[],
            variants=[_make_variant()],
            doc_tree=_make_doc_tree(),
            model="gpt-4",
        )
        assert results == []

    @patch("agent_evals.cost.estimate_cost", return_value=0.01)
    @patch("agent_evals.cost.count_message_tokens", return_value=400)
    def test_empty_variants(
        self, mock_count: MagicMock, mock_cost: MagicMock
    ) -> None:
        """Empty variant list returns no estimates."""
        results = estimate_run_cost(
            tasks=[_make_task()],
            variants=[],
            doc_tree=_make_doc_tree(),
            model="gpt-4",
        )
        assert results == []


# ---------------------------------------------------------------------------
# build_axis_report
# ---------------------------------------------------------------------------


class TestBuildAxisReport:
    """Tests for build_axis_report function."""

    def test_aggregates_by_variant(self) -> None:
        """Costs are summed per variant across tasks."""
        estimates = [
            CostEstimate(
                variant_name="v1",
                task_id="retrieval_001",
                estimated_prompt_tokens=100,
                estimated_completion_tokens=50,
                estimated_cost=0.01,
                model="gpt-4",
            ),
            CostEstimate(
                variant_name="v1",
                task_id="retrieval_002",
                estimated_prompt_tokens=200,
                estimated_completion_tokens=50,
                estimated_cost=0.02,
                model="gpt-4",
            ),
            CostEstimate(
                variant_name="v2",
                task_id="retrieval_001",
                estimated_prompt_tokens=150,
                estimated_completion_tokens=50,
                estimated_cost=0.015,
                model="gpt-4",
            ),
        ]

        report = build_axis_report(estimates, axis=1, repetitions=10)

        assert report.axis == 1
        assert report.variant_costs["v1"] == pytest.approx(0.03)
        assert report.variant_costs["v2"] == pytest.approx(0.015)
        assert report.total_cost == pytest.approx(0.045)
        assert report.task_count == 2  # retrieval_001 and retrieval_002
        assert report.repetitions == 10
        assert report.prompt_token_total == 450
        assert report.completion_token_total == 150

    def test_empty_estimates(self) -> None:
        """Empty estimate list produces zeroed report."""
        report = build_axis_report([], axis=3, repetitions=5)

        assert report.axis == 3
        assert report.variant_costs == {}
        assert report.total_cost == 0.0
        assert report.task_count == 0
        assert report.repetitions == 5
        assert report.prompt_token_total == 0
        assert report.completion_token_total == 0

    def test_single_estimate(self) -> None:
        """Single estimate populates report correctly."""
        est = CostEstimate(
            variant_name="only_variant",
            task_id="code_generation_001",
            estimated_prompt_tokens=500,
            estimated_completion_tokens=200,
            estimated_cost=0.05,
            model="gpt-4",
        )

        report = build_axis_report([est], axis=2, repetitions=1)

        assert report.variant_costs == {"only_variant": 0.05}
        assert report.total_cost == pytest.approx(0.05)
        assert report.task_count == 1
        assert report.prompt_token_total == 500
        assert report.completion_token_total == 200


# ---------------------------------------------------------------------------
# CostTracker
# ---------------------------------------------------------------------------


class TestCostTracker:
    """Tests for the CostTracker class."""

    def test_initial_state(self) -> None:
        """Tracker starts with zero cost and empty list."""
        tracker = CostTracker(budget=10.0)
        assert tracker.total_cost == 0.0
        assert tracker.accumulated_cost == 0.0
        assert tracker.trial_costs == []
        assert tracker.budget == 10.0

    def test_record_accumulates(self) -> None:
        """Recording trials accumulates cost."""
        tracker = CostTracker()
        tracker.record(0.01)
        tracker.record(0.02)
        tracker.record(0.03)

        assert tracker.total_cost == pytest.approx(0.06)
        assert len(tracker.trial_costs) == 3
        assert tracker.trial_costs == [0.01, 0.02, 0.03]

    def test_total_cost_property(self) -> None:
        """total_cost reflects accumulated_cost."""
        tracker = CostTracker()
        assert tracker.total_cost == 0.0
        tracker.record(1.5)
        assert tracker.total_cost == pytest.approx(1.5)

    def test_mean_trial_cost(self) -> None:
        """mean_trial_cost is the average of recorded trial costs."""
        tracker = CostTracker()
        tracker.record(0.10)
        tracker.record(0.20)
        tracker.record(0.30)
        assert tracker.mean_trial_cost == pytest.approx(0.20)

    def test_mean_trial_cost_no_trials(self) -> None:
        """mean_trial_cost is 0.0 when no trials recorded."""
        tracker = CostTracker()
        assert tracker.mean_trial_cost == 0.0

    def test_projected_cost_with_partial_completion(self) -> None:
        """Projected cost extrapolates from observed mean."""
        tracker = CostTracker()
        # Record 3 trials at $0.10 each
        tracker.record(0.10)
        tracker.record(0.10)
        tracker.record(0.10)

        # Total planned is 100 trials, mean is $0.10
        projected = tracker.projected_cost(total_planned_trials=100)
        assert projected == pytest.approx(10.0)

    def test_projected_cost_no_trials(self) -> None:
        """Projected cost is 0.0 when no trials have been recorded."""
        tracker = CostTracker()
        assert tracker.projected_cost(total_planned_trials=100) == 0.0

    def test_check_budget_under_2x(self) -> None:
        """check_budget returns False when projected cost is under 2x budget."""
        tracker = CostTracker(budget=10.0)
        # Mean 0.10, 100 trials => projected $10 => not > $20 (2x budget)
        tracker.record(0.10)
        assert tracker.check_budget(total_planned_trials=100) is False

    def test_check_budget_over_2x(self) -> None:
        """check_budget returns True when projected cost exceeds 2x budget."""
        tracker = CostTracker(budget=5.0)
        # Mean 0.50, 100 trials => projected $50 => > $10 (2x budget)
        tracker.record(0.50)
        assert tracker.check_budget(total_planned_trials=100) is True

    def test_check_budget_exactly_2x(self) -> None:
        """check_budget returns False when projected equals exactly 2x budget."""
        tracker = CostTracker(budget=5.0)
        # Mean 0.10, 100 trials => projected $10 => not > $10 (exactly 2x)
        tracker.record(0.10)
        assert tracker.check_budget(total_planned_trials=100) is False

    def test_check_budget_no_budget_set(self) -> None:
        """check_budget always returns False when no budget is set."""
        tracker = CostTracker(budget=None)
        tracker.record(100.0)
        assert tracker.check_budget(total_planned_trials=1000) is False

    def test_should_pause_delegates_to_check_budget(self) -> None:
        """should_pause returns the same result as check_budget."""
        tracker = CostTracker(budget=5.0)
        tracker.record(0.50)
        # Projected: 0.50 * 100 = 50.0, budget * 2 = 10.0
        assert tracker.should_pause(total_planned_trials=100) is True

    def test_should_pause_no_budget(self) -> None:
        """should_pause returns False when no budget is set."""
        tracker = CostTracker()
        tracker.record(999.0)
        assert tracker.should_pause(total_planned_trials=1000) is False

    def test_record_zero_cost(self) -> None:
        """Recording zero-cost trials works correctly."""
        tracker = CostTracker(budget=1.0)
        tracker.record(0.0)
        tracker.record(0.0)
        assert tracker.total_cost == 0.0
        assert tracker.mean_trial_cost == 0.0
        assert tracker.projected_cost(total_planned_trials=50) == 0.0
        assert tracker.check_budget(total_planned_trials=50) is False


# ---------------------------------------------------------------------------
# format_cost_summary
# ---------------------------------------------------------------------------


class TestFormatCostSummary:
    """Tests for format_cost_summary function."""

    def test_basic_output(self) -> None:
        """Summary includes model, trial count, and per-variant breakdown."""
        estimates = [
            CostEstimate(
                variant_name="alpha",
                task_id="retrieval_001",
                estimated_prompt_tokens=1000,
                estimated_completion_tokens=500,
                estimated_cost=0.03,
                model="gpt-4",
            ),
            CostEstimate(
                variant_name="beta",
                task_id="retrieval_001",
                estimated_prompt_tokens=1200,
                estimated_completion_tokens=500,
                estimated_cost=0.04,
                model="gpt-4",
            ),
        ]

        output = format_cost_summary(estimates, model="gpt-4")

        assert "gpt-4" in output
        assert "Total trials: 2" in output
        assert "$0.0700" in output  # total cost
        assert "alpha" in output
        assert "beta" in output

    def test_empty_estimates(self) -> None:
        """Empty estimates produces informative message."""
        output = format_cost_summary([], model="gpt-4")
        assert "no trials planned" in output
        assert "gpt-4" in output

    def test_per_variant_tokens_shown(self) -> None:
        """Summary shows prompt and completion tokens per variant."""
        estimates = [
            CostEstimate(
                variant_name="gamma",
                task_id="code_generation_001",
                estimated_prompt_tokens=2000,
                estimated_completion_tokens=800,
                estimated_cost=0.10,
                model="gpt-4",
            ),
        ]

        output = format_cost_summary(estimates, model="gpt-4")

        assert "prompt: 2,000" in output
        assert "completion: 800" in output

    def test_multiple_tasks_same_variant_aggregated(self) -> None:
        """Multiple tasks for the same variant are aggregated in the summary."""
        estimates = [
            CostEstimate(
                variant_name="v1",
                task_id="retrieval_001",
                estimated_prompt_tokens=100,
                estimated_completion_tokens=50,
                estimated_cost=0.01,
                model="gpt-4",
            ),
            CostEstimate(
                variant_name="v1",
                task_id="retrieval_002",
                estimated_prompt_tokens=200,
                estimated_completion_tokens=50,
                estimated_cost=0.02,
                model="gpt-4",
            ),
        ]

        output = format_cost_summary(estimates, model="gpt-4")

        assert "Total trials: 2" in output
        assert "$0.0300" in output  # total = 0.01 + 0.02
        # v1 total prompt tokens: 300
        assert "prompt: 300" in output

    def test_variants_sorted_alphabetically(self) -> None:
        """Variant names in the breakdown are sorted alphabetically."""
        estimates = [
            CostEstimate(
                variant_name="zebra",
                task_id="retrieval_001",
                estimated_prompt_tokens=100,
                estimated_completion_tokens=50,
                estimated_cost=0.01,
                model="gpt-4",
            ),
            CostEstimate(
                variant_name="apple",
                task_id="retrieval_001",
                estimated_prompt_tokens=100,
                estimated_completion_tokens=50,
                estimated_cost=0.01,
                model="gpt-4",
            ),
        ]

        output = format_cost_summary(estimates, model="gpt-4")
        lines = output.split("\n")

        # Find the variant breakdown lines
        variant_lines = [line.strip() for line in lines if line.strip().startswith(("apple", "zebra"))]
        assert len(variant_lines) == 2
        assert variant_lines[0].startswith("apple")
        assert variant_lines[1].startswith("zebra")
