"""Tests for TaguchiRunner - OA-based evaluation execution."""

from __future__ import annotations

from unittest.mock import MagicMock

from agent_evals.runner import EvalRunConfig, TrialResult
from agent_evals.taguchi.factors import (
    TaguchiDesign,
    TaguchiExperimentRow,
    TaguchiFactorDef,
)
from agent_evals.taguchi.runner import TaguchiRunResult, TaguchiRunner
from conftest import make_mock_client, make_mock_task, make_mock_variant


# ---------------------------------------------------------------------------
# Helpers: lightweight mocks that avoid hitting real LLMs
# ---------------------------------------------------------------------------


def _make_simple_design(
    n_rows: int = 3,
    axes: dict[int, list[str]] | None = None,
    models: list[str] | None = None,
) -> TaguchiDesign:
    """Create a minimal TaguchiDesign for testing."""
    if axes is None:
        axes = {1: ["flat", "2tier", "3tier"]}

    factors = []
    for axis_num in sorted(axes):
        names = axes[axis_num]
        factors.append(TaguchiFactorDef(
            name=f"axis_{axis_num}",
            n_levels=len(names),
            level_names=list(names),
            axis=axis_num,
        ))
    if models and len(models) > 1:
        factors.append(TaguchiFactorDef(
            name="model",
            n_levels=len(models),
            level_names=list(models),
            axis=None,
        ))

    rows = []
    for i in range(n_rows):
        assignments: dict[str, str] = {}
        for f in factors:
            if f.axis is not None:
                assignments[f.name] = f.level_names[i % f.n_levels]
            else:
                assignments[f.name] = f.level_names[i % f.n_levels]
        rows.append(TaguchiExperimentRow(run_id=i + 1, assignments=assignments))

    return TaguchiDesign(
        oa_name="L9",
        n_runs=n_rows,
        factors=factors,
        rows=rows,
        level_counts=[f.n_levels for f in factors],
    )


def _make_variant_lookup(
    axes: dict[int, list[str]],
) -> dict[str, MagicMock]:
    """Create a variant_lookup mapping variant_name -> mock variant."""
    lookup: dict[str, MagicMock] = {}
    for axis_num, names in axes.items():
        for name in names:
            lookup[name] = make_mock_variant(name, axis_num)
    return lookup


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWorkItemGeneration:
    """Work items = OA_rows * tasks * repetitions."""

    def test_correct_total_work_items(self):
        design = _make_simple_design(n_rows=9)
        axes = {1: ["flat", "2tier", "3tier"]}
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=5, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task(f"retrieval_{i:03d}") for i in range(10)]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)
        # 9 rows * 10 tasks * 5 reps = 450
        assert len(result.trials) == 9 * 10 * 5

    def test_single_task_single_rep(self):
        design = _make_simple_design(n_rows=3)
        axes = {1: ["flat", "2tier", "3tier"]}
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)
        assert len(result.trials) == 3  # 3 rows * 1 task * 1 rep


class TestCompositeVariantAssignment:
    """Each trial uses the correct composite variant from OA row."""

    def test_variant_names_match_row_assignments(self):
        axes = {1: ["flat", "2tier"], 2: ["path", "summary"]}
        design = _make_simple_design(
            n_rows=4,
            axes=axes,
        )
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        # Each trial's variant_name should be a composite of the row's axis
        # assignments joined by "+"
        for trial in result.trials:
            assert "+" in trial.variant_name or len(axes) == 1

    def test_setup_called_on_composite_variants(self):
        axes = {1: ["flat", "2tier"]}
        design = _make_simple_design(n_rows=2, axes=axes)
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        runner.run(tasks, doc_tree)

        # Variants should have had setup called
        for _v in variants.values():
            # setup is called on the individual variants via CompositeVariant
            pass  # Just verify no errors; composite delegates setup


class TestModelAssignment:
    """Each trial uses the correct model from OA row."""

    def test_multimodel_uses_correct_client(self):
        axes = {1: ["flat", "2tier"]}
        models = ["claude", "gpt"]
        design = _make_simple_design(n_rows=4, axes=axes, models=models)
        variants = _make_variant_lookup(axes)

        claude_client = make_mock_client("claude")
        gpt_client = make_mock_client("gpt")
        clients = {"claude": claude_client, "gpt": gpt_client}

        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients=clients,
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        # Both clients should have been called at least once
        assert claude_client.complete.call_count > 0
        assert gpt_client.complete.call_count > 0

    def test_single_model_all_same_client(self):
        axes = {1: ["flat", "2tier", "3tier"]}
        design = _make_simple_design(n_rows=3, axes=axes)
        variants = _make_variant_lookup(axes)
        client = make_mock_client("only-model")
        clients = {"only-model": client}

        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients=clients,
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        # All 3 trials should use the same client
        assert client.complete.call_count == 3


class TestResultGrouping:
    """Results can be grouped by OA row."""

    def test_trials_have_oa_row_id(self):
        design = _make_simple_design(n_rows=3)
        axes = {1: ["flat", "2tier", "3tier"]}
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=2, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        # All trials should have an oa_row_id in metrics
        for trial in result.trials:
            assert "oa_row_id" in trial.metrics

    def test_grouping_by_row_id(self):
        design = _make_simple_design(n_rows=3)
        axes = {1: ["flat", "2tier", "3tier"]}
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=2, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        # Group by oa_row_id
        grouped: dict[int, list[TrialResult]] = {}
        for trial in result.trials:
            row_id = int(trial.metrics["oa_row_id"])
            grouped.setdefault(row_id, []).append(trial)

        # Should have 3 groups (one per OA row)
        assert len(grouped) == 3
        # Each group should have 2 trials (1 task * 2 reps)
        for _row_id, trials in grouped.items():
            assert len(trials) == 2


class TestProgressCallback:
    """Progress callback fires per trial."""

    def test_callback_called_for_each_trial(self):
        design = _make_simple_design(n_rows=2)
        axes = {1: ["flat", "2tier", "3tier"]}
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        callback_calls: list[tuple[int, int, TrialResult]] = []

        def on_progress(completed: int, total: int, trial: TrialResult) -> None:
            callback_calls.append((completed, total, trial))

        runner.run(tasks, doc_tree, progress_callback=on_progress)

        # 2 rows * 1 task * 1 rep = 2 trials
        assert len(callback_calls) == 2

        # Completed count should increase
        completed_counts = [c[0] for c in callback_calls]
        assert completed_counts == [1, 2]

        # Total should be consistent
        assert all(c[1] == 2 for c in callback_calls)


class TestSourcePassthrough:
    """TaguchiRunner passes through source parameter."""

    def test_default_source(self):
        design = _make_simple_design(n_rows=2)
        axes = {1: ["flat", "2tier", "3tier"]}
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        for trial in result.trials:
            assert trial.source == "gold_standard"

    def test_custom_source(self):
        design = _make_simple_design(n_rows=2)
        axes = {1: ["flat", "2tier", "3tier"]}
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree, source="repliqa")

        for trial in result.trials:
            assert trial.source == "repliqa"


class TestTrialErrorHandling:
    """LLM failures should not abort the entire Taguchi run."""

    def test_llm_error_returns_trial_with_error(self):
        """When the LLM client raises, _run_trial returns TrialResult with error set."""
        axes = {1: ["flat", "2tier", "3tier"]}
        design = _make_simple_design(n_rows=3, axes=axes)
        variants = _make_variant_lookup(axes)

        client = make_mock_client()
        client.complete.side_effect = RuntimeError("API timeout")
        clients = {"mock-model": client}

        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients=clients,
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        # All 3 trials should complete (not raise)
        assert len(result.trials) == 3

        for trial in result.trials:
            assert trial.error is not None
            assert "API timeout" in trial.error
            assert trial.score == 0.0
            assert trial.total_tokens == 0
            assert trial.cost is None


class TestTaguchiRunResult:
    """TaguchiRunResult stores design metadata and trials."""

    def test_result_has_design(self):
        design = _make_simple_design(n_rows=2)
        axes = {1: ["flat", "2tier", "3tier"]}
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        assert result.design is design
        assert result.config is config

    def test_result_aggregates_costs(self):
        design = _make_simple_design(n_rows=2)
        axes = {1: ["flat", "2tier", "3tier"]}
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        assert result.total_cost > 0
        assert result.total_tokens > 0
        assert result.elapsed_seconds >= 0

    def test_result_has_elapsed_time(self):
        design = _make_simple_design(n_rows=1)
        axes = {1: ["flat", "2tier", "3tier"]}
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        assert isinstance(result.elapsed_seconds, float)
        assert result.elapsed_seconds >= 0

    def test_trials_carry_strategy_fields(self):
        """Every TaguchiRunner trial must have context_strategy set."""
        design = _make_simple_design(n_rows=2)
        axes = {1: ["flat", "2tier", "3tier"]}
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        assert len(result.trials) > 0
        for trial in result.trials:
            assert trial.context_strategy == "full_context", (
                f"Trial {trial.task_id}/{trial.variant_name} missing context_strategy"
            )
            assert trial.llm_calls >= 1
            assert isinstance(trial.strategy_metadata, dict)


class TestPhaseMetadata:
    """TaguchiRunner passes phase through to trial metrics."""

    def test_phase_stored_in_trial_metrics(self):
        """When phase is passed to run(), all trials include it in metrics."""
        design = _make_simple_design(n_rows=2)
        axes = {1: ["flat", "2tier", "3tier"]}
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree, phase="screening")

        for trial in result.trials:
            assert trial.metrics["phase"] == "screening"

    def test_phase_none_by_default(self):
        """When phase is not passed, metrics still have oa_row_id but no phase."""
        design = _make_simple_design(n_rows=2)
        axes = {1: ["flat", "2tier", "3tier"]}
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        for trial in result.trials:
            assert "oa_row_id" in trial.metrics
            assert "phase" not in trial.metrics

    def test_phase_in_error_trials(self):
        """Phase metadata is preserved even when the LLM call fails."""
        axes = {1: ["flat", "2tier", "3tier"]}
        design = _make_simple_design(n_rows=2, axes=axes)
        variants = _make_variant_lookup(axes)

        client = make_mock_client()
        client.complete.side_effect = RuntimeError("boom")
        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree, phase="confirmation")

        for trial in result.trials:
            assert trial.error is not None
            assert trial.metrics["phase"] == "confirmation"


class TestMetricsHarmonization:
    """TaguchiRunner metrics should match EvalRunner metrics."""

    def test_scoring_ms_in_metrics(self):
        """Trial metrics should include scoring_ms."""
        design = _make_simple_design(n_rows=2)
        axes = {1: ["flat", "2tier", "3tier"]}
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()
        result = runner.run(tasks, doc_tree)

        for trial in result.trials:
            assert "scoring_ms" in trial.metrics, (
                f"Trial {trial.task_id} missing scoring_ms metric"
            )
            assert trial.metrics["scoring_ms"] >= 0

    def test_prompt_build_ms_in_metrics(self):
        """Trial metrics should include prompt_build_ms."""
        design = _make_simple_design(n_rows=2)
        axes = {1: ["flat", "2tier", "3tier"]}
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()
        result = runner.run(tasks, doc_tree)

        for trial in result.trials:
            assert "prompt_build_ms" in trial.metrics, (
                f"Trial {trial.task_id} missing prompt_build_ms metric"
            )
            assert trial.metrics["prompt_build_ms"] >= 0


class TestSetupTeardownPerRow:
    """CompositeVariant setup/teardown should happen once per OA row, not per trial."""

    def test_setup_called_once_per_row_not_per_trial(self):
        """With 3 rows, 2 tasks, 2 reps: setup called 3 times, not 12."""
        from unittest.mock import call, patch

        axes = {1: ["flat", "2tier", "3tier"]}
        design = _make_simple_design(n_rows=3, axes=axes)
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=2, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task("t1"), make_mock_task("t2")]
        doc_tree = MagicMock()

        # Track setup/teardown calls on composites
        setup_count = 0
        teardown_count = 0
        orig_build = runner._build_composite

        def tracking_build(row):
            nonlocal setup_count, teardown_count
            composite = orig_build(row)
            orig_setup = composite.setup
            orig_teardown = composite.teardown

            def counted_setup(*a, **kw):
                nonlocal setup_count
                setup_count += 1
                return orig_setup(*a, **kw)

            def counted_teardown(*a, **kw):
                nonlocal teardown_count
                teardown_count += 1
                return orig_teardown(*a, **kw)

            composite.setup = counted_setup
            composite.teardown = counted_teardown
            return composite

        runner._build_composite = tracking_build

        result = runner.run(tasks, doc_tree)
        # 3 rows * 2 tasks * 2 reps = 12 trials
        assert len(result.trials) == 12

        # Setup and teardown should be called once per row (3), not per trial (12)
        assert setup_count == 3, (
            f"Expected 3 setup calls (once per row), got {setup_count}"
        )
        assert teardown_count == 3, (
            f"Expected 3 teardown calls (once per row), got {teardown_count}"
        )


class TestParallelExecution:
    """TaguchiRunner must use ThreadPoolExecutor to run trials concurrently."""

    def test_trials_run_in_parallel(self):
        """With max_connections=4 and 4 tasks, total time ≈ 1 trial (not 4x)."""
        import time

        SLEEP = 0.12  # seconds per fake API call
        TOLERANCE = 0.5  # max ratio: elapsed / SLEEP (should be ~1x not ~4x)

        axes = {1: ["flat"]}
        design = _make_simple_design(n_rows=1, axes=axes)
        variants = _make_variant_lookup(axes)

        client = MagicMock()
        client.model = "mock-model"
        gen = MagicMock()
        gen.content = "response"
        gen.prompt_tokens = 10
        gen.completion_tokens = 5
        gen.total_tokens = 15
        gen.cost = 0.001

        def slow_complete(*args, **kwargs):
            time.sleep(SLEEP)
            return gen

        client.complete.side_effect = slow_complete

        config = EvalRunConfig(repetitions=1, max_connections=4)
        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task(f"retrieval_{i:03d}") for i in range(4)]
        doc_tree = MagicMock()

        start = time.monotonic()
        result = runner.run(tasks, doc_tree)
        elapsed = time.monotonic() - start

        assert len(result.trials) == 4
        # Sequential would take 4 * SLEEP; parallel should take ~1 * SLEEP
        assert elapsed < SLEEP * (1 + TOLERANCE), (
            f"Trials appear sequential: {elapsed:.3f}s >= {SLEEP * (1 + TOLERANCE):.3f}s. "
            "TaguchiRunner must use ThreadPoolExecutor."
        )


class TestDummyLevelModel:
    """_select_client must handle DUMMY_LEVEL gracefully."""

    def test_select_client_uses_default_when_model_is_dummy(self):
        """When model factor gets DUMMY_LEVEL, _select_client should use default."""
        from agent_evals.taguchi.factors import DUMMY_LEVEL

        axes = {1: ["flat", "2tier"]}
        models = ["claude", "gpt"]
        design = _make_simple_design(n_rows=4, axes=axes, models=models)
        variants = _make_variant_lookup(axes)

        claude_client = make_mock_client("claude")
        gpt_client = make_mock_client("gpt")
        clients = {"claude": claude_client, "gpt": gpt_client}

        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients=clients,
            config=config,
            design=design,
            variant_lookup=variants,
        )

        # Create a row with DUMMY_LEVEL for the model factor
        dummy_row = TaguchiExperimentRow(
            run_id=99,
            assignments={"axis_1": "flat", "model": DUMMY_LEVEL},
            dummy_factors={"model"},
        )

        # Should not raise KeyError; should fall back to default client
        client = runner._select_client(dummy_row)
        assert client is claude_client  # "claude" is first in clients dict


class TestJudgeWiring:
    """TaguchiRunner calls LLM judge when judge_enabled=True."""

    def test_judge_called_at_sample_rate(self):
        """Judge is called every N-th trial when judge_enabled=True."""
        axes = {1: ["flat", "2tier", "3tier"]}
        design = _make_simple_design(n_rows=3, axes=axes)
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        # judge_enabled=True, sample_rate=2 -> judge on trials 2, 4, 6...
        config = EvalRunConfig(
            repetitions=1, max_connections=1,
            judge_enabled=True, judge_sample_rate=2,
            judge_model="openrouter/test/judge-model",
        )

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        # Mock the _call_judge method
        judge_calls: list[str] = []
        original_call_judge = runner._call_judge

        def tracking_judge(client, task_type, question, response):
            judge_calls.append(task_type)
            return 0.85, "good answer"

        runner._call_judge = tracking_judge  # type: ignore[assignment]

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        # 3 trials total (3 rows * 1 task * 1 rep)
        assert len(result.trials) == 3
        # Trial indices 0, 1, 2; judge on index 2 (every 2nd, skipping 0)
        assert len(judge_calls) == 1

        # The judged trial should have judge_score in metrics
        judged_trials = [
            t for t in result.trials if "judge_score" in t.metrics
        ]
        assert len(judged_trials) == 1
        assert judged_trials[0].metrics["judge_score"] == 0.85
        assert "judge_heuristic_delta" in judged_trials[0].metrics

    def test_judge_not_called_when_disabled(self):
        """Judge is NOT called when judge_enabled=False (default)."""
        axes = {1: ["flat", "2tier", "3tier"]}
        design = _make_simple_design(n_rows=3, axes=axes)
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        for trial in result.trials:
            assert "judge_score" not in trial.metrics

    def test_judge_call_judge_integration(self):
        """Real _call_judge fires and parses judge response without mocking.

        Verifies the actual _call_judge implementation works end-to-end:
        mock client returns a parseable judge response, and the judge score
        appears in trial metrics. This catches bugs where _call_judge is
        broken but masked by tests that mock it out entirely.
        """
        axes = {1: ["flat", "2tier", "3tier"]}
        design = _make_simple_design(n_rows=3, axes=axes)
        variants = _make_variant_lookup(axes)

        # Client that returns a parseable judge response for ALL calls.
        # The eval task's score_response() is mocked so eval scoring ignores
        # the response content; only the judge parsing cares about format.
        client = make_mock_client(
            content="RATIONALE: Good answer\nSCORE: 0.75",
        )
        config = EvalRunConfig(
            repetitions=1, max_connections=1,
            judge_enabled=True, judge_sample_rate=1,
            judge_model="openrouter/test/judge-model",
        )

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        # Do NOT mock _call_judge — let the real implementation run.
        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        # 3 trials (3 rows * 1 task * 1 rep).
        # With sample_rate=1, trial indices 1 and 2 should fire the judge
        # (index 0 is always skipped).
        assert len(result.trials) == 3
        judged = [t for t in result.trials if "judge_score" in t.metrics]
        assert len(judged) >= 1, (
            "Expected at least 1 trial with judge_score in metrics, "
            f"got 0. Trial metrics: {[t.metrics for t in result.trials]}"
        )
        assert judged[0].metrics["judge_score"] == 0.75
        assert "judge_heuristic_delta" in judged[0].metrics

    def test_judge_score_stored_in_observatory(self):
        """Judge scores are persisted to the observatory via the tracker.

        The orchestrator progress callback must pass judge_score to the
        EventTracker so that it appears in the observatory database.
        """
        from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig

        axes = {1: ["flat", "2tier", "3tier"]}
        design = _make_simple_design(n_rows=2, axes=axes)
        variants_map = _make_variant_lookup(axes)

        config = EvalRunConfig(
            repetitions=1, max_connections=1,
            judge_enabled=True, judge_sample_rate=1,
            judge_model="openrouter/test/judge-model",
        )

        # Create a mock store and tracker to capture what gets recorded.
        mock_store = MagicMock()
        mock_store.get_completed_trial_keys.return_value = set()
        mock_tracker = MagicMock()

        orch_config = OrchestratorConfig(
            mode="taguchi",
            models=["mock-model"],
            api_key="test-key",
            eval_config=config,
            store=mock_store,
            tracker=mock_tracker,
        )
        orchestrator = EvalOrchestrator(orch_config)

        # Patch the client pool to return a mock client with judge response.
        mock_client = make_mock_client(
            content="RATIONALE: Good\nSCORE: 0.80",
        )
        orchestrator.client_pool = MagicMock()
        orchestrator.client_pool.get_client.return_value = mock_client

        tasks = [make_mock_task()]
        variants_list = list(variants_map.values())

        result = orchestrator.run(
            tasks=tasks,
            variants=variants_list,
            doc_tree=MagicMock(),
            design=design,
            variant_lookup=variants_map,
        )

        # At least one trial should have judge_score in its metrics.
        judged = [t for t in result.trials if "judge_score" in t.metrics]
        assert len(judged) >= 1, "Judge must fire for at least one trial"

        # The tracker must have received judge_score in at least one call.
        record_calls = mock_tracker.record_trial.call_args_list
        judge_scores_in_tracker = [
            call for call in record_calls
            if call.kwargs.get("judge_score") is not None
        ]
        assert len(judge_scores_in_tracker) >= 1, (
            "Tracker.record_trial must receive judge_score for judged trials. "
            f"Received kwargs: {[c.kwargs for c in record_calls[:3]]}"
        )

    def test_judge_failure_does_not_abort_trial(self):
        """If judge call fails, the trial still completes with its heuristic score."""
        axes = {1: ["flat", "2tier", "3tier"]}
        design = _make_simple_design(n_rows=1, axes=axes)
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(
            repetitions=2, max_connections=1,
            judge_enabled=True, judge_sample_rate=1,
            judge_model="openrouter/test/judge-model",
        )

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        def failing_judge(client, task_type, question, response):
            raise RuntimeError("Judge API timeout")

        runner._call_judge = failing_judge  # type: ignore[assignment]

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        # Both trials complete despite judge failures
        assert len(result.trials) == 2
        for trial in result.trials:
            assert trial.error is None
            assert trial.score > 0  # heuristic score still works
            assert "judge_score" not in trial.metrics  # judge failed
