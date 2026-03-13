"""Tests for bugs #247, #236, #237.

Bug #247: code_generation scorer always returns 1.0 because patterns
          are matched against the full response (including prose) rather
          than extracted code blocks only.

Bug #236: Response cache not cleared between pipeline phases, causing
          confirmation/refinement to replay screening responses.

Bug #237: Confirmation/refinement trials missing phase and oa_row_id
          fields in the observatory DB because the orchestrator callback
          only reads them from trial.metrics (set by TaguchiRunner) but
          confirmation/refinement use EvalRunner which doesn't set them.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from agent_evals.tasks.base import TaskDefinition
from agent_evals.tasks.code_generation import CodeGenerationTask

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _codegen_task(**meta_overrides: Any) -> CodeGenerationTask:
    """Create a CodeGenerationTask with overridable metadata."""
    meta: dict[str, Any] = {
        "expected_answer": "",
        "test": "",
        "entry_point": "",
        "canonical_solution": "",
        "libs": [],
        "doc_struct": {},
        "forbidden_patterns": [],
    }
    meta.update(meta_overrides)
    defn = TaskDefinition(
        task_id="code_generation_999",
        type="code_generation",
        question="Write code.",
        domain="framework_api",
        difficulty="easy",
        metadata=meta,
    )
    return CodeGenerationTask(defn)


# ===================================================================
# Bug #247: code_generation scorer matches prose, not code blocks
# ===================================================================


class TestBug247CodeGenScoringOnCodeBlocks:
    """Bug #247: patterns must be matched against code blocks, not prose."""

    def test_pattern_in_prose_only_does_not_match(self) -> None:
        """When the pattern appears only in LLM prose (not in code blocks),
        the match rate should be 0, not 1."""
        task = _codegen_task(
            test="Settings\nDATABASE_URL\nLOG_LEVEL",
        )
        # Response where keywords appear in prose but NOT in the code block
        response = (
            "Here's a Settings class with DATABASE_URL and LOG_LEVEL:\n\n"
            "```python\n"
            "class Config:\n"
            "    db = os.getenv('DB')\n"
            "    level = 'INFO'\n"
            "```"
        )
        score = task.score_response(response)
        # Without the fix, this would score ~1.0 because all patterns
        # match the full response text. With the fix, patterns only
        # match code blocks, so match_rate should be low.
        assert score < 0.7, (
            f"Score {score} too high — patterns matched prose, not code (bug #247)"
        )

    def test_pattern_in_code_block_matches(self) -> None:
        """When patterns appear inside code blocks, they should match."""
        task = _codegen_task(
            test="Settings\nDATABASE_URL\nLOG_LEVEL",
        )
        response = (
            "Here's the implementation:\n\n"
            "```python\n"
            "class Settings:\n"
            "    DATABASE_URL: str\n"
            "    LOG_LEVEL: str = 'INFO'\n"
            "```"
        )
        score = task.score_response(response)
        assert score >= 0.8, (
            f"Score {score} too low — patterns in code blocks should match"
        )

    def test_generic_patterns_dont_inflate_score(self) -> None:
        """Generic single-word patterns like 'id', 'service' shouldn't
        vacuously match LLM explanatory text."""
        task = _codegen_task(
            test="Pipeline\nparallel\nvalidat\ndedup\nid",
        )
        # Response with a completely wrong code block but keywords in prose
        response = (
            "I'll create a Pipeline with parallel execution, validation, "
            "deduplication by id field.\n\n"
            "```python\n"
            "print('hello world')\n"
            "```"
        )
        score = task.score_response(response)
        assert score < 0.5, (
            f"Score {score} too high — generic patterns matched prose (bug #247)"
        )

    def test_no_code_blocks_falls_back_to_full_response(self) -> None:
        """When there are no fenced code blocks, match against full response."""
        task = _codegen_task(
            test="def add\nreturn a + b",
        )
        response = "def add(a, b):\n    return a + b"
        score = task.score_response(response)
        # No code blocks, so fallback to full response matching
        assert score >= 0.8


# ===================================================================
# Bug #236: Cache not cleared between pipeline phases
# ===================================================================


class TestBug236PipelineCacheClearing:
    """Bug #236: cache must be cleared between pipeline phases."""

    def test_pipeline_calls_clear_cache_between_screening_and_confirmation(
        self,
    ) -> None:
        """DOEPipeline.run() must call orchestrator.clear_cache() after
        screening and before confirmation, so cached screening responses
        don't leak into confirmation trials."""
        from agent_evals.pipeline import DOEPipeline, PhaseResult, PipelineConfig

        config = PipelineConfig(models=["test-model"])
        mock_orchestrator = MagicMock()
        mock_orchestrator.store = None
        mock_orchestrator.config = MagicMock()
        mock_orchestrator.config.eval_config = MagicMock()
        mock_orchestrator.clear_cache = MagicMock(return_value=0)

        pipeline = DOEPipeline(config, mock_orchestrator)

        # Stub out the phase methods to return minimal PhaseResult objects
        screening = PhaseResult(
            run_id="screen_1",
            phase="screening",
            trials=[],
            optimal={"axis_1": "v1"},
            significant_factors=["axis_1", "axis_2"],
            predicted_sn=5.0,
            prediction_interval=(4.0, 6.0),
            se_prediction=0.5,
        )
        confirmation = PhaseResult(
            run_id="confirm_1",
            phase="confirmation",
            trials=[],
        )
        refinement = PhaseResult(
            run_id="refine_1",
            phase="refinement",
            trials=[],
            optimal={"axis_1": "v1"},
        )

        with (
            patch.object(pipeline, "run_screening", return_value=screening),
            patch.object(pipeline, "run_confirmation", return_value=confirmation),
            patch.object(pipeline, "run_refinement", return_value=refinement),
        ):
            pipeline.run(tasks=[], variants=[], doc_tree=MagicMock())

        # clear_cache must be called at least twice:
        # once between screening->confirmation and once between
        # confirmation->refinement.
        assert mock_orchestrator.clear_cache.call_count >= 2, (
            f"Expected clear_cache called >=2 times, "
            f"got {mock_orchestrator.clear_cache.call_count} (bug #236)"
        )

    def test_orchestrator_exposes_cache_clearing(self) -> None:
        """EvalOrchestrator must expose a clear_cache method for pipeline use."""
        from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig

        config = OrchestratorConfig(
            models=["test-model"],
            api_key="test-key",
        )
        # Use a mock store to avoid DB file creation
        mock_store = MagicMock()
        config.store = mock_store
        config.tracker = MagicMock()

        orchestrator = EvalOrchestrator(config)
        assert hasattr(orchestrator, 'clear_cache'), (
            "EvalOrchestrator must have a clear_cache method (bug #236)"
        )

    def test_eval_runner_cache_can_be_cleared(self) -> None:
        """EvalRunner must support cache clearing."""
        from agent_evals.llm.cache import ResponseCache

        cache = ResponseCache(enabled=True, cache_dir="/tmp/test-cache-236")
        # Put an entry
        cache.put("test_key", {"text": "hello"}, "model", 100)
        assert cache.get("test_key") is not None

        # Clear
        cache.clear()
        assert cache.get("test_key") is None


# ===================================================================
# Bug #237: Confirmation/refinement trials missing phase/oa_row_id
# ===================================================================


class TestBug237TrialPhaseTagging:
    """Bug #237: orchestrator must inject phase into trial metrics."""

    def test_orchestrator_injects_phase_into_callback(self) -> None:
        """When phase is passed to orchestrator.run(), every trial recorded
        via the tracker must have that phase, even if the trial's own
        metrics don't include it."""
        from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig
        from agent_evals.runner import EvalRunConfig, EvalRunResult, TrialResult

        mock_store = MagicMock()
        mock_store.create_run = MagicMock()
        mock_store.finish_run = MagicMock()

        mock_tracker = MagicMock()

        config = OrchestratorConfig(
            models=["test-model"],
            api_key="test-key",
            store=mock_store,
            tracker=mock_tracker,
        )
        orchestrator = EvalOrchestrator(config)

        # Create a trial without phase in metrics (like EvalRunner produces)
        trial = TrialResult(
            task_id="task_1",
            task_type="code_generation",
            variant_name="variant_a",
            repetition=1,
            score=0.8,
            metrics={},  # No phase or oa_row_id
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.001,
            latency_seconds=1.0,
            response="code here",
            cached=False,
        )

        # Mock _run_full to invoke progress_callback for each trial
        def fake_run_full(*, tasks, variants, doc_tree, eval_config,
                          progress_callback, source, completed_keys=None):
            if progress_callback:
                progress_callback(1, 1, trial)
            return EvalRunResult(
                config=EvalRunConfig(),
                trials=[trial],
                total_cost=0.001,
                total_tokens=150,
                elapsed_seconds=1.0,
            )

        with patch.object(orchestrator, '_run_full', side_effect=fake_run_full):
            orchestrator.run(
                tasks=[],
                variants=[],
                doc_tree=MagicMock(),
                phase="confirmation",
                pipeline_id="test_pipeline",
                mode="full",
            )

        # The tracker.record_trial MUST have been called
        assert mock_tracker.record_trial.called, (
            "record_trial was not called — callback not invoked"
        )
        call_kwargs = mock_tracker.record_trial.call_args[1]
        assert call_kwargs.get("phase") == "confirmation", (
            f"Expected phase='confirmation', got {call_kwargs.get('phase')!r} (bug #237)"
        )

    def test_screening_phase_preserved_from_metrics(self) -> None:
        """When trial.metrics already has phase (TaguchiRunner), use it."""
        from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig
        from agent_evals.runner import EvalRunConfig, EvalRunResult, TrialResult

        mock_store = MagicMock()
        mock_store.create_run = MagicMock()
        mock_store.finish_run = MagicMock()
        mock_tracker = MagicMock()

        config = OrchestratorConfig(
            models=["test-model"],
            api_key="test-key",
            store=mock_store,
            tracker=mock_tracker,
        )
        orchestrator = EvalOrchestrator(config)

        trial = TrialResult(
            task_id="task_1",
            task_type="code_generation",
            variant_name="variant_a",
            repetition=1,
            score=0.8,
            metrics={"phase": "screening", "oa_row_id": 5.0},
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost=0.001,
            latency_seconds=1.0,
            response="code here",
            cached=False,
        )

        # Mock _run_taguchi to invoke callback
        def fake_run_taguchi(*, tasks, doc_tree, eval_config, design,
                             variant_lookup, progress_callback, source,
                             phase=None, completed_keys=None):
            if progress_callback:
                progress_callback(1, 1, trial)
            return EvalRunResult(
                config=EvalRunConfig(),
                trials=[trial],
                total_cost=0.001,
                total_tokens=150,
                elapsed_seconds=1.0,
            )

        with patch.object(orchestrator, '_run_taguchi', side_effect=fake_run_taguchi):
            orchestrator.run(
                tasks=[],
                variants=[],
                doc_tree=MagicMock(),
                design=MagicMock(),
                variant_lookup={},
                phase="screening",
                pipeline_id="test_pipeline",
            )

        assert mock_tracker.record_trial.called
        call_kwargs = mock_tracker.record_trial.call_args[1]
        assert call_kwargs.get("phase") == "screening"
        assert call_kwargs.get("oa_row_id") == 5.0

    def test_refinement_phase_injected_when_metrics_empty(self) -> None:
        """Refinement trials (via EvalRunner) should get phase='refinement'
        even though their metrics dict is empty."""
        from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig
        from agent_evals.runner import EvalRunConfig, EvalRunResult, TrialResult

        mock_store = MagicMock()
        mock_store.create_run = MagicMock()
        mock_store.finish_run = MagicMock()
        mock_tracker = MagicMock()

        config = OrchestratorConfig(
            models=["test-model"],
            api_key="test-key",
            store=mock_store,
            tracker=mock_tracker,
        )
        orchestrator = EvalOrchestrator(config)

        trial = TrialResult(
            task_id="task_2",
            task_type="code_generation",
            variant_name="variant_b",
            repetition=1,
            score=0.75,
            metrics={},  # Empty -- EvalRunner doesn't set phase
            prompt_tokens=80,
            completion_tokens=40,
            total_tokens=120,
            cost=0.001,
            latency_seconds=0.8,
            response="some code",
            cached=False,
        )

        def fake_run_full(*, tasks, variants, doc_tree, eval_config,
                          progress_callback, source, completed_keys=None):
            if progress_callback:
                progress_callback(1, 1, trial)
            return EvalRunResult(
                config=EvalRunConfig(),
                trials=[trial],
                total_cost=0.001,
                total_tokens=120,
                elapsed_seconds=0.8,
            )

        with patch.object(orchestrator, '_run_full', side_effect=fake_run_full):
            orchestrator.run(
                tasks=[],
                variants=[],
                doc_tree=MagicMock(),
                phase="refinement",
                pipeline_id="test_pipeline_2",
                mode="full",
            )

        assert mock_tracker.record_trial.called
        call_kwargs = mock_tracker.record_trial.call_args[1]
        assert call_kwargs.get("phase") == "refinement", (
            f"Expected phase='refinement', got {call_kwargs.get('phase')!r} (bug #237)"
        )
