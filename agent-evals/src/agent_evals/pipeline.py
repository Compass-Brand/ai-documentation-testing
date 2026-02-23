"""Multi-phase DOE pipeline data models and orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineConfig:
    """Configuration for a multi-phase DOE pipeline."""

    models: list[str]
    mode: str = "auto"
    quality_type: str = "larger_is_better"
    alpha: float = 0.05
    top_k: int = 3
    screening_reps: int = 3
    confirmation_reps: int = 5
    refinement_reps: int = 3
    oa_override: str | None = None
    report_format: str | None = None
    api_key: str = ""
    db_path: str | None = None
    dashboard: bool = False
    dashboard_port: int = 8501
    temperature: float = 0.3
    global_budget: float | None = None
    model_budgets: dict[str, float] | None = None


@dataclass
class PhaseResult:
    """Result from a single pipeline phase."""

    run_id: str
    phase: str
    trials: list[Any]
    total_cost: float = 0.0
    total_tokens: int = 0
    elapsed_seconds: float = 0.0
    main_effects: dict[str, Any] | None = None
    anova: dict[str, Any] | None = None
    optimal: dict[str, str] | None = None
    significant_factors: list[str] = field(default_factory=list)
    confirmation: dict[str, Any] | None = None


@dataclass
class PipelineResult:
    """Aggregated results across all pipeline phases."""

    pipeline_id: str
    screening: PhaseResult
    confirmation: PhaseResult | None = None
    refinement: PhaseResult | None = None
    final_optimal: dict[str, str] = field(default_factory=dict)
    total_trials: int = 0
    total_cost: float = 0.0
    elapsed_seconds: float = 0.0
