"""Tests for NavigationPathMetric."""

from __future__ import annotations

import pytest
from agent_evals.metrics.base import MetricContext
from agent_evals.metrics.navigation import NavigationPathMetric


def _make_context(
    tool_calls: list[dict[str, object]] | None = None,
    expected_files: list[str] | None = None,
    files: list[str] | dict[str, str] | None = None,
) -> MetricContext:
    """Helper to build a MetricContext for navigation tests."""
    task_def: dict[str, object] = {"type": "lookup"}
    if expected_files is not None:
        task_def["expected_files"] = expected_files
    if files is not None:
        task_def["files"] = files
    return MetricContext(
        task_definition=task_def,
        index_content="",
        source_documents=[],
        tool_calls=tool_calls or [],
        attempt_number=1,
    )


class TestNavigationPathMetric:
    """Tests for NavigationPathMetric."""

    def test_name(self) -> None:
        """Metric name should be 'navigation_path'."""
        metric = NavigationPathMetric()
        assert metric.name == "navigation_path"

    def test_no_tool_calls_returns_zero(self) -> None:
        """No tool calls should return 0.0."""
        ctx = _make_context(
            tool_calls=[],
            expected_files=["src/main.py"],
        )
        score = NavigationPathMetric().compute("response", ctx)
        assert score == 0.0

    def test_all_reads_relevant_no_backtracking(self) -> None:
        """All reads targeting relevant files with no backtracking -> ~1.0."""
        ctx = _make_context(
            tool_calls=[
                {"tool": "read_file", "arguments": {"path": "src/main.py"}},
                {"tool": "read_file", "arguments": {"path": "src/utils.py"}},
            ],
            expected_files=["src/main.py", "src/utils.py"],
        )
        score = NavigationPathMetric().compute("response", ctx)
        assert score == pytest.approx(1.0)

    def test_mixed_relevant_irrelevant_reads(self) -> None:
        """Mixed relevant and irrelevant reads -> between 0 and 1."""
        ctx = _make_context(
            tool_calls=[
                {"tool": "read_file", "arguments": {"path": "src/main.py"}},
                {"tool": "read_file", "arguments": {"path": "src/unrelated.py"}},
                {"tool": "read_file", "arguments": {"path": "src/also_unrelated.py"}},
            ],
            expected_files=["src/main.py"],
        )
        score = NavigationPathMetric().compute("response", ctx)
        assert 0.0 < score < 1.0

    def test_backtracking_lowers_score(self) -> None:
        """Reading the same file twice (backtracking) should lower score."""
        ctx_no_bt = _make_context(
            tool_calls=[
                {"tool": "read_file", "arguments": {"path": "src/main.py"}},
            ],
            expected_files=["src/main.py"],
        )
        ctx_bt = _make_context(
            tool_calls=[
                {"tool": "read_file", "arguments": {"path": "src/main.py"}},
                {"tool": "read_file", "arguments": {"path": "src/main.py"}},
            ],
            expected_files=["src/main.py"],
        )
        score_no_bt = NavigationPathMetric().compute("response", ctx_no_bt)
        score_bt = NavigationPathMetric().compute("response", ctx_bt)
        assert score_bt < score_no_bt

    def test_no_relevant_files_in_ground_truth_returns_one(self) -> None:
        """No relevant files defined in task_definition -> 1.0."""
        ctx = _make_context(
            tool_calls=[
                {"tool": "read_file", "arguments": {"path": "src/main.py"}},
            ],
        )
        score = NavigationPathMetric().compute("response", ctx)
        assert score == 1.0

    def test_uses_files_key_fallback(self) -> None:
        """Should check 'files' key when 'expected_files' is not present."""
        ctx = _make_context(
            tool_calls=[
                {"tool": "read_file", "arguments": {"path": "src/main.py"}},
            ],
            files=["src/main.py"],
        )
        score = NavigationPathMetric().compute("response", ctx)
        assert score == pytest.approx(1.0)

    def test_recognizes_various_read_tool_names(self) -> None:
        """Should detect tools whose names contain read, open, file, or get."""
        ctx = _make_context(
            tool_calls=[
                {"tool": "open_document", "arguments": {"path": "a.py"}},
                {"tool": "get_content", "arguments": {"file_path": "b.py"}},
                {"tool": "file_reader", "arguments": {"path": "c.py"}},
                {"tool": "search_code", "arguments": {"query": "foo"}},
            ],
            expected_files=["a.py", "b.py", "c.py"],
        )
        metric = NavigationPathMetric()
        score = metric.compute("response", ctx)
        # The search_code tool should NOT be counted as a read operation
        # 3 reads, all relevant, optimal=3, unique=3 => perfect
        assert score == pytest.approx(1.0)

    def test_recognizes_name_key_for_tool_calls(self) -> None:
        """Should detect tool name from 'name' key (AgenticTask schema)."""
        ctx = _make_context(
            tool_calls=[
                {"name": "read_file", "arguments": {"path": "src/main.py"}},
            ],
            expected_files=["src/main.py"],
        )
        score = NavigationPathMetric().compute("response", ctx)
        assert score == pytest.approx(1.0)

    def test_files_dict_extracts_keys(self) -> None:
        """Should handle 'files' as a dict (AgenticTask format) by using keys."""
        ctx = _make_context(
            tool_calls=[
                {"tool": "read_file", "arguments": {"path": "src/main.py"}},
                {"tool": "read_file", "arguments": {"path": "src/unrelated.py"}},
            ],
            files={"src/main.py": "main module", "src/utils.py": "utilities"},
        )
        score = NavigationPathMetric().compute("response", ctx)
        # 1 of 2 reads is relevant, so score should be between 0 and 1
        assert 0.0 < score < 1.0

    def test_score_bounded_zero_to_one(self) -> None:
        """Score should always be in [0.0, 1.0]."""
        ctx = _make_context(
            tool_calls=[
                {"tool": "read_file", "arguments": {"path": f"f{i}.py"}}
                for i in range(20)
            ],
            expected_files=["f0.py"],
        )
        score = NavigationPathMetric().compute("response", ctx)
        assert 0.0 <= score <= 1.0
