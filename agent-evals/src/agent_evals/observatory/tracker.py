"""Thread-safe event tracker with listeners, anomaly detection, and budgets.

Records trial events, notifies listeners, detects cost anomalies (>3x
running average), enforces per-model budget caps, and monitors burn rate.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
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
        burn_rate_threshold: Optional burn rate threshold in dollars per
            minute.  When the cost accumulated over a 60-second sliding
            window exceeds this rate, a ``burn_rate_alert`` event is
            emitted.  ``None`` (default) disables burn rate monitoring.
    """

    ANOMALY_MULTIPLIER: float = 3.0
    _BURN_RATE_WINDOW_SECONDS: float = 60.0

    def __init__(
        self,
        store: ObservatoryStore,
        model_budgets: dict[str, float] | None = None,
        burn_rate_threshold: float | None = None,
    ) -> None:
        self._store = store
        self._model_budgets: dict[str, float] = dict(model_budgets or {})
        self._burn_rate_threshold = burn_rate_threshold
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
            try:
                self._listeners.remove(callback)
            except ValueError:
                pass

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
        oa_row_id: int | None = None,
        phase: str | None = None,
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
            oa_row_id=oa_row_id,
            phase=phase,
        )

        trial_cost = cost or 0.0
        now = time.monotonic()

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

            # Update burn-rate sliding window.
            model_stats.cost_timestamps.append((now, trial_cost))
            cutoff = now - self._BURN_RATE_WINDOW_SECONDS
            while (
                model_stats.cost_timestamps
                and model_stats.cost_timestamps[0][0] < cutoff
            ):
                model_stats.cost_timestamps.popleft()

            # Compute burn rate (dollars per minute) over the window.
            burn_rate: float | None = None
            if (
                self._burn_rate_threshold is not None
                and len(model_stats.cost_timestamps) > 1
            ):
                window_cost = sum(
                    c for _, c in model_stats.cost_timestamps
                )
                # dollars per minute
                burn_rate = window_cost / (
                    self._BURN_RATE_WINDOW_SECONDS / 60.0
                )

            # Capture values needed outside the lock.
            count_after = model_stats.count
            total_cost_after = model_stats.total_cost

            # Snapshot listeners for notification outside lock.
            listeners = list(self._listeners)

        # Emit trial_completed event.
        trial_event = TrackerEvent(
            event_type="trial_completed",
            data={
                "run_id": run_id,
                "model": model,
                "cost": trial_cost,
                "score": score,
                "task_id": task_id,
                "task_type": task_type,
                "variant_name": variant_name,
                "latency_seconds": latency_seconds,
                "total_tokens": total_tokens,
            },
        )
        self._notify(listeners, trial_event)

        # Anomaly detection: cost > 3x running average (need >1 samples).
        if (
            avg_before > 0
            and count_after > 1
            and trial_cost > self.ANOMALY_MULTIPLIER * avg_before
        ):
            anomaly_event = TrackerEvent(
                event_type="anomaly_alert",
                data={
                    "run_id": run_id,
                    "model": model,
                    "cost": trial_cost,
                    "average_cost": avg_before,
                    "multiplier": trial_cost / avg_before,
                },
            )
            self._notify(listeners, anomaly_event)

        # Per-model budget check.
        budget = self._model_budgets.get(model)
        if budget is not None and total_cost_after > budget:
            budget_event = TrackerEvent(
                event_type="model_budget_exceeded",
                data={
                    "run_id": run_id,
                    "model": model,
                    "budget": budget,
                    "spent": total_cost_after,
                },
            )
            self._notify(listeners, budget_event)

        # Burn rate alert.
        if (
            burn_rate is not None
            and self._burn_rate_threshold is not None
            and burn_rate > self._burn_rate_threshold
        ):
            burn_event = TrackerEvent(
                event_type="burn_rate_alert",
                data={
                    "run_id": run_id,
                    "model": model,
                    "burn_rate_per_minute": burn_rate,
                    "threshold_per_minute": self._burn_rate_threshold,
                },
            )
            self._notify(listeners, burn_event)

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
                logging.getLogger(__name__).debug("Listener error", exc_info=True)


class _ModelStats:
    """Internal per-model aggregation.

    The ``costs`` deque keeps at most the last 100 trial costs for
    anomaly-detection's rolling-window comparison.  The overall average
    is derived from ``total_cost / count`` (not from the deque).
    """

    _COSTS_MAXLEN: int = 100

    __slots__ = ("count", "total_cost", "costs", "cost_timestamps")

    def __init__(self) -> None:
        self.count: int = 0
        self.total_cost: float = 0.0
        self.costs: deque[float] = deque(maxlen=self._COSTS_MAXLEN)
        self.cost_timestamps: deque[tuple[float, float]] = deque()

    @property
    def average_cost(self) -> float:
        if self.count == 0:
            return 0.0
        return self.total_cost / self.count
