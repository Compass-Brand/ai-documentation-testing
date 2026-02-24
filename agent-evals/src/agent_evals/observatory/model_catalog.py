"""SQLite-backed model catalog with filtering and sync logging.

Stores OpenRouter model metadata with support for upsert, soft-delete,
multi-criteria filtering (price, context, modality, capabilities,
tokenizer), and sync run history.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


class ModelCatalog:
    """SQLite-backed store for model metadata.

    Args:
        db_path: Path to the SQLite database file. Created if missing.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Yield the database connection while holding the lock.

        Use this to execute queries against the shared connection in
        a thread-safe manner.  External code (e.g. ``ModelGroupManager``)
        should prefer this over accessing ``_conn`` directly.
        """
        with self._lock:
            yield self._conn

    def _create_tables(self) -> None:
        """Create schema if not present."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS models (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                context_length INTEGER NOT NULL,
                prompt_price REAL NOT NULL,
                completion_price REAL NOT NULL,
                modality TEXT DEFAULT 'text',
                tokenizer TEXT DEFAULT '',
                supported_params TEXT DEFAULT '[]',
                created INTEGER DEFAULT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                removed_at TEXT DEFAULT NULL
            );
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                models_added INTEGER NOT NULL,
                models_removed INTEGER NOT NULL,
                total_count INTEGER NOT NULL
            );
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def upsert_model(
        self,
        id: str,
        name: str,
        context_length: int,
        prompt_price: float,
        completion_price: float,
        modality: str = "text",
        tokenizer: str = "",
        supported_params: list[str] | None = None,
        created: int | None = None,
    ) -> None:
        """Insert or update a model, preserving ``first_seen``."""
        now = _now_iso()
        params_json = json.dumps(supported_params or [])
        with self._lock:
            existing = self._conn.execute(
                "SELECT * FROM models WHERE id=?", (id,)
            ).fetchone()
            if existing is not None:
                self._conn.execute(
                    """UPDATE models SET
                           name=?, context_length=?, prompt_price=?,
                           completion_price=?, modality=?, tokenizer=?,
                           supported_params=?, created=?, last_seen=?
                       WHERE id=?""",
                    (name, context_length, prompt_price, completion_price,
                     modality, tokenizer, params_json, created, now, id),
                )
            else:
                self._conn.execute(
                    """INSERT INTO models
                       (id, name, context_length, prompt_price, completion_price,
                        modality, tokenizer, supported_params, created,
                        first_seen, last_seen)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (id, name, context_length, prompt_price, completion_price,
                     modality, tokenizer, params_json, created, now, now),
                )
            self._conn.commit()

    def get_model(self, model_id: str) -> dict[str, Any] | None:
        """Return model metadata as a dict, or ``None`` if not found."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM models WHERE id=?", (model_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def mark_removed(self, model_id: str) -> None:
        """Soft-delete a model by setting ``removed_at``."""
        with self._lock:
            self._conn.execute(
                "UPDATE models SET removed_at=? WHERE id=?",
                (_now_iso(), model_id),
            )
            self._conn.commit()

    def get_active_models(self) -> list[dict[str, Any]]:
        """Return all models that have not been soft-deleted."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM models WHERE removed_at IS NULL"
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Filtering
    # ------------------------------------------------------------------

    def filter_models(
        self,
        *,
        free: bool | None = None,
        max_price: float | None = None,
        min_context: int | None = None,
        modality: str | None = None,
        capabilities: list[str] | None = None,
        tokenizer: str | None = None,
    ) -> list[dict[str, Any]]:
        """Filter active models by multiple criteria (AND logic).

        All filters are optional. Passing none returns all active models.
        """
        clauses: list[str] = ["removed_at IS NULL"]
        params: list[Any] = []

        if free is True:
            clauses.append("prompt_price = 0.0 AND completion_price = 0.0")
        if max_price is not None:
            clauses.append("prompt_price <= ?")
            params.append(max_price)
        if min_context is not None:
            clauses.append("context_length >= ?")
            params.append(min_context)
        if modality is not None:
            clauses.append("modality = ?")
            params.append(modality)
        if tokenizer is not None:
            clauses.append("tokenizer = ?")
            params.append(tokenizer)

        where = " AND ".join(clauses)
        with self._lock:
            rows = self._conn.execute(
                f"SELECT * FROM models WHERE {where}", params  # noqa: S608
            ).fetchall()

        results = [self._row_to_dict(r) for r in rows]

        # Capability filtering done in Python (JSON array in SQLite).
        if capabilities:
            results = [
                m for m in results
                if all(c in m["supported_params"] for c in capabilities)
            ]

        return results

    # ------------------------------------------------------------------
    # Sync logging
    # ------------------------------------------------------------------

    def log_sync(
        self,
        added: int,
        removed: int,
        total: int,
    ) -> None:
        """Record a sync run in the log."""
        with self._lock:
            self._conn.execute(
                """INSERT INTO sync_log (timestamp, models_added, models_removed, total_count)
                   VALUES (?, ?, ?, ?)""",
                (_now_iso(), added, removed, total),
            )
            self._conn.commit()

    def get_sync_history(self) -> list[dict[str, Any]]:
        """Return sync history ordered by most recent first."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM sync_log ORDER BY id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        """Convert a Row to a dict, deserializing JSON fields."""
        d = dict(row)
        if "supported_params" in d and isinstance(d["supported_params"], str):
            d["supported_params"] = json.loads(d["supported_params"])
        return d
