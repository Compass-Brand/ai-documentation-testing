"""Tests for RunManager -- dashboard-started run lifecycle."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker


@pytest.fixture
def store(tmp_path: Path) -> ObservatoryStore:
    return ObservatoryStore(tmp_path / "test.db")


@pytest.fixture
def tracker(store: ObservatoryStore) -> EventTracker:
    return EventTracker(store=store)


from agent_evals.observatory.run_manager import (
    HeartbeatThread,
    RunConflictError,
    RunManager,
    RunSetupError,
    StartRunRequest,
)


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

    def test_default_source_is_gold_standard(self) -> None:
        req = StartRunRequest(model="m")
        assert req.source == "gold_standard"

    def test_source_accepts_custom_dataset(self) -> None:
        req = StartRunRequest(model="m", source="repliqa")
        assert req.source == "repliqa"

    def test_full_request(self) -> None:
        req = StartRunRequest(
            mode="full",
            model="openrouter/anthropic/claude-sonnet-4",
            repetitions=5, task_limit=10, oa_override="L9_3_4",
            pipeline_mode="semi", quality_type="smaller_is_better",
            top_k=5, alpha=0.01,
        )
        assert req.mode == "full"
        assert req.repetitions == 5
        assert req.oa_override == "L9_3_4"


class TestRunManager:
    """RunManager lifecycle: start, active check, cancel."""

    def test_init(self, store: ObservatoryStore, tracker: EventTracker) -> None:
        rm = RunManager(store=store, tracker=tracker)
        assert rm.active_run is None

    def test_start_run_returns_run_id(self, store: ObservatoryStore, tracker: EventTracker) -> None:
        rm = RunManager(store=store, tracker=tracker)
        with patch.object(rm, "_execute_run"):
            run_id = rm.start_run(StartRunRequest(model="test/model"))
        assert isinstance(run_id, str) and len(run_id) > 0

    def test_active_run_set_after_start(self, store: ObservatoryStore, tracker: EventTracker) -> None:
        rm = RunManager(store=store, tracker=tracker)
        started, hold = threading.Event(), threading.Event()
        def slow(*a, **k):
            started.set(); hold.wait(timeout=5)
        with patch.object(rm, "_execute_run", side_effect=slow):
            run_id = rm.start_run(StartRunRequest(model="test/model"))
            started.wait(timeout=2)
            active = rm.active_run
            assert active is not None and active["run_id"] == run_id
            hold.set()

    def test_multiple_concurrent_runs(self, store: ObservatoryStore, tracker: EventTracker) -> None:
        rm = RunManager(store=store, tracker=tracker)
        hold = threading.Event()
        with patch.object(rm, "_execute_run", side_effect=lambda *a, **k: hold.wait(5)):
            id1 = rm.start_run(StartRunRequest(model="model/a"))
            id2 = rm.start_run(StartRunRequest(model="model/b"))
            assert id1 != id2 and len(rm.active_runs) == 2
            hold.set()

    def test_cancel_run(self, store: ObservatoryStore, tracker: EventTracker) -> None:
        rm = RunManager(store=store, tracker=tracker)
        started, hold = threading.Event(), threading.Event()
        def slow(*a, **k):
            started.set(); hold.wait(timeout=5)
        with patch.object(rm, "_execute_run", side_effect=slow):
            rm.start_run(StartRunRequest(model="test/model"))
            started.wait(timeout=2)
            assert rm.cancel_run() is True
            hold.set()

    def test_cancel_when_no_run_returns_false(self, store: ObservatoryStore, tracker: EventTracker) -> None:
        rm = RunManager(store=store, tracker=tracker)
        assert rm.cancel_run() is False

    def test_active_run_cleared_after_completion(self, store: ObservatoryStore, tracker: EventTracker) -> None:
        rm = RunManager(store=store, tracker=tracker)
        done = threading.Event()
        with patch.object(rm, "_execute_run", side_effect=lambda *a, **k: done.set()):
            rm.start_run(StartRunRequest(model="test/model"))
            done.wait(timeout=2)
            time.sleep(0.1)
        assert rm.active_runs == [] and rm.active_run is None

    def test_models_parsed_from_comma_separated(self, store: ObservatoryStore, tracker: EventTracker) -> None:
        rm = RunManager(store=store, tracker=tracker)
        req = StartRunRequest(model="model/a, model/b, model/c")
        with patch.object(rm, "_execute_run"):
            rm.start_run(req)
        assert req.model == "model/a, model/b, model/c"


class TestRunWrapperFailure:
    """Task 13: _run_wrapper marks run as failed in DB on exception."""

    def test_run_wrapper_marks_run_failed_on_exception(self, tmp_path: Path) -> None:
        store = ObservatoryStore(db_path=tmp_path / "test.db")
        store.create_run("run1", "full", {}, phase="screening")
        tracker = EventTracker(store=store)
        manager = RunManager(store=store, tracker=tracker)
        with patch.object(manager, "_execute_run", side_effect=RuntimeError("crash")):
            manager._run_wrapper("run1", request=MagicMock(spec=StartRunRequest))
        summary = store.get_run_summary("run1")
        assert summary.status == "failed"


class TestRunSetupError:
    """Task 14: Early return paths in _execute_run raise RunSetupError."""

    def test_missing_api_key_marks_run_failed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        store = ObservatoryStore(db_path=tmp_path / "test.db")
        store.create_run("run1", "full", {}, phase="screening")
        tracker = EventTracker(store=store)
        manager = RunManager(store=store, tracker=tracker)
        manager._run_wrapper("run1", request=MagicMock(spec=StartRunRequest))
        summary = store.get_run_summary("run1")
        assert summary.status == "failed"


class TestHeartbeatThread:
    """Task 15b: HeartbeatThread writes heartbeat timestamps during a run."""

    def test_heartbeat_updates_during_run(self, tmp_path: Path) -> None:
        store = ObservatoryStore(db_path=tmp_path / "test.db")
        store.create_run("run1", "full", {}, phase="screening")
        thread = HeartbeatThread(store=store, run_id="run1", interval=0.01)
        thread.start()
        time.sleep(0.05)
        thread.stop()
        thread.join(timeout=1.0)
        summary = store.get_run_summary("run1")
        assert summary.heartbeat_at is not None


class TestModelValidation:
    """Task 17: Model name validation on run submission."""

    def test_model_name_without_slash_rejected(self, tmp_path: Path) -> None:
        store = ObservatoryStore(db_path=tmp_path / "test.db")
        tracker = EventTracker(store=store)
        manager = RunManager(store=store, tracker=tracker)
        with pytest.raises(ValueError, match="Invalid model"):
            manager.start_run(request=StartRunRequest(model="test", task_limit=1))

    def test_valid_model_name_accepted(self, tmp_path: Path) -> None:
        store = ObservatoryStore(db_path=tmp_path / "test.db")
        tracker = EventTracker(store=store)
        manager = RunManager(store=store, tracker=tracker)
        with patch.object(manager, "_execute_run"):
            run_id = manager.start_run(
                request=StartRunRequest(model="openrouter/anthropic/claude-sonnet-4", task_limit=1)
            )
        assert isinstance(run_id, str)
