# DOE Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a three-phase DOE pipeline (screen → confirm → refine) with statistical significance reporting in all scientific reports and two new frontend pages.

**Architecture:** A `DOEPipeline` class coordinates three phases, each writing results to the observatory SQLite store with phase metadata. The existing analysis engine (S/N ratios, ANOVA, optimal prediction) and statistics module (power analysis, Tukey HSD, Benjamini-Hochberg) are already complete — this plan wires them into reports and the frontend.

**Tech Stack:** Python 3.11+, pytest, SQLite, FastAPI, React 18, TypeScript, Chart.js, TanStack Query v5, TailwindCSS 3

**Design Doc:** `docs/plans/2026-02-23-doe-pipeline-statistical-reporting-design.md`

**Base path:** `agent-evals/src/agent_evals/` (abbreviated as `src/` below)
**Test path:** `agent-evals/tests/` (abbreviated as `tests/` below)
**Frontend path:** `src/observatory/web/ui/src/` (abbreviated as `ui/` below)
**Run tests:** `~/.local/bin/uv run pytest`
**Run single test:** `~/.local/bin/uv run pytest tests/<file>::<test> -v`

---

## Team Parallelism Map

```
Phase A: Foundation (sequential — blocks everything)
  Task 1: Schema migration
  Task 2: Pipeline data models

Phase B: Backend (3 parallel streams after Phase A)
  Stream 1 (store+runner):  Task 3 → Task 4
  Stream 2 (reports):       Task 5 → Task 6 → Task 7
  Stream 3 (pipeline):      Task 8 → Task 9 → Task 10

Phase C: Integration (after Phase B)
  Task 11: CLI flags + pipeline routing
  Task 12: API routes

Phase D: Frontend (after Phase C, 2 parallel streams)
  Stream 1: Task 13 → Task 15 → Task 17
  Stream 2: Task 14 → Task 16 → Task 18

Phase E: Validation (after Phase D)
  Task 19: Integration tests + dry-run
```

---

## Task 1: Schema Migration

**Files:**
- Modify: `src/observatory/store.py` (lines 52–80 schema, lines 115–193 methods)
- Test: `tests/test_observatory_store.py`

### Step 1: Write failing tests for new columns

```python
# tests/test_observatory_store.py — add to existing file

def test_create_run_with_phase_and_pipeline(tmp_path):
    """Runs table accepts phase and pipeline_id columns."""
    store = ObservatoryStore(tmp_path / "test.db")
    store.create_run(
        "run-1", "taguchi", {"mode": "taguchi"},
        phase="screening", pipeline_id="pipe-1",
    )
    runs = store.list_runs()
    assert len(runs) == 1
    assert runs[0].run_id == "run-1"


def test_create_run_with_parent(tmp_path):
    """Confirmation run links to parent screening run."""
    store = ObservatoryStore(tmp_path / "test.db")
    store.create_run("run-1", "taguchi", {}, phase="screening", pipeline_id="pipe-1")
    store.create_run(
        "run-2", "taguchi", {},
        phase="confirmation", pipeline_id="pipe-1", parent_run_id="run-1",
    )
    runs = store.list_runs()
    assert len(runs) == 2


def test_record_trial_with_oa_row_and_phase(tmp_path):
    """Trial records store oa_row_id and phase."""
    store = ObservatoryStore(tmp_path / "test.db")
    store.create_run("run-1", "taguchi", {})
    store.record_trial(
        run_id="run-1", task_id="t1", task_type="retrieval",
        variant_name="v1", repetition=1, score=0.8,
        prompt_tokens=100, completion_tokens=50, total_tokens=150,
        cost=0.01, latency_seconds=1.0, model="test-model",
        oa_row_id=3, phase="screening",
    )
    trials = store.get_trials("run-1")
    assert len(trials) == 1


def test_save_and_get_phase_results(tmp_path):
    """Phase results round-trip through SQLite."""
    store = ObservatoryStore(tmp_path / "test.db")
    store.create_run("run-1", "taguchi", {})
    store.save_phase_results(
        run_id="run-1",
        main_effects={"structure": {"flat": 10.5, "nested": 12.3}},
        anova={"structure": {"p_value": 0.001, "omega_squared": 0.089}},
        optimal={"structure": "nested"},
        significant_factors=["structure", "transform"],
        quality_type="larger_is_better",
    )
    result = store.get_phase_results("run-1")
    assert result is not None
    assert result["main_effects"]["structure"]["nested"] == 12.3
    assert result["quality_type"] == "larger_is_better"


def test_get_phase_results_missing(tmp_path):
    """Returns None for runs without phase results."""
    store = ObservatoryStore(tmp_path / "test.db")
    result = store.get_phase_results("nonexistent")
    assert result is None


def test_get_pipeline_runs(tmp_path):
    """Lists all runs in a pipeline ordered by creation."""
    store = ObservatoryStore(tmp_path / "test.db")
    store.create_run("r1", "taguchi", {}, phase="screening", pipeline_id="p1")
    store.create_run("r2", "taguchi", {}, phase="confirmation", pipeline_id="p1")
    store.create_run("r3", "taguchi", {}, phase="refinement", pipeline_id="p1")
    runs = store.get_pipeline_runs("p1")
    assert len(runs) == 3
    assert runs[0].run_id == "r1"


def test_schema_migration_preserves_existing_data(tmp_path):
    """Adding new columns does not break existing data."""
    store = ObservatoryStore(tmp_path / "test.db")
    store.create_run("old-run", "sweep", {"mode": "full"})
    store.record_trial(
        run_id="old-run", task_id="t1", task_type="retrieval",
        variant_name="v1", repetition=1, score=0.5,
        prompt_tokens=10, completion_tokens=5, total_tokens=15,
        cost=0.001, latency_seconds=0.5, model="m1",
    )
    # Re-open store (triggers migration again — should be idempotent)
    store2 = ObservatoryStore(tmp_path / "test.db")
    trials = store2.get_trials("old-run")
    assert len(trials) == 1
```

### Step 2: Run tests to verify they fail

```bash
~/.local/bin/uv run pytest tests/test_observatory_store.py::test_create_run_with_phase_and_pipeline -v
~/.local/bin/uv run pytest tests/test_observatory_store.py::test_save_and_get_phase_results -v
```

Expected: FAIL — `create_run()` does not accept `phase` or `pipeline_id`, `save_phase_results` does not exist.

### Step 3: Implement schema migration and new methods

**In `src/observatory/store.py`:**

1. Update `_SCHEMA` (line 52) to add new columns to runs and trials tables, and add the `phase_results` table.

2. Add a `_migrate_schema()` method that runs `ALTER TABLE ... ADD COLUMN` for each new column (wrapped in try/except for idempotency).

3. Update `create_run()` signature to accept optional `phase`, `pipeline_id`, `parent_run_id` params. Update the INSERT statement.

4. Update `record_trial()` signature to accept optional `oa_row_id` and `phase` params. Update the INSERT statement.

5. Add `save_phase_results(run_id, main_effects, anova, optimal, significant_factors, quality_type, confirmation=None)` method.

6. Add `get_phase_results(run_id) -> dict | None` method.

7. Add `get_pipeline_runs(pipeline_id) -> list[RunSummary]` method.

8. Update `RunSummary` and `TrialRecord` dataclasses to include new fields (with defaults for backward compatibility).

### Step 4: Run tests to verify they pass

```bash
~/.local/bin/uv run pytest tests/test_observatory_store.py -v
```

Expected: ALL PASS (both new and existing tests).

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/observatory/store.py agent-evals/tests/test_observatory_store.py
git commit -m "feat(store): add phase columns, phase_results table, and pipeline queries

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Pipeline Data Models

**Files:**
- Create: `src/pipeline.py`
- Test: `tests/test_pipeline.py`

### Step 1: Write failing tests for data models

```python
# tests/test_pipeline.py

from agent_evals.pipeline import PipelineConfig, PhaseResult, PipelineResult


def test_pipeline_config_defaults():
    """PipelineConfig provides sensible defaults."""
    config = PipelineConfig(models=["model-a"])
    assert config.mode == "auto"
    assert config.quality_type == "larger_is_better"
    assert config.alpha == 0.05
    assert config.top_k == 3
    assert config.screening_reps == 3
    assert config.confirmation_reps == 5
    assert config.refinement_reps == 3


def test_pipeline_config_semi_mode():
    """PipelineConfig accepts semi mode."""
    config = PipelineConfig(models=["m"], mode="semi")
    assert config.mode == "semi"


def test_phase_result_stores_analysis():
    """PhaseResult holds run_id, phase, trials, and analysis data."""
    result = PhaseResult(
        run_id="r1",
        phase="screening",
        trials=[],
        total_cost=1.23,
        total_tokens=5000,
        elapsed_seconds=60.0,
        main_effects={"structure": {"flat": 10.0}},
        anova={"structure": {"p_value": 0.01}},
        optimal={"structure": "nested"},
        significant_factors=["structure"],
    )
    assert result.phase == "screening"
    assert result.main_effects["structure"]["flat"] == 10.0


def test_phase_result_confirmation_field():
    """PhaseResult can store confirmation data for Phase 2."""
    result = PhaseResult(
        run_id="r2", phase="confirmation", trials=[],
        total_cost=0.5, total_tokens=1000, elapsed_seconds=30.0,
        confirmation={"within_interval": True, "sigma_deviation": 0.3},
    )
    assert result.confirmation["within_interval"] is True


def test_pipeline_result_aggregates_phases():
    """PipelineResult holds all phases and the final optimal."""
    screening = PhaseResult(
        run_id="r1", phase="screening", trials=[],
        total_cost=10.0, total_tokens=50000, elapsed_seconds=300.0,
        significant_factors=["structure", "transform"],
    )
    pr = PipelineResult(
        pipeline_id="pipe-1",
        screening=screening,
        confirmation=None,
        refinement=None,
        final_optimal={"structure": "nested", "transform": "summary"},
        total_trials=150,
        total_cost=10.0,
        elapsed_seconds=300.0,
    )
    assert pr.pipeline_id == "pipe-1"
    assert pr.final_optimal["structure"] == "nested"
```

### Step 2: Run tests to verify they fail

```bash
~/.local/bin/uv run pytest tests/test_pipeline.py -v
```

Expected: FAIL — `agent_evals.pipeline` module does not exist.

### Step 3: Implement data models

Create `src/pipeline.py`:

```python
"""Multi-phase DOE pipeline data models and orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PipelineConfig:
    """Configuration for a multi-phase DOE pipeline."""

    models: list[str]
    mode: str = "auto"                          # "auto" or "semi"
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
    phase: str                                  # screening / confirmation / refinement
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
```

### Step 4: Run tests to verify they pass

```bash
~/.local/bin/uv run pytest tests/test_pipeline.py -v
```

Expected: ALL PASS.

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/pipeline.py agent-evals/tests/test_pipeline.py
git commit -m "feat: add DOE pipeline data models (PipelineConfig, PhaseResult, PipelineResult)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Store Phase-Aware Queries + Runner Phase Metadata

**Depends on:** Task 1
**Files:**
- Modify: `src/taguchi/runner.py` (lines 68–117 run method, lines 119–196 _run_trial)
- Test: `tests/test_taguchi_runner.py`

### Step 1: Write failing test for phase metadata in trials

```python
# tests/test_taguchi_runner.py — add to existing file

def test_runner_sets_phase_in_trial_metrics(
    simple_design, simple_tasks, simple_doc_tree, dummy_client
):
    """TaguchiRunner stores phase in trial metrics when provided."""
    runner = TaguchiRunner(
        clients={"m": dummy_client},
        config=EvalRunConfig(repetitions=1),
        design=simple_design,
        variant_lookup=_build_lookup(simple_design),
    )
    result = runner.run(simple_tasks, simple_doc_tree, phase="screening")
    for trial in result.trials:
        assert trial.metrics.get("phase") == "screening"
        assert "oa_row_id" in trial.metrics


def test_runner_phase_defaults_to_none(
    simple_design, simple_tasks, simple_doc_tree, dummy_client
):
    """Without phase arg, trials have no phase in metrics."""
    runner = TaguchiRunner(
        clients={"m": dummy_client},
        config=EvalRunConfig(repetitions=1),
        design=simple_design,
        variant_lookup=_build_lookup(simple_design),
    )
    result = runner.run(simple_tasks, simple_doc_tree)
    for trial in result.trials:
        assert trial.metrics.get("phase") is None
```

### Step 2: Run tests to verify they fail

```bash
~/.local/bin/uv run pytest tests/test_taguchi_runner.py::test_runner_sets_phase_in_trial_metrics -v
```

Expected: FAIL — `run()` does not accept `phase` parameter.

### Step 3: Implement

In `src/taguchi/runner.py`:

1. Add `phase: str | None = None` parameter to `run()` method (line 68).
2. Pass `phase` through to `_run_trial()`.
3. In `_run_trial()`, set `trial.metrics["phase"] = phase` when phase is not None.
4. Ensure `trial.metrics["oa_row_id"]` is always set (already may be — verify and fix if needed).

### Step 4: Run tests to verify they pass

```bash
~/.local/bin/uv run pytest tests/test_taguchi_runner.py -v
```

Expected: ALL PASS (both new and existing).

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/taguchi/runner.py agent-evals/tests/test_taguchi_runner.py
git commit -m "feat(runner): pass phase metadata through to trial metrics

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Runner Store Integration — Phase-Aware Trial Recording

**Depends on:** Task 1, Task 3
**Files:**
- Modify: `src/orchestrator.py` (lines 346–382 _run_taguchi)
- Test: `tests/test_orchestrator.py`

### Step 1: Write failing test

```python
# tests/test_orchestrator.py — add to existing file

def test_orchestrator_passes_phase_to_store(tmp_path, mock_runner):
    """Orchestrator passes phase and pipeline_id to store when configured."""
    config = OrchestratorConfig(
        models=["m"], api_key="test", db_path=tmp_path / "obs.db",
        mode="taguchi",
    )
    orch = EvalOrchestrator(config)
    result = orch.run(
        tasks=mock_runner.tasks,
        variants=mock_runner.variants,
        doc_tree=mock_runner.doc_tree,
        design=mock_runner.design,
        variant_lookup=mock_runner.variant_lookup,
        phase="screening",
        pipeline_id="pipe-1",
    )
    store = ObservatoryStore(tmp_path / "obs.db")
    runs = store.get_pipeline_runs("pipe-1")
    assert len(runs) == 1
    assert runs[0].run_id == result.run_id
```

### Step 2: Run to verify failure

```bash
~/.local/bin/uv run pytest tests/test_orchestrator.py::test_orchestrator_passes_phase_to_store -v
```

Expected: FAIL — `run()` does not accept `phase` or `pipeline_id`.

### Step 3: Implement

In `src/orchestrator.py`:

1. Add `phase: str | None = None` and `pipeline_id: str | None = None` to `run()` (line 139).
2. Pass `phase` and `pipeline_id` to `self._store.create_run()`.
3. Pass `phase` to `TaguchiRunner.run()` call.
4. When recording trials to store, pass `phase` and `oa_row_id` from trial metrics.

### Step 4: Verify

```bash
~/.local/bin/uv run pytest tests/test_orchestrator.py -v
```

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/orchestrator.py agent-evals/tests/test_orchestrator.py
git commit -m "feat(orchestrator): pass phase and pipeline_id to store and runner

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Report Aggregator — Include Phase Results

**Depends on:** Task 1
**Files:**
- Modify: `src/reports/aggregator.py` (lines 25–45 ReportData, lines 71–98 aggregate)
- Test: `tests/test_report_aggregator.py`

### Step 1: Write failing tests

```python
# tests/test_report_aggregator.py — add to existing file

def test_report_data_includes_phase_results():
    """ReportData stores phase_results when provided."""
    data = ReportData(
        config=_make_config(),
        total_trials=100,
        total_cost=5.0,
        by_variant={},
        by_task_type={},
        by_source={},
        phase_results={
            "main_effects": {"structure": {"flat": 10.0}},
            "anova": {"structure": {"p_value": 0.001}},
            "optimal": {"structure": "nested"},
            "significant_factors": ["structure"],
            "quality_type": "larger_is_better",
        },
    )
    assert data.phase_results["anova"]["structure"]["p_value"] == 0.001


def test_report_data_phase_results_defaults_none():
    """ReportData.phase_results defaults to None for non-Taguchi runs."""
    data = ReportData(
        config=_make_config(),
        total_trials=10,
        total_cost=1.0,
        by_variant={},
        by_task_type={},
        by_source={},
    )
    assert data.phase_results is None


def test_aggregate_with_phase_results(sample_trials, sample_config):
    """aggregate() passes through phase_results when provided."""
    result = aggregate(
        sample_trials, sample_config, {},
        phase_results={"anova": {"structure": {"p_value": 0.01}}},
    )
    assert result.phase_results is not None
    assert result.phase_results["anova"]["structure"]["p_value"] == 0.01
```

### Step 2: Verify failure

```bash
~/.local/bin/uv run pytest tests/test_report_aggregator.py::test_report_data_includes_phase_results -v
```

Expected: FAIL — `ReportData` does not accept `phase_results`.

### Step 3: Implement

In `src/reports/aggregator.py`:

1. Add `phase_results: dict | None = None` field to `ReportData` (after line 45).
2. Add `phase_results: dict | None = None` param to `aggregate()` (line 71).
3. Pass `phase_results` through to the returned `ReportData`.

### Step 4: Verify

```bash
~/.local/bin/uv run pytest tests/test_report_aggregator.py -v
```

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/reports/aggregator.py agent-evals/tests/test_report_aggregator.py
git commit -m "feat(aggregator): add phase_results field to ReportData

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: HTML Renderer — Taguchi Statistical Sections

**Depends on:** Task 5
**Files:**
- Modify: `src/reports/html_renderer.py` (lines 16–183 template, lines 186–244 render_html)
- Test: `tests/test_report_html.py`

### Step 1: Write failing tests

```python
# tests/test_report_html.py — add to existing file

def test_html_renders_main_effects_section(taguchi_report_data):
    """HTML report includes Main Effects Analysis when phase_results present."""
    html = render_html(taguchi_report_data)
    assert "Main Effects Analysis" in html
    assert "structure" in html


def test_html_renders_anova_table(taguchi_report_data):
    """HTML report includes ANOVA table with p-values."""
    html = render_html(taguchi_report_data)
    assert "ANOVA" in html
    assert "p-value" in html.lower() or "p_value" in html


def test_html_renders_significance_markers(taguchi_report_data):
    """Significant factors (p < 0.05) are marked in HTML."""
    html = render_html(taguchi_report_data)
    # Should contain significance indicator for structure (p=0.001)
    assert "***" in html or "Significant" in html


def test_html_renders_optimal_prediction(taguchi_report_data):
    """HTML report shows the optimal configuration prediction."""
    html = render_html(taguchi_report_data)
    assert "Optimal" in html or "optimal" in html


def test_html_skips_taguchi_sections_without_phase_results(sample_report_data):
    """Non-Taguchi reports do not render Taguchi sections."""
    html = render_html(sample_report_data)
    assert "Main Effects" not in html
    assert "ANOVA" not in html
```

You must create a `taguchi_report_data` fixture that builds a `ReportData` with `phase_results` containing realistic main_effects, anova, optimal, and significant_factors dicts. Use the dataclass shapes from `taguchi/analysis.py`.

### Step 2: Verify failure

```bash
~/.local/bin/uv run pytest tests/test_report_html.py::test_html_renders_main_effects_section -v
```

Expected: FAIL — "Main Effects Analysis" not in output.

### Step 3: Implement

In `src/reports/html_renderer.py`:

1. Add 5 new sections to `_TEMPLATE` (after existing Section 9), conditional on `data.phase_results`:
   - **Section 10: Main Effects Analysis** — Bar chart data + response table
   - **Section 11: ANOVA Table** — Table with SS, df, MS, F-ratio, p-value, omega², significance markers
   - **Section 12: Statistical Assumptions & Power** — Normality/homogeneity results, power
   - **Section 13: Post-Hoc Comparisons** — Tukey HSD pairwise table
   - **Section 14: Optimal Prediction** — Optimal config + prediction interval

2. In `render_html()`, compute chart JSON for main effects using existing `generate_main_effects_plotly()` from `reports/charts.py`.

3. Compute statistical tests using existing functions from `reports/statistics.py` (power_analysis, check_assumptions, tukey_hsd, benjamini_hochberg).

### Step 4: Verify

```bash
~/.local/bin/uv run pytest tests/test_report_html.py -v
```

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/reports/html_renderer.py agent-evals/tests/test_report_html.py
git commit -m "feat(html): add Taguchi statistical sections 10-14 to HTML reports

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Markdown Renderer — Taguchi Statistical Sections

**Depends on:** Task 5
**Files:**
- Modify: `src/reports/md_renderer.py` (lines 12–136)
- Test: `tests/test_report_markdown.py`

### Step 1: Write failing tests

```python
# tests/test_report_markdown.py — add to existing file

def test_md_renders_main_effects_table(taguchi_report_data):
    """Markdown report includes main effects response table."""
    md = render_markdown(taguchi_report_data)
    assert "Main Effects" in md
    assert "Delta" in md


def test_md_renders_anova_table(taguchi_report_data):
    """Markdown report includes ANOVA table."""
    md = render_markdown(taguchi_report_data)
    assert "ANOVA" in md
    assert "p-value" in md.lower() or "p_value" in md


def test_md_renders_significance_stars(taguchi_report_data):
    """Significant factors get star markers in Markdown."""
    md = render_markdown(taguchi_report_data)
    assert "***" in md or "**" in md


def test_md_renders_optimal_config(taguchi_report_data):
    """Markdown report shows optimal configuration."""
    md = render_markdown(taguchi_report_data)
    assert "Optimal" in md or "optimal" in md


def test_md_skips_taguchi_without_phase_results(sample_report_data):
    """Non-Taguchi reports skip Taguchi sections."""
    md = render_markdown(sample_report_data)
    assert "ANOVA" not in md
```

Reuse the `taguchi_report_data` fixture from Task 6 (extract to `conftest.py` if needed).

### Step 2: Verify failure

```bash
~/.local/bin/uv run pytest tests/test_report_markdown.py::test_md_renders_main_effects_table -v
```

### Step 3: Implement

In `src/reports/md_renderer.py`, add 5 sections at the end of `render_markdown()`, conditional on `data.phase_results`:

- **Main Effects**: Pipe table with Factor, Level1 S/N, Level2 S/N, ..., Delta columns
- **ANOVA**: Pipe table with Factor, SS, df, MS, F-ratio, p-value, omega², significance markers
- **Assumptions & Power**: Text block with Shapiro-Wilk and Levene results
- **Post-Hoc**: Pipe table with Factor Pair, Mean Diff, Adjusted p-value
- **Optimal**: Config list + prediction interval

### Step 4: Verify

```bash
~/.local/bin/uv run pytest tests/test_report_markdown.py -v
```

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/reports/md_renderer.py agent-evals/tests/test_report_markdown.py
git commit -m "feat(md): add Taguchi statistical sections 10-14 to Markdown reports

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 8: DOEPipeline — Phase 1 Screening

**Depends on:** Task 2, Task 3, Task 4
**Files:**
- Modify: `src/pipeline.py`
- Test: `tests/test_pipeline.py`

### Step 1: Write failing tests

```python
# tests/test_pipeline.py — add to existing file

from unittest.mock import MagicMock, patch
from agent_evals.pipeline import DOEPipeline, PipelineConfig


def _make_mock_orchestrator(score=0.5):
    """Create a mock orchestrator that returns predictable results."""
    orch = MagicMock()
    trial = MagicMock()
    trial.score = score
    trial.cost = 0.01
    trial.total_tokens = 100
    trial.metrics = {"oa_row_id": 0}
    result = MagicMock()
    result.run_id = "test-run"
    result.trials = [trial] * 50
    result.total_cost = 0.5
    result.total_tokens = 5000
    result.elapsed_seconds = 10.0
    result.raw_result = MagicMock()
    result.raw_result.design = MagicMock()
    orch.run.return_value = result
    return orch


def test_pipeline_screening_builds_design():
    """Phase 1 builds a TaguchiDesign from variant axes."""
    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    with patch("agent_evals.pipeline.build_design") as mock_build:
        mock_build.return_value = MagicMock()
        pipeline.run_screening(
            tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
        )
        mock_build.assert_called_once()


def test_pipeline_screening_returns_phase_result():
    """Screening returns a PhaseResult with analysis data."""
    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    with patch("agent_evals.pipeline.build_design"), \
         patch("agent_evals.pipeline.compute_sn_ratios") as mock_sn, \
         patch("agent_evals.pipeline.compute_main_effects") as mock_me, \
         patch("agent_evals.pipeline.run_anova") as mock_anova, \
         patch("agent_evals.pipeline.predict_optimal") as mock_predict:
        mock_sn.return_value = {0: 10.5}
        mock_me.return_value = {"structure": {"flat": 10.0, "nested": 12.0}}
        mock_anova.return_value = MagicMock()
        mock_anova.return_value.factors = {
            "structure": MagicMock(p_value=0.001, omega_squared=0.089)
        }
        mock_predict.return_value = MagicMock()
        mock_predict.return_value.optimal_assignment = {"structure": "nested"}

        result = pipeline.run_screening(
            tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
        )
        assert result.phase == "screening"
        assert result.main_effects is not None
        assert result.anova is not None


def test_pipeline_screening_identifies_significant_factors():
    """Screening extracts factors with p < alpha."""
    config = PipelineConfig(models=["model-a"], alpha=0.05)
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    with patch("agent_evals.pipeline.build_design"), \
         patch("agent_evals.pipeline.compute_sn_ratios") as mock_sn, \
         patch("agent_evals.pipeline.compute_main_effects"), \
         patch("agent_evals.pipeline.run_anova") as mock_anova, \
         patch("agent_evals.pipeline.predict_optimal") as mock_predict:
        mock_sn.return_value = {0: 10.5}
        mock_anova.return_value = MagicMock()
        mock_anova.return_value.factors = {
            "structure": MagicMock(p_value=0.001, omega_squared=0.089),
            "xref": MagicMock(p_value=0.72, omega_squared=0.001),
        }
        mock_predict.return_value = MagicMock()
        mock_predict.return_value.optimal_assignment = {}

        result = pipeline.run_screening(
            tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
        )
        assert "structure" in result.significant_factors
        assert "xref" not in result.significant_factors
```

You must add a `_make_variants()` helper that returns a list of mock variants with `.metadata().axis` and `.metadata().name` attributes.

### Step 2: Verify failure

```bash
~/.local/bin/uv run pytest tests/test_pipeline.py::test_pipeline_screening_builds_design -v
```

Expected: FAIL — `DOEPipeline` class does not exist.

### Step 3: Implement

Add `DOEPipeline` class to `src/pipeline.py`:

```python
class DOEPipeline:
    """Coordinates screen → confirm → refine DOE workflow."""

    def __init__(self, config: PipelineConfig, orchestrator: EvalOrchestrator) -> None:
        self._config = config
        self._orchestrator = orchestrator
        self._pipeline_id = uuid4().hex[:12]

    def run_screening(self, tasks, variants, doc_tree) -> PhaseResult:
        """Execute Phase 1: Taguchi OA screening."""
        # 1. Build axes dict from variants
        # 2. Call build_design(axes, models, oa_override)
        # 3. Build variant_lookup
        # 4. Call orchestrator.run(phase="screening", pipeline_id=self._pipeline_id)
        # 5. Compute S/N ratios from trial scores grouped by OA row
        # 6. Compute main effects, run ANOVA, predict optimal
        # 7. Extract significant factors (p < alpha)
        # 8. Return PhaseResult
        ...
```

### Step 4: Verify

```bash
~/.local/bin/uv run pytest tests/test_pipeline.py -v
```

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/pipeline.py agent-evals/tests/test_pipeline.py
git commit -m "feat(pipeline): implement Phase 1 screening with analysis

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 9: DOEPipeline — Phase 2 Confirmation

**Depends on:** Task 8
**Files:**
- Modify: `src/pipeline.py`
- Test: `tests/test_pipeline.py`

### Step 1: Write failing tests

```python
# tests/test_pipeline.py — add

def test_pipeline_confirmation_uses_optimal_config():
    """Phase 2 runs the optimal config from Phase 1."""
    config = PipelineConfig(models=["model-a"], confirmation_reps=5)
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    screening = PhaseResult(
        run_id="r1", phase="screening", trials=[],
        optimal={"structure": "nested", "transform": "summary"},
        significant_factors=["structure", "transform"],
    )
    result = pipeline.run_confirmation(
        screening_result=screening,
        tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
    )
    assert result.phase == "confirmation"
    assert result.confirmation is not None


def test_pipeline_confirmation_validates_prediction():
    """Phase 2 runs validate_confirmation against screening prediction."""
    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator(score=0.7)
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    screening = PhaseResult(
        run_id="r1", phase="screening", trials=[],
        optimal={"structure": "nested"},
        significant_factors=["structure"],
    )

    with patch("agent_evals.pipeline.validate_confirmation") as mock_val:
        mock_val.return_value = MagicMock(
            within_interval=True, sigma_deviation=0.3,
        )
        result = pipeline.run_confirmation(
            screening_result=screening,
            tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
        )
        mock_val.assert_called_once()
        assert result.confirmation["within_interval"] is True
```

### Step 2: Verify failure

```bash
~/.local/bin/uv run pytest tests/test_pipeline.py::test_pipeline_confirmation_uses_optimal_config -v
```

### Step 3: Implement `run_confirmation()` in `DOEPipeline`

1. Build a single CompositeVariant from the optimal assignment
2. Build a baseline variant (best single variant from screening trials)
3. Run both against all tasks with `confirmation_reps`
4. Call `validate_confirmation()` from `taguchi/analysis.py`
5. Run paired t-test between optimal and baseline scores
6. Return PhaseResult with confirmation data

### Step 4: Verify

```bash
~/.local/bin/uv run pytest tests/test_pipeline.py -v
```

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/pipeline.py agent-evals/tests/test_pipeline.py
git commit -m "feat(pipeline): implement Phase 2 confirmation with validation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 10: DOEPipeline — Phase 3 Refinement + Full run()

**Depends on:** Task 9
**Files:**
- Modify: `src/pipeline.py`
- Test: `tests/test_pipeline.py`

### Step 1: Write failing tests

```python
# tests/test_pipeline.py — add

def test_pipeline_refinement_uses_top_k_factors():
    """Phase 3 runs full factorial on top K significant factors."""
    config = PipelineConfig(models=["model-a"], top_k=2)
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    screening = PhaseResult(
        run_id="r1", phase="screening", trials=[],
        optimal={"structure": "nested", "transform": "summary", "xref": "none"},
        significant_factors=["structure", "transform", "granularity"],
        main_effects={
            "structure": {"flat": 10.0, "nested": 12.0},
            "transform": {"raw": 9.0, "summary": 11.0},
            "granularity": {"fine": 10.5, "coarse": 10.8},
        },
    )
    result = pipeline.run_refinement(
        screening_result=screening,
        tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
    )
    assert result.phase == "refinement"


def test_pipeline_full_run_auto_mode():
    """Full pipeline in auto mode runs all three phases."""
    config = PipelineConfig(models=["model-a"], mode="auto")
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    with patch.object(pipeline, "run_screening") as mock_s, \
         patch.object(pipeline, "run_confirmation") as mock_c, \
         patch.object(pipeline, "run_refinement") as mock_r:
        mock_s.return_value = PhaseResult(
            run_id="r1", phase="screening", trials=[],
            significant_factors=["structure"], optimal={"structure": "nested"},
        )
        mock_c.return_value = PhaseResult(
            run_id="r2", phase="confirmation", trials=[],
            confirmation={"within_interval": True},
        )
        mock_r.return_value = PhaseResult(
            run_id="r3", phase="refinement", trials=[],
            optimal={"structure": "nested"},
        )
        result = pipeline.run(
            tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
        )
        mock_s.assert_called_once()
        mock_c.assert_called_once()
        mock_r.assert_called_once()
        assert result.pipeline_id == pipeline._pipeline_id


def test_pipeline_semi_mode_emits_phase_complete():
    """Semi mode emits phase_complete callback between phases."""
    approvals = []
    def approve_callback(phase_result):
        approvals.append(phase_result.phase)
        return True  # approve continuation

    config = PipelineConfig(models=["model-a"], mode="semi")
    orch = _make_mock_orchestrator()
    pipeline = DOEPipeline(config=config, orchestrator=orch)

    with patch.object(pipeline, "run_screening") as mock_s, \
         patch.object(pipeline, "run_confirmation") as mock_c, \
         patch.object(pipeline, "run_refinement") as mock_r:
        mock_s.return_value = PhaseResult(
            run_id="r1", phase="screening", trials=[],
            significant_factors=["structure"], optimal={"structure": "nested"},
        )
        mock_c.return_value = PhaseResult(
            run_id="r2", phase="confirmation", trials=[],
            confirmation={"within_interval": True},
        )
        mock_r.return_value = PhaseResult(
            run_id="r3", phase="refinement", trials=[],
        )
        pipeline.run(
            tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
            phase_callback=approve_callback,
        )
        assert "screening" in approvals
        assert "confirmation" in approvals
```

### Step 2: Verify failure

```bash
~/.local/bin/uv run pytest tests/test_pipeline.py::test_pipeline_full_run_auto_mode -v
```

### Step 3: Implement

1. Add `run_refinement()`: builds full factorial combinations for top K factors, fixes others at optimal levels, runs via orchestrator with `phase="refinement"`.
2. Add `run()`: coordinates all three phases. In auto mode, runs sequentially. In semi mode, calls `phase_callback(result)` after each phase — if callback returns False, stops and returns partial PipelineResult.
3. `run()` aggregates total_trials, total_cost, elapsed_seconds across phases and sets `final_optimal` from the best phase result.

### Step 4: Verify

```bash
~/.local/bin/uv run pytest tests/test_pipeline.py -v
```

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/pipeline.py agent-evals/tests/test_pipeline.py
git commit -m "feat(pipeline): implement Phase 3 refinement and full pipeline run

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 11: CLI Flags + Pipeline Routing

**Depends on:** Task 10
**Files:**
- Modify: `src/cli.py` (lines 200–260 flags, lines 672–761 _run_taguchi)
- Test: `tests/test_evals_cli.py`

### Step 1: Write failing tests

```python
# tests/test_evals_cli.py — add

def test_cli_parses_pipeline_flag():
    """--pipeline flag is accepted and stored."""
    parser = build_parser()
    args = parser.parse_args(["--mode", "taguchi", "--pipeline", "auto"])
    assert args.pipeline == "auto"


def test_cli_parses_phase_flag():
    """--phase flag is accepted."""
    parser = build_parser()
    args = parser.parse_args(["--mode", "taguchi", "--phase", "confirmation"])
    assert args.phase == "confirmation"


def test_cli_parses_parent_run():
    """--parent-run flag is accepted."""
    parser = build_parser()
    args = parser.parse_args(["--mode", "taguchi", "--parent-run", "abc123"])
    assert args.parent_run == "abc123"


def test_cli_parses_quality_type():
    """--quality-type flag is accepted."""
    parser = build_parser()
    args = parser.parse_args(["--quality-type", "smaller_is_better"])
    assert args.quality_type == "smaller_is_better"


def test_cli_parses_top_k():
    """--top-k flag is accepted."""
    parser = build_parser()
    args = parser.parse_args(["--top-k", "4"])
    assert args.top_k == 4


def test_cli_parses_alpha():
    """--alpha flag is accepted."""
    parser = build_parser()
    args = parser.parse_args(["--alpha", "0.01"])
    assert args.alpha == 0.01


def test_cli_pipeline_dry_run_shows_plan(capsys):
    """--pipeline --dry-run prints the three-phase plan."""
    with patch("agent_evals.cli._run_evaluation") as mock_run:
        mock_run.return_value = 0
        # This test verifies the dry-run output format
        # The exact implementation depends on how _run_evaluation handles it
```

### Step 2: Verify failure

```bash
~/.local/bin/uv run pytest tests/test_evals_cli.py::test_cli_parses_pipeline_flag -v
```

### Step 3: Implement

1. Add new flags to `build_parser()` after the existing Taguchi flags (after line 260):
   - `--pipeline` choices=["auto", "semi"]
   - `--phase` choices=["screening", "confirmation", "refinement"]
   - `--parent-run` type=str
   - `--quality-type` choices=["larger_is_better", "smaller_is_better", "nominal_is_best"]
   - `--top-k` type=int, default=3
   - `--alpha` type=float, default=0.05

2. In `_run_evaluation()` or `_run_taguchi()`, add routing:
   - If `--pipeline` is set, build `PipelineConfig` and create `DOEPipeline`
   - If `--phase` is set (manual mode), run single phase with `--parent-run`
   - Dry-run for pipeline: show three-phase plan with estimated trial counts

### Step 4: Verify

```bash
~/.local/bin/uv run pytest tests/test_evals_cli.py -v
```

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/cli.py agent-evals/tests/test_evals_cli.py
git commit -m "feat(cli): add --pipeline, --phase, --quality-type, --top-k, --alpha flags

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 12: API Routes for Pipeline Endpoints

**Depends on:** Task 1, Task 10
**Files:**
- Modify: `src/observatory/web/routes.py` (add after line 244)
- Test: `tests/test_observatory_web.py` (or existing web test file)

### Step 1: Write failing tests

```python
# tests/test_observatory_web.py — add

from fastapi.testclient import TestClient

def test_list_pipelines(app_with_store):
    """GET /api/pipelines returns pipeline summaries."""
    client = TestClient(app_with_store)
    response = client.get("/api/pipelines")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_pipeline_detail(app_with_store):
    """GET /api/pipelines/:id returns linked runs."""
    client = TestClient(app_with_store)
    response = client.get("/api/pipelines/pipe-1")
    assert response.status_code == 200


def test_get_run_analysis(app_with_store):
    """GET /api/runs/:id/analysis returns phase results."""
    client = TestClient(app_with_store)
    response = client.get("/api/runs/run-1/analysis")
    assert response.status_code == 200


def test_get_run_analysis_missing(app_with_store):
    """GET /api/runs/:id/analysis returns 404 for unknown run."""
    client = TestClient(app_with_store)
    response = client.get("/api/runs/nonexistent/analysis")
    assert response.status_code == 404
```

### Step 2: Verify failure

```bash
~/.local/bin/uv run pytest tests/test_observatory_web.py::test_list_pipelines -v
```

### Step 3: Implement

Add four new routes to `create_router()` in `routes.py`:

1. `GET /api/pipelines` — Query distinct pipeline_ids from runs table, return summary per pipeline
2. `GET /api/pipelines/{pipeline_id}` — Return all runs in the pipeline with phase results
3. `GET /api/runs/{run_id}/analysis` — Return phase_results for a run (404 if not found)
4. `POST /api/pipelines/{pipeline_id}/approve` — For semi-automatic mode; signal approval to continue (may need an asyncio.Event or similar mechanism)

### Step 4: Verify

```bash
~/.local/bin/uv run pytest tests/test_observatory_web.py -v
```

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/observatory/web/routes.py agent-evals/tests/test_observatory_web.py
git commit -m "feat(web): add pipeline API routes (list, detail, analysis, approve)

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 13: Frontend API Client + Hooks

**Depends on:** Task 12
**Files:**
- Modify: `ui/api/client.ts` (add after line 197)
- Modify: `ui/api/hooks.ts` (add after line 135)
- Test: `ui/src/__tests__/api/client.test.ts`, `ui/src/__tests__/api/hooks.test.ts`

### Step 1: Write failing tests

```typescript
// client.test.ts — add

describe('pipeline endpoints', () => {
  it('fetches pipeline list', async () => {
    fetchMock.mockResponseOnce(JSON.stringify([]));
    const result = await api.listPipelines();
    expect(result).toEqual([]);
    expect(fetchMock).toHaveBeenCalledWith('/api/pipelines', expect.any(Object));
  });

  it('fetches pipeline detail', async () => {
    fetchMock.mockResponseOnce(JSON.stringify({ pipeline_id: 'p1', runs: [] }));
    const result = await api.getPipeline('p1');
    expect(result.pipeline_id).toBe('p1');
  });

  it('fetches run analysis', async () => {
    fetchMock.mockResponseOnce(JSON.stringify({ main_effects: {} }));
    const result = await api.getRunAnalysis('r1');
    expect(result.main_effects).toBeDefined();
  });

  it('approves pipeline phase', async () => {
    fetchMock.mockResponseOnce(JSON.stringify({ status: 'approved' }));
    const result = await api.approvePipeline('p1');
    expect(result.status).toBe('approved');
  });
});
```

```typescript
// hooks.test.ts — add

describe('pipeline hooks', () => {
  it('usePipelines returns query result', () => {
    const { result } = renderHook(() => usePipelines(), { wrapper });
    expect(result.current.isLoading).toBe(true);
  });

  it('usePipeline fetches single pipeline', () => {
    const { result } = renderHook(() => usePipeline('p1'), { wrapper });
    expect(result.current.isLoading).toBe(true);
  });

  it('useRunAnalysis fetches analysis data', () => {
    const { result } = renderHook(() => useRunAnalysis('r1'), { wrapper });
    expect(result.current.isLoading).toBe(true);
  });
});
```

### Step 2: Verify failure

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run src/__tests__/api/client.test.ts
```

### Step 3: Implement

**In `client.ts`**, add types and methods:

```typescript
// Types
export interface Pipeline { pipeline_id: string; runs: Run[]; phase: string; }
export interface PhaseResults {
  main_effects: Record<string, Record<string, number>>;
  anova: Record<string, { p_value: number; omega_squared: number }>;
  optimal: Record<string, string>;
  significant_factors: string[];
  confirmation?: { within_interval: boolean; sigma_deviation: number };
}

// Methods on api object
listPipelines: () => fetchApi<Pipeline[]>('/api/pipelines'),
getPipeline: (id: string) => fetchApi<Pipeline>(`/api/pipelines/${id}`),
getRunAnalysis: (runId: string) => fetchApi<PhaseResults>(`/api/runs/${runId}/analysis`),
approvePipeline: (id: string) => fetchApi<{status: string}>(`/api/pipelines/${id}/approve`, { method: 'POST' }),
```

**In `hooks.ts`**, add hooks:

```typescript
export function usePipelines() {
  return useQuery({ queryKey: ['pipelines'], queryFn: () => api.listPipelines() });
}
export function usePipeline(id: string) {
  return useQuery({ queryKey: ['pipeline', id], queryFn: () => api.getPipeline(id), enabled: !!id });
}
export function useRunAnalysis(runId: string) {
  return useQuery({ queryKey: ['analysis', runId], queryFn: () => api.getRunAnalysis(runId), enabled: !!runId });
}
export function useApprovePipeline() {
  return useMutation({ mutationFn: (id: string) => api.approvePipeline(id) });
}
```

### Step 4: Verify

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run
```

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/api/
git commit -m "feat(web): add pipeline API client methods and TanStack Query hooks

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 14: Frontend — Factor Analysis Page

**Depends on:** Task 13
**Files:**
- Create: `ui/pages/FactorAnalysis.tsx`
- Test: `ui/src/__tests__/pages/FactorAnalysis.test.tsx`

### Step 1: Write failing test

```typescript
// FactorAnalysis.test.tsx

import { render, screen } from '@testing-library/react';
import { FactorAnalysis } from '../pages/FactorAnalysis';

// Mock useRunAnalysis to return test data
vi.mock('../api/hooks', () => ({
  useRunAnalysis: () => ({
    data: {
      main_effects: { structure: { flat: 10.0, nested: 12.3 } },
      anova: { structure: { p_value: 0.001, omega_squared: 0.089 } },
      optimal: { structure: 'nested' },
      significant_factors: ['structure'],
    },
    isLoading: false,
  }),
}));

describe('FactorAnalysis', () => {
  it('renders main effects chart heading', () => {
    render(<FactorAnalysis />);
    expect(screen.getByText(/Main Effects/i)).toBeInTheDocument();
  });

  it('renders ANOVA table', () => {
    render(<FactorAnalysis />);
    expect(screen.getByText(/ANOVA/i)).toBeInTheDocument();
  });

  it('marks significant factors', () => {
    render(<FactorAnalysis />);
    expect(screen.getByText(/Significant/i)).toBeInTheDocument();
  });

  it('shows optimal prediction', () => {
    render(<FactorAnalysis />);
    expect(screen.getByText(/Optimal/i)).toBeInTheDocument();
    expect(screen.getByText(/nested/)).toBeInTheDocument();
  });
});
```

### Step 2: Verify failure

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run src/__tests__/pages/FactorAnalysis.test.tsx
```

### Step 3: Implement

Create `ui/pages/FactorAnalysis.tsx` with three panels:
1. **Main Effects Chart** — Chart.js bar chart of S/N per level per factor
2. **ANOVA Table** — DataTable with Factor, SS, df, MS, F, p-value, omega², significance badge
3. **Optimal Prediction** — Card showing the best level for each factor

Use `useParams()` for `runId`, `useRunAnalysis(runId)` for data. Follow existing page patterns (Card, DataTable, StatusBadge components).

### Step 4: Verify

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npx vitest run
```

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/pages/FactorAnalysis.tsx \
        agent-evals/src/agent_evals/observatory/web/ui/src/__tests__/pages/FactorAnalysis.test.tsx
git commit -m "feat(web): add Factor Analysis page with main effects, ANOVA, optimal prediction

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 15: Frontend — Pipeline View Page

**Depends on:** Task 13
**Files:**
- Create: `ui/pages/PipelineView.tsx`
- Test: `ui/src/__tests__/pages/PipelineView.test.tsx`

### Step 1: Write failing test

```typescript
// PipelineView.test.tsx

import { render, screen } from '@testing-library/react';
import { PipelineView } from '../pages/PipelineView';

vi.mock('../api/hooks', () => ({
  usePipeline: () => ({
    data: {
      pipeline_id: 'pipe-1',
      runs: [
        { run_id: 'r1', phase: 'screening', status: 'completed' },
        { run_id: 'r2', phase: 'confirmation', status: 'completed' },
        { run_id: 'r3', phase: 'refinement', status: 'active' },
      ],
    },
    isLoading: false,
  }),
}));

describe('PipelineView', () => {
  it('renders three phase nodes', () => {
    render(<PipelineView />);
    expect(screen.getByText(/Screening/i)).toBeInTheDocument();
    expect(screen.getByText(/Confirmation/i)).toBeInTheDocument();
    expect(screen.getByText(/Refinement/i)).toBeInTheDocument();
  });

  it('shows phase status indicators', () => {
    render(<PipelineView />);
    // Completed phases should show complete status
    const completedBadges = screen.getAllByText(/completed/i);
    expect(completedBadges.length).toBeGreaterThanOrEqual(2);
  });

  it('renders pipeline ID', () => {
    render(<PipelineView />);
    expect(screen.getByText(/pipe-1/)).toBeInTheDocument();
  });
});
```

### Step 2: Verify failure

### Step 3: Implement

Create `ui/pages/PipelineView.tsx`:
- Horizontal timeline with three phase cards connected by arrows
- Each card shows: phase name, StatusDot, run_id, status
- Click a phase card → navigate to `/analysis/:runId` or `/results/:runId`
- Use `useParams()` for `pipelineId`, `usePipeline(pipelineId)` for data

### Step 4–5: Verify + Commit

```bash
git commit -m "feat(web): add Pipeline View page with phase timeline

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 16: Frontend — Update ResultsExplorer with Factor Tab

**Depends on:** Task 14
**Files:**
- Modify: `ui/pages/ResultsExplorer.tsx` (lines 52–225)
- Test: `ui/src/__tests__/pages/ResultsExplorer.test.tsx`

### Step 1: Write failing test

```typescript
// ResultsExplorer.test.tsx — add

it('shows Factor Analysis tab for Taguchi runs', () => {
  // Mock useRun to return a run with phase_results
  render(<ResultsExplorer />);
  expect(screen.getByText(/Factor Analysis/i)).toBeInTheDocument();
});

it('hides Factor Analysis tab for non-Taguchi runs', () => {
  // Mock useRun without phase_results
  render(<ResultsExplorer />);
  expect(screen.queryByText(/Factor Analysis/i)).not.toBeInTheDocument();
});
```

### Step 2: Verify failure

### Step 3: Implement

Add a tab bar to ResultsExplorer: "Overview" | "Factor Analysis" (shown only when run has phase_results). The Factor Analysis tab embeds the ANOVA table and optimal prediction card inline (reuse components from FactorAnalysis page or extract shared components).

### Step 4–5: Verify + Commit

```bash
git commit -m "feat(web): add Factor Analysis tab to ResultsExplorer for Taguchi runs

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 17: Frontend — Update RunConfig with Pipeline Options

**Depends on:** Task 13
**Files:**
- Modify: `ui/pages/RunConfig.tsx` (lines 12–181)
- Test: `ui/src/__tests__/pages/RunConfig.test.tsx`

### Step 1: Write failing test

```typescript
// RunConfig.test.tsx — add

it('shows pipeline options when Taguchi mode selected', async () => {
  render(<RunConfig />);
  // Select Taguchi mode
  await userEvent.selectOptions(screen.getByLabelText(/Mode/i), 'taguchi');
  expect(screen.getByLabelText(/Pipeline/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/Quality Type/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/Top-K/i)).toBeInTheDocument();
});

it('hides pipeline options for full mode', () => {
  render(<RunConfig />);
  expect(screen.queryByLabelText(/Pipeline/i)).not.toBeInTheDocument();
});
```

### Step 2: Verify failure

### Step 3: Implement

Add conditional fields in RunConfig form that appear when mode === "taguchi":
- Pipeline mode: select (auto / semi)
- Quality type: select (larger_is_better / smaller_is_better / nominal_is_best)
- Top-K: number input (default 3)
- Alpha: number input (default 0.05)

### Step 4–5: Verify + Commit

```bash
git commit -m "feat(web): add pipeline options to RunConfig for Taguchi mode

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 18: Frontend — App.tsx Routing

**Depends on:** Task 14, Task 15
**Files:**
- Modify: `ui/App.tsx` (lines 18–65)
- Test: `ui/src/__tests__/App.test.tsx`

### Step 1: Write failing test

```typescript
// App.test.tsx — add or modify

it('routes /analysis/:runId to FactorAnalysis page', () => {
  renderWithRouter('/analysis/test-run');
  expect(screen.getByText(/Main Effects/i)).toBeInTheDocument();
});

it('routes /pipeline/:pipelineId to PipelineView page', () => {
  renderWithRouter('/pipeline/pipe-1');
  expect(screen.getByText(/Screening/i)).toBeInTheDocument();
});

it('includes Analysis and Pipeline in navigation', () => {
  renderWithRouter('/');
  expect(screen.getByText(/Analysis/i)).toBeInTheDocument();
  expect(screen.getByText(/Pipeline/i)).toBeInTheDocument();
});
```

### Step 2: Verify failure

### Step 3: Implement

1. Import `FactorAnalysis` and `PipelineView` pages
2. Add routes: `/analysis/:runId` → `FactorAnalysis`, `/pipeline/:pipelineId?` → `PipelineView`
3. Add nav items for Analysis and Pipeline

### Step 4–5: Verify + Commit

```bash
git commit -m "feat(web): add Factor Analysis and Pipeline routes to App.tsx

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 19: Integration Tests + Dry-Run Validation

**Depends on:** All previous tasks
**Files:**
- Create: `tests/test_pipeline_integration.py`

### Step 1: Write integration tests

```python
# tests/test_pipeline_integration.py

"""End-to-end integration tests for the DOE pipeline."""

import subprocess


def test_all_python_tests_pass():
    """Full test suite passes with no regressions."""
    result = subprocess.run(
        ["uv", "run", "pytest", "--tb=short", "-q"],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, f"Tests failed:\n{result.stdout}\n{result.stderr}"


def test_frontend_tests_pass():
    """All frontend tests pass."""
    result = subprocess.run(
        ["npx", "vitest", "run"],
        capture_output=True, text=True, timeout=60,
        cwd="agent-evals/src/agent_evals/observatory/web/ui",
    )
    assert result.returncode == 0


def test_dry_run_pipeline_shows_plan():
    """--pipeline auto --dry-run prints three-phase plan."""
    result = subprocess.run(
        [
            "uv", "run", "agent-evals",
            "--mode", "taguchi",
            "--pipeline", "auto",
            "--model", "openrouter/arcee-ai/trinity-large-preview:free",
            "--dry-run",
        ],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    assert "Phase 1" in result.stdout
    assert "Phase 2" in result.stdout
    assert "Phase 3" in result.stdout
    assert "Screening" in result.stdout


def test_typescript_compiles():
    """TypeScript compiles without errors."""
    result = subprocess.run(
        ["npx", "tsc", "--noEmit"],
        capture_output=True, text=True, timeout=30,
        cwd="agent-evals/src/agent_evals/observatory/web/ui",
    )
    assert result.returncode == 0, f"TypeScript errors:\n{result.stdout}"
```

### Step 2: Run and verify all pass

```bash
~/.local/bin/uv run pytest tests/test_pipeline_integration.py -v
```

### Step 3: Commit

```bash
git add agent-evals/tests/test_pipeline_integration.py
git commit -m "test: add DOE pipeline integration tests and dry-run validation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Summary

| Task | Name | Depends On | Parallel Stream |
|------|------|-----------|-----------------|
| 1 | Schema migration | — | A (foundation) |
| 2 | Pipeline data models | — | A (foundation) |
| 3 | Runner phase metadata | 1 | B-stream1 |
| 4 | Orchestrator phase routing | 1, 3 | B-stream1 |
| 5 | Report aggregator phase_results | 1 | B-stream2 |
| 6 | HTML renderer sections 10–14 | 5 | B-stream2 |
| 7 | MD renderer sections 10–14 | 5 | B-stream2 |
| 8 | DOEPipeline Phase 1 screening | 2, 3, 4 | B-stream3 |
| 9 | DOEPipeline Phase 2 confirmation | 8 | B-stream3 |
| 10 | DOEPipeline Phase 3 + full run | 9 | B-stream3 |
| 11 | CLI flags + pipeline routing | 10 | C |
| 12 | API routes | 1, 10 | C |
| 13 | Frontend API client + hooks | 12 | D-stream1 |
| 14 | Factor Analysis page | 13 | D-stream1 |
| 15 | Pipeline View page | 13 | D-stream2 |
| 16 | ResultsExplorer update | 14 | D-stream1 |
| 17 | RunConfig update | 13 | D-stream2 |
| 18 | App.tsx routing | 14, 15 | D |
| 19 | Integration tests | All | E |
