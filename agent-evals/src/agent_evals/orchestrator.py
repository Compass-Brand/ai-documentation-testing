"""Top-level orchestrator coordinating mode, runners, observatory, and reports.

Routes ``--mode`` to the correct runner (EvalRunner or TaguchiRunner), wires
up observatory telemetry, manages the client pool, and optionally starts
the web dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agent_evals.llm.client_pool import LLMClientPool
from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker


@dataclass
class OrchestratorConfig:
    """Configuration for the evaluation orchestrator.

    Args:
        mode: Run mode -- ``"full"`` or ``"taguchi"``.
        models: List of model names to evaluate.
        api_key: API key for LLM access.
        db_path: Path to the observatory SQLite database.
        dashboard: Whether to start the web dashboard.
        report_format: Report output format (``"html"``, ``"md"``, ``"both"``, or ``None``).
        global_budget: Global budget cap across all models.
        model_budgets: Per-model budget caps.
        temperature: LLM temperature.
    """

    models: list[str] = field(default_factory=list)
    api_key: str = ""
    db_path: Path | None = None
    mode: str = "full"
    dashboard: bool = False
    report_format: str | None = None
    global_budget: float | None = None
    model_budgets: dict[str, float] | None = None
    temperature: float = 0.3


class EvalOrchestrator:
    """Coordinates evaluation runs across all subsystems.

    Args:
        config: Orchestrator configuration.
    """

    def __init__(self, config: OrchestratorConfig) -> None:
        self.config = config

        # Initialize observatory.
        db_path = config.db_path or Path("observatory.db")
        self.store = ObservatoryStore(db_path)
        self.tracker = EventTracker(store=self.store)

        # Initialize client pool.
        self.client_pool = LLMClientPool(
            models=config.models,
            api_key=config.api_key,
            temperature=config.temperature,
            global_budget=config.global_budget,
            model_budgets=config.model_budgets,
        )

    @property
    def runner_type(self) -> str:
        """Return the runner type based on configured mode."""
        if self.config.mode == "taguchi":
            return "taguchi"
        return "eval"
