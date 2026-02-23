"""FastAPI web dashboard for observatory live monitoring.

Serves HTML dashboard, REST API for run/trial data, SSE streaming,
model browser, and historical analytics endpoints.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse, Response

from agent_evals.observatory.model_catalog import ModelCatalog
from agent_evals.observatory.model_groups import ModelGroupManager
from agent_evals.observatory.model_sync import ModelSync
from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker
from agent_evals.observatory.web.routes import create_router

STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    store: ObservatoryStore,
    tracker: EventTracker,
    catalog: ModelCatalog | None = None,
    group_manager: ModelGroupManager | None = None,
    model_sync: ModelSync | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        store: ObservatoryStore for data access.
        tracker: EventTracker for live stats and SSE.
        catalog: Optional ModelCatalog for model browsing.
        group_manager: Optional ModelGroupManager for group CRUD.
        model_sync: Optional ModelSync for triggering syncs.
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
