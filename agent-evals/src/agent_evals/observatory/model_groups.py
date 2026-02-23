"""Model group management with SQLite persistence.

Named model groups allow users to save and reuse common model
selections across evaluation runs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from agent_evals.observatory.model_catalog import ModelCatalog

logger = logging.getLogger(__name__)


@dataclass
class ModelGroup:
    """A named group of models."""

    id: int
    name: str
    description: str
    member_ids: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of validating model IDs against the catalog."""

    valid: list[str]
    missing: list[str]


class ModelGroupManager:
    """CRUD operations for model groups using the catalog's SQLite connection."""

    def __init__(self, catalog: ModelCatalog) -> None:
        self._catalog = catalog
        self._create_tables()

    def _create_tables(self) -> None:
        """Create group tables if not present."""
        self._catalog._conn.executescript("""
            CREATE TABLE IF NOT EXISTS model_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS model_group_members (
                group_id INTEGER NOT NULL,
                model_id TEXT NOT NULL,
                PRIMARY KEY (group_id, model_id),
                FOREIGN KEY (group_id) REFERENCES model_groups(id)
            );
        """)
        self._catalog._conn.commit()

    def create_group(
        self,
        name: str,
        description: str = "",
    ) -> ModelGroup:
        """Create a new model group.

        Raises:
            ValueError: If a group with the same name already exists.
        """
        existing = self._catalog._conn.execute(
            "SELECT id FROM model_groups WHERE name = ?", (name,)
        ).fetchone()
        if existing is not None:
            raise ValueError(f"Group '{name}' already exists")

        cursor = self._catalog._conn.execute(
            "INSERT INTO model_groups (name, description) VALUES (?, ?)",
            (name, description),
        )
        self._catalog._conn.commit()
        return ModelGroup(
            id=cursor.lastrowid,
            name=name,
            description=description,
        )

    def add_to_group(
        self,
        group_id: int,
        model_ids: list[str],
    ) -> list[str]:
        """Add models to a group. Returns warnings for missing models."""
        warnings: list[str] = []
        for model_id in model_ids:
            model = self._catalog.get_model(model_id)
            if model is None:
                warnings.append(f"Model '{model_id}' not found in catalog")
                logger.warning("Model '%s' not found in catalog", model_id)
                continue
            self._catalog._conn.execute(
                "INSERT OR IGNORE INTO model_group_members "
                "(group_id, model_id) VALUES (?, ?)",
                (group_id, model_id),
            )
        self._catalog._conn.commit()
        return warnings

    def remove_from_group(
        self,
        group_id: int,
        model_ids: list[str],
    ) -> None:
        """Remove models from a group."""
        for model_id in model_ids:
            self._catalog._conn.execute(
                "DELETE FROM model_group_members "
                "WHERE group_id = ? AND model_id = ?",
                (group_id, model_id),
            )
        self._catalog._conn.commit()

    def get_group_members(self, group_id: int) -> list[str]:
        """Return list of model IDs in the group."""
        rows = self._catalog._conn.execute(
            "SELECT model_id FROM model_group_members WHERE group_id = ?",
            (group_id,),
        ).fetchall()
        return [row[0] for row in rows]

    def list_groups(self) -> list[ModelGroup]:
        """Return all groups (without member lists)."""
        rows = self._catalog._conn.execute(
            "SELECT id, name, description FROM model_groups ORDER BY name"
        ).fetchall()
        return [
            ModelGroup(id=row[0], name=row[1], description=row[2])
            for row in rows
        ]

    def show_group(self, group_id: int) -> ModelGroup:
        """Return a group with its member IDs populated."""
        row = self._catalog._conn.execute(
            "SELECT id, name, description FROM model_groups WHERE id = ?",
            (group_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Group {group_id} not found")
        members = self.get_group_members(group_id)
        return ModelGroup(
            id=row[0],
            name=row[1],
            description=row[2],
            member_ids=members,
        )

    def delete_group(self, group_id: int) -> None:
        """Delete a group and its memberships."""
        self._catalog._conn.execute(
            "DELETE FROM model_group_members WHERE group_id = ?",
            (group_id,),
        )
        self._catalog._conn.execute(
            "DELETE FROM model_groups WHERE id = ?",
            (group_id,),
        )
        self._catalog._conn.commit()

    def validate_model_ids(
        self,
        model_ids: list[str],
    ) -> ValidationResult:
        """Check which model IDs exist in the catalog."""
        valid: list[str] = []
        missing: list[str] = []
        for model_id in model_ids:
            if self._catalog.get_model(model_id) is not None:
                valid.append(model_id)
            else:
                missing.append(model_id)
        return ValidationResult(valid=valid, missing=missing)

    def resolve_group(self, group_id: int) -> list[str]:
        """Resolve a group to its member model IDs."""
        return self.get_group_members(group_id)

    def resolve_models(
        self,
        model_ids: list[str] | None = None,
        group_id: int | None = None,
    ) -> list[str]:
        """Union of explicit model IDs and group members, preserving order."""
        result: list[str] = []
        seen: set[str] = set()

        if group_id is not None:
            for mid in self.resolve_group(group_id):
                if mid not in seen:
                    result.append(mid)
                    seen.add(mid)

        if model_ids is not None:
            for mid in model_ids:
                if mid not in seen:
                    result.append(mid)
                    seen.add(mid)

        return result
