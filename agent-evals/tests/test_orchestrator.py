"""Tests for EvalOrchestrator coordinating all subsystems.

Covers E5-S1: Orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig


class TestModeRouting:
    """Orchestrator routes to correct runner based on mode."""

    def test_full_mode_uses_eval_runner(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            mode="full",
            models=["test-model"],
            api_key="key",
            db_path=tmp_path / "obs.db",
        )
        orch = EvalOrchestrator(config)
        assert orch.runner_type == "eval"

    def test_taguchi_mode_uses_taguchi_runner(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            mode="taguchi",
            models=["test-model"],
            api_key="key",
            db_path=tmp_path / "obs.db",
        )
        orch = EvalOrchestrator(config)
        assert orch.runner_type == "taguchi"

    def test_default_mode_is_full(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            models=["test-model"],
            api_key="key",
            db_path=tmp_path / "obs.db",
        )
        assert config.mode == "full"
        orch = EvalOrchestrator(config)
        assert orch.runner_type == "eval"


class TestObservatoryInit:
    """Observatory initialized for all modes."""

    def test_store_created(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            mode="full",
            models=["m"],
            api_key="key",
            db_path=tmp_path / "obs.db",
        )
        orch = EvalOrchestrator(config)
        assert orch.store is not None

    def test_tracker_created(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            mode="full",
            models=["m"],
            api_key="key",
            db_path=tmp_path / "obs.db",
        )
        orch = EvalOrchestrator(config)
        assert orch.tracker is not None


class TestDashboard:
    """Dashboard started when flag is set."""

    def test_dashboard_flag_stored(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            mode="full",
            models=["m"],
            api_key="key",
            db_path=tmp_path / "obs.db",
            dashboard=True,
        )
        orch = EvalOrchestrator(config)
        assert orch.config.dashboard is True

    def test_dashboard_default_false(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            mode="full",
            models=["m"],
            api_key="key",
            db_path=tmp_path / "obs.db",
        )
        assert config.dashboard is False


class TestClientPool:
    """Client pool created from model list."""

    def test_client_pool_has_all_models(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            mode="full",
            models=["model-a", "model-b"],
            api_key="key",
            db_path=tmp_path / "obs.db",
        )
        orch = EvalOrchestrator(config)
        assert orch.client_pool.models == ["model-a", "model-b"]

    def test_client_pool_budget(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            mode="full",
            models=["m"],
            api_key="key",
            db_path=tmp_path / "obs.db",
            global_budget=10.0,
        )
        orch = EvalOrchestrator(config)
        state = orch.client_pool.get_budget_state()
        assert state["global_budget"] == 10.0


class TestReportConfig:
    """Report generation configuration."""

    def test_report_format_stored(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            mode="full",
            models=["m"],
            api_key="key",
            db_path=tmp_path / "obs.db",
            report_format="both",
        )
        assert config.report_format == "both"

    def test_report_format_default_none(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            mode="full",
            models=["m"],
            api_key="key",
            db_path=tmp_path / "obs.db",
        )
        assert config.report_format is None


class TestMultiModelSequential:
    """Full mode with multiple models runs sequentially."""

    def test_models_list_preserved(self, tmp_path: Path) -> None:
        config = OrchestratorConfig(
            mode="full",
            models=["a", "b", "c"],
            api_key="key",
            db_path=tmp_path / "obs.db",
        )
        orch = EvalOrchestrator(config)
        assert orch.config.models == ["a", "b", "c"]
