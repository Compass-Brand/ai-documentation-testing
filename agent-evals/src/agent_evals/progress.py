"""Progress display callbacks for evaluation runs."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_evals.runner import ProgressCallback, TrialResult

logger = logging.getLogger(__name__)


def _plain_callback(completed: int, total: int, trial: TrialResult) -> None:
    logger.info(
        "[%d/%d] %s | %s | score=%.2f",
        completed,
        total,
        trial.task_id,
        trial.variant_name,
        trial.score,
    )


def _rich_callback(completed: int, total: int, trial: TrialResult) -> None:
    pct = (completed / total * 100) if total > 0 else 0
    bar_width = 20
    filled = int(bar_width * completed / total) if total > 0 else 0
    bar = "#" * filled + "-" * (bar_width - filled)
    logger.info(
        "[%s] %3.0f%% (%d/%d) %s | %s | %.2f",
        bar,
        pct,
        completed,
        total,
        trial.task_id,
        trial.variant_name,
        trial.score,
    )


def make_progress_callback(display_mode: str) -> ProgressCallback | None:
    """Create a progress callback based on display mode.

    Args:
        display_mode: One of "rich", "plain", or "none".

    Returns:
        A callback function or None if display_mode is "none".
    """
    if display_mode == "none":
        return None
    if display_mode == "plain":
        return _plain_callback
    return _rich_callback
