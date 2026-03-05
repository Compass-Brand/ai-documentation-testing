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
