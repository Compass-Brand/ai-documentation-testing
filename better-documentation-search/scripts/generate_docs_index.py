#!/usr/bin/env python3
"""
generate_docs_index.py — Generate compressed AGENTS.md / CLAUDE.md documentation indexes.

Scans local directories and/or GitHub repositories to collect documentation file
listings, then outputs a compressed pipe-delimited index in the format pioneered
by Vercel's Next.js AGENTS.md approach. The resulting index can be embedded directly
into an AGENTS.md or CLAUDE.md file to give AI coding agents persistent, version-
matched documentation context.

Requires:  Python 3.14+
Optional:  PyYAML (pip install pyyaml) for YAML config files
           (JSON and TOML configs work with stdlib only)

Free-threading:
    When running on a free-threaded Python 3.14 build (python3.14t or
    PYTHON_GIL=0), all source scanning and GitHub API calls run with true
    thread-level parallelism — no GIL serialization. On standard builds,
    the same ThreadPoolExecutor code still provides I/O-bound concurrency
    which is beneficial for network calls.

Usage:
    # From a YAML config (recommended):
    python generate_docs_index.py --config sources.yaml

    # From a JSON config:
    python generate_docs_index.py --config sources.json

    # From a TOML config:
    python generate_docs_index.py --config sources.toml

    # Quick single local source (no config file needed):
    python generate_docs_index.py \\
        --local ./docs \\
        --name "My Framework Docs" \\
        --root ./.my-docs \\
        --extensions .md .mdx .rst \\
        --output my-docs-index.md

    # Inject into an existing AGENTS.md:
    python generate_docs_index.py --config sources.yaml --inject AGENTS.md

    # Expanded (human-readable) output:
    python generate_docs_index.py --config sources.yaml --expanded

Author:  Generated for Compass-Brand ai-enhancements project
License: MIT
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import textwrap
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Version & free-threading detection
# ---------------------------------------------------------------------------

MIN_PYTHON = (3, 14)

if sys.version_info < MIN_PYTHON:
    sys.exit(
        f"Error: Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required "
        f"(running {sys.version_info.major}.{sys.version_info.minor})."
    )

FREE_THREADED: bool = False
try:
    import sysconfig

    FREE_THREADED = bool(sysconfig.get_config_var("Py_GIL_DISABLED"))
except Exception:
    pass

# ---------------------------------------------------------------------------
# Optional config format support
# ---------------------------------------------------------------------------

_HAS_YAML = False
try:
    import yaml  # type: ignore[import-untyped]

    _HAS_YAML = True
except ImportError:
    pass

_HAS_TOML = False
try:
    import tomllib  # stdlib since 3.11

    _HAS_TOML = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log = logging.getLogger("docs-index")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

DEFAULT_EXTENSIONS: set[str] = {".md", ".mdx", ".rst", ".txt"}


@dataclass
class SourceLocal:
    """A local filesystem documentation source."""

    path: str
    strip_prefix: str = ""


@dataclass
class SourceGitHub:
    """A GitHub repository documentation source."""

    repo: str  # "owner/repo"
    branch: str = "main"
    path: str = "docs"
    token_env: str = ""  # env var name holding a GitHub token


@dataclass
class IndexConfig:
    """Full configuration for generating a docs index."""

    # Metadata
    index_name: str = "Docs Index"
    marker_id: str = "DOCS"
    root_path: str = "./.docs"
    instruction: str = (
        "Prefer retrieval-led reasoning over pre-training-led reasoning "
        "for any tasks related to this project."
    )
    fallback_command: str = ""

    # Sources
    local_sources: list[SourceLocal] = field(default_factory=list)
    github_sources: list[SourceGitHub] = field(default_factory=list)

    # Scanning options
    file_extensions: set[str] = field(default_factory=lambda: set(DEFAULT_EXTENSIONS))
    ignore_patterns: list[str] = field(
        default_factory=lambda: ["node_modules", "__pycache__", ".git", ".venv", "venv"]
    )

    # Output options
    output_file: str = ""
    inject_into: str = ""
    expanded: bool = False

    # Parallelism
    max_workers: int = 8


# ---------------------------------------------------------------------------
# Config loaders
# ---------------------------------------------------------------------------


def _parse_sources(raw: dict[str, Any]) -> tuple[list[SourceLocal], list[SourceGitHub]]:
    """Parse the 'sources' list from a config dict."""
    locals_: list[SourceLocal] = []
    githubs: list[SourceGitHub] = []
    for src in raw.get("sources", []):
        stype = src.get("type", "local")
        if stype == "local":
            locals_.append(
                SourceLocal(
                    path=src["path"],
                    strip_prefix=src.get("strip_prefix", ""),
                )
            )
        elif stype == "github":
            githubs.append(
                SourceGitHub(
                    repo=src["repo"],
                    branch=src.get("branch", "main"),
                    path=src.get("path", "docs"),
                    token_env=src.get("token_env", ""),
                )
            )
        else:
            log.warning("Unknown source type %r — skipping", stype)
    return locals_, githubs


def load_config(path: str) -> IndexConfig:
    """Load an IndexConfig from a YAML, JSON, or TOML file."""
    p = Path(path)
    suffix = p.suffix.lower()
    text = p.read_text(encoding="utf-8")

    if suffix in (".yaml", ".yml"):
        if not _HAS_YAML:
            sys.exit(
                "Error: PyYAML is required for .yaml configs. "
                "Install with: pip install pyyaml --break-system-packages"
            )
        raw: dict[str, Any] = yaml.safe_load(text)
    elif suffix == ".json":
        raw = json.loads(text)
    elif suffix == ".toml":
        if not _HAS_TOML:
            sys.exit("Error: tomllib not available (requires Python 3.11+).")
        raw = tomllib.loads(text)
    else:
        sys.exit(f"Error: Unsupported config format {suffix!r}. Use .yaml, .json, or .toml.")

    locals_, githubs = _parse_sources(raw)
    exts = raw.get("file_extensions", list(DEFAULT_EXTENSIONS))

    return IndexConfig(
        index_name=raw.get("index_name", "Docs Index"),
        marker_id=raw.get("marker_id", "DOCS"),
        root_path=raw.get("root_path", "./.docs"),
        instruction=raw.get(
            "instruction",
            "Prefer retrieval-led reasoning over pre-training-led reasoning "
            "for any tasks related to this project.",
        ),
        fallback_command=raw.get("fallback_command", ""),
        local_sources=locals_,
        github_sources=githubs,
        file_extensions=set(exts),
        ignore_patterns=raw.get(
            "ignore_patterns",
            ["node_modules", "__pycache__", ".git", ".venv", "venv"],
        ),
        output_file=raw.get("output_file", ""),
        inject_into=raw.get("inject_into", ""),
        expanded=raw.get("expanded", False),
        max_workers=raw.get("max_workers", 8),
    )


# ---------------------------------------------------------------------------
# Source scanners
# ---------------------------------------------------------------------------

# Type alias: mapping from directory path (str) to sorted list of filenames
DirIndex = dict[str, list[str]]


def scan_local(source: SourceLocal, config: IndexConfig) -> DirIndex:
    """Walk a local directory tree and collect documentation files by directory."""
    result: dict[str, list[str]] = defaultdict(list)
    root = Path(source.path).resolve()

    if not root.is_dir():
        log.error("Local source path does not exist: %s", root)
        return {}

    log.info("Scanning local source: %s", root)
    ignore = set(config.ignore_patterns)

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories (modifying dirnames in-place)
        dirnames[:] = [d for d in dirnames if d not in ignore and not d.startswith(".")]
        dirnames.sort()

        dp = Path(dirpath)
        rel = dp.relative_to(root)

        # Apply strip_prefix if configured
        rel_str = str(PurePosixPath(rel))
        if source.strip_prefix:
            prefix = source.strip_prefix.rstrip("/")
            if rel_str.startswith(prefix):
                rel_str = rel_str[len(prefix) :].lstrip("/")

        if rel_str == ".":
            rel_str = ""

        for fname in sorted(filenames):
            if Path(fname).suffix.lower() in config.file_extensions:
                result[rel_str].append(fname)

    return dict(result)


def scan_github(source: SourceGitHub, config: IndexConfig) -> DirIndex:
    """Fetch the file tree from a GitHub repo via the Trees API and collect docs."""
    result: dict[str, list[str]] = defaultdict(list)

    token = ""
    if source.token_env:
        token = os.environ.get(source.token_env, "")

    api_url = (
        f"https://api.github.com/repos/{source.repo}"
        f"/git/trees/{source.branch}?recursive=1"
    )

    log.info("Fetching GitHub tree: %s (branch: %s, path: %s)", source.repo, source.branch, source.path)

    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "docs-index-generator/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request(api_url, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        log.error("GitHub API error for %s: %s", source.repo, exc)
        return {}

    tree = data.get("tree", [])
    doc_prefix = source.path.strip("/")
    ignore = set(config.ignore_patterns)

    for item in tree:
        if item.get("type") != "blob":
            continue

        file_path = item["path"]  # e.g. "docs/01-app/getting-started/intro.mdx"

        # Must be under the configured docs path
        if not file_path.startswith(doc_prefix + "/") and file_path != doc_prefix:
            continue

        # Strip the docs prefix to get relative path
        rel_path = file_path[len(doc_prefix) :].lstrip("/")
        p = PurePosixPath(rel_path)

        # Check extension
        if p.suffix.lower() not in config.file_extensions:
            continue

        # Check ignore patterns
        if any(part in ignore for part in p.parts):
            continue

        dir_part = str(p.parent) if str(p.parent) != "." else ""
        result[dir_part].append(p.name)

    # Sort files within each directory
    for key in result:
        result[key].sort()

    return dict(result)


# ---------------------------------------------------------------------------
# Parallel scanning orchestrator
# ---------------------------------------------------------------------------


def scan_all_sources(config: IndexConfig) -> DirIndex:
    """
    Scan all configured sources in parallel using ThreadPoolExecutor.

    On free-threaded Python 3.14 (no-GIL), threads run with true parallelism.
    On standard builds, threads still provide I/O concurrency for network calls.
    """
    merged: dict[str, list[str]] = defaultdict(list)
    futures = []

    worker_count = config.max_workers
    if FREE_THREADED:
        log.info(
            "Free-threaded Python detected (GIL disabled) — using %d true parallel workers",
            worker_count,
        )
    else:
        log.info("Standard Python (GIL enabled) — using %d I/O-concurrent workers", worker_count)

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        for src in config.local_sources:
            futures.append(pool.submit(scan_local, src, config))
        for src in config.github_sources:
            futures.append(pool.submit(scan_github, src, config))

        for future in as_completed(futures):
            try:
                partial: DirIndex = future.result()
                for dir_path, files in partial.items():
                    merged[dir_path].extend(files)
            except Exception:
                log.exception("Source scan failed")

    # Deduplicate and sort
    final: DirIndex = {}
    for dir_path in sorted(merged.keys()):
        final[dir_path] = sorted(set(merged[dir_path]))

    return final


# ---------------------------------------------------------------------------
# Index formatting
# ---------------------------------------------------------------------------


def format_compressed(config: IndexConfig, index: DirIndex) -> str:
    """
    Produce the compressed single-line pipe-delimited index.

    Format:
        <!-- MARKER-START -->[Name]|root: path|IMPORTANT: ...|dir:{f1,f2}|...<!-- MARKER-END -->
    """
    parts: list[str] = []
    parts.append(f"<!-- {config.marker_id}-START -->")
    parts.append(f"[{config.index_name}]")
    parts.append(f"|root: {config.root_path}")
    parts.append(f"|IMPORTANT: {config.instruction}")

    if config.fallback_command:
        parts.append(f"|If docs missing run: {config.fallback_command}")

    for dir_path, files in index.items():
        files_str = ",".join(files)
        if dir_path:
            parts.append(f"|{dir_path}:{{{files_str}}}")
        else:
            # Root-level files
            parts.append(f"|.:{{{files_str}}}")

    parts.append(f"<!-- {config.marker_id}-END -->")
    return "".join(parts)


def format_expanded(config: IndexConfig, index: DirIndex) -> str:
    """
    Produce an expanded multi-line index (human-readable).

    Each section on its own line, indented for clarity.
    """
    lines: list[str] = []
    lines.append(f"<!-- {config.marker_id}-START -->")
    lines.append(f"[{config.index_name}]")
    lines.append(f"|root: {config.root_path}")
    lines.append(f"|IMPORTANT: {config.instruction}")

    if config.fallback_command:
        lines.append(f"|If docs missing run: {config.fallback_command}")

    lines.append("")  # blank separator

    for dir_path, files in index.items():
        files_str = ",".join(files)
        if dir_path:
            lines.append(f"|{dir_path}:{{{files_str}}}")
        else:
            lines.append(f"|.:{{{files_str}}}")

    lines.append(f"<!-- {config.marker_id}-END -->")
    return "\n".join(lines)


def format_index(config: IndexConfig, index: DirIndex) -> str:
    """Format the index according to the configured mode."""
    if config.expanded:
        return format_expanded(config, index)
    return format_compressed(config, index)


# ---------------------------------------------------------------------------
# Output / injection
# ---------------------------------------------------------------------------


def inject_into_file(content: str, target_path: str, marker_id: str) -> None:
    """
    Inject (or replace) the docs index block inside an existing file.

    Looks for <!-- MARKER-START --> ... <!-- MARKER-END --> boundaries.
    If found, replaces the content between them. If not found, appends
    the block to the end of the file.
    """
    target = Path(target_path)

    if target.exists():
        existing = target.read_text(encoding="utf-8")
    else:
        existing = ""

    start_marker = f"<!-- {marker_id}-START -->"
    end_marker = f"<!-- {marker_id}-END -->"
    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker),
        re.DOTALL,
    )

    if pattern.search(existing):
        updated = pattern.sub(content, existing)
        log.info("Replaced existing %s block in %s", marker_id, target_path)
    else:
        separator = "\n\n" if existing and not existing.endswith("\n\n") else "\n" if existing else ""
        updated = existing + separator + content + "\n"
        log.info("Appended %s block to %s", marker_id, target_path)

    target.write_text(updated, encoding="utf-8")


def write_output(content: str, config: IndexConfig) -> None:
    """Write the formatted index to file or stdout."""
    if config.inject_into:
        inject_into_file(content, config.inject_into, config.marker_id)
        return

    if config.output_file:
        Path(config.output_file).write_text(content + "\n", encoding="utf-8")
        log.info("Wrote index to %s", config.output_file)
    else:
        print(content)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


def print_stats(index: DirIndex) -> None:
    """Print summary statistics about the generated index."""
    total_dirs = len(index)
    total_files = sum(len(files) for files in index.values())
    extensions: dict[str, int] = defaultdict(int)
    for files in index.values():
        for f in files:
            ext = Path(f).suffix.lower()
            extensions[ext] += 1

    log.info("Index statistics:")
    log.info("  Directories:  %d", total_dirs)
    log.info("  Files:        %d", total_files)
    for ext, count in sorted(extensions.items(), key=lambda x: -x[1]):
        log.info("    %-10s  %d", ext, count)

    # Estimate compressed size
    compressed = "|".join(
        f"{d}:{{{','.join(files)}}}" for d, files in index.items()
    )
    size_kb = len(compressed.encode("utf-8")) / 1024
    log.info("  Est. index size: %.1f KB", size_kb)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_docs_index",
        description="Generate compressed AGENTS.md documentation indexes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              %(prog)s --config sources.yaml
              %(prog)s --config sources.yaml --output index.md
              %(prog)s --config sources.yaml --inject AGENTS.md
              %(prog)s --local ./docs --name "React Docs" --root ./.react-docs
              %(prog)s --github vercel/next.js --gh-branch canary --gh-path docs
        """),
    )

    # Config file mode
    parser.add_argument(
        "--config", "-c",
        metavar="FILE",
        help="Path to a YAML, JSON, or TOML configuration file.",
    )

    # Quick single-source mode (local)
    parser.add_argument(
        "--local", "-l",
        metavar="DIR",
        help="Scan a local directory (quick mode, no config file needed).",
    )

    # Quick single-source mode (GitHub)
    parser.add_argument(
        "--github", "-g",
        metavar="OWNER/REPO",
        help="Scan a GitHub repository (quick mode, e.g. 'vercel/next.js').",
    )
    parser.add_argument(
        "--gh-branch",
        default="main",
        help="GitHub branch to scan (default: main).",
    )
    parser.add_argument(
        "--gh-path",
        default="docs",
        help="Path within the GitHub repo to scan (default: docs).",
    )
    parser.add_argument(
        "--gh-token-env",
        default="GITHUB_TOKEN",
        help="Env var name for GitHub token (default: GITHUB_TOKEN).",
    )

    # Metadata overrides
    parser.add_argument(
        "--name", "-n",
        default="Docs Index",
        help="Index display name (default: 'Docs Index').",
    )
    parser.add_argument(
        "--marker",
        default="DOCS",
        help="HTML comment marker ID (default: DOCS).",
    )
    parser.add_argument(
        "--root",
        default="./.docs",
        help="Root path where doc files live relative to project (default: ./.docs).",
    )
    parser.add_argument(
        "--instruction",
        default="",
        help="Custom retrieval instruction (overrides config).",
    )
    parser.add_argument(
        "--fallback-cmd",
        default="",
        help="Command to run if docs are missing.",
    )
    parser.add_argument(
        "--extensions", "-e",
        nargs="+",
        default=None,
        help="File extensions to include (default: .md .mdx .rst .txt).",
    )

    # Output
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Output file path (default: stdout).",
    )
    parser.add_argument(
        "--inject", "-i",
        metavar="FILE",
        help="Inject/replace the index block inside an existing file (e.g. AGENTS.md).",
    )
    parser.add_argument(
        "--expanded",
        action="store_true",
        help="Output in expanded (multi-line) format instead of compressed.",
    )

    # Parallelism
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=8,
        help="Max parallel workers for scanning (default: 8).",
    )

    # Verbosity
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging.",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress all output except the index itself.",
    )

    return parser


def config_from_args(args: argparse.Namespace) -> IndexConfig:
    """Build an IndexConfig from CLI arguments (quick mode)."""
    sources_local: list[SourceLocal] = []
    sources_github: list[SourceGitHub] = []

    if args.local:
        sources_local.append(SourceLocal(path=args.local))

    if args.github:
        sources_github.append(
            SourceGitHub(
                repo=args.github,
                branch=args.gh_branch,
                path=args.gh_path,
                token_env=args.gh_token_env,
            )
        )

    exts = set(args.extensions) if args.extensions else set(DEFAULT_EXTENSIONS)

    return IndexConfig(
        index_name=args.name,
        marker_id=args.marker,
        root_path=args.root,
        instruction=args.instruction
        or (
            "Prefer retrieval-led reasoning over pre-training-led reasoning "
            "for any tasks related to this project."
        ),
        fallback_command=args.fallback_cmd,
        local_sources=sources_local,
        github_sources=sources_github,
        file_extensions=exts,
        output_file=args.output or "",
        inject_into=args.inject or "",
        expanded=args.expanded,
        max_workers=args.workers,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Logging setup
    if args.quiet:
        logging.basicConfig(level=logging.ERROR)
    elif args.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(levelname)-8s %(message)s",
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)-8s %(message)s",
        )

    # Announce runtime info
    log.info(
        "Python %s | Free-threaded: %s",
        sys.version.split()[0],
        "YES" if FREE_THREADED else "no",
    )

    # Build config
    if args.config:
        config = load_config(args.config)
        # CLI overrides
        if args.output:
            config.output_file = args.output
        if args.inject:
            config.inject_into = args.inject
        if args.expanded:
            config.expanded = True
        if args.instruction:
            config.instruction = args.instruction
        if args.extensions:
            config.file_extensions = set(args.extensions)
        if args.workers != 8:
            config.max_workers = args.workers
    elif args.local or args.github:
        config = config_from_args(args)
    else:
        parser.print_help()
        return 1

    # Validate we have at least one source
    if not config.local_sources and not config.github_sources:
        log.error("No sources configured. Provide --local, --github, or a config file with sources.")
        return 1

    # Scan
    index = scan_all_sources(config)

    if not index:
        log.error("No documentation files found across all sources.")
        return 1

    # Stats
    print_stats(index)

    # Format
    output = format_index(config, index)

    # Write
    write_output(output, config)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
