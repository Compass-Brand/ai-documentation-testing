"""Run lifecycle manager for dashboard-started evaluations.

Encapsulates starting, monitoring, and cancelling evaluation runs
initiated from the web UI. Uses the dashboard's shared store and
tracker so trials appear in the Live Monitor in real time.

Supports multiple concurrent runs.
"""

from __future__ import annotations

import logging
import os
import re
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


class RunSetupError(RuntimeError):
    """Raised when run setup fails; causes _run_wrapper to mark run as failed."""


_MODEL_PATTERN = re.compile(r"^[\w.-]+/[\w./-]+$")


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


def _validate_model_name(model: str) -> None:
    """Validate that model string follows LiteLLM provider/model format."""
    for m in (m.strip() for m in model.split(",")):
        if not _MODEL_PATTERN.match(m):
            raise ValueError(
                f"Invalid model name '{m}'. "
                "Expected LiteLLM format: 'provider/model' "
                "(e.g., 'openrouter/anthropic/claude-sonnet-4.5')."
            )


class HeartbeatThread(threading.Thread):
    """Periodically writes a heartbeat timestamp for a run."""

    def __init__(
        self, store: ObservatoryStore, run_id: str, interval: float = 30
    ) -> None:
        super().__init__(daemon=True, name=f"heartbeat-{run_id}")
        self._store = store
        self._run_id = run_id
        self._interval = interval
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.wait(self._interval):
            try:
                self._store.update_heartbeat(self._run_id)
            except Exception:
                pass

    def stop(self) -> None:
        self._stop_event.set()


class RunManager:
    """Manages background evaluation runs started from the dashboard.

    Supports multiple concurrent runs, each tracked independently.

    Args:
        store: The dashboard's shared ObservatoryStore.
        tracker: The dashboard's shared EventTracker.
    """

    def __init__(
        self, store: ObservatoryStore, tracker: EventTracker
    ) -> None:
        self._store = store
        self._tracker = tracker
        self._runs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    _PUBLIC_KEYS = ("run_id", "mode", "models", "started_at")

    def _public_info(self, info: dict[str, Any]) -> dict[str, Any]:
        """Return only serializable fields from a run info dict."""
        return {k: v for k, v in info.items() if k in self._PUBLIC_KEYS}

    @property
    def active_run(self) -> dict[str, Any] | None:
        """Return info about the first active run, or None."""
        with self._lock:
            if not self._runs:
                return None
            return self._public_info(next(iter(self._runs.values())))

    @property
    def active_runs(self) -> list[dict[str, Any]]:
        """Return info about all active runs."""
        with self._lock:
            return [self._public_info(r) for r in self._runs.values()]

    def start_run(self, request: StartRunRequest) -> str:
        """Start a background evaluation run.

        Returns the run_id. Multiple runs can execute concurrently.

        Raises:
            ValueError: If model name is invalid.
        """
        _validate_model_name(request.model)

        run_id = uuid.uuid4().hex[:12]
        models = [m.strip() for m in request.model.split(",")]
        cancel_event = threading.Event()

        run_info = {
            "run_id": run_id,
            "mode": request.mode,
            "models": models,
            "started_at": datetime.now(tz=timezone.utc).isoformat(),
            "cancel_event": cancel_event,
        }

        with self._lock:
            self._runs[run_id] = run_info

        thread = threading.Thread(
            target=self._run_wrapper,
            args=(run_id, request),
            daemon=True,
        )
        thread.start()

        return run_id

    def cancel_run(self, run_id: str | None = None) -> bool:
        """Request cancellation of a specific run, or all runs."""
        with self._lock:
            if not self._runs:
                return False
            if run_id is not None:
                run_info = self._runs.get(run_id)
                if run_info is None:
                    return False
                run_info["cancel_event"].set()
                return True
            for info in self._runs.values():
                info["cancel_event"].set()
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
        except Exception as exc:
            logger.error("Run %s failed: %s", run_id, exc, exc_info=True)
            try:
                self._store.fail_run(run_id, error=str(exc))
            except Exception:
                logger.exception(
                    "Failed to update DB status for run %s", run_id
                )
        finally:
            with self._lock:
                self._runs.pop(run_id, None)

    def _execute_run(
        self, run_id: str, request: StartRunRequest
    ) -> None:
        """Execute the evaluation run using the orchestrator."""
        from pathlib import Path

        from agent_evals.fixtures import load_sample_doc_tree
        from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig
        from agent_evals.runner import EvalRunConfig
        from agent_evals.tasks.loader import load_tasks
        from agent_evals.variants.registry import get_all_variants, load_all

        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            raise RunSetupError("OPENROUTER_API_KEY not set")

        gold_standard_dir = (
            Path(__file__).resolve().parent.parent.parent.parent / "gold_standard"
        )
        if not gold_standard_dir.is_dir():
            raise RunSetupError(
                f"gold_standard directory not found: {gold_standard_dir}"
            )

        tasks = load_tasks(gold_standard_dir)
        if request.task_limit > 0:
            tasks = tasks[: request.task_limit]
        if not tasks:
            raise RunSetupError("no tasks loaded from gold_standard")

        load_all()
        variants = get_all_variants()
        if not variants:
            raise RunSetupError("no variants configured")

        doc_tree = load_sample_doc_tree()
        models = [m.strip() for m in request.model.split(",")]

        eval_config = EvalRunConfig(
            repetitions=request.repetitions,
            continue_on_error=True,
            temperature=0.3,
        )

        orch_config = OrchestratorConfig(
            mode=request.mode,
            models=models,
            api_key=api_key,
            temperature=0.3,
            eval_config=eval_config,
            store=self._store,
            tracker=self._tracker,
            run_id=run_id,
        )
        orchestrator = EvalOrchestrator(orch_config)

        heartbeat = HeartbeatThread(self._store, run_id)
        heartbeat.start()
        try:
            if request.mode == "taguchi" and request.pipeline_mode:
                self._run_pipeline(
                    orchestrator, request, tasks, variants, doc_tree,
                    models, api_key,
                )
            elif request.mode == "taguchi":
                self._run_taguchi(
                    orchestrator, request, tasks, variants, doc_tree,
                )
            else:
                orchestrator.run(
                    tasks=tasks, variants=variants, doc_tree=doc_tree,
                    source="gold_standard",
                )
        finally:
            heartbeat.stop()
            heartbeat.join(timeout=5.0)

        logger.info("Run %s completed", run_id)

    def _run_taguchi(
        self, orchestrator: Any, request: StartRunRequest,
        tasks: list, variants: list, doc_tree: Any,
    ) -> None:
        """Execute a Taguchi-mode run."""
        from agent_evals.taguchi.factors import build_design

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
            tasks=tasks, variants=variants, doc_tree=doc_tree,
            design=design, variant_lookup=variant_lookup,
            source="gold_standard",
        )

    def _run_pipeline(
        self, orchestrator: Any, request: StartRunRequest,
        tasks: list, variants: list, doc_tree: Any,
        models: list[str], api_key: str,
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
