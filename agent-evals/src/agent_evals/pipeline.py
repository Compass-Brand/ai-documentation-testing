"""Multi-phase DOE pipeline data models and orchestration."""

from __future__ import annotations

import copy
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field, fields
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from agent_evals.context.base import StrategyConfig
from agent_evals.taguchi.analysis import (
    compute_interactions,
    compute_main_effects,
    compute_sn_ratios,
    predict_optimal,
    run_anova,
    validate_confirmation,
)
from agent_evals.taguchi.factors import build_design

if TYPE_CHECKING:
    from agent_evals.orchestrator import EvalOrchestrator

logger = logging.getLogger(__name__)


def _to_dict(obj: Any) -> Any:
    """Convert a dataclass instance to a dict, or return the object as-is."""
    if obj is None:
        return {}
    try:
        fields(obj)  # raises TypeError if not a dataclass instance
        return asdict(obj)
    except TypeError:
        return obj


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
    strategy_config: StrategyConfig = field(default_factory=StrategyConfig)
    strategy_reps: dict[str, int] = field(default_factory=dict)


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
    predicted_sn: float | None = None
    prediction_interval: tuple[float, float] | list[float] | None = None
    se_prediction: float | None = None
    confirmation: dict[str, Any] | None = None
    interaction_effects: list[dict] = field(default_factory=list)


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
        pipeline_id: str | None = None,
    ) -> None:
        self.config = config
        self._orchestrator = orchestrator
        self._pipeline_id = pipeline_id or uuid4().hex[:12]
        self._store = orchestrator.store

    @staticmethod
    def _group_refinement_scores(
        trials: list[Any],
        design: Any,
    ) -> dict[int, list[float]]:
        """Group full-mode trial scores into design-row buckets.

        In refinement, trials run in full mode (one variant per trial).
        Each design row assigns a level per factor; we match a trial's
        ``variant_name`` to any row that includes it, then collect
        scores per row.  Trials matching no row are skipped.
        """
        name_to_rows: dict[str, set[int]] = defaultdict(set)
        for row in design.rows:
            for level_name in row.assignments.values():
                name_to_rows[level_name].add(row.run_id)

        row_scores: dict[int, list[float]] = defaultdict(list)
        for trial in trials:
            vname = trial.variant_name
            for rid in name_to_rows.get(vname, set()):
                row_scores[rid].append(trial.score)

        return dict(row_scores)

    def _analyse_refinement(
        self,
        filtered_variants: list[Any],
        trials: list[Any],
    ) -> dict[str, Any]:
        """Run the statistical analysis pipeline on refinement trials.

        Mirrors screening: builds a Taguchi design from filtered axes,
        groups scores into rows, computes S/N, main effects, ANOVA,
        and optimal prediction.
        """
        axes: dict[int, list[str]] = defaultdict(list)
        for v in filtered_variants:
            meta = v.metadata()
            if meta.name not in axes[meta.axis]:
                axes[meta.axis].append(meta.name)

        design = build_design(
            dict(axes), self.config.models, self.config.oa_override,
        )
        row_scores = self._group_refinement_scores(trials, design)
        sn_ratios = compute_sn_ratios(
            row_scores, self.config.quality_type,
        )
        main_effects = compute_main_effects(design, sn_ratios)
        anova = run_anova(design, sn_ratios)
        optimal = predict_optimal(
            main_effects, sn_ratios,
            design=design, anova_result=anova,
        )
        sig_factors = sorted(
            (
                f for f in anova.factors
                if f.corrected_p_value < self.config.alpha
            ),
            key=lambda f: f.omega_squared,
            reverse=True,
        )

        # Compute 2-way interaction effects from the full factorial data
        # Only include rows that have S/N data (some may be missing)
        design_rows = [
            row.assignments for row in design.rows
            if row.run_id in sn_ratios
        ]
        sn_list = [
            sn_ratios[row.run_id] for row in design.rows
            if row.run_id in sn_ratios
        ]
        interactions = compute_interactions(design_rows, sn_list)

        return {
            "main_effects": main_effects,
            "anova": anova,
            "optimal": optimal.optimal_assignment,
            "predicted_sn": optimal.predicted_sn,
            "significant_factors": [
                f.factor_name for f in sig_factors
            ],
            "interaction_effects": [
                asdict(ie) for ie in interactions
            ],
        }

    @staticmethod
    def _resolve_factor_axes(
        variants: list[Any],
        factor_names: list[str],
    ) -> set[int]:
        """Map Taguchi factor names back to variant axis numbers.

        Factor names follow the convention ``axis_{N}`` where *N* is
        the integer axis number from variant metadata.  Returns the
        set of axis ints that correspond to *factor_names*.
        """
        axes: set[int] = set()
        for name in factor_names:
            if name.startswith("axis_"):
                try:
                    axes.add(int(name.split("_", 1)[1]))
                except ValueError:
                    pass
        return axes

    def run_screening(
        self,
        tasks: list[Any],
        variants: list[Any],
        doc_tree: Any,
        *,
        resume_run_id: str | None = None,
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

        # 1b. Validate axes — Taguchi needs >= 2 axes with >= 2 levels each
        usable_axes = {
            k: v for k, v in axes.items() if k != 0 and len(v) >= 2
        }
        if len(usable_axes) < 2:
            raise ValueError(
                f"Taguchi design requires at least 2 axes with 2+ levels "
                f"each (excluding axis 0 baselines). Got {len(usable_axes)} "
                f"usable axes from {len(variants)} variant(s)."
            )

        # 1c. Apply phase-specific repetition count
        if self._orchestrator.config.eval_config is not None:
            self._orchestrator.config.eval_config.repetitions = (
                self.config.screening_reps
            )

        # 2. Build the Taguchi experimental design (axis 0 baselines excluded)
        design = build_design(
            dict(usable_axes), self.config.models, self.config.oa_override
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
            resume_run_id=resume_run_id,
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
        optimal = predict_optimal(
            main_effects, sn_ratios, design=design, anova_result=anova,
        )

        # 10. Extract significant factors (BH-corrected p < alpha), sorted by omega_squared
        sig_factors = sorted(
            (f for f in anova.factors if f.corrected_p_value < self.config.alpha),
            key=lambda f: f.omega_squared,
            reverse=True,
        )

        phase_result = PhaseResult(
            run_id=result.run_id,
            phase="screening",
            trials=result.trials,
            total_cost=result.total_cost,
            total_tokens=result.total_tokens,
            elapsed_seconds=result.elapsed_seconds,
            main_effects=main_effects,
            anova=anova,
            optimal=optimal.optimal_assignment,
            predicted_sn=optimal.predicted_sn,
            prediction_interval=optimal.prediction_interval,
            se_prediction=optimal.se_prediction,
            significant_factors=[f.factor_name for f in sig_factors],
        )

        if self._store is not None:
            self._store.save_phase_results(
                run_id=phase_result.run_id,
                main_effects=_to_dict(phase_result.main_effects),
                anova=_to_dict(phase_result.anova),
                optimal=_to_dict(phase_result.optimal),
                significant_factors=phase_result.significant_factors,
                quality_type=self.config.quality_type,
                total_cost=phase_result.total_cost,
                total_tokens=phase_result.total_tokens,
                elapsed_seconds=phase_result.elapsed_seconds,
                predicted_sn=phase_result.predicted_sn,
                prediction_interval=phase_result.prediction_interval,
                se_prediction=phase_result.se_prediction,
            )

        return phase_result

    def run_confirmation(
        self,
        screening_result: PhaseResult,
        tasks: list[Any],
        variants: list[Any],
        doc_tree: Any,
        *,
        resume_run_id: str | None = None,
    ) -> PhaseResult:
        """Execute Phase 2: confirmation experiment.

        Runs the predicted optimal config from Phase 1 against all tasks,
        then validates that observed performance falls within the prediction
        interval.
        """
        # Apply phase-specific repetition count
        if self._orchestrator.config.eval_config is not None:
            self._orchestrator.config.eval_config.repetitions = (
                self.config.confirmation_reps
            )

        # Filter variants to only the optimal config from screening
        optimal_names = set(
            (screening_result.optimal or {}).values()
        )
        filtered_variants = [
            v for v in variants if v.metadata().name in optimal_names
        ]
        if not filtered_variants:
            logger.warning(
                "No variants matched optimal config %s; using all",
                screening_result.optimal,
            )
            filtered_variants = variants

        # Build variant lookup from filtered set
        variant_lookup = {
            v.metadata().name: v for v in filtered_variants
        }

        # Run optimal config trials via orchestrator (full mode, not Taguchi)
        result = self._orchestrator.run(
            tasks,
            filtered_variants,
            doc_tree,
            variant_lookup=variant_lookup,
            phase="confirmation",
            pipeline_id=self._pipeline_id,
            mode="full",
            resume_run_id=resume_run_id,
        )

        # Gather observed scores
        optimal_scores = [t.score for t in result.trials]

        # Build an OptimalPrediction from screening results for validation
        from agent_evals.taguchi.analysis import OptimalPrediction

        # Reconstruct prediction_interval as tuple if stored as list
        pi = screening_result.prediction_interval
        if isinstance(pi, list) and len(pi) == 2:
            pi = (pi[0], pi[1])

        prediction = OptimalPrediction(
            optimal_assignment=screening_result.optimal or {},
            predicted_sn=screening_result.predicted_sn or 0.0,
            prediction_interval=pi,
            se_prediction=screening_result.se_prediction,
        )

        # Validate observed against prediction
        conf_result = validate_confirmation(
            prediction, optimal_scores, self.config.quality_type
        )

        phase_result = PhaseResult(
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

        if self._store is not None:
            self._store.save_phase_results(
                run_id=phase_result.run_id,
                main_effects=_to_dict(phase_result.main_effects),
                anova=_to_dict(phase_result.anova),
                optimal=_to_dict(phase_result.optimal),
                significant_factors=phase_result.significant_factors,
                quality_type=self.config.quality_type,
                total_cost=phase_result.total_cost,
                total_tokens=phase_result.total_tokens,
                elapsed_seconds=phase_result.elapsed_seconds,
            )

        return phase_result

    def run_refinement(
        self,
        screening_result: PhaseResult,
        tasks: list[Any],
        variants: list[Any],
        doc_tree: Any,
        *,
        resume_run_id: str | None = None,
    ) -> PhaseResult:
        """Execute Phase 3: full factorial refinement on top K factors.

        Builds all combinations of the top K significant factors while
        fixing remaining factors at their optimal levels, then runs
        the same analysis pipeline as screening.
        """
        # Apply phase-specific repetition count
        if self._orchestrator.config.eval_config is not None:
            self._orchestrator.config.eval_config.repetitions = (
                self.config.refinement_reps
            )

        # Filter variants to top-K significant factors from screening
        top_k_factors = (
            screening_result.significant_factors[: self.config.top_k]
        )
        top_k_axes = self._resolve_factor_axes(variants, top_k_factors)
        filtered_variants = [
            v for v in variants if v.metadata().axis in top_k_axes
        ]
        if not filtered_variants:
            logger.warning(
                "No variants matched top-K factors %s; using all",
                top_k_factors,
            )
            filtered_variants = variants

        # Build variant lookup from filtered set
        variant_lookup = {
            v.metadata().name: v for v in filtered_variants
        }

        # Run trials via orchestrator (full mode, not Taguchi)
        result = self._orchestrator.run(
            tasks,
            filtered_variants,
            doc_tree,
            variant_lookup=variant_lookup,
            phase="refinement",
            pipeline_id=self._pipeline_id,
            mode="full",
            resume_run_id=resume_run_id,
        )

        # Analyse refinement trials (mirrors screening analysis)
        analysis = self._analyse_refinement(
            filtered_variants, result.trials,
        )

        phase_result = PhaseResult(
            run_id=result.run_id,
            phase="refinement",
            trials=result.trials,
            total_cost=result.total_cost,
            total_tokens=result.total_tokens,
            elapsed_seconds=result.elapsed_seconds,
            main_effects=analysis["main_effects"],
            anova=analysis["anova"],
            optimal=analysis["optimal"],
            predicted_sn=analysis["predicted_sn"],
            significant_factors=analysis["significant_factors"],
            interaction_effects=analysis.get("interaction_effects", []),
        )

        if self._store is not None:
            self._store.save_phase_results(
                run_id=phase_result.run_id,
                main_effects=_to_dict(phase_result.main_effects),
                anova=_to_dict(phase_result.anova),
                optimal=_to_dict(phase_result.optimal),
                significant_factors=phase_result.significant_factors,
                quality_type=self.config.quality_type,
                total_cost=phase_result.total_cost,
                total_tokens=phase_result.total_tokens,
                elapsed_seconds=phase_result.elapsed_seconds,
                interaction_effects=phase_result.interaction_effects,
            )

        return phase_result

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

        When resuming (pipeline_id passed to __init__), completed phases
        are skipped and in-progress phases are resumed from their checkpoint.
        """
        # Check for completed and in-progress phases when resuming.
        completed_phases: dict[str, str] = {}  # phase -> run_id
        in_progress_phases: dict[str, str] = {}  # phase -> run_id
        if self._store:
            existing_runs = self._store.get_pipeline_runs(self._pipeline_id)
            for run in existing_runs:
                if run.status == "completed" and run.phase:
                    completed_phases[run.phase] = run.run_id
                elif run.status in ("active", "failed") and run.phase:
                    in_progress_phases[run.phase] = run.run_id

        # Phase 1: Screening
        if "screening" in completed_phases:
            # Reconstruct PhaseResult from DB, including cost/token aggregates.
            screen_run_id = completed_phases["screening"]
            phase_results = self._store.get_phase_results(screen_run_id)
            screening = PhaseResult(
                run_id=screen_run_id,
                phase="screening",
                trials=[],  # Don't reload all trials for skipped phases
                main_effects=phase_results.get("main_effects") if phase_results else None,
                anova=phase_results.get("anova") if phase_results else None,
                optimal=phase_results.get("optimal") if phase_results else None,
                significant_factors=phase_results.get("significant_factors", []) if phase_results else [],
                total_cost=phase_results.get("total_cost", 0.0) if phase_results else 0.0,
                total_tokens=phase_results.get("total_tokens", 0) if phase_results else 0,
                elapsed_seconds=phase_results.get("elapsed_seconds", 0.0) if phase_results else 0.0,
                predicted_sn=phase_results.get("predicted_sn") if phase_results else None,
                prediction_interval=phase_results.get("prediction_interval") if phase_results else None,
                se_prediction=phase_results.get("se_prediction") if phase_results else None,
            )
        elif "screening" in in_progress_phases:
            screening = self.run_screening(
                tasks, variants, doc_tree,
                resume_run_id=in_progress_phases["screening"],
            )
        else:
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
        if "confirmation" in completed_phases:
            conf_run_id = completed_phases["confirmation"]
            conf_phase_results = self._store.get_phase_results(conf_run_id)
            confirmation = PhaseResult(
                run_id=conf_run_id,
                phase="confirmation",
                trials=[],
                total_cost=conf_phase_results.get("total_cost", 0.0) if conf_phase_results else 0.0,
                total_tokens=conf_phase_results.get("total_tokens", 0) if conf_phase_results else 0,
                elapsed_seconds=conf_phase_results.get("elapsed_seconds", 0.0) if conf_phase_results else 0.0,
            )
        elif "confirmation" in in_progress_phases:
            confirmation = self.run_confirmation(
                screening, tasks, variants, doc_tree,
                resume_run_id=in_progress_phases["confirmation"],
            )
        else:
            confirmation = self.run_confirmation(
                screening, tasks, variants, doc_tree,
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
        if "refinement" in completed_phases:
            ref_run_id = completed_phases["refinement"]
            ref_phase_results = self._store.get_phase_results(ref_run_id)
            refinement = PhaseResult(
                run_id=ref_run_id,
                phase="refinement",
                trials=[],
                main_effects=ref_phase_results.get("main_effects") if ref_phase_results else None,
                anova=ref_phase_results.get("anova") if ref_phase_results else None,
                optimal=ref_phase_results.get("optimal") if ref_phase_results else None,
                significant_factors=ref_phase_results.get("significant_factors", []) if ref_phase_results else [],
                total_cost=ref_phase_results.get("total_cost", 0.0) if ref_phase_results else 0.0,
                total_tokens=ref_phase_results.get("total_tokens", 0) if ref_phase_results else 0,
                elapsed_seconds=ref_phase_results.get("elapsed_seconds", 0.0) if ref_phase_results else 0.0,
                interaction_effects=ref_phase_results.get("interaction_effects", []) if ref_phase_results else [],
            )
        elif "refinement" in in_progress_phases:
            refinement = self.run_refinement(
                screening, tasks, variants, doc_tree,
                resume_run_id=in_progress_phases["refinement"],
            )
        else:
            refinement = self.run_refinement(
                screening, tasks, variants, doc_tree,
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


@dataclass
class MultiStrategyResult:
    """Aggregated results across multiple context strategies."""

    pipeline_id: str
    strategy_results: dict[str, PipelineResult] = field(default_factory=dict)
    total_cost: float = 0.0
    total_trials: int = 0
    elapsed_seconds: float = 0.0


class MultiStrategyPipeline:
    """Runs independent DOEPipeline per context strategy.

    Deep-copies PipelineConfig per strategy to avoid shared-state
    mutation. Overrides per-strategy repetition counts from
    ``strategy_reps``. Each strategy gets a distinct pipeline_id.
    """

    def __init__(
        self,
        config: PipelineConfig,
        orchestrator: EvalOrchestrator,
        strategies: list[str],
        pipeline_id: str | None = None,
    ) -> None:
        self.config = config
        self._orchestrator = orchestrator
        self.strategies = strategies
        self._pipeline_id = pipeline_id or uuid4().hex[:12]
        self._completed_strategies: dict[str, PipelineResult] = {}

    def _build_pipeline_ids(self) -> dict[str, str]:
        """Build strategy-specific pipeline IDs."""
        return {
            name: f"{self._pipeline_id}__{name}"
            for name in self.strategies
        }

    def _build_strategy_configs(self) -> dict[str, PipelineConfig]:
        """Deep-copy PipelineConfig per strategy with rep overrides."""
        configs: dict[str, PipelineConfig] = {}
        for name in self.strategies:
            cfg = copy.deepcopy(self.config)
            cfg.strategy_config = StrategyConfig(
                strategy=name,
                token_budget=self.config.strategy_config.token_budget,
                truncation=self.config.strategy_config.truncation,
                chunk_method=self.config.strategy_config.chunk_method,
                rag_top_k=self.config.strategy_config.rag_top_k,
                embedding_model=self.config.strategy_config.embedding_model,
                max_turns=self.config.strategy_config.max_turns,
            )
            # Override reps from strategy_reps mapping
            if name in self.config.strategy_reps:
                cfg.screening_reps = self.config.strategy_reps[name]
                cfg.confirmation_reps = cfg.screening_reps + 2
            configs[name] = cfg
        return configs

    def run(
        self,
        tasks: list[Any],
        variants: list[Any],
        doc_tree: Any,
        *,
        phase_callback: Any | None = None,
    ) -> MultiStrategyResult:
        """Execute DOEPipeline per strategy, collecting results."""
        pipeline_ids = self._build_pipeline_ids()
        configs = self._build_strategy_configs()
        results: dict[str, PipelineResult] = dict(self._completed_strategies)
        total_cost = sum(r.total_cost for r in results.values())
        total_trials = sum(r.total_trials for r in results.values())
        elapsed = sum(r.elapsed_seconds for r in results.values())

        for name in self.strategies:
            if name in results:
                logger.info("Strategy %s already completed, skipping", name)
                continue

            logger.info("Running DOEPipeline for strategy: %s", name)
            # Update orchestrator's strategy_config for this strategy
            self._orchestrator.config.strategy_config = configs[name].strategy_config

            pipeline = DOEPipeline(
                config=configs[name],
                orchestrator=self._orchestrator,
                pipeline_id=pipeline_ids[name],
            )
            result = pipeline.run(
                tasks=tasks,
                variants=variants,
                doc_tree=doc_tree,
                phase_callback=phase_callback,
            )
            results[name] = result
            self._completed_strategies[name] = result
            total_cost += result.total_cost
            total_trials += result.total_trials
            elapsed += result.elapsed_seconds

        return MultiStrategyResult(
            pipeline_id=self._pipeline_id,
            strategy_results=results,
            total_cost=total_cost,
            total_trials=total_trials,
            elapsed_seconds=elapsed,
        )
