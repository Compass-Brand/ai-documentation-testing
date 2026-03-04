"""Diagnostic tracker for long-running evaluation runs.

Thread-safe stats aggregator with periodic heartbeat logging and stall
detection.  Designed to give visibility into runs with thousands of trials
that would otherwise appear silent.
"""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger(__name__)


class DiagnosticTracker:
    """Aggregates per-trial stats and emits periodic heartbeat logs.

    Parameters
    ----------
    total_trials:
        Expected number of trials in the run (for progress %).
    heartbeat_interval:
        Seconds between heartbeat log messages.
    stall_threshold:
        Seconds without a completed trial before logging a stall warning.
    """

    def __init__(
        self,
        total_trials: int,
        heartbeat_interval: float = 60.0,
        stall_threshold: float = 300.0,
        completed_offset: int = 0,
    ) -> None:
        self._total = total_trials
        self._heartbeat_interval = heartbeat_interval
        self._stall_threshold = stall_threshold

        # Counters (protected by _lock)
        self._lock = threading.Lock()
        self._completed_offset = completed_offset
        self._completed = completed_offset
        self._total_tokens = 0
        self._total_cost = 0.0
        self._total_retries = 0
        self._total_rate_limits = 0
        self._total_errors = 0
        self._total_judge_failures = 0
        self._total_api_ms = 0.0
        self._total_trial_ms = 0.0
        self._last_trial_time: float = time.monotonic()
        self._start_time: float = time.monotonic()

        # Heartbeat thread
        self._stop_event = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None

    def record_trial(
        self,
        tokens: int,
        cost: float | None,
        retries: int,
        api_ms: float,
        trial_ms: float,
        error: bool,
        rate_limited: bool,
    ) -> None:
        """Record stats from a completed trial (thread-safe)."""
        with self._lock:
            self._completed += 1
            self._total_tokens += tokens
            self._total_cost += cost if cost is not None else 0.0
            self._total_retries += retries
            if rate_limited:
                self._total_rate_limits += 1
            if error:
                self._total_errors += 1
            self._total_api_ms += api_ms
            self._total_trial_ms += trial_ms
            self._last_trial_time = time.monotonic()

    def record_judge_failure(self) -> None:
        """Record a judge call failure (thread-safe)."""
        with self._lock:
            self._total_judge_failures += 1

    def snapshot(self) -> dict[str, float | int]:
        """Return a point-in-time copy of all stats."""
        with self._lock:
            completed = self._completed
            total_api_ms = self._total_api_ms
            total_trial_ms = self._total_trial_ms
            return {
                "completed": completed,
                "total_trials": self._total,
                "total_tokens": self._total_tokens,
                "total_cost": self._total_cost,
                "total_retries": self._total_retries,
                "total_rate_limits": self._total_rate_limits,
                "total_errors": self._total_errors,
                "total_judge_failures": self._total_judge_failures,
                "total_api_ms": total_api_ms,
                "total_trial_ms": total_trial_ms,
                "avg_api_ms": (
                    total_api_ms / (completed - self._completed_offset)
                    if completed > self._completed_offset
                    else 0.0
                ),
                "avg_trial_ms": (
                    total_trial_ms / (completed - self._completed_offset)
                    if completed > self._completed_offset
                    else 0.0
                ),
            }

    def start(self) -> None:
        """Start the heartbeat background thread."""
        self._start_time = time.monotonic()
        with self._lock:
            self._last_trial_time = time.monotonic()
        self._stop_event.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="diagnostics-heartbeat",
        )
        self._heartbeat_thread.start()

    def stop(self) -> None:
        """Stop the heartbeat thread and log a final summary."""
        self._stop_event.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=5.0)
            self._heartbeat_thread = None
        self._log_summary()

    def _heartbeat_loop(self) -> None:
        """Periodically log stats and check for stalls."""
        while not self._stop_event.wait(self._heartbeat_interval):
            snap = self.snapshot()
            elapsed = time.monotonic() - self._start_time
            new_trials = snap["completed"] - self._completed_offset
            rate = new_trials / (elapsed / 60.0) if elapsed > 0 else 0.0
            pct = 100.0 * snap["completed"] / self._total if self._total else 0.0

            with self._lock:
                since_last = time.monotonic() - self._last_trial_time

            logger.info(
                "HEARTBEAT %d/%d (%.1f%%) | %.1f trials/min | $%.4f spent | "
                "%d tokens | %d retries | %d rate-limits | avg_api=%.0fms "
                "avg_trial=%.0fms | %d errors | %d judge-failures | "
                "last_trial %.0fs ago",
                snap["completed"],
                self._total,
                pct,
                rate,
                snap["total_cost"],
                snap["total_tokens"],
                snap["total_retries"],
                snap["total_rate_limits"],
                snap["avg_api_ms"],
                snap["avg_trial_ms"],
                snap["total_errors"],
                snap["total_judge_failures"],
                since_last,
            )

            if since_last >= self._stall_threshold:
                logger.warning(
                    "POSSIBLE STALL: no trial completed in %.0fs "
                    "(threshold: %.0fs). Run may be stuck.",
                    since_last,
                    self._stall_threshold,
                )

    def _log_summary(self) -> None:
        """Log a final summary line."""
        snap = self.snapshot()
        elapsed = time.monotonic() - self._start_time
        new_trials = snap["completed"] - self._completed_offset
        rate = new_trials / (elapsed / 60.0) if elapsed > 0 else 0.0

        logger.info(
            "RUN COMPLETE: %d/%d trials | %.1f trials/min | $%.4f spent | "
            "%d tokens | %d retries | %d rate-limits | %d errors | "
            "%d judge-failures | %.1fs elapsed",
            snap["completed"],
            self._total,
            rate,
            snap["total_cost"],
            snap["total_tokens"],
            snap["total_retries"],
            snap["total_rate_limits"],
            snap["total_errors"],
            snap["total_judge_failures"],
            elapsed,
        )
