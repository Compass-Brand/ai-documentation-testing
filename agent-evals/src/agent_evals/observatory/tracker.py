"""Thread-safe event tracker with listeners, anomaly detection, and budgets.

Records trial events, notifies listeners, detects cost anomalies (>3x
running average), and enforces per-model budget caps.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from agent_evals.observatory.store import ObservatoryStore


@dataclass
class TrackerEvent:
    """An event emitted by the tracker.

    Attributes:
        event_type: One of "trial_completed", "anomaly_alert",
            "model_budget_exceeded", "burn_rate_alert".
        data: Event-specific payload.
    """

    event_type: str
    data: dict[str, Any] = field(default_factory=dict)


# Type alias for listener callbacks.
ListenerCallback = Callable[[TrackerEvent], None]


class EventTracker:
    """Thread-safe event tracker with real-time listener notification.

    Args:
        store: The ObservatoryStore to persist trial records.
        model_budgets: Optional per-model budget caps (model -> dollars).
    """

    ANOMALY_MULTIPLIER: float = 3.0

    def __init__(
        self,
        store: ObservatoryStore,
        model_budgets: dict[str, float] | None = None,
    ) -> None:
        self._store = store
        self._model_budgets: dict[str, float] = dict(model_budgets or {})
        self._listeners: list[ListenerCallback] = []
        self._lock = threading.Lock()

        # In-memory aggregates for fast stats access.
        self._total_trials: int = 0
        self._total_cost: float = 0.0
        self._per_model: dict[str, _ModelStats] = {}

    def add_listener(self, callback: ListenerCallback) -> None:
        """Register a listener to be notified on events."""
        with self._lock:
            self._listeners.append(callback)

    def remove_listener(self, callback: ListenerCallback) -> None:
        """Unregister a previously registered listener."""
        with self._lock:
            self._listeners.remove(callback)

    def record_trial(
        self,
        *,
        run_id: str,
        task_id: str,
        task_type: str,
        variant_name: str,
        repetition: int,
        score: float,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost: float | None,
        latency_seconds: float,
        model: str,
        source: str = "gold_standard",
        error: str | None = None,
    ) -> None:
        """Record a trial, persist it, update stats, and notify listeners."""
        # Persist to store.
        self._store.record_trial(
            run_id=run_id,
            task_id=task_id,
            task_type=task_type,
            variant_name=variant_name,
            repetition=repetition,
            score=score,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost=cost,
            latency_seconds=latency_seconds,
            model=model,
            source=source,
            error=error,
        )

        trial_cost = cost or 0.0

        with self._lock:
            # Update aggregates.
            self._total_trials += 1
            self._total_cost += trial_cost

            if model not in self._per_model:
                self._per_model[model] = _ModelStats()
            model_stats = self._per_model[model]

            avg_before = model_stats.average_cost
            model_stats.count += 1
            model_stats.total_cost += trial_cost
            model_stats.costs.append(trial_cost)

            # Snapshot listeners for notification outside lock.
            listeners = list(self._listeners)

        # Emit trial_completed event.
        trial_event = TrackerEvent(
            event_type="trial_completed",
            data={
                "model": model,
                "cost": trial_cost,
                "score": score,
                "task_id": task_id,
            },
        )
        self._notify(listeners, trial_event)

        # Anomaly detection: cost > 3x running average (need >1 samples).
        if (
            avg_before > 0
            and model_stats.count > 1
            and trial_cost > self.ANOMALY_MULTIPLIER * avg_before
        ):
            anomaly_event = TrackerEvent(
                event_type="anomaly_alert",
                data={
                    "model": model,
                    "cost": trial_cost,
                    "average_cost": avg_before,
                    "multiplier": trial_cost / avg_before,
                },
            )
            self._notify(listeners, anomaly_event)

        # Per-model budget check.
        budget = self._model_budgets.get(model)
        if budget is not None and model_stats.total_cost > budget:
            budget_event = TrackerEvent(
                event_type="model_budget_exceeded",
                data={
                    "model": model,
                    "budget": budget,
                    "spent": model_stats.total_cost,
                },
            )
            self._notify(listeners, budget_event)

    def is_model_over_budget(self, model: str) -> bool:
        """Check whether a model has exceeded its per-model budget."""
        budget = self._model_budgets.get(model)
        if budget is None:
            return False
        with self._lock:
            stats = self._per_model.get(model)
            if stats is None:
                return False
            return stats.total_cost > budget

    @property
    def stats(self) -> dict[str, Any]:
        """Return a snapshot of aggregate statistics."""
        with self._lock:
            per_model: dict[str, dict[str, Any]] = {}
            for name, ms in self._per_model.items():
                per_model[name] = {
                    "count": ms.count,
                    "total_cost": ms.total_cost,
                    "average_cost": ms.average_cost,
                }
            return {
                "total_trials": self._total_trials,
                "total_cost": self._total_cost,
                "per_model": per_model,
            }

    @staticmethod
    def _notify(
        listeners: list[ListenerCallback], event: TrackerEvent
    ) -> None:
        """Notify all listeners. Errors in listeners are swallowed."""
        for listener in listeners:
            try:
                listener(event)
            except Exception:  # noqa: BLE001
                pass


class _ModelStats:
    """Internal per-model aggregation."""

    __slots__ = ("count", "total_cost", "costs")

    def __init__(self) -> None:
        self.count: int = 0
        self.total_cost: float = 0.0
        self.costs: list[float] = []

    @property
    def average_cost(self) -> float:
        if self.count == 0:
            return 0.0
        return self.total_cost / self.count
