"""Multi-phase DOE pipeline data models and orchestration."""

from __future__ import annotations

import copy
import logging
import sqlite3
from collections import defaultdict
from dataclasses import asdict, dataclass, field, fields
from itertools import product as itertools_product
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from agent_evals.context.base import StrategyConfig
from agent_evals.taguchi.analysis import (
    compute_interactions,
    compute_main_effects,
    compute_sn_ratios,
    predict_optimal,
    rank_factors_by_effect_range,
    run_anova,
    validate_confirmation,
)
from agent_evals.taguchi.factors import build_design, build_factorial_design
from agent_evals.taguchi.multi_objective import run_multi_objective_analysis
from agent_evals.variants.composite import CompositeVariant

if TYPE_CHECKING:
    from agent_evals.orchestrator import EvalOrchestrator

logger = logging.getLogger(__name__)


def _effective_score(
    trial: Any, judge_primary_types: frozenset[str],
) -> float:
    """Return the appropriate score for analysis.

    If graduation was applied in the runner, trial.score already contains
    the blended score — use it directly. Otherwise, fall back to returning
    judge_score for judge-primary types.
    """
    if (
        trial.metrics
        and trial.metrics.get("graduation_applied")
    ):
        return trial.score
    if (
        trial.task_type in judge_primary_types
        and trial.metrics
        and "judge_score" in trial.metrics
    ):
        return trial.metrics["judge_score"]
    return trial.score


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
    judge_primary_types: frozenset[str] = field(default_factory=frozenset)
    split_ratio: float | None = None
    split_seed: int = 42


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
    trial_count: int | None = None
    multi_objective: dict[str, dict] | None = None


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
        self._test_tasks: list[Any] = []

    def _save_phase_report(self, phase_result: PhaseResult) -> None:
        """Save a DOE-enriched report artifact for a pipeline phase."""
        if self._store is None:
            return
        data: dict[str, Any] = {
            "run_id": phase_result.run_id,
            "phase": phase_result.phase,
            "pipeline_id": self._pipeline_id,
            "trial_count": len(phase_result.trials),
            "total_cost": phase_result.total_cost,
            "total_tokens": phase_result.total_tokens,
            "elapsed_seconds": phase_result.elapsed_seconds,
            "main_effects": _to_dict(phase_result.main_effects),
            "anova": _to_dict(phase_result.anova),
            "optimal": _to_dict(phase_result.optimal),
            "significant_factors": phase_result.significant_factors,
            "predicted_sn": phase_result.predicted_sn,
            "confirmation": phase_result.confirmation,
            "interaction_effects": phase_result.interaction_effects,
        }
        self._store.save_report_artifact(
            phase_result.run_id, "phase_report", data,
        )

    def _save_factor_definitions(
        self, run_id: str, variants: list[Any],
    ) -> None:
        """Persist factor/level definitions derived from variant metadata.

        Gracefully handles FK violations (e.g. when the run_id has not
        yet been recorded in the store) so that pipeline phases are not
        aborted by ancillary persistence failures.
        """
        if self._store is None:
            return
        axes: dict[int, list[str]] = defaultdict(list)
        for v in variants:
            meta = v.metadata()
            if meta.axis == 0:
                continue
            if meta.name not in axes[meta.axis]:
                axes[meta.axis].append(meta.name)

        definitions: list[dict] = []
        for axis_id, level_names in sorted(axes.items()):
            for idx, name in enumerate(level_names):
                definitions.append({
                    "factor_name": f"axis_{axis_id}",
                    "axis_id": axis_id,
                    "level_index": idx,
                    "level_name": name,
                    "description": "",
                })
        try:
            self._store.save_factor_definitions(run_id, definitions)
        except sqlite3.IntegrityError:
            logger.debug(
                "Could not save factor definitions for run %s", run_id,
            )

    def _save_task_metadata(self, tasks: list[Any]) -> None:
        """Persist task metadata to the observatory store."""
        if self._store is None:
            return
        metadata_list: list[dict] = []
        for task in tasks:
            defn = task.definition
            meta = defn.metadata if hasattr(defn, "metadata") else {}
            metadata_list.append({
                "task_id": defn.task_id,
                "task_type": defn.type,
                "domain": meta.get("domain", "") if isinstance(meta, dict) else "",
                "difficulty": meta.get("difficulty", "") if isinstance(meta, dict) else "",
                "word_count": meta.get("word_count", 0) if isinstance(meta, dict) else 0,
                "tag_count": meta.get("tag_count", 0) if isinstance(meta, dict) else 0,
            })
        self._store.save_task_metadata(metadata_list)

    def _phase_trial_count(self, phase: PhaseResult) -> int:
        """Return trial count for a phase, using the store for resumed phases."""
        if phase.trials:
            return len(phase.trials)
        if phase.trial_count is not None:
            return phase.trial_count
        if self._store:
            try:
                summary = self._store.get_run_summary(phase.run_id)
                return summary.total_trials
            except ValueError:
                return 0
        return 0

    @staticmethod
    def _group_refinement_scores(
        trials: list[Any],
        design: Any,
        judge_primary_types: frozenset[str] = frozenset(),
    ) -> dict[int, list[float]]:
        """Group trial scores into design-row buckets by exact match.

        Matches each trial to the OA row whose full factor combination
        matches the trial's variant name.  Composite names (``"a+b+c"``)
        are split on ``"+"`` and matched against the row's sorted
        assignment values.  Single-variant names are matched when only
        one factor uses that level name (unambiguous).

        Trials with ``oa_row_id`` in metrics are mapped directly.
        Trials matching no row are skipped.
        """
        # Build row signature -> row_id for exact combination matching.
        # Signature = tuple of level names sorted by factor name.
        sig_to_row: dict[tuple[str, ...], int] = {}
        factor_names_sorted = sorted(f.name for f in design.factors)
        for row in design.rows:
            sig = tuple(row.assignments[f] for f in factor_names_sorted)
            sig_to_row[sig] = row.run_id

        # Build single-level-name -> factor_name for unambiguous
        # single-variant matching.  None marks ambiguous names.
        level_to_factor: dict[str, str | None] = {}
        for factor in design.factors:
            for level_name in factor.level_names:
                if level_name in level_to_factor:
                    # Ambiguous — appears in multiple factors
                    level_to_factor[level_name] = None
                else:
                    level_to_factor[level_name] = factor.name

        row_scores: dict[int, list[float]] = defaultdict(list)
        for trial in trials:
            if trial.error is not None:
                continue

            score = _effective_score(trial, judge_primary_types)

            # Fast path: direct oa_row_id from Taguchi runner
            oa_row_id = (
                trial.metrics.get("oa_row_id")
                if hasattr(trial, "metrics") and trial.metrics
                else None
            )
            if oa_row_id is not None:
                row_scores[int(oa_row_id)].append(score)
                continue

            vname = trial.variant_name

            # Try composite name match: "level1+level2+..." -> exact row
            if "+" in vname:
                parts = vname.split("+")
                # Try all permutations against row signatures
                sig = tuple(parts)
                if sig in sig_to_row:
                    row_scores[sig_to_row[sig]].append(score)
                    continue
                # Also try matching by sorted level names.
                # sorted() comparison is order-independent but avoids the
                # false-positive that set equality allows when two factors
                # share a level name (set loses duplicates).
                sorted_parts = sorted(parts)
                for row in design.rows:
                    vals = [
                        row.assignments[f] for f in factor_names_sorted
                    ]
                    if sorted_parts == sorted(vals):
                        row_scores[row.run_id].append(score)
                        break
                continue

            # Single-variant name: map to rows where this level's
            # specific factor matches.  Skip if ambiguous.
            factor_name = level_to_factor.get(vname)
            if factor_name is None:
                continue  # ambiguous or unknown level name
            for row in design.rows:
                if row.assignments.get(factor_name) == vname:
                    row_scores[row.run_id].append(score)

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

        design = build_factorial_design(dict(axes))
        row_scores = self._group_refinement_scores(
            trials, design, self.config.judge_primary_types,
        )
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

        # Train/test split for generalization validation
        if self.config.split_ratio is not None:
            from agent_evals.splits import stratified_split
            tasks, self._test_tasks = stratified_split(
                tasks,
                train_ratio=self.config.split_ratio,
                seed=self.config.split_seed,
            )
            logger.info(
                "Train/test split: %d train, %d test (ratio=%.2f)",
                len(tasks), len(self._test_tasks), self.config.split_ratio,
            )

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

        # 5. Group trial scores by OA row (exclude error trials — they are
        #    not real measurements and would bias S/N and ANOVA with 0.0).
        row_scores: dict[int, list[float]] = defaultdict(list)
        for trial in result.trials:
            if trial.error is not None:
                continue
            row_id = trial.metrics["oa_row_id"]
            row_scores[row_id].append(
                _effective_score(trial, self.config.judge_primary_types)
            )

        # Collect cost and latency per OA row for multi-objective analysis
        row_costs: dict[int, list[float]] = defaultdict(list)
        row_latencies: dict[int, list[float]] = defaultdict(list)
        for trial in result.trials:
            if trial.error is not None:
                continue
            row_id = int(trial.metrics["oa_row_id"])
            if trial.cost is not None:
                row_costs[row_id].append(trial.cost)
            if isinstance(trial.latency_seconds, (int, float)) and trial.latency_seconds >= 0:
                row_latencies[row_id].append(trial.latency_seconds)

        # Multi-objective analysis (accuracy + cost + latency)
        multi_obj = run_multi_objective_analysis(
            design, dict(row_scores), dict(row_costs), dict(row_latencies),
        )

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
            multi_objective=multi_obj if multi_obj else None,
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
            self._save_phase_report(phase_result)

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

        # Build a single CompositeVariant from all optimal levels.
        # Each factor (axis_N) maps to a variant name; we need one
        # component per axis to form the combined optimal configuration.
        optimal_map = screening_result.optimal or {}
        variant_by_name = {v.metadata().name: v for v in variants}

        components: dict[int, Any] = {}
        for _factor_name, level_name in optimal_map.items():
            variant = variant_by_name.get(level_name)
            if variant is not None:
                axis = variant.metadata().axis
                components[axis] = variant

        if components:
            composite = CompositeVariant(components)
            filtered_variants = [composite]
        else:
            logger.warning(
                "No variants matched optimal config %s; using all",
                screening_result.optimal,
            )
            filtered_variants = variants

        # Build variant lookup from the composite
        variant_lookup = {
            v.metadata().name: v for v in filtered_variants
        }

        # Use held-out test tasks for confirmation if train/test split was used
        if self._test_tasks:
            logger.info(
                "Using %d held-out test tasks for confirmation",
                len(self._test_tasks),
            )
            tasks = self._test_tasks

        # Run combined optimal config trials via orchestrator (full mode)
        result = self._orchestrator.run(
            tasks,
            filtered_variants,
            doc_tree,
            variant_lookup=variant_lookup,
            phase="confirmation",
            pipeline_id=self._pipeline_id,
            mode="full",
            resume_run_id=resume_run_id,
            parent_run_id=screening_result.run_id,
        )

        # Gather observed scores (exclude error trials, matching screening)
        optimal_scores = [t.score for t in result.trials if t.error is None]

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
                confirmation=phase_result.confirmation,
            )
            self._save_phase_report(phase_result)

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

        # Select top-K factors by main effect S/N range (#235).
        # More robust than ANOVA significance with noisy LLM data.
        ranked_factors = rank_factors_by_effect_range(
            screening_result.main_effects or {},
            exclude_factors={"model"},
        )
        top_k_factors = ranked_factors[: self.config.top_k]

        if not top_k_factors:
            top_k_factors = (
                screening_result.significant_factors[: self.config.top_k]
            )

        top_k_axes = self._resolve_factor_axes(variants, top_k_factors)

        # Build full factorial CompositeVariants (#234).
        # Each combo varies the top-K factor levels; non-top-K axes
        # are fixed at their screening optimal.
        optimal = screening_result.optimal or {}
        variant_by_name = {v.metadata().name: v for v in variants}

        axis_variants: dict[int, list[Any]] = {}
        for axis in sorted(top_k_axes):
            axis_variants[axis] = [
                v for v in variants if v.metadata().axis == axis
            ]

        fixed_components: dict[int, Any] = {}
        for factor_name, level_name in optimal.items():
            if not factor_name.startswith("axis_"):
                continue
            axis = int(factor_name.split("_", 1)[1])
            if axis not in top_k_axes and level_name in variant_by_name:
                fixed_components[axis] = variant_by_name[level_name]

        sorted_top_axes = sorted(top_k_axes)
        level_lists = [axis_variants[ax] for ax in sorted_top_axes]

        factorial_composites: list[Any] = []
        for combo in itertools_product(*level_lists):
            components = dict(fixed_components)
            for axis, variant in zip(sorted_top_axes, combo):
                components[axis] = variant
            factorial_composites.append(CompositeVariant(components))

        if not factorial_composites:
            logger.warning(
                "No factorial combinations for top-K %s; using all",
                top_k_factors,
            )
            filtered_variants = variants
        else:
            filtered_variants = factorial_composites

        analysis_variants = [
            v for v in variants if v.metadata().axis in top_k_axes
        ]

        variant_lookup = {
            v.metadata().name: v for v in filtered_variants
        }

        result = self._orchestrator.run(
            tasks,
            filtered_variants,
            doc_tree,
            variant_lookup=variant_lookup,
            phase="refinement",
            pipeline_id=self._pipeline_id,
            mode="full",
            resume_run_id=resume_run_id,
            parent_run_id=screening_result.run_id,
        )

        analysis = self._analyse_refinement(
            analysis_variants, result.trials,
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
            self._save_phase_report(phase_result)

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
        # Persist task metadata and factor definitions (bug #242).
        self._save_task_metadata(tasks)

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
            screen_summary = self._store.get_run_summary(screen_run_id)
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
                trial_count=screen_summary.total_trials,
            )
        elif "screening" in in_progress_phases:
            screening = self.run_screening(
                tasks, variants, doc_tree,
                resume_run_id=in_progress_phases["screening"],
            )
        else:
            screening = self.run_screening(tasks, variants, doc_tree)

        # Persist factor definitions for the screening run (bug #242).
        if "screening" not in completed_phases:
            self._save_factor_definitions(screening.run_id, variants)

        # Semi mode: check callback after screening
        if self.config.mode == "semi" and phase_callback is not None:
            if not phase_callback(screening):
                return PipelineResult(
                    pipeline_id=self._pipeline_id,
                    screening=screening,
                    total_trials=self._phase_trial_count(screening),
                    total_cost=screening.total_cost,
                    elapsed_seconds=screening.elapsed_seconds,
                )

        # Clear cache between phases to prevent cross-phase contamination
        # (bug #236: screening responses replayed in confirmation/refinement).
        self._orchestrator.clear_cache()

        # Phase 2: Confirmation
        if "confirmation" in completed_phases:
            conf_run_id = completed_phases["confirmation"]
            conf_phase_results = self._store.get_phase_results(conf_run_id)
            conf_summary = self._store.get_run_summary(conf_run_id)
            confirmation = PhaseResult(
                run_id=conf_run_id,
                phase="confirmation",
                trials=[],
                total_cost=conf_phase_results.get("total_cost", 0.0) if conf_phase_results else 0.0,
                total_tokens=conf_phase_results.get("total_tokens", 0) if conf_phase_results else 0,
                elapsed_seconds=conf_phase_results.get("elapsed_seconds", 0.0) if conf_phase_results else 0.0,
                confirmation=conf_phase_results.get("confirmation") if conf_phase_results else None,
                trial_count=conf_summary.total_trials,
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
                    total_trials=self._phase_trial_count(screening) + self._phase_trial_count(confirmation),
                    total_cost=screening.total_cost + confirmation.total_cost,
                    elapsed_seconds=screening.elapsed_seconds + confirmation.elapsed_seconds,
                )

        # Clear cache before refinement (bug #236).
        self._orchestrator.clear_cache()

        # Phase 3: Refinement
        if "refinement" in completed_phases:
            ref_run_id = completed_phases["refinement"]
            ref_phase_results = self._store.get_phase_results(ref_run_id)
            ref_summary = self._store.get_run_summary(ref_run_id)
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
                trial_count=ref_summary.total_trials,
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
            self._phase_trial_count(screening)
            + self._phase_trial_count(confirmation)
            + self._phase_trial_count(refinement)
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
