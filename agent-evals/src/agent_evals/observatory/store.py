"""SQLite-backed observatory store for run and trial telemetry.

Provides persistent storage for evaluation runs and their trial-level
results, with support for filtering, aggregation, and concurrent writes.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class TrialRecord:
    """A single trial row read back from the store."""

    trial_id: int
    run_id: str
    task_id: str
    task_type: str
    variant_name: str
    repetition: int
    score: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float | None
    latency_seconds: float
    model: str
    source: str
    error: str | None


@dataclass
class RunSummary:
    """Summary of a single run with aggregate statistics."""

    run_id: str
    run_type: str
    status: str
    created_at: str
    finished_at: str | None
    total_trials: int
    total_cost: float
    avg_latency: float


_SCHEMA = """\
CREATE TABLE IF NOT EXISTS runs (
    run_id        TEXT PRIMARY KEY,
    run_type      TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active',
    config        TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL,
    finished_at   TEXT,
    parent_run_id TEXT REFERENCES runs(run_id),
    phase         TEXT,
    pipeline_id   TEXT
);

CREATE TABLE IF NOT EXISTS trials (
    trial_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           TEXT NOT NULL REFERENCES runs(run_id),
    task_id          TEXT NOT NULL,
    task_type        TEXT NOT NULL,
    variant_name     TEXT NOT NULL,
    repetition       INTEGER NOT NULL,
    score            REAL NOT NULL,
    prompt_tokens    INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens     INTEGER NOT NULL,
    cost             REAL,
    latency_seconds  REAL NOT NULL,
    model            TEXT NOT NULL,
    source           TEXT NOT NULL DEFAULT 'gold_standard',
    error            TEXT,
    created_at       TEXT NOT NULL,
    oa_row_id        INTEGER,
    phase            TEXT
);

CREATE TABLE IF NOT EXISTS phase_results (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              TEXT NOT NULL UNIQUE REFERENCES runs(run_id),
    main_effects        TEXT NOT NULL,
    anova               TEXT NOT NULL,
    optimal             TEXT NOT NULL,
    significant_factors TEXT NOT NULL,
    quality_type        TEXT NOT NULL,
    created_at          TEXT NOT NULL
);
"""


class ObservatoryStore:
    """SQLite-backed store for evaluation telemetry.

    Args:
        db_path: Path to the SQLite database file. Created on first use.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()
        self._migrate_schema()

    def _init_db(self) -> None:
        """Create schema if it doesn't exist."""
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _migrate_schema(self) -> None:
        """Add new columns to existing tables (idempotent)."""
        migrations = [
            "ALTER TABLE runs ADD COLUMN parent_run_id TEXT",
            "ALTER TABLE runs ADD COLUMN phase TEXT",
            "ALTER TABLE runs ADD COLUMN pipeline_id TEXT",
            "ALTER TABLE trials ADD COLUMN oa_row_id INTEGER",
            "ALTER TABLE trials ADD COLUMN phase TEXT",
        ]
        with self._connect() as conn:
            for stmt in migrations:
                try:
                    conn.execute(stmt)
                except sqlite3.OperationalError as exc:
                    msg = str(exc).lower()
                    if "duplicate column" in msg or "already exists" in msg:
                        continue
                    raise

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _get_tables(self) -> list[str]:
        """Return table names in the database (for testing)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        return [r["name"] for r in rows]

    def create_run(
        self,
        run_id: str,
        run_type: str,
        config: dict,
        *,
        phase: str | None = None,
        pipeline_id: str | None = None,
        parent_run_id: str | None = None,
    ) -> None:
        """Create a new run record.

        Args:
            run_id: Unique identifier for the run.
            run_type: Type of run (e.g. "taguchi", "sweep").
            config: Configuration dict (stored as JSON).
            phase: Pipeline phase (e.g. "screening", "confirmation").
            pipeline_id: Pipeline this run belongs to.
            parent_run_id: Parent run for confirmation/refinement phases.

        Raises:
            ValueError: If run_id already exists.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT 1 FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if existing:
                raise ValueError(f"Run '{run_id}' already exists")
            conn.execute(
                "INSERT INTO runs (run_id, run_type, config, created_at, "
                "parent_run_id, phase, pipeline_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id, run_type, json.dumps(config), now,
                    parent_run_id, phase, pipeline_id,
                ),
            )

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
        """Record a single trial result.

        Args:
            run_id: The run this trial belongs to.
            task_id: Task identifier.
            task_type: Task type classification.
            variant_name: Name of the variant used.
            repetition: 1-based repetition number.
            score: Score between 0.0 and 1.0.
            prompt_tokens: Prompt token count.
            completion_tokens: Completion token count.
            total_tokens: Total token count.
            cost: Monetary cost (None if unknown).
            latency_seconds: Wall-clock latency.
            model: Model identifier.
            source: Task source (e.g. "gold_standard", "repliqa").
            error: Error message if trial failed.
            oa_row_id: Orthogonal array row index (Taguchi runs).
            phase: Pipeline phase (e.g. "screening").
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO trials "
                "(run_id, task_id, task_type, variant_name, repetition, "
                "score, prompt_tokens, completion_tokens, total_tokens, "
                "cost, latency_seconds, model, source, error, created_at, "
                "oa_row_id, phase) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id, task_id, task_type, variant_name, repetition,
                    score, prompt_tokens, completion_tokens, total_tokens,
                    cost, latency_seconds, model, source, error, now,
                    oa_row_id, phase,
                ),
            )

    def finish_run(self, run_id: str) -> None:
        """Mark a run as completed with a timestamp.

        Args:
            run_id: The run to finish.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE runs SET status = 'completed', finished_at = ? "
                "WHERE run_id = ?",
                (now, run_id),
            )

    def list_runs(self) -> list[RunSummary]:
        """Return summaries of all runs.

        Returns:
            List of RunSummary with aggregate trial statistics.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT r.run_id, r.run_type, r.status, r.created_at, "
                "r.finished_at, "
                "COALESCE(COUNT(t.trial_id), 0) AS total_trials, "
                "COALESCE(SUM(t.cost), 0.0) AS total_cost, "
                "COALESCE(AVG(t.latency_seconds), 0.0) AS avg_latency "
                "FROM runs r LEFT JOIN trials t ON r.run_id = t.run_id "
                "GROUP BY r.run_id ORDER BY r.created_at"
            ).fetchall()
        return [
            RunSummary(
                run_id=r["run_id"],
                run_type=r["run_type"],
                status=r["status"],
                created_at=r["created_at"],
                finished_at=r["finished_at"],
                total_trials=r["total_trials"],
                total_cost=r["total_cost"],
                avg_latency=r["avg_latency"],
            )
            for r in rows
        ]

    def get_run_summary(self, run_id: str) -> RunSummary:
        """Return summary for a specific run.

        Args:
            run_id: The run to summarize.

        Returns:
            RunSummary with aggregate statistics.

        Raises:
            ValueError: If run_id is not found.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT r.run_id, r.run_type, r.status, r.created_at, "
                "r.finished_at, "
                "COALESCE(COUNT(t.trial_id), 0) AS total_trials, "
                "COALESCE(SUM(t.cost), 0.0) AS total_cost, "
                "COALESCE(AVG(t.latency_seconds), 0.0) AS avg_latency "
                "FROM runs r LEFT JOIN trials t ON r.run_id = t.run_id "
                "WHERE r.run_id = ? GROUP BY r.run_id",
                (run_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Run '{run_id}' not found")
        return RunSummary(
            run_id=row["run_id"],
            run_type=row["run_type"],
            status=row["status"],
            created_at=row["created_at"],
            finished_at=row["finished_at"],
            total_trials=row["total_trials"],
            total_cost=row["total_cost"],
            avg_latency=row["avg_latency"],
        )

    def get_trials(
        self,
        run_id: str,
        *,
        model: str | None = None,
        source: str | None = None,
    ) -> list[TrialRecord]:
        """Return trials for a run, optionally filtered.

        Args:
            run_id: The run to query.
            model: If set, only return trials with this model.
            source: If set, only return trials with this source.

        Returns:
            List of TrialRecord instances.
        """
        query = "SELECT * FROM trials WHERE run_id = ?"
        params: list[str] = [run_id]
        if model is not None:
            query += " AND model = ?"
            params.append(model)
        if source is not None:
            query += " AND source = ?"
            params.append(source)
        query += " ORDER BY trial_id"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            TrialRecord(
                trial_id=r["trial_id"],
                run_id=r["run_id"],
                task_id=r["task_id"],
                task_type=r["task_type"],
                variant_name=r["variant_name"],
                repetition=r["repetition"],
                score=r["score"],
                prompt_tokens=r["prompt_tokens"],
                completion_tokens=r["completion_tokens"],
                total_tokens=r["total_tokens"],
                cost=r["cost"],
                latency_seconds=r["latency_seconds"],
                model=r["model"],
                source=r["source"],
                error=r["error"],
            )
            for r in rows
        ]

    def save_phase_results(
        self,
        *,
        run_id: str,
        main_effects: dict,
        anova: dict,
        optimal: dict,
        significant_factors: list[str],
        quality_type: str,
    ) -> None:
        """Save Taguchi phase analysis results for a run.

        Args:
            run_id: The run these results belong to.
            main_effects: Factor main-effect means (JSON-serialized).
            anova: ANOVA table with p-values and effect sizes.
            optimal: Optimal level per factor.
            significant_factors: List of statistically significant factors.
            quality_type: Quality characteristic type (e.g. "larger_is_better").
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO phase_results "
                "(run_id, main_effects, anova, optimal, "
                "significant_factors, quality_type, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    json.dumps(main_effects),
                    json.dumps(anova),
                    json.dumps(optimal),
                    json.dumps(significant_factors),
                    quality_type,
                    now,
                ),
            )

    def get_phase_results(self, run_id: str) -> dict | None:
        """Retrieve phase analysis results for a run.

        Args:
            run_id: The run to query.

        Returns:
            Dict with main_effects, anova, optimal, significant_factors,
            quality_type keys, or None if no results exist.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM phase_results WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "main_effects": json.loads(row["main_effects"]),
            "anova": json.loads(row["anova"]),
            "optimal": json.loads(row["optimal"]),
            "significant_factors": json.loads(row["significant_factors"]),
            "quality_type": row["quality_type"],
        }

    def get_pipeline_runs(self, pipeline_id: str) -> list[RunSummary]:
        """Return all runs in a pipeline ordered by creation time.

        Args:
            pipeline_id: The pipeline to query.

        Returns:
            List of RunSummary for runs in this pipeline.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT r.run_id, r.run_type, r.status, r.created_at, "
                "r.finished_at, "
                "COALESCE(COUNT(t.trial_id), 0) AS total_trials, "
                "COALESCE(SUM(t.cost), 0.0) AS total_cost, "
                "COALESCE(AVG(t.latency_seconds), 0.0) AS avg_latency "
                "FROM runs r LEFT JOIN trials t ON r.run_id = t.run_id "
                "WHERE r.pipeline_id = ? "
                "GROUP BY r.run_id ORDER BY r.created_at",
                (pipeline_id,),
            ).fetchall()
        return [
            RunSummary(
                run_id=r["run_id"],
                run_type=r["run_type"],
                status=r["status"],
                created_at=r["created_at"],
                finished_at=r["finished_at"],
                total_trials=r["total_trials"],
                total_cost=r["total_cost"],
                avg_latency=r["avg_latency"],
            )
            for r in rows
        ]
