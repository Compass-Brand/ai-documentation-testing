"""Doc transformation pipeline for agent-index.

Provides a composable pipeline for transforming documentation content.
Strategies execute sequentially, with support for incremental processing
via content hash tracking.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from agent_index.models import DocFile, DocTree, TransformStep

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Strategy functions
# ---------------------------------------------------------------------------


def passthrough(content: str) -> str:
    """Return content unchanged."""
    return content


def algorithmic_compress(content: str) -> str:
    """Apply regex/heuristic cleanup to documentation content.

    Transformations applied (in order):
    - Remove HTML comments
    - Collapse consecutive blank lines to a single blank line
    - Remove trailing whitespace from each line
    - Normalize markdown headings (ensure space after #)
    - Strip leading/trailing whitespace from the entire file
    """
    # Remove HTML comments (including multiline)
    content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)

    # Collapse consecutive blank lines to a single blank line
    content = re.sub(r"\n{3,}", "\n\n", content)

    # Remove trailing whitespace from each line
    content = re.sub(r"[ \t]+$", "", content, flags=re.MULTILINE)

    # Normalize markdown headings: ensure space after #
    # Matches lines starting with 1-6 # followed by a non-space, non-# character
    content = re.sub(
        r"^(#{1,6})([^\s#])",
        r"\1 \2",
        content,
        flags=re.MULTILINE,
    )

    # Strip leading/trailing whitespace from the entire file
    content = content.strip()

    return content


def llm_compress(content: str, model: str | None = None) -> str:
    """Placeholder for LLM-based compression.

    In production this would send the content to an LLM for intelligent
    compression while preserving key information. Currently returns the
    content with a comment indicating where LLM compression would occur.
    """
    model_name = model or "default"
    return f"<!-- LLM compression would be applied here (model: {model_name}) -->\n{content}"


def llm_restructure(content: str, model: str | None = None) -> str:
    """Placeholder for LLM-based restructuring.

    In production this would send the content to an LLM to reorganize
    and restructure the document. Currently returns the content with a
    comment indicating where LLM restructuring would occur.
    """
    model_name = model or "default"
    return f"<!-- LLM restructuring would be applied here (model: {model_name}) -->\n{content}"


def llm_tagged(content: str, model: str | None = None) -> str:
    """Placeholder for LLM-based tagging.

    In production this would send the content to an LLM to add semantic
    tags and annotations. Currently returns the content with a comment
    indicating where LLM tagging would occur.
    """
    model_name = model or "default"
    return f"<!-- LLM tagging would be applied here (model: {model_name}) -->\n{content}"


# Map strategy names to functions
_STRATEGY_MAP: dict[str, object] = {
    "passthrough": passthrough,
    "algorithmic": algorithmic_compress,
    "compressed": llm_compress,
    "restructured": llm_restructure,
    "tagged": llm_tagged,
}


# ---------------------------------------------------------------------------
# Data classes and models
# ---------------------------------------------------------------------------


@dataclass
class TransformResult:
    """Result of transforming a single documentation file."""

    file_path: str
    original_content: str
    transformed_content: str
    strategy_applied: str
    success: bool
    error: str | None = None


class TransformState(BaseModel):
    """Persistent state for incremental transform processing.

    Serialized to .agent-index-state.json.
    """

    file_hashes: dict[str, str] = Field(default_factory=dict)
    last_run: datetime | None = None
    transform_config: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------


def save_state(state: TransformState, path: Path) -> None:
    """Save transform state to a JSON file.

    Args:
        state: The transform state to persist.
        path: File path to write the state to.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        state.model_dump_json(indent=2),
        encoding="utf-8",
    )


def load_state(path: Path) -> TransformState | None:
    """Load transform state from a JSON file.

    Args:
        path: File path to read the state from.

    Returns:
        The loaded TransformState, or None if the file does not exist
        or cannot be parsed.
    """
    if not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        return TransformState.model_validate_json(raw)
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

# Retry settings for LLM strategies
_MAX_RETRIES = 3
_BASE_DELAY = 0.1  # seconds


def _resolve_strategy(step: TransformStep) -> tuple[object, str]:
    """Resolve a TransformStep to its callable strategy and label.

    Returns:
        A (callable, label) tuple.
    """
    if step.type == "passthrough":
        return passthrough, "passthrough"

    if step.type == "algorithmic":
        return algorithmic_compress, "algorithmic"

    # LLM strategies: look up by strategy name
    strategy_fn = _STRATEGY_MAP.get(step.strategy)
    if strategy_fn is not None:
        return strategy_fn, f"llm/{step.strategy}"

    # Fallback
    return passthrough, "passthrough"


def _is_llm_step(step: TransformStep) -> bool:
    """Return True if the step involves an LLM call."""
    return step.type == "llm"


class TransformPipeline:
    """Composable pipeline for transforming documentation content.

    Steps execute sequentially. Each step receives the output of the
    previous step.
    """

    def __init__(self, steps: list[TransformStep]) -> None:
        self.steps = steps

    # ------------------------------------------------------------------
    # Single-file transform
    # ------------------------------------------------------------------

    def transform_file(self, doc: DocFile) -> TransformResult:
        """Run a single file through all pipeline steps.

        On failure the pipeline falls back to passthrough so that partial
        results are always available.

        Args:
            doc: The documentation file to transform.

        Returns:
            A TransformResult describing the outcome.
        """
        content = doc.content
        applied_strategies: list[str] = []

        for step in self.steps:
            strategy_fn, label = _resolve_strategy(step)
            try:
                content = self._execute_step(
                    strategy_fn, content, step, is_llm=_is_llm_step(step)
                )
                applied_strategies.append(label)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Strategy %s failed for %s: %s – falling back to passthrough",
                    label,
                    doc.rel_path,
                    exc,
                )
                applied_strategies.append("passthrough(fallback)")
                # Content remains unchanged from before this step

        return TransformResult(
            file_path=doc.rel_path,
            original_content=doc.content,
            transformed_content=content,
            strategy_applied="+".join(applied_strategies),
            success=True,
        )

    # ------------------------------------------------------------------
    # Tree-level transform
    # ------------------------------------------------------------------

    def transform_tree(
        self,
        doc_tree: DocTree,
        state: TransformState | None = None,
    ) -> tuple[DocTree, TransformState]:
        """Transform every file in a DocTree, returning an updated tree and state.

        Files whose content_hash matches the value stored in *state* are
        skipped (incremental processing).

        Args:
            doc_tree: The documentation tree to transform.
            state: Optional prior state for incremental processing.

        Returns:
            A tuple of (updated DocTree, updated TransformState).
        """
        if state is None:
            state = TransformState()

        new_files: dict[str, DocFile] = {}

        for rel_path, doc in doc_tree.files.items():
            # Incremental: skip if hash unchanged
            if (
                rel_path in state.file_hashes
                and state.file_hashes[rel_path] == doc.content_hash
            ):
                new_files[rel_path] = doc
                continue

            result = self.transform_file(doc)

            # Build updated DocFile with transformed content
            new_hash = hashlib.sha256(
                result.transformed_content.encode("utf-8")
            ).hexdigest()

            new_doc = doc.model_copy(
                update={
                    "content": result.transformed_content,
                    "content_hash": new_hash,
                    "size_bytes": len(result.transformed_content.encode("utf-8")),
                },
            )
            new_files[rel_path] = new_doc

            # Track hash of the *original* content so we can detect
            # future changes to the source file.
            state.file_hashes[rel_path] = doc.content_hash

        # Update state metadata
        state.last_run = datetime.now(UTC)
        state.transform_config = [s.model_dump() for s in self.steps]

        new_tree = doc_tree.model_copy(update={"files": new_files})
        return new_tree, state

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _execute_step(
        strategy_fn: object,
        content: str,
        step: TransformStep,
        *,
        is_llm: bool,
    ) -> str:
        """Execute a single strategy, with retries for LLM steps.

        Args:
            strategy_fn: The callable strategy function.
            content: Current content to transform.
            step: The TransformStep configuration.
            is_llm: Whether this is an LLM-based step (enables retry).

        Returns:
            Transformed content string.
        """
        max_attempts = _MAX_RETRIES if is_llm else 1

        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                if is_llm:
                    return strategy_fn(content, model=step.model)  # type: ignore[operator]
                return strategy_fn(content)  # type: ignore[operator]
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < max_attempts - 1:
                    delay = _BASE_DELAY * (2**attempt)
                    time.sleep(delay)

        # All retries exhausted — re-raise so caller can handle
        raise last_exc  # type: ignore[misc]
