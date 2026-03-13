# Backlog Cleanup Sprint: Beads 109, 106, 95, 94, 52, 53

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close 6 open beads — 2 quick-win tasks (config docs + cost display), 2 partial integrations (judge graduation + multi-objective wiring), and 2 newly-unblocked analysis features (train/test split + difficulty validation).

**Architecture:** Tasks 1-2 are self-contained edits to existing files. Tasks 3-4 wire existing modules into the pipeline/runner. Tasks 5-6 add new modules for post-hoc analysis of evaluation data.

**Tech Stack:** Python 3.11+, pytest, Pydantic v2

---

## Task 1: Complete full-config.yaml (Bead 109)

**Files:**
- Modify: `agent-evals/examples/full-config.yaml`
- Test: `agent-evals/tests/test_evals_cli.py` (existing tests validate config loading — no new tests needed)

**Step 1: Read the current CLI flags for reference**

Run: `grep -n "add_argument" agent-evals/src/agent_evals/cli.py | head -60`
Cross-reference with the `_CONFIG_KEYS` dict (around line 500 in cli.py) — only keys in that dict are valid YAML config keys.

**Step 2: Rewrite full-config.yaml with all sections**

Replace the contents of `agent-evals/examples/full-config.yaml` with:

```yaml
# full-config.yaml — All configuration options for agent-evals
# Usage: agent-evals --config examples/full-config.yaml
#
# Precedence: CLI args > environment variables (AGENT_EVALS_ prefix) > this file > defaults
# Commented-out lines show defaults or optional settings.

# === LLM Settings ===
model: openrouter/anthropic/claude-sonnet-4.5  # Required: provider/model format
temperature: 0.3                                # Sampling temperature (0.0-1.0)
max_tokens: 2048                                # Max tokens per completion (YAML-only)

# === Evaluation Scope ===
# axis: 1                       # Run only variants for axis N (1-10)
# tasks: retrieval,agentic      # Filter to specific task types (comma-separated)
# task_id: retrieval_001        # Run a single task by ID (debugging)
# variant: scale_50             # Run a single variant by name (debugging)
# limit: 5                      # Max tasks per type

# === Execution ===
repetitions: 10                  # Trials per (task, variant) pair
max_connections: 10              # Concurrent API connections
max_tasks: 1                     # Parallel task evaluation threads
continue_on_error: false         # Skip failed trials instead of aborting
# dry_run: false                 # Estimate tokens and cost without API calls

# === Mode & Design ===
mode: taguchi                    # taguchi (default) or full (Cartesian product)
# oa_type: L121                  # Force specific orthogonal array (e.g., L50, L54, L121)

# === Multi-Model ===
# models: openrouter/anthropic/claude-sonnet-4.5,openrouter/openai/gpt-4o
#   # Comma-separated list. In taguchi mode, "model" becomes a design factor.
# model_group: fast-models       # Logical group name for reporting

# === Pipeline (DOE phases) ===
# Requires mode: taguchi
# pipeline: auto                 # auto (3-phase) or semi (pause between phases)
# quality_type: larger_is_better # larger_is_better | smaller_is_better | nominal_is_best
# top_k: 3                       # Top N factors for Phase 3 refinement
# alpha: 0.05                    # ANOVA significance threshold
# split_ratio: 0.8               # Train/test split ratio (screening=train, confirmation=test)
# split_seed: 42                 # Random seed for split reproducibility

# === Data Sources ===
source: gold_standard            # gold_standard | legacy | adapter name | comma-list
# dataset_limit: 100             # Max tasks per dataset source
# dataset_cache_dir: /data/huggingface  # Override HF cache directory

# === Cost Control ===
# budget: 5.00                   # Total cost cap in dollars
# model_budgets: "openrouter/anthropic/claude-sonnet-4.5=3.00,openrouter/openai/gpt-4o=2.00"
# no_cache: false                 # Disable LLM response caching (CLI: --no-cache)
cache_dir: .agent-evals-cache    # Cache directory (YAML-only)

# === Judge (LLM-as-Judge) ===
# judge_enabled: true            # Enable LLM-as-judge scoring
# judge_model: openrouter/openai/gpt-4o-mini  # Judge model
# judge_mode: routine            # routine (single model) or poll (3-model panel)
# judge_sample_rate: 20          # 1-in-N trials sent to judge (20 = 5%)
# judge_primary_types: code_generation,agentic  # Types using judge as primary scorer
# judge_graduation: false        # Blend judge scores into trial.score (requires judge_enabled)
# judge_graduation_weight: 0.3   # Judge weight in blended scoring (0.0=heuristic, 1.0=judge)

# === Context Strategy ===
# context_strategy: full_context  # full_context | system_prompt | rag | tool_based
# strategies: "full_context,rag,tool_based"  # Multi-strategy pipeline (comma-separated)
# strategy_reps: "rag=5,tool_based=3"        # Per-strategy rep overrides
#
# Strategy sub-parameters (YAML-only, not available via CLI):
# strategy_config:
#   token_budget: 4096
#   chunk_method: semantic
#   chunk_size: 512
#   top_k_chunks: 5

# === Output ===
output_dir: reports              # Directory for results
output_format: both              # json | csv | both
display: rich                    # Progress display: rich | plain | none
# report: both                   # html | markdown | both | none

# === Observatory ===
# store_traces: true             # Store prompt/response in SQLite DB

# === Resume ===
# resume: "abc123"               # Resume a crashed run by run_id
# resume_pipeline: "pipe456"     # Resume a pipeline by pipeline_id
```

> **Note:** Dashboard flags (`--dashboard`, `--port`, `--host`, `--db-dir`) are subcommand-specific
> (`agent-evals dashboard`) and not supported in the config YAML. Logging flags
> (`--verbose`, `--quiet`) are also CLI-only.

**Step 3: Verify config loads correctly**

Run: `cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing && uv run pytest agent-evals/tests/test_evals_cli.py::TestLoadConfig::test_parses_full_config -v`
Expected: PASS

**Step 4: Commit**

```bash
git add agent-evals/examples/full-config.yaml
git commit -m "docs: complete full-config.yaml with all Taguchi/pipeline/observatory options

Closes bead 109."
```

---

## Task 2: Show Running Cost in Progress Callbacks (Bead 106)

**Files:**
- Modify: `agent-evals/src/agent_evals/progress.py`
- Modify: `agent-evals/src/agent_evals/orchestrator.py` (wire display callback into _on_trial_progress)
- Test: `agent-evals/tests/test_progress.py`

### Architecture Note

The progress display flow is:
1. `orchestrator.run()` defines `_on_trial_progress()` (stores trials in observatory)
2. This callback is passed to `EvalRunner.run()` as `progress_callback`
3. Runner calls `progress_callback(completed, total, trial)` after each trial
4. `make_progress_callback()` in `progress.py` creates display-only callbacks but is **currently not called anywhere**

The fix wires `make_progress_callback()` into the orchestrator so both store AND display happen. Cost accumulation uses a closure — no separate CostTracker needed.

### Step 1: Write the failing tests

Add to `agent-evals/tests/test_progress.py`:

```python
class TestCostDisplay:
    """Tests for cost display in progress callbacks."""

    def test_plain_callback_shows_cost(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Plain callback displays accumulated cost."""
        cb = make_progress_callback("plain", budget=None)
        assert cb is not None
        t1 = MagicMock(spec=TrialResult, task_id="t1", variant_name="v1", score=0.8, cost=0.05)
        t2 = MagicMock(spec=TrialResult, task_id="t2", variant_name="v1", score=0.9, cost=0.03)
        with caplog.at_level(logging.INFO, logger="agent_evals"):
            cb(1, 100, t1)
            cb(2, 100, t2)
        assert "$0.08" in caplog.text

    def test_rich_callback_shows_cost_and_budget(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Rich callback displays cost and budget percentage."""
        cb = make_progress_callback("rich", budget=2.0)
        assert cb is not None
        trial = MagicMock(spec=TrialResult, task_id="t1", variant_name="v1", score=0.9, cost=0.42)
        with caplog.at_level(logging.INFO, logger="agent_evals"):
            cb(1, 10, trial)
        assert "$0.42" in caplog.text
        assert "21%" in caplog.text

    def test_rich_callback_no_budget_omits_percentage(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """When no budget set, show cost without budget percentage."""
        cb = make_progress_callback("rich", budget=None)
        assert cb is not None
        trial = MagicMock(spec=TrialResult, task_id="t1", variant_name="v1", score=0.75, cost=1.23)
        with caplog.at_level(logging.INFO, logger="agent_evals"):
            cb(1, 50, trial)
        assert "$1.23" in caplog.text

    def test_none_mode_with_budget_returns_none(self) -> None:
        """Display mode 'none' returns None even with budget."""
        cb = make_progress_callback("none", budget=5.0)
        assert cb is None

    def test_cost_accumulates_across_calls(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Cost accumulates across successive callback invocations."""
        cb = make_progress_callback("plain", budget=None)
        assert cb is not None
        for i in range(1, 6):
            trial = MagicMock(spec=TrialResult, task_id=f"t{i}", variant_name="v1", score=0.5, cost=0.10)
            with caplog.at_level(logging.INFO, logger="agent_evals"):
                cb(i, 10, trial)
        assert "$0.50" in caplog.text

    def test_none_cost_treated_as_zero(
        self, caplog: pytest.LogCaptureFixture,
    ) -> None:
        """trial.cost=None should not crash and is treated as $0."""
        cb = make_progress_callback("plain", budget=None)
        assert cb is not None
        trial = MagicMock(spec=TrialResult, task_id="t1", variant_name="v1", score=0.5, cost=None)
        with caplog.at_level(logging.INFO, logger="agent_evals"):
            cb(1, 10, trial)
        assert "$0.00" in caplog.text
```

### Step 2: Run tests to verify they fail

Run: `cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing && uv run pytest agent-evals/tests/test_progress.py::TestCostDisplay -v`
Expected: FAIL — `make_progress_callback` doesn't accept `budget` parameter

### Step 3: Implement cost-aware callbacks

Replace `agent-evals/src/agent_evals/progress.py` with:

```python
"""Progress display callbacks for evaluation runs."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_evals.runner import ProgressCallback, TrialResult

logger = logging.getLogger(__name__)


def _plain_callback(completed: int, total: int, trial: TrialResult) -> None:
    logger.info(
        "[%d/%d] %s | %s | score=%.2f",
        completed,
        total,
        trial.task_id,
        trial.variant_name,
        trial.score,
    )


def _rich_callback(completed: int, total: int, trial: TrialResult) -> None:
    pct = (completed / total * 100) if total > 0 else 0
    bar_width = 20
    filled = int(bar_width * completed / total) if total > 0 else 0
    bar = "#" * filled + "-" * (bar_width - filled)
    logger.info(
        "[%s] %3.0f%% (%d/%d) %s | %s | %.2f",
        bar,
        pct,
        completed,
        total,
        trial.task_id,
        trial.variant_name,
        trial.score,
    )


def _make_cost_callback(
    base: str,
    budget: float | None,
) -> ProgressCallback:
    """Create a closure-based callback that accumulates and displays cost."""
    state = {"cost": 0.0}

    def _plain_cost(completed: int, total: int, trial: TrialResult) -> None:
        state["cost"] += trial.cost or 0.0
        cost_str = f"${state['cost']:.2f}"
        logger.info(
            "[%d/%d] %s | %s | score=%.2f | %s",
            completed,
            total,
            trial.task_id,
            trial.variant_name,
            trial.score,
            cost_str,
        )

    def _rich_cost(completed: int, total: int, trial: TrialResult) -> None:
        state["cost"] += trial.cost or 0.0
        pct = (completed / total * 100) if total > 0 else 0
        bar_width = 20
        filled = int(bar_width * completed / total) if total > 0 else 0
        bar = "#" * filled + "-" * (bar_width - filled)
        cost_str = f"${state['cost']:.2f}"
        if budget is not None and budget > 0:
            budget_pct = int(state["cost"] / budget * 100)
            cost_str += f"/${budget:.2f} ({budget_pct}%)"
        logger.info(
            "[%s] %3.0f%% (%d/%d) %s | %s | %.2f | %s",
            bar,
            pct,
            completed,
            total,
            trial.task_id,
            trial.variant_name,
            trial.score,
            cost_str,
        )

    return _plain_cost if base == "plain" else _rich_cost


def make_progress_callback(
    display_mode: str,
    budget: float | None = None,
) -> ProgressCallback | None:
    """Create a progress callback based on display mode.

    Args:
        display_mode: One of "rich", "plain", or "none".
        budget: Optional budget in dollars for percentage display.

    Returns:
        A callback function or None if display_mode is "none".
    """
    if display_mode == "none":
        return None
    if budget is not None:
        return _make_cost_callback(display_mode, budget)
    if display_mode == "plain":
        return _plain_callback
    return _rich_callback
```

### Step 4: Wire display callback into orchestrator

In `agent-evals/src/agent_evals/orchestrator.py`, find the `run()` method where `_on_trial_progress` is defined. After the existing `_on_trial_progress` definition, add display callback chaining:

```python
        # Display callback for progress output
        from agent_evals.progress import make_progress_callback
        display_cb = make_progress_callback(
            eval_config.display_mode, budget=eval_config.budget,
        )

        def _on_trial_progress(
            completed: int, total: int, trial: TrialResult,
        ) -> None:
            # ... existing store logic stays here ...
            # Add display at the end:
            if display_cb is not None:
                display_cb(completed, total, trial)
```

> **Important:** Check how `_on_trial_progress` is currently defined in orchestrator.py.
> The display call should be added at the END of the existing function body,
> not replacing any existing logic.

### Step 5: Run tests to verify they pass

Run: `cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing && uv run pytest agent-evals/tests/test_progress.py -v`
Expected: ALL PASS (existing tests still pass since `budget=None` returns old callbacks)

### Step 6: Run full test suite

Run: `cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing && uv run pytest agent-evals/tests/ -x -q`
Expected: ALL PASS

### Step 7: Commit

```bash
git add agent-evals/src/agent_evals/progress.py agent-evals/src/agent_evals/orchestrator.py agent-evals/tests/test_progress.py
git commit -m "feat: display running cost and budget % in progress callbacks

Uses closure-based cost accumulation in progress callbacks.
When budget is set, shows cost/budget (percentage).
Wired into orchestrator's _on_trial_progress for live display.

Closes bead 106."
```

---

## Task 3: Graduate Judge Scores into Trial Scoring (Bead 95)

**Files:**
- Modify: `agent-evals/src/agent_evals/runner.py` (EvalRunConfig + _run_trial)
- Modify: `agent-evals/src/agent_evals/cli.py` (new flags + _CONFIG_KEYS + build_eval_run_config)
- Modify: `agent-evals/src/agent_evals/pipeline.py:33-43` (_effective_score — respect graduation)
- Test: `agent-evals/tests/test_runner_judge.py`
- Test: `agent-evals/tests/test_judge_graduation.py` (existing — no changes)

### Architecture Decision

**Conflict resolution:** The pipeline's `_effective_score()` (pipeline.py:33-43) already returns `judge_score` for judge-primary types. The runner's `_run_trial` will now blend scores at trial creation time. To avoid dual graduation:

- **Runner:** Blends scores using `blend_scores()` when graduation is enabled. Sets `trial.score` to the blended value. Stores `metrics["graduation_applied"] = True`.
- **Pipeline:** `_effective_score()` checks for `metrics["graduation_applied"]` — if present, uses `trial.score` directly (already graduated). Otherwise falls back to current behavior.

### Step 1: Write failing tests for graduation integration

Add to `agent-evals/tests/test_runner_judge.py`:

```python
class TestJudgeGraduation:
    """Tests for judge score graduation into trial.score."""

    def test_graduation_config_fields_exist(self):
        """EvalRunConfig accepts graduation fields."""
        config = EvalRunConfig(
            judge_enabled=True,
            judge_graduation_enabled=True,
            judge_graduation_weight=0.5,
        )
        assert config.judge_graduation_enabled is True
        assert config.judge_graduation_weight == 0.5

    def test_graduation_disabled_by_default(self):
        """Graduation is off by default."""
        config = EvalRunConfig()
        assert config.judge_graduation_enabled is False

    def test_graduation_weight_validation(self):
        """Weight must be between 0.0 and 1.0."""
        with pytest.raises(ValueError, match="judge_graduation_weight"):
            EvalRunConfig(judge_graduation_weight=1.5)
        with pytest.raises(ValueError, match="judge_graduation_weight"):
            EvalRunConfig(judge_graduation_weight=-0.1)

    def test_graduation_requires_judge_enabled(self):
        """Cannot enable graduation without enabling judge."""
        with pytest.raises(ValueError, match="judge_enabled"):
            EvalRunConfig(
                judge_enabled=False,
                judge_graduation_enabled=True,
            )
```

### Step 2: Run tests to verify they fail

Run: `cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing && uv run pytest agent-evals/tests/test_runner_judge.py::TestJudgeGraduation -v`
Expected: FAIL — `EvalRunConfig` doesn't accept graduation fields

### Step 3: Add graduation fields to EvalRunConfig

In `agent-evals/src/agent_evals/runner.py`, add after `judge_primary_types` (line 135):

```python
    judge_graduation_enabled: bool = False
    judge_graduation_weight: float = 0.3
```

Add validation in `__post_init__()` (after line 164):

```python
        if not 0.0 <= self.judge_graduation_weight <= 1.0:
            raise ValueError(
                f"judge_graduation_weight must be in [0.0, 1.0], "
                f"got {self.judge_graduation_weight}"
            )
        if self.judge_graduation_enabled and not self.judge_enabled:
            raise ValueError(
                "judge_graduation_enabled requires judge_enabled=True"
            )
```

### Step 4: Run tests to verify they pass

Run: `cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing && uv run pytest agent-evals/tests/test_runner_judge.py::TestJudgeGraduation -v`
Expected: ALL PASS

### Step 5: Wire graduation into _run_trial score assignment

In `runner.py`, at the top of the file (with other imports from judge), add:

```python
from agent_evals.judge_graduation import blend_scores
```

Then in `_run_trial`, after the judge scoring block (after line 1112), before `return TrialResult(...)` at line 1114:

```python
        # Judge graduation: blend judge score into trial.score
        final_score = score
        if (
            self._config.judge_graduation_enabled
            and "judge_score" in metrics
        ):
            weight = (
                1.0 if is_judge_primary
                else self._config.judge_graduation_weight
            )
            final_score = blend_scores(score, metrics["judge_score"], weight)
            metrics["graduation_applied"] = True
            metrics["graduation_weight"] = weight
            metrics["pre_graduation_score"] = score
```

Then change `score=score` to `score=final_score` in the TrialResult constructor at line 1119.

### Step 6: Update pipeline's _effective_score to respect graduation

In `pipeline.py`, modify `_effective_score()` (lines 33-43):

```python
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
```

### Step 7: Add CLI flags and wire config resolution

In `cli.py`, add to the argparse section (near existing judge flags, around line 210):

```python
parser.add_argument(
    "--judge-graduation",
    action="store_true",
    default=False,
    help="Enable judge score graduation into trial.score (requires --judge-enabled)",
)
parser.add_argument(
    "--judge-graduation-weight",
    type=float,
    default=0.3,
    help="Weight for judge score in blended scoring (0.0=all heuristic, 1.0=all judge)",
)
```

Add to `_CONFIG_KEYS` dict (around line 540):

```python
"judge_graduation": bool,
"judge_graduation_weight": float,
```

Wire in `build_eval_run_config()` — map `judge_graduation` to `judge_graduation_enabled`:

```python
    judge_graduation_enabled=resolved.get("judge_graduation", False),
    judge_graduation_weight=resolved.get("judge_graduation_weight", 0.3),
```

### Step 8: Run full test suite

Run: `cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing && uv run pytest agent-evals/tests/ -x -q`
Expected: ALL PASS

### Step 9: Commit

```bash
git add agent-evals/src/agent_evals/runner.py agent-evals/src/agent_evals/pipeline.py agent-evals/src/agent_evals/cli.py agent-evals/tests/test_runner_judge.py
git commit -m "feat: graduate judge scores into trial.score when enabled

Adds --judge-graduation and --judge-graduation-weight CLI flags.
When enabled, blends programmatic and judge scores using configured weight.
Judge-primary types use weight=1.0 (full judge scoring).
Pipeline's _effective_score respects graduation_applied flag to avoid
double-scoring.

Closes bead 95."
```

---

## Task 4: Wire Multi-Objective Analysis into Pipeline (Bead 94)

**Files:**
- Modify: `agent-evals/src/agent_evals/pipeline.py` (imports, PhaseResult, run_screening)
- Test: `agent-evals/tests/test_pipeline.py`

### Step 1: Write the failing test

Add to `agent-evals/tests/test_pipeline.py`, using the existing test pattern (module-level functions with helper setup):

```python
@patch("agent_evals.pipeline.run_multi_objective_analysis")
@patch("agent_evals.pipeline.predict_optimal")
@patch("agent_evals.pipeline.run_anova")
@patch("agent_evals.pipeline.compute_main_effects")
@patch("agent_evals.pipeline.compute_sn_ratios")
@patch("agent_evals.pipeline.build_design")
def test_screening_populates_multi_objective(
    mock_build, mock_sn, mock_me, mock_anova, mock_pred, mock_mo,
):
    """Screening phase calls run_multi_objective_analysis with row costs/latencies."""
    mock_build.return_value = MagicMock()
    mock_sn.return_value = {0: 10.0}
    mock_me.return_value = {}
    mock_anova.return_value = MagicMock(factors=[])
    mock_pred.return_value = MagicMock(optimal_assignment={})
    mock_mo.return_value = {
        "accuracy": {"sn_ratios": {0: 10.0}},
        "cost": {"sn_ratios": {0: -5.0}},
        "latency": {"sn_ratios": {0: -3.0}},
    }

    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    # Ensure mock trials have cost and latency data
    for trial in orch.run.return_value.trials:
        trial.cost = 0.05
        trial.latency_seconds = 1.5
        trial.error = None

    pipeline = DOEPipeline(config=config, orchestrator=orch)
    result = pipeline.run_screening(
        tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
    )

    mock_mo.assert_called_once()
    assert result.multi_objective is not None


@patch("agent_evals.pipeline.run_multi_objective_analysis")
@patch("agent_evals.pipeline.predict_optimal")
@patch("agent_evals.pipeline.run_anova")
@patch("agent_evals.pipeline.compute_main_effects")
@patch("agent_evals.pipeline.compute_sn_ratios")
@patch("agent_evals.pipeline.build_design")
def test_screening_multi_objective_skips_empty_cost(
    mock_build, mock_sn, mock_me, mock_anova, mock_pred, mock_mo,
):
    """Multi-objective still called when cost is None (accuracy-only result)."""
    mock_build.return_value = MagicMock()
    mock_sn.return_value = {0: 10.0}
    mock_me.return_value = {}
    mock_anova.return_value = MagicMock(factors=[])
    mock_pred.return_value = MagicMock(optimal_assignment={})
    mock_mo.return_value = {"accuracy": {"sn_ratios": {0: 10.0}}}

    config = PipelineConfig(models=["model-a"])
    orch = _make_mock_orchestrator()
    for trial in orch.run.return_value.trials:
        trial.cost = None
        trial.latency_seconds = 0.0
        trial.error = None

    pipeline = DOEPipeline(config=config, orchestrator=orch)
    result = pipeline.run_screening(
        tasks=[], variants=_make_variants(), doc_tree=MagicMock(),
    )

    mock_mo.assert_called_once()
    assert result.multi_objective is not None
```

### Step 2: Run tests to verify they fail

Run: `cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing && uv run pytest agent-evals/tests/test_pipeline.py::test_screening_populates_multi_objective -v`
Expected: FAIL — `run_multi_objective_analysis` not imported in pipeline, `PhaseResult` has no `multi_objective`

### Step 3: Add multi_objective field to PhaseResult and import

In `pipeline.py`, add import at the top (with existing taguchi imports):

```python
from agent_evals.taguchi.multi_objective import run_multi_objective_analysis
```

Add field to `PhaseResult` dataclass (after `trial_count` field, around line 102):

```python
    multi_objective: dict[str, dict] | None = None
```

### Step 4: Collect cost/latency per row and call multi_objective in run_screening

In `pipeline.py`, after the `row_scores` loop (after line 468, before the "6-9. Statistical analysis" comment at line 470), add:

```python
        # Collect cost and latency per OA row for multi-objective analysis
        row_costs: dict[int, list[float]] = defaultdict(list)
        row_latencies: dict[int, list[float]] = defaultdict(list)
        for trial in result.trials:
            if trial.error is not None:
                continue
            row_id = int(trial.metrics["oa_row_id"])
            if trial.cost is not None:
                row_costs[row_id].append(trial.cost)
            if trial.latency_seconds is not None and trial.latency_seconds >= 0:
                row_latencies[row_id].append(trial.latency_seconds)

        # Multi-objective analysis (accuracy + cost + latency)
        multi_obj = run_multi_objective_analysis(
            design, dict(row_scores), dict(row_costs), dict(row_latencies),
        )
```

Then add `multi_objective=multi_obj if multi_obj else None` to the `PhaseResult` constructor around line 487.

### Step 5: Run tests

Run: `cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing && uv run pytest agent-evals/tests/test_pipeline.py agent-evals/tests/test_taguchi_multi_objective.py -v -x`
Expected: ALL PASS

### Step 6: Run full test suite

Run: `cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing && uv run pytest agent-evals/tests/ -x -q`
Expected: ALL PASS

### Step 7: Commit

```bash
git add agent-evals/src/agent_evals/pipeline.py agent-evals/tests/test_pipeline.py
git commit -m "feat: wire multi-objective analysis (accuracy+cost+latency) into pipeline screening

Collects per-row cost and latency from trials, passes to
run_multi_objective_analysis() which computes independent S/N ratios
and ANOVA for each objective. Results stored in PhaseResult.multi_objective.

Closes bead 94."
```

> **Future work:** To persist multi_objective to the observatory, add a `multi_objective TEXT`
> column to the `phase_results` table and update `save_phase_results()`/`get_phase_results()`.
> This is not required for the initial wiring.

---

## Task 5: Train/Test Split for Generalization Testing (Bead 52)

**Files:**
- Create: `agent-evals/src/agent_evals/splits.py`
- Modify: `agent-evals/src/agent_evals/pipeline.py` (PipelineConfig + run_screening + run_confirmation)
- Modify: `agent-evals/src/agent_evals/cli.py` (add `--split-ratio`, `--split-seed`)
- Test: `agent-evals/tests/test_splits.py`

### Step 1: Write failing tests for the splitter module

Create `agent-evals/tests/test_splits.py`:

```python
"""Tests for train/test split module."""

from __future__ import annotations

import pytest

from agent_evals.splits import stratified_split
from agent_evals.tasks.base import TaskDefinition
from agent_evals.tasks.retrieval import RetrievalTask
from agent_evals.tasks.code_generation import CodeGenerationTask
from agent_evals.tasks.fact_extraction import FactExtractionTask


@pytest.fixture
def sample_tasks():
    """Create a diverse set of tasks for split testing."""
    tasks = []
    for i in range(1, 11):
        tasks.append(RetrievalTask(TaskDefinition(
            task_id=f"retrieval_{i:03d}",
            type="retrieval",
            question=f"Retrieve info {i}",
            domain="framework_api",
            difficulty="easy",
        )))
    for i in range(1, 8):
        tasks.append(CodeGenerationTask(TaskDefinition(
            task_id=f"code_generation_{i:03d}",
            type="code_generation",
            question=f"Generate code {i}",
            domain="framework_api",
            difficulty="medium",
        )))
    for i in range(1, 6):
        tasks.append(FactExtractionTask(TaskDefinition(
            task_id=f"fact_extraction_{i:03d}",
            type="fact_extraction",
            question=f"Extract fact {i}",
            domain="framework_api",
            difficulty="hard",
        )))
    return tasks


class TestStratifiedSplit:
    """Tests for stratified_split function."""

    def test_split_preserves_total_count(self, sample_tasks):
        train, test = stratified_split(sample_tasks, train_ratio=0.8, seed=42)
        assert len(train) + len(test) == len(sample_tasks)

    def test_split_ratio_approximately_correct(self, sample_tasks):
        train, test = stratified_split(sample_tasks, train_ratio=0.7, seed=42)
        ratio = len(train) / len(sample_tasks)
        assert 0.6 <= ratio <= 0.8  # Allow slack for stratification rounding

    def test_split_preserves_task_type_distribution(self, sample_tasks):
        train, test = stratified_split(sample_tasks, train_ratio=0.8, seed=42)
        train_types = {t.definition.type for t in train}
        test_types = {t.definition.type for t in test}
        all_types = {t.definition.type for t in sample_tasks}
        # Every type with 2+ tasks should appear in both splits
        for task_type in all_types:
            type_count = sum(1 for t in sample_tasks if t.definition.type == task_type)
            if type_count >= 2:
                assert task_type in train_types, f"{task_type} missing from train"
                assert task_type in test_types, f"{task_type} missing from test"

    def test_split_deterministic_with_same_seed(self, sample_tasks):
        train1, _ = stratified_split(sample_tasks, train_ratio=0.8, seed=42)
        train2, _ = stratified_split(sample_tasks, train_ratio=0.8, seed=42)
        assert [t.definition.task_id for t in train1] == [t.definition.task_id for t in train2]

    def test_split_different_with_different_seed(self, sample_tasks):
        train1, _ = stratified_split(sample_tasks, train_ratio=0.8, seed=42)
        train2, _ = stratified_split(sample_tasks, train_ratio=0.8, seed=99)
        ids1 = {t.definition.task_id for t in train1}
        ids2 = {t.definition.task_id for t in train2}
        assert ids1 != ids2

    def test_split_no_overlap(self, sample_tasks):
        train, test = stratified_split(sample_tasks, train_ratio=0.8, seed=42)
        train_ids = {t.definition.task_id for t in train}
        test_ids = {t.definition.task_id for t in test}
        assert train_ids.isdisjoint(test_ids)

    def test_empty_task_list(self):
        train, test = stratified_split([], train_ratio=0.8, seed=42)
        assert train == []
        assert test == []

    def test_single_task_goes_to_train(self):
        """Types with only 1 task go to train set."""
        tasks = [
            RetrievalTask(TaskDefinition(
                task_id="retrieval_001",
                type="retrieval",
                question="Q1",
                domain="framework_api",
                difficulty="easy",
            ))
        ]
        train, test = stratified_split(tasks, train_ratio=0.8, seed=42)
        assert len(train) == 1
        assert len(test) == 0
```

### Step 2: Run tests to verify they fail

Run: `cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing && uv run pytest agent-evals/tests/test_splits.py -v`
Expected: FAIL — `agent_evals.splits` module does not exist

### Step 3: Implement the splits module

Create `agent-evals/src/agent_evals/splits.py`:

```python
"""Stratified train/test splitting for evaluation tasks."""

from __future__ import annotations

import random
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_evals.tasks.base import EvalTask


def stratified_split(
    tasks: list[EvalTask],
    train_ratio: float = 0.8,
    seed: int = 42,
) -> tuple[list[EvalTask], list[EvalTask]]:
    """Split tasks into train and test sets, stratified by task type.

    Ensures each task type is represented proportionally in both sets.
    Types with fewer than 2 tasks are placed entirely in train.

    Args:
        tasks: All evaluation tasks to split.
        train_ratio: Fraction of tasks for training (0.0-1.0).
        seed: Random seed for reproducibility.

    Returns:
        Tuple of (train_tasks, test_tasks).
    """
    if not tasks:
        return [], []

    rng = random.Random(seed)

    # Group by task type
    by_type: dict[str, list[EvalTask]] = defaultdict(list)
    for task in tasks:
        by_type[task.definition.type].append(task)

    train: list[EvalTask] = []
    test: list[EvalTask] = []

    for task_type in sorted(by_type):
        group = by_type[task_type]
        rng.shuffle(group)

        if len(group) < 2:
            train.extend(group)
            continue

        split_idx = max(1, round(len(group) * train_ratio))
        # Ensure at least 1 in test
        split_idx = min(split_idx, len(group) - 1)
        train.extend(group[:split_idx])
        test.extend(group[split_idx:])

    return train, test
```

### Step 4: Run tests to verify they pass

Run: `cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing && uv run pytest agent-evals/tests/test_splits.py -v`
Expected: ALL PASS

### Step 5: Add CLI flags and PipelineConfig fields

In `cli.py`, add CLI flags (near existing pipeline flags, around line 210):

```python
parser.add_argument(
    "--split-ratio",
    type=float,
    default=None,
    help="Train/test split ratio (e.g., 0.8 = 80%% train, 20%% test). "
         "When set, Taguchi screening uses train split, confirmation validates on test split.",
)
parser.add_argument(
    "--split-seed",
    type=int,
    default=42,
    help="Random seed for train/test split reproducibility (default: 42).",
)
```

Add to `_CONFIG_KEYS` dict (around line 540, after `strategy_reps`):

```python
"split_ratio": float,
"split_seed": int,
```

Wire into **both** `PipelineConfig(...)` constructor calls in `_run_pipeline_mode()` (line 1183) and `_run_multi_strategy_mode()` (line 1273) — add after `judge_primary_types=...`:

```python
        split_ratio=resolved.get("split_ratio"),
        split_seed=int(resolved.get("split_seed", 42)),
```

In `pipeline.py`, add fields to `PipelineConfig` (after `judge_primary_types`, at the end of the dataclass):

```python
    split_ratio: float | None = None
    split_seed: int = 42
```

### Step 6: Wire split into pipeline

In `pipeline.py`, add `_test_tasks` initialization to `DOEPipeline.__init__()`:

```python
    def __init__(
        self,
        config: PipelineConfig,
        orchestrator: EvalOrchestrator,
        pipeline_id: str | None = None,
    ) -> None:
        # ... existing init code ...
        self._test_tasks: list[Any] = []
```

In `run_screening()`, before the orchestrator call (before line 448 where `result = self._orchestrator.run(...)` is called), add:

```python
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
```

In `run_confirmation()`, if test tasks are available, use them instead of all tasks:

```python
        # Use held-out test tasks for confirmation if train/test split was used
        if self._test_tasks:
            logger.info(
                "Using %d held-out test tasks for confirmation",
                len(self._test_tasks),
            )
            tasks = self._test_tasks
```

### Step 7: Run full test suite

Run: `cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing && uv run pytest agent-evals/tests/ -x -q`
Expected: ALL PASS

### Step 8: Commit

```bash
git add agent-evals/src/agent_evals/splits.py agent-evals/tests/test_splits.py agent-evals/src/agent_evals/pipeline.py agent-evals/src/agent_evals/cli.py
git commit -m "feat: add stratified train/test split for generalization testing

Adds splits.py with stratified_split() that preserves task-type distribution.
CLI flags: --split-ratio, --split-seed.
When set, pipeline screening uses train split; confirmation uses held-out test tasks.

Closes bead 52."
```

---

## Task 6: Validate Task Difficulty Labels Empirically (Bead 53)

**Files:**
- Create: `agent-evals/src/agent_evals/analysis/__init__.py`
- Create: `agent-evals/src/agent_evals/analysis/difficulty.py`
- Test: `agent-evals/tests/test_difficulty_validation.py`

### Step 1: Write failing tests

Create `agent-evals/tests/test_difficulty_validation.py`:

```python
"""Tests for empirical difficulty validation."""

from __future__ import annotations

import pytest

from agent_evals.analysis.difficulty import (
    compute_empirical_difficulty,
    validate_difficulty_labels,
    DifficultyReport,
)


class TestComputeEmpiricalDifficulty:
    """Tests for computing difficulty from scores."""

    def test_high_scores_are_easy(self):
        result = compute_empirical_difficulty(scores=[0.95, 0.90, 0.92, 0.88])
        assert result == "easy"

    def test_medium_scores_are_medium(self):
        result = compute_empirical_difficulty(scores=[0.65, 0.70, 0.60, 0.72])
        assert result == "medium"

    def test_low_scores_are_hard(self):
        result = compute_empirical_difficulty(scores=[0.30, 0.25, 0.35, 0.20])
        assert result == "hard"

    def test_very_low_scores_are_edge(self):
        result = compute_empirical_difficulty(scores=[0.05, 0.10, 0.00, 0.08])
        assert result == "edge"

    def test_empty_scores_returns_unknown(self):
        result = compute_empirical_difficulty(scores=[])
        assert result == "unknown"

    def test_boundary_easy_medium(self):
        """Score exactly at 0.80 threshold is easy."""
        result = compute_empirical_difficulty(scores=[0.80])
        assert result == "easy"

    def test_boundary_medium_hard(self):
        """Score exactly at 0.50 threshold is medium."""
        result = compute_empirical_difficulty(scores=[0.50])
        assert result == "medium"

    def test_boundary_hard_edge(self):
        """Score exactly at 0.15 threshold is hard."""
        result = compute_empirical_difficulty(scores=[0.15])
        assert result == "hard"


class TestValidateDifficultyLabels:
    """Tests for label validation against empirical data."""

    def test_returns_difficulty_report(self):
        data = [("retrieval_001", "easy", [0.95, 0.90])]
        report = validate_difficulty_labels(data)
        assert isinstance(report, DifficultyReport)

    def test_report_contains_all_task_ids(self):
        data = [
            ("retrieval_001", "easy", [0.95, 0.90]),
            ("code_generation_001", "hard", [0.30, 0.25]),
        ]
        report = validate_difficulty_labels(data)
        task_ids = {entry.task_id for entry in report.entries}
        assert task_ids == {"retrieval_001", "code_generation_001"}

    def test_detects_mislabeled_easy_task(self):
        """A task labeled 'hard' that scores 0.95 should be flagged."""
        data = [("retrieval_001", "hard", [0.95, 0.92, 0.90])]
        report = validate_difficulty_labels(data)
        assert len(report.mismatches) == 1
        assert report.mismatches[0].task_id == "retrieval_001"
        assert report.mismatches[0].labeled == "hard"
        assert report.mismatches[0].empirical == "easy"

    def test_no_mismatch_for_correct_label(self):
        """A task labeled 'easy' that scores 0.90+ should not be flagged."""
        data = [("retrieval_001", "easy", [0.95, 0.92, 0.90])]
        report = validate_difficulty_labels(data)
        assert len(report.mismatches) == 0

    def test_report_summary_counts(self):
        data = [
            ("t1", "easy", [0.95, 0.90]),
            ("t2", "hard", [0.90, 0.88]),  # mismatch: labeled hard, scores easy
            ("t3", "medium", [0.65, 0.70]),
            ("t4", "edge", [0.05, 0.10]),
        ]
        report = validate_difficulty_labels(data)
        assert report.total == 4
        assert report.matched + report.mismatched == report.total

    def test_unknown_not_flagged_as_mismatch(self):
        """Tasks with no scores (empirical='unknown') are not mismatches."""
        data = [("retrieval_001", "easy", [])]
        report = validate_difficulty_labels(data)
        assert len(report.mismatches) == 0

    def test_empty_input(self):
        report = validate_difficulty_labels([])
        assert report.total == 0
        assert report.matched == 0
        assert report.mismatched == 0
```

### Step 2: Run tests to verify they fail

Run: `cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing && uv run pytest agent-evals/tests/test_difficulty_validation.py -v`
Expected: FAIL — module does not exist

### Step 3: Create the analysis package and difficulty module

```bash
mkdir -p agent-evals/src/agent_evals/analysis
```

Create `agent-evals/src/agent_evals/analysis/__init__.py`:

```python
"""Post-hoc analysis modules."""
```

Create `agent-evals/src/agent_evals/analysis/difficulty.py`:

```python
"""Empirical validation of task difficulty labels.

Compares labeled difficulty (easy/medium/hard/edge) against actual
baseline scores to detect mislabeled tasks. Thresholds are based on
mean score across all repetitions of a task under the baseline variant.

Note: 5 of 11 task types produce binary scores (0.0 or 1.0), which means
mean scores cluster at specific fractions (0/N, 1/N, ..., N/N). The
thresholds below are set to work with both continuous and binary scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Difficulty thresholds based on mean baseline score.
# These thresholds work for both continuous scores and binary scores.
# For binary scoring with 10 reps: easy >= 8/10, medium >= 5/10, hard >= 2/10.
_THRESHOLDS = {
    "easy": 0.80,    # mean score >= 0.80
    "medium": 0.50,  # mean score >= 0.50
    "hard": 0.15,    # mean score >= 0.15
    "edge": 0.0,     # mean score < 0.15
}


@dataclass
class DifficultyEntry:
    """Per-task difficulty validation result."""

    task_id: str
    labeled: str
    empirical: str
    mean_score: float
    is_mismatch: bool


@dataclass
class DifficultyReport:
    """Aggregate difficulty validation report."""

    entries: list[DifficultyEntry] = field(default_factory=list)

    @property
    def mismatches(self) -> list[DifficultyEntry]:
        return [e for e in self.entries if e.is_mismatch]

    @property
    def total(self) -> int:
        return len(self.entries)

    @property
    def matched(self) -> int:
        return sum(1 for e in self.entries if not e.is_mismatch)

    @property
    def mismatched(self) -> int:
        return sum(1 for e in self.entries if e.is_mismatch)


def compute_empirical_difficulty(scores: list[float]) -> str:
    """Compute empirical difficulty level from observed scores.

    Args:
        scores: List of scores (0.0-1.0) from baseline variant runs.

    Returns:
        Difficulty label: "easy", "medium", "hard", "edge", or "unknown".
    """
    if not scores:
        return "unknown"

    mean = sum(scores) / len(scores)

    if mean >= _THRESHOLDS["easy"]:
        return "easy"
    if mean >= _THRESHOLDS["medium"]:
        return "medium"
    if mean >= _THRESHOLDS["hard"]:
        return "hard"
    return "edge"


def validate_difficulty_labels(
    trial_data: list[tuple[str, str, list[float]]],
) -> DifficultyReport:
    """Validate difficulty labels against empirical scores.

    Args:
        trial_data: List of (task_id, labeled_difficulty, scores) tuples.
            Scores should be from baseline variant runs.

    Returns:
        DifficultyReport with per-task entries and mismatch detection.
    """
    report = DifficultyReport()

    for task_id, labeled, scores in trial_data:
        empirical = compute_empirical_difficulty(scores)
        mean_score = sum(scores) / len(scores) if scores else 0.0
        is_mismatch = empirical != labeled and empirical != "unknown"

        report.entries.append(DifficultyEntry(
            task_id=task_id,
            labeled=labeled,
            empirical=empirical,
            mean_score=mean_score,
            is_mismatch=is_mismatch,
        ))

    return report
```

### Step 4: Run tests to verify they pass

Run: `cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing && uv run pytest agent-evals/tests/test_difficulty_validation.py -v`
Expected: ALL PASS

### Step 5: Run full test suite

Run: `cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing && uv run pytest agent-evals/tests/ -x -q`
Expected: ALL PASS

### Step 6: Commit

```bash
git add agent-evals/src/agent_evals/analysis/__init__.py agent-evals/src/agent_evals/analysis/difficulty.py agent-evals/tests/test_difficulty_validation.py
git commit -m "feat: add empirical difficulty validation for task labels

Adds analysis/difficulty.py with compute_empirical_difficulty() and
validate_difficulty_labels(). Compares labeled difficulty (easy/medium/hard/edge)
against actual baseline scores to detect mislabeled tasks.
Library-only for now — CLI integration deferred to future work.

Closes bead 53."
```

> **Future work:** Add observatory integration to auto-fetch baseline scores,
> and a CLI subcommand (`agent-evals validate-difficulty --run-id <id>`).

---

## Summary

| Task | Bead | Estimated Effort | Dependencies |
|------|------|-----------------|--------------|
| 1. full-config.yaml | 109 | ~15 min | None |
| 2. Progress cost display | 106 | ~30 min | None |
| 3. Judge graduation | 95 | ~45 min | None |
| 4. Multi-objective wiring | 94 | ~30 min | None |
| 5. Train/test split | 52 | ~30 min | None |
| 6. Difficulty validation | 53 | ~20 min | None |

Tasks 1-4 are independent. Tasks 5-6 are independent. All 6 can be parallelized with subagents (3 pairs of 2).

### Review Round 1 Fixes Applied

| Issue | Fix |
|-------|-----|
| Task 1: Missing `judge_primary_types` | Added to YAML |
| Task 1: `dashboard_port` wrong key/default | Removed (dashboard-subcommand only) |
| Task 1: Missing `dry_run` | Added to Execution section |
| Task 1: Missing `dataset_cache_dir` | Added to Data Sources section |
| Task 1: Axis range "1-12" | Fixed to "1-10" |
| Task 2: Callbacks don't accumulate cost | Replaced with closure-based accumulator |
| Task 2: Tests contradict behavior | Rewrote tests to match closure design |
| Task 2: No code path to populate tracker | Eliminated separate tracker; closure accumulates from trial.cost |
| Task 2: CLI call site not shown | Wired into orchestrator._on_trial_progress instead |
| Task 2: Option A/B contradiction | Removed; single clean approach (closure) |
| Task 2: inner param never used | Removed; separate plain/rich closures |
| Task 3: Missing _CONFIG_KEYS entries | Added explicit entries + build_eval_run_config wiring |
| Task 3: Pipeline _effective_score conflict | Added graduation_applied check to _effective_score |
| Task 3: Missing validation in __post_init__ | Added weight range + requires judge_enabled checks |
| Task 3: Import path inconsistency | Changed to module-level import |
| Task 3: Integration test incomplete | Replaced with config validation + error tests |
| Task 3: No calibration data loading | Removed calibration_data from EvalRunConfig (graduation doesn't need it — judge_primary_types handles routing) |
| Task 4: `_run_screening` wrong method name | Fixed to `run_screening` |
| Task 4: Non-existent fixture | Rewrote tests using existing pattern (module-level + _make_mock_orchestrator) |
| Task 4: oa_row_id type conversion | Added explicit `int()` cast |
| Task 4: Cost > 0 filter excludes zero-cost | Changed to `is not None` |
| Task 4: Latency > 0 excludes zero | Changed to `>= 0` |
| Task 4: Import inside method | Moved to top-level import |
| Task 4: PhaseResult persistence gap | Documented as future work |
| Task 5: getattr pattern fragile | Changed to direct `self.config.split_ratio` |
| Task 5: _test_tasks not initialized | Added to __init__ |
| Task 5: Confirmation doesn't use test tasks | Added test task routing in run_confirmation |
| Task 6: Binary scoring thresholds | Added docstring explaining threshold rationale |
| Task 6: No CLI command | Documented as future work |
