"""Top-level orchestrator coordinating mode, runners, observatory, and reports.

Routes ``--mode`` to the correct runner (EvalRunner or TaguchiRunner), wires
up observatory telemetry, manages the client pool, and optionally starts
the web dashboard.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent_evals.llm.client_pool import LLMClientPool
from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker, TrackerEvent
from agent_evals.reports.aggregator import ReportData, aggregate
from agent_evals.runner import EvalRunConfig, EvalRunResult, EvalRunner, TrialResult

if TYPE_CHECKING:
    from agent_index.models import DocTree

    from agent_evals.taguchi.factors import TaguchiDesign
    from agent_evals.taguchi.runner import TaguchiRunResult
    from agent_evals.tasks.base import EvalTask
    from agent_evals.variants.base import IndexVariant

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorConfig:
    """Configuration for the evaluation orchestrator.

    Args:
        mode: Run mode -- ``"full"`` or ``"taguchi"``.
        models: List of model names to evaluate.
        api_key: API key for LLM access.
        db_path: Path to the observatory SQLite database.
        dashboard: Whether to start the web dashboard.
        dashboard_port: Port for the web dashboard.
        report_format: Report output format (``"html"``, ``"md"``, ``"both"``, or ``None``).
        global_budget: Global budget cap across all models.
        model_budgets: Per-model budget caps.
        temperature: LLM temperature.
        eval_config: Optional EvalRunConfig overrides for the runner.
    """

    models: list[str] = field(default_factory=list)
    api_key: str = ""
    db_path: Path | None = None
    mode: str = "full"
    dashboard: bool = False
    dashboard_port: int = 8501
    report_format: str | None = None
    global_budget: float | None = None
    model_budgets: dict[str, float] | None = None
    temperature: float = 0.3
    eval_config: EvalRunConfig | None = None


@dataclass
class OrchestratorResult:
    """Result returned by :meth:`EvalOrchestrator.run`.

    Attributes:
        run_id: Unique identifier for this run.
        mode: The mode that was used (``"full"`` or ``"taguchi"``).
        trials: All trial results from the run.
        total_cost: Sum of all trial costs.
        total_tokens: Sum of all trial token counts.
        elapsed_seconds: Wall-clock time for the run.
        report: Aggregated report data, if report generation was configured.
        raw_result: The underlying runner-specific result object.
    """

    run_id: str
    mode: str
    trials: list[TrialResult]
    total_cost: float
    total_tokens: int
    elapsed_seconds: float
    report: ReportData | None
    raw_result: EvalRunResult | Any


class EvalOrchestrator:
    """Coordinates evaluation runs across all subsystems.

    Responsibilities:

    1. Routes ``--mode`` to the correct runner (EvalRunner or TaguchiRunner).
    2. Wires observatory telemetry (EventTracker listeners) to the runner.
    3. Manages the client pool for multi-model runs.
    4. Optionally starts the web dashboard in a background thread.
    5. Generates aggregated reports after the run completes.

    Args:
        config: Orchestrator configuration.
    """

    def __init__(self, config: OrchestratorConfig) -> None:
        self.config = config

        # Initialize observatory.
        db_path = config.db_path or Path("observatory.db")
        self.store = ObservatoryStore(db_path)
        self.tracker = EventTracker(
            store=self.store,
            model_budgets=config.model_budgets,
        )

        # Initialize client pool.
        self.client_pool = LLMClientPool(
            models=config.models,
            api_key=config.api_key,
            temperature=config.temperature,
            global_budget=config.global_budget,
            model_budgets=config.model_budgets,
        )

        self._dashboard_thread: threading.Thread | None = None
        self._dashboard_shutdown: threading.Event = threading.Event()

    @property
    def runner_type(self) -> str:
        """Return the runner type based on configured mode."""
        if self.config.mode == "taguchi":
            return "taguchi"
        return "eval"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        tasks: list[EvalTask],
        variants: list[IndexVariant],
        doc_tree: DocTree,
        *,
        design: TaguchiDesign | None = None,
        variant_lookup: dict[str, IndexVariant] | None = None,
        source: str = "gold_standard",
    ) -> OrchestratorResult:
        """Execute a full evaluation run with telemetry and reporting.

        Determines the runner based on the configured mode, registers an
        EventTracker listener to record trial telemetry, runs the
        evaluation, and optionally aggregates results into a report.

        Parameters
        ----------
        tasks:
            Eval tasks to run.
        variants:
            Index variants to evaluate (used in ``"full"`` mode).
        doc_tree:
            Documentation tree for variant rendering.
        design:
            Taguchi experimental design (required for ``"taguchi"`` mode).
        variant_lookup:
            Mapping of variant name to IndexVariant (required for
            ``"taguchi"`` mode).
        source:
            Source tag for all resulting TrialResults.

        Returns
        -------
        OrchestratorResult
            Aggregated results with optional report data.

        Raises
        ------
        ValueError
            If mode is ``"taguchi"`` but *design* or *variant_lookup*
            is not provided.
        """
        run_id = uuid.uuid4().hex[:12]
        eval_config = self.config.eval_config or EvalRunConfig()

        # Create run record in the observatory store.
        self.store.create_run(
            run_id=run_id,
            run_type=self.config.mode,
            config={"mode": self.config.mode, "models": self.config.models},
        )

        # Wire up telemetry: bridge trial progress to the EventTracker.
        model_name = self.config.models[0] if self.config.models else "unknown"

        def _on_trial_progress(
            completed: int, total: int, trial: TrialResult
        ) -> None:
            self.tracker.record_trial(
                run_id=run_id,
                task_id=trial.task_id,
                task_type=trial.task_type,
                variant_name=trial.variant_name,
                repetition=trial.repetition,
                score=trial.score,
                prompt_tokens=trial.prompt_tokens,
                completion_tokens=trial.completion_tokens,
                total_tokens=trial.total_tokens,
                cost=trial.cost,
                latency_seconds=trial.latency_seconds,
                model=getattr(trial, "model", model_name),
                source=trial.source,
                error=trial.error,
            )

        # Route to the correct runner.
        if self.config.mode == "taguchi":
            raw_result = self._run_taguchi(
                tasks=tasks,
                doc_tree=doc_tree,
                eval_config=eval_config,
                design=design,
                variant_lookup=variant_lookup,
                progress_callback=_on_trial_progress,
                source=source,
            )
        else:
            raw_result = self._run_full(
                tasks=tasks,
                variants=variants,
                doc_tree=doc_tree,
                eval_config=eval_config,
                progress_callback=_on_trial_progress,
                source=source,
            )

        # Mark run as completed.
        self.store.finish_run(run_id)

        # Aggregate report if configured.
        report: ReportData | None = None
        if self.config.report_format is not None:
            report = aggregate(
                raw_result.trials,
                config=eval_config,
            )

        logger.info(
            "Run %s completed: %d trials, %.4f cost, %.1fs elapsed",
            run_id,
            len(raw_result.trials),
            raw_result.total_cost,
            raw_result.elapsed_seconds,
        )

        return OrchestratorResult(
            run_id=run_id,
            mode=self.config.mode,
            trials=raw_result.trials,
            total_cost=raw_result.total_cost,
            total_tokens=raw_result.total_tokens,
            elapsed_seconds=raw_result.elapsed_seconds,
            report=report,
            raw_result=raw_result,
        )

    def start_dashboard(self) -> threading.Thread | None:
        """Start the FastAPI web dashboard in a background thread.

        Only starts if ``config.dashboard`` is ``True``. Returns the
        background thread, or ``None`` if the dashboard is disabled.

        The dashboard is served via ``uvicorn`` on the configured port
        and can be stopped by calling :meth:`stop_dashboard`.
        """
        if not self.config.dashboard:
            return None

        from agent_evals.observatory.web.server import create_app

        app = create_app(store=self.store, tracker=self.tracker)
        self._dashboard_shutdown.clear()

        def _serve() -> None:
            try:
                import uvicorn

                config = uvicorn.Config(
                    app,
                    host="0.0.0.0",  # noqa: S104
                    port=self.config.dashboard_port,
                    log_level="warning",
                )
                server = uvicorn.Server(config)
                # Allow shutdown via event.
                self._uvicorn_server = server
                server.run()
            except Exception:
                logger.exception("Dashboard server failed")

        thread = threading.Thread(
            target=_serve, daemon=True, name="observatory-dashboard"
        )
        thread.start()
        self._dashboard_thread = thread
        logger.info(
            "Dashboard started on port %d", self.config.dashboard_port
        )
        return thread

    def stop_dashboard(self) -> None:
        """Signal the dashboard to shut down."""
        self._dashboard_shutdown.set()
        server = getattr(self, "_uvicorn_server", None)
        if server is not None:
            server.should_exit = True
        if self._dashboard_thread is not None:
            self._dashboard_thread.join(timeout=5.0)
            self._dashboard_thread = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_full(
        self,
        tasks: list[EvalTask],
        variants: list[IndexVariant],
        doc_tree: DocTree,
        eval_config: EvalRunConfig,
        progress_callback: Any,
        source: str,
    ) -> EvalRunResult:
        """Run a full-sweep evaluation via EvalRunner."""
        model_name = self.config.models[0] if self.config.models else "unknown"
        client = self.client_pool.get_client(model_name)

        runner = EvalRunner(client=client, config=eval_config)
        return runner.run(
            tasks=tasks,
            variants=variants,
            doc_tree=doc_tree,
            progress_callback=progress_callback,
            source=source,
        )

    def _run_taguchi(
        self,
        tasks: list[EvalTask],
        doc_tree: DocTree,
        eval_config: EvalRunConfig,
        design: TaguchiDesign | None,
        variant_lookup: dict[str, IndexVariant] | None,
        progress_callback: Any,
        source: str,
    ) -> Any:
        """Run a Taguchi-design evaluation via TaguchiRunner."""
        if design is None:
            msg = "TaguchiDesign is required for mode='taguchi'"
            raise ValueError(msg)
        if variant_lookup is None:
            msg = "variant_lookup is required for mode='taguchi'"
            raise ValueError(msg)

        from agent_evals.taguchi.runner import TaguchiRunner

        # Build client dict for all configured models.
        clients: dict[str, Any] = {}
        for model_name in self.config.models:
            clients[model_name] = self.client_pool.get_client(model_name)

        runner = TaguchiRunner(
            clients=clients,
            config=eval_config,
            design=design,
            variant_lookup=variant_lookup,
        )
        return runner.run(
            tasks=tasks,
            doc_tree=doc_tree,
            progress_callback=progress_callback,
            source=source,
        )
