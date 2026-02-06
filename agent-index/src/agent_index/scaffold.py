"""Scaffold mode for generating a project directory structure.

Creates directories, placeholder .llms.md files, and an agent-index.yaml
config file based on an IndexConfig.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from agent_index.models import IndexConfig


def scaffold_project(root_path: Path, config: IndexConfig) -> list[Path]:
    """Create directory structure with placeholder files.

    Creates:
    - The root_path directory (if it doesn't exist)
    - Subdirectories for each tier
    - Placeholder .llms.md files per tier
    - agent-index.yaml config file

    Does NOT overwrite existing files.

    Args:
        root_path: Root directory where the scaffold should be created.
        config: IndexConfig describing the desired structure.

    Returns:
        List of paths that were created (directories and files).
    """
    root = Path(root_path)
    created: list[Path] = []

    # Create root directory
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
        created.append(root)

    # Create .docs subdirectory (the docs root)
    docs_dir = root / ".docs"
    if not docs_dir.exists():
        docs_dir.mkdir(parents=True, exist_ok=True)
        created.append(docs_dir)

    # Create tier subdirectories and placeholder files
    for tier in config.tiers:
        tier_dir = docs_dir / tier.name
        if not tier_dir.exists():
            tier_dir.mkdir(parents=True, exist_ok=True)
            created.append(tier_dir)

        # Create placeholder .llms.md file
        placeholder = tier_dir / f"{tier.name}.llms.md"
        if not placeholder.exists():
            content = (
                f"# {tier.name.capitalize()} Documentation\n"
                f"\n"
                f"{tier.instruction}\n"
                f"\n"
                f"<!-- Add your {tier.name} documentation files here -->\n"
            )
            placeholder.write_text(content, encoding="utf-8")
            created.append(placeholder)

    # Create agent-index.yaml config file
    config_file = root / "agent-index.yaml"
    if not config_file.exists():
        config_data = config.model_dump(mode="json")
        # Update root_path to point to the .docs directory
        config_data["root_path"] = "./.docs"
        # Clean up empty/default values for cleaner YAML
        _clean_for_yaml(config_data)
        yaml_content = yaml.dump(
            config_data,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
        config_file.write_text(yaml_content, encoding="utf-8")
        created.append(config_file)

    return created


def _clean_for_yaml(data: dict) -> None:
    """Remove empty or default fields from config data for cleaner YAML output.

    Mutates the dict in place.
    """
    removable = []
    for key, value in data.items():
        if value == "" or value == [] or value == {}:
            removable.append(key)
    for key in removable:
        del data[key]
