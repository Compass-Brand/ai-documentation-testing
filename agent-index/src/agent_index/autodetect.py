"""Auto-detect mode for scanning a project and generating an IndexConfig.

Scans a project directory and uses filename/path heuristics to auto-assign
documentation files to tiers (required, recommended, reference).
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from agent_index.models import IndexConfig, TierConfig

# Filename patterns that signal "required" tier (getting started, setup, install)
_REQUIRED_KEYWORDS: set[str] = {
    "getting-started",
    "getting_started",
    "quickstart",
    "quick-start",
    "quick_start",
    "setup",
    "install",
    "installation",
}

# Filename patterns that signal "reference" tier (API docs, reference material)
_REFERENCE_KEYWORDS: set[str] = {
    "api",
    "reference",
    "ref",
    "spec",
    "specification",
}


def auto_detect(root_path: Path) -> IndexConfig:
    """Scan a project directory and generate an IndexConfig with auto-assigned tiers.

    Heuristics:
    - "getting-started", "quickstart", "setup", "install" -> required tier
    - "api", "reference" -> reference tier
    - Everything else -> recommended tier
    - Detect project name from directory name or package.json/pyproject.toml

    Args:
        root_path: Root directory of the project to scan.

    Returns:
        IndexConfig with auto-detected settings and tier patterns.
    """
    root = Path(root_path)

    # Detect project name
    project_name = _detect_project_name(root)

    # Collect documentation files
    doc_extensions = {".md", ".mdx", ".rst", ".txt"}
    ignore_dirs = {"node_modules", "__pycache__", ".git", ".venv", ".tox"}
    doc_files = _collect_doc_files(root, doc_extensions, ignore_dirs)

    # Classify files into tiers
    required_patterns: list[str] = []
    reference_patterns: list[str] = []
    recommended_patterns: list[str] = []

    for rel_path in doc_files:
        tier = _classify_file(rel_path)
        if tier == "required":
            required_patterns.append(rel_path)
        elif tier == "reference":
            reference_patterns.append(rel_path)
        else:
            recommended_patterns.append(rel_path)

    # Build tier configs with the classified patterns
    tiers = [
        TierConfig(
            name="required",
            instruction="Read these files at the start of every session.",
            patterns=sorted(required_patterns),
        ),
        TierConfig(
            name="recommended",
            instruction="Read these files when working on related tasks.",
            patterns=sorted(recommended_patterns),
        ),
        TierConfig(
            name="reference",
            instruction="Consult these files when you need specific details.",
            patterns=sorted(reference_patterns),
        ),
    ]

    return IndexConfig(
        index_name=project_name,
        root_path=str(root),
        tiers=tiers,
    )


def generate_config_yaml(config: IndexConfig) -> str:
    """Serialize an IndexConfig to YAML string.

    Args:
        config: The IndexConfig to serialize.

    Returns:
        YAML string representation of the config.
    """
    data = config.model_dump(mode="json")

    # Remove defaults that clutter the output
    _clean_defaults(data)

    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)


def _clean_defaults(data: dict) -> None:
    """Remove fields that match IndexConfig defaults to keep YAML concise.

    Mutates the dict in place.
    """
    # Remove empty or default fields that are just noise
    removable = []
    for key, value in data.items():
        if value == "" or value == [] or value == {}:
            removable.append(key)
    for key in removable:
        del data[key]


def _detect_project_name(root: Path) -> str:
    """Detect the project name from the project directory.

    Checks package.json and pyproject.toml for a name field,
    then falls back to the directory name.

    Args:
        root: Root directory of the project.

    Returns:
        Detected project name.
    """
    # Try package.json
    package_json = root / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            name = data.get("name")
            if name and isinstance(name, str):
                return name
        except (json.JSONDecodeError, OSError):
            pass

    # Try pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib

            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            name = data.get("project", {}).get("name")
            if name and isinstance(name, str):
                return name
        except (OSError, Exception):
            pass

    # Fall back to directory name
    return root.name or "Docs Index"


def _collect_doc_files(
    root: Path,
    extensions: set[str],
    ignore_dirs: set[str],
) -> list[str]:
    """Collect relative paths of documentation files under root.

    Args:
        root: Root directory to scan.
        extensions: File extensions to include.
        ignore_dirs: Directory names to skip.

    Returns:
        List of relative paths (using forward slashes).
    """
    results: list[str] = []

    if not root.exists() or not root.is_dir():
        return results

    for item in sorted(root.rglob("*")):
        # Skip ignored directories
        if any(part in ignore_dirs for part in item.parts):
            continue

        if item.is_file() and item.suffix.lower() in extensions:
            rel = item.relative_to(root).as_posix()
            results.append(rel)

    return results


def _classify_file(rel_path: str) -> str:
    """Classify a file path into a tier based on keyword heuristics.

    Args:
        rel_path: Relative path of the file (forward slashes).

    Returns:
        Tier name: "required", "reference", or "recommended".
    """
    # Normalize: lowercase, split into path parts and filename stem
    lower = rel_path.lower()
    parts = lower.replace("\\", "/").split("/")

    for part in parts:
        # Strip extension for matching
        stem = Path(part).stem

        if stem in _REQUIRED_KEYWORDS or any(kw in stem for kw in _REQUIRED_KEYWORDS):
            return "required"
        if stem in _REFERENCE_KEYWORDS or any(kw in stem for kw in _REFERENCE_KEYWORDS):
            return "reference"

    return "recommended"
