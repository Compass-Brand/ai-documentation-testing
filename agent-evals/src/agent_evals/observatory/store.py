"""SQLite-backed observatory store for run and trial telemetry.

Provides persistent storage for evaluation runs and their trial-level
results, with support for filtering, aggregation, and concurrent writes.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_provider(model: str | None) -> str | None:
    """Extract the provider prefix from a model string.

    Examples:
        "openrouter/arcee-ai/trinity:free" -> "openrouter"
        "claude-sonnet" -> None
        None -> None
    """
    if not model or "/" not in model:
        return None
    return model.split("/", 1)[0]


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
    oa_row_id: int | None = None
    phase: str | None = None
    context_strategy: str = "full_context"
    llm_calls: int = 1
    strategy_metadata: dict | None = None
    judge_score: float | None = None


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
    heartbeat_at: str | None = None
    config: dict = field(default_factory=dict)
    pipeline_id: str | None = None
    phase: str | None = None


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

CREATE TABLE IF NOT EXISTS trial_traces (
    trial_id      INTEGER PRIMARY KEY REFERENCES trials(trial_id),
    prompt_json   TEXT NOT NULL,
    response_text TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS factor_definitions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL REFERENCES runs(run_id),
    factor_name  TEXT NOT NULL,
    axis_id      INTEGER NOT NULL,
    level_index  INTEGER NOT NULL,
    level_name   TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS task_metadata (
    task_id    TEXT PRIMARY KEY,
    task_type  TEXT NOT NULL,
    domain     TEXT NOT NULL DEFAULT '',
    difficulty TEXT NOT NULL DEFAULT '',
    word_count INTEGER NOT NULL DEFAULT 0,
    tag_count  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS report_artifacts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL REFERENCES runs(run_id),
    artifact_type TEXT NOT NULL,
    data_json     TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    UNIQUE(run_id, artifact_type)
);

CREATE TABLE IF NOT EXISTS llm_call_details (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_id          INTEGER NOT NULL REFERENCES trials(trial_id),
    call_index        INTEGER NOT NULL,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    cost              REAL,
    api_call_ms       REAL NOT NULL DEFAULT 0.0,
    cached_tokens     INTEGER NOT NULL DEFAULT 0,
    model             TEXT NOT NULL DEFAULT '',
    provider          TEXT
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
        """Add new columns and indexes to existing tables (idempotent)."""
        migrations = [
            "ALTER TABLE runs ADD COLUMN parent_run_id TEXT",
            "ALTER TABLE runs ADD COLUMN phase TEXT",
            "ALTER TABLE runs ADD COLUMN pipeline_id TEXT",
            "ALTER TABLE runs ADD COLUMN heartbeat_at TEXT",
            "ALTER TABLE trials ADD COLUMN oa_row_id INTEGER",
            "ALTER TABLE trials ADD COLUMN phase TEXT",
            "ALTER TABLE trials ADD COLUMN context_strategy TEXT DEFAULT 'full_context'",
            "ALTER TABLE trials ADD COLUMN llm_calls INTEGER DEFAULT 1",
            "ALTER TABLE trials ADD COLUMN strategy_metadata TEXT",
            "ALTER TABLE phase_results ADD COLUMN total_cost REAL DEFAULT 0.0",
            "ALTER TABLE phase_results ADD COLUMN total_tokens INTEGER DEFAULT 0",
            "ALTER TABLE phase_results ADD COLUMN elapsed_seconds REAL DEFAULT 0.0",
            "ALTER TABLE phase_results ADD COLUMN interaction_effects TEXT DEFAULT '[]'",
            "ALTER TABLE phase_results ADD COLUMN predicted_sn REAL",
            "ALTER TABLE phase_results ADD COLUMN prediction_interval TEXT",
            "ALTER TABLE phase_results ADD COLUMN se_prediction REAL",
            "ALTER TABLE phase_results ADD COLUMN confirmation TEXT",
            "ALTER TABLE trials ADD COLUMN judge_score REAL",
        ]
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_trials_run_type_variant "
            "ON trials (run_id, task_type, variant_name)",
            "CREATE INDEX IF NOT EXISTS idx_trials_source_type "
            "ON trials (source, task_type)",
            "CREATE INDEX IF NOT EXISTS idx_trials_variant_rep "
            "ON trials (variant_name, repetition)",
            "CREATE INDEX IF NOT EXISTS idx_trials_strategy "
            "ON trials (context_strategy)",
            "CREATE INDEX IF NOT EXISTS idx_factor_defs_run "
            "ON factor_definitions (run_id)",
            "CREATE INDEX IF NOT EXISTS idx_report_artifacts_run "
            "ON report_artifacts (run_id)",
            "CREATE INDEX IF NOT EXISTS idx_llm_calls_trial "
            "ON llm_call_details (trial_id)",
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
            for stmt in indexes:
                conn.execute(stmt)

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

    @staticmethod
    def _row_to_summary(r: sqlite3.Row) -> RunSummary:
        """Convert a joined run+trials aggregate row to RunSummary."""
        return RunSummary(
            run_id=r["run_id"],
            run_type=r["run_type"],
            status=r["status"],
            created_at=r["created_at"],
            finished_at=r["finished_at"],
            total_trials=r["total_trials"],
            total_cost=r["total_cost"],
            avg_latency=r["avg_latency"],
            heartbeat_at=r["heartbeat_at"],
            config=json.loads(r["config"] or "{}"),
            pipeline_id=r["pipeline_id"],
            phase=r["phase"],
        )

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
        context_strategy: str = "full_context",
        llm_calls: int = 1,
        strategy_metadata: dict | None = None,
        judge_score: float | None = None,
    ) -> int:
        """Record a single trial result.

        Returns:
            The auto-generated trial_id for the inserted row.
        """
        now = datetime.now(timezone.utc).isoformat()
        meta_json = json.dumps(strategy_metadata) if strategy_metadata else None
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO trials "
                "(run_id, task_id, task_type, variant_name, repetition, "
                "score, prompt_tokens, completion_tokens, total_tokens, "
                "cost, latency_seconds, model, source, error, created_at, "
                "oa_row_id, phase, context_strategy, llm_calls, "
                "strategy_metadata, judge_score) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id, task_id, task_type, variant_name, repetition,
                    score, prompt_tokens, completion_tokens, total_tokens,
                    cost, latency_seconds, model, source, error, now,
                    oa_row_id, phase, context_strategy, llm_calls, meta_json,
                    judge_score,
                ),
            )
            return cursor.lastrowid  # type: ignore[return-value]

    def record_trace(
        self,
        *,
        trial_id: int,
        prompt_json: list[dict],
        response_text: str,
    ) -> None:
        """Store prompt/response trace for a trial.

        Idempotent: silently ignores duplicate insertions for the same
        trial_id (INSERT OR IGNORE).

        Args:
            trial_id: The trial to attach the trace to.
            prompt_json: Prompt messages as a list of dicts.
            response_text: Raw LLM response text.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO trial_traces "
                "(trial_id, prompt_json, response_text, created_at) "
                "VALUES (?, ?, ?, ?)",
                (trial_id, json.dumps(prompt_json), response_text, now),
            )

    def get_trace(self, trial_id: int) -> dict | None:
        """Retrieve the trace for a given trial.

        Returns:
            Dict with prompt_json (parsed), response_text, created_at,
            or None if no trace exists.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT prompt_json, response_text, created_at "
                "FROM trial_traces WHERE trial_id = ?",
                (trial_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "prompt_json": json.loads(row["prompt_json"]),
            "response_text": row["response_text"],
            "created_at": row["created_at"],
        }

    def finish_run(self, run_id: str) -> None:
        """Mark a run as completed (or 'empty' if it has zero trials)."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            trial_count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM trials WHERE run_id = ?",
                (run_id,),
            ).fetchone()["cnt"]
            status = "completed" if trial_count > 0 else "empty"
            conn.execute(
                "UPDATE runs SET status = ?, finished_at = ? "
                "WHERE run_id = ?",
                (status, now, run_id),
            )

    def purge_empty_runs(self) -> list[str]:
        """Delete runs with status 'empty' (zero trials).

        Returns list of purged run_ids.
        """
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT run_id FROM runs WHERE status = 'empty'"
            ).fetchall()
            if rows:
                ids = [r["run_id"] for r in rows]
                placeholders = ",".join("?" * len(ids))
                conn.execute(
                    f"DELETE FROM runs WHERE run_id IN ({placeholders})",
                    ids,
                )
            return [r["run_id"] for r in rows]

    def fail_run(self, run_id: str, error: str | None = None) -> None:
        """Mark a run as failed with optional error message and timestamp."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            if error:
                conn.execute(
                    "UPDATE runs SET status = 'failed', finished_at = ?, "
                    "config = json_set(COALESCE(config, '{}'), '$.error', ?) "
                    "WHERE run_id = ?",
                    (now, error, run_id),
                )
            else:
                conn.execute(
                    "UPDATE runs SET status = 'failed', finished_at = ? "
                    "WHERE run_id = ?",
                    (now, run_id),
                )

    def update_heartbeat(self, run_id: str) -> None:
        """Update the heartbeat timestamp for a run."""
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE runs SET heartbeat_at = ? WHERE run_id = ?",
                (now, run_id),
            )

    def reap_stale_runs(self, max_age_seconds: int = 300) -> list[str]:
        """Mark stale active runs as failed.

        Catches two cases:
        1. Runs with a heartbeat older than the cutoff.
        2. Runs with no heartbeat whose created_at is older than the cutoff
           (zombie runs that never received a heartbeat).

        Returns list of reaped run_ids.
        """
        cutoff = (
            datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
        ).isoformat()
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            stale = conn.execute(
                "SELECT run_id FROM runs WHERE status = 'active' "
                "AND ("
                "  (heartbeat_at IS NOT NULL AND heartbeat_at < ?) "
                "  OR (heartbeat_at IS NULL AND created_at < ?)"
                ")",
                (cutoff, cutoff),
            ).fetchall()
            if stale:
                ids = [row["run_id"] for row in stale]
                placeholders = ",".join("?" * len(ids))
                conn.execute(
                    f"UPDATE runs SET status = 'failed', finished_at = ? "
                    f"WHERE run_id IN ({placeholders})",
                    [now, *ids],
                )
        return [row["run_id"] for row in stale]

    def list_runs(
        self, limit: int | None = None, offset: int = 0
    ) -> list[RunSummary]:
        """Return summaries of all runs with optional SQL pagination."""
        query = (
            "SELECT r.run_id, r.run_type, r.status, r.created_at, "
            "r.finished_at, r.config, r.pipeline_id, r.heartbeat_at, "
            "r.phase, "
            "COALESCE(COUNT(t.trial_id), 0) AS total_trials, "
            "COALESCE(SUM(t.cost), 0.0) AS total_cost, "
            "COALESCE(AVG(t.latency_seconds), 0.0) AS avg_latency "
            "FROM runs r LEFT JOIN trials t ON r.run_id = t.run_id "
            "GROUP BY r.run_id ORDER BY r.created_at DESC"
        )
        params: list[int] = []
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params = [int(limit), int(offset)]
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_summary(r) for r in rows]

    def get_run_summary(self, run_id: str) -> RunSummary:
        """Return summary for a specific run."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT r.run_id, r.run_type, r.status, r.created_at, "
                "r.finished_at, r.config, r.pipeline_id, r.heartbeat_at, "
                "r.phase, "
                "COALESCE(COUNT(t.trial_id), 0) AS total_trials, "
                "COALESCE(SUM(t.cost), 0.0) AS total_cost, "
                "COALESCE(AVG(t.latency_seconds), 0.0) AS avg_latency "
                "FROM runs r LEFT JOIN trials t ON r.run_id = t.run_id "
                "WHERE r.run_id = ? GROUP BY r.run_id",
                (run_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Run '{run_id}' not found")
        return self._row_to_summary(row)

    def get_run_aggregates(self, run_id: str) -> dict:
        """Return SQL-aggregated trial statistics without loading individual records."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt, AVG(score) AS avg_score, "
                "SUM(prompt_tokens + completion_tokens) AS tok, "
                "AVG(latency_seconds) AS avg_lat "
                "FROM trials WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            by_variant = conn.execute(
                "SELECT variant_name, COUNT(*) AS cnt, AVG(score) AS avg_score "
                "FROM trials WHERE run_id = ? "
                "GROUP BY variant_name",
                (run_id,),
            ).fetchall()
            by_strategy = conn.execute(
                "SELECT variant_name, context_strategy, "
                "COUNT(*) AS cnt, AVG(score) AS avg_score "
                "FROM trials WHERE run_id = ? "
                "GROUP BY variant_name, context_strategy",
                (run_id,),
            ).fetchall()
        return {
            "trial_count": row["cnt"] or 0,
            "mean_score": row["avg_score"] or 0.0,
            "total_tokens": row["tok"] or 0,
            "mean_latency_seconds": row["avg_lat"] or 0.0,
            "by_variant": [
                {
                    "variant": r["variant_name"],
                    "count": r["cnt"],
                    "mean_score": r["avg_score"],
                }
                for r in by_variant
            ],
            "by_strategy": [
                {
                    "variant": r["variant_name"],
                    "strategy": r["context_strategy"] or "full_context",
                    "count": r["cnt"],
                    "mean_score": r["avg_score"],
                }
                for r in by_strategy
            ],
        }

    def get_trials(
        self,
        run_id: str,
        *,
        model: str | None = None,
        source: str | None = None,
        context_strategy: str | None = None,
    ) -> list[TrialRecord]:
        """Return trials for a run, optionally filtered."""
        query = "SELECT * FROM trials WHERE run_id = ?"
        params: list[str] = [run_id]
        if model is not None:
            query += " AND model = ?"
            params.append(model)
        if source is not None:
            query += " AND source = ?"
            params.append(source)
        if context_strategy is not None:
            query += " AND context_strategy = ?"
            params.append(context_strategy)
        query += " ORDER BY trial_id"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        def _parse_metadata(raw: str | None) -> dict | None:
            if raw is None:
                return None
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return None

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
                oa_row_id=r["oa_row_id"],
                phase=r["phase"],
                context_strategy=r["context_strategy"] or "full_context",
                llm_calls=r["llm_calls"] or 1,
                strategy_metadata=_parse_metadata(r["strategy_metadata"]),
                judge_score=r["judge_score"] if "judge_score" in r.keys() else None,
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
        total_cost: float = 0.0,
        total_tokens: int = 0,
        elapsed_seconds: float = 0.0,
        interaction_effects: list[dict] | None = None,
        predicted_sn: float | None = None,
        prediction_interval: tuple[float, float] | None = None,
        se_prediction: float | None = None,
        confirmation: dict | None = None,
    ) -> None:
        """Save Taguchi phase analysis results for a run."""
        now = datetime.now(timezone.utc).isoformat()
        interval_json = (
            json.dumps(list(prediction_interval))
            if prediction_interval is not None
            else None
        )
        confirmation_json = (
            json.dumps(confirmation) if confirmation is not None else None
        )
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO phase_results "
                "(run_id, main_effects, anova, optimal, "
                "significant_factors, quality_type, created_at, "
                "total_cost, total_tokens, elapsed_seconds, "
                "interaction_effects, predicted_sn, prediction_interval, "
                "se_prediction, confirmation) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    json.dumps(main_effects),
                    json.dumps(anova),
                    json.dumps(optimal),
                    json.dumps(significant_factors),
                    quality_type,
                    now,
                    total_cost,
                    total_tokens,
                    elapsed_seconds,
                    json.dumps(interaction_effects or []),
                    predicted_sn,
                    interval_json,
                    se_prediction,
                    confirmation_json,
                ),
            )

    def get_phase_results(self, run_id: str) -> dict | None:
        """Retrieve phase analysis results for a run."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM phase_results WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None

        def _safe_json(column: str) -> object:
            try:
                return json.loads(row[column])
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "Corrupted JSON in phase_results.%s for run %s",
                    column,
                    run_id,
                )
                return None

        # Parse prediction_interval JSON (stored as [low, high] or null)
        raw_interval = row["prediction_interval"] if "prediction_interval" in row.keys() else None
        prediction_interval = None
        if raw_interval is not None:
            try:
                prediction_interval = json.loads(raw_interval)
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "Corrupted JSON in phase_results.prediction_interval for run %s",
                    run_id,
                )

        return {
            "main_effects": _safe_json("main_effects"),
            "anova": _safe_json("anova"),
            "optimal": _safe_json("optimal"),
            "significant_factors": _safe_json("significant_factors"),
            "quality_type": row["quality_type"],
            "total_cost": row["total_cost"] or 0.0,
            "total_tokens": row["total_tokens"] or 0,
            "elapsed_seconds": row["elapsed_seconds"] or 0.0,
            "interaction_effects": _safe_json("interaction_effects") or [],
            "predicted_sn": row["predicted_sn"] if "predicted_sn" in row.keys() else None,
            "prediction_interval": prediction_interval,
            "se_prediction": row["se_prediction"] if "se_prediction" in row.keys() else None,
            "confirmation": _safe_json("confirmation") if "confirmation" in row.keys() else None,
        }

    def get_pipeline_runs(self, pipeline_id: str) -> list[RunSummary]:
        """Return all runs in a pipeline ordered by creation time."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT r.run_id, r.run_type, r.status, r.created_at, "
                "r.finished_at, r.config, r.pipeline_id, r.heartbeat_at, "
                "r.phase, "
                "COALESCE(COUNT(t.trial_id), 0) AS total_trials, "
                "COALESCE(SUM(t.cost), 0.0) AS total_cost, "
                "COALESCE(AVG(t.latency_seconds), 0.0) AS avg_latency "
                "FROM runs r LEFT JOIN trials t ON r.run_id = t.run_id "
                "WHERE r.pipeline_id = ? "
                "GROUP BY r.run_id ORDER BY r.created_at",
                (pipeline_id,),
            ).fetchall()
        return [self._row_to_summary(r) for r in rows]

    def resume_run(self, run_id: str) -> None:
        """Reactivate a failed/completed run for resumption.

        Sets status back to 'active' and updates heartbeat.

        Raises:
            ValueError: If run_id does not exist.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT 1 FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if existing is None:
                raise ValueError(f"Run '{run_id}' not found")
            conn.execute(
                "UPDATE runs SET status = 'active', heartbeat_at = ?, "
                "finished_at = NULL WHERE run_id = ?",
                (now, run_id),
            )

    def get_completed_trial_keys(
        self, run_id: str
    ) -> set[tuple[int | None, str, str, int]]:
        """Return identifiers for all successfully completed trials in a run.

        Each key is ``(oa_row_id, task_id, variant_name, repetition)``.
        Error trials (error IS NOT NULL) are excluded so they can be retried.

        Returns:
            Empty set if the run doesn't exist or has no completed trials.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT oa_row_id, task_id, variant_name, repetition "
                "FROM trials WHERE run_id = ? AND error IS NULL",
                (run_id,),
            ).fetchall()
        return {
            (r["oa_row_id"], r["task_id"], r["variant_name"], r["repetition"])
            for r in rows
        }

    def checkpoint_wal(self) -> None:
        """Force a WAL checkpoint to flush writes to the main database file."""
        with self._connect() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def list_pipelines(self) -> list[dict]:
        """Return all distinct pipelines with aggregated run statistics."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT pipeline_id, COUNT(*) as run_count, "
                "MAX(created_at) as last_run_at "
                "FROM runs WHERE pipeline_id IS NOT NULL "
                "GROUP BY pipeline_id ORDER BY last_run_at DESC"
            ).fetchall()
        return [
            {"pipeline_id": r["pipeline_id"], "run_count": r["run_count"]}
            for r in rows
        ]

    def save_factor_definitions(
        self, run_id: str, definitions: list[dict]
    ) -> None:
        """Save factor/level definitions for a run.

        Replaces any existing definitions for the run (DELETE + INSERT).

        Args:
            run_id: The run to attach definitions to.
            definitions: List of dicts with keys: factor_name, axis_id,
                level_index, level_name, description.
        """
        with self._lock, self._connect() as conn:
            conn.execute(
                "DELETE FROM factor_definitions WHERE run_id = ?",
                (run_id,),
            )
            for d in definitions:
                conn.execute(
                    "INSERT INTO factor_definitions "
                    "(run_id, factor_name, axis_id, level_index, "
                    "level_name, description) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        run_id,
                        d["factor_name"],
                        d["axis_id"],
                        d["level_index"],
                        d["level_name"],
                        d.get("description", ""),
                    ),
                )

    def get_factor_definitions(self, run_id: str) -> list[dict]:
        """Retrieve factor definitions for a run.

        Returns:
            List of dicts ordered by axis_id then level_index.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT factor_name, axis_id, level_index, "
                "level_name, description "
                "FROM factor_definitions WHERE run_id = ? "
                "ORDER BY axis_id, level_index",
                (run_id,),
            ).fetchall()
        return [
            {
                "factor_name": r["factor_name"],
                "axis_id": r["axis_id"],
                "level_index": r["level_index"],
                "level_name": r["level_name"],
                "description": r["description"],
            }
            for r in rows
        ]

    def save_task_metadata(self, metadata_list: list[dict]) -> None:
        """Upsert task metadata records.

        Each dict must have keys: task_id, task_type, domain, difficulty,
        word_count, tag_count. Existing rows with the same task_id are
        replaced (INSERT OR REPLACE).

        Args:
            metadata_list: List of task metadata dicts to persist.
        """
        with self._lock, self._connect() as conn:
            for m in metadata_list:
                conn.execute(
                    "INSERT OR REPLACE INTO task_metadata "
                    "(task_id, task_type, domain, difficulty, "
                    "word_count, tag_count) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        m["task_id"],
                        m["task_type"],
                        m.get("domain", ""),
                        m.get("difficulty", ""),
                        m.get("word_count", 0),
                        m.get("tag_count", 0),
                    ),
                )

    def save_report_artifact(
        self, run_id: str, artifact_type: str, data: dict
    ) -> None:
        """Save or replace a report artifact.

        Uses INSERT OR REPLACE on the UNIQUE(run_id, artifact_type)
        constraint so a second save for the same key overwrites.

        Args:
            run_id: The run this artifact belongs to.
            artifact_type: Kind of artifact (e.g. "kv_cache_analysis").
            data: Arbitrary dict payload serialised as JSON.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO report_artifacts "
                "(run_id, artifact_type, data_json, created_at) "
                "VALUES (?, ?, ?, ?)",
                (run_id, artifact_type, json.dumps(data), now),
            )

    def get_report_artifact(
        self, run_id: str, artifact_type: str
    ) -> dict | None:
        """Retrieve a specific report artifact.

        Returns:
            Dict with ``data`` (parsed JSON) and ``created_at``,
            or None if no matching artifact exists.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data_json, created_at FROM report_artifacts "
                "WHERE run_id = ? AND artifact_type = ?",
                (run_id, artifact_type),
            ).fetchone()
        if row is None:
            return None
        return {
            "data": json.loads(row["data_json"]),
            "created_at": row["created_at"],
        }

    def list_report_artifacts(self, run_id: str) -> list[dict]:
        """List all artifacts for a run.

        Returns:
            List of ``{"artifact_type": str, "created_at": str}``
            ordered by artifact_type.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT artifact_type, created_at FROM report_artifacts "
                "WHERE run_id = ? ORDER BY artifact_type",
                (run_id,),
            ).fetchall()
        return [
            {
                "artifact_type": r["artifact_type"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def get_task_metadata(
        self, *, task_type: str | None = None
    ) -> list[dict]:
        """Retrieve task metadata, optionally filtered by task_type.

        Returns:
            List of dicts ordered by task_id.
        """
        query = "SELECT task_id, task_type, domain, difficulty, word_count, tag_count FROM task_metadata"
        params: list[str] = []
        if task_type is not None:
            query += " WHERE task_type = ?"
            params.append(task_type)
        query += " ORDER BY task_id"

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            {
                "task_id": r["task_id"],
                "task_type": r["task_type"],
                "domain": r["domain"],
                "difficulty": r["difficulty"],
                "word_count": r["word_count"],
                "tag_count": r["tag_count"],
            }
            for r in rows
        ]

    def save_llm_call_details(
        self, trial_id: int, calls: list[dict]
    ) -> None:
        """Batch insert per-call LLM details for a trial.

        Args:
            trial_id: The trial to attach call details to.
            calls: List of dicts with keys: call_index, prompt_tokens,
                completion_tokens, cost, api_call_ms, cached_tokens,
                model, provider.
        """
        with self._lock, self._connect() as conn:
            for c in calls:
                raw_provider = c.get("provider")
                # Treat the literal string "None" as missing (bug #244).
                if raw_provider is None or raw_provider == "None":
                    raw_provider = extract_provider(c.get("model", ""))
                conn.execute(
                    "INSERT INTO llm_call_details "
                    "(trial_id, call_index, prompt_tokens, "
                    "completion_tokens, cost, api_call_ms, "
                    "cached_tokens, model, provider) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        trial_id,
                        c["call_index"],
                        c.get("prompt_tokens", 0),
                        c.get("completion_tokens", 0),
                        c.get("cost"),
                        c.get("api_call_ms", 0.0),
                        c.get("cached_tokens", 0),
                        c.get("model", ""),
                        raw_provider,
                    ),
                )

    def get_llm_call_details(self, trial_id: int) -> list[dict]:
        """Retrieve per-call LLM details for a trial.

        Returns:
            List of dicts ordered by call_index. Each dict has:
            call_index, prompt_tokens, completion_tokens, cost,
            api_call_ms, cached_tokens, model, provider.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT call_index, prompt_tokens, completion_tokens, "
                "cost, api_call_ms, cached_tokens, model, provider "
                "FROM llm_call_details WHERE trial_id = ? "
                "ORDER BY call_index",
                (trial_id,),
            ).fetchall()
        return [
            {
                "call_index": r["call_index"],
                "prompt_tokens": r["prompt_tokens"],
                "completion_tokens": r["completion_tokens"],
                "cost": r["cost"],
                "api_call_ms": r["api_call_ms"],
                "cached_tokens": r["cached_tokens"],
                "model": r["model"],
                "provider": r["provider"],
            }
            for r in rows
        ]
