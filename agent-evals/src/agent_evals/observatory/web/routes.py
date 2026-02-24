"""API routes and SSE streaming for the observatory web dashboard."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agent_evals.observatory.model_catalog import ModelCatalog
from agent_evals.observatory.model_groups import ModelGroupManager
from agent_evals.observatory.model_sync import ModelSync
from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker


_DASHBOARD_HTML = """\
<!DOCTYPE html>
<html>
<head><title>Observatory Dashboard</title></head>
<body>
<nav>
  <a href="/">Dashboard</a>
  <a href="#models">Models</a>
</nav>
<h1>Observatory Dashboard</h1>
<div id="progress"></div>
<div id="models"></div>
<div id="budget"></div>

<!-- Model Browser (Page 6) -->
<section id="model-browser">
  <div id="filter-panel">
    <input type="text" id="model-search" placeholder="Search models..." />
    <div id="price-filter"></div>
    <div id="context-filter"></div>
    <div id="modality-filter"></div>
    <div id="capability-filter"></div>
    <div id="tokenizer-filter"></div>
  </div>
  <div id="view-toggle">
    <button data-view="table">Table</button>
    <button data-view="card">Card</button>
  </div>
  <div id="model-actions">
    <button id="select-all">Select All</button>
    <button id="run-selected">Run Selected</button>
    <button id="save-group">Save as Group</button>
  </div>
  <div id="model-table"></div>
  <div id="card-view"></div>
  <div id="detail-panel"></div>
</section>
</body>
</html>
"""


class CreateGroupRequest(BaseModel):
    """Request body for creating a model group."""

    name: str
    models: list[str] = []


def _get_pipeline_id(store: ObservatoryStore, run_id: str) -> str | None:
    """Look up the pipeline_id for a given run from the database."""
    with store._connect() as conn:
        row = conn.execute(
            "SELECT pipeline_id FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
    if row is None:
        return None
    return row["pipeline_id"]


def create_router(
    store: ObservatoryStore,
    tracker: EventTracker,
    catalog: ModelCatalog | None = None,
    group_manager: ModelGroupManager | None = None,
    model_sync: ModelSync | None = None,
) -> APIRouter:
    """Create API router with all observatory and model browser endpoints."""
    router = APIRouter()

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------

    @router.get("/", response_class=HTMLResponse)
    async def dashboard() -> str:
        return _DASHBOARD_HTML

    # ------------------------------------------------------------------
    # Runs API
    # ------------------------------------------------------------------

    @router.get("/api/runs")
    async def list_runs() -> list[dict[str, Any]]:
        runs = store.list_runs()
        return [asdict(r) for r in runs]

    def _enrich_run(run_id: str) -> dict[str, Any]:
        """Build enriched run summary with variant/model aggregations."""
        summary = store.get_run_summary(run_id)
        trials = store.get_trials(run_id)

        by_variant: dict[str, dict[str, Any]] = {}
        for t in trials:
            entry = by_variant.setdefault(
                t.variant_name, {"total_score": 0.0, "trial_count": 0}
            )
            entry["total_score"] += t.score
            entry["trial_count"] += 1
        by_variant_out = {
            k: {
                "mean_score": v["total_score"] / v["trial_count"],
                "trial_count": v["trial_count"],
            }
            for k, v in by_variant.items()
        }

        by_model: dict[str, dict[str, Any]] = {}
        for t in trials:
            if not t.model:
                continue
            entry = by_model.setdefault(
                t.model, {"total_score": 0.0, "trial_count": 0, "cost": 0.0}
            )
            entry["total_score"] += t.score
            entry["trial_count"] += 1
            entry["cost"] += t.cost or 0.0
        by_model_out = {
            k: {
                "mean_score": v["total_score"] / v["trial_count"],
                "trial_count": v["trial_count"],
                "cost": v["cost"],
            }
            for k, v in by_model.items()
        } or None

        completed_trials = sum(1 for t in trials if t.error is None)
        total_tokens = sum(t.total_tokens for t in trials)
        mean_score = (
            (sum(t.score for t in trials) / len(trials)) if trials else 0.0
        )

        return {
            "run": {
                "run_id": summary.run_id,
                "run_type": summary.run_type,
                "status": summary.status,
                "config": {},
                "created_at": summary.created_at,
                "finished_at": summary.finished_at,
            },
            "total_trials": summary.total_trials,
            "completed_trials": completed_trials,
            "total_cost": summary.total_cost,
            "total_tokens": total_tokens,
            "mean_score": mean_score,
            "by_variant": by_variant_out,
            "by_model": by_model_out,
        }

    @router.get("/api/runs/{run_id}")
    async def get_run(run_id: str) -> dict[str, Any]:
        try:
            return _enrich_run(run_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/runs/{run_id}/finish")
    async def finish_run(run_id: str) -> dict[str, Any]:
        try:
            store.get_run_summary(run_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        store.finish_run(run_id)
        return {"run_id": run_id, "status": "completed"}

    @router.get("/api/runs/{run_id}/trials")
    async def get_trials(run_id: str) -> list[dict[str, Any]]:
        trials = store.get_trials(run_id)
        return [asdict(t) for t in trials]

    @router.get("/api/runs/{run_id}/stream")
    async def stream_events(run_id: str, request: Request) -> EventSourceResponse:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        def _on_event(event: Any) -> None:
            try:
                if event.data.get("run_id") != run_id:
                    return
                queue.put_nowait({
                    "event_type": event.event_type,
                    "data": event.data,
                })
            except asyncio.QueueFull:
                pass

        tracker.add_listener(_on_event)

        async def _generator():
            try:
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
                    except TimeoutError:
                        yield {"comment": "keepalive"}
            finally:
                tracker.remove_listener(_on_event)

        return EventSourceResponse(_generator())

    # ------------------------------------------------------------------
    # History API
    # ------------------------------------------------------------------

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
                results.append(_enrich_run(run_id))
            except ValueError:
                results.append({"run_id": run_id, "error": "not found"})
        return results

    # ------------------------------------------------------------------
    # Model Browser API
    # ------------------------------------------------------------------

    @router.get("/api/models")
    async def list_models(
        free: bool | None = None,
        max_price: float | None = None,
        min_context: int | None = None,
        modality: str | None = None,
        capabilities: str | None = None,
        tokenizer: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        if catalog is None:
            return {"models": [], "total": 0}
        caps_list = (
            [c.strip() for c in capabilities.split(",")]
            if capabilities
            else None
        )
        results = catalog.filter_models(
            free=free,
            max_price=max_price,
            min_context=min_context,
            modality=modality,
            capabilities=caps_list,
            tokenizer=tokenizer,
        )
        if search:
            term = search.lower()
            results = [
                m for m in results
                if term in m.get("name", "").lower()
                or term in m.get("id", "").lower()
            ]
        return {"models": results, "total": len(results)}

    @router.get("/api/models/groups")
    async def get_groups() -> list[dict[str, Any]]:
        if group_manager is None:
            return []
        groups = group_manager.list_groups()
        return [asdict(g) for g in groups]

    @router.post("/api/models/groups", status_code=201)
    async def create_group(body: CreateGroupRequest) -> dict[str, Any]:
        if group_manager is None:
            raise HTTPException(status_code=503, detail="Groups not configured")
        group = group_manager.create_group(body.name)
        if body.models:
            group_manager.add_to_group(group.id, body.models)
        return asdict(group)

    @router.get("/api/models/sync")
    async def sync_status() -> dict[str, Any]:
        if catalog is None:
            return {"total_models": 0, "last_sync": None, "models_added": 0, "models_removed": 0, "models_updated": 0}
        history = catalog.get_sync_history()
        latest = history[0] if history else {}
        active = catalog.get_active_models()
        return {
            "total_models": len(active),
            "last_sync": latest.get("timestamp"),
            "models_added": latest.get("models_added", 0),
            "models_removed": latest.get("models_removed", 0),
            "models_updated": 0,
        }

    @router.post("/api/models/sync")
    async def trigger_sync() -> dict[str, Any]:
        if model_sync is None:
            raise HTTPException(status_code=503, detail="Sync not configured")
        result = model_sync.run_sync()
        return asdict(result)

    @router.get("/api/models/{model_id:path}")
    async def get_model(model_id: str) -> dict[str, Any]:
        if catalog is None:
            raise HTTPException(status_code=503, detail="Catalog not configured")
        model = catalog.get_model(model_id)
        if model is None:
            raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
        return model

    # ------------------------------------------------------------------
    # Pipeline API
    # ------------------------------------------------------------------

    @router.get("/api/pipelines")
    async def list_pipelines() -> list[dict[str, Any]]:
        runs = store.list_runs()
        pipelines: dict[str, list[dict[str, Any]]] = {}
        for r in runs:
            rd = asdict(r)
            pid = _get_pipeline_id(store, r.run_id)
            if pid is None:
                continue
            pipelines.setdefault(pid, []).append(rd)
        return [
            {
                "pipeline_id": pid,
                "run_count": len(pipe_runs),
                "latest_status": pipe_runs[-1]["status"],
            }
            for pid, pipe_runs in pipelines.items()
        ]

    @router.get("/api/pipelines/{pipeline_id}")
    async def get_pipeline_detail(pipeline_id: str) -> dict[str, Any]:
        runs = store.get_pipeline_runs(pipeline_id)
        if not runs:
            raise HTTPException(
                status_code=404,
                detail=f"Pipeline '{pipeline_id}' not found",
            )
        return {
            "pipeline_id": pipeline_id,
            "runs": [asdict(r) for r in runs],
        }

    @router.get("/api/runs/{run_id}/analysis")
    async def get_run_analysis(run_id: str) -> dict[str, Any]:
        results = store.get_phase_results(run_id)
        if results is None:
            raise HTTPException(
                status_code=404,
                detail=f"No analysis results for run '{run_id}'",
            )
        return results

    @router.post("/api/pipelines/{pipeline_id}/approve")
    async def approve_pipeline(pipeline_id: str) -> dict[str, Any]:
        return {"pipeline_id": pipeline_id, "approved": True}

    return router
