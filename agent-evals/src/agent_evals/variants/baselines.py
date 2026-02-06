"""Baseline variants for controlled evaluation comparisons.

Provides four axis-0 baseline variants:

- **NoIndexBaseline** -- Empty index (lower bound).
- **NoDocsBaseline** -- File listing without content.
- **OracleBaseline** -- Pre-selected relevant docs (upper bound).
- **LengthMatchedRandomBaseline** -- Random docs matching a token target.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from agent_evals.variants.base import IndexVariant, VariantMetadata
from agent_evals.variants.registry import register_variant

if TYPE_CHECKING:
    from agent_index.models import DocTree


@register_variant
class NoIndexBaseline(IndexVariant):
    """Baseline that provides no documentation index at all.

    Establishes the lower-bound performance: what happens when an agent
    receives zero guidance from a documentation index.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the no-index baseline."""
        return VariantMetadata(
            name="no-index",
            axis=0,
            category="baseline",
            description="Empty index providing no documentation guidance (lower bound).",
            token_estimate=0,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Return an empty string regardless of the doc tree.

        Args:
            doc_tree: Ignored; no output is produced.

        Returns:
            An empty string.
        """
        return ""


@register_variant
class NoDocsBaseline(IndexVariant):
    """Baseline that lists file paths without their content.

    Measures the value of file-listing metadata alone: the agent sees
    which files exist but cannot read their contents.
    """

    def metadata(self) -> VariantMetadata:
        """Return metadata for the no-docs baseline."""
        return VariantMetadata(
            name="no-docs",
            axis=0,
            category="baseline",
            description="File listing without content to isolate index-only value.",
            token_estimate=0,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Return a listing of file paths from the doc tree without content.

        Args:
            doc_tree: Documentation tree whose file paths are listed.

        Returns:
            A newline-separated listing of file paths with tier and section.
        """
        if not doc_tree.files:
            return ""
        lines: list[str] = []
        for rel_path, doc_file in sorted(doc_tree.files.items()):
            lines.append(
                f"- {rel_path} (tier: {doc_file.tier}, section: {doc_file.section})"
            )
        return "\n".join(lines)


@register_variant
class OracleBaseline(IndexVariant):
    """Baseline that provides pre-selected relevant documents.

    Establishes an upper bound by simulating perfect retrieval: the runner
    calls ``set_relevant_docs`` before each task to specify exactly which
    documents are relevant.
    """

    def __init__(self) -> None:
        self._relevant_docs: list[str] = []

    def set_relevant_docs(self, docs: list[str]) -> None:
        """Set the list of relevant document paths for the next render.

        Called by the evaluation runner before each task.

        Args:
            docs: List of ``rel_path`` keys into the doc tree that are
                relevant for the current task.
        """
        self._relevant_docs = list(docs)

    def metadata(self) -> VariantMetadata:
        """Return metadata for the oracle baseline."""
        return VariantMetadata(
            name="oracle",
            axis=0,
            category="baseline",
            description="Pre-selected relevant docs simulating perfect retrieval (upper bound).",
            token_estimate=0,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Return content for only the pre-selected relevant documents.

        Args:
            doc_tree: Documentation tree to extract relevant docs from.

        Returns:
            Concatenated content of relevant documents, each prefixed by
            its file path.  Documents not found in the tree are skipped.
        """
        sections: list[str] = []
        for rel_path in self._relevant_docs:
            if rel_path in doc_tree.files:
                doc = doc_tree.files[rel_path]
                sections.append(f"## {rel_path}\n{doc.content}")
        return "\n\n".join(sections)


@register_variant
class LengthMatchedRandomBaseline(IndexVariant):
    """Baseline that samples random documents to match a target token count.

    Controls for the confound that longer indexes might perform better
    simply because they contain more information.  The runner calls
    ``set_target_tokens`` to set the budget before each render.

    Uses ``random.Random(42)`` for deterministic shuffling so results
    are reproducible across runs.
    """

    def __init__(self) -> None:
        self._target_tokens: int = 0
        self._rng: random.Random = random.Random(42)  # noqa: S311

    def set_target_tokens(self, tokens: int) -> None:
        """Set the target token budget for the next render.

        Called by the evaluation runner before each task.

        Args:
            tokens: Maximum total token count for the rendered output.
        """
        self._target_tokens = tokens

    def metadata(self) -> VariantMetadata:
        """Return metadata for the length-matched random baseline."""
        return VariantMetadata(
            name="length-matched-random",
            axis=0,
            category="baseline",
            description="Random docs matching a target token count to control for length.",
            token_estimate=0,
        )

    def render(self, doc_tree: DocTree) -> str:
        """Return random documents from the tree within the token budget.

        Files are shuffled deterministically (seed 42), then greedily added
        until the next file would exceed the remaining token budget.

        Args:
            doc_tree: Documentation tree to sample from.

        Returns:
            Concatenated content of selected documents, each prefixed by
            its file path.  Returns empty string if target is 0.
        """
        if self._target_tokens <= 0:
            return ""

        # Re-seed each render for determinism
        self._rng = random.Random(42)  # noqa: S311

        files = list(doc_tree.files.values())
        self._rng.shuffle(files)

        selected: list[str] = []
        remaining_tokens = self._target_tokens

        for doc in files:
            token_count = doc.token_count if doc.token_count is not None else 0
            if token_count <= remaining_tokens:
                selected.append(f"## {doc.rel_path}\n{doc.content}")
                remaining_tokens -= token_count

        return "\n\n".join(selected)
