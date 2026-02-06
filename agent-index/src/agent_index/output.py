"""Output formatter for generating documentation indexes across tool formats.

This module handles:
- Rendering a BLUF-ordered markdown index from DocFiles (AGENTS.md)
- Rendering Claude Code-specific CLAUDE.md format
- Rendering Cursor Rules .mdc files
- Rendering GitHub Copilot instructions format
- Dispatching to the correct renderer based on output target
- Injecting generated content into existing files via markers
"""

from __future__ import annotations

from pathlib import Path

from agent_index.models import DocFile, TierConfig
from agent_index.tiers import group_by_section, sort_files_bluf

DEFAULT_INSTRUCTION = "Prefer retrieval-led reasoning over pre-training-led reasoning."


def _group_files_by_tier(
    files: list[DocFile],
    tier_configs: list[TierConfig],
) -> dict[str, list[DocFile]]:
    """Sort files in BLUF order and group them by tier.

    Args:
        files: List of DocFiles (should already have tier/section assigned)
        tier_configs: Tier configurations (for tier order and instructions)

    Returns:
        Dict mapping tier names to their files, in BLUF order
    """
    sorted_files = sort_files_bluf(files, tier_configs)

    files_by_tier: dict[str, list[DocFile]] = {}
    for doc in sorted_files:
        if doc.tier not in files_by_tier:
            files_by_tier[doc.tier] = []
        files_by_tier[doc.tier].append(doc)

    return files_by_tier


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

    files_by_tier = _group_files_by_tier(files, tier_configs)

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


def render_claude_md(
    files: list[DocFile],
    tier_configs: list[TierConfig],
    instruction: str = DEFAULT_INSTRUCTION,
) -> str:
    """Render a Claude Code-specific CLAUDE.md format.

    Uses CLAUDE.md conventions: starts with project context, lists files
    grouped by tier with "Read these files" / "Consult these files" language
    appropriate for Claude.

    Args:
        files: List of DocFiles (should already have tier/section assigned)
        tier_configs: Tier configurations (for tier order and instructions)
        instruction: Project-level instruction for Claude

    Returns:
        Markdown string for CLAUDE.md
    """
    lines: list[str] = []

    # Project context header
    lines.append("# Project Documentation")
    lines.append("")
    lines.append(instruction)
    lines.append("")

    files_by_tier = _group_files_by_tier(files, tier_configs)

    # Map tier names to Claude-appropriate language
    _claude_verbs: dict[str, str] = {
        "required": "Read these files at the start of every task.",
        "recommended": "Read these files when working on related areas.",
        "reference": "Consult these files when you need specific details.",
    }

    for tier_config in tier_configs:
        tier_files = files_by_tier.get(tier_config.name, [])
        if not tier_files:
            continue

        tier_name_capitalized = tier_config.name.capitalize()
        verb = _claude_verbs.get(
            tier_config.name,
            tier_config.instruction,
        )

        lines.append(f"## {tier_name_capitalized}")
        lines.append("")
        lines.append(verb)
        lines.append("")

        for doc in tier_files:
            lines.append(f"- `{doc.rel_path}`")
        lines.append("")

    return "\n".join(lines) + "\n"


def render_cursor_rules(
    files: list[DocFile],
    tier_configs: list[TierConfig],
) -> dict[str, str]:
    """Render Cursor Rules .mdc files for .cursor/rules/ directory.

    Each non-empty tier gets its own .mdc file with YAML frontmatter
    containing description and globs fields.

    Args:
        files: List of DocFiles (should already have tier/section assigned)
        tier_configs: Tier configurations (for tier order and instructions)

    Returns:
        Dict mapping rule filenames (e.g. "required-docs.mdc") to their content
    """
    files_by_tier = _group_files_by_tier(files, tier_configs)
    rules: dict[str, str] = {}

    for tier_config in tier_configs:
        tier_files = files_by_tier.get(tier_config.name, [])
        if not tier_files:
            continue

        filename = f"{tier_config.name}-docs.mdc"

        # Build glob patterns from the file paths
        globs = ", ".join(doc.rel_path for doc in tier_files)

        # YAML frontmatter
        frontmatter_lines = [
            "---",
            f"description: {tier_config.instruction}",
            f"globs: {globs}",
            "---",
        ]

        # Content body
        body_lines = [
            "",
            f"# {tier_config.name.capitalize()} Documentation",
            "",
        ]
        for doc in tier_files:
            body_lines.append(f"- {doc.rel_path}")
        body_lines.append("")

        rules[filename] = "\n".join(frontmatter_lines + body_lines)

    return rules


def render_copilot_instructions(
    files: list[DocFile],
    tier_configs: list[TierConfig],
    instruction: str = DEFAULT_INSTRUCTION,
) -> str:
    """Render GitHub Copilot instructions format.

    Generates .github/copilot-instructions.md format with instruction
    header and all tiers with their files.

    Args:
        files: List of DocFiles (should already have tier/section assigned)
        tier_configs: Tier configurations (for tier order and instructions)
        instruction: Project-level instruction for Copilot

    Returns:
        Markdown string for .github/copilot-instructions.md
    """
    lines: list[str] = []

    lines.append("# Copilot Instructions")
    lines.append("")
    lines.append(instruction)
    lines.append("")

    files_by_tier = _group_files_by_tier(files, tier_configs)

    for tier_config in tier_configs:
        tier_files = files_by_tier.get(tier_config.name, [])
        if not tier_files:
            continue

        tier_name_capitalized = tier_config.name.capitalize()
        lines.append(f"## {tier_name_capitalized}")
        lines.append("")
        lines.append(f"_{tier_config.instruction}_")
        lines.append("")

        for doc in tier_files:
            lines.append(f"- {doc.rel_path}")
        lines.append("")

    return "\n".join(lines) + "\n"


def render_for_target(
    target: str,
    files: list[DocFile],
    tier_configs: list[TierConfig],
    instruction: str = DEFAULT_INSTRUCTION,
) -> str | dict[str, str]:
    """Dispatch to the correct renderer based on output target name.

    Args:
        target: Output target identifier. One of:
            "agents.md", "claude.md", "cursor-rules", "copilot-instructions"
        files: List of DocFiles (should already have tier/section assigned)
        tier_configs: Tier configurations (for tier order and instructions)
        instruction: Project-level instruction

    Returns:
        Rendered output (str for most targets, dict[str, str] for cursor-rules)

    Raises:
        ValueError: If target is not recognized
    """
    if target == "agents.md":
        return render_index(files, tier_configs, instruction=instruction)
    if target == "claude.md":
        return render_claude_md(files, tier_configs, instruction)
    if target == "cursor-rules":
        return render_cursor_rules(files, tier_configs)
    if target == "copilot-instructions":
        return render_copilot_instructions(files, tier_configs, instruction)

    raise ValueError(
        f"Unknown output target: {target!r}. "
        f"Valid targets: 'agents.md', 'claude.md', 'cursor-rules', 'copilot-instructions'"
    )


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
        target_path.write_text(content, encoding="utf-8")
        return

    # Read existing content
    existing = target_path.read_text(encoding="utf-8")

    # Find markers
    start_pos = existing.find(start_marker)
    end_pos = existing.find(end_marker)

    # Both markers must exist for replacement
    if start_pos == -1 or end_pos == -1 or end_pos <= start_pos:
        # Append to end if markers don't exist or are incomplete
        if existing and not existing.endswith("\n"):
            existing += "\n"
        new_content = existing + content
        target_path.write_text(new_content, encoding="utf-8")
        return

    # Replace content between markers (keeping markers)
    before = existing[: start_pos + len(start_marker)]
    after = existing[end_pos:]

    new_content = f"{before}\n{content}\n{after}"
    target_path.write_text(new_content, encoding="utf-8")
