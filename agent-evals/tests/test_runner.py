"""Tests for the eval runner core."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agent_evals.llm.cache import CacheEntry, ResponseCache
from agent_evals.llm.client import GenerationResult, LLMClient, LLMClientError
from agent_evals.runner import (
    EvalRunConfig,
    EvalRunner,
    EvalRunResult,
    TrialResult,
)
from agent_evals.tasks.base import TaskDefinition
from agent_evals.variants.base import VariantMetadata
from agent_evals.variants.baselines import (
    LengthMatchedRandomBaseline,
    OracleBaseline,
)
from agent_index.models import DocFile, DocTree

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_task_definition(
    *,
    task_id: str = "retrieval_001",
    task_type: str = "retrieval",
    question: str = "What is authentication?",
    domain: str = "framework_api",
    difficulty: str = "easy",
) -> TaskDefinition:
    """Create a minimal TaskDefinition for testing."""
    return TaskDefinition(
        task_id=task_id,
        type=task_type,
        question=question,
        domain=domain,
        difficulty=difficulty,
    )


def _make_mock_task(
    *,
    task_id: str = "retrieval_001",
    score: float = 0.85,
) -> MagicMock:
    """Create a mock EvalTask."""
    task = MagicMock()
    task.definition = _make_task_definition(task_id=task_id)
    task.build_prompt.return_value = [
        {"role": "system", "content": "Use this index."},
        {"role": "user", "content": "What is auth?"},
    ]
    task.score_response.return_value = score
    return task


def _make_mock_variant(
    *,
    name: str = "test-variant",
    axis: int = 1,
) -> MagicMock:
    """Create a mock IndexVariant."""
    variant = MagicMock()
    variant.metadata.return_value = VariantMetadata(
        name=name,
        axis=axis,
        category="test",
        description="A test variant",
        token_estimate=100,
    )
    variant.render.return_value = "# Index Content\nSome docs here."
    return variant


def _make_mock_client(
    *,
    content: str = "The answer is authentication via OAuth.",
    prompt_tokens: int = 50,
    completion_tokens: int = 20,
    total_tokens: int = 70,
    cost: float | None = 0.001,
) -> MagicMock:
    """Create a mock LLMClient."""
    client = MagicMock(spec=LLMClient)
    client.model = "openrouter/anthropic/claude-sonnet-4.5"
    client.temperature = 0.3
    client.complete.return_value = GenerationResult(
        content=content,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost=cost,
        model="openrouter/anthropic/claude-sonnet-4.5",
        generation_id="gen-test-123",
    )
    return client


def _make_sample_doc_tree() -> DocTree:
    """Create a minimal DocTree for testing."""
    return DocTree(
        files={
            "guides/auth.md": DocFile(
                rel_path="guides/auth.md",
                content="# Authentication\nHow to authenticate.",
                size_bytes=42,
                token_count=10,
                tier="required",
                section="Guides",
            ),
        },
        scanned_at=datetime(2024, 1, 1, tzinfo=UTC),
        source="/tmp/docs",
        total_tokens=10,
    )


# ---------------------------------------------------------------------------
# TrialResult dataclass tests
# ---------------------------------------------------------------------------


class TestTrialResult:
    """Tests for the TrialResult dataclass."""

    def test_fields_are_stored(self) -> None:
        result = TrialResult(
            task_id="retrieval_001",
            task_type="retrieval",
            variant_name="no-index",
            repetition=1,
            score=0.75,
            metrics={"faithfulness": 0.9},
            prompt_tokens=50,
            completion_tokens=20,
            total_tokens=70,
            cost=0.001,
            latency_seconds=1.5,
            response="The answer is X.",
            cached=False,
        )
        assert result.task_id == "retrieval_001"
        assert result.task_type == "retrieval"
        assert result.variant_name == "no-index"
        assert result.repetition == 1
        assert result.score == 0.75
        assert result.metrics == {"faithfulness": 0.9}
        assert result.prompt_tokens == 50
        assert result.completion_tokens == 20
        assert result.total_tokens == 70
        assert result.cost == 0.001
        assert result.latency_seconds == 1.5
        assert result.response == "The answer is X."
        assert result.cached is False

    def test_cost_can_be_none(self) -> None:
        result = TrialResult(
            task_id="retrieval_001",
            task_type="retrieval",
            variant_name="v",
            repetition=1,
            score=0.0,
            metrics={},
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost=None,
            latency_seconds=0.0,
            response="",
            cached=True,
        )
        assert result.cost is None
        assert result.cached is True

    def test_empty_metrics(self) -> None:
        result = TrialResult(
            task_id="retrieval_001",
            task_type="retrieval",
            variant_name="v",
            repetition=1,
            score=0.5,
            metrics={},
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost=None,
            latency_seconds=0.1,
            response="resp",
            cached=False,
        )
        assert result.metrics == {}


# ---------------------------------------------------------------------------
# EvalRunConfig dataclass tests
# ---------------------------------------------------------------------------


class TestEvalRunConfig:
    """Tests for EvalRunConfig defaults and custom values."""

    def test_defaults(self) -> None:
        config = EvalRunConfig()
        assert config.repetitions == 10
        assert config.max_connections == 10
        assert config.max_tasks == 1
        assert config.temperature == 0.3
        assert config.max_tokens == 2048
        assert config.use_cache is True
        assert config.cache_dir == ".agent-evals-cache"
        assert config.output_dir == "reports"
        assert config.display_mode == "rich"

    def test_custom_values(self) -> None:
        config = EvalRunConfig(
            repetitions=5,
            max_connections=20,
            max_tasks=3,
            temperature=0.7,
            max_tokens=4096,
            use_cache=False,
            cache_dir="/tmp/cache",
            output_dir="/tmp/reports",
            display_mode="plain",
        )
        assert config.repetitions == 5
        assert config.max_connections == 20
        assert config.max_tasks == 3
        assert config.temperature == 0.7
        assert config.max_tokens == 4096
        assert config.use_cache is False
        assert config.cache_dir == "/tmp/cache"
        assert config.output_dir == "/tmp/reports"
        assert config.display_mode == "plain"


# ---------------------------------------------------------------------------
# EvalRunResult dataclass tests
# ---------------------------------------------------------------------------


class TestEvalRunResult:
    """Tests for EvalRunResult fields."""

    def test_fields_are_stored(self) -> None:
        config = EvalRunConfig()
        result = EvalRunResult(
            config=config,
            trials=[],
            total_cost=0.0,
            total_tokens=0,
            elapsed_seconds=0.5,
        )
        assert result.config is config
        assert result.trials == []
        assert result.total_cost == 0.0
        assert result.total_tokens == 0
        assert result.elapsed_seconds == 0.5

    def test_with_trials(self) -> None:
        trial = TrialResult(
            task_id="retrieval_001",
            task_type="retrieval",
            variant_name="v",
            repetition=1,
            score=0.9,
            metrics={},
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            cost=0.001,
            latency_seconds=0.2,
            response="resp",
            cached=False,
        )
        result = EvalRunResult(
            config=EvalRunConfig(),
            trials=[trial],
            total_cost=0.001,
            total_tokens=15,
            elapsed_seconds=1.0,
        )
        assert len(result.trials) == 1
        assert result.total_cost == 0.001
        assert result.total_tokens == 15


# ---------------------------------------------------------------------------
# EvalRunner._run_trial tests
# ---------------------------------------------------------------------------


class TestRunTrial:
    """Tests for the _run_trial method."""

    def test_single_trial_returns_trial_result(self) -> None:
        """A single trial with a mock client returns a valid TrialResult."""
        client = _make_mock_client()
        config = EvalRunConfig(repetitions=1, use_cache=False)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task(score=0.85)
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        result = runner._run_trial(task, variant, doc_tree, 1)

        assert isinstance(result, TrialResult)
        assert result.task_id == "retrieval_001"
        assert result.variant_name == "test-variant"
        assert result.repetition == 1
        assert result.score == 0.85
        assert result.prompt_tokens == 50
        assert result.completion_tokens == 20
        assert result.total_tokens == 70
        assert result.cost == 0.001
        assert result.cached is False
        assert result.latency_seconds > 0
        assert result.response == "The answer is authentication via OAuth."

    def test_trial_calls_variant_render(self) -> None:
        """The trial renders the variant with the doc tree."""
        client = _make_mock_client()
        config = EvalRunConfig(use_cache=False)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task()
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        runner._run_trial(task, variant, doc_tree, 1)

        variant.render.assert_called_once_with(doc_tree)

    def test_trial_calls_build_prompt(self) -> None:
        """The trial builds a prompt with the rendered index content."""
        client = _make_mock_client()
        config = EvalRunConfig(use_cache=False)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task()
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        runner._run_trial(task, variant, doc_tree, 1)

        task.build_prompt.assert_called_once_with("# Index Content\nSome docs here.")

    def test_trial_calls_llm_complete(self) -> None:
        """The trial calls client.complete with the messages."""
        client = _make_mock_client()
        config = EvalRunConfig(use_cache=False, max_tokens=1024)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task()
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        runner._run_trial(task, variant, doc_tree, 1)

        client.complete.assert_called_once()
        call_args = client.complete.call_args
        assert call_args[0][0] == [
            {"role": "system", "content": "Use this index."},
            {"role": "user", "content": "What is auth?"},
        ]
        assert call_args[1]["max_tokens"] == 1024

    def test_trial_calls_score_response(self) -> None:
        """The trial scores the LLM response."""
        client = _make_mock_client(content="my response")
        config = EvalRunConfig(use_cache=False)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task(score=0.7)
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        result = runner._run_trial(task, variant, doc_tree, 1)

        task.score_response.assert_called_once_with("my response")
        assert result.score == 0.7


# ---------------------------------------------------------------------------
# Cache integration tests
# ---------------------------------------------------------------------------


class TestCacheIntegration:
    """Tests for cache hit/miss behavior."""

    def test_cache_hit_skips_llm_call(self) -> None:
        """When the cache has an entry, the LLM client is not called."""
        client = _make_mock_client()
        cache = MagicMock(spec=ResponseCache)
        cache.make_key.return_value = "test-cache-key"
        cache.get.return_value = CacheEntry(
            key="test-cache-key",
            response={
                "content": "cached answer",
                "prompt_tokens": 30,
                "completion_tokens": 10,
                "total_tokens": 40,
                "cost": 0.0005,
                "model": "openrouter/anthropic/claude-sonnet-4.5",
                "generation_id": "gen-cached",
            },
            created_at=1700000000.0,
            model="openrouter/anthropic/claude-sonnet-4.5",
            tokens_used=40,
            cache_version=1,
        )

        config = EvalRunConfig(repetitions=1, use_cache=True)
        runner = EvalRunner(client=client, config=config, cache=cache)

        task = _make_mock_task()
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        result = runner._run_trial(task, variant, doc_tree, 1)

        # LLM was NOT called
        client.complete.assert_not_called()
        # But scoring was still called
        task.score_response.assert_called_once_with("cached answer")
        assert result.cached is True
        assert result.response == "cached answer"
        assert result.total_tokens == 40

    def test_cache_miss_calls_llm_and_stores(self) -> None:
        """When the cache misses, the LLM is called and result is stored."""
        client = _make_mock_client(content="fresh answer")
        cache = MagicMock(spec=ResponseCache)
        cache.make_key.return_value = "test-key"
        cache.get.return_value = None

        config = EvalRunConfig(repetitions=1, use_cache=True)
        runner = EvalRunner(client=client, config=config, cache=cache)

        task = _make_mock_task()
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        result = runner._run_trial(task, variant, doc_tree, 1)

        # LLM was called
        client.complete.assert_called_once()
        # Cache was updated
        cache.put.assert_called_once()
        put_args = cache.put.call_args
        assert put_args[0][0] == "test-key"
        assert put_args[0][1]["content"] == "fresh answer"
        assert result.cached is False

    def test_cache_disabled_skips_cache(self) -> None:
        """When use_cache=False, no cache operations happen."""
        client = _make_mock_client()
        cache = MagicMock(spec=ResponseCache)

        config = EvalRunConfig(use_cache=False)
        runner = EvalRunner(client=client, config=config, cache=cache)

        task = _make_mock_task()
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        runner._run_trial(task, variant, doc_tree, 1)

        # Cache is never consulted
        cache.get.assert_not_called()
        cache.put.assert_not_called()
        # LLM is called directly
        client.complete.assert_called_once()


# ---------------------------------------------------------------------------
# EvalRunner.run tests
# ---------------------------------------------------------------------------


class TestRunMethod:
    """Tests for the run() orchestration method."""

    def test_multiple_repetitions_produce_n_results(self) -> None:
        """Running with N repetitions produces N results per task/variant."""
        client = _make_mock_client()
        config = EvalRunConfig(repetitions=3, use_cache=False, max_connections=2)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task()
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        result = runner.run([task], [variant], doc_tree)

        assert isinstance(result, EvalRunResult)
        assert len(result.trials) == 3
        reps = sorted(t.repetition for t in result.trials)
        assert reps == [1, 2, 3]

    def test_variant_setup_teardown_lifecycle(self) -> None:
        """Setup is called before trials and teardown after."""
        client = _make_mock_client()
        config = EvalRunConfig(repetitions=1, use_cache=False, max_connections=1)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task()
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        # Track call order
        call_order: list[str] = []
        variant.setup.side_effect = lambda dt: call_order.append("setup")
        variant.teardown.side_effect = lambda: call_order.append("teardown")
        variant.render.side_effect = lambda dt: (
            call_order.append("render") or "index content"
        )

        runner.run([task], [variant], doc_tree)

        assert call_order[0] == "setup"
        assert "render" in call_order
        assert call_order[-1] == "teardown"

    def test_teardown_called_even_on_error(self) -> None:
        """Teardown is called even when a trial raises and continue_on_error is False."""
        client = _make_mock_client()
        client.complete.side_effect = RuntimeError("API failure")
        config = EvalRunConfig(
            repetitions=1, use_cache=False, max_connections=1,
            continue_on_error=False,
        )
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task()
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        with pytest.raises(RuntimeError, match="API failure"):
            runner.run([task], [variant], doc_tree)

        # Teardown must still be called despite the exception
        variant.teardown.assert_called_once()

    def test_multiple_variants_each_get_setup_teardown(self) -> None:
        """Each variant gets its own setup and teardown call."""
        client = _make_mock_client()
        config = EvalRunConfig(repetitions=1, use_cache=False, max_connections=1)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task()
        v1 = _make_mock_variant(name="v1")
        v2 = _make_mock_variant(name="v2")
        doc_tree = _make_sample_doc_tree()

        runner.run([task], [v1, v2], doc_tree)

        v1.setup.assert_called_once_with(doc_tree)
        v1.teardown.assert_called_once()
        v2.setup.assert_called_once_with(doc_tree)
        v2.teardown.assert_called_once()

    def test_progress_callback_called(self) -> None:
        """The progress callback is called after each trial."""
        client = _make_mock_client()
        config = EvalRunConfig(repetitions=2, use_cache=False, max_connections=1)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task()
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        callback = MagicMock()
        runner.run([task], [variant], doc_tree, progress_callback=callback)

        assert callback.call_count == 2
        # Each call should have (completed, total, trial)
        for c in callback.call_args_list:
            completed, total, trial = c[0]
            assert total == 2
            assert isinstance(trial, TrialResult)
            assert 1 <= completed <= 2

    def test_progress_callback_none_is_fine(self) -> None:
        """Passing None for progress_callback does not raise."""
        client = _make_mock_client()
        config = EvalRunConfig(repetitions=1, use_cache=False, max_connections=1)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task()
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        result = runner.run([task], [variant], doc_tree, progress_callback=None)
        assert len(result.trials) == 1

    def test_total_cost_aggregated(self) -> None:
        """Total cost is the sum of all trial costs."""
        client = _make_mock_client(cost=0.002)
        config = EvalRunConfig(repetitions=3, use_cache=False, max_connections=1)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task()
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        result = runner.run([task], [variant], doc_tree)

        assert result.total_cost == pytest.approx(0.006)

    def test_total_tokens_aggregated(self) -> None:
        """Total tokens is the sum of all trial token counts."""
        client = _make_mock_client(total_tokens=100)
        config = EvalRunConfig(repetitions=2, use_cache=False, max_connections=1)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task()
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        result = runner.run([task], [variant], doc_tree)

        assert result.total_tokens == 200

    def test_elapsed_seconds_positive(self) -> None:
        """Elapsed time should be positive."""
        client = _make_mock_client()
        config = EvalRunConfig(repetitions=1, use_cache=False, max_connections=1)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task()
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        result = runner.run([task], [variant], doc_tree)

        assert result.elapsed_seconds > 0

    def test_config_stored_in_result(self) -> None:
        """The run result stores the config that was used."""
        client = _make_mock_client()
        config = EvalRunConfig(repetitions=1, use_cache=False)
        runner = EvalRunner(client=client, config=config)

        result = runner.run(
            [_make_mock_task()],
            [_make_mock_variant()],
            _make_sample_doc_tree(),
        )

        assert result.config is config


# ---------------------------------------------------------------------------
# Concurrent execution tests
# ---------------------------------------------------------------------------


class TestConcurrentExecution:
    """Tests for concurrent trial execution via ThreadPoolExecutor."""

    def test_multiple_tasks_run_concurrently(self) -> None:
        """Multiple tasks complete when max_connections > 1."""
        client = _make_mock_client()
        config = EvalRunConfig(
            repetitions=1, use_cache=False, max_connections=4
        )
        runner = EvalRunner(client=client, config=config)

        tasks = [
            _make_mock_task(task_id="retrieval_001"),
            _make_mock_task(task_id="retrieval_002"),
            _make_mock_task(task_id="retrieval_003"),
        ]
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        result = runner.run(tasks, [variant], doc_tree)

        assert len(result.trials) == 3
        task_ids = {t.task_id for t in result.trials}
        assert task_ids == {"retrieval_001", "retrieval_002", "retrieval_003"}

    def test_multiple_variants_and_tasks(self) -> None:
        """Combinations of tasks and variants all produce results."""
        client = _make_mock_client()
        config = EvalRunConfig(
            repetitions=2, use_cache=False, max_connections=4
        )
        runner = EvalRunner(client=client, config=config)

        tasks = [
            _make_mock_task(task_id="retrieval_001"),
            _make_mock_task(task_id="retrieval_002"),
        ]
        variants = [
            _make_mock_variant(name="v1"),
            _make_mock_variant(name="v2"),
        ]
        doc_tree = _make_sample_doc_tree()

        result = runner.run(tasks, variants, doc_tree)

        # 2 tasks * 2 variants * 2 reps = 8
        assert len(result.trials) == 8

    def test_thread_pool_uses_max_connections(self) -> None:
        """ThreadPoolExecutor is configured with max_connections workers."""
        client = _make_mock_client()
        config = EvalRunConfig(
            repetitions=1, use_cache=False, max_connections=7
        )
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task()
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        with patch(
            "agent_evals.runner.ThreadPoolExecutor",
            wraps=ThreadPoolExecutor,
        ) as mock_pool:
            runner.run([task], [variant], doc_tree)
            mock_pool.assert_called_once_with(max_workers=7)


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Tests for error handling in the runner."""

    def test_llm_client_error_propagates(self) -> None:
        """An LLMClientError from the client propagates from run()."""
        client = _make_mock_client()
        client.complete.side_effect = LLMClientError("API timeout")

        config = EvalRunConfig(repetitions=1, use_cache=False, max_connections=1)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task()
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        with pytest.raises(LLMClientError, match="API timeout"):
            runner.run([task], [variant], doc_tree)

    def test_generic_exception_propagates(self) -> None:
        """A generic exception from the client propagates."""
        client = _make_mock_client()
        client.complete.side_effect = RuntimeError("unexpected failure")

        config = EvalRunConfig(repetitions=1, use_cache=False, max_connections=1)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task()
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        with pytest.raises(RuntimeError, match="unexpected failure"):
            runner.run([task], [variant], doc_tree)


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Tests for empty inputs and edge cases."""

    def test_empty_tasks_returns_empty_trials(self) -> None:
        """Running with no tasks produces zero trials."""
        client = _make_mock_client()
        config = EvalRunConfig(repetitions=5, use_cache=False)
        runner = EvalRunner(client=client, config=config)

        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        result = runner.run([], [variant], doc_tree)

        assert len(result.trials) == 0
        assert result.total_cost == 0.0
        assert result.total_tokens == 0
        # Setup/teardown still called for the variant
        variant.setup.assert_called_once()
        variant.teardown.assert_called_once()

    def test_empty_variants_returns_empty_trials(self) -> None:
        """Running with no variants produces zero trials."""
        client = _make_mock_client()
        config = EvalRunConfig(repetitions=5, use_cache=False)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task()
        doc_tree = _make_sample_doc_tree()

        result = runner.run([task], [], doc_tree)

        assert len(result.trials) == 0
        assert result.total_cost == 0.0
        assert result.total_tokens == 0

    def test_empty_tasks_and_variants(self) -> None:
        """Running with no tasks and no variants produces zero trials."""
        client = _make_mock_client()
        config = EvalRunConfig(use_cache=False)
        runner = EvalRunner(client=client, config=config)

        result = runner.run([], [], _make_sample_doc_tree())

        assert len(result.trials) == 0

    def test_none_cost_in_total(self) -> None:
        """Trials with None cost are treated as 0 in the total."""
        client = _make_mock_client(cost=None)
        config = EvalRunConfig(repetitions=2, use_cache=False, max_connections=1)
        runner = EvalRunner(client=client, config=config)

        result = runner.run(
            [_make_mock_task()],
            [_make_mock_variant()],
            _make_sample_doc_tree(),
        )

        assert result.total_cost == 0.0

    def test_default_config_when_none(self) -> None:
        """When config is None, default EvalRunConfig is used."""
        client = _make_mock_client()
        runner = EvalRunner(client=client, config=None, cache=ResponseCache(enabled=False))

        # Confirm default config is used
        assert runner._config.repetitions == 10
        assert runner._config.max_connections == 10

    def test_default_cache_created_when_use_cache_true(self) -> None:
        """When no cache is provided and use_cache is True, one is created."""
        client = _make_mock_client()
        config = EvalRunConfig(use_cache=True, cache_dir="/tmp/test-cache")
        runner = EvalRunner(client=client, config=config)

        assert isinstance(runner._cache, ResponseCache)

    def test_disabled_cache_created_when_use_cache_false(self) -> None:
        """When use_cache is False and no cache provided, a disabled cache is created."""
        client = _make_mock_client()
        config = EvalRunConfig(use_cache=False)
        runner = EvalRunner(client=client, config=config)

        assert isinstance(runner._cache, ResponseCache)


# ---------------------------------------------------------------------------
# Output format tests
# ---------------------------------------------------------------------------


class TestOutputFormat:
    """Tests for the output_format config option controlling file output."""

    def test_json_only_creates_no_csv(self, tmp_path: Path) -> None:
        config = EvalRunConfig(output_dir=str(tmp_path), output_format="json")
        runner = EvalRunner(
            client=MagicMock(spec=LLMClient),
            config=config,
        )
        result = EvalRunResult(
            config=config, trials=[], total_cost=0, total_tokens=0, elapsed_seconds=0,
        )
        paths = runner._save_results(result, [])
        json_files = list(tmp_path.glob("*.json"))
        csv_files = list(tmp_path.glob("*.csv"))
        assert len(json_files) == 1
        assert len(csv_files) == 0

    def test_csv_only_creates_no_json(self, tmp_path: Path) -> None:
        config = EvalRunConfig(output_dir=str(tmp_path), output_format="csv")
        runner = EvalRunner(
            client=MagicMock(spec=LLMClient),
            config=config,
        )
        result = EvalRunResult(
            config=config, trials=[], total_cost=0, total_tokens=0, elapsed_seconds=0,
        )
        paths = runner._save_results(result, [])
        json_files = list(tmp_path.glob("*.json"))
        csv_files = list(tmp_path.glob("*.csv"))
        assert len(json_files) == 0
        assert len(csv_files) == 1

    def test_both_creates_json_and_csv(self, tmp_path: Path) -> None:
        config = EvalRunConfig(output_dir=str(tmp_path), output_format="both")
        runner = EvalRunner(
            client=MagicMock(spec=LLMClient),
            config=config,
        )
        result = EvalRunResult(
            config=config, trials=[], total_cost=0, total_tokens=0, elapsed_seconds=0,
        )
        paths = runner._save_results(result, [])
        json_files = list(tmp_path.glob("*.json"))
        csv_files = list(tmp_path.glob("*.csv"))
        assert len(json_files) == 1
        assert len(csv_files) == 1


# ---------------------------------------------------------------------------
# Oracle / Length-Matched-Random baseline wiring tests
# ---------------------------------------------------------------------------


def _make_mock_task_with_metadata(
    *,
    task_id: str = "retrieval_001",
    task_type: str = "retrieval",
    score: float = 0.85,
    metadata: dict | None = None,
) -> MagicMock:
    """Create a mock EvalTask with specific metadata."""
    task = MagicMock()
    task.definition = TaskDefinition(
        task_id=task_id,
        type=task_type,
        question="What is authentication?",
        domain="framework_api",
        difficulty="easy",
        metadata=metadata or {},
    )
    task.build_prompt.return_value = [
        {"role": "system", "content": "Use this index."},
        {"role": "user", "content": "What is auth?"},
    ]
    task.score_response.return_value = score
    return task


class TestOracleBaselineWiring:
    """Tests that the runner wires up OracleBaseline.set_relevant_docs before render."""

    def test_oracle_renders_nonempty_with_expected_files(self) -> None:
        """Oracle baseline renders non-empty when task has expected_files metadata."""
        client = _make_mock_client()
        config = EvalRunConfig(repetitions=1, use_cache=False, max_connections=1)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task_with_metadata(
            metadata={"expected_files": ["guides/auth.md"]},
        )
        variant = OracleBaseline()
        doc_tree = _make_sample_doc_tree()

        result = runner._run_trial(task, variant, doc_tree, 1)

        # The oracle should have rendered non-empty content
        # (not identical to no-index which returns "")
        call_args = task.build_prompt.call_args[0][0]
        assert len(call_args) > 0, "Oracle should render non-empty index content"
        assert "guides/auth.md" in call_args

    def test_oracle_renders_nonempty_with_nearest_doc(self) -> None:
        """Oracle baseline renders non-empty when task has nearest_doc metadata."""
        client = _make_mock_client()
        config = EvalRunConfig(repetitions=1, use_cache=False, max_connections=1)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task_with_metadata(
            task_id="negative_001",
            task_type="negative",
            metadata={"nearest_doc": "guides/auth.md"},
        )
        variant = OracleBaseline()
        doc_tree = _make_sample_doc_tree()

        runner._run_trial(task, variant, doc_tree, 1)

        call_args = task.build_prompt.call_args[0][0]
        assert len(call_args) > 0, "Oracle should render non-empty with nearest_doc"

    def test_oracle_renders_nonempty_with_sources(self) -> None:
        """Oracle baseline renders non-empty when task has sources metadata."""
        client = _make_mock_client()
        config = EvalRunConfig(repetitions=1, use_cache=False, max_connections=1)
        runner = EvalRunner(client=client, config=config)

        doc_tree = DocTree(
            files={
                "api/caching.md": DocFile(
                    rel_path="api/caching.md",
                    content="# Caching\nCache docs.",
                    size_bytes=30,
                    token_count=8,
                    tier="recommended",
                    section="API",
                ),
            },
            scanned_at=datetime(2024, 1, 1, tzinfo=UTC),
            source="/tmp/docs",
            total_tokens=8,
        )

        task = _make_mock_task_with_metadata(
            task_id="conflicting_001",
            task_type="conflicting",
            metadata={
                "sources": [
                    {"name": "caching.md", "claim": "TTL=300", "authority": 9},
                ],
            },
        )
        variant = OracleBaseline()

        runner._run_trial(task, variant, doc_tree, 1)

        call_args = task.build_prompt.call_args[0][0]
        assert len(call_args) > 0, "Oracle should render non-empty with sources"


class TestLengthMatchedRandomWiring:
    """Tests that the runner wires up LengthMatchedRandomBaseline.set_target_tokens."""

    def test_lmr_renders_nonempty_with_expected_files(self) -> None:
        """Length-matched-random renders non-empty when task has expected_files."""
        client = _make_mock_client()
        config = EvalRunConfig(repetitions=1, use_cache=False, max_connections=1)
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task_with_metadata(
            metadata={"expected_files": ["guides/auth.md"]},
        )
        variant = LengthMatchedRandomBaseline()
        doc_tree = _make_sample_doc_tree()

        runner._run_trial(task, variant, doc_tree, 1)

        call_args = task.build_prompt.call_args[0][0]
        assert len(call_args) > 0, "LMR should render non-empty index content"


# ---------------------------------------------------------------------------
# Failed trial recording tests
# ---------------------------------------------------------------------------


class TestFailedTrialRecording:
    """Tests that failed trials are recorded in results instead of silently dropped."""

    def test_failed_trial_recorded_with_continue_on_error(self) -> None:
        """When continue_on_error=True, failed trials appear in results with error."""
        client = _make_mock_client()
        client.complete.side_effect = LLMClientError("Rate limit exceeded")

        config = EvalRunConfig(
            repetitions=1, use_cache=False, max_connections=1,
            continue_on_error=True,
        )
        runner = EvalRunner(client=client, config=config)

        task = _make_mock_task()
        variant = _make_mock_variant()
        doc_tree = _make_sample_doc_tree()

        result = runner.run([task], [variant], doc_tree)

        # Trial should be recorded, not silently dropped
        assert len(result.trials) == 1, "Failed trial should be recorded in results"
        trial = result.trials[0]
        assert trial.error is not None, "Failed trial should have error field set"
        assert "Rate limit" in trial.error
        assert trial.score == 0.0
        assert trial.task_id == "retrieval_001"
        assert trial.variant_name == "test-variant"

    def test_failed_trial_error_in_csv(self, tmp_path: Path) -> None:
        """Failed trials include error column in CSV output."""
        config = EvalRunConfig(
            output_dir=str(tmp_path), output_format="csv",
        )
        runner = EvalRunner(
            client=MagicMock(spec=LLMClient),
            config=config,
        )

        error_trial = TrialResult(
            task_id="test_001",
            task_type="retrieval",
            variant_name="v",
            repetition=1,
            score=0.0,
            metrics={},
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost=None,
            latency_seconds=0.1,
            response="",
            cached=False,
            error="Rate limit exceeded",
        )

        result = EvalRunResult(
            config=config,
            trials=[error_trial],
            total_cost=0,
            total_tokens=0,
            elapsed_seconds=0,
        )
        runner._save_results(result, [])

        csv_files = list(tmp_path.glob("*.csv"))
        assert len(csv_files) == 1
        content = csv_files[0].read_text()
        assert "error" in content.splitlines()[0], "CSV should have error column"
        assert "Rate limit exceeded" in content

    def test_trial_result_has_error_field(self) -> None:
        """TrialResult supports an error field defaulting to None."""
        result = TrialResult(
            task_id="test_001",
            task_type="retrieval",
            variant_name="v",
            repetition=1,
            score=0.0,
            metrics={},
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost=None,
            latency_seconds=0.0,
            response="",
            cached=False,
        )
        assert result.error is None

        result_with_error = TrialResult(
            task_id="test_001",
            task_type="retrieval",
            variant_name="v",
            repetition=1,
            score=0.0,
            metrics={},
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost=None,
            latency_seconds=0.0,
            response="",
            cached=False,
            error="Some error message",
        )
        assert result_with_error.error == "Some error message"
