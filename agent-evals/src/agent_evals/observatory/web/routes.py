"""API routes and SSE streaming for the observatory web dashboard."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker


_DASHBOARD_HTML = """\
<!DOCTYPE html>
<html>
<head><title>Observatory Dashboard</title></head>
<body>
<h1>Observatory Dashboard</h1>
<div id="progress"></div>
<div id="models"></div>
<div id="budget"></div>
</body>
</html>
"""


def create_router(
    store: ObservatoryStore,
    tracker: EventTracker,
) -> APIRouter:
    """Create API router with all observatory endpoints."""
    router = APIRouter()

    @router.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        return _DASHBOARD_HTML

    @router.get("/api/runs")
    async def list_runs() -> list[dict[str, Any]]:
        runs = store.list_runs()
        return [asdict(r) for r in runs]

    @router.get("/api/runs/{run_id}")
    async def get_run(run_id: str) -> dict[str, Any]:
        try:
            summary = store.get_run_summary(run_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return asdict(summary)

    @router.get("/api/runs/{run_id}/trials")
    async def get_trials(run_id: str) -> list[dict[str, Any]]:
        trials = store.get_trials(run_id)
        return [asdict(t) for t in trials]

    @router.get("/api/runs/{run_id}/stream")
    async def stream_events(run_id: str, request: Request) -> EventSourceResponse:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        def _on_event(event: Any) -> None:
            try:
                queue.put_nowait({
                    "event_type": event.event_type,
                    "data": event.data,
                })
            except asyncio.QueueFull:
                pass

        tracker.add_listener(_on_event)

        async def _generator():
            try:
                # Send initial connected event.
                yield {"event": "connected", "data": json.dumps({"run_id": run_id})}
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=1.0)
                        yield {
                            "event": event["event_type"],
                            "data": json.dumps(event["data"]),
                        }
                    except asyncio.TimeoutError:
                        # Send keepalive comment.
                        yield {"comment": "keepalive"}
            finally:
                tracker.remove_listener(_on_event)

        return EventSourceResponse(_generator())

    @router.get("/api/history/cost-trend")
    async def cost_trend() -> list[dict[str, Any]]:
        runs = store.list_runs()
        return [
            {
                "run_id": r.run_id,
                "total_cost": r.total_cost,
                "created_at": r.created_at,
            }
            for r in runs
            if r.status == "completed"
        ]

    @router.get("/api/compare")
    async def compare_runs(ids: str = Query(...)) -> list[dict[str, Any]]:
        run_ids = [rid.strip() for rid in ids.split(",") if rid.strip()]
        results = []
        for run_id in run_ids:
            try:
                summary = store.get_run_summary(run_id)
                results.append(asdict(summary))
            except ValueError:
                results.append({"run_id": run_id, "error": "not found"})
        return results

    return router
