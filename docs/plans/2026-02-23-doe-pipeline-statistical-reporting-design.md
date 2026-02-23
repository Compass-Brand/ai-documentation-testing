# DOE Pipeline & Statistical Reporting Design

**Date:** 2026-02-23
**Status:** Approved
**Scope:** Multi-phase DOE pipeline, statistical significance reporting, frontend updates

---

## 1. Problem

The Taguchi L50 orthogonal array screens 10 format axes in 50 runs — far fewer than the millions required by full factorial. But screening alone cannot guarantee the predicted optimal is truly optimal. It assumes main effects dominate and misses higher-order interactions between factors.

To find the best documentation format for AI agents, the system requires three phases:

1. **Screen** with Taguchi OA to identify which factors matter and predict the optimal combination
2. **Confirm** the prediction against a baseline to validate it works
3. **Refine** via full factorial on the top significant factors to catch interaction effects

The first Taguchi run (L50 × 3 tasks × 3 reps = 150 trials) revealed that structure, transform, and granularity are the top three factors. Cross-references had almost no effect. A full factorial on just the top 3 factors (125 combinations) is tractable; a full factorial on all 10 is not.

The existing analysis engine computes S/N ratios, ANOVA, optimal predictions, and confirmation validation — but none of these reach the reports or the frontend. Every result's statistical significance must appear in the scientific reports.

---

## 2. Phase Model & Pipeline Architecture

### Three Phases

**Phase 1 — Screening (Taguchi OA)**

Runs the orthogonal array across all 355 gold-standard tasks. Produces:
- Main effects: mean S/N ratio per level per factor
- ANOVA: F-ratio, p-value, eta², omega² per factor
- Ranked factor list by influence (largest S/N delta first)
- Predicted optimal configuration with prediction interval

**Phase 2 — Confirmation**

Runs the predicted optimal from Phase 1 against a baseline (the single best-performing variant from screening). Uses the same 355 tasks with increased repetitions (default: 5). Produces:
- Observed vs predicted S/N comparison
- Paired t-test or Wilcoxon signed-rank test between optimal and baseline
- Confirmation result: within prediction interval or not, sigma deviation

**Phase 3 — Refinement (Full Factorial on Top Factors)**

Takes the top K significant factors from Phase 1 (default: 3, configurable via `--top-k`). Runs every combination of their levels while fixing non-significant factors at their optimal levels. Produces:
- Full ANOVA on the reduced factor space, capturing interaction effects
- Interaction plots for each factor pair
- Final optimal: the best combination from direct measurement

### Pipeline Orchestration

A `DOEPipeline` class coordinates all three phases:

```python
class DOEPipeline:
    """Coordinates screen → confirm → refine DOE workflow."""

    def __init__(self, config: PipelineConfig, orchestrator: EvalOrchestrator):
        ...

    def run(
        self,
        tasks: list[EvalTask],
        variants: list[IndexVariant],
        doc_tree: DocTree,
    ) -> PipelineResult:
        """Run complete DOE pipeline.

        In automatic mode, runs all phases sequentially.
        In semi-automatic mode, emits phase_complete events
        and waits for approval between phases.
        """
        ...
```

```python
@dataclass
class PipelineConfig:
    """Configuration for a multi-phase DOE pipeline."""

    mode: str                      # "auto" or "semi"
    quality_type: str              # "larger_is_better" (default)
    alpha: float                   # Significance threshold (default: 0.05)
    top_k: int                     # Factors for Phase 3 (default: 3)
    screening_reps: int            # Repetitions for Phase 1 (default: 3)
    confirmation_reps: int         # Repetitions for Phase 2 (default: 5)
    refinement_reps: int           # Repetitions for Phase 3 (default: 3)
    models: list[str]              # Model list
    oa_override: str | None        # Force specific OA (default: auto-select)
    report_format: str | None      # "html", "markdown", "both", or None
```

```python
@dataclass
class PipelineResult:
    """Aggregated results across all pipeline phases."""

    pipeline_id: str
    screening: PhaseResult
    confirmation: PhaseResult | None
    refinement: PhaseResult | None
    final_optimal: dict[str, str]  # factor_name → best_level
    total_trials: int
    total_cost: float
    elapsed_seconds: float
```

### Phase Transitions

After Phase 1 completes, the pipeline:
1. Reads the `phase_results` record for Phase 1
2. Extracts factors where p < alpha, ranked by omega²
3. Builds the Phase 2 config: optimal combo + baseline combo
4. In semi-automatic mode, prints the analysis summary and prompts for approval

After Phase 2 completes, the pipeline:
1. Reports whether confirmation succeeded (within prediction interval)
2. Builds the Phase 3 full factorial design for the top K factors
3. Fixes remaining factors at their Phase 1 optimal levels
4. In semi-automatic mode, shows the factorial design size and prompts

---

## 3. Database Schema Extensions

### Modified Tables

**`trials` table — two new columns:**

| Column | Type | Purpose |
|--------|------|---------|
| `oa_row_id` | INTEGER | Which OA row generated this trial. Indexed. |
| `phase` | TEXT | `screening`, `confirmation`, or `refinement`. |

**`runs` table — three new columns:**

| Column | Type | Purpose |
|--------|------|---------|
| `parent_run_id` | TEXT | Links to the screening run. NULL for screening runs. |
| `phase` | TEXT | Same enum as trials. |
| `pipeline_id` | TEXT | Groups all phases of a single pipeline. |

### New Table: `phase_results`

Stores analysis output after each phase completes. Avoids recomputing expensive statistical analysis.

```sql
CREATE TABLE IF NOT EXISTS phase_results (
    run_id        TEXT PRIMARY KEY,
    main_effects  TEXT,    -- JSON: per-factor mean S/N by level
    anova         TEXT,    -- JSON: full ANOVA decomposition
    optimal       TEXT,    -- JSON: predicted best config + interval
    confirmation  TEXT,    -- JSON: observed vs predicted (Phase 2)
    significant_factors TEXT, -- JSON: ordered factor list with p < alpha
    quality_type  TEXT,    -- larger_is_better / smaller_is_better
    created_at    TEXT DEFAULT (datetime('now'))
);
```

### Migration Strategy

A `_migrate_schema()` method runs on store initialization. It uses `ALTER TABLE ... ADD COLUMN` for new columns (SQLite-safe, no data loss). Existing runs continue working — new columns default to NULL.

---

## 4. Statistical Significance in Reports

The HTML and Markdown renderers currently produce 9 generic sections. Taguchi runs add 5 new sections that wire in the existing analysis engine and statistics module.

### Section 10 — Main Effects Analysis

Bar chart showing mean S/N ratio per level for each factor. Uses the existing `generate_main_effects_plotly()` function. Below the chart, a response table ranks factors by delta (max S/N minus min S/N). Factors with the largest delta influence results most.

### Section 11 — ANOVA Table

Classic ANOVA decomposition:

| Factor | SS | df | MS | F-ratio | p-value | omega² | Significance |
|--------|----|----|----|---------|---------|----|------|
| Structure | 12.34 | 4 | 3.08 | 8.72 | 0.001 | 0.089 | *** |
| Transform | 11.89 | 4 | 2.97 | 8.41 | 0.001 | 0.084 | *** |
| Granularity | 7.45 | 4 | 1.86 | 5.27 | 0.008 | 0.051 | ** |
| ... | | | | | | | |

Rows with p < 0.05 receive a significance marker. Omega² values include effect size labels: small (< 0.01), medium (0.01–0.06), large (> 0.06).

### Section 12 — Statistical Assumptions & Power

Before interpreting ANOVA results, the report validates assumptions:
- **Normality**: Shapiro-Wilk test on residuals (existing `check_assumptions()`)
- **Homogeneity**: Levene's test for equality of variances
- **Remediation**: When assumptions fail, the report notes that Kruskal-Wallis (non-parametric) replaced one-way ANOVA

Power analysis reports observed statistical power and the sample size required to detect the observed effect size at 80% power.

### Section 13 — Post-Hoc Comparisons

Tukey HSD pairwise comparisons between levels within each significant factor. Benjamini-Hochberg FDR correction applied across all p-values. Shows which specific levels differ from each other with mean difference and adjusted p-value.

### Section 14 — Optimal Prediction & Confirmation

Displays the predicted optimal combination with prediction interval from the additive model. After Phase 2 completes, adds the confirmation chart (predicted vs observed with CI band, via existing `generate_confirmation_chart()`) and reports whether the observed score falls within the interval.

### Cross-Phase Summary

When a full pipeline completes, the report opens with a pipeline overview:
- Phase timeline with trial counts, costs, and durations
- Factor ranking evolution across phases (screening rank vs refinement rank)
- Final optimal configuration with evidence from all three phases
- Overall statistical conclusion: which factors matter, which do not, and the best format

---

## 5. Frontend Updates

### New Page: Factor Analysis (`/analysis/:runId`)

The primary page for Taguchi results. Three panels:

**Main Effects Chart**
Interactive Chart.js bar chart of mean S/N per factor level. Factors sorted by influence (largest delta first). Hovering a bar shows the exact S/N value and delta rank.

**ANOVA Results Table**
DataTable with sortable columns: Factor, SS, df, MS, F-ratio, p-value, omega². Rows with p < 0.05 display a green StatusBadge ("Significant"); non-significant rows display a muted badge. Effect size column shows small/medium/large interpretation.

**Post-Hoc Panel**
Expandable sections per significant factor showing Tukey HSD pairwise comparisons. Each pair displays mean difference, confidence interval, and adjusted p-value.

### New Page: Pipeline View (`/pipeline/:pipelineId`)

Horizontal timeline with three phase nodes connected by arrows. Each node shows:
- Phase status: pending, running, or complete (StatusDot indicator)
- Run ID, trial count, cost, duration
- Click navigates to Factor Analysis or ResultsExplorer for that phase

In semi-automatic mode, a "Start Next Phase" button appears after each phase completes.

### Updated: ResultsExplorer

When viewing a Taguchi run, adds a "Factor Analysis" tab alongside existing variant and model tabs. Shows the optimal prediction card: predicted best configuration, prediction interval, and (after confirmation) whether the observed score validated.

### Updated: RunConfig

Adds pipeline options when Taguchi mode is selected:
- Pipeline mode toggle: automatic vs semi-automatic
- Quality type dropdown: larger-is-better (default), smaller-is-better, nominal-is-best
- Top-K factor input for refinement phase (default: 3)
- Alpha threshold input (default: 0.05)

### New API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/pipelines` | List all pipelines with phase summaries |
| GET | `/api/pipelines/:id` | Pipeline detail with linked runs |
| GET | `/api/runs/:id/analysis` | Phase results (main effects, ANOVA, optimal) |
| POST | `/api/pipelines/:id/approve` | Approve next phase (semi-automatic mode) |

---

## 6. CLI Interface

### New Flags

```
--pipeline {auto|semi}          Run full three-phase DOE pipeline
--phase {screening|confirmation|refinement}
                                Run a single phase manually
--parent-run RUN_ID             Link to prior screening run
--quality-type {larger_is_better|smaller_is_better|nominal_is_best}
                                S/N ratio type (default: larger_is_better)
--top-k N                       Factors for Phase 3 factorial (default: 3)
--alpha FLOAT                   Significance threshold (default: 0.05)
```

### Dry-Run Output

`agent-evals --mode taguchi --pipeline auto --dry-run` displays:

```
DOE Pipeline Plan
─────────────────
Phase 1 (Screening):  L50 OA × 355 tasks × 3 reps  =  53,250 trials
Phase 2 (Confirmation):  2 configs × 355 tasks × 5 reps  =  3,550 trials
Phase 3 (Refinement):  ≤125 combos × 355 tasks × 3 reps  =  ≤133,125 trials

Estimated total: ≤189,925 trials
Quality type: larger_is_better
Significance threshold: α = 0.05
Top-K factors for refinement: 3
```

Phase 3 shows "≤" because the actual count depends on how many levels the top K factors have.

### Backward Compatibility

Existing `--mode taguchi` without `--pipeline` runs a single screening phase, preserving current behavior. The pipeline flags are additive. Existing `--mode full` is unaffected.

### Single-Phase Manual Usage

For manual phase control:

```bash
# Phase 1: Screening
agent-evals --mode taguchi --model ... --phase screening

# Review results, then...
# Phase 2: Confirmation
agent-evals --mode taguchi --model ... --phase confirmation --parent-run <run_id>

# Phase 3: Refinement
agent-evals --mode taguchi --model ... --phase refinement --parent-run <run_id> --top-k 3
```

---

## 7. End-to-End Pipeline Flow

### Automatic Mode

```
CLI --pipeline auto
 │
 ├─► DOEPipeline.run()
 │    │
 │    ├─► Phase 1: Screening
 │    │    ├─ build_design() from variant registry
 │    │    ├─ create run (phase=screening, pipeline_id=uuid)
 │    │    ├─ TaguchiRunner.run() → trials with oa_row_id
 │    │    ├─ compute_sn_ratios() → compute_main_effects() → run_anova()
 │    │    ├─ predict_optimal()
 │    │    ├─ persist to phase_results table
 │    │    └─ emit phase_complete SSE event
 │    │
 │    ├─► Phase transition
 │    │    ├─ read phase_results for Phase 1
 │    │    ├─ extract significant factors (p < alpha)
 │    │    └─ build confirmation config (optimal + baseline)
 │    │
 │    ├─► Phase 2: Confirmation
 │    │    ├─ create run (phase=confirmation, parent_run_id, pipeline_id)
 │    │    ├─ run optimal vs baseline × tasks × reps
 │    │    ├─ validate_confirmation() against prediction interval
 │    │    ├─ paired t-test / Wilcoxon between optimal and baseline
 │    │    ├─ persist to phase_results table
 │    │    └─ emit phase_complete SSE event
 │    │
 │    ├─► Phase transition
 │    │    ├─ select top K significant factors
 │    │    ├─ compute full factorial design (K factors × all levels)
 │    │    └─ fix remaining factors at optimal levels
 │    │
 │    ├─► Phase 3: Refinement
 │    │    ├─ create run (phase=refinement, parent_run_id, pipeline_id)
 │    │    ├─ run full factorial × tasks × reps
 │    │    ├─ full ANOVA on reduced factor space
 │    │    ├─ interaction analysis between factor pairs
 │    │    ├─ persist to phase_results table
 │    │    └─ emit phase_complete SSE event
 │    │
 │    └─► Report generation
 │         ├─ aggregate across all three phases
 │         ├─ render HTML/Markdown with 14 sections
 │         ├─ wire in existing chart functions
 │         └─ save to reports/<pipeline_id>/
 │
 └─► Frontend SSE updates
      ├─ Pipeline View shows phase progression
      ├─ Factor Analysis populates per phase
      └─ ResultsExplorer shows cross-phase comparison
```

### Semi-Automatic Mode

Same flow, but after each `phase_complete` event:
1. Pipeline prints analysis summary to terminal
2. Prompts "Continue to [next phase]? [Y/n]"
3. If the user declines, the pipeline saves current state and exits
4. The user can resume later with `--phase <next> --parent-run <run_id>`

---

## 8. Key Files Reference

| File | Role | Change Type |
|------|------|-------------|
| `agent_evals/pipeline.py` | DOEPipeline class | **New** |
| `agent_evals/cli.py` | New flags, pipeline routing | Modify |
| `agent_evals/orchestrator.py` | Phase-aware run creation | Modify |
| `agent_evals/observatory/store.py` | Schema migration, new methods | Modify |
| `agent_evals/taguchi/analysis.py` | Already complete | No change |
| `agent_evals/taguchi/runner.py` | Add phase metadata to trials | Modify |
| `agent_evals/reports/aggregator.py` | Include phase_results in ReportData | Modify |
| `agent_evals/reports/statistics.py` | Already complete | No change |
| `agent_evals/reports/html_renderer.py` | Add sections 10–14 | Modify |
| `agent_evals/reports/md_renderer.py` | Add sections 10–14 | Modify |
| `agent_evals/reports/charts.py` | Already complete | No change |
| `observatory/web/ui/src/pages/FactorAnalysis.tsx` | New page | **New** |
| `observatory/web/ui/src/pages/PipelineView.tsx` | New page | **New** |
| `observatory/web/ui/src/pages/ResultsExplorer.tsx` | Add factor tab | Modify |
| `observatory/web/ui/src/pages/RunConfig.tsx` | Add pipeline options | Modify |
| `observatory/web/ui/src/api/client.ts` | New pipeline endpoints | Modify |
| `observatory/web/ui/src/api/hooks.ts` | New pipeline hooks | Modify |
| `observatory/web/routes.py` | New API routes | Modify |
