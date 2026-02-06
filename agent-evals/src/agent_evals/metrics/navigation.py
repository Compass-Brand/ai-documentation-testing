"""Navigation path efficiency metric.

Measures how efficiently an agent navigates the file system during
agentic tasks by evaluating relevance, efficiency, and backtracking.
"""

from __future__ import annotations

import re
from typing import Any

from agent_evals.metrics.base import Metric, MetricContext

# Tool name patterns that indicate a file read operation.
_READ_TOOL_PATTERN: re.Pattern[str] = re.compile(
    r"read|open|file|get", re.IGNORECASE
)

# Argument keys where file paths are commonly found.
_PATH_KEYS: list[str] = ["path", "file_path", "file", "filename"]


def _extract_file_reads(tool_calls: list[dict[str, Any]]) -> list[str]:
    """Extract file paths from tool calls that look like read operations.

    Returns a list of file paths (one per read operation, may contain
    duplicates if the same file was read multiple times).
    """
    paths: list[str] = []
    for call in tool_calls:
        tool_name = str(call.get("tool", "") or call.get("name", ""))
        if not _READ_TOOL_PATTERN.search(tool_name):
            continue
        arguments: dict[str, Any] = call.get("arguments", {})
        if not isinstance(arguments, dict):
            continue
        for key in _PATH_KEYS:
            if key in arguments:
                paths.append(str(arguments[key]))
                break
    return paths


def _get_relevant_files(task_definition: dict[str, Any]) -> list[str] | None:
    """Get the list of relevant files from the task definition.

    Checks ``expected_files`` first, then ``files`` as a fallback.
    Returns ``None`` if neither key is present.
    """
    files: object = task_definition.get("expected_files")
    if files is None:
        files = task_definition.get("files")
    if files is None:
        return None
    if isinstance(files, list):
        return [str(f) for f in files]
    if isinstance(files, dict):
        return [str(k) for k in files]
    return None


class NavigationPathMetric(Metric):
    """Navigation path efficiency metric.

    Evaluates how effectively an agent navigates to the right files.

    Sub-scores (weighted):
        - **Relevance (0.4)**: fraction of reads targeting relevant files.
        - **Efficiency (0.3)**: ``min(optimal / actual, 1.0)``.
        - **No-backtracking (0.3)**: ``1 - (total - unique) / max(total, 1)``.

    Returns 0.0 when there are no tool calls, and 1.0 when the task
    definition does not specify any relevant files.
    """

    _WEIGHT_RELEVANCE: float = 0.4
    _WEIGHT_EFFICIENCY: float = 0.3
    _WEIGHT_NO_BACKTRACK: float = 0.3

    @property
    def name(self) -> str:  # noqa: D102
        return "navigation_path"

    def compute(self, response: str, context: MetricContext) -> float:
        """Compute navigation path efficiency score.

        Args:
            response: Unused for this metric (kept for interface conformance).
            context: Must contain ``tool_calls`` and ``task_definition``.

        Returns:
            Float in ``[0.0, 1.0]``.
        """
        read_paths = _extract_file_reads(context.tool_calls)
        total_reads = len(read_paths)

        if total_reads == 0:
            return 0.0

        relevant_files = _get_relevant_files(context.task_definition)
        if relevant_files is None or len(relevant_files) == 0:
            return 1.0

        relevant_set = set(relevant_files)
        optimal_count = len(relevant_set)
        unique_reads = len(set(read_paths))

        # Relevance: fraction of reads that target relevant files.
        relevant_reads = sum(1 for p in read_paths if p in relevant_set)
        relevance = relevant_reads / total_reads

        # Efficiency: optimal / actual, capped at 1.0.
        efficiency = min(optimal_count / total_reads, 1.0)

        # No-backtracking: penalise repeated reads.
        backtrack_penalty = (total_reads - unique_reads) / max(total_reads, 1)
        no_backtrack = 1.0 - backtrack_penalty

        return (
            self._WEIGHT_RELEVANCE * relevance
            + self._WEIGHT_EFFICIENCY * efficiency
            + self._WEIGHT_NO_BACKTRACK * no_backtrack
        )
