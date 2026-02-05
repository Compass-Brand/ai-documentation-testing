"""Local file scanner for documentation discovery.

Scans directories recursively to find documentation files,
producing a DocTree with metadata and content hashes for
incremental processing.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from agent_index.models import DocFile, DocTree

# Default file extensions for documentation files
DEFAULT_FILE_EXTENSIONS: set[str] = {".md", ".mdx", ".rst", ".txt"}

# Default patterns to ignore during scanning
DEFAULT_IGNORE_PATTERNS: list[str] = ["node_modules", "__pycache__", ".git", ".venv"]


def scan_local(
    root_path: Path | str,
    *,
    file_extensions: set[str] | None = None,
    ignore_patterns: list[str] | None = None,
) -> DocTree:
    """Scan a local directory for documentation files.

    Walks the directory tree recursively, filtering by file extensions
    and ignore patterns. Computes content hashes for incremental processing.

    Args:
        root_path: Directory to scan.
        file_extensions: File extensions to include (default: .md, .mdx, .rst, .txt).
        ignore_patterns: Path patterns to ignore (default: node_modules, __pycache__, .git, .venv).

    Returns:
        DocTree with all matching files.

    Raises:
        FileNotFoundError: If root_path doesn't exist.
        NotADirectoryError: If root_path is not a directory.
    """
    root = Path(root_path)

    # Validate root path
    if not root.exists():
        raise FileNotFoundError(f"Directory not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {root}")

    # Apply defaults
    extensions = file_extensions if file_extensions is not None else DEFAULT_FILE_EXTENSIONS
    ignores = ignore_patterns if ignore_patterns is not None else DEFAULT_IGNORE_PATTERNS

    # Normalize extensions to lowercase for case-insensitive matching
    extensions_lower = {ext.lower() for ext in extensions}

    # Collect files
    files: dict[str, DocFile] = {}
    _scan_directory(root, root, extensions_lower, ignores, files, visited_dirs=set())

    return DocTree(
        files=files,
        scanned_at=datetime.now(UTC),
        source=str(root),
    )


def _scan_directory(
    current: Path,
    root: Path,
    extensions: set[str],
    ignore_patterns: list[str],
    files: dict[str, DocFile],
    visited_dirs: set[Path],
) -> None:
    """Recursively scan a directory for documentation files.

    Args:
        current: Current directory being scanned.
        root: Root directory (for computing relative paths).
        extensions: Lowercase file extensions to include.
        ignore_patterns: Path patterns to ignore.
        files: Dictionary to populate with found files.
        visited_dirs: Set of real paths already visited (for loop detection).
    """
    # Resolve to real path for loop detection
    try:
        real_current = current.resolve()
    except OSError:
        # Cannot resolve path, skip
        return

    # Check for directory loops
    if real_current in visited_dirs:
        return
    visited_dirs.add(real_current)

    try:
        entries = list(current.iterdir())
    except PermissionError:
        # Cannot read directory, skip
        return

    for entry in entries:
        # Check if path matches any ignore pattern
        if _should_ignore(entry, root, ignore_patterns):
            continue

        if entry.is_symlink():
            # Handle symlinks: follow to files only, skip directory symlinks
            try:
                target = entry.resolve()
                if not target.exists():
                    # Broken symlink
                    continue
                if target.is_dir():
                    # Skip symlinks to directories
                    continue
                # Symlink to file - process it
                if _matches_extension(entry, extensions):
                    doc = _create_docfile(entry, root)
                    if doc is not None:
                        files[doc.rel_path] = doc
            except OSError:
                # Cannot resolve symlink, skip
                continue
        elif entry.is_dir():
            # Recurse into subdirectory
            _scan_directory(entry, root, extensions, ignore_patterns, files, visited_dirs)
        elif entry.is_file():
            # Check extension and process file
            if _matches_extension(entry, extensions):
                doc = _create_docfile(entry, root)
                if doc is not None:
                    files[doc.rel_path] = doc


def _should_ignore(path: Path, root: Path, ignore_patterns: list[str]) -> bool:
    """Check if a path should be ignored based on patterns.

    A path is ignored if any component of its relative path matches
    any of the ignore patterns.

    Args:
        path: Path to check.
        root: Root directory for computing relative path.
        ignore_patterns: Patterns to match against path components.

    Returns:
        True if the path should be ignored.
    """
    if not ignore_patterns:
        return False

    try:
        rel_path = path.relative_to(root)
    except ValueError:
        return False

    # Check each path component against ignore patterns
    for part in rel_path.parts:
        if part in ignore_patterns:
            return True

    return False


def _matches_extension(path: Path, extensions: set[str]) -> bool:
    """Check if a file has a matching extension (case-insensitive).

    Args:
        path: File path to check.
        extensions: Set of lowercase extensions including the dot.

    Returns:
        True if the file extension matches.
    """
    return path.suffix.lower() in extensions


def _create_docfile(path: Path, root: Path) -> DocFile | None:
    """Create a DocFile from a file path.

    Args:
        path: Path to the file.
        root: Root directory for computing relative path.

    Returns:
        DocFile instance, or None if the file cannot be read.
    """
    try:
        content = path.read_text(encoding="utf-8")
        stat = path.stat()

        # Compute relative path with forward slashes for consistency
        rel_path = path.relative_to(root).as_posix()

        # Compute SHA-256 hash of content
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Get last modified time as timezone-aware datetime
        last_modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC)

        return DocFile(
            rel_path=rel_path,
            content=content,
            size_bytes=stat.st_size,
            tier="",  # Assigned later by tier system
            section="",  # Assigned later by tier system
            content_hash=content_hash,
            last_modified=last_modified,
        )
    except (OSError, UnicodeDecodeError):
        # Cannot read file or decode content, skip
        return None
