"""Background model sync with OpenRouter API.

Fetches model metadata from OpenRouter, computes diffs against the
local catalog, and applies changes. Supports one-time and periodic
sync with configurable intervals.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from agent_evals.observatory.model_catalog import ModelCatalog

logger = logging.getLogger(__name__)

_OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


@dataclass
class SyncDiff:
    """Result of comparing local and remote model sets."""

    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    price_changes: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SyncResult:
    """Result of a sync execution."""

    added_count: int = 0
    removed_count: int = 0
    updated_count: int = 0
    total_count: int = 0
    error: str | None = None


class ModelSync:
    """Syncs model catalog with OpenRouter API.

    Args:
        catalog: The ModelCatalog to update.
        interval_hours: Hours between periodic syncs (default 6).
    """

    def __init__(
        self,
        catalog: ModelCatalog,
        interval_hours: float = 6.0,
    ) -> None:
        self._catalog = catalog
        self._interval_hours = interval_hours
        self._timer: threading.Timer | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        """Whether periodic sync is active."""
        return self._running

    @staticmethod
    def compute_diff(
        local: dict[str, dict[str, Any]],
        remote: dict[str, dict[str, Any]],
    ) -> SyncDiff:
        """Compute diff between local and remote model sets."""
        local_ids = set(local.keys())
        remote_ids = set(remote.keys())

        added = sorted(remote_ids - local_ids)
        removed = sorted(local_ids - remote_ids)

        price_changes: list[dict[str, Any]] = []
        for model_id in local_ids & remote_ids:
            old_price = local[model_id].get("prompt_price")
            new_price = remote[model_id].get("prompt_price")
            if old_price is not None and new_price is not None and old_price != new_price:
                price_changes.append({
                    "id": model_id,
                    "old": old_price,
                    "new": new_price,
                })

        return SyncDiff(added=added, removed=removed, price_changes=price_changes)

    def fetch_remote_models(self) -> list[dict[str, Any]]:
        """Fetch model list from OpenRouter API.

        Returns a list of model metadata dicts. Override in tests.
        """
        import httpx  # noqa: PLC0415

        response = httpx.get(_OPENROUTER_MODELS_URL, timeout=30)
        response.raise_for_status()
        return response.json().get("data", [])

    def run_sync(self) -> SyncResult:
        """Execute a one-time sync against the catalog."""
        try:
            remote_models = self.fetch_remote_models()
        except Exception as exc:
            logger.error("Model sync failed: %s", exc)
            return SyncResult(error=str(exc))

        # Build remote lookup by id.
        remote_by_id: dict[str, dict[str, Any]] = {}
        for m in remote_models:
            model_id = m.get("id", "")
            if model_id:
                remote_by_id[model_id] = self._normalize_model(m)

        # Build local lookup.
        local_models = self._catalog.get_active_models()
        local_by_id = {m["id"]: m for m in local_models}

        diff = self.compute_diff(local_by_id, remote_by_id)

        # Apply additions and updates.
        added_count = 0
        updated_count = 0
        for model_id, data in remote_by_id.items():
            self._catalog.upsert_model(
                id=model_id,
                name=data.get("name", model_id),
                context_length=data.get("context_length", 0),
                prompt_price=data.get("prompt_price", 0.0),
                completion_price=data.get("completion_price", 0.0),
                modality=data.get("modality", "text"),
                tokenizer=data.get("tokenizer", ""),
                supported_params=data.get("supported_params"),
            )
            if model_id in diff.added:
                added_count += 1
            elif model_id in local_by_id:
                updated_count += 1

        # Mark removed models.
        for model_id in diff.removed:
            self._catalog.mark_removed(model_id)

        # Log sync.
        self._catalog.log_sync(
            added=added_count,
            removed=len(diff.removed),
            total=len(remote_by_id),
        )

        return SyncResult(
            added_count=added_count,
            removed_count=len(diff.removed),
            updated_count=updated_count,
            total_count=len(remote_by_id),
        )

    def start_periodic(self) -> None:
        """Start periodic sync in a background thread."""
        if self._running:
            return
        self._running = True
        self._schedule_next()

    def stop_periodic(self) -> None:
        """Stop periodic sync."""
        self._running = False
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _schedule_next(self) -> None:
        """Schedule the next sync run."""
        if not self._running:
            return
        interval_seconds = self._interval_hours * 3600
        self._timer = threading.Timer(interval_seconds, self._periodic_run)
        self._timer.daemon = True
        self._timer.start()

    def _periodic_run(self) -> None:
        """Execute sync and schedule the next run."""
        if not self._running:
            return
        try:
            self.run_sync()
        except Exception:
            logger.exception("Periodic model sync failed")
        self._schedule_next()

    @staticmethod
    def _normalize_model(raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize OpenRouter model response to our schema."""
        pricing = raw.get("pricing", {})
        prompt_price = float(pricing.get("prompt", 0) or 0)
        completion_price = float(pricing.get("completion", 0) or 0)

        return {
            "id": raw.get("id", ""),
            "name": raw.get("name", ""),
            "context_length": raw.get("context_length", 0),
            "prompt_price": prompt_price,
            "completion_price": completion_price,
            "modality": raw.get("modality", "text"),
            "tokenizer": raw.get("tokenizer", ""),
            "supported_params": raw.get("supported_parameters"),
        }
