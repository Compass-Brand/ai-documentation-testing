"""Command-line interface for agent-index.

Usage:
    agent-index --local ./docs --name "My Project"
    agent-index --config agent-index.yaml
    agent-index --local ./docs --output AGENTS.md
    agent-index --local ./docs --inject README.md --marker-id DOCS
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from agent_index.config import ConfigError, find_config, load_config
from agent_index.models import IndexConfig
from agent_index.output import inject_into_file, render_index
from agent_index.scanner import scan_local
from agent_index.tiers import assign_tiers, sort_files_bluf

if TYPE_CHECKING:
    from argparse import Namespace


def parse_args(argv: list[str] | None = None) -> Namespace:
    """Parse command-line arguments.

    Args:
        argv: Command-line arguments. Defaults to sys.argv[1:].

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="agent-index",
        description="Generate AI-optimized documentation indexes.",
        add_help=False,
    )

    parser.add_argument(
        "--local",
        metavar="PATH",
        help="Directory to scan for docs",
    )
    parser.add_argument(
        "--name",
        metavar="TEXT",
        help="Project/index name",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        help="Config file path (optional, auto-detected)",
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--inject",
        metavar="PATH",
        help="Inject into existing file using markers",
    )
    parser.add_argument(
        "--marker-id",
        metavar="TEXT",
        default="DOCS",
        help="Marker ID for injection (default: DOCS)",
    )
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help="Show this help message",
    )

    return parser.parse_args(argv)


def run(args: Namespace) -> int:
    """Execute the CLI workflow.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Exit code: 0 for success, 1 for error.
    """
    config: IndexConfig

    # Step 1: Determine configuration source
    if args.config:
        # Load specified config file
        try:
            config = load_config(Path(args.config))
        except ConfigError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    elif args.local:
        # Use defaults with --local path
        config = IndexConfig(
            index_name=args.name or "Docs Index",
            root_path=args.local,
        )
    else:
        # Try to auto-detect config file
        detected_config = find_config()
        if detected_config is None:
            print(
                "Error: No config file found and no --local flag provided.\n"
                "Use --local <path> to scan a directory or --config <path> to specify a config file.",
                file=sys.stderr,
            )
            return 1
        try:
            config = load_config(detected_config)
        except ConfigError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Step 2: Determine the root path to scan
    scan_path = Path(args.local) if args.local else Path.cwd() / config.root_path

    # Step 3: Scan the docs
    try:
        doc_tree = scan_local(
            scan_path,
            file_extensions=config.file_extensions,
            ignore_patterns=config.ignore_patterns,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except NotADirectoryError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Step 4: Assign tiers
    doc_tree = assign_tiers(doc_tree, config.tiers)

    # Step 5: Sort BLUF
    sorted_files = sort_files_bluf(list(doc_tree.files.values()), config.tiers)

    # Step 6: Render index
    index_content = render_index(
        sorted_files,
        config.tiers,
        instruction=config.instruction,
    )

    # Step 7: Output
    if args.output:
        # Write to file
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(index_content, encoding="utf-8")
    elif args.inject:
        # Inject into existing file
        inject_path = Path(args.inject)
        inject_into_file(inject_path, index_content, marker_id=args.marker_id)
    else:
        # Print to stdout
        print(index_content, end="")

    return 0


def main() -> int:
    """Main entry point for the CLI.

    Returns:
        Exit code: 0 for success, 1 for error.
    """
    args = parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
