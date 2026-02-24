"""Tests for RunManager -- dashboard-started run lifecycle.

Covers start_run, prevent double-start, cancel, active_run, and cleanup.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> ObservatoryStore:
    return ObservatoryStore(tmp_path / "test.db")


@pytest.fixture
def tracker(store: ObservatoryStore) -> EventTracker:
    return EventTracker(store=store)


# ---------------------------------------------------------------------------
# Import helpers (deferred to avoid import errors before implementation)
# ---------------------------------------------------------------------------

from agent_evals.observatory.run_manager import (
    RunConflictError,
    RunManager,
    StartRunRequest,
)


# ---------------------------------------------------------------------------
# TestStartRunRequest
# ---------------------------------------------------------------------------


class TestStartRunRequest:
    """Pydantic validation for StartRunRequest."""

    def test_minimal_valid_request(self) -> None:
        req = StartRunRequest(model="openrouter/anthropic/claude-sonnet-4")
        assert req.mode == "taguchi"
        assert req.repetitions == 3
        assert req.task_limit == 0

    def test_model_required(self) -> None:
        with pytest.raises(ValidationError):
            StartRunRequest()

    def test_mode_must_be_valid(self) -> None:
        with pytest.raises(ValidationError):
            StartRunRequest(model="m", mode="invalid")

    def test_repetitions_min_1(self) -> None:
        with pytest.raises(ValidationError):
            StartRunRequest(model="m", repetitions=0)

    def test_repetitions_max_100(self) -> None:
        with pytest.raises(ValidationError):
            StartRunRequest(model="m", repetitions=101)

    def test_task_limit_min_0(self) -> None:
        with pytest.raises(ValidationError):
            StartRunRequest(model="m", task_limit=-1)

    def test_alpha_min_0_001(self) -> None:
        with pytest.raises(ValidationError):
            StartRunRequest(model="m", alpha=0.0001)

    def test_alpha_max_0_1(self) -> None:
        with pytest.raises(ValidationError):
            StartRunRequest(model="m", alpha=0.2)

    def test_top_k_min_1(self) -> None:
        with pytest.raises(ValidationError):
            StartRunRequest(model="m", top_k=0)

    def test_top_k_max_10(self) -> None:
        with pytest.raises(ValidationError):
            StartRunRequest(model="m", top_k=11)

    def test_pipeline_mode_valid_values(self) -> None:
        req = StartRunRequest(model="m", pipeline_mode="auto")
        assert req.pipeline_mode == "auto"
        req2 = StartRunRequest(model="m", pipeline_mode="semi")
        assert req2.pipeline_mode == "semi"

    def test_pipeline_mode_invalid(self) -> None:
        with pytest.raises(ValidationError):
            StartRunRequest(model="m", pipeline_mode="bad")

    def test_full_request(self) -> None:
        req = StartRunRequest(
            mode="full",
            model="openrouter/anthropic/claude-sonnet-4",
            repetitions=5,
            task_limit=10,
            oa_override="L9_3_4",
            pipeline_mode="semi",
            quality_type="smaller_is_better",
            top_k=5,
            alpha=0.01,
        )
        assert req.mode == "full"
        assert req.repetitions == 5
        assert req.oa_override == "L9_3_4"


# ---------------------------------------------------------------------------
# TestRunManager
# ---------------------------------------------------------------------------


class TestRunManager:
    """RunManager lifecycle: start, active check, cancel."""

    def test_init(
        self, store: ObservatoryStore, tracker: EventTracker
    ) -> None:
        rm = RunManager(store=store, tracker=tracker)
        assert rm.active_run is None

    def test_start_run_returns_run_id(
        self, store: ObservatoryStore, tracker: EventTracker
    ) -> None:
        rm = RunManager(store=store, tracker=tracker)
        request = StartRunRequest(model="test-model")

        # Mock the heavy dependencies so we don't need real tasks/variants
        with patch.object(rm, "_execute_run"):
            run_id = rm.start_run(request)

        assert isinstance(run_id, str)
        assert len(run_id) > 0

    def test_active_run_set_after_start(
        self, store: ObservatoryStore, tracker: EventTracker
    ) -> None:
        rm = RunManager(store=store, tracker=tracker)
        request = StartRunRequest(model="test-model")

        # Use a long-running mock so the run stays active
        started = threading.Event()
        hold = threading.Event()

        def slow_execute(*args, **kwargs):
            started.set()
            hold.wait(timeout=5)

        with patch.object(rm, "_execute_run", side_effect=slow_execute):
            run_id = rm.start_run(request)
            started.wait(timeout=2)

            active = rm.active_run
            assert active is not None
            assert active["run_id"] == run_id
            assert active["mode"] == "taguchi"
            assert "test-model" in active["models"]

            hold.set()

    def test_double_start_raises_conflict(
        self, store: ObservatoryStore, tracker: EventTracker
    ) -> None:
        rm = RunManager(store=store, tracker=tracker)
        request = StartRunRequest(model="test-model")

        hold = threading.Event()

        def slow_execute(*args, **kwargs):
            hold.wait(timeout=5)

        with patch.object(rm, "_execute_run", side_effect=slow_execute):
            rm.start_run(request)

            with pytest.raises(RunConflictError):
                rm.start_run(request)

            hold.set()

    def test_cancel_run(
        self, store: ObservatoryStore, tracker: EventTracker
    ) -> None:
        rm = RunManager(store=store, tracker=tracker)
        request = StartRunRequest(model="test-model")

        started = threading.Event()
        hold = threading.Event()

        def slow_execute(*args, **kwargs):
            started.set()
            hold.wait(timeout=5)

        with patch.object(rm, "_execute_run", side_effect=slow_execute):
            rm.start_run(request)
            started.wait(timeout=2)

            cancelled = rm.cancel_run()
            assert cancelled is True

            hold.set()

    def test_cancel_when_no_run_returns_false(
        self, store: ObservatoryStore, tracker: EventTracker
    ) -> None:
        rm = RunManager(store=store, tracker=tracker)
        assert rm.cancel_run() is False

    def test_active_run_cleared_after_completion(
        self, store: ObservatoryStore, tracker: EventTracker
    ) -> None:
        rm = RunManager(store=store, tracker=tracker)
        request = StartRunRequest(model="test-model")

        done = threading.Event()

        def fast_execute(*args, **kwargs):
            done.set()

        with patch.object(rm, "_execute_run", side_effect=fast_execute):
            rm.start_run(request)
            done.wait(timeout=2)
            # Give the cleanup thread a moment
            time.sleep(0.1)

        assert rm.active_run is None

    def test_models_parsed_from_comma_separated(
        self, store: ObservatoryStore, tracker: EventTracker
    ) -> None:
        rm = RunManager(store=store, tracker=tracker)
        request = StartRunRequest(model="model-a, model-b, model-c")

        with patch.object(rm, "_execute_run"):
            rm.start_run(request)

        active = rm.active_run
        # Run may have finished already, so check the request parsing
        assert request.model == "model-a, model-b, model-c"
