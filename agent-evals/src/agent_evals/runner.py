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
import time
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

ProgressCallback = Callable[[int, int, TrialResult], None]


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
    ) -> None:
        self._client = client
        self._config = config or EvalRunConfig()

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

        # Setup all variants
        for variant in variants:
            variant.setup(doc_tree)

        # Build the list of (task, variant, repetition) triples
        work_items: list[tuple[EvalTask, IndexVariant, int]] = []
        for variant in variants:
            for task in tasks:
                for rep in range(1, self._config.repetitions + 1):
                    work_items.append((task, variant, rep))

        total = len(work_items)
        trials: list[TrialResult] = []
        completed = 0

        try:
            if total > 0:
                with ThreadPoolExecutor(
                    max_workers=self._config.max_connections,
                ) as executor:
                    future_to_item = {
                        executor.submit(
                            self._run_trial, task, variant, doc_tree, rep
                        ): (task, variant, rep)
                        for task, variant, rep in work_items
                    }

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
                            trial = TrialResult(
                                task_id=task.definition.task_id,
                                task_type=task.definition.type,
                                variant_name=variant.metadata().name,
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
                            )
                        trials.append(trial)
                        completed += 1
                        if progress_callback is not None:
                            progress_callback(completed, total, trial)
        finally:
            # Teardown all variants even if an exception occurred
            for variant in variants:
                variant.teardown()

        elapsed = time.monotonic() - run_start
        total_cost = sum(t.cost for t in trials if t.cost is not None)
        total_tokens = sum(t.total_tokens for t in trials)

        result = EvalRunResult(
            config=self._config,
            trials=trials,
            total_cost=total_cost,
            total_tokens=total_tokens,
            elapsed_seconds=elapsed,
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
    ) -> None:
        """Configure task-specific variant parameters before rendering.

        For baseline variants that require per-task setup (oracle and
        length-matched-random), this method extracts the relevant
        information from task metadata and calls the appropriate setter.
        """
        if isinstance(variant, OracleBaseline):
            relevant = self._extract_relevant_docs(task, doc_tree)
            variant.set_relevant_docs(relevant)
        elif isinstance(variant, LengthMatchedRandomBaseline):
            relevant = self._extract_relevant_docs(task, doc_tree)
            oracle_tokens = sum(
                (doc_tree.files[p].token_count or 0)
                for p in relevant
                if p in doc_tree.files
                and doc_tree.files[p].token_count is not None
            )
            variant.set_target_tokens(oracle_tokens)

    def _run_trial(
        self,
        task: EvalTask,
        variant: IndexVariant,
        doc_tree: DocTree,
        repetition: int,
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

        # Configure task-specific variant parameters (oracle, LMR)
        self._setup_variant_for_task(variant, task, doc_tree)

        # Render and build prompt
        index_content = variant.render(doc_tree)
        messages = task.build_prompt(index_content)

        variant_meta = variant.metadata()
        variant_name = variant_meta.name

        # Check cache
        cached = False
        generation: GenerationResult | None = None

        if self._config.use_cache:
            # Include repetition in the cache key so that different
            # repetitions within a run are NOT served from cache.
            # DESIGN.md line 833: "Caching disabled across repetitions
            # within a run to capture variance."  Including the repetition
            # number means a re-run of the *same* configuration reuses
            # the prior results (cross-run caching), while different
            # repetitions always produce distinct API calls.
            cache_messages = [
                *messages,
                {"role": "system", "content": f"__rep:{repetition}"},
            ]
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

        # Cache miss: call LLM
        if generation is None:
            generation = self._client.complete(
                messages,
                max_tokens=self._config.max_tokens,
                temperature=self._config.temperature,
            )

            # Store in cache
            if self._config.use_cache:
                self._cache.put(
                    cache_key,
                    {
                        "content": generation.content,
                        "prompt_tokens": generation.prompt_tokens,
                        "completion_tokens": generation.completion_tokens,
                        "total_tokens": generation.total_tokens,
                        "cost": generation.cost,
                        "model": generation.model,
                        "generation_id": generation.generation_id,
                    },
                    model=generation.model,
                    tokens_used=generation.total_tokens,
                )

        # Score the response
        score = task.score_response(generation.content)

        latency = time.monotonic() - trial_start

        return TrialResult(
            task_id=task.definition.task_id,
            task_type=task.definition.type,
            variant_name=variant_name,
            repetition=repetition,
            score=score,
            metrics={},
            prompt_tokens=generation.prompt_tokens,
            completion_tokens=generation.completion_tokens,
            total_tokens=generation.total_tokens,
            cost=generation.cost,
            latency_seconds=latency,
            response=generation.content,
            cached=cached,
        )
