"""FastAPI web dashboard for observatory live monitoring.

Serves HTML dashboard, REST API for run/trial data, SSE streaming,
and historical analytics endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse

from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker
from agent_evals.observatory.web.routes import create_router


def create_app(
    store: ObservatoryStore,
    tracker: EventTracker,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        store: ObservatoryStore for data access.
        tracker: EventTracker for live stats and SSE.
    """
    app = FastAPI(title="Observatory Dashboard")
    app.state.store = store
    app.state.tracker = tracker

    router = create_router(store=store, tracker=tracker)
    app.include_router(router)

    return app
