"""Output formatter for generating AGENTS.md index files.

This module handles:
- Rendering a BLUF-ordered markdown index from DocFiles
- Injecting generated content into existing files via markers
"""

from __future__ import annotations

from pathlib import Path

from agent_index.models import DocFile, TierConfig
from agent_index.tiers import group_by_section, sort_files_bluf

DEFAULT_INSTRUCTION = "Prefer retrieval-led reasoning over pre-training-led reasoning."


def render_index(
    files: list[DocFile],
    tier_configs: list[TierConfig],
    *,
    instruction: str = DEFAULT_INSTRUCTION,
) -> str:
    """Render a BLUF-ordered markdown index.

    Args:
        files: List of DocFiles (should already have tier/section assigned)
        tier_configs: Tier configurations (for tier order and instructions)
        instruction: Critical instruction to place at top and bottom

    Returns:
        Markdown string for AGENTS.md
    """
    lines: list[str] = []

    # Top instruction bookend
    lines.append(f"IMPORTANT: {instruction}")
    lines.append("")

    # Sort files in BLUF order
    sorted_files = sort_files_bluf(files, tier_configs)

    # Group files by tier
    files_by_tier: dict[str, list[DocFile]] = {}
    for doc in sorted_files:
        if doc.tier not in files_by_tier:
            files_by_tier[doc.tier] = []
        files_by_tier[doc.tier].append(doc)

    # Render each tier in config order
    for tier_config in tier_configs:
        tier_files = files_by_tier.get(tier_config.name, [])
        if not tier_files:
            continue

        # Tier header: ## TierName [instruction]
        tier_name_capitalized = tier_config.name.capitalize()
        lines.append(f"## {tier_name_capitalized} [{tier_config.instruction}]")
        lines.append("")

        # Group by section within tier
        section_groups = group_by_section(tier_files)

        # Render files without section first (empty string section)
        if "" in section_groups:
            for doc in section_groups[""]:
                lines.append(doc.rel_path)
            lines.append("")

        # Render sectioned files
        for section_name, section_files in section_groups.items():
            if section_name == "":
                continue  # Already rendered above

            # Section header: ### SectionName
            section_capitalized = section_name.capitalize()
            lines.append(f"### {section_capitalized}")
            for doc in section_files:
                lines.append(doc.rel_path)
            lines.append("")

    # Bottom instruction bookend
    lines.append(f"IMPORTANT: {instruction}")

    return "\n".join(lines) + "\n"


def inject_into_file(
    target_path: Path,
    content: str,
    marker_id: str = "DOCS",
) -> None:
    """Inject content into a file between markers.

    Markers are HTML comments: <!-- MARKER_ID:START --> and <!-- MARKER_ID:END -->
    If markers don't exist, appends content to end of file.
    If file doesn't exist, creates it with just the content.

    Args:
        target_path: Path to file to inject into
        content: Content to inject
        marker_id: ID for markers (creates MARKER_ID:START and MARKER_ID:END)
    """
    start_marker = f"<!-- {marker_id}:START -->"
    end_marker = f"<!-- {marker_id}:END -->"

    # Create parent directories if needed
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # If file doesn't exist, create with just content
    if not target_path.exists():
        target_path.write_text(content)
        return

    # Read existing content
    existing = target_path.read_text()

    # Find markers
    start_pos = existing.find(start_marker)
    end_pos = existing.find(end_marker)

    # Both markers must exist for replacement
    if start_pos == -1 or end_pos == -1 or end_pos <= start_pos:
        # Append to end if markers don't exist or are incomplete
        if existing and not existing.endswith("\n"):
            existing += "\n"
        new_content = existing + content
        target_path.write_text(new_content)
        return

    # Replace content between markers (keeping markers)
    before = existing[: start_pos + len(start_marker)]
    after = existing[end_pos:]

    new_content = f"{before}\n{content}\n{after}"
    target_path.write_text(new_content)
