"""Eval runner core: orchestrates evaluation runs across tasks and variants.

This module provides:
- TrialResult: Per-trial result dataclass with score, metrics, and metadata
- EvalRunConfig: Configuration for an evaluation run
- EvalRunResult: Aggregated results from a complete evaluation run
- EvalRunner: Orchestrator that runs tasks against variants with concurrency
"""

from __future__ import annotations

import csv
import io
import json
import logging
import signal
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

from agent_evals.context.base import ContextStrategy, StrategyResult
from agent_evals.context.full import FullContextStrategy
from agent_evals.diagnostics import DiagnosticTracker
from agent_evals.llm.cache import ResponseCache
from agent_evals.llm.client import GenerationResult, LLMClient
from agent_evals.variants.baselines import (
    LengthMatchedRandomBaseline,
    OracleBaseline,
)

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.tasks.base import EvalTask
    from agent_evals.variants.base import IndexVariant

JUDGE_SAMPLE_RATE = 50  # Call judge for 1 in every 50 trials (2%)
JUDGE_MODEL = "openrouter/openai/gpt-4o-mini"  # Cheap grading model


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class TrialResult:
    """Result of a single (task, variant, repetition) trial.

    Attributes:
        task_id: Identifier of the task that was evaluated.
        task_type: Type of the task (e.g. 'retrieval', 'code_generation').
        variant_name: Name of the index variant used.
        repetition: 1-based repetition number.
        score: Task score between 0.0 and 1.0.
        metrics: Additional metric name-value pairs.
        prompt_tokens: Number of tokens in the prompt.
        completion_tokens: Number of tokens in the completion.
        total_tokens: Total tokens (prompt + completion).
        cost: Monetary cost of the API call, if available.
        latency_seconds: Wall-clock time for the trial in seconds.
        response: Raw LLM response text.
        cached: Whether the result came from the response cache.
    """

    task_id: str
    task_type: str
    variant_name: str
    repetition: int
    score: float
    metrics: dict[str, float]
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float | None
    latency_seconds: float
    response: str
    cached: bool
    error: str | None = None
    source: str = "gold_standard"
    model: str = ""
    prompt_messages: list[dict] | None = None
    context_strategy: str | None = None
    strategy_metadata: dict = field(default_factory=dict)
    llm_calls: int = 1


@dataclass
class EvalRunConfig:
    """Configuration for an evaluation run.

    Attributes:
        repetitions: Number of times to repeat each (task, variant) pair.
        max_connections: Maximum concurrent API connections (thread pool size).
        max_tasks: Maximum number of tasks to process (for limiting runs).
        temperature: LLM sampling temperature.
        max_tokens: Maximum tokens for LLM completions.
        use_cache: Whether to use the response cache.
        cache_dir: Directory for cache files.
        output_dir: Directory for output reports.
        output_format: Output format (json|csv|both).
        display_mode: Progress display mode (rich|plain|none).
    """

    repetitions: int = 10
    max_connections: int = 10
    max_tasks: int = 1
    temperature: float = 0.3
    max_tokens: int = 2048
    use_cache: bool = True
    cache_dir: str = ".agent-evals-cache"
    output_dir: str = "reports"
    output_format: str = "both"
    display_mode: str = "rich"
    continue_on_error: bool = False
    store_traces: bool = False
    judge_enabled: bool = False
    judge_sample_rate: int = 20
    judge_model: str = "openrouter/openai/gpt-4o-mini"
    judge_mode: str = "routine"  # "routine" or "poll"
    poll_models: list[str] | None = None
    fetch_generation_stats: bool = False
    generation_stats_rate: float = 1.0

    _VALID_OUTPUT_FORMATS = frozenset({"json", "csv", "both"})
    _VALID_DISPLAY_MODES = frozenset({"rich", "plain", "none"})

    def __post_init__(self) -> None:
        if self.repetitions < 1:
            raise ValueError(f"repetitions must be >= 1, got {self.repetitions}")
        if self.max_connections < 1:
            raise ValueError(
                f"max_connections must be >= 1, got {self.max_connections}"
            )
        if self.max_tasks < 1:
            raise ValueError(f"max_tasks must be >= 1, got {self.max_tasks}")
        if self.max_tokens < 1:
            raise ValueError(f"max_tokens must be >= 1, got {self.max_tokens}")
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(
                f"temperature must be between 0.0 and 2.0, got {self.temperature}"
            )
        if self.output_format not in self._VALID_OUTPUT_FORMATS:
            raise ValueError(
                f"output_format must be one of {sorted(self._VALID_OUTPUT_FORMATS)}, "
                f"got {self.output_format!r}"
            )
        if self.display_mode not in self._VALID_DISPLAY_MODES:
            raise ValueError(
                f"display_mode must be one of {sorted(self._VALID_DISPLAY_MODES)}, "
                f"got {self.display_mode!r}"
            )


@dataclass
class EvalRunResult:
    """Aggregated results from a complete evaluation run.

    Attributes:
        config: The configuration used for this run.
        trials: All trial results collected during the run.
        total_cost: Sum of all trial costs (treating None as 0).
        total_tokens: Sum of all trial token counts.
        elapsed_seconds: Total wall-clock time for the run.
    """

    config: EvalRunConfig
    trials: list[TrialResult]
    total_cost: float
    total_tokens: int
    elapsed_seconds: float
    graceful_shutdown: bool = False


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

ProgressCallback = Callable[[int, int, TrialResult], None]


def compute_variant_summary(
    trials: list[TrialResult],
    variant_name: str,
) -> dict:
    """Compute aggregate summary statistics for a single variant.

    Args:
        trials: List of all trial results.
        variant_name: Name of the variant to summarise.

    Returns:
        Dict with variant_name, mean_score, trial_count, and
        hallucination_rate (if any trial carries a hallucination_score).
    """
    variant_trials = [t for t in trials if t.variant_name == variant_name]
    if not variant_trials:
        return {}

    scores = [t.score for t in variant_trials]
    h_scores = [
        t.metrics["hallucination_score"]
        for t in variant_trials
        if "hallucination_score" in t.metrics
    ]

    summary: dict = {
        "variant_name": variant_name,
        "mean_score": sum(scores) / len(scores),
        "trial_count": len(variant_trials),
    }

    if h_scores:
        summary["hallucination_rate"] = sum(h_scores) / len(h_scores)

    return summary


class EvalRunner:
    """Orchestrates evaluation runs across tasks and index variants.

    The runner:
    1. Calls ``variant.setup(doc_tree)`` for each variant.
    2. For each (variant, task, repetition) triple, executes a trial:
       renders the index, builds a prompt, queries the LLM (with caching),
       and scores the response.
    3. Calls ``variant.teardown()`` for each variant.
    4. Returns an :class:`EvalRunResult` with all trial data.

    Trials are executed concurrently via a :class:`ThreadPoolExecutor`
    whose size is controlled by ``config.max_connections``.

    Parameters
    ----------
    client:
        LLM client for completion calls.
    config:
        Run configuration. Defaults to :class:`EvalRunConfig` defaults.
    cache:
        Response cache instance. When ``None`` and ``config.use_cache`` is
        ``True``, a default :class:`ResponseCache` is created.
    """

    def __init__(
        self,
        client: LLMClient,
        config: EvalRunConfig | None = None,
        cache: ResponseCache | None = None,
        strategy_factory: Callable[[], ContextStrategy] | None = None,
    ) -> None:
        self._client = client
        self._config = config or EvalRunConfig()
        self._strategy_factory = strategy_factory or (lambda: FullContextStrategy())

        if cache is not None:
            self._cache = cache
        elif self._config.use_cache:
            self._cache = ResponseCache(
                cache_dir=self._config.cache_dir,
                enabled=True,
            )
        else:
            self._cache = ResponseCache(enabled=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        tasks: list[EvalTask],
        variants: list[IndexVariant],
        doc_tree: DocTree,
        progress_callback: ProgressCallback | None = None,
        source: str = "gold_standard",
        completed_keys: set[tuple[int | None, str, str, int]] | None = None,
    ) -> EvalRunResult:
        """Execute a full evaluation run.

        Parameters
        ----------
        tasks:
            Eval tasks to run against each variant.
        variants:
            Index variants to evaluate.
        doc_tree:
            Documentation tree passed to each variant for rendering.
        progress_callback:
            Optional callback invoked after each trial with
            ``(completed, total, trial_result)``.

        Returns
        -------
        EvalRunResult
            Aggregated results from all trials.
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

        # Setup all variants (track which succeeded for teardown safety)
        setup_variants: list[IndexVariant] = []
        variant_strategies: dict[str, ContextStrategy] = {}
        for variant in variants:
            try:
                variant.setup(doc_tree)
                setup_variants.append(variant)
                # Create per-variant strategy instance
                strategy = self._strategy_factory()
                vname = variant.metadata().name
                is_baseline = isinstance(
                    variant, (OracleBaseline, LengthMatchedRandomBaseline),
                )
                # Skip strategy setup for baselines with non-full strategies
                # (baselines produce per-task renders; non-full strategies
                # cache the rendered index at setup time).
                if not is_baseline or strategy.name() == "full_context":
                    strategy.setup(variant.render(doc_tree), doc_tree)
                variant_strategies[vname] = strategy
            except Exception:
                # Teardown variants that were already set up before re-raising
                for v in setup_variants:
                    try:
                        v.teardown()
                    except Exception:
                        logger.warning(
                            "Teardown failed for variant %s during setup cleanup",
                            v.metadata().name,
                            exc_info=True,
                        )
                for s in variant_strategies.values():
                    try:
                        s.teardown()
                    except Exception:
                        logger.warning(
                            "Strategy teardown failed during setup cleanup",
                            exc_info=True,
                        )
                raise

        # Build the list of (task, variant, repetition) triples
        work_items: list[tuple[EvalTask, IndexVariant, int]] = []
        for variant in variants:
            for task in tasks:
                for rep in range(1, self._config.repetitions + 1):
                    work_items.append((task, variant, rep))

        original_total = len(work_items)

        # Filter out already-completed trials for resume.
        if completed_keys:
            work_items = [
                (task, variant, rep)
                for task, variant, rep in work_items
                if (
                    None,
                    task.definition.task_id,
                    variant.metadata().name,
                    rep,
                ) not in completed_keys
            ]

        remaining = len(work_items)
        offset = original_total - remaining
        total = remaining
        trials: list[TrialResult] = []
        completed = 0
        tracker = DiagnosticTracker(
            total_trials=remaining + offset, completed_offset=offset,
        )
        tracker.start()

        try:
            if total > 0:
                with ThreadPoolExecutor(
                    max_workers=self._config.max_connections,
                ) as executor:
                    future_to_item = {}
                    for idx, (task, variant, rep) in enumerate(work_items, 1):
                        if shutdown_requested.is_set():
                            break
                        vname = variant.metadata().name
                        strat = variant_strategies.get(vname)
                        future = executor.submit(
                            self._run_trial, task, variant, doc_tree, rep, source,
                            trial_index=idx, strategy=strat,
                        )
                        future_to_item[future] = (task, variant, rep)

                    for future in as_completed(future_to_item):
                        try:
                            trial = future.result()
                        except Exception as exc:
                            if not self._config.continue_on_error:
                                raise
                            task, variant, rep = future_to_item[future]
                            logger.warning(
                                "Trial failed (%s/%s rep %d): %s",
                                task.definition.task_id,
                                variant.metadata().name,
                                rep,
                                exc,
                            )
                            vname = variant.metadata().name
                            strategy = variant_strategies.get(vname)
                            strategy_name = strategy.name() if strategy else None
                            trial = TrialResult(
                                task_id=task.definition.task_id,
                                task_type=task.definition.type,
                                variant_name=vname,
                                repetition=rep,
                                score=0.0,
                                metrics={},
                                prompt_tokens=0,
                                completion_tokens=0,
                                total_tokens=0,
                                cost=None,
                                latency_seconds=0.0,
                                response="",
                                cached=False,
                                error=str(exc),
                                source=source,
                                context_strategy=strategy_name,
                                llm_calls=0,
                            )
                        trials.append(trial)
                        completed += 1
                        tracker.record_trial(
                            tokens=trial.total_tokens,
                            cost=trial.cost,
                            retries=int(trial.metrics.get("retry_count", 0)),
                            api_ms=trial.metrics.get("api_call_ms", 0.0),
                            trial_ms=trial.latency_seconds * 1000,
                            error=trial.error is not None,
                            rate_limited=False,
                        )
                        if progress_callback is not None:
                            progress_callback(completed, total, trial)

        finally:
            tracker.stop()
            # Teardown all variant strategies.
            for s in variant_strategies.values():
                try:
                    s.teardown()
                except Exception:
                    logger.warning(
                        "Strategy teardown failed",
                        exc_info=True,
                    )
            # Teardown all variants even if an exception occurred.
            # Protect individual teardowns so one failure doesn't skip the rest.
            for variant in setup_variants:
                try:
                    variant.teardown()
                except Exception:
                    logger.warning(
                        "Teardown failed for variant %s",
                        variant.metadata().name,
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
        total_cost = sum(t.cost for t in trials if t.cost is not None)
        total_tokens = sum(t.total_tokens for t in trials)

        was_shutdown = shutdown_requested.is_set()
        if was_shutdown:
            logger.info(
                "Graceful shutdown complete: %d/%d trials saved",
                completed, total,
            )

        result = EvalRunResult(
            config=self._config,
            trials=trials,
            total_cost=total_cost,
            total_tokens=total_tokens,
            elapsed_seconds=elapsed,
            graceful_shutdown=was_shutdown,
        )

        if self._config.output_dir:
            saved_paths = self._save_results(result, tasks)
            for p in saved_paths:
                logger.info("Report saved to: %s", p)

        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _save_results(
        self,
        result: EvalRunResult,
        tasks: list[EvalTask],
    ) -> tuple[Path, ...]:
        """Save results to JSON and/or CSV files based on output_format.

        Returns a tuple of paths for the files that were written.
        """
        output_dir = Path(self._config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fmt = self._config.output_format

        # -- Trial dicts (shared between JSON and by_* aggregations) ---------
        trial_dicts: list[dict[str, Any]] = []
        for t in result.trials:
            trial_dicts.append({
                "task_id": t.task_id,
                "task_type": t.task_type,
                "variant_name": t.variant_name,
                "repetition": t.repetition,
                "score": t.score,
                "metrics": t.metrics,
                "prompt_tokens": t.prompt_tokens,
                "completion_tokens": t.completion_tokens,
                "total_tokens": t.total_tokens,
                "cost": t.cost,
                "latency_seconds": t.latency_seconds,
                "cached": t.cached,
                "error": t.error,
                "source": t.source,
                "context_strategy": t.context_strategy,
                "llm_calls": t.llm_calls,
                "strategy_metadata": t.strategy_metadata,
            })

        # -- by_variant aggregation ------------------------------------------
        variant_scores: dict[str, list[float]] = defaultdict(list)
        variant_tokens: dict[str, int] = defaultdict(int)
        variant_counts: dict[str, int] = defaultdict(int)
        for t in result.trials:
            variant_scores[t.variant_name].append(t.score)
            variant_tokens[t.variant_name] += t.total_tokens
            variant_counts[t.variant_name] += 1

        by_variant: dict[str, dict[str, Any]] = {}
        for name in variant_scores:
            scores = variant_scores[name]
            by_variant[name] = {
                "mean_score": sum(scores) / len(scores) if scores else 0.0,
                "trial_count": variant_counts[name],
                "total_tokens": variant_tokens[name],
            }

        # -- by_task_type aggregation ----------------------------------------
        task_type_scores: dict[str, list[float]] = defaultdict(list)
        task_type_counts: dict[str, int] = defaultdict(int)
        for t in result.trials:
            tt = t.task_type
            task_type_scores[tt].append(t.score)
            task_type_counts[tt] += 1

        by_task_type: dict[str, dict[str, Any]] = {}
        for tt in task_type_scores:
            scores = task_type_scores[tt]
            by_task_type[tt] = {
                "mean_score": sum(scores) / len(scores) if scores else 0.0,
                "trial_count": task_type_counts[tt],
            }

        # -- Config dict -----------------------------------------------------
        config_dict: dict[str, Any] = {
            "repetitions": self._config.repetitions,
            "max_connections": self._config.max_connections,
            "max_tasks": self._config.max_tasks,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "use_cache": self._config.use_cache,
            "cache_dir": self._config.cache_dir,
            "output_dir": self._config.output_dir,
            "output_format": self._config.output_format,
            "display_mode": self._config.display_mode,
        }

        paths: list[Path] = []

        # -- JSON report -----------------------------------------------------
        if fmt in ("json", "both"):
            report: dict[str, Any] = {
                "config": config_dict,
                "summary": {
                    "total_trials": len(result.trials),
                    "total_tokens": result.total_tokens,
                    "total_cost": result.total_cost,
                    "elapsed_seconds": result.elapsed_seconds,
                },
                "trials": trial_dicts,
                "by_variant": by_variant,
                "by_task_type": by_task_type,
            }

            json_path = output_dir / f"run_{timestamp}.json"
            json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            paths.append(json_path)

        # -- CSV report ------------------------------------------------------
        if fmt in ("csv", "both"):
            csv_fields = [
                "task_id",
                "task_type",
                "variant_name",
                "repetition",
                "score",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "cost",
                "latency_seconds",
                "cached",
                "error",
                "source",
                "context_strategy",
                "llm_calls",
            ]

            csv_path = output_dir / f"run_{timestamp}.csv"
            buf = io.StringIO()
            writer = csv.DictWriter(
                buf, fieldnames=csv_fields, extrasaction="ignore",
            )
            writer.writeheader()
            for td in trial_dicts:
                writer.writerow(td)
            csv_path.write_text(buf.getvalue(), encoding="utf-8")
            paths.append(csv_path)

        return tuple(paths)

    @staticmethod
    def _extract_relevant_docs(
        task: EvalTask,
        doc_tree: DocTree,
    ) -> list[str]:
        """Extract relevant doc paths from task metadata.

        Maps from various metadata keys used by different task types:
        - ``expected_files`` → direct list (retrieval, canary, sentinel tasks)
        - ``sources[].name`` → filenames matched against doc tree (conflicting)
        - ``nearest_doc`` → single doc path (negative tasks)

        Falls back to all doc tree paths when no file references are found.
        """
        meta = task.definition.metadata

        # Direct file list
        expected_files = meta.get("expected_files")
        if expected_files and isinstance(expected_files, list):
            return list(expected_files)

        # Agentic task file dict (path -> summary)
        files_dict = meta.get("files")
        if files_dict and isinstance(files_dict, dict):
            return list(files_dict.keys())

        # Sources with name field (conflicting tasks)
        sources = meta.get("sources")
        if sources and isinstance(sources, list):
            doc_paths: list[str] = []
            for source in sources:
                name = source.get("name", "") if isinstance(source, dict) else ""
                if not name:
                    continue
                # Match filename against doc tree paths
                for path in doc_tree.files:
                    if path.endswith(name) or path.endswith(f"/{name}"):
                        doc_paths.append(path)
                        break
            if doc_paths:
                return doc_paths

        # Single nearest doc (negative tasks)
        nearest_doc = meta.get("nearest_doc")
        if nearest_doc and isinstance(nearest_doc, str):
            return [nearest_doc]

        # Fallback: all docs (degrades oracle to full-index)
        return list(doc_tree.files.keys())

    def _setup_variant_for_task(
        self,
        variant: IndexVariant,
        task: EvalTask,
        doc_tree: DocTree,
    ) -> IndexVariant:
        """Configure task-specific variant parameters before rendering.

        For baseline variants that require per-task setup (oracle and
        length-matched-random), this method creates a shallow copy to
        avoid mutating the shared instance from concurrent threads,
        then sets the task-specific state on the copy.

        Returns the (possibly copied) variant to use for rendering.
        """
        import copy

        if isinstance(variant, OracleBaseline):
            variant = copy.copy(variant)
            relevant = self._extract_relevant_docs(task, doc_tree)
            variant.set_relevant_docs(relevant)
        elif isinstance(variant, LengthMatchedRandomBaseline):
            variant = copy.copy(variant)
            relevant = self._extract_relevant_docs(task, doc_tree)
            oracle_tokens = sum(
                (doc_tree.files[p].token_count or 0)
                for p in relevant
                if p in doc_tree.files
                and doc_tree.files[p].token_count is not None
            )
            variant.set_target_tokens(oracle_tokens)
        return variant

    def _call_judge(self, task_type: str, question: str, response: str) -> "JudgeScore":
        """Call LLM judge to score one trial response.

        PHASE A GUARD: judge scores are validation-only. Do NOT modify
        trial.score with judge results. See Phase B Task 9 for graduation.
        """
        from agent_evals.judge.calibrator import (
            JudgeScore,
            build_judge_prompt,
            parse_judge_response,
        )

        if self._config.judge_mode == "poll":
            from agent_evals.judge.poll import PollConfig, build_poll_result

            poll_config = PollConfig(
                panel_models=self._config.poll_models or [
                    "openrouter/openai/gpt-5-mini",
                    "openrouter/anthropic/claude-haiku-4.5",
                    "openrouter/google/gemini-2.5-flash",
                ],
            )
            # Collect scores from each panel model
            scores_by_model: dict[str, list[JudgeScore]] = {}
            for model in poll_config.panel_models:
                messages = build_judge_prompt(
                    task_type=task_type,
                    question=question,
                    response=response,
                    rubric=None,
                )
                raw = self._client.complete(messages, model=model).content
                score_val, rationale = parse_judge_response(raw)
                js = JudgeScore(
                    example_id="",
                    judge_model=model,
                    score=score_val,
                    rationale=rationale,
                    raw_response=raw,
                )
                scores_by_model.setdefault(model, []).append(js)

            result = build_poll_result(scores_by_model, config=poll_config)
            agg_score = result.scores[0].aggregated_score if result.scores else 0.0
            return JudgeScore(
                example_id="",
                judge_model=f"poll:{','.join(poll_config.panel_models)}",
                score=agg_score,
                rationale=f"PoLL aggregate ({poll_config.aggregation})",
                raw_response="",
            )

        # Routine mode: single model
        judge_model = self._config.judge_model
        messages = build_judge_prompt(
            task_type=task_type,
            question=question,
            response=response,
            rubric=None,
        )
        raw = self._client.complete(messages, model=judge_model).content
        score, rationale = parse_judge_response(raw)
        return JudgeScore(
            example_id="",
            judge_model=judge_model,
            score=score,
            rationale=rationale,
            raw_response=raw,
        )

    def _run_trial(
        self,
        task: EvalTask,
        variant: IndexVariant,
        doc_tree: DocTree,
        repetition: int,
        source: str = "gold_standard",
        trial_index: int = 0,
        strategy: ContextStrategy | None = None,
    ) -> TrialResult:
        """Execute a single (task, variant, repetition) trial.

        Parameters
        ----------
        task:
            The eval task to run.
        variant:
            The index variant providing index content.
        doc_tree:
            Documentation tree for rendering.
        repetition:
            1-based repetition number.
        strategy:
            Context strategy for this variant (looked up from variant_strategies).

        Returns
        -------
        TrialResult
            The trial result with score, token counts, and timing.

        Raises
        ------
        LLMClientError
            If the LLM call fails and no cached response is available.
        """
        trial_start = time.monotonic()
        strategy = strategy or FullContextStrategy()
        strategy_name = strategy.name()

        # Get a thread-safe variant (copied for stateful baselines).
        variant = self._setup_variant_for_task(variant, task, doc_tree)

        prompt_build_start = time.monotonic()
        index_content = variant.render(doc_tree)

        # Use strategy to prepare context
        prepared = strategy.prepare(index_content, task, doc_tree)
        messages = prepared.messages
        prompt_build_ms = (time.monotonic() - prompt_build_start) * 1000

        variant_meta = variant.metadata()
        variant_name = variant_meta.name

        # Check cache (only if strategy supports it)
        cached = False
        strategy_result: StrategyResult | None = None

        if self._config.use_cache and strategy.supports_caching():
            cache_messages = [
                *messages,
                {"role": "system", "content": f"__rep:{repetition}"},
            ]
            # Include strategy name in cache key for non-full_context
            # to preserve backward compat with existing caches.
            if strategy_name != "full_context":
                cache_messages.append(
                    {"role": "system", "content": f"__strategy:{strategy_name}"},
                )
            cache_key = self._cache.make_key(
                model=self._client.model,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                messages=cache_messages,
            )
            entry = self._cache.get(cache_key)
            if entry is not None:
                cached = True
                resp_data: dict[str, Any] = entry.response
                generation = GenerationResult(
                    content=resp_data.get("content", ""),
                    prompt_tokens=resp_data.get("prompt_tokens", 0),
                    completion_tokens=resp_data.get("completion_tokens", 0),
                    total_tokens=resp_data.get("total_tokens", 0),
                    cost=resp_data.get("cost"),
                    model=resp_data.get("model", self._client.model),
                    generation_id=resp_data.get("generation_id"),
                )
                strategy_result = StrategyResult(
                    final_response=generation.content,
                    generations=[generation],
                    total_prompt_tokens=generation.prompt_tokens,
                    total_completion_tokens=generation.completion_tokens,
                    total_tokens=generation.total_tokens,
                    total_cost=generation.cost,
                    messages=messages,
                    strategy_metadata=prepared.strategy_metadata,
                )

        # Cache miss: execute via strategy
        if strategy_result is None:
            strategy_result = strategy.execute(
                prepared, task, self._client,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
            )

            # Store in cache
            if self._config.use_cache and strategy.supports_caching():
                first_gen = (
                    strategy_result.generations[0]
                    if strategy_result.generations
                    else None
                )
                self._cache.put(
                    cache_key,
                    {
                        "content": strategy_result.final_response,
                        "prompt_tokens": strategy_result.total_prompt_tokens,
                        "completion_tokens": strategy_result.total_completion_tokens,
                        "total_tokens": strategy_result.total_tokens,
                        "cost": strategy_result.total_cost,
                        "model": first_gen.model if first_gen else self._client.model,
                        "generation_id": first_gen.generation_id if first_gen else None,
                    },
                    model=first_gen.model if first_gen else self._client.model,
                    tokens_used=strategy_result.total_tokens,
                )

        # Score the response
        score_start = time.monotonic()
        score = task.score_response(strategy_result.final_response)
        scoring_ms = (time.monotonic() - score_start) * 1000

        latency = time.monotonic() - trial_start

        # Extract timing from first generation if available
        first_gen = (
            strategy_result.generations[0]
            if strategy_result.generations
            else None
        )
        metrics: dict[str, float] = {
            "scoring_ms": round(scoring_ms, 2),
            "prompt_build_ms": round(prompt_build_ms, 2),
            "api_call_ms": round(first_gen.api_call_ms, 1) if first_gen else 0.0,
            "total_api_ms": round(first_gen.total_api_ms, 1) if first_gen else 0.0,
            "retry_count": float(first_gen.retry_count) if first_gen else 0.0,
        }

        # Build CostMetrics from strategy result
        from agent_evals.metrics import CostMetrics

        cost_metrics = CostMetrics(
            prompt_tokens=strategy_result.total_prompt_tokens,
            completion_tokens=strategy_result.total_completion_tokens,
            reasoning_tokens=first_gen.reasoning_tokens if first_gen else 0,
            cached_tokens=first_gen.cached_tokens if first_gen else 0,
            cache_write_tokens=first_gen.cache_write_tokens if first_gen else 0,
            total_cost_usd=strategy_result.total_cost,
            cache_discount_usd=None,
            latency_ms=first_gen.api_call_ms if first_gen else None,
            generation_time_ms=None,
            provider=first_gen.provider if first_gen else None,
            generation_id=first_gen.generation_id if first_gen else None,
            provider_fallbacks=0,
        )

        # Optionally fetch generation stats from OpenRouter
        if self._config.fetch_generation_stats and cost_metrics.generation_id:
            from agent_evals.llm.generation_stats import fetch_generation_stats

            stats = fetch_generation_stats(
                cost_metrics.generation_id,
                api_key=self._client.api_key,
                fetch_rate=self._config.generation_stats_rate,
            )
            if stats:
                cost_metrics = CostMetrics(
                    prompt_tokens=cost_metrics.prompt_tokens,
                    completion_tokens=cost_metrics.completion_tokens,
                    reasoning_tokens=cost_metrics.reasoning_tokens,
                    cached_tokens=cost_metrics.cached_tokens,
                    cache_write_tokens=cost_metrics.cache_write_tokens,
                    total_cost_usd=cost_metrics.total_cost_usd,
                    cache_discount_usd=stats.cache_discount,
                    latency_ms=stats.latency_ms,
                    generation_time_ms=stats.generation_time_ms,
                    provider=stats.provider_name or cost_metrics.provider,
                    generation_id=cost_metrics.generation_id,
                    provider_fallbacks=stats.provider_fallbacks,
                )

        metrics["cost_metrics"] = cost_metrics.to_dict()
        # LLM-as-judge sampling: configurable via EvalRunConfig
        sample_rate = self._config.judge_sample_rate
        judge_active = self._config.judge_enabled and trial_index > 0 and trial_index % sample_rate == 0
        if judge_active:
            try:
                question = getattr(task.definition, "question", None) or ""
                judge_result = self._call_judge(
                    task.definition.type,
                    question,
                    strategy_result.final_response,
                )
                metrics["judge_score"] = judge_result.score
                metrics["judge_heuristic_delta"] = round(
                    abs(judge_result.score - score), 4,
                )
            except Exception:
                logger.warning("Judge call failed for trial %d", trial_index, exc_info=True)

        return TrialResult(
            task_id=task.definition.task_id,
            task_type=task.definition.type,
            variant_name=variant_name,
            repetition=repetition,
            score=score,
            metrics=metrics,
            prompt_tokens=strategy_result.total_prompt_tokens,
            completion_tokens=strategy_result.total_completion_tokens,
            total_tokens=strategy_result.total_tokens,
            cost=strategy_result.total_cost,
            latency_seconds=latency,
            response=strategy_result.final_response,
            cached=cached,
            source=source,
            model=self._client.model,
            prompt_messages=messages,
            context_strategy=strategy_name,
            strategy_metadata=strategy_result.strategy_metadata,
            llm_calls=len(strategy_result.generations),
        )
