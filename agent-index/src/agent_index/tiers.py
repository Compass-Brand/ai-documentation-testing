"""Tier system for assigning files to documentation tiers.

This module handles:
- Matching files to tiers via glob patterns
- Section extraction from file paths
- BLUF (Bottom Line Up Front) ordering for output
"""

from __future__ import annotations

import re

from agent_index.models import DocFile, DocTree, TierConfig


def assign_tiers(
    doc_tree: DocTree,
    tier_configs: list[TierConfig],
) -> DocTree:
    """Assign tier and section to each file in a DocTree.

    Files are matched against tier patterns in order. The first matching
    tier wins. Files that match no pattern go to the last tier.

    Args:
        doc_tree: DocTree with files to assign
        tier_configs: List of tier configurations with patterns

    Returns:
        New DocTree with tier and section assigned to each file
    """
    # Build new files dict with assigned tiers
    new_files: dict[str, DocFile] = {}

    for rel_path, doc in doc_tree.files.items():
        tier_name = _match_tier(rel_path, tier_configs)
        section = _extract_section(rel_path)

        # Create new DocFile with updated tier and section
        new_files[rel_path] = doc.model_copy(
            update={"tier": tier_name, "section": section}
        )

    # Return new DocTree with same metadata but updated files
    return DocTree(
        files=new_files,
        scanned_at=doc_tree.scanned_at,
        source=doc_tree.source,
        total_tokens=doc_tree.total_tokens,
    )


def _match_tier(rel_path: str, tier_configs: list[TierConfig]) -> str:
    """Match a file path to a tier based on glob patterns.

    Args:
        rel_path: Relative path of the file
        tier_configs: List of tier configurations with patterns

    Returns:
        Name of the matching tier, or the last tier name if no pattern matches,
        or empty string if no tiers are configured.
    """
    if not tier_configs:
        return ""

    # Try each tier in order
    for tier in tier_configs:
        for pattern in tier.patterns:
            if _glob_match(rel_path, pattern):
                return tier.name

    # No pattern matched - fall back to last tier
    return tier_configs[-1].name


def _glob_match(path: str, pattern: str) -> bool:
    """Match a path against a glob pattern.

    Supports:
    - * matches any characters except /
    - ** matches any characters including / (zero or more path segments)
    - ? matches single character

    Args:
        path: File path to match (using forward slashes)
        pattern: Glob pattern to match against

    Returns:
        True if the path matches the pattern
    """
    # Handle ** by converting the glob pattern to a regex.
    # This correctly handles multiple ** segments (e.g. docs/**/api/**/*.md).
    if "**" in pattern:
        regex = _glob_to_regex(pattern)
        return bool(re.fullmatch(regex, path))

    # Simple glob matching without **
    return _simple_glob_match(path, pattern)


def _glob_to_regex(pattern: str) -> str:
    """Convert a glob pattern containing ** to an equivalent regex string.

    Rules:
    - ** matches zero or more path segments (any characters including /)
    - *  matches any characters except /
    - ?  matches a single character except /
    - All other characters are escaped as regex literals.

    A leading or trailing **/ or /** is normalised so that:
    - **/foo  -> foo anywhere in the path (at any depth)
    - foo/**  -> foo followed by any deeper path

    Args:
        pattern: Glob pattern that may contain ** tokens.

    Returns:
        Regex string suitable for re.fullmatch().
    """
    # Split the pattern on ** to get the literal segments between them.
    # We will join them with a regex that matches any path segment (or none).
    double_star_parts = pattern.split("**")

    regex_parts: list[str] = []
    for i, part in enumerate(double_star_parts):
        # Strip slashes adjacent to ** so we can handle them in the connector
        if i > 0:
            part = part.lstrip("/")
        next_has_star = i < len(double_star_parts) - 1
        if next_has_star:
            part = part.rstrip("/")

        regex_parts.append(_simple_glob_to_regex(part))

        if next_has_star:
            # ** connector: matches zero or more path segments.
            # We absorbed adjacent slashes above, so now insert a pattern
            # that optionally matches path segments.
            if i == 0 and not part:
                # Leading **: match optional path prefix (no leading /)
                regex_parts.append("(?:.+/)?")
            else:
                # Middle/trailing **: match /anything including deeper paths
                regex_parts.append("(?:/.+)*(?:/)?")

    return "".join(regex_parts)


def _simple_glob_to_regex(segment: str) -> str:
    """Convert a simple glob segment (no **) to a regex string.

    - * becomes [^/]* (any chars except slash)
    - ? becomes [^/]  (single char except slash)
    - Other chars are regex-escaped.

    Args:
        segment: Glob segment without **.

    Returns:
        Regex string for this segment.
    """
    parts: list[str] = []
    i = 0
    while i < len(segment):
        ch = segment[i]
        if ch == "*":
            parts.append("[^/]*")
        elif ch == "?":
            parts.append("[^/]")
        else:
            parts.append(re.escape(ch))
        i += 1
    return "".join(parts)


def _simple_glob_match(path: str, pattern: str) -> bool:
    """Match a path against a simple glob pattern (no **).

    Uses regex conversion to ensure * does not match /,
    unlike fnmatch which allows * to cross path separators on Linux.

    Args:
        path: File path to match
        pattern: Glob pattern (supports * and ?)

    Returns:
        True if the path matches the pattern
    """
    regex = _simple_glob_to_regex(pattern)
    return bool(re.fullmatch(regex, path))


def _extract_section(rel_path: str) -> str:
    """Extract section name from a relative file path.

    Section is determined by the path structure:
    - Top-level files: section = ""
    - Single directory deep: section = "" (first dir is root)
    - Nested deeper: section = second directory component

    Examples:
        "README.md" -> ""
        "docs/setup.md" -> ""
        "docs/guides/auth.md" -> "guides"
        "docs/api/v2/users.md" -> "api"

    Args:
        rel_path: Relative file path using forward slashes

    Returns:
        Section name, or empty string for root-level files
    """
    parts = rel_path.split("/")

    # File is at root or only one directory deep
    if len(parts) <= 2:
        return ""

    # Return the second directory component (index 1)
    return parts[1]


def sort_files_bluf(
    files: list[DocFile],
    tier_configs: list[TierConfig],
) -> list[DocFile]:
    """Sort files in BLUF (Bottom Line Up Front) order.

    Order: required tier first, then recommended, then reference,
    with files sorted by priority (descending) then path within each tier.

    Args:
        files: List of DocFiles to sort
        tier_configs: Tier configurations (for tier ordering)

    Returns:
        Sorted list of DocFiles
    """
    # Build tier name to order mapping
    tier_order = {tier.name: i for i, tier in enumerate(tier_configs)}
    max_order = len(tier_configs)  # Unknown tiers get this order

    def sort_key(doc: DocFile) -> tuple[int, int, str]:
        """Generate sort key: (tier_order, -priority, path)."""
        tier_idx = tier_order.get(doc.tier, max_order)
        # Negate priority so higher priority comes first
        return (tier_idx, -doc.priority, doc.rel_path)

    return sorted(files, key=sort_key)


def group_by_section(files: list[DocFile]) -> dict[str, list[DocFile]]:
    """Group files by their section field.

    Args:
        files: List of DocFiles

    Returns:
        Dict mapping section names to files in that section
    """
    groups: dict[str, list[DocFile]] = {}

    for doc in files:
        if doc.section not in groups:
            groups[doc.section] = []
        groups[doc.section].append(doc)

    return groups
