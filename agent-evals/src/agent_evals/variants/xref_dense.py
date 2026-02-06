"""Axis 9 cross-reference variant: dense cross-references.

After each file entry, adds "See also:" listing up to 3 files from the same
section AND any files whose content mentions the current file's stem.  Also
adds "Referenced by:" listing files that this file's content mentions.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


def _brief_summary(content: str, max_chars: int = 80) -> str:
    """Extract a brief summary from content.

    Takes the first non-empty line and truncates to *max_chars*.
    """
    for line in content.splitlines():
        stripped = line.strip().lstrip("# ")
        if stripped:
            return stripped[:max_chars]
    return ""


@register_variant
class XrefDenseVariant(IndexVariant):
    """Dense cross-references using section matching and content scanning.

    Produces both "See also:" (section peers + files mentioning this file's
    stem) and "Referenced by:" (files whose stems appear in this file's
    content) sub-items under each entry.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the dense-xref variant."""
        return VariantMetadata(
            name="xref-dense",
            axis=9,
            category="xref",
            description=(
                "Dense cross-references; section peers, content-based mentions, "
                "and referenced-by links."
            ),
            token_estimate=600,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Render files with dense cross-references.

        Args:
            doc_tree: Documentation tree to render.

        Returns:
            A bulleted list where each file has indented "See also:" and
            "Referenced by:" sub-items.
        """
        if not doc_tree.files:
            return ""

        sorted_paths = sorted(doc_tree.files)

        # Build section -> sorted paths mapping
        section_map: dict[str, list[str]] = defaultdict(list)
        for rel_path in sorted_paths:
            doc = doc_tree.files[rel_path]
            section_map[doc.section].append(rel_path)

        # Build stem -> path mapping for content-based lookups
        stem_to_path: dict[str, str] = {}
        for rel_path in sorted_paths:
            stem = PurePosixPath(rel_path).stem
            stem_to_path[stem] = rel_path

        # Pre-compute: which files mention each stem?
        # mentions_of[stem] = list of paths whose content contains that stem
        mentions_of: dict[str, list[str]] = defaultdict(list)
        for rel_path in sorted_paths:
            doc = doc_tree.files[rel_path]
            content_lower = doc.content.lower()
            for stem, stem_path in stem_to_path.items():
                if stem_path != rel_path and stem.lower() in content_lower:
                    mentions_of[stem].append(rel_path)

        lines: list[str] = []
        for rel_path in sorted_paths:
            doc = doc_tree.files[rel_path]
            summary = doc.summary or _brief_summary(doc.content)
            lines.append(f"- {rel_path}: {summary}")

            current_stem = PurePosixPath(rel_path).stem

            # "See also:" = up to 3 same-section peers + files that mention this stem
            section_peers = [
                p for p in section_map[doc.section] if p != rel_path
            ][:3]
            content_mentioners = [
                p
                for p in mentions_of.get(current_stem, [])
                if p not in section_peers
            ]
            see_also = section_peers + content_mentioners
            if see_also:
                lines.append(f"  See also: {', '.join(see_also)}")

            # "Referenced by:" = files whose stems appear in this file's content
            content_lower = doc.content.lower()
            referenced = []
            for stem, stem_path in sorted(stem_to_path.items()):
                if stem_path != rel_path and stem.lower() in content_lower:
                    referenced.append(stem_path)
            if referenced:
                lines.append(f"  Referenced by: {', '.join(referenced)}")

        return "\n".join(lines)
