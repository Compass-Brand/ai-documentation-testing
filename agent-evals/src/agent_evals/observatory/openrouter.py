"""OpenRouter cost reconciliation.

Validates recorded trial costs against OpenRouter API billing data
and flags discrepancies in cost and token counts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from agent_evals.observatory.store import TrialRecord

logger = logging.getLogger(__name__)


@dataclass
class CostDiscrepancy:
    """A flagged cost mismatch between recorded and OpenRouter data."""

    trial_id: int
    model: str
    recorded_cost: float
    openrouter_cost: float | None
    absolute_diff: float
    percent_diff: float | None


@dataclass
class ReconciliationReport:
    """Summary of cost reconciliation between store and OpenRouter."""

    total_recorded: float
    total_openrouter: float
    discrepancy_count: int
    discrepancies: list[CostDiscrepancy] = field(default_factory=list)


def reconcile_trial_cost(
    trial: TrialRecord,
    openrouter_cost: float,
    *,
    percent_threshold: float = 0.01,
    absolute_threshold: float = 0.01,
) -> CostDiscrepancy | None:
    """Compare a single trial's recorded cost against OpenRouter cost.

    Returns a CostDiscrepancy if the difference exceeds thresholds,
    None otherwise.

    Args:
        trial: The trial record from the store.
        openrouter_cost: Cost reported by OpenRouter.
        percent_threshold: Minimum relative difference to flag (default 1%).
        absolute_threshold: Minimum absolute difference to flag (default $0.01).

    Returns:
        CostDiscrepancy if mismatch exceeds thresholds, else None.
    """
    recorded = trial.cost or 0.0
    abs_diff = abs(recorded - openrouter_cost)

    # Check absolute threshold first
    if abs_diff < absolute_threshold:
        return None

    # Check percent threshold
    base = max(recorded, openrouter_cost)
    if base > 0:
        pct_diff = abs_diff / base
        if pct_diff < percent_threshold:
            return None
    else:
        pct_diff = 0.0

    return CostDiscrepancy(
        trial_id=trial.trial_id,
        model=trial.model,
        recorded_cost=recorded,
        openrouter_cost=openrouter_cost,
        absolute_diff=abs_diff,
        percent_diff=pct_diff,
    )


def token_accuracy_check(
    trial: TrialRecord,
    or_prompt_tokens: int,
    or_completion_tokens: int,
    *,
    variance_threshold: float = 0.05,
) -> bool:
    """Check whether token counts match within tolerance.

    Args:
        trial: The trial record.
        or_prompt_tokens: OpenRouter's reported prompt tokens.
        or_completion_tokens: OpenRouter's reported completion tokens.
        variance_threshold: Maximum allowed relative variance (default 5%).

    Returns:
        True if token counts are within tolerance, False otherwise.
    """
    for recorded, reported in [
        (trial.prompt_tokens, or_prompt_tokens),
        (trial.completion_tokens, or_completion_tokens),
    ]:
        base = max(recorded, reported)
        if base > 0:
            variance = abs(recorded - reported) / base
            if variance > variance_threshold:
                return False
    return True


def find_discrepancies(
    trials: list[TrialRecord],
    openrouter_costs: dict[int, float],
) -> list[CostDiscrepancy]:
    """Find cost discrepancies across a list of trials.

    Args:
        trials: Trial records from the store.
        openrouter_costs: Mapping of trial_id to OpenRouter cost.

    Returns:
        List of CostDiscrepancy for trials with mismatched costs.
    """
    discrepancies: list[CostDiscrepancy] = []

    for trial in trials:
        or_cost = openrouter_costs.get(trial.trial_id)
        if or_cost is None:
            # No matching OpenRouter record
            discrepancies.append(CostDiscrepancy(
                trial_id=trial.trial_id,
                model=trial.model,
                recorded_cost=trial.cost or 0.0,
                openrouter_cost=None,
                absolute_diff=trial.cost or 0.0,
                percent_diff=None,
            ))
            continue

        result = reconcile_trial_cost(trial, or_cost)
        if result is not None:
            discrepancies.append(result)

    return discrepancies


def build_reconciliation_report(
    trials: list[TrialRecord],
    openrouter_costs: dict[int, float],
) -> ReconciliationReport:
    """Build a reconciliation report comparing store vs OpenRouter costs.

    Args:
        trials: Trial records from the store.
        openrouter_costs: Mapping of trial_id to OpenRouter cost.

    Returns:
        ReconciliationReport with totals and discrepancy list.
    """
    total_recorded = sum(t.cost or 0.0 for t in trials)
    total_or = sum(openrouter_costs.values())
    discs = find_discrepancies(trials, openrouter_costs)

    return ReconciliationReport(
        total_recorded=total_recorded,
        total_openrouter=total_or,
        discrepancy_count=len(discs),
        discrepancies=discs,
    )


def fetch_generation_stats(
    generation_id: str,
    *,
    api_key: str | None = None,
) -> dict[str, Any] | None:
    """Fetch generation stats from OpenRouter API.

    Args:
        generation_id: The OpenRouter generation ID.
        api_key: Optional API key (reads from env if not provided).

    Returns:
        Dict with generation stats, or None on failure.
    """
    try:
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        resp = httpx.get(
            f"https://openrouter.ai/api/v1/generation?id={generation_id}",
            headers=headers,
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        logger.debug("Failed to fetch generation %s", generation_id)
        return None
