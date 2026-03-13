"""Progress display callbacks for evaluation runs."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_evals.runner import ProgressCallback, TrialResult

logger = logging.getLogger(__name__)


def _make_cost_callback(
    base: str,
    budget: float | None,
) -> ProgressCallback:
    """Create a closure-based callback that accumulates and displays cost."""
    state = {"cost": 0.0}

    def _plain_cost(completed: int, total: int, trial: TrialResult) -> None:
        state["cost"] += trial.cost or 0.0
        cost_str = f"${state['cost']:.2f}"
        logger.info(
            "[%d/%d] %s | %s | score=%.2f | %s",
            completed,
            total,
            trial.task_id,
            trial.variant_name,
            trial.score,
            cost_str,
        )

    def _rich_cost(completed: int, total: int, trial: TrialResult) -> None:
        state["cost"] += trial.cost or 0.0
        pct = (completed / total * 100) if total > 0 else 0
        bar_width = 20
        filled = int(bar_width * completed / total) if total > 0 else 0
        bar = "#" * filled + "-" * (bar_width - filled)
        cost_str = f"${state['cost']:.2f}"
        if budget is not None and budget > 0:
            budget_pct = int(state["cost"] / budget * 100)
            cost_str += f"/${budget:.2f} ({budget_pct}%)"
        logger.info(
            "[%s] %3.0f%% (%d/%d) %s | %s | %.2f | %s",
            bar,
            pct,
            completed,
            total,
            trial.task_id,
            trial.variant_name,
            trial.score,
            cost_str,
        )

    return _plain_cost if base == "plain" else _rich_cost


def make_progress_callback(
    display_mode: str,
    budget: float | None = None,
) -> ProgressCallback | None:
    """Create a progress callback based on display mode.

    Args:
        display_mode: One of "rich", "plain", or "none".
        budget: Optional budget in dollars for percentage display.

    Returns:
        A callback function or None if display_mode is "none".
    """
    if display_mode == "none":
        return None
    return _make_cost_callback(display_mode, budget)
