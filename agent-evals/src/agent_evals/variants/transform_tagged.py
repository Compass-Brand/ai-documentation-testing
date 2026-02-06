"""Axis 5 transform variant: semantic tagging.

Adds semantic tags/annotations to each file entry.  Tags are derived from
content analysis: language tags from code blocks, topic tags from headings,
tier tag, and section tag.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocFile, DocTree

_CODE_FENCE_RE = re.compile(r"^```(\w+)", re.MULTILINE)
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)", re.MULTILINE)


def _extract_language_tags(content: str) -> list[str]:
    """Extract programming language tags from fenced code blocks."""
    languages = _CODE_FENCE_RE.findall(content)
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for lang in languages:
        lower = lang.lower()
        if lower not in seen:
            seen.add(lower)
            unique.append(lower)
    return unique


def _extract_topic_tags(content: str) -> list[str]:
    """Extract topic tags from Markdown headings.

    Takes the first three unique heading texts, lowered and stripped,
    as topic indicators.
    """
    headings = _HEADING_RE.findall(content)
    seen: set[str] = set()
    topics: list[str] = []
    for heading in headings:
        tag = heading.strip().lower()
        if tag and tag not in seen:
            seen.add(tag)
            topics.append(tag)
            if len(topics) >= 3:
                break
    return topics


def _build_tags(doc: DocFile) -> list[str]:
    """Build a list of semantic tags for a document."""
    tags: list[str] = []

    # Tier and section tags
    tags.append(f"tier:{doc.tier}")
    tags.append(f"section:{doc.section}")

    # Language tags from code blocks
    for lang in _extract_language_tags(doc.content):
        tags.append(f"lang:{lang}")

    # Topic tags from headings
    for topic in _extract_topic_tags(doc.content):
        tags.append(f"topic:{topic}")

    return tags


def _brief_summary(content: str, max_chars: int = 80) -> str:
    """Extract a brief summary from content."""
    for line in content.splitlines():
        stripped = line.strip().lstrip("# ")
        if stripped:
            return stripped[:max_chars]
    return ""


@register_variant
class TransformTaggedVariant(IndexVariant):
    """Semantic tagging -- annotates each file with derived tags.

    Tags include tier, section, programming languages from code blocks,
    and topic keywords from headings.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the tagged transform variant."""
        return VariantMetadata(
            name="transform-tagged",
            axis=5,
            category="transform",
            description=(
                "Semantic tags: tier, section, languages from code blocks, "
                "topics from headings."
            ),
            token_estimate=500,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render all files with semantic tag annotations.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            Markdown string with tagged file entries.
        """
        if not doc_tree.files:
            return ""

        lines: list[str] = []
        for rel_path in sorted(doc_tree.files):
            doc = doc_tree.files[rel_path]
            tags = _build_tags(doc)
            tag_str = ", ".join(tags)
            summary = _brief_summary(doc.content)
            lines.append(f"- {rel_path} [{tag_str}]: {summary}")
        return "\n".join(lines)
