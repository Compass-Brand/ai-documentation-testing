"""TaguchiRunner - executes trials based on a Taguchi OA design.

Instead of the full Cartesian product of variants, this runner generates
work items from OA rows.  Each row specifies one variant per axis (and
optionally a model), which are combined into a CompositeVariant for
evaluation.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import TYPE_CHECKING

from agent_evals.runner import EvalRunConfig, TrialResult
from agent_evals.taguchi.factors import TaguchiDesign, TaguchiExperimentRow
from agent_evals.variants.composite import CompositeVariant

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.llm.client import LLMClient
    from agent_evals.tasks.base import EvalTask
    from agent_evals.variants.base import IndexVariant

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int, TrialResult], None]


@dataclass
class TaguchiRunResult:
    """Results from a complete Taguchi evaluation run."""

    design: TaguchiDesign
    config: EvalRunConfig
    trials: list[TrialResult]
    total_cost: float
    total_tokens: int
    elapsed_seconds: float


class TaguchiRunner:
    """Runs evaluation trials based on a Taguchi orthogonal array design.

    For each OA row the runner:
    1. Looks up the variant for each axis assignment.
    2. Creates a CompositeVariant from those variants.
    3. Looks up the LLMClient for the model assignment (if multi-model).
    4. Runs all tasks x repetitions against that combo.
    """

    def __init__(
        self,
        clients: dict[str, LLMClient],
        config: EvalRunConfig,
        design: TaguchiDesign,
        variant_lookup: dict[str, IndexVariant],
    ) -> None:
        self._clients = clients
        self._config = config
        self._design = design
        self._variant_lookup = variant_lookup
        self._default_client_name = next(iter(clients))

    def run(
        self,
        tasks: list[EvalTask],
        doc_tree: DocTree,
        progress_callback: ProgressCallback | None = None,
        source: str = "gold_standard",
        phase: str | None = None,
    ) -> TaguchiRunResult:
        """Execute trials for all OA rows x tasks x repetitions.

        Args:
            tasks: Eval tasks to run against each composite variant.
            doc_tree: Documentation tree for variant rendering.
            progress_callback: Optional ``(completed, total, trial)`` callback.
            source: Source tag for all resulting TrialResults.
            phase: Pipeline phase name (e.g. "screening", "confirmation").

        Returns:
            TaguchiRunResult with all trials and aggregated metrics.
        """
        run_start = time.monotonic()

        # Build work items: (row, task, repetition)
        work_items: list[tuple[TaguchiExperimentRow, EvalTask, int]] = []
        for row in self._design.rows:
            for task in tasks:
                for rep in range(1, self._config.repetitions + 1):
                    work_items.append((row, task, rep))

        total = len(work_items)
        all_trials: list[TrialResult] = []
        completed = 0

        if total > 0:
            with ThreadPoolExecutor(
                max_workers=self._config.max_connections,
            ) as executor:
                future_to_item = {
                    executor.submit(
                        self._run_trial, row, task, doc_tree, rep, source, phase
                    ): (row, task, rep)
                    for row, task, rep in work_items
                }
                for future in as_completed(future_to_item):
                    trial = future.result()
                    all_trials.append(trial)
                    completed += 1
                    if progress_callback is not None:
                        progress_callback(completed, total, trial)

        elapsed = time.monotonic() - run_start
        total_cost = sum(t.cost for t in all_trials if t.cost is not None)
        total_tokens = sum(t.total_tokens for t in all_trials)

        return TaguchiRunResult(
            design=self._design,
            config=self._config,
            trials=all_trials,
            total_cost=total_cost,
            total_tokens=total_tokens,
            elapsed_seconds=elapsed,
        )

    def _run_trial(
        self,
        row: TaguchiExperimentRow,
        task: EvalTask,
        doc_tree: DocTree,
        repetition: int,
        source: str,
        phase: str | None = None,
    ) -> TrialResult:
        """Execute a single trial for an OA row + task + repetition."""
        trial_start = time.monotonic()

        # Build composite variant from row assignments
        composite = self._build_composite(row)
        composite.setup(doc_tree)

        # Build metrics dict with optional phase
        metrics: dict[str, float | str] = {"oa_row_id": float(row.run_id)}
        if phase is not None:
            metrics["phase"] = phase

        try:
            # Select client
            client = self._select_client(row)

            # Render and build prompt
            index_content = composite.render(doc_tree)
            messages = task.build_prompt(index_content)

            # Call LLM
            generation = client.complete(
                messages,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
            )

            # Score
            score = task.score_response(generation.content)
            latency = time.monotonic() - trial_start

            return TrialResult(
                task_id=task.definition.task_id,
                task_type=task.definition.type,
                variant_name=composite.metadata().name,
                repetition=repetition,
                score=score,
                metrics=metrics,
                prompt_tokens=generation.prompt_tokens,
                completion_tokens=generation.completion_tokens,
                total_tokens=generation.total_tokens,
                cost=generation.cost,
                latency_seconds=latency,
                response=generation.content,
                cached=False,
                source=source,
            )
        except Exception as exc:
            logger.warning(
                "Trial failed (row %d, %s rep %d): %s",
                row.run_id,
                task.definition.task_id,
                repetition,
                exc,
            )
            latency = time.monotonic() - trial_start
            return TrialResult(
                task_id=task.definition.task_id,
                task_type=task.definition.type,
                variant_name=composite.metadata().name,
                repetition=repetition,
                score=0.0,
                metrics=metrics,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost=None,
                latency_seconds=latency,
                response="",
                cached=False,
                error=str(exc),
                source=source,
            )
        finally:
            composite.teardown()

    def _build_composite(self, row: TaguchiExperimentRow) -> CompositeVariant:
        """Create a CompositeVariant from an OA row's axis assignments."""
        components: dict[int, IndexVariant] = {}
        for factor in self._design.factors:
            if factor.axis is not None:
                variant_name = row.assignments[factor.name]
                components[factor.axis] = self._variant_lookup[variant_name]
        return CompositeVariant(components)

    def _select_client(self, row: TaguchiExperimentRow) -> LLMClient:
        """Select the LLMClient for this row's model assignment."""
        if "model" in row.assignments:
            model_name = row.assignments["model"]
            return self._clients[model_name]
        return self._clients[self._default_client_name]
