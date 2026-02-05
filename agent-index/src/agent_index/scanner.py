"""Documentation scanner for local and GitHub sources.

Scans directories recursively to find documentation files,
producing a DocTree with metadata and content hashes for
incremental processing.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx

from agent_index.models import DocFile, DocTree


class GitHubError(Exception):
    """Error from GitHub API.

    Attributes:
        status_code: HTTP status code from the API response, if available.
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code

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
        elif entry.is_file() and _matches_extension(entry, extensions):
            # Process file with matching extension
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
    return any(part in ignore_patterns for part in rel_path.parts)


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


# --- GitHub Scanner ---

# Default cache directory for GitHub content
DEFAULT_GITHUB_CACHE_DIR = Path.home() / ".cache" / "agent-index" / "github"


def scan_github(
    repo: str,
    *,
    path: str = "",
    branch: str = "main",
    file_extensions: set[str] | None = None,
    ignore_patterns: list[str] | None = None,
    cache_dir: Path | None = None,
) -> DocTree:
    """Scan a GitHub repository for documentation files.

    Args:
        repo: Repository in "owner/repo" format.
        path: Subdirectory to scan (default: root).
        branch: Branch to scan (default: main).
        file_extensions: File extensions to include.
        ignore_patterns: Path patterns to ignore.
        cache_dir: Directory to cache fetched content (default: ~/.cache/agent-index).

    Returns:
        DocTree with all matching files.

    Raises:
        ValueError: If repo format is invalid.
        GitHubError: If API request fails (rate limit, not found, etc.).
    """
    # Validate repo format
    _validate_repo_format(repo)

    # Apply defaults
    extensions = file_extensions if file_extensions is not None else DEFAULT_FILE_EXTENSIONS
    ignores = ignore_patterns if ignore_patterns is not None else DEFAULT_IGNORE_PATTERNS
    cache_path = cache_dir if cache_dir is not None else DEFAULT_GITHUB_CACHE_DIR

    # Normalize extensions to lowercase for case-insensitive matching
    extensions_lower = {ext.lower() for ext in extensions}

    # Ensure cache directory exists
    cache_path.mkdir(parents=True, exist_ok=True)

    # Collect files
    files: dict[str, DocFile] = {}
    _scan_github_directory(
        repo=repo,
        path=path,
        branch=branch,
        extensions=extensions_lower,
        ignore_patterns=ignores,
        files=files,
        cache_dir=cache_path,
    )

    return DocTree(
        files=files,
        scanned_at=datetime.now(UTC),
        source=f"github:{repo}",
    )


def _validate_repo_format(repo: str) -> None:
    """Validate the repository format.

    Args:
        repo: Repository string to validate.

    Raises:
        ValueError: If format is invalid.
    """
    parts = repo.split("/")
    if len(parts) != 2:
        raise ValueError(
            f"Invalid repo format: '{repo}'. Expected 'owner/repo' format."
        )
    owner, repo_name = parts
    if not owner or not repo_name:
        raise ValueError(
            f"Invalid repo format: '{repo}'. Both owner and repo name must be non-empty."
        )


def _scan_github_directory(
    repo: str,
    path: str,
    branch: str,
    extensions: set[str],
    ignore_patterns: list[str],
    files: dict[str, DocFile],
    cache_dir: Path,
) -> None:
    """Recursively scan a GitHub directory for documentation files.

    Args:
        repo: Repository in "owner/repo" format.
        path: Current path within the repository.
        branch: Branch to scan.
        extensions: Lowercase file extensions to include.
        ignore_patterns: Path patterns to ignore.
        files: Dictionary to populate with found files.
        cache_dir: Directory to cache fetched content.
    """
    # Build API URL
    owner, repo_name = repo.split("/")
    if path:
        url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{path}?ref={branch}"
    else:
        url = f"https://api.github.com/repos/{owner}/{repo_name}/contents?ref={branch}"

    # Fetch directory listing
    response = _github_api_get(url)

    # Handle errors
    if response.status_code == 404:
        raise GitHubError(
            f"Repository or path not found: {repo}/{path}",
            status_code=404,
        )
    if response.status_code == 403:
        reset_time = response.headers.get("X-RateLimit-Reset")
        if reset_time:
            raise GitHubError(
                f"GitHub API rate limit exceeded. Resets at timestamp {reset_time}.",
                status_code=403,
            )
        raise GitHubError("GitHub API access forbidden.", status_code=403)
    if response.status_code != 200:
        raise GitHubError(
            f"GitHub API error: {response.status_code}",
            status_code=response.status_code,
        )

    # Parse response
    items = response.json()

    for item in items:
        item_name = item["name"]
        item_path = item["path"]
        item_type = item["type"]

        # Check ignore patterns
        if _should_ignore_github_path(item_path, ignore_patterns):
            continue

        if item_type == "dir":
            # Recurse into subdirectory
            _scan_github_directory(
                repo=repo,
                path=item_path,
                branch=branch,
                extensions=extensions,
                ignore_patterns=ignore_patterns,
                files=files,
                cache_dir=cache_dir,
            )
        elif item_type == "file":
            # Check extension
            suffix = Path(item_name).suffix.lower()
            if suffix not in extensions:
                continue

            # Fetch file content (with caching)
            file_sha = item.get("sha", "")
            content = _get_cached_content(
                repo=repo,
                branch=branch,
                path=item_path,
                sha=file_sha,
                cache_dir=cache_dir,
            )

            if content is not None:
                # Compute content hash
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

                doc = DocFile(
                    rel_path=item_path,
                    content=content,
                    size_bytes=len(content.encode("utf-8")),
                    tier="",
                    section="",
                    content_hash=content_hash,
                    last_modified=None,  # GitHub API doesn't provide this easily
                )
                files[doc.rel_path] = doc


def _should_ignore_github_path(path: str, ignore_patterns: list[str]) -> bool:
    """Check if a GitHub path should be ignored.

    Args:
        path: Path within the repository.
        ignore_patterns: Patterns to match against path components.

    Returns:
        True if the path should be ignored.
    """
    if not ignore_patterns:
        return False

    # Split path into components
    parts = path.split("/")
    return any(part in ignore_patterns for part in parts)


def _get_cached_content(
    repo: str,
    branch: str,
    path: str,
    sha: str,
    cache_dir: Path,
) -> str | None:
    """Get file content from cache or fetch from GitHub.

    Args:
        repo: Repository in "owner/repo" format.
        branch: Branch name.
        path: File path within the repository.
        sha: Git SHA of the file (for cache invalidation).
        cache_dir: Directory to store cached content.

    Returns:
        File content as string, or None if fetch fails.
    """
    # Build cache file path
    safe_repo = repo.replace("/", "_")
    safe_path = path.replace("/", "_")
    cache_file = cache_dir / safe_repo / branch / f"{safe_path}.cache"
    meta_file = cache_dir / safe_repo / branch / f"{safe_path}.meta"

    # Check cache
    if cache_file.exists() and meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            if meta.get("sha") == sha:
                # Cache hit
                return cache_file.read_text(encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            pass

    # Cache miss - fetch content
    content = _fetch_file_content(repo, branch, path)
    if content is None:
        return None

    # Save to cache
    try:
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(content, encoding="utf-8")
        meta_file.write_text(json.dumps({"sha": sha}), encoding="utf-8")
    except OSError:
        # Cache write failed, but we still have the content
        pass

    return content


def _fetch_file_content(repo: str, branch: str, path: str) -> str | None:
    """Fetch file content from GitHub raw URL.

    Args:
        repo: Repository in "owner/repo" format.
        branch: Branch name.
        path: File path within the repository.

    Returns:
        File content as string, or None if fetch fails.
    """
    owner, repo_name = repo.split("/")
    url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/{path}"

    try:
        with httpx.Client() as client:
            response = client.get(url, follow_redirects=True)
            if response.status_code == 200:
                return response.text
    except httpx.HTTPError:
        pass

    return None


def _github_api_get(url: str) -> httpx.Response:
    """Make a GET request to the GitHub API.

    Args:
        url: URL to fetch.

    Returns:
        HTTP response object.
    """
    with httpx.Client() as client:
        response = client.get(
            url,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "agent-index/0.1.0",
            },
            follow_redirects=True,
        )
    return response
