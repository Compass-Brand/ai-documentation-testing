"""Tests for DashboardConfig, DashboardHandle, and launch_dashboard().

TDD RED phase: all tests written before implementation.
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_evals.observatory.web.server import (
    DashboardConfig,
    DashboardHandle,
    launch_dashboard,
)


class TestDashboardConfig:
    """Tests for DashboardConfig dataclass defaults."""

    def test_default_observatory_db(self) -> None:
        cfg = DashboardConfig()
        assert cfg.observatory_db == Path.home() / ".observatory" / "observatory.db"

    def test_default_models_db(self) -> None:
        cfg = DashboardConfig()
        assert cfg.models_db == Path.home() / ".observatory" / "models.db"

    def test_default_host(self) -> None:
        cfg = DashboardConfig()
        assert cfg.host == "0.0.0.0"

    def test_default_port(self) -> None:
        cfg = DashboardConfig()
        assert cfg.port == 8080

    def test_default_log_level(self) -> None:
        cfg = DashboardConfig()
        assert cfg.log_level == "info"

    def test_default_auto_sync(self) -> None:
        cfg = DashboardConfig()
        assert cfg.auto_sync is True

    def test_default_sync_interval_hours(self) -> None:
        cfg = DashboardConfig()
        assert cfg.sync_interval_hours == 6.0

    def test_custom_values(self) -> None:
        cfg = DashboardConfig(
            observatory_db=Path("/tmp/obs.db"),
            models_db=Path("/tmp/models.db"),
            host="127.0.0.1",
            port=9090,
            log_level="debug",
            auto_sync=False,
            sync_interval_hours=12.0,
        )
        assert cfg.observatory_db == Path("/tmp/obs.db")
        assert cfg.models_db == Path("/tmp/models.db")
        assert cfg.host == "127.0.0.1"
        assert cfg.port == 9090
        assert cfg.log_level == "debug"
        assert cfg.auto_sync is False
        assert cfg.sync_interval_hours == 12.0


class TestDashboardHandle:
    """Tests for DashboardHandle.stop() behavior."""

    def test_stop_sets_shutdown_event(self) -> None:
        event = threading.Event()
        mock_server = MagicMock()
        handle = DashboardHandle(
            thread=None, shutdown_event=event, _server=mock_server
        )
        handle.stop()
        assert event.is_set()

    def test_stop_calls_server_shutdown(self) -> None:
        event = threading.Event()
        mock_server = MagicMock()
        handle = DashboardHandle(
            thread=None, shutdown_event=event, _server=mock_server
        )
        handle.stop()
        mock_server.should_exit = True

    def test_stop_joins_thread(self) -> None:
        event = threading.Event()
        mock_thread = MagicMock(spec=threading.Thread)
        mock_server = MagicMock()
        handle = DashboardHandle(
            thread=mock_thread, shutdown_event=event, _server=mock_server
        )
        handle.stop(timeout=3.0)
        mock_thread.join.assert_called_once_with(timeout=3.0)

    def test_stop_without_thread(self) -> None:
        event = threading.Event()
        mock_server = MagicMock()
        handle = DashboardHandle(
            thread=None, shutdown_event=event, _server=mock_server
        )
        # Should not raise even when thread is None
        handle.stop()
        assert event.is_set()

    def test_stop_without_server(self) -> None:
        event = threading.Event()
        handle = DashboardHandle(
            thread=None, shutdown_event=event, _server=None
        )
        # Should not raise even when _server is None
        handle.stop()
        assert event.is_set()


@pytest.fixture()
def tmp_config(tmp_path: Path) -> DashboardConfig:
    """Config using tmp_path for db files."""
    return DashboardConfig(
        observatory_db=tmp_path / "observatory.db",
        models_db=tmp_path / "models.db",
    )


class TestLaunchDashboardStandalone:
    """Tests for launch_dashboard() standalone mode (no store/tracker)."""

    @patch("agent_evals.observatory.web.server.uvicorn.Server")
    def test_creates_store_from_config(
        self, mock_server_cls: MagicMock, tmp_config: DashboardConfig
    ) -> None:
        mock_server = MagicMock()
        mock_server_cls.return_value = mock_server

        with patch(
            "agent_evals.observatory.web.server.ModelCatalog"
        ) as mock_catalog_cls:
            mock_catalog = MagicMock()
            mock_catalog.get_active_models.return_value = [{"id": "m1"}]
            mock_catalog_cls.return_value = mock_catalog

            handle = launch_dashboard(tmp_config, background=True)

        # Verify the server was constructed and handle returned
        assert handle is not None
        assert handle.shutdown_event is not None
        handle.stop()

    @patch("agent_evals.observatory.web.server.uvicorn.Server")
    def test_creates_db_directories(
        self, mock_server_cls: MagicMock, tmp_path: Path
    ) -> None:
        db_dir = tmp_path / "subdir" / "nested"
        cfg = DashboardConfig(
            observatory_db=db_dir / "observatory.db",
            models_db=db_dir / "models.db",
        )
        mock_server = MagicMock()
        mock_server_cls.return_value = mock_server

        with patch(
            "agent_evals.observatory.web.server.ModelCatalog"
        ) as mock_catalog_cls:
            mock_catalog = MagicMock()
            mock_catalog.get_active_models.return_value = [{"id": "m1"}]
            mock_catalog_cls.return_value = mock_catalog

            handle = launch_dashboard(cfg, background=True)

        assert db_dir.exists()
        handle.stop()


class TestLaunchDashboardEmbedded:
    """Tests for launch_dashboard() embedded mode (store/tracker provided)."""

    @patch("agent_evals.observatory.web.server.uvicorn.Server")
    def test_uses_provided_store_and_tracker(
        self, mock_server_cls: MagicMock, tmp_config: DashboardConfig
    ) -> None:
        mock_store = MagicMock()
        mock_tracker = MagicMock()
        mock_server = MagicMock()
        mock_server_cls.return_value = mock_server

        with patch(
            "agent_evals.observatory.web.server.ModelCatalog"
        ) as mock_catalog_cls:
            mock_catalog = MagicMock()
            mock_catalog.get_active_models.return_value = [{"id": "m1"}]
            mock_catalog_cls.return_value = mock_catalog

            with patch(
                "agent_evals.observatory.web.server.create_app"
            ) as mock_create_app:
                mock_create_app.return_value = MagicMock()
                handle = launch_dashboard(
                    tmp_config,
                    store=mock_store,
                    tracker=mock_tracker,
                    background=True,
                )

                # Verify create_app was called with the provided store/tracker
                mock_create_app.assert_called_once()
                call_kwargs = mock_create_app.call_args
                assert call_kwargs.kwargs.get("store") is mock_store or (
                    call_kwargs.args[0] is mock_store
                    if call_kwargs.args
                    else False
                )

        handle.stop()


class TestLaunchDashboardAutoSync:
    """Tests for auto-sync behavior."""

    @patch("agent_evals.observatory.web.server.uvicorn.Server")
    def test_auto_sync_triggers_when_catalog_empty(
        self, mock_server_cls: MagicMock, tmp_config: DashboardConfig
    ) -> None:
        mock_server = MagicMock()
        mock_server_cls.return_value = mock_server

        with (
            patch(
                "agent_evals.observatory.web.server.ModelCatalog"
            ) as mock_catalog_cls,
            patch(
                "agent_evals.observatory.web.server.ModelSync"
            ) as mock_sync_cls,
        ):
            mock_catalog = MagicMock()
            mock_catalog.get_active_models.return_value = []  # empty
            mock_catalog_cls.return_value = mock_catalog

            mock_sync = MagicMock()
            mock_sync_cls.return_value = mock_sync

            handle = launch_dashboard(tmp_config, background=True)

        mock_sync.run_sync.assert_called_once()
        handle.stop()

    @patch("agent_evals.observatory.web.server.uvicorn.Server")
    def test_skips_sync_when_auto_sync_false(
        self, mock_server_cls: MagicMock, tmp_path: Path
    ) -> None:
        cfg = DashboardConfig(
            observatory_db=tmp_path / "observatory.db",
            models_db=tmp_path / "models.db",
            auto_sync=False,
        )
        mock_server = MagicMock()
        mock_server_cls.return_value = mock_server

        with (
            patch(
                "agent_evals.observatory.web.server.ModelCatalog"
            ) as mock_catalog_cls,
            patch(
                "agent_evals.observatory.web.server.ModelSync"
            ) as mock_sync_cls,
        ):
            mock_catalog = MagicMock()
            mock_catalog.get_active_models.return_value = []
            mock_catalog_cls.return_value = mock_catalog

            mock_sync = MagicMock()
            mock_sync_cls.return_value = mock_sync

            handle = launch_dashboard(cfg, background=True)

        mock_sync.run_sync.assert_not_called()
        handle.stop()

    @patch("agent_evals.observatory.web.server.uvicorn.Server")
    def test_skips_sync_when_catalog_not_empty(
        self, mock_server_cls: MagicMock, tmp_config: DashboardConfig
    ) -> None:
        mock_server = MagicMock()
        mock_server_cls.return_value = mock_server

        with (
            patch(
                "agent_evals.observatory.web.server.ModelCatalog"
            ) as mock_catalog_cls,
            patch(
                "agent_evals.observatory.web.server.ModelSync"
            ) as mock_sync_cls,
        ):
            mock_catalog = MagicMock()
            mock_catalog.get_active_models.return_value = [{"id": "m1"}]
            mock_catalog_cls.return_value = mock_catalog

            mock_sync = MagicMock()
            mock_sync_cls.return_value = mock_sync

            handle = launch_dashboard(tmp_config, background=True)

        mock_sync.run_sync.assert_not_called()
        handle.stop()


class TestLaunchDashboardBackground:
    """Tests for background/foreground mode."""

    @patch("agent_evals.observatory.web.server.uvicorn.Server")
    def test_background_returns_handle_with_thread(
        self, mock_server_cls: MagicMock, tmp_config: DashboardConfig
    ) -> None:
        mock_server = MagicMock()
        mock_server_cls.return_value = mock_server

        with patch(
            "agent_evals.observatory.web.server.ModelCatalog"
        ) as mock_catalog_cls:
            mock_catalog = MagicMock()
            mock_catalog.get_active_models.return_value = [{"id": "m1"}]
            mock_catalog_cls.return_value = mock_catalog

            handle = launch_dashboard(tmp_config, background=True)

        assert isinstance(handle, DashboardHandle)
        assert handle.thread is not None
        assert isinstance(handle.thread, threading.Thread)
        assert handle.thread.daemon is True
        handle.stop()

    @patch("agent_evals.observatory.web.server.uvicorn.Server")
    def test_foreground_calls_server_run(
        self, mock_server_cls: MagicMock, tmp_config: DashboardConfig
    ) -> None:
        mock_server = MagicMock()
        mock_server_cls.return_value = mock_server

        with patch(
            "agent_evals.observatory.web.server.ModelCatalog"
        ) as mock_catalog_cls:
            mock_catalog = MagicMock()
            mock_catalog.get_active_models.return_value = [{"id": "m1"}]
            mock_catalog_cls.return_value = mock_catalog

            handle = launch_dashboard(tmp_config, background=False)

        mock_server.run.assert_called_once()
        assert isinstance(handle, DashboardHandle)
