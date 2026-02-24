"""Run lifecycle manager for dashboard-started evaluations.

Encapsulates starting, monitoring, and cancelling evaluation runs
initiated from the web UI. Uses the dashboard's shared store and
tracker so trials appear in the Live Monitor in real time.
"""

from __future__ import annotations

import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker

logger = logging.getLogger(__name__)


class RunConflictError(Exception):
    """Raised when attempting to start a run while one is already active."""


class StartRunRequest(BaseModel):
    """Validated request to start an evaluation run from the dashboard."""

    mode: Literal["full", "taguchi"] = "taguchi"
    model: str
    repetitions: int = Field(default=3, ge=1, le=100)
    task_limit: int = Field(default=0, ge=0)
    oa_override: str | None = None
    pipeline_mode: Literal["auto", "semi"] | None = None
    quality_type: Literal[
        "larger_is_better", "smaller_is_better", "nominal_is_best"
    ] = "larger_is_better"
    top_k: int = Field(default=3, ge=1, le=10)
    alpha: float = Field(default=0.05, ge=0.001, le=0.1)


class RunManager:
    """Manages background evaluation runs started from the dashboard.

    Args:
        store: The dashboard's shared ObservatoryStore.
        tracker: The dashboard's shared EventTracker.
    """

    def __init__(
        self, store: ObservatoryStore, tracker: EventTracker
    ) -> None:
        self._store = store
        self._tracker = tracker
        self._active: dict[str, Any] | None = None
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def active_run(self) -> dict[str, Any] | None:
        """Return info about the active run, or None."""
        with self._lock:
            if self._active is None:
                return None
            return dict(self._active)

    def start_run(self, request: StartRunRequest) -> str:
        """Start a background evaluation run.

        Returns the run_id. Raises RunConflictError if a run is active.
        """
        with self._lock:
            if self._active is not None:
                raise RunConflictError("A run is already in progress")

            run_id = uuid.uuid4().hex[:12]
            models = [m.strip() for m in request.model.split(",")]

            self._active = {
                "run_id": run_id,
                "mode": request.mode,
                "models": models,
                "started_at": datetime.now(tz=timezone.utc).isoformat(),
            }
            self._cancel_event.clear()

        thread = threading.Thread(
            target=self._run_wrapper,
            args=(run_id, request),
            daemon=True,
        )
        self._thread = thread
        thread.start()

        return run_id

    def cancel_run(self) -> bool:
        """Request cancellation of the active run.

        Returns True if a run was cancelled, False if none active.
        """
        with self._lock:
            if self._active is None:
                return False
            self._cancel_event.set()
            return True

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_wrapper(
        self, run_id: str, request: StartRunRequest
    ) -> None:
        """Wrapper that calls _execute_run and cleans up afterwards."""
        try:
            self._execute_run(run_id, request)
        except Exception:
            logger.exception("Run %s failed", run_id)
        finally:
            with self._lock:
                self._active = None
                self._thread = None

    def _execute_run(
        self, run_id: str, request: StartRunRequest
    ) -> None:
        """Execute the evaluation run using the orchestrator.

        Loads tasks, variants, doc_tree from gold_standard fixtures,
        builds the orchestrator with the shared store/tracker, and runs.
        """
        from pathlib import Path

        from agent_evals.fixtures import load_sample_doc_tree
        from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig
        from agent_evals.runner import EvalRunConfig
        from agent_evals.tasks.loader import load_tasks
        from agent_evals.variants.registry import get_all_variants, load_all

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            logger.error("OPENROUTER_API_KEY not set, cannot start run %s", run_id)
            return

        # Load tasks from gold_standard
        gold_standard_dir = (
            Path(__file__).resolve().parent.parent.parent.parent / "gold_standard"
        )
        if not gold_standard_dir.is_dir():
            logger.error("Gold standard directory not found: %s", gold_standard_dir)
            return

        tasks = load_tasks(gold_standard_dir)

        # Apply task limit
        if request.task_limit > 0:
            tasks = tasks[: request.task_limit]

        if not tasks:
            logger.warning("No tasks loaded for run %s", run_id)
            return

        # Load variants
        load_all()
        variants = get_all_variants()

        if not variants:
            logger.warning("No variants loaded for run %s", run_id)
            return

        # Load doc_tree
        doc_tree = load_sample_doc_tree()

        # Parse models
        models = [m.strip() for m in request.model.split(",")]

        # Build eval config
        eval_config = EvalRunConfig(
            repetitions=request.repetitions,
            continue_on_error=True,
            temperature=0.3,
        )

        # Build orchestrator with shared store/tracker
        orch_config = OrchestratorConfig(
            mode=request.mode,
            models=models,
            api_key=api_key,
            temperature=0.3,
            eval_config=eval_config,
            store=self._store,
            tracker=self._tracker,
        )
        orchestrator = EvalOrchestrator(orch_config)

        # Route to appropriate runner
        if request.mode == "taguchi" and request.pipeline_mode:
            self._run_pipeline(
                orchestrator, request, tasks, variants, doc_tree, models, api_key
            )
        elif request.mode == "taguchi":
            self._run_taguchi(orchestrator, request, tasks, variants, doc_tree)
        else:
            orchestrator.run(
                tasks=tasks,
                variants=variants,
                doc_tree=doc_tree,
                source="gold_standard",
            )

        logger.info("Run %s completed", run_id)

    def _run_taguchi(
        self,
        orchestrator: Any,
        request: StartRunRequest,
        tasks: list,
        variants: list,
        doc_tree: Any,
    ) -> None:
        """Execute a Taguchi-mode run."""
        from agent_evals.taguchi.factors import build_design

        # Build axes from variants (exclude axis 0 baselines)
        axes: dict[int, list[str]] = {}
        for v in variants:
            m = v.metadata()
            if m.axis == 0:
                continue
            if m.axis not in axes:
                axes[m.axis] = []
            if m.name not in axes[m.axis]:
                axes[m.axis].append(m.name)

        models = orchestrator.config.models
        design = build_design(
            axes,
            models=models if len(models) > 1 else None,
            oa_override=request.oa_override,
        )

        variant_lookup = {v.metadata().name: v for v in variants}

        orchestrator.run(
            tasks=tasks,
            variants=variants,
            doc_tree=doc_tree,
            design=design,
            variant_lookup=variant_lookup,
            source="gold_standard",
        )

    def _run_pipeline(
        self,
        orchestrator: Any,
        request: StartRunRequest,
        tasks: list,
        variants: list,
        doc_tree: Any,
        models: list[str],
        api_key: str,
    ) -> None:
        """Execute a DOE pipeline run."""
        from agent_evals.pipeline import DOEPipeline, PipelineConfig

        pipeline_config = PipelineConfig(
            models=models,
            mode=request.pipeline_mode or "auto",
            quality_type=request.quality_type,
            alpha=request.alpha,
            top_k=request.top_k,
            oa_override=request.oa_override,
            api_key=api_key,
            temperature=0.3,
        )

        pipeline = DOEPipeline(config=pipeline_config, orchestrator=orchestrator)
        pipeline.run(tasks=tasks, variants=variants, doc_tree=doc_tree)
