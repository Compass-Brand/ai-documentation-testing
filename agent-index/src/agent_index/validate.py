"""CI validation mode for drift detection.

Compares the generated index against actual documentation files on disk
to detect missing files, extra files, and stale (changed) entries.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from agent_index.models import DocTree
from agent_index.scanner import DEFAULT_FILE_EXTENSIONS, DEFAULT_IGNORE_PATTERNS


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
    root_path: Path,
    *,
    file_extensions: set[str] | None = None,
    ignore_patterns: list[str] | None = None,
) -> ValidationResult:
    """Compare generated index against actual docs on disk.

    Checks for:
    1. Missing files: referenced in doc_tree but not on disk
    2. Extra files: on disk but not in doc_tree
    3. Stale entries: content hash changed since doc_tree was built

    Args:
        doc_tree: The DocTree from a previous scan.
        root_path: The root directory where docs should exist on disk.
        file_extensions: File extensions to include. Defaults to DEFAULT_FILE_EXTENSIONS.
        ignore_patterns: Directory names to skip. Defaults to DEFAULT_IGNORE_PATTERNS.

    Returns:
        ValidationResult with lists of any detected issues.
    """
    root = Path(root_path)
    result = ValidationResult()

    # Get the set of paths in the doc_tree
    indexed_paths = set(doc_tree.files.keys())

    # Get the set of actual doc files on disk
    disk_paths = _collect_disk_files(
        root,
        file_extensions=file_extensions,
        ignore_patterns=ignore_patterns,
    )

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


def _collect_disk_files(
    root: Path,
    *,
    file_extensions: set[str] | None = None,
    ignore_patterns: list[str] | None = None,
) -> set[str]:
    """Collect relative paths of doc files currently on disk.

    Args:
        root: Root directory to scan.
        file_extensions: File extensions to include. Defaults to DEFAULT_FILE_EXTENSIONS.
        ignore_patterns: Directory names to skip. Defaults to DEFAULT_IGNORE_PATTERNS.

    Returns:
        Set of relative paths (forward slashes).
    """
    extensions = file_extensions if file_extensions is not None else DEFAULT_FILE_EXTENSIONS
    ignore_dirs = set(ignore_patterns) if ignore_patterns is not None else set(DEFAULT_IGNORE_PATTERNS)
    results: set[str] = set()

    if not root.exists() or not root.is_dir():
        return results

    visited_dirs: set[str] = set()
    _walk_disk_files(root, root, extensions, ignore_dirs, results, visited_dirs)

    return results


def _walk_disk_files(
    current: Path,
    root: Path,
    extensions: set[str],
    ignore_dirs: set[str],
    results: set[str],
    visited_dirs: set[str],
) -> None:
    """Recursively walk directories with symlink loop protection.

    Args:
        current: Current directory being walked.
        root: Root directory for computing relative paths.
        extensions: File extensions to include.
        ignore_dirs: Directory names to skip.
        results: Set to populate with relative paths.
        visited_dirs: Set of resolved real paths already visited.
    """
    try:
        real_path = str(current.resolve())
    except OSError:
        return

    if real_path in visited_dirs:
        return
    visited_dirs.add(real_path)

    try:
        entries = list(current.iterdir())
    except (PermissionError, OSError):
        return

    for item in entries:
        rel_parts = item.relative_to(root).parts
        if any(part in ignore_dirs for part in rel_parts):
            continue

        if item.is_symlink():
            try:
                target = item.resolve()
                if not target.exists():
                    continue
                if target.is_dir():
                    # Follow symlinked directories with loop protection
                    _walk_disk_files(item, root, extensions, ignore_dirs, results, visited_dirs)
                    continue
                # Symlink to file
                if item.suffix.lower() in extensions:
                    rel = item.relative_to(root).as_posix()
                    results.add(rel)
            except OSError:
                continue
        elif item.is_dir():
            _walk_disk_files(item, root, extensions, ignore_dirs, results, visited_dirs)
        elif item.is_file() and item.suffix.lower() in extensions:
            rel = item.relative_to(root).as_posix()
            results.add(rel)


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
