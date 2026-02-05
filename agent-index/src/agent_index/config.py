"""Configuration file loading for agent-index.

Supports YAML (.yaml, .yml) and TOML (.toml) configuration files.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from agent_index.models import IndexConfig

if TYPE_CHECKING:
    from typing import Any

# Config file names to search for, in priority order
CONFIG_FILENAMES = ["agent-index.yaml", "agent-index.yml", "agent-index.toml"]


class ConfigError(Exception):
    """Error loading or validating configuration.

    Attributes:
        path: The config file path, if applicable.
        cause: The underlying exception that caused this error.
    """

    def __init__(
        self,
        message: str,
        *,
        path: Path | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.path = path
        self.cause = cause


def load_config(path: Path | str) -> IndexConfig:
    """Load and validate a configuration file.

    Args:
        path: Path to the configuration file (.yaml, .yml, or .toml).

    Returns:
        Validated IndexConfig instance.

    Raises:
        ConfigError: If the file doesn't exist, has an unsupported extension,
            fails to parse, or fails validation.
    """
    config_path = Path(path)

    # Check file exists
    if not config_path.exists():
        raise ConfigError(
            f"Config file not found: {config_path}",
            path=config_path,
        )

    # Determine format by extension
    suffix = config_path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        data = _load_yaml(config_path)
    elif suffix == ".toml":
        data = _load_toml(config_path)
    else:
        raise ConfigError(
            f"Unsupported config file extension: {suffix}. "
            "Expected .yaml, .yml, or .toml",
            path=config_path,
        )

    # Validate against IndexConfig model
    return _validate_config(data, config_path)


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML file, wrapping parse errors with context."""
    try:
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        return data if data is not None else {}
    except yaml.YAMLError as e:
        # Extract line number if available
        line_info = ""
        if hasattr(e, "problem_mark") and e.problem_mark is not None:
            mark = e.problem_mark
            line_info = f" at line {mark.line + 1}, column {mark.column + 1}"
        raise ConfigError(
            f"YAML parse error in {path}{line_info}: {e}",
            path=path,
            cause=e,
        ) from e


def _load_toml(path: Path) -> dict[str, Any]:
    """Load TOML file, wrapping parse errors with context."""
    try:
        content = path.read_text(encoding="utf-8")
        return tomllib.loads(content)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(
            f"TOML parse error in {path}: {e}",
            path=path,
            cause=e,
        ) from e


def _validate_config(data: dict[str, Any], path: Path) -> IndexConfig:
    """Validate config data against IndexConfig model."""
    from pydantic import ValidationError

    try:
        return IndexConfig.model_validate(data)
    except ValidationError as e:
        # Format validation errors with field paths
        error_details = []
        for error in e.errors():
            loc = ".".join(str(part) for part in error["loc"])
            msg = error["msg"]
            error_details.append(f"  {loc}: {msg}")

        raise ConfigError(
            f"Validation error in {path}:\n" + "\n".join(error_details),
            path=path,
            cause=e,
        ) from e


def find_config(start_dir: Path | None = None) -> Path | None:
    """Search for a config file starting from the given directory.

    Searches upward through parent directories until a config file is found
    or the filesystem root is reached.

    Args:
        start_dir: Directory to start searching from. Defaults to current
            working directory.

    Returns:
        Path to the found config file, or None if not found.
    """
    start_path = Path.cwd() if start_dir is None else Path(start_dir)
    current = start_path.resolve()

    while True:
        # Check for config files in priority order
        for filename in CONFIG_FILENAMES:
            config_path = current / filename
            if config_path.exists():
                return config_path

        # Move to parent directory
        parent = current.parent
        if parent == current:
            # Reached filesystem root
            break
        current = parent

    return None
