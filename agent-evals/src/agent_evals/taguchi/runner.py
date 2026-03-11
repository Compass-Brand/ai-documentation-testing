"""TaguchiRunner - executes trials based on a Taguchi OA design.

Instead of the full Cartesian product of variants, this runner generates
work items from OA rows.  Each row specifies one variant per axis (and
optionally a model), which are combined into a CompositeVariant for
evaluation.
"""

from __future__ import annotations

import logging
import signal
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from agent_evals.context.base import ContextStrategy
from agent_evals.context.full import FullContextStrategy
from agent_evals.diagnostics import DiagnosticTracker
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
    graceful_shutdown: bool = False


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
        store: Any | None = None,
        strategy_factory: Callable[[], ContextStrategy] | None = None,
    ) -> None:
        self._clients = clients
        self._config = config
        self._design = design
        self._variant_lookup = variant_lookup
        self._default_client_name = next(iter(clients))
        self._store = store
        self._strategy_factory = strategy_factory or (lambda: FullContextStrategy())
        # Thread-safe trial counter for judge sampling.
        self._trial_counter = 0
        self._trial_counter_lock = threading.Lock()

    def run(
        self,
        tasks: list[EvalTask],
        doc_tree: DocTree,
        progress_callback: ProgressCallback | None = None,
        source: str = "gold_standard",
        phase: str | None = None,
        completed_keys: set[tuple[int | None, str, str, int]] | None = None,
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
        shutdown_requested = threading.Event()

        # Install signal handlers for graceful shutdown (main thread only).
        old_sigint = None
        old_sigterm = None
        try:
            def _shutdown_handler(signum: int, frame: object) -> None:
                logger.info("Shutdown signal received (signal %d)", signum)
                shutdown_requested.set()

            old_sigint = signal.signal(signal.SIGINT, _shutdown_handler)
            old_sigterm = signal.signal(signal.SIGTERM, _shutdown_handler)
        except ValueError:
            # Not in main thread — skip signal registration.
            pass

        # Pre-build composites and strategies once per row.
        row_composites: dict[int, CompositeVariant] = {}
        row_strategies: dict[int, ContextStrategy] = {}
        row_rendered: dict[int, str] = {}
        skipped_rows: set[int] = set()
        for row in self._design.rows:
            composite = self._build_composite(row)
            if composite is None:
                skipped_rows.add(row.run_id)
                continue
            composite.setup(doc_tree)
            row_composites[row.run_id] = composite
            # Pre-render index and create per-row strategy
            rendered = composite.render(doc_tree)
            row_rendered[row.run_id] = rendered
            strategy = self._strategy_factory()
            strategy.setup(rendered, doc_tree)
            row_strategies[row.run_id] = strategy

        # Build work items: (row, task, repetition) — skip all-dummy rows.
        work_items: list[tuple[TaguchiExperimentRow, EvalTask, int]] = []
        for row in self._design.rows:
            if row.run_id in skipped_rows:
                continue
            for task in tasks:
                for rep in range(1, self._config.repetitions + 1):
                    work_items.append((row, task, rep))

        original_total = len(work_items)

        # Filter out already-completed trials for resume.
        if completed_keys:
            # Match on (oa_row_id, task_id, repetition) only -- variant_name
            # is ignored because it may differ between runs (e.g. axis 0
            # included in the original run but excluded on resume).
            completed_oa_keys: set[tuple[int | None, str, int]] = {
                (oa_row_id, task_id, rep)
                for oa_row_id, task_id, _variant, rep in completed_keys
            }
            work_items = [
                (row, task, rep)
                for row, task, rep in work_items
                if (row.run_id, task.definition.task_id, rep)
                not in completed_oa_keys
            ]

        remaining = len(work_items)
        offset = original_total - remaining
        total = remaining
        all_trials: list[TrialResult] = []
        completed = 0
        error_count = 0
        was_shutdown = False
        tracker = DiagnosticTracker(
            total_trials=remaining + offset, completed_offset=offset,
        )
        tracker.start()

        # Track per-row completion for logging and WAL checkpoints.
        total_rows = len(self._design.rows)
        trials_per_row = len(tasks) * self._config.repetitions
        row_completed_counts: dict[int, int] = {
            row.run_id: 0 for row in self._design.rows
        }

        try:
            if total > 0:
                with ThreadPoolExecutor(
                    max_workers=self._config.max_connections,
                ) as executor:
                    # Submit work in batches, checking for shutdown between.
                    futures = {}
                    for row, task, rep in work_items:
                        if shutdown_requested.is_set():
                            break
                        composite = row_composites[row.run_id]
                        strat = row_strategies[row.run_id]
                        rendered = row_rendered[row.run_id]
                        future = executor.submit(
                            self._run_trial, row, task, composite,
                            doc_tree, rep, source, phase,
                            strategy=strat, rendered_index=rendered,
                        )
                        futures[future] = (row, task, rep)

                    for future in as_completed(futures):
                        trial = future.result()
                        all_trials.append(trial)
                        completed += 1
                        if trial.error:
                            error_count += 1
                        tracker.record_trial(
                            tokens=trial.total_tokens,
                            cost=trial.cost,
                            retries=int(trial.metrics.get("retry_count", 0)),
                            api_ms=trial.metrics.get("api_call_ms", 0.0),
                            trial_ms=trial.latency_seconds * 1000,
                            error=trial.error is not None,
                            rate_limited=False,
                        )

                        # Track per-row progress.
                        oa_row_id = trial.metrics.get("oa_row_id")
                        if oa_row_id is not None:
                            row_id = int(oa_row_id)
                            row_completed_counts[row_id] = (
                                row_completed_counts.get(row_id, 0) + 1
                            )
                            if row_completed_counts[row_id] == trials_per_row:
                                completed_rows = sum(
                                    1 for c in row_completed_counts.values()
                                    if c >= trials_per_row
                                )
                                logger.info(
                                    "Row %d/%d complete: %d/%d trials (%.1f%%), %d errors",
                                    completed_rows,
                                    total_rows,
                                    completed,
                                    total,
                                    100.0 * completed / total,
                                    error_count,
                                )
                                # Flush WAL to disk after each row.
                                if self._store is not None:
                                    try:
                                        self._store.checkpoint_wal()
                                    except Exception:
                                        logger.debug(
                                            "WAL checkpoint failed",
                                            exc_info=True,
                                        )

                        if progress_callback is not None:
                            progress_callback(completed, total, trial)

                    if shutdown_requested.is_set():
                        was_shutdown = True
                        logger.info(
                            "Graceful shutdown: %d/%d trials saved",
                            completed, total,
                        )
        finally:
            tracker.stop()
            # Teardown per-row strategies.
            for strat in row_strategies.values():
                try:
                    strat.teardown()
                except Exception:
                    logger.warning(
                        "Strategy teardown failed for row",
                        exc_info=True,
                    )
            # Teardown all pre-built composites once per row.
            for composite in row_composites.values():
                try:
                    composite.teardown()
                except Exception:
                    logger.warning(
                        "Teardown failed for composite row",
                        exc_info=True,
                    )
            # Restore original signal handlers.
            try:
                if old_sigint is not None:
                    signal.signal(signal.SIGINT, old_sigint)
                if old_sigterm is not None:
                    signal.signal(signal.SIGTERM, old_sigterm)
            except ValueError:
                pass

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
            graceful_shutdown=was_shutdown,
        )

    def _run_trial(
        self,
        row: TaguchiExperimentRow,
        task: EvalTask,
        composite: CompositeVariant,
        doc_tree: DocTree,
        repetition: int,
        source: str,
        phase: str | None = None,
        strategy: ContextStrategy | None = None,
        rendered_index: str | None = None,
    ) -> TrialResult:
        """Execute a single trial for an OA row + task + repetition."""
        trial_start = time.monotonic()
        strategy = strategy or FullContextStrategy()
        strategy_name = strategy.name()

        # Build metrics dict with optional phase
        metrics: dict[str, float | str] = {"oa_row_id": float(row.run_id)}
        if phase is not None:
            metrics["phase"] = phase

        # Select client before try block so model name is available in error path.
        client = self._select_client(row)
        model_name = getattr(client, "model", self._default_client_name)

        try:
            # Use pre-rendered index or render now
            prompt_build_start = time.monotonic()
            index_content = rendered_index if rendered_index is not None else composite.render(doc_tree)

            # Use strategy to prepare and execute
            prepared = strategy.prepare(index_content, task, doc_tree)
            messages = prepared.messages
            prompt_build_ms = (time.monotonic() - prompt_build_start) * 1000

            strategy_result = strategy.execute(
                prepared, task, client,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
            )

            # Score
            score_start = time.monotonic()
            score = task.score_response(strategy_result.final_response)
            scoring_ms = (time.monotonic() - score_start) * 1000
            latency = time.monotonic() - trial_start

            # LLM-as-judge sampling
            with self._trial_counter_lock:
                trial_index = self._trial_counter
                self._trial_counter += 1
            sample_rate = self._config.judge_sample_rate
            judge_active = (
                self._config.judge_enabled
                and trial_index > 0
                and trial_index % sample_rate == 0
            )
            if judge_active:
                try:
                    question = getattr(task.definition, "question", None) or ""
                    judge_score, _rationale = self._call_judge(
                        client, task.definition.type,
                        question, strategy_result.final_response,
                    )
                    metrics["judge_score"] = judge_score
                    metrics["judge_heuristic_delta"] = round(
                        abs(judge_score - score), 4,
                    )
                except Exception:
                    logger.warning(
                        "Judge call failed (row %d, %s)",
                        row.run_id, task.definition.task_id,
                        exc_info=True,
                    )

            # Extract timing from first generation if available
            first_gen = (
                strategy_result.generations[0]
                if strategy_result.generations
                else None
            )
            metrics["scoring_ms"] = round(scoring_ms, 2)
            metrics["prompt_build_ms"] = round(prompt_build_ms, 2)
            metrics["api_call_ms"] = round(first_gen.api_call_ms, 1) if first_gen else 0.0
            metrics["total_api_ms"] = round(first_gen.total_api_ms, 1) if first_gen else 0.0
            metrics["retry_count"] = float(first_gen.retry_count) if first_gen else 0.0

            return TrialResult(
                task_id=task.definition.task_id,
                task_type=task.definition.type,
                variant_name=composite.metadata().name,
                repetition=repetition,
                score=score,
                metrics=metrics,
                prompt_tokens=strategy_result.total_prompt_tokens,
                completion_tokens=strategy_result.total_completion_tokens,
                total_tokens=strategy_result.total_tokens,
                cost=strategy_result.total_cost,
                latency_seconds=latency,
                response=strategy_result.final_response,
                cached=False,
                source=source,
                model=model_name,
                prompt_messages=messages,
                context_strategy=strategy_name,
                strategy_metadata=strategy_result.strategy_metadata,
                llm_calls=len(strategy_result.generations),
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
                model=model_name,
                context_strategy=strategy_name,
            )
    def _call_judge(
        self,
        client: LLMClient,
        task_type: str,
        question: str,
        response: str,
    ) -> tuple[float, str]:
        """Call LLM judge to score one trial response.

        Returns:
            Tuple of (score, rationale).
        """
        from agent_evals.judge.calibrator import (
            build_judge_prompt,
            parse_judge_response,
        )

        judge_model = self._config.judge_model
        messages = build_judge_prompt(
            task_type=task_type,
            question=question,
            response=response,
            rubric=None,
        )
        raw = client.complete(messages, model=judge_model).content
        score, rationale = parse_judge_response(raw)
        return score, rationale

    def _build_composite(self, row: TaguchiExperimentRow) -> CompositeVariant | None:
        """Create a CompositeVariant from an OA row's axis assignments.

        Returns None when every axis factor in the row is DUMMY_LEVEL.
        """
        from agent_evals.taguchi.factors import DUMMY_LEVEL

        components: dict[int, IndexVariant] = {}
        for factor in self._design.factors:
            if factor.axis is not None:
                variant_name = row.assignments[factor.name]
                if variant_name == DUMMY_LEVEL:
                    continue
                components[factor.axis] = self._variant_lookup[variant_name]
        if not components:
            logger.info("Skipping all-dummy OA row %d", row.run_id)
            return None
        return CompositeVariant(components)

    def _select_client(self, row: TaguchiExperimentRow) -> LLMClient:
        """Select the LLMClient for this row's model assignment."""
        from agent_evals.taguchi.factors import DUMMY_LEVEL

        if "model" in row.assignments:
            model_name = row.assignments["model"]
            if model_name == DUMMY_LEVEL:
                return self._clients[self._default_client_name]
            return self._clients[model_name]
        return self._clients[self._default_client_name]
