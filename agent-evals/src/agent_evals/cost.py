"""Cost estimation and budget guardrails for evaluation runs.

Provides pre-run cost estimates (token-based), live budget tracking during
execution, and helpers for building per-axis cost reports.

Key functions:
- ``estimate_trial_cost``: estimate a single (task, variant) trial
- ``estimate_run_cost``: estimate all trials in a run
- ``build_axis_report``: aggregate estimates into an axis-level report
- ``format_cost_summary``: human-readable summary for ``--dry-run``

Key class:
- ``CostTracker``: accumulates observed costs and enforces budget caps
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from agent_evals.llm.token_counter import count_message_tokens, estimate_cost

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.tasks.base import EvalTask
    from agent_evals.variants.base import IndexVariant

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

DEFAULT_ESTIMATED_COMPLETION_TOKENS: int = 500


@dataclass
class CostEstimate:
    """Cost estimate for a single (variant, task) trial.

    Attributes:
        variant_name: Name of the index variant.
        task_id: Unique identifier for the evaluation task.
        estimated_prompt_tokens: Number of prompt tokens estimated.
        estimated_completion_tokens: Number of completion tokens estimated.
        estimated_cost: Total estimated cost in dollars.
        model: Model name used for pricing lookup.
    """

    variant_name: str
    task_id: str
    estimated_prompt_tokens: int
    estimated_completion_tokens: int = DEFAULT_ESTIMATED_COMPLETION_TOKENS
    estimated_cost: float = 0.0
    model: str = ""


@dataclass
class AxisCostReport:
    """Aggregated cost report for a single evaluation axis.

    Attributes:
        axis: Evaluation axis number (0-10).
        variant_costs: Mapping of variant name to total cost for that variant.
        total_cost: Sum of all variant costs on this axis.
        task_count: Number of unique tasks evaluated.
        repetitions: Number of repetitions per (variant, task) pair.
        prompt_token_total: Total prompt tokens across all estimates.
        completion_token_total: Total completion tokens across all estimates.
    """

    axis: int
    variant_costs: dict[str, float] = field(default_factory=dict)
    total_cost: float = 0.0
    task_count: int = 0
    repetitions: int = 0
    prompt_token_total: int = 0
    completion_token_total: int = 0


# ---------------------------------------------------------------------------
# Estimation helpers
# ---------------------------------------------------------------------------


def estimate_trial_cost(
    task: EvalTask,
    variant: IndexVariant,
    doc_tree: DocTree,
    model: str,
    repetitions: int = 1,
    estimated_completion_tokens: int = DEFAULT_ESTIMATED_COMPLETION_TOKENS,
) -> CostEstimate:
    """Estimate the cost of running one (task, variant) trial.

    Steps:
    1. Render the variant's index content from *doc_tree*.
    2. Build the task prompt with that index content.
    3. Count prompt tokens via ``count_message_tokens``.
    4. Estimate per-trial cost via ``estimate_cost``.
    5. Multiply by *repetitions*.

    Args:
        task: The evaluation task to estimate.
        variant: The index variant to render.
        doc_tree: Documentation tree passed to the variant renderer.
        model: LLM model name for tokenisation and pricing.
        repetitions: How many times this trial will be repeated.
        estimated_completion_tokens: Expected completion token count per
            trial (default 500).

    Returns:
        A populated ``CostEstimate``.
    """
    index_content: str = variant.render(doc_tree)
    messages: list[dict[str, str]] = task.build_prompt(index_content)
    prompt_tokens: int = count_message_tokens(messages, model=model)

    single_cost: float = estimate_cost(
        prompt_tokens=prompt_tokens,
        completion_tokens=estimated_completion_tokens,
        model=model,
    )
    total_cost: float = single_cost * repetitions
    total_prompt_tokens: int = prompt_tokens * repetitions
    total_completion_tokens: int = estimated_completion_tokens * repetitions

    return CostEstimate(
        variant_name=variant.metadata().name,
        task_id=task.definition.task_id,
        estimated_prompt_tokens=total_prompt_tokens,
        estimated_completion_tokens=total_completion_tokens,
        estimated_cost=total_cost,
        model=model,
    )


def estimate_run_cost(
    tasks: list[EvalTask],
    variants: list[IndexVariant],
    doc_tree: DocTree,
    model: str,
    repetitions: int = 10,
    estimated_completion_tokens: int = DEFAULT_ESTIMATED_COMPLETION_TOKENS,
) -> list[CostEstimate]:
    """Estimate costs for every (task, variant) combination in a run.

    Args:
        tasks: All evaluation tasks to run.
        variants: All index variants under test.
        doc_tree: Documentation tree for rendering.
        model: LLM model name.
        repetitions: Repetitions per trial.
        estimated_completion_tokens: Expected completion tokens per trial.

    Returns:
        A list of ``CostEstimate`` instances, one per (task, variant) pair.
    """
    estimates: list[CostEstimate] = []
    for task in tasks:
        for variant in variants:
            est = estimate_trial_cost(
                task=task,
                variant=variant,
                doc_tree=doc_tree,
                model=model,
                repetitions=repetitions,
                estimated_completion_tokens=estimated_completion_tokens,
            )
            estimates.append(est)
    return estimates


# ---------------------------------------------------------------------------
# Axis report
# ---------------------------------------------------------------------------


def build_axis_report(
    estimates: list[CostEstimate],
    axis: int,
    repetitions: int,
) -> AxisCostReport:
    """Build an aggregated cost report for a given axis.

    Filters *estimates* to only those whose ``variant_name`` matches a
    variant on the given axis (callers are expected to pass pre-filtered
    estimates or all estimates -- the function aggregates everything it
    receives).

    Args:
        estimates: Cost estimates to aggregate.
        axis: The axis number this report covers.
        repetitions: Number of repetitions used (stored in the report).

    Returns:
        An ``AxisCostReport`` with totals computed.
    """
    variant_costs: dict[str, float] = {}
    prompt_total = 0
    completion_total = 0
    task_ids: set[str] = set()

    for est in estimates:
        variant_costs[est.variant_name] = (
            variant_costs.get(est.variant_name, 0.0) + est.estimated_cost
        )
        prompt_total += est.estimated_prompt_tokens
        completion_total += est.estimated_completion_tokens
        task_ids.add(est.task_id)

    total_cost = sum(variant_costs.values())

    return AxisCostReport(
        axis=axis,
        variant_costs=variant_costs,
        total_cost=total_cost,
        task_count=len(task_ids),
        repetitions=repetitions,
        prompt_token_total=prompt_total,
        completion_token_total=completion_total,
    )


# ---------------------------------------------------------------------------
# Budget tracker
# ---------------------------------------------------------------------------


class CostTracker:
    """Live cost tracker with optional budget guardrails.

    Records actual trial costs during execution and can project total run
    cost based on the observed average.  When a *budget* is set, the tracker
    signals a pause if the projected cost exceeds twice the budget.

    Args:
        budget: Maximum spend in dollars.  ``None`` disables budget checks.
    """

    def __init__(self, budget: float | None = None) -> None:
        self.budget: float | None = budget
        self.accumulated_cost: float = 0.0
        self.trial_costs: list[float] = []

    def record(self, cost: float) -> None:
        """Record the cost of a completed trial.

        Args:
            cost: The cost (in dollars) of the trial just completed.
        """
        self.trial_costs.append(cost)
        self.accumulated_cost += cost

    @property
    def total_cost(self) -> float:
        """Total cost observed so far."""
        return self.accumulated_cost

    @property
    def mean_trial_cost(self) -> float:
        """Mean cost per trial, or 0.0 if no trials recorded."""
        if not self.trial_costs:
            return 0.0
        return self.accumulated_cost / len(self.trial_costs)

    def projected_cost(self, total_planned_trials: int) -> float:
        """Project total run cost based on the observed mean.

        If no trials have been recorded yet, the projection is 0.0.

        Args:
            total_planned_trials: Total number of trials in the full run.

        Returns:
            Projected total cost in dollars.
        """
        if not self.trial_costs:
            return 0.0
        return self.mean_trial_cost * total_planned_trials

    def check_budget(self, total_planned_trials: int) -> bool:
        """Check whether the projected cost exceeds twice the budget.

        Args:
            total_planned_trials: Total number of trials in the full run.

        Returns:
            ``True`` if projected cost exceeds 2x budget, ``False``
            otherwise.  Always returns ``False`` when no budget is set.
        """
        if self.budget is None:
            return False
        return self.projected_cost(total_planned_trials) > (self.budget * 2)

    def should_pause(self, total_planned_trials: int) -> bool:
        """Determine whether the runner should pause for user confirmation.

        Equivalent to :meth:`check_budget` -- returns ``True`` when the
        projected cost exceeds 2x the budget.

        Args:
            total_planned_trials: Total trials in the run.

        Returns:
            ``True`` if the runner should pause.
        """
        return self.check_budget(total_planned_trials)


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_cost_summary(
    estimates: list[CostEstimate],
    model: str,
) -> str:
    """Format a human-readable cost summary suitable for ``--dry-run`` output.

    Groups estimates by variant, showing per-variant totals and a grand
    total.

    Args:
        estimates: All cost estimates for the run.
        model: LLM model name (shown in the header).

    Returns:
        A multi-line string summary.
    """
    if not estimates:
        return f"Cost estimate for model '{model}': no trials planned."

    variant_totals: dict[str, float] = {}
    variant_prompt_tokens: dict[str, int] = {}
    variant_completion_tokens: dict[str, int] = {}
    total_cost = 0.0
    total_prompt = 0
    total_completion = 0

    for est in estimates:
        name = est.variant_name
        variant_totals[name] = variant_totals.get(name, 0.0) + est.estimated_cost
        variant_prompt_tokens[name] = (
            variant_prompt_tokens.get(name, 0) + est.estimated_prompt_tokens
        )
        variant_completion_tokens[name] = (
            variant_completion_tokens.get(name, 0) + est.estimated_completion_tokens
        )
        total_cost += est.estimated_cost
        total_prompt += est.estimated_prompt_tokens
        total_completion += est.estimated_completion_tokens

    lines: list[str] = [
        f"Cost estimate for model '{model}'",
        f"  Total trials: {len(estimates)}",
        f"  Total estimated cost: ${total_cost:.4f}",
        f"  Total prompt tokens: {total_prompt:,}",
        f"  Total completion tokens: {total_completion:,}",
        "",
        "  Per-variant breakdown:",
    ]

    for name in sorted(variant_totals):
        cost = variant_totals[name]
        prompt = variant_prompt_tokens[name]
        completion = variant_completion_tokens[name]
        lines.append(
            f"    {name}: ${cost:.4f} "
            f"(prompt: {prompt:,}, completion: {completion:,})"
        )

    return "\n".join(lines)
