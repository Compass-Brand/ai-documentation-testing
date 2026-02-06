"""CI validation mode for drift detection.

Compares the generated index against actual documentation files on disk
to detect missing files, extra files, and stale (changed) entries.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from agent_index.models import DocTree


@dataclass
class ValidationResult:
    """Result of validating an index against actual docs on disk.

    Attributes:
        valid: True if no issues found (no missing, extra, or stale files).
        missing_files: Files referenced in the index but not found on disk.
        extra_files: Files found on disk but not referenced in the index.
        stale_entries: Files whose content hash has changed since the index was generated.
    """

    valid: bool = True
    missing_files: list[str] = field(default_factory=list)
    extra_files: list[str] = field(default_factory=list)
    stale_entries: list[str] = field(default_factory=list)


def validate_index(
    doc_tree: DocTree,
    index_content: str,
    root_path: Path,
) -> ValidationResult:
    """Compare generated index against actual docs on disk.

    Checks for:
    1. Missing files: referenced in doc_tree but not on disk
    2. Extra files: on disk but not in doc_tree
    3. Stale entries: content hash changed since doc_tree was built

    Args:
        doc_tree: The DocTree from a previous scan.
        index_content: The rendered index content (used to extract referenced paths).
        root_path: The root directory where docs should exist on disk.

    Returns:
        ValidationResult with lists of any detected issues.
    """
    root = Path(root_path)
    result = ValidationResult()

    # Get the set of paths in the doc_tree
    indexed_paths = set(doc_tree.files.keys())

    # Get the set of actual doc files on disk
    disk_paths = _collect_disk_files(root)

    # Check for missing files (in index but not on disk)
    for rel_path in sorted(indexed_paths):
        full_path = root / rel_path
        if not full_path.exists():
            result.missing_files.append(rel_path)

    # Check for extra files (on disk but not in index)
    for rel_path in sorted(disk_paths):
        if rel_path not in indexed_paths:
            result.extra_files.append(rel_path)

    # Check for stale entries (hash mismatch)
    for rel_path, doc_file in doc_tree.files.items():
        full_path = root / rel_path
        if full_path.exists() and doc_file.content_hash:
            current_hash = _compute_file_hash(full_path)
            if current_hash and current_hash != doc_file.content_hash:
                result.stale_entries.append(rel_path)

    # Set valid flag
    result.valid = (
        len(result.missing_files) == 0
        and len(result.extra_files) == 0
        and len(result.stale_entries) == 0
    )

    return result


def _collect_disk_files(root: Path) -> set[str]:
    """Collect relative paths of doc files currently on disk.

    Args:
        root: Root directory to scan.

    Returns:
        Set of relative paths (forward slashes).
    """
    extensions = {".md", ".mdx", ".rst", ".txt"}
    ignore_dirs = {"node_modules", "__pycache__", ".git", ".venv"}
    results: set[str] = set()

    if not root.exists() or not root.is_dir():
        return results

    for item in root.rglob("*"):
        if any(part in ignore_dirs for part in item.parts):
            continue
        if item.is_file() and item.suffix.lower() in extensions:
            rel = item.relative_to(root).as_posix()
            results.add(rel)

    return results


def _compute_file_hash(path: Path) -> str | None:
    """Compute SHA-256 hash of a file's content.

    Args:
        path: Path to the file.

    Returns:
        Hex digest string, or None if file cannot be read.
    """
    try:
        content = path.read_text(encoding="utf-8")
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
    except (OSError, UnicodeDecodeError):
        return None
