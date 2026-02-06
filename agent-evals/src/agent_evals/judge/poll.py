"""Panel of LLM evaluators (PoLL) for final comparison.

Implements the two-tier evaluation strategy from DESIGN.md:
- GPT-4o-mini for routine evaluation runs
- 3-model PoLL panel for validation / final comparison

Panels of smaller models outperform a single GPT-4 judge at 7-8x lower
cost (Verga et al., 2024).  The PoLL aggregate is validated against the
routine model via Spearman correlation (target >= 0.80).
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field

from agent_evals.judge.calibrator import JudgeScore, compute_spearman

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_PANEL: list[str] = [
    "openrouter/openai/gpt-4o-mini",
    "openrouter/anthropic/claude-3.5-haiku",
    "openrouter/google/gemini-2.0-flash-001",
]
"""Default 3-model panel for PoLL evaluation."""

ROUTINE_MODEL: str = "openrouter/openai/gpt-4o-mini"
"""Model used for routine (non-PoLL) evaluation runs."""

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class PanelScore:
    """Aggregated score for one example across the panel."""

    example_id: str
    panel_scores: list[JudgeScore]
    aggregated_score: float
    score_spread: float  # max - min across panel members
    aggregation_method: str = "mean"


@dataclass
class PollResult:
    """Complete result from a PoLL evaluation."""

    panel_models: list[str]
    scores: list[PanelScore]
    correlation_with_routine: float | None = None
    correlation_passed: bool = False


@dataclass
class PollConfig:
    """Configuration for a PoLL evaluation."""

    panel_models: list[str] = field(default_factory=lambda: list(DEFAULT_PANEL))
    routine_model: str = ROUTINE_MODEL
    aggregation: str = "mean"
    correlation_threshold: float = 0.80


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def aggregate_panel_scores(
    judge_scores_by_model: dict[str, list[JudgeScore]],
    aggregation: str = "mean",
) -> list[PanelScore]:
    """Aggregate scores from multiple panel models per example.

    Groups scores by ``example_id`` across models, then computes the
    aggregated score (mean or median) and the score spread (max - min)
    for each example.

    Parameters
    ----------
    judge_scores_by_model:
        Mapping from model identifier to that model's list of
        :class:`JudgeScore` objects.
    aggregation:
        ``"mean"`` (default) or ``"median"``.

    Returns
    -------
    list[PanelScore]
        One entry per unique example, sorted by ``example_id``.
    """
    if aggregation not in ("mean", "median"):
        msg = f"Unsupported aggregation method: {aggregation!r} (expected 'mean' or 'median')"
        raise ValueError(msg)

    # Collect scores per example across all models
    by_example: dict[str, list[JudgeScore]] = defaultdict(list)
    for scores in judge_scores_by_model.values():
        for js in scores:
            by_example[js.example_id].append(js)

    results: list[PanelScore] = []
    for example_id in sorted(by_example.keys()):
        panel_scores = by_example[example_id]
        raw_values = [js.score for js in panel_scores]

        if aggregation == "median":
            agg = statistics.median(raw_values)
        else:
            agg = statistics.mean(raw_values)

        spread = max(raw_values) - min(raw_values)

        results.append(
            PanelScore(
                example_id=example_id,
                panel_scores=panel_scores,
                aggregated_score=agg,
                score_spread=spread,
                aggregation_method=aggregation,
            )
        )

    return results


def validate_panel_correlation(
    poll_scores: list[PanelScore],
    routine_scores: list[JudgeScore],
    threshold: float = 0.80,
) -> tuple[float, bool]:
    """Validate PoLL aggregate correlates with routine model scores.

    Computes Spearman rank correlation between the PoLL aggregated scores
    and the routine model scores for all overlapping examples.

    Parameters
    ----------
    poll_scores:
        Aggregated panel scores from :func:`aggregate_panel_scores`.
    routine_scores:
        Scores from the routine (single-model) judge.
    threshold:
        Minimum Spearman rho to pass.  Default ``0.80``.

    Returns
    -------
    tuple[float, bool]
        ``(correlation, passed)`` where *passed* is ``True`` when
        ``correlation >= threshold``.
    """
    poll_lookup: dict[str, float] = {
        ps.example_id: ps.aggregated_score for ps in poll_scores
    }
    routine_lookup: dict[str, float] = {
        js.example_id: js.score for js in routine_scores
    }

    common_ids = sorted(set(poll_lookup.keys()) & set(routine_lookup.keys()))

    if not common_ids:
        return 0.0, False

    poll_values = [poll_lookup[eid] for eid in common_ids]
    routine_values = [routine_lookup[eid] for eid in common_ids]

    correlation = compute_spearman(poll_values, routine_values)
    return correlation, correlation >= threshold


def build_poll_result(
    judge_scores_by_model: dict[str, list[JudgeScore]],
    routine_scores: list[JudgeScore] | None = None,
    config: PollConfig | None = None,
) -> PollResult:
    """Build a complete PoLL result.

    This is the main entry point: it aggregates panel scores and
    optionally validates correlation with the routine model.

    Parameters
    ----------
    judge_scores_by_model:
        Mapping from model identifier to that model's scores.
    routine_scores:
        Optional routine-model scores for correlation validation.
    config:
        Optional configuration; uses defaults when ``None``.
    """
    cfg = config or PollConfig()

    panel_scores = aggregate_panel_scores(
        judge_scores_by_model,
        aggregation=cfg.aggregation,
    )

    correlation: float | None = None
    passed = False

    if routine_scores is not None:
        correlation, passed = validate_panel_correlation(
            panel_scores,
            routine_scores,
            threshold=cfg.correlation_threshold,
        )

    return PollResult(
        panel_models=list(cfg.panel_models),
        scores=panel_scores,
        correlation_with_routine=correlation,
        correlation_passed=passed,
    )


def identify_disagreements(
    scores: list[PanelScore],
    spread_threshold: float = 0.3,
) -> list[PanelScore]:
    """Find examples where panel members disagree significantly.

    Parameters
    ----------
    scores:
        Panel scores from :func:`aggregate_panel_scores`.
    spread_threshold:
        Minimum ``score_spread`` to be flagged.  Default ``0.3``.

    Returns
    -------
    list[PanelScore]
        Subset of *scores* where ``score_spread > spread_threshold``.
    """
    return [ps for ps in scores if ps.score_spread > spread_threshold]


def format_poll_report(result: PollResult) -> str:
    """Format a human-readable PoLL summary report.

    Includes panel composition, per-model statistics, aggregated scores,
    correlation with routine model, and any high-disagreement examples.
    """
    lines: list[str] = []

    # Header
    lines.append("=" * 60)
    lines.append("PoLL (Panel of LLM Evaluators) Report")
    lines.append("=" * 60)

    # Panel composition
    lines.append("")
    lines.append("Panel Models:")
    for model in result.panel_models:
        lines.append(f"  - {model}")

    lines.append("")
    lines.append(f"Total Examples: {len(result.scores)}")

    # Per-model statistics
    if result.scores:
        model_scores: dict[str, list[float]] = defaultdict(list)
        for ps in result.scores:
            for js in ps.panel_scores:
                model_scores[js.judge_model].append(js.score)

        lines.append("")
        lines.append("Per-Model Statistics:")
        for model in sorted(model_scores.keys()):
            vals = model_scores[model]
            avg = statistics.mean(vals)
            lines.append(f"  {model}: mean={avg:.3f}, n={len(vals)}")

    # Aggregated score summary
    if result.scores:
        agg_values = [ps.aggregated_score for ps in result.scores]
        agg_mean = statistics.mean(agg_values)
        lines.append("")
        lines.append(f"Aggregated Score (mean of means): {agg_mean:.3f}")

    # Correlation
    lines.append("")
    lines.append("Correlation with Routine Model:")
    if result.correlation_with_routine is not None:
        status = "PASSED" if result.correlation_passed else "FAILED"
        lines.append(
            f"  Spearman rho = {result.correlation_with_routine:.3f} [{status}]"
        )
    else:
        lines.append("  Not computed (no routine scores provided)")

    # Disagreements
    disagreements = identify_disagreements(result.scores)
    lines.append("")
    lines.append(f"Disagreements (spread > 0.3): {len(disagreements)}")
    for ps in disagreements:
        individual = ", ".join(
            f"{js.judge_model}={js.score:.2f}" for js in ps.panel_scores
        )
        lines.append(
            f"  {ps.example_id}: spread={ps.score_spread:.2f} ({individual})"
        )

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)
