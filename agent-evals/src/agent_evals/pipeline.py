"""Multi-phase DOE pipeline data models and orchestration."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from agent_evals.taguchi.analysis import (
    compute_main_effects,
    compute_sn_ratios,
    predict_optimal,
    run_anova,
    validate_confirmation,
)
from agent_evals.taguchi.factors import build_design

if TYPE_CHECKING:
    from agent_evals.orchestrator import EvalOrchestrator


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


class DOEPipeline:
    """Multi-phase DOE pipeline orchestrator.

    Coordinates screening, confirmation, and refinement phases
    using Taguchi experimental design methodology.
    """

    def __init__(
        self,
        config: PipelineConfig,
        orchestrator: EvalOrchestrator,
    ) -> None:
        self.config = config
        self._orchestrator = orchestrator
        self._pipeline_id = uuid4().hex[:12]

    def run_screening(
        self,
        tasks: list[Any],
        variants: list[Any],
        doc_tree: Any,
    ) -> PhaseResult:
        """Execute Phase 1: screening experiment.

        Builds a Taguchi design from variant axes, runs trials via
        the orchestrator, then computes S/N ratios, main effects,
        ANOVA, and optimal prediction.
        """
        # 1. Build axes dict from variants
        axes: dict[int, list[str]] = defaultdict(list)
        for v in variants:
            meta = v.metadata()
            if meta.name not in axes[meta.axis]:
                axes[meta.axis].append(meta.name)

        # 2. Build the Taguchi experimental design
        design = build_design(
            dict(axes), self.config.models, self.config.oa_override
        )

        # 3. Build variant lookup
        variant_lookup = {v.metadata().name: v for v in variants}

        # 4. Run trials via orchestrator
        result = self._orchestrator.run(
            tasks,
            variants,
            doc_tree,
            design=design,
            variant_lookup=variant_lookup,
            phase="screening",
            pipeline_id=self._pipeline_id,
        )

        # 5. Group trial scores by OA row
        row_scores: dict[int, list[float]] = defaultdict(list)
        for trial in result.trials:
            row_id = trial.metrics["oa_row_id"]
            row_scores[row_id].append(trial.score)

        # 6-9. Statistical analysis
        sn_ratios = compute_sn_ratios(
            dict(row_scores), self.config.quality_type
        )
        main_effects = compute_main_effects(design, sn_ratios)
        anova = run_anova(design, sn_ratios)
        optimal = predict_optimal(main_effects, sn_ratios)

        # 10. Extract significant factors (p < alpha), sorted by omega_squared
        sig_factors = sorted(
            (f for f in anova.factors if f.p_value < self.config.alpha),
            key=lambda f: f.omega_squared,
            reverse=True,
        )

        return PhaseResult(
            run_id=result.run_id,
            phase="screening",
            trials=result.trials,
            total_cost=result.total_cost,
            total_tokens=result.total_tokens,
            elapsed_seconds=result.elapsed_seconds,
            main_effects=main_effects,
            anova=anova,
            optimal=optimal.optimal_assignment,
            significant_factors=[f.factor_name for f in sig_factors],
        )

    def run_confirmation(
        self,
        screening_result: PhaseResult,
        tasks: list[Any],
        variants: list[Any],
        doc_tree: Any,
    ) -> PhaseResult:
        """Execute Phase 2: confirmation experiment.

        Runs the predicted optimal config from Phase 1 against all tasks,
        then validates that observed performance falls within the prediction
        interval.
        """
        # Build variant lookup
        variant_lookup = {v.metadata().name: v for v in variants}

        # Run optimal config trials via orchestrator (full mode, not Taguchi)
        result = self._orchestrator.run(
            tasks,
            variants,
            doc_tree,
            variant_lookup=variant_lookup,
            phase="confirmation",
            pipeline_id=self._pipeline_id,
        )

        # Gather observed scores
        optimal_scores = [t.score for t in result.trials]

        # Build an OptimalPrediction from screening results for validation
        from agent_evals.taguchi.analysis import OptimalPrediction

        prediction = OptimalPrediction(
            optimal_assignment=screening_result.optimal or {},
            predicted_sn=0.0,
        )

        # Validate observed against prediction
        conf_result = validate_confirmation(
            prediction, optimal_scores, self.config.quality_type
        )

        return PhaseResult(
            run_id=result.run_id,
            phase="confirmation",
            trials=result.trials,
            total_cost=result.total_cost,
            total_tokens=result.total_tokens,
            elapsed_seconds=result.elapsed_seconds,
            confirmation={
                "within_interval": conf_result.within_interval,
                "sigma_deviation": conf_result.sigma_deviation,
                "observed_sn": conf_result.observed_sn,
                "predicted_sn": conf_result.predicted_sn,
                "prediction_interval": conf_result.prediction_interval,
            },
        )

    def run_refinement(
        self,
        screening_result: PhaseResult,
        tasks: list[Any],
        variants: list[Any],
        doc_tree: Any,
    ) -> PhaseResult:
        """Execute Phase 3: full factorial refinement on top K factors.

        Builds all combinations of the top K significant factors while
        fixing remaining factors at their optimal levels.
        """
        # Build variant lookup
        variant_lookup = {v.metadata().name: v for v in variants}

        # Select top K significant factors
        top_factors = screening_result.significant_factors[: self.config.top_k]

        # Build full factorial design for top K factors
        # Collect level names from main_effects for each top factor
        axes: dict[int, list[str]] = {}
        main_eff = screening_result.main_effects or {}
        for i, fname in enumerate(top_factors):
            if fname in main_eff:
                axes[i + 1] = list(main_eff[fname].keys())

        if axes:
            from itertools import product as iter_product

            # Build full factorial combos
            factor_names = list(axes.keys())
            level_lists = [axes[k] for k in factor_names]
            combos = list(iter_product(*level_lists))

            # Run trials via orchestrator
            result = self._orchestrator.run(
                tasks,
                variants,
                doc_tree,
                variant_lookup=variant_lookup,
                phase="refinement",
                pipeline_id=self._pipeline_id,
            )
        else:
            result = self._orchestrator.run(
                tasks,
                variants,
                doc_tree,
                variant_lookup=variant_lookup,
                phase="refinement",
                pipeline_id=self._pipeline_id,
            )

        return PhaseResult(
            run_id=result.run_id,
            phase="refinement",
            trials=result.trials,
            total_cost=result.total_cost,
            total_tokens=result.total_tokens,
            elapsed_seconds=result.elapsed_seconds,
        )

    def run(
        self,
        tasks: list[Any],
        variants: list[Any],
        doc_tree: Any,
        *,
        phase_callback: Any | None = None,
    ) -> PipelineResult:
        """Execute complete DOE pipeline: screen -> confirm -> refine.

        In auto mode, runs all phases sequentially. In semi mode, calls
        phase_callback after each phase. If callback returns False, stops.
        """
        # Phase 1: Screening
        screening = self.run_screening(tasks, variants, doc_tree)

        # Semi mode: check callback after screening
        if self.config.mode == "semi" and phase_callback is not None:
            if not phase_callback(screening):
                return PipelineResult(
                    pipeline_id=self._pipeline_id,
                    screening=screening,
                    total_trials=len(screening.trials),
                    total_cost=screening.total_cost,
                    elapsed_seconds=screening.elapsed_seconds,
                )

        # Phase 2: Confirmation
        confirmation = self.run_confirmation(
            screening, tasks, variants, doc_tree
        )

        # Semi mode: check callback after confirmation
        if self.config.mode == "semi" and phase_callback is not None:
            if not phase_callback(confirmation):
                return PipelineResult(
                    pipeline_id=self._pipeline_id,
                    screening=screening,
                    confirmation=confirmation,
                    total_trials=len(screening.trials) + len(confirmation.trials),
                    total_cost=screening.total_cost + confirmation.total_cost,
                    elapsed_seconds=screening.elapsed_seconds + confirmation.elapsed_seconds,
                )

        # Phase 3: Refinement
        refinement = self.run_refinement(
            screening, tasks, variants, doc_tree
        )

        # Aggregate final results
        final_optimal = refinement.optimal or screening.optimal or {}
        total_trials = (
            len(screening.trials)
            + len(confirmation.trials)
            + len(refinement.trials)
        )
        total_cost = (
            screening.total_cost + confirmation.total_cost + refinement.total_cost
        )
        elapsed = (
            screening.elapsed_seconds
            + confirmation.elapsed_seconds
            + refinement.elapsed_seconds
        )

        return PipelineResult(
            pipeline_id=self._pipeline_id,
            screening=screening,
            confirmation=confirmation,
            refinement=refinement,
            final_optimal=final_optimal,
            total_trials=total_trials,
            total_cost=total_cost,
            elapsed_seconds=elapsed,
        )
