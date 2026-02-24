"""FastAPI web dashboard for observatory live monitoring.

Serves HTML dashboard, REST API for run/trial data, SSE streaming,
model browser, and historical analytics endpoints.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse, Response

from agent_evals.observatory.model_catalog import ModelCatalog
from agent_evals.observatory.model_groups import ModelGroupManager
from agent_evals.observatory.model_sync import ModelSync
from agent_evals.observatory.run_manager import RunManager
from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker
from agent_evals.observatory.web.routes import create_router

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

_DEFAULT_OBS_DB = Path.home() / ".observatory" / "observatory.db"
_DEFAULT_MODELS_DB = Path.home() / ".observatory" / "models.db"


@dataclass
class DashboardConfig:
    """Configuration for the observatory dashboard server."""

    observatory_db: Path = field(default_factory=lambda: _DEFAULT_OBS_DB)
    models_db: Path = field(default_factory=lambda: _DEFAULT_MODELS_DB)
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "info"
    auto_sync: bool = True
    sync_interval_hours: float = 6.0


@dataclass
class DashboardHandle:
    """Handle for controlling a running dashboard server."""

    thread: threading.Thread | None
    shutdown_event: threading.Event
    _server: Any = None

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the server to shut down and wait for the thread to finish."""
        self.shutdown_event.set()
        if self._server is not None:
            self._server.should_exit = True
        if self.thread is not None:
            self.thread.join(timeout=timeout)


def launch_dashboard(
    config: DashboardConfig,
    *,
    store: ObservatoryStore | None = None,
    tracker: EventTracker | None = None,
    background: bool = False,
) -> DashboardHandle:
    """Launch the observatory dashboard server.

    Args:
        config: Dashboard configuration.
        store: Existing ObservatoryStore (standalone creates one if None).
        tracker: Existing EventTracker (standalone creates one if None).
        background: If True, run in a daemon thread and return immediately.

    Returns:
        DashboardHandle for controlling the server lifecycle.
    """
    # Ensure db directories exist
    config.observatory_db.parent.mkdir(parents=True, exist_ok=True)
    config.models_db.parent.mkdir(parents=True, exist_ok=True)

    # Standalone mode: create store and tracker from config paths
    if store is None:
        store = ObservatoryStore(db_path=config.observatory_db)
    if tracker is None:
        tracker = EventTracker(store=store)

    # Model catalog, group manager, and sync
    catalog = ModelCatalog(db_path=config.models_db)
    group_manager = ModelGroupManager(catalog=catalog)
    model_sync = ModelSync(
        catalog=catalog, interval_hours=config.sync_interval_hours
    )

    # Auto-sync if catalog is empty
    if config.auto_sync and not catalog.get_active_models():
        logger.info("Model catalog empty — running initial sync")
        model_sync.run_sync()

    # Create run manager for dashboard-initiated runs
    run_manager = RunManager(store=store, tracker=tracker)

    app = create_app(
        store=store,
        tracker=tracker,
        catalog=catalog,
        group_manager=group_manager,
        model_sync=model_sync,
        run_manager=run_manager,
    )

    uvicorn_config = uvicorn.Config(
        app,
        host=config.host,
        port=config.port,
        log_level=config.log_level,
    )
    server = uvicorn.Server(uvicorn_config)

    shutdown_event = threading.Event()

    if background:
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        return DashboardHandle(
            thread=thread, shutdown_event=shutdown_event, _server=server
        )

    # Foreground: block on server.run()
    server.run()
    return DashboardHandle(
        thread=None, shutdown_event=shutdown_event, _server=server
    )


def create_app(
    store: ObservatoryStore,
    tracker: EventTracker,
    catalog: ModelCatalog | None = None,
    group_manager: ModelGroupManager | None = None,
    model_sync: ModelSync | None = None,
    run_manager: RunManager | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        store: ObservatoryStore for data access.
        tracker: EventTracker for live stats and SSE.
        catalog: Optional ModelCatalog for model browsing.
        group_manager: Optional ModelGroupManager for group CRUD.
        model_sync: Optional ModelSync for triggering syncs.
        run_manager: Optional RunManager for dashboard-started runs.
    """
    app = FastAPI(title="Observatory Dashboard")
    app.state.store = store
    app.state.tracker = tracker

    router = create_router(
        store=store,
        tracker=tracker,
        catalog=catalog,
        group_manager=group_manager,
        model_sync=model_sync,
        run_manager=run_manager,
    )
    app.include_router(router)

    if STATIC_DIR.exists():
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.exists():
            app.mount(
                "/assets",
                StaticFiles(directory=assets_dir),
                name="assets",
            )

        @app.get("/{path:path}", response_model=None)
        async def spa_fallback(path: str) -> Response:
            """Return index.html for client-side routing."""
            index = STATIC_DIR / "index.html"
            if index.exists():
                return FileResponse(index)
            return JSONResponse(
                {"error": "Frontend not built. Run: npm run build"},
                status_code=404,
            )

    return app
