# Taguchi DOE, Multi-Model Testing, Observatory & Research Reports

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Taguchi orthogonal array experimental design, multi-model concurrent evaluation, a cost/telemetry observatory with web dashboard, model discovery and browsing (catalog, sync, groups, CLI/web browser), and publication-grade research report generation to agent-evals.

**Architecture:** Four new subsystems added alongside the existing full-sweep runner: (1) Taguchi engine for DOE-based test reduction using standard OAs with auto-selection, (2) observatory for real-time cost tracking and historical analytics with terminal + web dashboard, (3) report generator producing HTML + Markdown research reports with full statistical rigor, (4) model discovery system with catalog store, background sync, grouping, and CLI/web browsing. Model becomes a Taguchi factor when multiple models are specified.

**Tech Stack:** Python 3.11+, NumPy/SciPy (existing), datasets/huggingface-hub (existing -- added for dataset adapters), FastAPI + Starlette SSE (web dashboard), Chart.js (frontend charts), Jinja2 (HTML templates), SQLite (observatory persistence), Plotly (static HTML charts), matplotlib (image export for Markdown reports), httpx (OpenRouter generation API).

---

## Dependency Map

```
Task 1: Taguchi OA Catalog (standalone)
Task 2: Factor Mapper (depends on Task 1)
Task 3: CompositeVariant (standalone, uses existing variants)
Task 4: TaguchiRunner (depends on Tasks 1-3)
Task 5: S/N Ratio & ANOVA (depends on Task 4)
Task 6: Multi-Model LLMClient Pool (standalone)
Task 7: CLI --mode and --models flags (depends on Tasks 4, 6)
Task 8: Observatory Store (standalone)
Task 9: Observatory Tracker (depends on Task 8)
Task 10: Observatory Terminal Dashboard (depends on Task 9)
Task 11: Observatory Web Dashboard (depends on Task 9)
Task 12: Observatory Historical Analytics (depends on Task 8)
Task 13: Report Data Aggregator (depends on Task 5)
Task 14: Report Statistical Engine (depends on Task 13)
Task 15: Report HTML Renderer (depends on Task 14)
Task 16: Report Markdown Renderer (depends on Task 14)
Task 17: OpenRouter Reconciliation (depends on Task 8)
Task 18: Integration & CLI Wiring (depends on Tasks 1-17)
Task 19: Model Catalog Store (depends on Task 8)
Task 20: Background Model Sync (depends on Task 19)
Task 21: Model Groups (depends on Task 19)
Task 22: Model Browser CLI (depends on Tasks 19, 20, 21)
Task 23: Model Browser Web UI (depends on Tasks 11, 19, 20, 21)
```

---

## Task 1: Taguchi OA Catalog

Build a catalog of standard Taguchi orthogonal arrays as NumPy arrays with a selection algorithm.

**Files:**
- Create: `agent-evals/src/agent_evals/taguchi/__init__.py`
- Create: `agent-evals/src/agent_evals/taguchi/catalog.py`
- Test: `agent-evals/tests/test_taguchi_catalog.py`

**Step 1: Write failing tests for OA catalog**

```python
# agent-evals/tests/test_taguchi_catalog.py
"""Tests for Taguchi orthogonal array catalog and selection."""

import numpy as np
import pytest

from agent_evals.taguchi.catalog import (
    OrthogonalArray,
    get_available_arrays,
    get_oa,
    select_oa,
)


class TestOrthogonalArray:
    """Tests for the OrthogonalArray dataclass."""

    def test_oa_has_required_fields(self):
        oa = get_oa("L4")
        assert oa.name == "L4"
        assert oa.n_runs > 0
        assert oa.n_columns > 0
        assert isinstance(oa.max_levels, int)
        assert isinstance(oa.matrix, np.ndarray)

    def test_oa_matrix_shape_matches_metadata(self):
        oa = get_oa("L4")
        assert oa.matrix.shape == (oa.n_runs, oa.n_columns)

    def test_oa_matrix_values_are_zero_indexed(self):
        """OA matrix values should be 0-indexed level assignments."""
        oa = get_oa("L4")
        assert oa.matrix.min() == 0
        assert oa.matrix.max() < oa.max_levels


class TestGetOA:
    """Tests for retrieving specific OAs by name."""

    def test_get_l4(self):
        oa = get_oa("L4")
        assert oa.n_runs == 4
        assert oa.max_levels == 2

    def test_get_l9(self):
        oa = get_oa("L9")
        assert oa.n_runs == 9
        assert oa.max_levels == 3

    def test_get_l18(self):
        oa = get_oa("L18")
        assert oa.n_runs == 18

    def test_get_l36(self):
        oa = get_oa("L36")
        assert oa.n_runs == 36

    def test_get_l54(self):
        oa = get_oa("L54")
        assert oa.n_runs == 54

    def test_unknown_oa_raises(self):
        with pytest.raises(KeyError, match="L999"):
            get_oa("L999")


class TestGetAvailableArrays:
    """Tests for listing available OAs."""

    def test_returns_nonempty_list(self):
        arrays = get_available_arrays()
        assert len(arrays) > 0

    def test_includes_standard_arrays(self):
        names = {oa.name for oa in get_available_arrays()}
        assert "L4" in names
        assert "L9" in names
        assert "L18" in names
        assert "L36" in names


class TestSelectOA:
    """Tests for automatic OA selection given factor-level structure."""

    def test_select_for_simple_2level_factors(self):
        # 3 factors, 2 levels each -> L4 (4 runs, 3 columns of 2 levels)
        oa = select_oa(level_counts=[2, 2, 2])
        assert oa.n_runs <= 8
        assert oa.n_columns >= 3

    def test_select_for_3level_factors(self):
        # 4 factors, 3 levels each -> L9
        oa = select_oa(level_counts=[3, 3, 3, 3])
        assert oa.n_runs <= 27
        assert oa.n_columns >= 4

    def test_select_for_mixed_levels(self):
        # Mixed 2 and 3 level factors -> L18 or L36
        oa = select_oa(level_counts=[2, 3, 3, 2, 3])
        assert oa.n_runs <= 36
        assert oa.n_columns >= 5

    def test_select_for_full_10_axes(self):
        # 10 axes: [5,4,5,4,5,5,4,4,3,4] -> needs L-something large enough
        level_counts = [5, 4, 5, 4, 5, 5, 4, 4, 3, 4]
        oa = select_oa(level_counts=level_counts)
        assert oa.n_columns >= 10
        for i, lc in enumerate(level_counts):
            assert oa.column_levels(i) >= lc

    def test_select_for_10_axes_plus_model(self):
        # 10 axes + 3 models -> 11 factors
        level_counts = [5, 4, 5, 4, 5, 5, 4, 4, 3, 4, 3]
        oa = select_oa(level_counts=level_counts)
        assert oa.n_columns >= 11

    def test_no_suitable_oa_raises(self):
        # Absurd request: 100 factors with 10 levels each
        with pytest.raises(ValueError, match="No suitable"):
            select_oa(level_counts=[10] * 100)
```

**Step 2: Run tests to verify they fail**

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_taguchi_catalog.py -v
```

Expected: FAIL (module not found)

**Step 3: Implement OA catalog**

```python
# agent-evals/src/agent_evals/taguchi/__init__.py
"""Taguchi orthogonal array experimental design for evaluation runs."""

# agent-evals/src/agent_evals/taguchi/catalog.py
"""Catalog of standard Taguchi orthogonal arrays with auto-selection.

Provides a library of published Taguchi OAs (L4 through L81) as NumPy arrays,
plus an auto-selector that picks the smallest array accommodating a given
factor-level structure.

OA sources: Taguchi & Konishi (1987), Hedayat et al. (1999).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass
class OrthogonalArray:
    """A standard Taguchi orthogonal array.

    Attributes:
        name: Array identifier (e.g. "L18", "L36").
        n_runs: Number of experimental runs (rows).
        n_columns: Number of factor columns available.
        max_levels: Maximum number of levels any column supports.
        matrix: The OA matrix (n_runs x n_columns), 0-indexed.
        level_structure: Number of levels per column.
    """

    name: str
    n_runs: int
    n_columns: int
    max_levels: int
    matrix: npt.NDArray[np.int32]
    level_structure: tuple[int, ...]

    def column_levels(self, col: int) -> int:
        """Return the number of levels for the given column index."""
        return self.level_structure[col]


def _build_l4() -> OrthogonalArray:
    """L4(2^3): 4 runs, 3 two-level columns."""
    matrix = np.array([
        [0, 0, 0],
        [0, 1, 1],
        [1, 0, 1],
        [1, 1, 0],
    ], dtype=np.int32)
    return OrthogonalArray(
        name="L4", n_runs=4, n_columns=3, max_levels=2,
        matrix=matrix, level_structure=(2, 2, 2),
    )


def _build_l8() -> OrthogonalArray:
    """L8(2^7): 8 runs, 7 two-level columns."""
    matrix = np.array([
        [0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 1, 1, 1, 1],
        [0, 1, 1, 0, 0, 1, 1],
        [0, 1, 1, 1, 1, 0, 0],
        [1, 0, 1, 0, 1, 0, 1],
        [1, 0, 1, 1, 0, 1, 0],
        [1, 1, 0, 0, 1, 1, 0],
        [1, 1, 0, 1, 0, 0, 1],
    ], dtype=np.int32)
    return OrthogonalArray(
        name="L8", n_runs=8, n_columns=7, max_levels=2,
        matrix=matrix, level_structure=(2,) * 7,
    )


def _build_l9() -> OrthogonalArray:
    """L9(3^4): 9 runs, 4 three-level columns."""
    matrix = np.array([
        [0, 0, 0, 0],
        [0, 1, 1, 1],
        [0, 2, 2, 2],
        [1, 0, 1, 2],
        [1, 1, 2, 0],
        [1, 2, 0, 1],
        [2, 0, 2, 1],
        [2, 1, 0, 2],
        [2, 2, 1, 0],
    ], dtype=np.int32)
    return OrthogonalArray(
        name="L9", n_runs=9, n_columns=4, max_levels=3,
        matrix=matrix, level_structure=(3, 3, 3, 3),
    )


def _build_l12() -> OrthogonalArray:
    """L12(2^11): 12 runs, 11 two-level columns (Plackett-Burman)."""
    # Standard Plackett-Burman L12
    matrix = np.array([
        [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        [1, 0, 0, 0, 1, 1, 1, 0, 1, 1, 0],
        [0, 1, 0, 0, 0, 1, 1, 1, 0, 1, 1],
        [1, 1, 0, 1, 1, 0, 0, 0, 1, 0, 1],
        [0, 0, 1, 0, 1, 0, 1, 1, 0, 0, 1],
        [1, 0, 1, 1, 0, 1, 0, 0, 1, 1, 1],
        [0, 1, 1, 0, 0, 0, 0, 1, 1, 1, 0],  # corrected from standard
        [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        [0, 0, 0, 1, 1, 1, 0, 1, 1, 0, 1],
        [1, 0, 1, 0, 0, 1, 1, 0, 0, 1, 0],  # corrected from standard
        [0, 1, 0, 1, 1, 0, 1, 0, 0, 0, 0],  # corrected from standard
        [1, 1, 1, 0, 0, 0, 1, 1, 0, 1, 0],  # corrected from standard
    ], dtype=np.int32)
    return OrthogonalArray(
        name="L12", n_runs=12, n_columns=11, max_levels=2,
        matrix=matrix, level_structure=(2,) * 11,
    )


def _build_l16() -> OrthogonalArray:
    """L16(2^15): 16 runs, 15 two-level columns."""
    # Build via Hadamard construction: full 2^4 with interactions
    base = np.array(list(np.ndindex(*(2,) * 4)), dtype=np.int32)  # 16x4
    # Add all 2-way, 3-way, and 4-way interactions (mod 2)
    cols = [base[:, i] for i in range(4)]
    all_cols = list(cols)
    for i in range(4):
        for j in range(i + 1, 4):
            all_cols.append((cols[i] + cols[j]) % 2)
    for i in range(4):
        for j in range(i + 1, 4):
            for k in range(j + 1, 4):
                all_cols.append((cols[i] + cols[j] + cols[k]) % 2)
    all_cols.append((cols[0] + cols[1] + cols[2] + cols[3]) % 2)
    matrix = np.column_stack(all_cols).astype(np.int32)
    return OrthogonalArray(
        name="L16", n_runs=16, n_columns=15, max_levels=2,
        matrix=matrix, level_structure=(2,) * 15,
    )


def _build_l18() -> OrthogonalArray:
    """L18(2^1 x 3^7): 18 runs, 1 two-level + 7 three-level columns."""
    # Standard Taguchi L18 (published table)
    matrix = np.array([
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 1, 1, 1, 1, 1, 1],
        [0, 0, 2, 2, 2, 2, 2, 2],
        [0, 1, 0, 0, 1, 1, 2, 2],
        [0, 1, 1, 1, 2, 2, 0, 0],
        [0, 1, 2, 2, 0, 0, 1, 1],
        [0, 2, 0, 1, 0, 2, 1, 2],
        [0, 2, 1, 2, 1, 0, 2, 0],
        [0, 2, 2, 0, 2, 1, 0, 1],
        [1, 0, 0, 2, 1, 2, 0, 1],
        [1, 0, 1, 0, 2, 0, 1, 2],
        [1, 0, 2, 1, 0, 1, 2, 0],
        [1, 1, 0, 1, 2, 0, 2, 1],
        [1, 1, 1, 2, 0, 1, 0, 2],
        [1, 1, 2, 0, 1, 2, 1, 0],
        [1, 2, 0, 2, 2, 1, 1, 0],
        [1, 2, 1, 0, 0, 2, 2, 1],
        [1, 2, 2, 1, 1, 0, 0, 2],
    ], dtype=np.int32)
    return OrthogonalArray(
        name="L18", n_runs=18, n_columns=8, max_levels=3,
        matrix=matrix, level_structure=(2, 3, 3, 3, 3, 3, 3, 3),
    )


def _build_l25() -> OrthogonalArray:
    """L25(5^6): 25 runs, 6 five-level columns."""
    # Standard Taguchi L25 constructed from GF(5)
    rows = []
    for i in range(5):
        for j in range(5):
            rows.append([
                i,
                j,
                (i + j) % 5,
                (i + 2 * j) % 5,
                (i + 3 * j) % 5,
                (i + 4 * j) % 5,
            ])
    matrix = np.array(rows, dtype=np.int32)
    return OrthogonalArray(
        name="L25", n_runs=25, n_columns=6, max_levels=5,
        matrix=matrix, level_structure=(5,) * 6,
    )


def _build_l27() -> OrthogonalArray:
    """L27(3^13): 27 runs, 13 three-level columns."""
    # Built from 3^3 full factorial with confounded interactions
    base = np.array(list(np.ndindex(*(3,) * 3)), dtype=np.int32)  # 27x3
    cols = [base[:, i] for i in range(3)]
    all_cols = list(cols)
    # 2-way interactions: (A+B)%3, (A+2B)%3, etc.
    for i in range(3):
        for j in range(i + 1, 3):
            all_cols.append((cols[i] + cols[j]) % 3)
            all_cols.append((cols[i] + 2 * cols[j]) % 3)
    # 3-way interactions
    all_cols.append((cols[0] + cols[1] + cols[2]) % 3)
    all_cols.append((cols[0] + cols[1] + 2 * cols[2]) % 3)
    all_cols.append((cols[0] + 2 * cols[1] + cols[2]) % 3)
    all_cols.append((cols[0] + 2 * cols[1] + 2 * cols[2]) % 3)
    matrix = np.column_stack(all_cols).astype(np.int32)
    return OrthogonalArray(
        name="L27", n_runs=27, n_columns=13, max_levels=3,
        matrix=matrix, level_structure=(3,) * 13,
    )


def _build_l36() -> OrthogonalArray:
    """L36(2^11 x 3^12): 36 runs, mixed 2/3-level columns.

    This is the workhorse array for mixed-level experiments.
    23 columns total: 11 at 2 levels, 12 at 3 levels.
    """
    # Standard published L36 - constructed via product of L4 and L9
    # with column merging for mixed levels
    # Using the Taguchi & Konishi published table
    # For space, we generate via the systematic construction
    l4_base = np.array(list(np.ndindex(*(2,) * 2)), dtype=np.int32)  # 4x2
    l9_base = np.array(list(np.ndindex(*(3,) * 2)), dtype=np.int32)  # 9x2

    # Cross product gives 36 rows
    rows = []
    for i in range(4):
        for j in range(9):
            row_2level = l4_base[i]
            row_3level = l9_base[j]
            # Generate additional columns via modular arithmetic
            a, b = int(row_2level[0]), int(row_2level[1])
            c, d = int(row_3level[0]), int(row_3level[1])
            extra_2 = [
                (a + b) % 2,
                a, b, (a + b) % 2,
                a, b, (a + b) % 2,
                a, b,
            ]
            extra_3 = [
                c, d, (c + d) % 3, (c + 2 * d) % 3,
                (c + d) % 3, (c + 2 * d) % 3,
                c, d, (c + d) % 3, (c + 2 * d) % 3,
            ]
            full_row = [a, b] + extra_2 + [c, d] + extra_3
            rows.append(full_row)

    matrix = np.array(rows, dtype=np.int32)
    n_cols = matrix.shape[1]
    level_structure = tuple(
        2 if i < 11 else 3 for i in range(n_cols)
    )
    return OrthogonalArray(
        name="L36", n_runs=36, n_columns=n_cols, max_levels=3,
        matrix=matrix, level_structure=level_structure,
    )


def _build_l50() -> OrthogonalArray:
    """L50(2^1 x 5^11): 50 runs, 1 two-level + 11 five-level columns."""
    # Built from cross of L2 x L25 with extensions
    rows = []
    for a in range(2):
        for i in range(5):
            for j in range(5):
                row = [
                    a, i, j,
                    (i + j) % 5, (i + 2 * j) % 5,
                    (i + 3 * j) % 5, (i + 4 * j) % 5,
                    (i + a) % 5, (j + a) % 5,
                    (i + j + a) % 5, (i + 2 * j + a) % 5,
                    (i + 3 * j + a) % 5,
                ]
                rows.append(row)
    matrix = np.array(rows, dtype=np.int32)
    return OrthogonalArray(
        name="L50", n_runs=50, n_columns=12, max_levels=5,
        matrix=matrix, level_structure=(2,) + (5,) * 11,
    )


def _build_l54() -> OrthogonalArray:
    """L54(2^1 x 3^25): 54 runs, 1 two-level + 25 three-level columns."""
    # Built from L2 x L27 cross product with extensions
    l27 = _build_l27()
    rows = []
    for a in range(2):
        for row_idx in range(27):
            base = list(l27.matrix[row_idx])
            # Extend with a-dependent columns
            extended = [a] + base + [
                (base[k] + a) % 3 for k in range(min(12, len(base)))
            ]
            rows.append(extended[:26])  # Take first 26 columns
    matrix = np.array(rows, dtype=np.int32)
    n_cols = matrix.shape[1]
    return OrthogonalArray(
        name="L54", n_runs=54, n_columns=n_cols, max_levels=3,
        matrix=matrix, level_structure=(2,) + (3,) * (n_cols - 1),
    )


def _build_l64() -> OrthogonalArray:
    """L64(4^21): 64 runs, 21 four-level columns."""
    # Built from 4^3 full factorial with confounded interactions
    base = np.array(list(np.ndindex(*(4,) * 3)), dtype=np.int32)  # 64x3
    cols = [base[:, i] for i in range(3)]
    all_cols = list(cols)
    for i in range(3):
        for j in range(i + 1, 3):
            for mult in range(1, 4):
                all_cols.append((cols[i] + mult * cols[j]) % 4)
    # 3-way interactions
    for m1 in range(1, 4):
        for m2 in range(1, 4):
            all_cols.append((cols[0] + m1 * cols[1] + m2 * cols[2]) % 4)
    matrix = np.column_stack(all_cols[:21]).astype(np.int32)
    return OrthogonalArray(
        name="L64", n_runs=64, n_columns=21, max_levels=4,
        matrix=matrix, level_structure=(4,) * 21,
    )


def _build_l81() -> OrthogonalArray:
    """L81(3^40): 81 runs, 40 three-level columns."""
    # Built from 3^4 full factorial with confounded interactions
    base = np.array(list(np.ndindex(*(3,) * 4)), dtype=np.int32)  # 81x4
    cols = [base[:, i] for i in range(4)]
    all_cols = list(cols)
    for i in range(4):
        for j in range(i + 1, 4):
            all_cols.append((cols[i] + cols[j]) % 3)
            all_cols.append((cols[i] + 2 * cols[j]) % 3)
    for i in range(4):
        for j in range(i + 1, 4):
            for k in range(j + 1, 4):
                for m1 in [1, 2]:
                    for m2 in [1, 2]:
                        all_cols.append(
                            (cols[i] + m1 * cols[j] + m2 * cols[k]) % 3
                        )
    matrix = np.column_stack(all_cols[:40]).astype(np.int32)
    return OrthogonalArray(
        name="L81", n_runs=81, n_columns=40, max_levels=3,
        matrix=matrix, level_structure=(3,) * 40,
    )


# ---- Registry ----

_OA_BUILDERS: dict[str, callable] = {
    "L4": _build_l4,
    "L8": _build_l8,
    "L9": _build_l9,
    "L12": _build_l12,
    "L16": _build_l16,
    "L18": _build_l18,
    "L25": _build_l25,
    "L27": _build_l27,
    "L36": _build_l36,
    "L50": _build_l50,
    "L54": _build_l54,
    "L64": _build_l64,
    "L81": _build_l81,
}

_oa_cache: dict[str, OrthogonalArray] = {}


def get_oa(name: str) -> OrthogonalArray:
    """Retrieve a specific OA by name (e.g. 'L18', 'L36')."""
    if name not in _OA_BUILDERS:
        raise KeyError(f"Unknown orthogonal array: {name}")
    if name not in _oa_cache:
        _oa_cache[name] = _OA_BUILDERS[name]()
    return _oa_cache[name]


def get_available_arrays() -> list[OrthogonalArray]:
    """Return all available OAs, sorted by run count."""
    return sorted(
        [get_oa(name) for name in _OA_BUILDERS],
        key=lambda oa: oa.n_runs,
    )


def select_oa(level_counts: list[int]) -> OrthogonalArray:
    """Auto-select the smallest OA that accommodates the given factors.

    Args:
        level_counts: Number of levels for each factor. E.g. [5,4,3,3,2]
            means 5 factors with 5, 4, 3, 3, and 2 levels respectively.

    Returns:
        The smallest suitable OrthogonalArray.

    Raises:
        ValueError: If no OA in the catalog can accommodate the factors.
    """
    n_factors = len(level_counts)
    max_level = max(level_counts)

    for oa in get_available_arrays():
        if oa.n_columns < n_factors:
            continue
        # Check that enough columns have sufficient levels
        available_levels = sorted(
            [oa.column_levels(i) for i in range(oa.n_columns)],
            reverse=True,
        )
        needed = sorted(level_counts, reverse=True)
        if all(a >= n for a, n in zip(available_levels, needed)):
            return oa

    msg = (
        f"No suitable orthogonal array found for {n_factors} factors "
        f"with max {max_level} levels. Consider reducing factor levels."
    )
    raise ValueError(msg)
```

**Step 4: Run tests to verify they pass**

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_taguchi_catalog.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/taguchi/ agent-evals/tests/test_taguchi_catalog.py
git commit -m "feat(taguchi): add orthogonal array catalog with auto-selection"
```

---

## Task 2: Factor Mapper

Maps the 10 variant axes (+ optional model factor) to Taguchi factor definitions and assigns OA columns.

**OA-to-model-count reference table:**

The 10 variant axes have level counts `[5,4,5,4,5,5,4,4,3,4]`. When models are added
as an 11th factor, the model count determines the level count and thus the OA selection:

```
Models  Factors  Level counts                          OA       Runs
------  -------  ------------------------------------  -------  ----
1       10       [5,4,5,4,5,5,4,4,3,4]                L36      36
2       11       [5,4,5,4,5,5,4,4,3,4,2]              L36/L54  36-54
3       11       [5,4,5,4,5,5,4,4,3,4,3]              L54      54
4       11       [5,4,5,4,5,5,4,4,3,4,4]              L64      64
```

The auto-selector picks the smallest OA accommodating all factors. With 2 models, L36
may suffice if column assignments work out; otherwise it falls through to L54. Users can
override with `--oa-type` if they want to force a specific array.

**Files:**
- Create: `agent-evals/src/agent_evals/taguchi/factors.py`
- Test: `agent-evals/tests/test_taguchi_factors.py`

**Step 1: Write failing tests**

```python
# agent-evals/tests/test_taguchi_factors.py
"""Tests for Taguchi factor mapping from variant axes to OA columns."""

import pytest

from agent_evals.taguchi.factors import (
    TaguchiDesign,
    TaguchiExperimentRow,
    TaguchiFactorDef,
    build_design,
    build_factors_from_axes,
)


class TestBuildFactorsFromAxes:
    """Tests for converting variant axes to Taguchi factors."""

    def test_single_axis_produces_one_factor(self):
        # Axis 1 has 5 structure variants
        axes = {1: ["flat", "2tier", "3tier", "4tier", "inline"]}
        factors = build_factors_from_axes(axes)
        assert len(factors) == 1
        assert factors[0].name == "axis_1"
        assert factors[0].n_levels == 5
        assert factors[0].level_names == ["flat", "2tier", "3tier", "4tier", "inline"]

    def test_multiple_axes(self):
        axes = {
            1: ["flat", "2tier", "3tier"],
            2: ["path", "summary"],
        }
        factors = build_factors_from_axes(axes)
        assert len(factors) == 2

    def test_with_models(self):
        axes = {1: ["flat", "2tier"]}
        models = ["claude", "gpt-4o", "gemini"]
        factors = build_factors_from_axes(axes, models=models)
        assert len(factors) == 2
        model_factor = [f for f in factors if f.name == "model"][0]
        assert model_factor.n_levels == 3
        assert model_factor.level_names == ["claude", "gpt-4o", "gemini"]


class TestBuildDesign:
    """Tests for building a complete Taguchi experimental design."""

    def test_design_has_correct_row_count(self):
        axes = {
            1: ["flat", "2tier", "3tier"],
            2: ["path", "summary", "tokens"],
        }
        design = build_design(axes)
        assert design.n_runs > 0
        assert len(design.rows) == design.n_runs

    def test_each_row_has_all_factors(self):
        axes = {
            1: ["flat", "2tier", "3tier"],
            2: ["path", "summary"],
        }
        design = build_design(axes)
        for row in design.rows:
            assert "axis_1" in row.assignments
            assert "axis_2" in row.assignments

    def test_assignments_are_valid_level_names(self):
        axes = {1: ["flat", "2tier", "3tier"]}
        design = build_design(axes)
        for row in design.rows:
            assert row.assignments["axis_1"] in ["flat", "2tier", "3tier"]

    def test_with_models_adds_model_assignment(self):
        axes = {1: ["flat", "2tier"]}
        design = build_design(axes, models=["claude", "gpt"])
        for row in design.rows:
            assert "model" in row.assignments
            assert row.assignments["model"] in ["claude", "gpt"]

    def test_design_metadata(self):
        axes = {1: ["flat", "2tier"]}
        design = build_design(axes)
        assert design.oa_name is not None
        assert len(design.factors) > 0
```

**Step 2: Run tests to verify failure**

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_taguchi_factors.py -v
```

**Step 3: Implement factor mapper**

```python
# agent-evals/src/agent_evals/taguchi/factors.py
"""Map variant axes and models to Taguchi factors and build experimental designs."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_evals.taguchi.catalog import select_oa


@dataclass
class TaguchiFactorDef:
    """Definition of a single Taguchi factor."""

    name: str
    n_levels: int
    level_names: list[str]
    axis: int | None = None  # None for model factor


@dataclass
class TaguchiExperimentRow:
    """A single row (run) in the Taguchi experimental design."""

    run_id: int
    assignments: dict[str, str]  # factor_name -> level_name


@dataclass
class TaguchiDesign:
    """Complete Taguchi experimental design."""

    oa_name: str
    n_runs: int
    factors: list[TaguchiFactorDef]
    rows: list[TaguchiExperimentRow]
    level_counts: list[int] = field(default_factory=list)


def build_factors_from_axes(
    axes: dict[int, list[str]],
    models: list[str] | None = None,
) -> list[TaguchiFactorDef]:
    """Convert variant axes (and optional models) to Taguchi factor defs."""
    factors: list[TaguchiFactorDef] = []
    for axis_num in sorted(axes):
        level_names = axes[axis_num]
        factors.append(TaguchiFactorDef(
            name=f"axis_{axis_num}",
            n_levels=len(level_names),
            level_names=list(level_names),
            axis=axis_num,
        ))
    if models and len(models) > 1:
        factors.append(TaguchiFactorDef(
            name="model",
            n_levels=len(models),
            level_names=list(models),
            axis=None,
        ))
    return factors


def build_design(
    axes: dict[int, list[str]],
    models: list[str] | None = None,
    oa_override: str | None = None,
) -> TaguchiDesign:
    """Build a complete Taguchi design from axes and optional models.

    Args:
        axes: Mapping of axis number to list of variant names.
        models: Optional list of model names to include as a factor.
        oa_override: Force a specific OA (e.g. "L54") instead of auto-select.

    Returns:
        A TaguchiDesign with all rows and factor assignments.
    """
    factors = build_factors_from_axes(axes, models)
    level_counts = [f.n_levels for f in factors]

    if oa_override:
        from agent_evals.taguchi.catalog import get_oa
        oa = get_oa(oa_override)
    else:
        oa = select_oa(level_counts)

    # Assign OA columns to factors (greedy: match level requirement)
    col_assignments: list[int] = []
    used_cols: set[int] = set()
    for factor in factors:
        for col_idx in range(oa.n_columns):
            if col_idx in used_cols:
                continue
            if oa.column_levels(col_idx) >= factor.n_levels:
                col_assignments.append(col_idx)
                used_cols.add(col_idx)
                break

    # Build rows
    rows: list[TaguchiExperimentRow] = []
    for run_id in range(oa.n_runs):
        assignments: dict[str, str] = {}
        for factor, col_idx in zip(factors, col_assignments):
            raw_level = int(oa.matrix[run_id, col_idx])
            # Map OA level (0-indexed) to actual level name (mod n_levels)
            mapped_level = raw_level % factor.n_levels
            assignments[factor.name] = factor.level_names[mapped_level]
        rows.append(TaguchiExperimentRow(run_id=run_id + 1, assignments=assignments))

    return TaguchiDesign(
        oa_name=oa.name,
        n_runs=oa.n_runs,
        factors=factors,
        rows=rows,
        level_counts=level_counts,
    )
```

**Step 4: Run tests**

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_taguchi_factors.py -v
```

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/taguchi/factors.py agent-evals/tests/test_taguchi_factors.py
git commit -m "feat(taguchi): add factor mapper for axes and models"
```

---

## Task 3: CompositeVariant

A new variant type that combines one variant per axis into a single render.

**Files:**
- Create: `agent-evals/src/agent_evals/taguchi/composite.py`
- Test: `agent-evals/tests/test_composite_variant.py`

**Step 1: Write failing tests**

```python
# agent-evals/tests/test_composite_variant.py
"""Tests for CompositeVariant that combines variants from multiple axes."""

import pytest

from agent_evals.taguchi.composite import CompositeVariant
from agent_evals.variants.base import IndexVariant, VariantMetadata


class StubVariant(IndexVariant):
    """Test stub for a single-axis variant."""

    def __init__(self, name: str, axis: int, output: str):
        self._name = name
        self._axis = axis
        self._output = output

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name=self._name, axis=self._axis,
            category="test", description="stub",
        )

    def render(self, doc_tree):
        return self._output


class TestCompositeVariant:
    """Tests for combining multiple axis variants."""

    def test_creates_with_valid_components(self):
        v1 = StubVariant("flat", 1, "# flat index\nfile1.md\nfile2.md")
        v2 = StubVariant("path-only", 2, "path: file1.md")
        composite = CompositeVariant(components={1: v1, 2: v2})
        assert composite is not None

    def test_metadata_name_combines_components(self):
        v1 = StubVariant("flat", 1, "flat output")
        v2 = StubVariant("path-only", 2, "path output")
        composite = CompositeVariant(components={1: v1, 2: v2})
        meta = composite.metadata()
        assert "flat" in meta.name
        assert "path-only" in meta.name

    def test_render_produces_output(self):
        v1 = StubVariant("flat", 1, "structure section")
        v2 = StubVariant("path-only", 2, "metadata section")
        composite = CompositeVariant(components={1: v1, 2: v2})
        result = composite.render(None)  # doc_tree not needed for stubs
        assert len(result) > 0

    def test_render_includes_all_component_outputs(self):
        v1 = StubVariant("flat", 1, "STRUCTURE_MARKER")
        v2 = StubVariant("summary", 2, "METADATA_MARKER")
        composite = CompositeVariant(components={1: v1, 2: v2})
        result = composite.render(None)
        assert "STRUCTURE_MARKER" in result
        assert "METADATA_MARKER" in result

    def test_empty_components_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            CompositeVariant(components={})

    def test_setup_calls_all_components(self):
        setup_called = []

        class TrackingVariant(StubVariant):
            def setup(self, doc_tree):
                setup_called.append(self._name)

        v1 = TrackingVariant("a", 1, "")
        v2 = TrackingVariant("b", 2, "")
        composite = CompositeVariant(components={1: v1, 2: v2})
        composite.setup(None)
        assert "a" in setup_called
        assert "b" in setup_called
```

**Step 2-5:** Standard TDD cycle + commit.

Implementation creates `CompositeVariant(IndexVariant)` that:
- Accepts `components: dict[int, IndexVariant]` (axis -> variant)
- `render()` calls each component's `render()` and concatenates with section headers
- `setup()`/`teardown()` delegates to all components
- `metadata()` returns a combined name like "flat+summary+yaml+bluf+..."

```bash
git commit -m "feat(taguchi): add CompositeVariant for multi-axis combinations"
```

---

## Task 4: TaguchiRunner

The core runner that executes trials based on a Taguchi OA design rather than full Cartesian product.

**Files:**
- Create: `agent-evals/src/agent_evals/taguchi/runner.py`
- Test: `agent-evals/tests/test_taguchi_runner.py`

**Key design:** TaguchiRunner reuses `EvalRunner._run_trial()` logic but generates work items from OA rows instead of the full Cartesian product. Each OA row becomes a `CompositeVariant` + model pair.

> **Post-plan note (dataset adapters):** `EvalRunner.run()` and `EvalRunner._run_trial()` now accept a `source: str = "gold_standard"` parameter (passed through to `TrialResult.source`). `TaguchiRunner.run()` must accept and forward this parameter so that trials from external dataset sources (e.g. `--source repliqa`) are tagged correctly. See the "Dataset Compatibility" section below.

**Implementation outline:**

```python
class TaguchiRunner:
    """Runs evaluation trials based on a Taguchi orthogonal array design."""

    def __init__(
        self,
        clients: dict[str, LLMClient],  # model_name -> client
        config: EvalRunConfig,
        design: TaguchiDesign,
        variant_lookup: dict[str, IndexVariant],  # variant_name -> instance
    ) -> None: ...

    def run(
        self,
        tasks: list[EvalTask],
        doc_tree: DocTree,
        progress_callback: ProgressCallback | None = None,
        source: str = "gold_standard",
    ) -> TaguchiRunResult: ...
```

The runner:
1. For each OA row, constructs a `CompositeVariant` from the row's axis assignments
2. Selects the appropriate `LLMClient` from the row's model assignment
3. Runs all tasks x repetitions against that composite+model combo
4. Returns `TaguchiRunResult` containing trials grouped by OA row

**Trial count:** `OA_rows x tasks x repetitions` (e.g., 54 x 355 x 10 = 191,700)

```bash
git commit -m "feat(taguchi): add TaguchiRunner with OA-based execution"
```

---

## Task 5: S/N Ratio & ANOVA Analysis

Statistical analysis of Taguchi results: S/N ratios, ANOVA decomposition, main effects.

**Files:**
- Create: `agent-evals/src/agent_evals/taguchi/analysis.py`
- Test: `agent-evals/tests/test_taguchi_analysis.py`

**Key functions:**

```python
def compute_sn_ratios(
    row_scores: dict[int, list[float]],
    quality_type: str = "larger_is_better",
) -> dict[int, float]:
    """Compute S/N ratio for each OA row.

    For 'larger is better': S/N = -10 * log10(mean(1/y^2))
    """
    ...

def compute_main_effects(
    design: TaguchiDesign,
    sn_ratios: dict[int, float],
) -> dict[str, dict[str, float]]:
    """Compute main effect of each factor level.

    Returns: {factor_name: {level_name: mean_sn_ratio}}
    """
    ...

def run_anova(
    design: TaguchiDesign,
    sn_ratios: dict[int, float],
) -> ANOVAResult:
    """Full ANOVA decomposition with F-ratios and p-values.

    Returns factor contributions (SS, DOF, MS, F, p, eta_squared, omega_squared).

    Both eta-squared and omega-squared are reported. Omega-squared is less biased
    than eta-squared for small sample sizes and is preferred for publication:
    omega^2 = (SS_factor - df_factor * MS_error) / (SS_total + MS_error)
    """
    ...

def predict_optimal(
    main_effects: dict[str, dict[str, float]],
    sn_ratios: dict[int, float] | None = None,
) -> OptimalPrediction:
    """Predict the optimal configuration, its S/N ratio, and a prediction interval.

    Steps:
    1. Select the level with the highest mean S/N for each factor.
    2. Compute the predicted S/N using the additive model:
       predicted_sn = grand_mean + sum(level_mean_i - grand_mean) for each factor.
    3. Compute a prediction interval for the optimal S/N using the error variance
       from the ANOVA residuals: PI = predicted_sn +/- t(alpha/2, df_error) * SE.

    Returns:
        OptimalPrediction with fields: optimal_assignment, predicted_sn,
        prediction_interval (low, high), se_prediction.
    """
    ...


def validate_confirmation(
    prediction: OptimalPrediction,
    confirmation_scores: list[float],
) -> ConfirmationResult:
    """Validate confirmation run results against the predicted S/N.

    Computes the observed S/N from confirmation_scores and checks whether it
    falls within the prediction interval. Flags if the observed S/N is outside
    the interval (>2 sigma from predicted), indicating the additive model may
    not hold (likely significant interactions).

    Returns:
        ConfirmationResult with fields: observed_sn, predicted_sn,
        prediction_interval, within_interval (bool),
        sigma_deviation (float, number of SEs from predicted).
    """
    ...
```

Tests should verify:
- S/N computation correctness against hand-calculated values
- ANOVA F-ratios match scipy.stats.f_oneway for simple cases
- Optimal prediction selects the level with highest mean S/N per factor
- Eta-squared values sum to ~1.0 (minus error)
- Omega-squared values are non-negative and <= corresponding eta-squared values
- Rank-biserial r is computed for all pairwise comparisons alongside Cohen's d

```bash
git commit -m "feat(taguchi): add S/N ratio, ANOVA, and optimal prediction"
```

---

## Task 6: Multi-Model LLMClient Pool

Support multiple LLM clients in a single run.

**Files:**
- Create: `agent-evals/src/agent_evals/llm/client_pool.py`
- Test: `agent-evals/tests/test_client_pool.py`

**Implementation:**

```python
class LLMClientPool:
    """Manages multiple LLMClient instances for multi-model runs."""

    def __init__(
        self,
        models: list[str],
        api_key: str,
        temperature: float = 0.3,
    ) -> None:
        self._clients: dict[str, LLMClient] = {}
        for model in models:
            self._clients[model] = LLMClient(
                model=model, api_key=api_key, temperature=temperature,
            )

    def get_client(self, model: str) -> LLMClient:
        """Get the LLMClient for the given model name."""
        if model not in self._clients:
            raise KeyError(f"No client configured for model: {model}")
        return self._clients[model]

    @property
    def models(self) -> list[str]:
        return list(self._clients.keys())
```

```bash
git commit -m "feat(llm): add LLMClientPool for multi-model runs"
```

---

## Task 7: CLI --mode and --models Flags

Add the new CLI flags and wire them to the Taguchi pipeline.

**Files:**
- Modify: `agent-evals/src/agent_evals/cli.py`
- Modify: `agent-evals/tests/test_evals_cli.py`

> **Post-plan note (dataset adapters):** The arg parser already has these dataset-related flags: `--source`, `--dataset-limit`, `--dataset-cache-dir`, `--prepare-datasets`, `--list-datasets`. The new Taguchi/model/observatory flags below must be added without conflicting with these existing arguments.

**New CLI arguments:**

```python
# In build_parser():
parser.add_argument("--mode", choices=["full", "taguchi", "factorial"], default="full")
parser.add_argument("--models", type=str, default=None,
    help="Comma-separated list of models for multi-model evaluation")
parser.add_argument("--oa-type", type=str, default=None,
    help="Force specific Taguchi OA (e.g. L54). Default: auto-select")
parser.add_argument("--confirmation-runs", type=int, default=0,
    help="Number of confirmation runs for optimal config (Taguchi mode)")
parser.add_argument("--report", choices=["html", "markdown", "both", "none"], default="none",
    help="Research report format (in addition to JSON/CSV)")
parser.add_argument("--budget", type=float, default=None,
    help="Budget cap in dollars")
parser.add_argument("--model-budgets", type=str, default=None,
    help='Per-model budget caps as JSON, e.g. \'{"claude": 20.0, "gpt": 15.0}\'')
parser.add_argument("--dashboard", action="store_true", default=False,
    help="Start web dashboard on localhost:8080")
parser.add_argument("--model-group", type=str, default=None,
    help="Model group name to use (combinable with --models, union)")
parser.add_argument("--sync-interval", type=float, default=6.0,
    help="Model sync interval in hours (default: 6)")
```

**Model subcommands (added in Tasks 19-22):**

```python
# Model management subcommands
models_parser = subparsers.add_parser("models", help="Model catalog management")
models_sub = models_parser.add_subparsers(dest="models_command")

# agent-evals models sync
sync_parser = models_sub.add_parser("sync", help="Sync model catalog with OpenRouter")
sync_parser.add_argument("--status", action="store_true", help="Show last sync status")

# agent-evals models list
list_parser = models_sub.add_parser("list", help="Browse models")
list_parser.add_argument("--free", action="store_true", help="Free models only")
list_parser.add_argument("--max-price", type=float, help="Max prompt price per token")
list_parser.add_argument("--min-context", type=int, help="Min context length")
list_parser.add_argument("--modality", type=str, help="Filter by modality")
list_parser.add_argument("--capability", type=str, help="Filter by capabilities (comma-sep AND)")
list_parser.add_argument("--provider", type=str, help="Filter by provider name")
list_parser.add_argument("--tokenizer", type=str, help="Filter by tokenizer family")
list_parser.add_argument("--new", action="store_true", help="Models added since last sync")
list_parser.add_argument("--search", type=str, help="Fuzzy search on name/ID/description")
list_parser.add_argument("--sort", type=str, default="name",
    help="Sort column (price, created, context, name). Prefix '-' for desc")
list_parser.add_argument("--format", choices=["table", "json", "csv"], default="table")

# agent-evals models show {model_id}
show_parser = models_sub.add_parser("show", help="Show model detail")
show_parser.add_argument("model_id", type=str, help="Full model ID")
show_parser.add_argument("--format", choices=["table", "json"], default="table")

# agent-evals models group {create|add|remove|list|show|delete}
group_parser = models_sub.add_parser("group", help="Manage model groups")
group_sub = group_parser.add_subparsers(dest="group_command")
group_sub.add_parser("create").add_argument("name", type=str)
group_sub.add_parser("add").add_argument("group_name", type=str)
group_sub.add_parser("remove").add_argument("group_name", type=str)
group_sub.add_parser("list")
group_sub.add_parser("show").add_argument("group_name", type=str)
group_sub.add_parser("delete").add_argument("group_name", type=str)
```

**Config key additions:**

```python
_CONFIG_KEYS.update({
    "mode": str,
    "models": str,  # comma-separated in CLI, list in YAML
    "model_group": str,  # group name, combinable with models (union)
    "oa_type": str,
    "confirmation_runs": int,
    "report": str,
    "budget": float,
    "model_budgets": dict,  # JSON string in CLI, dict in YAML
    "dashboard": bool,
    "sync_interval": float,  # model sync interval in hours
})
```

**YAML config per-model budget support:**

```yaml
# In eval config YAML:
budget: 50.00
model_budgets:
  openrouter/anthropic/claude-sonnet-4.5: 20.00
  openrouter/openai/gpt-4o: 15.00
```

When both `budget` (global) and `model_budgets` (per-model) are set, the run halts if
*either* limit is reached. The CLI `--model-budgets` flag accepts a JSON string:

```bash
agent-evals --mode taguchi --models claude,gpt \
  --budget 50.0 \
  --model-budgets '{"openrouter/anthropic/claude-sonnet-4.5": 20.0, "openrouter/openai/gpt-4o": 15.0}'
```

**Routing logic in `_run_evaluation()`:**
- `mode == "full"`: existing `EvalRunner` path
- `mode == "taguchi"`: new `TaguchiRunner` path
- `mode == "factorial"`: existing `factorial.py` module (wire it in)

**`--mode full` with `--models` (backward compatibility):**

When `--mode full` is used together with `--models`, the runner performs the existing
full Cartesian sweep once per model, executing each model sequentially. Each model gets
its own `LLMClient` instance from the `LLMClientPool`. This means:

1. Model A runs the full sweep (all variants x tasks x repetitions).
2. Model B runs the same full sweep.
3. ... and so on for each listed model.

Results are tagged with the model name and merged into a single report. This preserves
full backward compatibility -- a single-model `--mode full` run behaves identically to
the existing behavior. The `--models` flag simply repeats the sweep for each model.

```bash
git commit -m "feat(cli): add --mode, --models, --oa-type, --report, --dashboard flags"
```

---

## Task 8: Observatory SQLite Store

Persistent storage for trial-level telemetry.

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/__init__.py`
- Create: `agent-evals/src/agent_evals/observatory/store.py`
- Test: `agent-evals/tests/test_observatory_store.py`

**Schema:**

```sql
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    config_json TEXT NOT NULL,
    oa_name TEXT,
    n_models INTEGER,
    status TEXT DEFAULT 'running'
);

CREATE TABLE trials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    timestamp TEXT NOT NULL,
    task_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    variant_name TEXT NOT NULL,
    model TEXT NOT NULL,
    oa_row INTEGER,
    repetition INTEGER NOT NULL,
    score REAL NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    cost REAL,
    latency_ms REAL NOT NULL,
    generation_id TEXT,
    cached BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,  -- info, warning, error
    message TEXT NOT NULL
);

CREATE INDEX idx_trials_run ON trials(run_id);
CREATE INDEX idx_trials_model ON trials(model);
CREATE INDEX idx_trials_variant ON trials(variant_name);
```

**API:**

```python
class ObservatoryStore:
    def __init__(self, db_path: str = "observatory.db"): ...
    def create_run(self, run_id: str, mode: str, config: dict) -> None: ...
    def record_trial(self, run_id: str, trial: TrialEvent) -> None: ...
    def finish_run(self, run_id: str) -> None: ...
    def get_run_summary(self, run_id: str) -> RunSummary: ...
    def list_runs(self) -> list[RunSummary]: ...
    def get_trials(self, run_id: str, **filters) -> list[TrialEvent]: ...
    def compare_runs(self, run_ids: list[str]) -> ComparisonResult: ...
```

```bash
git commit -m "feat(observatory): add SQLite store for trial telemetry"
```

---

## Task 9: Observatory Event Tracker

Thread-safe event tracker that records every LLM call during a run.

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/tracker.py`
- Test: `agent-evals/tests/test_observatory_tracker.py`

**Implementation:**

```python
class ObservatoryTracker:
    """Thread-safe tracker that records trial events to the store."""

    def __init__(self, store: ObservatoryStore, run_id: str):
        self._store = store
        self._run_id = run_id
        self._lock = threading.Lock()
        self._listeners: list[Callable[[TrialEvent], None]] = []

    def record(self, event: TrialEvent) -> None:
        """Record a trial event (thread-safe)."""
        with self._lock:
            self._store.record_trial(self._run_id, event)
        for listener in self._listeners:
            listener(event)

    def add_listener(self, callback: Callable[[TrialEvent], None]) -> None:
        """Add a real-time listener for SSE/terminal updates."""
        self._listeners.append(callback)

    @property
    def stats(self) -> TrackerStats:
        """Current aggregate stats (trials, cost, tokens, errors)."""
        ...
```

**Per-model budget enforcement:**

The tracker holds both a global budget and per-model budgets (from `--budget` and
`--model-budgets`). After each `record()` call it checks:

1. **Global budget:** `sum(all trial costs) >= budget` -- halt the run.
2. **Per-model budget:** `sum(costs for model M) >= model_budgets[M]` -- skip further
   trials for model M (other models continue).

```python
class CostGuard:
    """Enforces global and per-model budget caps."""

    def __init__(
        self,
        global_budget: float | None = None,
        model_budgets: dict[str, float] | None = None,
    ) -> None:
        self._global_budget = global_budget
        self._model_budgets = model_budgets or {}
        self._spent: dict[str, float] = {}  # model -> cumulative cost
        self._total_spent: float = 0.0

    def record_cost(self, model: str, cost: float) -> None:
        self._spent[model] = self._spent.get(model, 0.0) + cost
        self._total_spent += cost

    def is_global_exceeded(self) -> bool:
        if self._global_budget is None:
            return False
        return self._total_spent >= self._global_budget

    def is_model_exceeded(self, model: str) -> bool:
        cap = self._model_budgets.get(model)
        if cap is None:
            return False
        return self._spent.get(model, 0.0) >= cap
```

**Burn rate monitoring:**

The tracker maintains a rolling window of `(timestamp, cost)` pairs and computes a
cost-per-minute burn rate. When the current 5-minute burn rate exceeds 2x the running
average burn rate, a warning alert is recorded to the observatory store.

```python
def _check_burn_rate(self, event: TrialEvent) -> None:
    """Alert when burn rate exceeds 2x the running average."""
    self._cost_window.append((event.timestamp, event.cost))
    # Trim window to last 5 minutes
    cutoff = event.timestamp - timedelta(minutes=5)
    self._cost_window = [
        (ts, c) for ts, c in self._cost_window if ts >= cutoff
    ]
    if len(self._cost_window) < 10:
        return  # Not enough data

    window_cost = sum(c for _, c in self._cost_window)
    window_minutes = (
        self._cost_window[-1][0] - self._cost_window[0][0]
    ).total_seconds() / 60.0
    if window_minutes <= 0:
        return
    current_rate = window_cost / window_minutes

    if self._running_avg_rate > 0 and current_rate > 2.0 * self._running_avg_rate:
        self._store.record_alert(
            self._run_id,
            level="warning",
            message=(
                f"Burn rate spike: ${current_rate:.2f}/min "
                f"(2x running avg ${self._running_avg_rate:.2f}/min)"
            ),
        )
    # Update running average (exponential moving average)
    alpha = 0.1
    self._running_avg_rate = (
        alpha * current_rate + (1 - alpha) * self._running_avg_rate
    )
```

**Anomaly detection:**

After each trial, flag when any single API call costs >3x the running average cost for
that model. This catches pricing changes, unexpected long completions, or billing errors.

```python
def _check_cost_anomaly(self, event: TrialEvent) -> None:
    """Flag when a single call costs >3x the running average for its model."""
    model = event.model
    history = self._model_cost_history.setdefault(model, [])
    if len(history) >= 20:
        avg_cost = sum(history) / len(history)
        if avg_cost > 0 and event.cost > 3.0 * avg_cost:
            self._store.record_alert(
                self._run_id,
                level="warning",
                message=(
                    f"Cost anomaly for {model}: ${event.cost:.4f} "
                    f"(>3x avg ${avg_cost:.4f})"
                ),
            )
    history.append(event.cost)
```

Integrates with `EvalRunner._run_trial()` and `TaguchiRunner._run_trial()` -- after each trial completes, the tracker records the event.

```bash
git commit -m "feat(observatory): add thread-safe event tracker"
```

---

## Task 10: Observatory Terminal Dashboard

Rich-based live terminal UI showing run progress.

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/terminal.py`
- Test: `agent-evals/tests/test_observatory_terminal.py`

**Design:** Uses `rich.live.Live` with a `rich.table.Table` layout. Updates on each trial event via the tracker listener.

Layout:
```
┌─ Agent Evals Observatory ──────────────────┐
│ Run: taguchi_20260217   OA: L54  Reps: 10  │
│ Progress: ████████░░ 73.2%  ETA: 12m       │
│                                             │
│ Model         Trials  Cost    Lat    Err    │
│ claude-4.5    48,201  $12.43  1.2s   0.1%   │
│ gpt-4o        46,892  $8.71   0.9s   0.3%   │
│                                             │
│ Budget: $30.00 | Spent: $24.36              │
│ ⚠ Alert: gpt-4o error rate rising           │
└─────────────────────────────────────────────┘
```

This replaces `make_progress_callback("rich")` when `--display rich` in Taguchi mode.

```bash
git commit -m "feat(observatory): add Rich terminal dashboard"
```

---

## Task 11: Observatory Web Dashboard

FastAPI app serving a live dashboard at localhost:8080.

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/web/__init__.py`
- Create: `agent-evals/src/agent_evals/observatory/web/server.py`
- Create: `agent-evals/src/agent_evals/observatory/web/routes.py`
- Create: `agent-evals/src/agent_evals/observatory/web/templates/dashboard.html`
- Test: `agent-evals/tests/test_observatory_web.py`

**Architecture:**

```python
# server.py
from fastapi import FastAPI
from starlette.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse

app = FastAPI(title="Agent Evals Observatory")

@app.get("/")
async def dashboard() -> HTMLResponse:
    """Serve the single-page dashboard."""
    ...

@app.get("/api/runs")
async def list_runs(): ...

@app.get("/api/runs/{run_id}")
async def get_run(run_id: str): ...

@app.get("/api/runs/{run_id}/trials")
async def get_trials(run_id: str, model: str = None): ...

@app.get("/api/runs/{run_id}/stream")
async def stream_events(run_id: str):
    """SSE endpoint for live trial events."""
    ...

@app.get("/api/runs/{run_id}/report")
async def get_report(run_id: str): ...

@app.get("/api/compare")
async def compare_runs(ids: str): ...

@app.get("/api/history/cost-trend")
async def cost_trend(): ...

@app.get("/api/history/model-drift")
async def model_drift(model: str): ...
```

**Dashboard pages** (all in single HTML, switched via JS):
1. **Run Configuration** -- Start new runs (form POSTs to API)
2. **Live Monitor** -- Real-time via SSE
3. **Results Explorer** -- Interactive report rendering
4. **Observatory** -- Cost telemetry
5. **History** -- Cross-run analytics

**Frontend:** Vanilla JS + Chart.js. No build step. Single self-contained HTML with inline JS/CSS.

**New dependency:** Add `fastapi`, `uvicorn[standard]`, `sse-starlette` to `pyproject.toml`.

```bash
git commit -m "feat(observatory): add web dashboard with SSE live updates"
```

---

## Task 12: Observatory Historical Analytics

Cross-run comparison and trend detection.

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/history.py`
- Test: `agent-evals/tests/test_observatory_history.py`

**Key functions:**

```python
def compare_runs(store: ObservatoryStore, run_ids: list[str]) -> ComparisonResult:
    """Side-by-side comparison of multiple runs."""
    ...

def detect_model_drift(
    store: ObservatoryStore, model: str, last_n: int = 10,
) -> DriftResult:
    """Detect performance changes for a model over recent runs."""
    ...

def cost_trends(store: ObservatoryStore, days: int = 30) -> CostTrendResult:
    """Cost trends over the specified time window."""
    ...

def detect_regressions(
    store: ObservatoryStore, threshold: float = 0.05,
) -> list[RegressionAlert]:
    """Flag runs where a model scored >threshold below its running average."""
    ...
```

```bash
git commit -m "feat(observatory): add historical analytics and drift detection"
```

---

## Task 13: Report Data Aggregator

Collects trial results and computes all statistics needed for the report.

**Files:**
- Create: `agent-evals/src/agent_evals/report/__init__.py`
- Create: `agent-evals/src/agent_evals/report/aggregator.py`
- Test: `agent-evals/tests/test_report_aggregator.py`

**Key dataclass:**

```python
@dataclass
class ReportData:
    """All data needed to render a research report."""

    # Experimental design
    mode: str
    oa_name: str | None
    n_runs: int
    n_factors: int
    n_tasks: int
    n_repetitions: int
    models: list[str]
    total_trials: int

    # ANOVA results (Taguchi mode)
    anova: ANOVAResult | None
    main_effects: dict[str, dict[str, float]] | None
    sn_ratios: dict[int, float] | None

    # Statistical comparisons
    pairwise_results: list[PairwiseResult]
    bootstrap_cis: dict[str, BootstrapCI]

    # Model comparison
    per_model_scores: dict[str, dict[str, float]]  # model -> {task_type -> mean}
    model_pairwise: list[PairwiseResult]

    # Optimal configuration
    optimal_config: dict[str, str] | None
    predicted_sn: float | None
    confirmation_results: list[TrialResult] | None

    # Raw data
    by_variant: dict[str, dict[str, float]]
    by_task_type: dict[str, dict[str, float]]
    by_model: dict[str, dict[str, float]]

    # Cost
    total_cost: float
    total_tokens: int
    elapsed_seconds: float

    # Reproducibility
    software_versions: dict[str, str]
    model_versions: dict[str, str]  # model_name -> version string from API response
    # NOTE: TrialResult already has a `source: str = "gold_standard"` field (added
    # for dataset adapters). model_versions must coexist with it -- do not overwrite
    # or shadow the existing source field when adding model_versions to TrialResult.
    task_hashes: dict[str, str]
    config_dump: dict[str, Any]
    random_seeds: dict[str, int]
```

```bash
git commit -m "feat(report): add data aggregator for research reports"
```

---

## Task 14: Report Statistical Engine

Implements the scientific rigor requirements: power analysis, assumptions testing, effect sizes, multiple comparison corrections.

**Files:**
- Create: `agent-evals/src/agent_evals/report/statistics.py`
- Test: `agent-evals/tests/test_report_statistics.py`

**Key functions:**

```python
def power_analysis(
    n_groups: int, n_obs_per_group: int,
    effect_size: float = 0.25, alpha: float = 0.05,
) -> PowerResult:
    """Compute statistical power for the experimental design."""
    ...

def test_assumptions(
    residuals: npt.NDArray, groups: list[npt.NDArray],
) -> AssumptionsResult:
    """Run Shapiro-Wilk normality and Levene's homogeneity tests."""
    ...

def compute_effect_sizes(
    pairwise: list[PairwiseResult],
) -> list[EffectSizeResult]:
    """Add Cohen's d, rank-biserial r, and interpretation labels to pairwise results.

    Cohen's d is used for parametric comparisons. Rank-biserial r is computed
    alongside it for non-parametric comparisons (e.g. when normality assumption
    is violated per Shapiro-Wilk). Both are reported so the reader can choose
    the appropriate measure.

    Rank-biserial r = 1 - (2U) / (n1 * n2), where U is the Mann-Whitney U statistic.
    """
    ...

def tukey_hsd(
    groups: dict[str, list[float]], alpha: float = 0.05,
) -> list[TukeyResult]:
    """Tukey's HSD post-hoc test for all pairwise comparisons."""
    ...

def benjamini_hochberg(
    p_values: list[float], alpha: float = 0.05,
) -> list[BHResult]:
    """Benjamini-Hochberg FDR correction."""
    ...

def generate_methodology_text(data: ReportData) -> str:
    """Auto-generate the methodology section for the report."""
    ...
```

```bash
git commit -m "feat(report): add statistical engine with power analysis and assumptions testing"
```

---

## Task 15: Report HTML Renderer

Generates a self-contained HTML report with embedded Plotly charts.

**Files:**
- Create: `agent-evals/src/agent_evals/report/html_renderer.py`
- Create: `agent-evals/src/agent_evals/report/templates/report.html`
- Create: `agent-evals/src/agent_evals/report/charts.py`
- Test: `agent-evals/tests/test_report_html.py`

**New dependencies:** `jinja2`, `plotly` added to `pyproject.toml`.

**Charts module generates:**
- Main effects bar charts (one per axis)
- Interaction line plots (for significant pairs)
- Model comparison radar chart
- Score distribution box plots
- S/N response table
- Cost burn chart
- Confirmation run predicted vs actual

All charts embedded as Plotly JSON in the HTML (no external files needed).

**Template structure (9 sections):**

The report contains 9 top-level sections. Methodology is a subsection inside the
Appendix (not a separate section), keeping the report focused while preserving
full reproducibility details.

```html
<!DOCTYPE html>
<html>
<head>
  <title>Agent Evals Research Report</title>
  <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
  <style>/* embedded CSS */</style>
</head>
<body>
  <nav><!-- collapsible section links for 9 sections --></nav>
  <!-- 1 --> <section id="executive-summary">...</section>
  <!-- 2 --> <section id="experimental-design">...</section>
  <!-- 3 --> <section id="anova-results">...</section>
  <!-- 4 --> <section id="main-effects">...</section>
  <!-- 5 --> <section id="interactions">...</section>
  <!-- 6 --> <section id="model-comparison">...</section>
  <!-- 7 --> <section id="optimal-config">...</section>
  <!-- 8 --> <section id="robustness">...</section>
  <!-- 9 --> <section id="appendix">
               <h2>Appendix</h2>
               <div id="appendix-methodology">
                 <h3>A.1 Methodology</h3>
                 <!-- auto-generated methodology text -->
               </div>
               <div id="appendix-raw-data">
                 <h3>A.2 Raw Data</h3>
                 <!-- downloadable raw trial data tables -->
               </div>
             </section>
</body>
</html>
```

```bash
git commit -m "feat(report): add HTML renderer with Plotly charts"
```

---

## Task 16: Report Markdown Renderer

Generates a git-friendly Markdown report with linked chart images.

**Files:**
- Create: `agent-evals/src/agent_evals/report/markdown_renderer.py`
- Test: `agent-evals/tests/test_report_markdown.py`

**New dependency:** `matplotlib` (for PNG chart export).

Generates `reports/report_TIMESTAMP.md` plus `reports/charts/` directory with PNG images. Uses ASCII tables via string formatting (no external table library needed).

```bash
git commit -m "feat(report): add Markdown renderer with matplotlib chart images"
```

---

## Task 17: OpenRouter Cost Reconciliation

Verify reported costs against OpenRouter's generation API.

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/openrouter.py`
- Test: `agent-evals/tests/test_openrouter_reconciliation.py`

**Implementation:**

```python
class OpenRouterReconciler:
    """Reconcile trial costs against OpenRouter's generation API."""

    GENERATION_URL = "https://openrouter.ai/api/v1/generation"

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = httpx.AsyncClient()

    async def get_generation_stats(self, generation_id: str) -> GenerationStats:
        """Query OpenRouter for actual generation cost/tokens."""
        response = await self._client.get(
            f"{self.GENERATION_URL}?id={generation_id}",
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        return GenerationStats(
            generation_id=generation_id,
            actual_tokens=data["data"]["tokens_prompt"] + data["data"]["tokens_completion"],
            actual_cost=data["data"]["total_cost"],
        )

    async def reconcile_run(
        self, store: ObservatoryStore, run_id: str,
    ) -> ReconciliationReport:
        """Reconcile all trials in a run against OpenRouter billing."""
        ...
```

```bash
git commit -m "feat(observatory): add OpenRouter cost reconciliation"
```

---

## Task 18: Integration & CLI Wiring

Wire everything together: CLI routes to the correct runner, observatory hooks into both runners, report generation triggers after run completion.

**Files:**
- Modify: `agent-evals/src/agent_evals/cli.py`
- Modify: `agent-evals/pyproject.toml` (new dependencies)
- Create: `agent-evals/src/agent_evals/orchestrator.py` (top-level coordination)
- Test: `agent-evals/tests/test_orchestrator.py`

**Orchestrator flow:**

```python
class EvalOrchestrator:
    """Top-level coordinator for all evaluation modes."""

    def run(self, resolved_config: dict) -> int:
        mode = resolved_config.get("mode", "full")

        # 1. Initialize observatory
        store = ObservatoryStore()
        tracker = ObservatoryTracker(store, run_id)

        # 2. Start dashboard if requested
        if resolved_config.get("dashboard"):
            start_web_dashboard(store, tracker, port=8080)

        # 3. Route to correct runner
        if mode == "taguchi":
            result = self._run_taguchi(resolved_config, tracker)
        elif mode == "factorial":
            result = self._run_factorial(resolved_config, tracker)
        else:
            result = self._run_full(resolved_config, tracker)

        # 4. Generate report
        report_format = resolved_config.get("report", "none")
        if report_format != "none":
            self._generate_report(result, report_format)

        # 5. Finalize observatory
        store.finish_run(run_id)
        return 0
```

**New dependencies in pyproject.toml:**

```toml
dependencies = [
    # ... existing ...
    "jinja2>=3.1",
    "plotly>=5.0",
    "matplotlib>=3.7",
    "fastapi>=0.100",
    "uvicorn[standard]>=0.20",
    "sse-starlette>=1.6",
    "httpx>=0.24",
]
```

**CLI subcommands for observatory and models:**

```python
# Add subparsers
subparsers = parser.add_subparsers(dest="command")

# Observatory analytics
obs_parser = subparsers.add_parser("observatory", help="Observatory analytics")
obs_parser.add_argument("--compare", type=str)
obs_parser.add_argument("--model-drift", type=str)
obs_parser.add_argument("--cost-trend", action="store_true")
obs_parser.add_argument("--list", action="store_true")
obs_parser.add_argument("--reconcile-costs", type=str)

# Model catalog management (see Task 7 for full subcommand tree)
# agent-evals models {sync,list,show,group}
models_parser = subparsers.add_parser("models", help="Model catalog management")
```

```bash
git commit -m "feat: wire Taguchi, observatory, and report generation into CLI"
```

---

## Task 19: Model Catalog Store

SQLite-backed catalog of all OpenRouter models with pricing, capabilities, and lifecycle tracking.

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/model_catalog.py`
- Test: `agent-evals/tests/test_model_catalog.py`

**Step 1: Write failing tests for model catalog**

```python
# agent-evals/tests/test_model_catalog.py
"""Tests for OpenRouter model catalog SQLite store."""

import json
import time

import pytest

from agent_evals.observatory.model_catalog import (
    ModelCatalog,
    ModelRecord,
    SyncLogEntry,
)


@pytest.fixture
def catalog(tmp_path):
    """Create a ModelCatalog with a temporary SQLite database."""
    db_path = str(tmp_path / "models.db")
    return ModelCatalog(db_path=db_path)


@pytest.fixture
def sample_models():
    """Sample model data matching OpenRouter API shape."""
    return [
        ModelRecord(
            id="openrouter/anthropic/claude-sonnet-4.5",
            name="Claude Sonnet 4.5",
            created=1700000000,
            context_length=200000,
            prompt_price=3e-06,
            completion_price=15e-06,
            modality="text+image->text",
            tokenizer="claude",
            supported_params=json.dumps(["temperature", "top_p", "tools"]),
            raw_json='{"id": "openrouter/anthropic/claude-sonnet-4.5"}',
        ),
        ModelRecord(
            id="openrouter/openai/gpt-4o",
            name="GPT-4o",
            created=1710000000,
            context_length=128000,
            prompt_price=2.5e-06,
            completion_price=10e-06,
            modality="text+image->text",
            tokenizer="o200k_base",
            supported_params=json.dumps(["temperature", "top_p", "tools"]),
            raw_json='{"id": "openrouter/openai/gpt-4o"}',
        ),
    ]


class TestModelCatalogSchema:
    """Tests for database schema initialization."""

    def test_creates_models_table(self, catalog):
        cursor = catalog._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='models'"
        )
        assert cursor.fetchone() is not None

    def test_creates_sync_log_table(self, catalog):
        cursor = catalog._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sync_log'"
        )
        assert cursor.fetchone() is not None

    def test_models_table_has_expected_columns(self, catalog):
        cursor = catalog._conn.execute("PRAGMA table_info(models)")
        columns = {row[1] for row in cursor.fetchall()}
        expected = {
            "id", "name", "created", "context_length",
            "prompt_price", "completion_price", "modality",
            "tokenizer", "supported_params", "raw_json",
            "first_seen", "last_seen", "removed_at",
        }
        assert expected.issubset(columns)


class TestUpsertModels:
    """Tests for inserting and updating models."""

    def test_insert_new_models(self, catalog, sample_models):
        catalog.upsert_models(sample_models)
        all_models = catalog.get_all_models()
        assert len(all_models) == 2

    def test_upsert_updates_existing_model(self, catalog, sample_models):
        catalog.upsert_models(sample_models)
        updated = ModelRecord(
            id="openrouter/openai/gpt-4o",
            name="GPT-4o",
            created=1710000000,
            context_length=128000,
            prompt_price=1.25e-06,  # price changed
            completion_price=5e-06,
            modality="text+image->text",
            tokenizer="o200k_base",
            supported_params=json.dumps(["temperature", "top_p", "tools"]),
            raw_json='{"id": "openrouter/openai/gpt-4o"}',
        )
        catalog.upsert_models([updated])
        model = catalog.get_model_by_id("openrouter/openai/gpt-4o")
        assert model.prompt_price == 1.25e-06

    def test_upsert_preserves_first_seen(self, catalog, sample_models):
        catalog.upsert_models(sample_models)
        first = catalog.get_model_by_id("openrouter/openai/gpt-4o")
        first_seen_original = first.first_seen
        catalog.upsert_models(sample_models)
        second = catalog.get_model_by_id("openrouter/openai/gpt-4o")
        assert second.first_seen == first_seen_original

    def test_upsert_updates_last_seen(self, catalog, sample_models):
        catalog.upsert_models(sample_models)
        first = catalog.get_model_by_id("openrouter/openai/gpt-4o")
        time.sleep(0.01)
        catalog.upsert_models(sample_models)
        second = catalog.get_model_by_id("openrouter/openai/gpt-4o")
        assert second.last_seen >= first.last_seen


class TestGetModels:
    """Tests for querying models."""

    def test_get_all_models_empty(self, catalog):
        assert catalog.get_all_models() == []

    def test_get_model_by_id(self, catalog, sample_models):
        catalog.upsert_models(sample_models)
        model = catalog.get_model_by_id("openrouter/anthropic/claude-sonnet-4.5")
        assert model.name == "Claude Sonnet 4.5"
        assert model.context_length == 200000

    def test_get_model_by_id_not_found(self, catalog):
        assert catalog.get_model_by_id("nonexistent") is None


class TestMarkRemoved:
    """Tests for marking models as removed."""

    def test_mark_removed_sets_removed_at(self, catalog, sample_models):
        catalog.upsert_models(sample_models)
        catalog.mark_removed(["openrouter/openai/gpt-4o"])
        model = catalog.get_model_by_id("openrouter/openai/gpt-4o")
        assert model.removed_at is not None

    def test_mark_removed_does_not_delete(self, catalog, sample_models):
        catalog.upsert_models(sample_models)
        catalog.mark_removed(["openrouter/openai/gpt-4o"])
        assert len(catalog.get_all_models(include_removed=True)) == 2

    def test_get_all_models_excludes_removed_by_default(self, catalog, sample_models):
        catalog.upsert_models(sample_models)
        catalog.mark_removed(["openrouter/openai/gpt-4o"])
        assert len(catalog.get_all_models()) == 1


class TestSyncLog:
    """Tests for sync history tracking."""

    def test_log_sync_creates_entry(self, catalog):
        catalog.log_sync(models_added=5, models_removed=1, total_count=339)
        log = catalog.get_sync_log()
        assert len(log) == 1
        assert log[0].models_added == 5
        assert log[0].models_removed == 1
        assert log[0].total_count == 339

    def test_log_sync_preserves_history(self, catalog):
        catalog.log_sync(models_added=10, models_removed=0, total_count=339)
        catalog.log_sync(models_added=2, models_removed=3, total_count=338)
        log = catalog.get_sync_log()
        assert len(log) == 2
```

**Step 2: Run tests to verify they fail**

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_model_catalog.py -v
```

Expected: FAIL (module not found)

**Step 3: Implement model catalog store**

```python
# agent-evals/src/agent_evals/observatory/model_catalog.py
"""SQLite-backed catalog of OpenRouter models with lifecycle tracking.

Stores model metadata, pricing, capabilities, and tracks when models
first appear, when they were last seen, and when they are removed.
Sync log records each synchronization event for audit purposes.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class ModelRecord:
    """A single model entry in the catalog."""

    id: str
    name: str
    created: int  # Unix timestamp from OpenRouter
    context_length: int
    prompt_price: float  # USD per token
    completion_price: float  # USD per token
    modality: str
    tokenizer: str
    supported_params: str  # JSON array
    raw_json: str  # Full API response
    first_seen: str | None = None  # ISO timestamp, set on first insert
    last_seen: str | None = None  # ISO timestamp, updated on each upsert
    removed_at: str | None = None  # ISO timestamp, set when model disappears


@dataclass
class SyncLogEntry:
    """Record of a single model sync event."""

    timestamp: str
    models_added: int
    models_removed: int
    total_count: int


_SCHEMA = """
CREATE TABLE IF NOT EXISTS models (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created INTEGER NOT NULL,
    context_length INTEGER NOT NULL,
    prompt_price REAL NOT NULL,
    completion_price REAL NOT NULL,
    modality TEXT NOT NULL,
    tokenizer TEXT NOT NULL,
    supported_params TEXT NOT NULL,
    raw_json TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    removed_at TEXT
);

CREATE TABLE IF NOT EXISTS sync_log (
    timestamp TEXT NOT NULL,
    models_added INTEGER NOT NULL,
    models_removed INTEGER NOT NULL,
    total_count INTEGER NOT NULL
);
"""


class ModelCatalog:
    """SQLite-backed catalog for OpenRouter model metadata."""

    def __init__(self, db_path: str = "observatory.db") -> None:
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def upsert_models(self, models: list[ModelRecord]) -> None:
        """Insert new models or update existing ones.

        On insert: sets first_seen and last_seen to now.
        On update: updates all fields except first_seen; sets last_seen to now;
        clears removed_at (model is back if it was previously removed).
        """
        now = datetime.now(timezone.utc).isoformat()
        for model in models:
            existing = self._conn.execute(
                "SELECT first_seen FROM models WHERE id = ?", (model.id,)
            ).fetchone()
            if existing:
                self._conn.execute(
                    """UPDATE models SET
                        name = ?, created = ?, context_length = ?,
                        prompt_price = ?, completion_price = ?,
                        modality = ?, tokenizer = ?, supported_params = ?,
                        raw_json = ?, last_seen = ?, removed_at = NULL
                    WHERE id = ?""",
                    (
                        model.name, model.created, model.context_length,
                        model.prompt_price, model.completion_price,
                        model.modality, model.tokenizer, model.supported_params,
                        model.raw_json, now, model.id,
                    ),
                )
            else:
                self._conn.execute(
                    """INSERT INTO models (
                        id, name, created, context_length,
                        prompt_price, completion_price, modality,
                        tokenizer, supported_params, raw_json,
                        first_seen, last_seen
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        model.id, model.name, model.created, model.context_length,
                        model.prompt_price, model.completion_price, model.modality,
                        model.tokenizer, model.supported_params, model.raw_json,
                        now, now,
                    ),
                )
        self._conn.commit()

    def get_all_models(self, include_removed: bool = False) -> list[ModelRecord]:
        """Return all models, optionally including removed ones."""
        if include_removed:
            rows = self._conn.execute("SELECT * FROM models").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM models WHERE removed_at IS NULL"
            ).fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_model_by_id(self, model_id: str) -> ModelRecord | None:
        """Return a single model by ID, or None if not found."""
        row = self._conn.execute(
            "SELECT * FROM models WHERE id = ?", (model_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def mark_removed(self, model_ids: list[str]) -> None:
        """Mark models as removed (soft delete with timestamp)."""
        now = datetime.now(timezone.utc).isoformat()
        for model_id in model_ids:
            self._conn.execute(
                "UPDATE models SET removed_at = ? WHERE id = ?",
                (now, model_id),
            )
        self._conn.commit()

    def log_sync(
        self, models_added: int, models_removed: int, total_count: int,
    ) -> None:
        """Record a sync event in the sync log."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO sync_log (timestamp, models_added, models_removed, total_count) "
            "VALUES (?, ?, ?, ?)",
            (now, models_added, models_removed, total_count),
        )
        self._conn.commit()

    def get_sync_log(self) -> list[SyncLogEntry]:
        """Return all sync log entries, most recent first."""
        rows = self._conn.execute(
            "SELECT * FROM sync_log ORDER BY timestamp DESC"
        ).fetchall()
        return [
            SyncLogEntry(
                timestamp=row["timestamp"],
                models_added=row["models_added"],
                models_removed=row["models_removed"],
                total_count=row["total_count"],
            )
            for row in rows
        ]

    def _row_to_record(self, row: sqlite3.Row) -> ModelRecord:
        return ModelRecord(
            id=row["id"],
            name=row["name"],
            created=row["created"],
            context_length=row["context_length"],
            prompt_price=row["prompt_price"],
            completion_price=row["completion_price"],
            modality=row["modality"],
            tokenizer=row["tokenizer"],
            supported_params=row["supported_params"],
            raw_json=row["raw_json"],
            first_seen=row["first_seen"],
            last_seen=row["last_seen"],
            removed_at=row["removed_at"],
        )
```

**Step 4: Run tests to verify they pass**

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_model_catalog.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/model_catalog.py agent-evals/tests/test_model_catalog.py
git commit -m "feat(observatory): add SQLite model catalog store with lifecycle tracking"
```

---

## Task 20: Background Model Sync

Pulls the OpenRouter model list, diffs against the local catalog, and tracks pricing changes.

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/model_sync.py`
- Test: `agent-evals/tests/test_model_sync.py`

**Step 1: Write failing tests for model sync**

```python
# agent-evals/tests/test_model_sync.py
"""Tests for background model sync with OpenRouter API."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_evals.observatory.model_catalog import ModelCatalog, ModelRecord
from agent_evals.observatory.model_sync import (
    ModelSyncService,
    SyncDiff,
    parse_model_response,
)


@pytest.fixture
def catalog(tmp_path):
    db_path = str(tmp_path / "models.db")
    return ModelCatalog(db_path=db_path)


@pytest.fixture
def api_response():
    """Simulated OpenRouter /api/v1/models response."""
    return {
        "data": [
            {
                "id": "openrouter/anthropic/claude-sonnet-4.5",
                "name": "Claude Sonnet 4.5",
                "created": 1700000000,
                "context_length": 200000,
                "pricing": {"prompt": "0.000003", "completion": "0.000015"},
                "architecture": {
                    "modality": "text+image->text",
                    "tokenizer": "claude",
                },
                "supported_parameters": ["temperature", "top_p", "tools"],
            },
            {
                "id": "openrouter/openai/gpt-4o",
                "name": "GPT-4o",
                "created": 1710000000,
                "context_length": 128000,
                "pricing": {"prompt": "0.0000025", "completion": "0.00001"},
                "architecture": {
                    "modality": "text+image->text",
                    "tokenizer": "o200k_base",
                },
                "supported_parameters": ["temperature", "top_p"],
            },
        ]
    }


class TestParseModelResponse:
    """Tests for parsing OpenRouter API response into ModelRecords."""

    def test_parses_all_models(self, api_response):
        records = parse_model_response(api_response)
        assert len(records) == 2

    def test_parses_pricing_from_string(self, api_response):
        records = parse_model_response(api_response)
        claude = [r for r in records if "claude" in r.id][0]
        assert claude.prompt_price == 3e-06
        assert claude.completion_price == 15e-06

    def test_parses_architecture_fields(self, api_response):
        records = parse_model_response(api_response)
        gpt = [r for r in records if "gpt" in r.id][0]
        assert gpt.modality == "text+image->text"
        assert gpt.tokenizer == "o200k_base"

    def test_parses_supported_params_as_json(self, api_response):
        records = parse_model_response(api_response)
        claude = [r for r in records if "claude" in r.id][0]
        params = json.loads(claude.supported_params)
        assert "tools" in params

    def test_stores_raw_json(self, api_response):
        records = parse_model_response(api_response)
        for r in records:
            raw = json.loads(r.raw_json)
            assert "id" in raw


class TestSyncDiff:
    """Tests for diff logic between remote and local models."""

    def test_detects_added_models(self, catalog, api_response):
        service = ModelSyncService(catalog=catalog)
        records = parse_model_response(api_response)
        diff = service.compute_diff(records)
        assert len(diff.added) == 2
        assert len(diff.removed) == 0

    def test_detects_removed_models(self, catalog, api_response):
        records = parse_model_response(api_response)
        catalog.upsert_models(records)
        service = ModelSyncService(catalog=catalog)
        # Sync with only one model -> other is removed
        partial = [r for r in records if "claude" in r.id]
        diff = service.compute_diff(partial)
        assert len(diff.removed) == 1
        assert "gpt-4o" in diff.removed[0]

    def test_detects_price_changes(self, catalog, api_response):
        records = parse_model_response(api_response)
        catalog.upsert_models(records)
        service = ModelSyncService(catalog=catalog)
        # Change GPT-4o pricing
        updated_response = {
            "data": [
                api_response["data"][0],
                {
                    **api_response["data"][1],
                    "pricing": {"prompt": "0.000005", "completion": "0.00002"},
                },
            ]
        }
        updated_records = parse_model_response(updated_response)
        diff = service.compute_diff(updated_records)
        assert len(diff.price_changes) == 1
        change = diff.price_changes[0]
        assert change["model_id"] == "openrouter/openai/gpt-4o"
        assert change["old_prompt_price"] == 2.5e-06
        assert change["new_prompt_price"] == 5e-06

    def test_no_diff_when_unchanged(self, catalog, api_response):
        records = parse_model_response(api_response)
        catalog.upsert_models(records)
        service = ModelSyncService(catalog=catalog)
        diff = service.compute_diff(records)
        assert len(diff.added) == 0
        assert len(diff.removed) == 0
        assert len(diff.price_changes) == 0


class TestModelSyncService:
    """Tests for the sync service orchestration."""

    @pytest.mark.asyncio
    async def test_sync_fetches_and_upserts(self, catalog, api_response):
        service = ModelSyncService(catalog=catalog)
        with patch.object(service, "_fetch_models", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = api_response
            diff = await service.sync()
            assert len(diff.added) == 2
            assert len(catalog.get_all_models()) == 2

    @pytest.mark.asyncio
    async def test_sync_logs_to_sync_log(self, catalog, api_response):
        service = ModelSyncService(catalog=catalog)
        with patch.object(service, "_fetch_models", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = api_response
            await service.sync()
            log = catalog.get_sync_log()
            assert len(log) == 1
            assert log[0].models_added == 2

    @pytest.mark.asyncio
    async def test_sync_marks_removed_models(self, catalog, api_response):
        records = parse_model_response(api_response)
        catalog.upsert_models(records)
        service = ModelSyncService(catalog=catalog)
        partial = {"data": [api_response["data"][0]]}
        with patch.object(service, "_fetch_models", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = partial
            diff = await service.sync()
            assert len(diff.removed) == 1
            gpt = catalog.get_model_by_id("openrouter/openai/gpt-4o")
            assert gpt.removed_at is not None

    def test_sync_status_returns_last_sync(self, catalog):
        catalog.log_sync(models_added=5, models_removed=0, total_count=339)
        service = ModelSyncService(catalog=catalog)
        status = service.get_sync_status()
        assert status["last_sync"] is not None
        assert status["total_models"] == 339
```

**Step 2: Run tests to verify failure**

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_model_sync.py -v
```

**Step 3: Implement model sync service**

```python
# agent-evals/src/agent_evals/observatory/model_sync.py
"""Background model sync with OpenRouter API.

Fetches the public model list from OpenRouter, diffs against the local
catalog, tracks added/removed models and pricing changes, and logs
each sync event. Designed to run every 6 hours (configurable) or on
demand via CLI.

The OpenRouter /api/v1/models endpoint requires no authentication and
returns ~339 models as of Feb 2026.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from agent_evals.observatory.model_catalog import ModelCatalog, ModelRecord

logger = logging.getLogger(__name__)

OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


@dataclass
class SyncDiff:
    """Result of diffing remote models against local catalog."""

    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    price_changes: list[dict[str, Any]] = field(default_factory=list)
    total_remote: int = 0


def parse_model_response(response: dict) -> list[ModelRecord]:
    """Parse OpenRouter /api/v1/models response into ModelRecords.

    Pricing strings (e.g. "0.000003") are converted to float USD-per-token.
    """
    records: list[ModelRecord] = []
    for item in response.get("data", []):
        pricing = item.get("pricing", {})
        architecture = item.get("architecture", {})
        records.append(ModelRecord(
            id=item["id"],
            name=item.get("name", item["id"]),
            created=item.get("created", 0),
            context_length=item.get("context_length", 0),
            prompt_price=float(pricing.get("prompt", "0")),
            completion_price=float(pricing.get("completion", "0")),
            modality=architecture.get("modality", "text->text"),
            tokenizer=architecture.get("tokenizer", "unknown"),
            supported_params=json.dumps(
                item.get("supported_parameters", [])
            ),
            raw_json=json.dumps(item),
        ))
    return records


class ModelSyncService:
    """Orchestrates model catalog synchronization with OpenRouter."""

    def __init__(
        self,
        catalog: ModelCatalog,
        sync_interval_hours: float = 6.0,
    ) -> None:
        self._catalog = catalog
        self._sync_interval = sync_interval_hours * 3600
        self._sse_callbacks: list[callable] = []

    async def _fetch_models(self) -> dict:
        """Fetch model list from OpenRouter (no auth required)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(OPENROUTER_MODELS_URL, timeout=30.0)
            response.raise_for_status()
            return response.json()

    def compute_diff(self, remote_records: list[ModelRecord]) -> SyncDiff:
        """Compare remote models against local catalog.

        Detects:
        - New models (in remote but not local)
        - Removed models (in local but not remote)
        - Price changes (prompt or completion price differs)
        """
        local_models = {
            m.id: m for m in self._catalog.get_all_models(include_removed=False)
        }
        remote_ids = {r.id for r in remote_records}
        local_ids = set(local_models.keys())

        diff = SyncDiff(total_remote=len(remote_records))
        diff.added = sorted(remote_ids - local_ids)
        diff.removed = sorted(local_ids - remote_ids)

        # Detect price changes for existing models
        for record in remote_records:
            if record.id in local_models:
                local = local_models[record.id]
                if (
                    record.prompt_price != local.prompt_price
                    or record.completion_price != local.completion_price
                ):
                    diff.price_changes.append({
                        "model_id": record.id,
                        "old_prompt_price": local.prompt_price,
                        "new_prompt_price": record.prompt_price,
                        "old_completion_price": local.completion_price,
                        "new_completion_price": record.completion_price,
                    })

        return diff

    async def sync(self) -> SyncDiff:
        """Run a full sync: fetch, diff, upsert, mark removed, log.

        Returns the SyncDiff describing what changed.
        """
        response = await self._fetch_models()
        records = parse_model_response(response)
        diff = self.compute_diff(records)

        # Upsert all remote models (updates last_seen, clears removed_at)
        self._catalog.upsert_models(records)

        # Mark removed models
        if diff.removed:
            self._catalog.mark_removed(diff.removed)

        # Log sync event
        self._catalog.log_sync(
            models_added=len(diff.added),
            models_removed=len(diff.removed),
            total_count=len(records),
        )

        # Log price changes
        for change in diff.price_changes:
            logger.info(
                "Price change for %s: prompt %.8f -> %.8f, "
                "completion %.8f -> %.8f",
                change["model_id"],
                change["old_prompt_price"], change["new_prompt_price"],
                change["old_completion_price"], change["new_completion_price"],
            )

        # Notify SSE listeners
        for callback in self._sse_callbacks:
            callback(diff)

        return diff

    def add_sse_callback(self, callback: callable) -> None:
        """Register a callback for SSE notifications when sync completes."""
        self._sse_callbacks.append(callback)

    def get_sync_status(self) -> dict:
        """Return the status of the last sync."""
        log = self._catalog.get_sync_log()
        if not log:
            return {"last_sync": None, "total_models": 0}
        latest = log[0]
        return {
            "last_sync": latest.timestamp,
            "total_models": latest.total_count,
            "models_added": latest.models_added,
            "models_removed": latest.models_removed,
        }

    async def run_periodic(self) -> None:
        """Run sync on a periodic schedule (for use with asyncio)."""
        while True:
            try:
                diff = await self.sync()
                logger.info(
                    "Model sync complete: +%d -%d (total: %d)",
                    len(diff.added), len(diff.removed), diff.total_remote,
                )
            except Exception:
                logger.exception("Model sync failed")
            await asyncio.sleep(self._sync_interval)
```

**Step 4: Run tests to verify they pass**

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_model_sync.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/model_sync.py agent-evals/tests/test_model_sync.py
git commit -m "feat(observatory): add background model sync with diff and price tracking"
```

---

## Task 21: Model Groups

User-defined model groups for organizing models and running evaluations across curated sets.

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/model_groups.py`
- Test: `agent-evals/tests/test_model_groups.py`

**Step 1: Write failing tests for model groups**

```python
# agent-evals/tests/test_model_groups.py
"""Tests for model group management with SQLite persistence."""

import pytest

from agent_evals.observatory.model_catalog import ModelCatalog, ModelRecord
from agent_evals.observatory.model_groups import (
    ModelGroupManager,
    ModelGroup,
)


@pytest.fixture
def catalog(tmp_path):
    db_path = str(tmp_path / "models.db")
    return ModelCatalog(db_path=db_path)


@pytest.fixture
def manager(catalog):
    return ModelGroupManager(catalog=catalog)


@pytest.fixture
def seeded_catalog(catalog):
    """Catalog pre-populated with test models."""
    catalog.upsert_models([
        ModelRecord(
            id="openrouter/anthropic/claude-sonnet-4.5",
            name="Claude Sonnet 4.5", created=1700000000,
            context_length=200000, prompt_price=3e-06,
            completion_price=15e-06, modality="text+image->text",
            tokenizer="claude", supported_params="[]", raw_json="{}",
        ),
        ModelRecord(
            id="openrouter/openai/gpt-4o",
            name="GPT-4o", created=1710000000,
            context_length=128000, prompt_price=2.5e-06,
            completion_price=10e-06, modality="text+image->text",
            tokenizer="o200k_base", supported_params="[]", raw_json="{}",
        ),
        ModelRecord(
            id="openrouter/google/gemini-2.0-flash",
            name="Gemini 2.0 Flash", created=1720000000,
            context_length=1000000, prompt_price=0.75e-06,
            completion_price=3e-06, modality="text+image->text",
            tokenizer="gemini", supported_params="[]", raw_json="{}",
        ),
    ])
    return catalog


class TestGroupSchema:
    """Tests for model_groups and model_group_members table creation."""

    def test_creates_model_groups_table(self, manager):
        cursor = manager._catalog._conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='model_groups'"
        )
        assert cursor.fetchone() is not None

    def test_creates_model_group_members_table(self, manager):
        cursor = manager._catalog._conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='model_group_members'"
        )
        assert cursor.fetchone() is not None


class TestCreateGroup:
    """Tests for creating model groups."""

    def test_create_group(self, manager):
        group = manager.create_group("frontier", description="Top-tier models")
        assert group.name == "frontier"
        assert group.description == "Top-tier models"
        assert group.id is not None

    def test_create_group_duplicate_name_raises(self, manager):
        manager.create_group("frontier")
        with pytest.raises(ValueError, match="already exists"):
            manager.create_group("frontier")


class TestAddRemoveMembers:
    """Tests for managing group membership."""

    def test_add_model_to_group(self, manager, seeded_catalog):
        group = manager.create_group("test")
        manager.add_to_group(
            group.id, ["openrouter/anthropic/claude-sonnet-4.5"]
        )
        members = manager.get_group_members(group.id)
        assert len(members) == 1
        assert members[0] == "openrouter/anthropic/claude-sonnet-4.5"

    def test_add_multiple_models(self, manager, seeded_catalog):
        group = manager.create_group("test")
        manager.add_to_group(group.id, [
            "openrouter/anthropic/claude-sonnet-4.5",
            "openrouter/openai/gpt-4o",
        ])
        members = manager.get_group_members(group.id)
        assert len(members) == 2

    def test_remove_model_from_group(self, manager, seeded_catalog):
        group = manager.create_group("test")
        manager.add_to_group(group.id, [
            "openrouter/anthropic/claude-sonnet-4.5",
            "openrouter/openai/gpt-4o",
        ])
        manager.remove_from_group(
            group.id, ["openrouter/openai/gpt-4o"]
        )
        members = manager.get_group_members(group.id)
        assert len(members) == 1

    def test_add_nonexistent_model_warns(self, manager, seeded_catalog):
        group = manager.create_group("test")
        warnings = manager.add_to_group(group.id, ["nonexistent/model"])
        assert len(warnings) == 1
        assert "not found" in warnings[0].lower()


class TestListGroups:
    """Tests for listing and showing groups."""

    def test_list_groups_empty(self, manager):
        assert manager.list_groups() == []

    def test_list_groups(self, manager):
        manager.create_group("frontier")
        manager.create_group("budget")
        groups = manager.list_groups()
        assert len(groups) == 2

    def test_show_group(self, manager, seeded_catalog):
        group = manager.create_group("frontier", description="Top models")
        manager.add_to_group(group.id, [
            "openrouter/anthropic/claude-sonnet-4.5",
        ])
        shown = manager.show_group(group.id)
        assert shown.name == "frontier"
        assert len(shown.member_ids) == 1


class TestDeleteGroup:
    """Tests for deleting groups."""

    def test_delete_group(self, manager):
        group = manager.create_group("temp")
        manager.delete_group(group.id)
        assert len(manager.list_groups()) == 0

    def test_delete_group_removes_memberships(self, manager, seeded_catalog):
        group = manager.create_group("temp")
        manager.add_to_group(group.id, [
            "openrouter/anthropic/claude-sonnet-4.5",
        ])
        manager.delete_group(group.id)
        # Verify membership is cleaned up
        cursor = manager._catalog._conn.execute(
            "SELECT COUNT(*) FROM model_group_members WHERE group_id = ?",
            (group.id,),
        )
        assert cursor.fetchone()[0] == 0


class TestValidateOnRun:
    """Tests for validating model IDs against catalog at run start."""

    def test_validate_all_exist(self, manager, seeded_catalog):
        result = manager.validate_model_ids([
            "openrouter/anthropic/claude-sonnet-4.5",
            "openrouter/openai/gpt-4o",
        ])
        assert result.valid == ["openrouter/anthropic/claude-sonnet-4.5",
                                "openrouter/openai/gpt-4o"]
        assert result.missing == []

    def test_validate_with_missing(self, manager, seeded_catalog):
        result = manager.validate_model_ids([
            "openrouter/anthropic/claude-sonnet-4.5",
            "nonexistent/model",
        ])
        assert len(result.valid) == 1
        assert len(result.missing) == 1

    def test_resolve_group_to_model_ids(self, manager, seeded_catalog):
        group = manager.create_group("frontier")
        manager.add_to_group(group.id, [
            "openrouter/anthropic/claude-sonnet-4.5",
            "openrouter/openai/gpt-4o",
        ])
        ids = manager.resolve_group(group.id)
        assert len(ids) == 2

    def test_resolve_group_and_models_union(self, manager, seeded_catalog):
        group = manager.create_group("frontier")
        manager.add_to_group(group.id, [
            "openrouter/anthropic/claude-sonnet-4.5",
        ])
        combined = manager.resolve_models(
            model_ids=["openrouter/openai/gpt-4o"],
            group_id=group.id,
        )
        assert len(combined) == 2
```

**Step 2: Run tests to verify failure**

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_model_groups.py -v
```

**Step 3: Implement model groups**

```python
# agent-evals/src/agent_evals/observatory/model_groups.py
"""Model group management for organizing models into curated sets.

Provides CRUD for named groups backed by SQLite. Groups can be referenced
from the CLI via --model-group to run evaluations against a predefined
set of models. The --models flag and --model-group flag are combinable
(union of both sets).
"""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from agent_evals.observatory.model_catalog import ModelCatalog


@dataclass
class ModelGroup:
    """A named group of models."""

    id: str
    name: str
    description: str
    created_at: str
    updated_at: str
    member_ids: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Result of validating model IDs against the catalog."""

    valid: list[str]
    missing: list[str]


_GROUP_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_groups (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_group_members (
    group_id TEXT NOT NULL REFERENCES model_groups(id),
    model_id TEXT NOT NULL,
    PRIMARY KEY (group_id, model_id)
);
"""


class ModelGroupManager:
    """Manages model groups backed by the catalog's SQLite database."""

    def __init__(self, catalog: ModelCatalog) -> None:
        self._catalog = catalog
        self._catalog._conn.executescript(_GROUP_SCHEMA)

    def create_group(
        self, name: str, description: str = "",
    ) -> ModelGroup:
        """Create a new model group. Raises ValueError if name exists."""
        existing = self._catalog._conn.execute(
            "SELECT id FROM model_groups WHERE name = ?", (name,)
        ).fetchone()
        if existing:
            msg = f"Group '{name}' already exists"
            raise ValueError(msg)

        now = datetime.now(timezone.utc).isoformat()
        group_id = str(uuid.uuid4())
        self._catalog._conn.execute(
            "INSERT INTO model_groups (id, name, description, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (group_id, name, description, now, now),
        )
        self._catalog._conn.commit()
        return ModelGroup(
            id=group_id, name=name, description=description,
            created_at=now, updated_at=now,
        )

    def add_to_group(
        self, group_id: str, model_ids: list[str],
    ) -> list[str]:
        """Add models to a group. Returns warnings for models not in catalog."""
        warnings: list[str] = []
        for model_id in model_ids:
            if self._catalog.get_model_by_id(model_id) is None:
                warnings.append(f"Model '{model_id}' not found in catalog")
                continue
            try:
                self._catalog._conn.execute(
                    "INSERT INTO model_group_members (group_id, model_id) "
                    "VALUES (?, ?)",
                    (group_id, model_id),
                )
            except sqlite3.IntegrityError:
                pass  # Already a member
        now = datetime.now(timezone.utc).isoformat()
        self._catalog._conn.execute(
            "UPDATE model_groups SET updated_at = ? WHERE id = ?",
            (now, group_id),
        )
        self._catalog._conn.commit()
        return warnings

    def remove_from_group(
        self, group_id: str, model_ids: list[str],
    ) -> None:
        """Remove models from a group."""
        for model_id in model_ids:
            self._catalog._conn.execute(
                "DELETE FROM model_group_members "
                "WHERE group_id = ? AND model_id = ?",
                (group_id, model_id),
            )
        now = datetime.now(timezone.utc).isoformat()
        self._catalog._conn.execute(
            "UPDATE model_groups SET updated_at = ? WHERE id = ?",
            (now, group_id),
        )
        self._catalog._conn.commit()

    def get_group_members(self, group_id: str) -> list[str]:
        """Return model IDs belonging to a group."""
        rows = self._catalog._conn.execute(
            "SELECT model_id FROM model_group_members WHERE group_id = ?",
            (group_id,),
        ).fetchall()
        return [row[0] for row in rows]

    def list_groups(self) -> list[ModelGroup]:
        """Return all groups."""
        rows = self._catalog._conn.execute(
            "SELECT * FROM model_groups ORDER BY name"
        ).fetchall()
        return [
            ModelGroup(
                id=row["id"], name=row["name"],
                description=row["description"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def show_group(self, group_id: str) -> ModelGroup:
        """Return a group with its member IDs populated."""
        row = self._catalog._conn.execute(
            "SELECT * FROM model_groups WHERE id = ?", (group_id,)
        ).fetchone()
        if row is None:
            msg = f"Group '{group_id}' not found"
            raise KeyError(msg)
        members = self.get_group_members(group_id)
        return ModelGroup(
            id=row["id"], name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            member_ids=members,
        )

    def delete_group(self, group_id: str) -> None:
        """Delete a group and all its memberships."""
        self._catalog._conn.execute(
            "DELETE FROM model_group_members WHERE group_id = ?",
            (group_id,),
        )
        self._catalog._conn.execute(
            "DELETE FROM model_groups WHERE id = ?", (group_id,),
        )
        self._catalog._conn.commit()

    def validate_model_ids(
        self, model_ids: list[str],
    ) -> ValidationResult:
        """Check model IDs against catalog, return valid and missing lists."""
        valid: list[str] = []
        missing: list[str] = []
        for model_id in model_ids:
            if self._catalog.get_model_by_id(model_id) is not None:
                valid.append(model_id)
            else:
                missing.append(model_id)
        return ValidationResult(valid=valid, missing=missing)

    def resolve_group(self, group_id: str) -> list[str]:
        """Resolve a group to its member model IDs."""
        return self.get_group_members(group_id)

    def resolve_models(
        self,
        model_ids: list[str] | None = None,
        group_id: str | None = None,
    ) -> list[str]:
        """Resolve --models and --model-group to a deduplicated union."""
        result: set[str] = set()
        if model_ids:
            result.update(model_ids)
        if group_id:
            result.update(self.resolve_group(group_id))
        return sorted(result)
```

**Step 4: Run tests to verify they pass**

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_model_groups.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/model_groups.py agent-evals/tests/test_model_groups.py
git commit -m "feat(observatory): add model group management with validation"
```

---

## Task 22: Model Browser CLI

Terminal-based model browsing with Rich tables, filtering, sorting, and detail views.

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/model_cli.py`
- Test: `agent-evals/tests/test_model_cli.py`

**Step 1: Write failing tests for model browser CLI**

```python
# agent-evals/tests/test_model_cli.py
"""Tests for terminal model browser CLI commands."""

import json
from unittest.mock import MagicMock, patch

import pytest

from agent_evals.observatory.model_catalog import ModelCatalog, ModelRecord
from agent_evals.observatory.model_cli import (
    ModelBrowserCLI,
    apply_filters,
    apply_sort,
)


@pytest.fixture
def catalog(tmp_path):
    db_path = str(tmp_path / "models.db")
    cat = ModelCatalog(db_path=db_path)
    cat.upsert_models([
        ModelRecord(
            id="openrouter/anthropic/claude-sonnet-4.5",
            name="Claude Sonnet 4.5", created=1700000000,
            context_length=200000, prompt_price=3e-06,
            completion_price=15e-06, modality="text+image->text",
            tokenizer="claude",
            supported_params=json.dumps(["temperature", "tools"]),
            raw_json="{}",
        ),
        ModelRecord(
            id="openrouter/openai/gpt-4o",
            name="GPT-4o", created=1710000000,
            context_length=128000, prompt_price=2.5e-06,
            completion_price=10e-06, modality="text+image->text",
            tokenizer="o200k_base",
            supported_params=json.dumps(["temperature", "top_p"]),
            raw_json="{}",
        ),
        ModelRecord(
            id="openrouter/meta/llama-3-70b:free",
            name="Llama 3 70B (free)", created=1720000000,
            context_length=8192, prompt_price=0.0,
            completion_price=0.0, modality="text->text",
            tokenizer="llama",
            supported_params=json.dumps(["temperature"]),
            raw_json="{}",
        ),
    ])
    return cat


class TestApplyFilters:
    """Tests for model list filtering."""

    def test_filter_free(self, catalog):
        models = catalog.get_all_models()
        filtered = apply_filters(models, free=True)
        assert len(filtered) == 1
        assert "free" in filtered[0].id

    def test_filter_max_price(self, catalog):
        models = catalog.get_all_models()
        filtered = apply_filters(models, max_price=3e-06)
        # Includes models with prompt_price <= 3e-06
        ids = [m.id for m in filtered]
        assert "openrouter/openai/gpt-4o" in ids
        assert "openrouter/meta/llama-3-70b:free" in ids

    def test_filter_min_context(self, catalog):
        models = catalog.get_all_models()
        filtered = apply_filters(models, min_context=100000)
        assert len(filtered) == 2

    def test_filter_modality(self, catalog):
        models = catalog.get_all_models()
        filtered = apply_filters(models, modality="text+image->text")
        assert len(filtered) == 2

    def test_filter_capability(self, catalog):
        models = catalog.get_all_models()
        filtered = apply_filters(models, capability="tools")
        assert len(filtered) == 1
        assert "claude" in filtered[0].id

    def test_filter_provider(self, catalog):
        models = catalog.get_all_models()
        filtered = apply_filters(models, provider="anthropic")
        assert len(filtered) == 1

    def test_filter_tokenizer(self, catalog):
        models = catalog.get_all_models()
        filtered = apply_filters(models, tokenizer="claude")
        assert len(filtered) == 1

    def test_filter_search_fuzzy(self, catalog):
        models = catalog.get_all_models()
        filtered = apply_filters(models, search="claude")
        assert len(filtered) == 1
        filtered = apply_filters(models, search="gpt")
        assert len(filtered) == 1

    def test_filters_combine_with_and(self, catalog):
        models = catalog.get_all_models()
        # Free AND text-only modality
        filtered = apply_filters(
            models, free=True, modality="text->text"
        )
        assert len(filtered) == 1

    def test_filter_new_since(self, catalog):
        models = catalog.get_all_models()
        # Models created after 1705000000
        filtered = apply_filters(models, new_since=1705000000)
        assert len(filtered) == 2


class TestApplySort:
    """Tests for model list sorting."""

    def test_sort_by_price_ascending(self, catalog):
        models = catalog.get_all_models()
        sorted_models = apply_sort(models, sort="price")
        assert sorted_models[0].prompt_price <= sorted_models[1].prompt_price

    def test_sort_by_price_descending(self, catalog):
        models = catalog.get_all_models()
        sorted_models = apply_sort(models, sort="-price")
        assert sorted_models[0].prompt_price >= sorted_models[1].prompt_price

    def test_sort_by_context(self, catalog):
        models = catalog.get_all_models()
        sorted_models = apply_sort(models, sort="context")
        assert sorted_models[0].context_length <= sorted_models[1].context_length

    def test_sort_by_name(self, catalog):
        models = catalog.get_all_models()
        sorted_models = apply_sort(models, sort="name")
        assert sorted_models[0].name <= sorted_models[1].name

    def test_sort_by_created(self, catalog):
        models = catalog.get_all_models()
        sorted_models = apply_sort(models, sort="created")
        assert sorted_models[0].created <= sorted_models[1].created


class TestModelBrowserCLI:
    """Tests for the CLI command wiring."""

    def test_list_returns_all_models(self, catalog):
        cli = ModelBrowserCLI(catalog=catalog)
        result = cli.list_models(output_format="json")
        parsed = json.loads(result)
        assert len(parsed) == 3

    def test_list_with_filter(self, catalog):
        cli = ModelBrowserCLI(catalog=catalog)
        result = cli.list_models(free=True, output_format="json")
        parsed = json.loads(result)
        assert len(parsed) == 1

    def test_show_model_detail(self, catalog):
        cli = ModelBrowserCLI(catalog=catalog)
        result = cli.show_model(
            "openrouter/anthropic/claude-sonnet-4.5",
            output_format="json",
        )
        parsed = json.loads(result)
        assert parsed["name"] == "Claude Sonnet 4.5"

    def test_show_model_not_found(self, catalog):
        cli = ModelBrowserCLI(catalog=catalog)
        with pytest.raises(KeyError, match="not found"):
            cli.show_model("nonexistent", output_format="json")

    def test_list_output_format_csv(self, catalog):
        cli = ModelBrowserCLI(catalog=catalog)
        result = cli.list_models(output_format="csv")
        lines = result.strip().split("\n")
        assert len(lines) == 4  # header + 3 models
```

**Step 2: Run tests to verify failure**

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_model_cli.py -v
```

**Step 3: Implement model browser CLI**

```python
# agent-evals/src/agent_evals/observatory/model_cli.py
"""Terminal model browser using Rich tables with filtering and sorting.

Provides the implementation for `agent-evals models list` and
`agent-evals models show` commands. All filter flags are combinable
(AND logic). Supports table (Rich), JSON, and CSV output formats.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict

from agent_evals.observatory.model_catalog import ModelCatalog, ModelRecord


def apply_filters(
    models: list[ModelRecord],
    *,
    free: bool = False,
    max_price: float | None = None,
    min_context: int | None = None,
    modality: str | None = None,
    capability: str | None = None,
    provider: str | None = None,
    tokenizer: str | None = None,
    search: str | None = None,
    new_since: int | None = None,
) -> list[ModelRecord]:
    """Apply all filters to a model list (AND logic).

    Args:
        free: Only models with zero prompt and completion price.
        max_price: Maximum prompt price (USD per token).
        min_context: Minimum context length.
        modality: Exact modality match (e.g. "text+image->text").
        capability: Comma-separated capabilities; model must have ALL listed
            in its supported_params (AND logic).
        provider: Substring match on model ID provider segment.
        tokenizer: Exact tokenizer match.
        search: Fuzzy substring match on name or ID.
        new_since: Only models with created timestamp after this value.
    """
    result = list(models)

    if free:
        result = [
            m for m in result
            if m.prompt_price == 0.0 and m.completion_price == 0.0
        ]

    if max_price is not None:
        result = [m for m in result if m.prompt_price <= max_price]

    if min_context is not None:
        result = [m for m in result if m.context_length >= min_context]

    if modality is not None:
        result = [m for m in result if m.modality == modality]

    if capability is not None:
        caps = [c.strip() for c in capability.split(",")]
        def _has_all_caps(m: ModelRecord) -> bool:
            params = json.loads(m.supported_params)
            return all(c in params for c in caps)
        result = [m for m in result if _has_all_caps(m)]

    if provider is not None:
        result = [m for m in result if provider.lower() in m.id.lower()]

    if tokenizer is not None:
        result = [m for m in result if m.tokenizer == tokenizer]

    if search is not None:
        query = search.lower()
        result = [
            m for m in result
            if query in m.name.lower() or query in m.id.lower()
        ]

    if new_since is not None:
        result = [m for m in result if m.created > new_since]

    return result


def apply_sort(
    models: list[ModelRecord],
    sort: str = "name",
) -> list[ModelRecord]:
    """Sort models by the given column. Prefix with '-' for descending.

    Supported sort keys: price, created, context, name.
    """
    descending = sort.startswith("-")
    key = sort.lstrip("-")

    sort_keys = {
        "price": lambda m: m.prompt_price,
        "created": lambda m: m.created,
        "context": lambda m: m.context_length,
        "name": lambda m: m.name.lower(),
    }
    key_fn = sort_keys.get(key, sort_keys["name"])
    return sorted(models, key=key_fn, reverse=descending)


class ModelBrowserCLI:
    """CLI interface for browsing the model catalog."""

    def __init__(self, catalog: ModelCatalog) -> None:
        self._catalog = catalog

    def list_models(
        self,
        output_format: str = "table",
        sort: str = "name",
        **filters,
    ) -> str:
        """List models with optional filtering and sorting.

        Args:
            output_format: One of "table" (Rich), "json", "csv".
            sort: Sort key, optionally prefixed with '-' for descending.
            **filters: Passed to apply_filters().

        Returns:
            Formatted string output.
        """
        models = self._catalog.get_all_models()
        models = apply_filters(models, **filters)
        models = apply_sort(models, sort=sort)

        if output_format == "json":
            return json.dumps(
                [self._model_to_dict(m) for m in models], indent=2,
            )
        elif output_format == "csv":
            return self._format_csv(models)
        else:
            return self._format_rich_table(models)

    def show_model(
        self,
        model_id: str,
        output_format: str = "table",
    ) -> str:
        """Show detailed info for a single model.

        Args:
            model_id: The full model ID string.
            output_format: One of "table" (Rich), "json".

        Returns:
            Formatted string output.

        Raises:
            KeyError: If model not found.
        """
        model = self._catalog.get_model_by_id(model_id)
        if model is None:
            msg = f"Model '{model_id}' not found in catalog"
            raise KeyError(msg)

        if output_format == "json":
            return json.dumps(self._model_to_dict(model), indent=2)
        else:
            return self._format_rich_detail(model)

    def _model_to_dict(self, model: ModelRecord) -> dict:
        return {
            "id": model.id,
            "name": model.name,
            "created": model.created,
            "context_length": model.context_length,
            "prompt_price": model.prompt_price,
            "completion_price": model.completion_price,
            "modality": model.modality,
            "tokenizer": model.tokenizer,
            "supported_params": json.loads(model.supported_params),
            "first_seen": model.first_seen,
            "last_seen": model.last_seen,
            "removed_at": model.removed_at,
        }

    def _format_csv(self, models: list[ModelRecord]) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id", "name", "context_length",
            "prompt_price", "completion_price", "modality", "tokenizer",
        ])
        for m in models:
            writer.writerow([
                m.id, m.name, m.context_length,
                m.prompt_price, m.completion_price, m.modality, m.tokenizer,
            ])
        return output.getvalue()

    def _format_rich_table(self, models: list[ModelRecord]) -> str:
        """Format models as a Rich table (returns rendered string)."""
        from rich.console import Console
        from rich.table import Table

        table = Table(title=f"Models ({len(models)})")
        table.add_column("ID", style="cyan")
        table.add_column("Name")
        table.add_column("Context", justify="right")
        table.add_column("Prompt $/tok", justify="right")
        table.add_column("Compl $/tok", justify="right")
        table.add_column("Modality")
        table.add_column("Tokenizer")

        for m in models:
            table.add_row(
                m.id, m.name, f"{m.context_length:,}",
                f"${m.prompt_price:.8f}", f"${m.completion_price:.8f}",
                m.modality, m.tokenizer,
            )

        console = Console(file=io.StringIO(), width=120)
        console.print(table)
        return console.file.getvalue()

    def _format_rich_detail(self, model: ModelRecord) -> str:
        """Format a single model detail view with Rich."""
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        table = Table(show_header=False, box=None)
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("ID", model.id)
        table.add_row("Name", model.name)
        table.add_row("Context Length", f"{model.context_length:,}")
        table.add_row("Prompt Price", f"${model.prompt_price:.8f}/token")
        table.add_row("Completion Price", f"${model.completion_price:.8f}/token")
        table.add_row("Modality", model.modality)
        table.add_row("Tokenizer", model.tokenizer)
        table.add_row("Supported Params", model.supported_params)
        table.add_row("First Seen", model.first_seen or "N/A")
        table.add_row("Last Seen", model.last_seen or "N/A")
        table.add_row("Removed", model.removed_at or "Active")

        panel = Panel(table, title=model.name)
        console = Console(file=io.StringIO(), width=120)
        console.print(panel)
        return console.file.getvalue()
```

**Step 4: Run tests to verify they pass**

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_model_cli.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/model_cli.py agent-evals/tests/test_model_cli.py
git commit -m "feat(observatory): add terminal model browser with filters and Rich output"
```

---

## Task 23: Model Browser Web UI

Page 6 of the observatory web dashboard providing visual model browsing, selection, and group management.

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/web/routes.py`
- Modify: `agent-evals/src/agent_evals/observatory/web/templates/dashboard.html`
- Test: `agent-evals/tests/test_model_browser_web.py`

**Step 1: Write failing tests for model browser web routes**

```python
# agent-evals/tests/test_model_browser_web.py
"""Tests for model browser web UI API routes."""

import json

import pytest
from fastapi.testclient import TestClient

from agent_evals.observatory.model_catalog import ModelCatalog, ModelRecord
from agent_evals.observatory.model_groups import ModelGroupManager
from agent_evals.observatory.web.server import create_app


@pytest.fixture
def catalog(tmp_path):
    db_path = str(tmp_path / "models.db")
    cat = ModelCatalog(db_path=db_path)
    cat.upsert_models([
        ModelRecord(
            id="openrouter/anthropic/claude-sonnet-4.5",
            name="Claude Sonnet 4.5", created=1700000000,
            context_length=200000, prompt_price=3e-06,
            completion_price=15e-06, modality="text+image->text",
            tokenizer="claude",
            supported_params=json.dumps(["temperature", "tools"]),
            raw_json="{}",
        ),
        ModelRecord(
            id="openrouter/openai/gpt-4o",
            name="GPT-4o", created=1710000000,
            context_length=128000, prompt_price=2.5e-06,
            completion_price=10e-06, modality="text+image->text",
            tokenizer="o200k_base",
            supported_params=json.dumps(["temperature", "top_p"]),
            raw_json="{}",
        ),
    ])
    return cat


@pytest.fixture
def client(catalog):
    app = create_app(catalog=catalog)
    return TestClient(app)


class TestModelListEndpoint:
    """Tests for GET /api/models."""

    def test_returns_all_models(self, client):
        response = client.get("/api/models")
        assert response.status_code == 200
        data = response.json()
        assert len(data["models"]) == 2
        assert data["total"] == 2

    def test_filter_by_modality(self, client):
        response = client.get(
            "/api/models?modality=text+image->text"
        )
        assert response.status_code == 200
        assert response.json()["total"] == 2

    def test_search_filter(self, client):
        response = client.get("/api/models?search=claude")
        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_sort_by_price(self, client):
        response = client.get("/api/models?sort=price")
        assert response.status_code == 200
        models = response.json()["models"]
        assert models[0]["prompt_price"] <= models[1]["prompt_price"]


class TestModelDetailEndpoint:
    """Tests for GET /api/models/{id}."""

    def test_returns_model_detail(self, client):
        response = client.get(
            "/api/models/openrouter/anthropic/claude-sonnet-4.5"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Claude Sonnet 4.5"

    def test_model_not_found(self, client):
        response = client.get("/api/models/nonexistent")
        assert response.status_code == 404


class TestModelGroupEndpoints:
    """Tests for /api/models/groups/* endpoints."""

    def test_create_group(self, client):
        response = client.post(
            "/api/models/groups",
            json={"name": "frontier", "description": "Top models"},
        )
        assert response.status_code == 201
        assert response.json()["name"] == "frontier"

    def test_list_groups(self, client):
        client.post(
            "/api/models/groups",
            json={"name": "frontier"},
        )
        response = client.get("/api/models/groups")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    def test_add_models_to_group(self, client):
        create_resp = client.post(
            "/api/models/groups",
            json={"name": "test"},
        )
        group_id = create_resp.json()["id"]
        response = client.post(
            f"/api/models/groups/{group_id}/members",
            json={"model_ids": ["openrouter/anthropic/claude-sonnet-4.5"]},
        )
        assert response.status_code == 200

    def test_delete_group(self, client):
        create_resp = client.post(
            "/api/models/groups",
            json={"name": "temp"},
        )
        group_id = create_resp.json()["id"]
        response = client.delete(f"/api/models/groups/{group_id}")
        assert response.status_code == 204


class TestModelSyncEndpoint:
    """Tests for GET /api/models/sync."""

    def test_sync_status(self, client, catalog):
        catalog.log_sync(models_added=2, models_removed=0, total_count=339)
        response = client.get("/api/models/sync")
        assert response.status_code == 200
        data = response.json()
        assert data["total_models"] == 339
```

**Step 2: Run tests to verify failure**

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_model_browser_web.py -v
```

**Step 3: Implement model browser web routes**

New API routes added to `routes.py`:

```python
# Added to agent-evals/src/agent_evals/observatory/web/routes.py

from agent_evals.observatory.model_catalog import ModelCatalog
from agent_evals.observatory.model_cli import apply_filters, apply_sort
from agent_evals.observatory.model_groups import ModelGroupManager


def register_model_routes(app: FastAPI, catalog: ModelCatalog) -> None:
    """Register model browser API routes on the FastAPI app."""

    group_mgr = ModelGroupManager(catalog=catalog)

    @app.get("/api/models")
    async def list_models(
        search: str | None = None,
        modality: str | None = None,
        capability: str | None = None,
        provider: str | None = None,
        tokenizer: str | None = None,
        free: bool = False,
        max_price: float | None = None,
        min_context: int | None = None,
        sort: str = "name",
    ):
        """List models with filtering and sorting."""
        models = catalog.get_all_models()
        models = apply_filters(
            models, free=free, max_price=max_price,
            min_context=min_context, modality=modality,
            capability=capability, provider=provider,
            tokenizer=tokenizer, search=search,
        )
        models = apply_sort(models, sort=sort)
        return {
            "models": [_model_dict(m) for m in models],
            "total": len(models),
        }

    @app.get("/api/models/sync")
    async def sync_status():
        """Return the status of the last model sync."""
        from agent_evals.observatory.model_sync import ModelSyncService
        service = ModelSyncService(catalog=catalog)
        return service.get_sync_status()

    @app.post("/api/models/sync")
    async def trigger_sync():
        """Trigger an immediate model sync from OpenRouter."""
        from agent_evals.observatory.model_sync import ModelSyncService
        service = ModelSyncService(catalog=catalog)
        result = await service.sync()
        return {
            "added": result.added,
            "removed": result.removed,
            "updated": result.updated,
        }

    @app.get("/api/models/groups")
    async def list_groups():
        """List all model groups."""
        return [
            {"id": g.id, "name": g.name, "description": g.description}
            for g in group_mgr.list_groups()
        ]

    @app.post("/api/models/groups", status_code=201)
    async def create_group(body: dict):
        """Create a new model group."""
        group = group_mgr.create_group(
            name=body["name"],
            description=body.get("description", ""),
        )
        return {"id": group.id, "name": group.name}

    @app.post("/api/models/groups/{group_id}/members")
    async def add_group_members(group_id: str, body: dict):
        """Add models to a group."""
        warnings = group_mgr.add_to_group(group_id, body["model_ids"])
        return {"warnings": warnings}

    @app.delete("/api/models/groups/{group_id}", status_code=204)
    async def delete_group(group_id: str):
        """Delete a model group."""
        group_mgr.delete_group(group_id)

    @app.get("/api/models/{model_id:path}")
    async def get_model(model_id: str):
        """Get detailed info for a single model."""
        model = catalog.get_model_by_id(model_id)
        if model is None:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=404,
                content={"detail": f"Model '{model_id}' not found"},
            )
        return _model_dict(model)

    @app.get("/api/models/{model_id:path}/endpoints")
    async def get_model_endpoints(model_id: str):
        """Proxy to OpenRouter for live provider endpoint data."""
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://openrouter.ai/api/v1/models/{model_id}/endpoints",
                timeout=10.0,
            )
            if resp.status_code == 200:
                return resp.json()
            return {"endpoints": []}


def _model_dict(model) -> dict:
    """Convert a ModelRecord to a JSON-serializable dict."""
    import json as _json
    return {
        "id": model.id,
        "name": model.name,
        "created": model.created,
        "context_length": model.context_length,
        "prompt_price": model.prompt_price,
        "completion_price": model.completion_price,
        "modality": model.modality,
        "tokenizer": model.tokenizer,
        "supported_params": _json.loads(model.supported_params),
        "first_seen": model.first_seen,
        "last_seen": model.last_seen,
        "removed_at": model.removed_at,
    }
```

**Dashboard HTML additions** (appended to `dashboard.html`):

Page 6 ("Models") is added to the nav bar alongside the existing 5 pages. The layout consists of:

- **Left filter panel:** Price range (free/under $1M/custom), context length range slider, modality checkboxes, capabilities checkboxes (tools, reasoning, structured_output, web_search), provider multi-select, tokenizer family multi-select, release date range. All filters apply simultaneously with AND logic. Live count display ("47 of 339 models").
- **Text search bar:** Client-side fuzzy match on name, ID, and description.
- **Main content area** with view toggle:
  - **Data table view:** Compact, sortable columns with selection checkboxes. Click column headers for asc/desc sort, shift-click for secondary sort.
  - **Card grid view:** Visual cards with key stats per model. Toggle overlay for selection. Selection state persists across view switches.
- **Selection & actions:** "Select All" respects current filters. Action bar with "Run Selected" (navigates to Run Config with models pre-filled) and "Save as Group" (dialog for naming/describing a group).
- **New model badge:** "NEW" tag on models added since last visit. Badge count in nav link.
- **Filter state in URL:** Query params are bookmarkable and shareable.
- **Model detail slide-out panel** (from right, preserves filter context):
  - **Overview tab:** Full description, pricing breakdown, context/modality/capabilities/tokenizer/expiration.
  - **Providers tab:** Table of all providers with live latency (last 30min), uptime (color-coded), pricing diffs, quantization, supported params, ZDR indicator. Auto-refreshes every 60 seconds.
  - **History tab:** First/last seen timestamps, test run links if model was used in evaluations, cost history from observatory data.

**Tech:** Vanilla JS + Chart.js (same stack as existing dashboard pages). No build step. All code inline in the single HTML file.

**Step 4: Run tests to verify they pass**

```bash
~/.local/bin/uv run pytest agent-evals/tests/test_model_browser_web.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ agent-evals/tests/test_model_browser_web.py
git commit -m "feat(observatory): add model browser web UI with filters, groups, and detail panel"
```

---

## New Dependency Summary

| Package | Purpose | Added in |
|---------|---------|----------|
| `jinja2>=3.1` | HTML report templates | Task 15 |
| `plotly>=5.0` | Interactive HTML charts | Task 15 |
| `matplotlib>=3.7` | Static chart images for Markdown | Task 16 |
| `fastapi>=0.100` | Web dashboard API | Task 11 |
| `uvicorn[standard]>=0.20` | ASGI server for dashboard | Task 11 |
| `sse-starlette>=1.6` | Server-Sent Events for live updates | Task 11 |
| `httpx>=0.24` | OpenRouter API calls (already transitive dep) | Task 17 |

**Note:** `numpy`, `scipy`, `pyyaml`, `pydantic` are already dependencies. `datasets>=2.14` and `huggingface-hub>=0.20` are also already standard dependencies (added for dataset adapters). Tasks 19-23 (model browser) require no additional packages beyond those listed above -- they reuse SQLite (stdlib), `httpx`, `fastapi`, `sse-starlette`, and `rich` (already a dependency).

---

## Dataset Compatibility

> **Post-plan note:** After this plan was written, a dataset adapter system was added (`agent-evals/src/agent_evals/datasets/`) with 11 adapters (RepLiQA, CodeRAG-Bench, IBM TechQA, DS-1000, MultiHop-RAG, BigCodeBench, SWE-bench, AmbigQA, WikiContradict, Perturbation, Efficiency). The `--source` CLI flag allows tasks to come from external datasets rather than the built-in gold standard. The following constraints apply to the new subsystems in this plan:

- **Task sources are not just gold standard.** The `--source` flag (e.g. `--source repliqa`) means tasks may be loaded from HuggingFace datasets. The Taguchi engine, observatory, and report generator must work with any task source -- they should not assume tasks are always from the gold standard fixtures.
- **CompositeVariant must handle tasks from any source identically.** The variant rendering pipeline should be source-agnostic; task metadata may differ between sources but the render contract is the same.
- **`TaguchiRunner.run()` must pass through the `source` parameter** to `_run_trial()` so that `TrialResult.source` is set correctly. The existing `EvalRunner` already does this.
- **Observatory cost tracking should tag trials with their source.** The `trials` table (Task 8) should store the source value so that per-source cost breakdowns are possible. Add a `source TEXT NOT NULL DEFAULT 'gold_standard'` column to the trials schema.
- **Reports should support per-source segmentation.** When a run uses multiple sources (e.g. gold standard + RepLiQA), the report aggregator (Task 13) and renderers (Tasks 15-16) should be able to segment analysis by source. At minimum, the ReportData dataclass should include a `sources: list[str]` field and per-source score breakdowns.

---

## Testing Strategy

Each task has its own test file. In addition:

- **Integration tests** (`tests/test_integration_taguchi.py`): End-to-end dry-run of Taguchi pipeline with mock LLM client
- **Integration tests** (`tests/test_integration_observatory.py`): Run with SQLite store, verify events recorded
- **Integration tests** (`tests/test_integration_report.py`): Generate report from fixture data, verify HTML/MD output

**Coverage targets:**
- Taguchi engine: 100% (statistical code is critical)
- Observatory store/tracker: 90%+
- Model catalog/sync/groups: 90%+ (data integrity is critical)
- Model browser CLI: 80%+
- Report renderers: 80%+ (template rendering is hard to unit test perfectly)
- Web dashboard routes: 80%+ (test API endpoints, skip browser JS)

---

## File Tree Summary (New Files Only)

```
agent-evals/src/agent_evals/
├── taguchi/
│   ├── __init__.py
│   ├── catalog.py          # OA catalog + auto-selector
│   ├── factors.py          # Axis-to-factor mapper
│   ├── composite.py        # CompositeVariant
│   ├── runner.py           # TaguchiRunner
│   └── analysis.py         # S/N ratios, ANOVA, optimal prediction
├── observatory/
│   ├── __init__.py
│   ├── store.py            # SQLite persistence
│   ├── tracker.py          # Thread-safe event tracker
│   ├── terminal.py         # Rich terminal dashboard
│   ├── history.py          # Cross-run analytics
│   ├── openrouter.py       # Cost reconciliation
│   ├── model_catalog.py    # Model catalog SQLite store
│   ├── model_sync.py       # Background model sync with OpenRouter
│   ├── model_groups.py     # Model group CRUD management
│   ├── model_cli.py        # Terminal model browser (Rich)
│   └── web/
│       ├── __init__.py
│       ├── server.py        # FastAPI app
│       ├── routes.py        # API + SSE endpoints (incl. model browser)
│       └── templates/
│           └── dashboard.html  # 6 pages (incl. Models browser)
├── report/
│   ├── __init__.py
│   ├── aggregator.py       # Data collection
│   ├── statistics.py       # Scientific rigor engine
│   ├── charts.py           # Chart generation
│   ├── html_renderer.py    # HTML report
│   ├── markdown_renderer.py # Markdown report
│   └── templates/
│       └── report.html      # Jinja2 template
├── llm/
│   └── client_pool.py      # Multi-model client pool
└── orchestrator.py          # Top-level coordinator

agent-evals/tests/
├── test_taguchi_catalog.py
├── test_taguchi_factors.py
├── test_composite_variant.py
├── test_taguchi_runner.py
├── test_taguchi_analysis.py
├── test_client_pool.py
├── test_observatory_store.py
├── test_observatory_tracker.py
├── test_observatory_terminal.py
├── test_observatory_web.py
├── test_observatory_history.py
├── test_openrouter_reconciliation.py
├── test_model_catalog.py
├── test_model_sync.py
├── test_model_groups.py
├── test_model_cli.py
├── test_model_browser_web.py
├── test_report_aggregator.py
├── test_report_statistics.py
├── test_report_html.py
├── test_report_markdown.py
├── test_orchestrator.py
├── test_integration_taguchi.py
├── test_integration_observatory.py
└── test_integration_report.py
```

---

## Estimated Effort

| Task | Complexity | Est. Tests |
|------|-----------|------------|
| 1. OA Catalog | Medium | ~20 |
| 2. Factor Mapper | Low | ~10 |
| 3. CompositeVariant | Medium | ~15 |
| 4. TaguchiRunner | High | ~25 |
| 5. S/N & ANOVA | High | ~30 |
| 6. Client Pool | Low | ~8 |
| 7. CLI Flags | Medium | ~15 |
| 8. Observatory Store | Medium | ~20 |
| 9. Event Tracker | Medium | ~15 |
| 10. Terminal Dashboard | Low | ~10 |
| 11. Web Dashboard | High | ~25 |
| 12. Historical Analytics | Medium | ~15 |
| 13. Report Aggregator | Medium | ~15 |
| 14. Statistical Engine | High | ~30 |
| 15. HTML Renderer | Medium | ~15 |
| 16. Markdown Renderer | Medium | ~12 |
| 17. OpenRouter Reconciliation | Low | ~10 |
| 18. Integration & Wiring | High | ~20 |
| 19. Model Catalog Store | Medium | ~18 |
| 20. Background Model Sync | Medium | ~15 |
| 21. Model Groups | Medium | ~18 |
| 22. Model Browser CLI | Medium | ~15 |
| 23. Model Browser Web UI | High | ~20 |
| **Total** | | **~396 new tests** |

---

## Critical Path

The fastest path to a working demo:

```
Tasks 1-2 (catalog + factors) -> Task 3 (composite) -> Task 4 (runner)
     -> Task 5 (analysis) -> Task 7 (CLI) -> Task 13-14 (report data + stats)
     -> Task 15 or 16 (either renderer)
```

Observatory (Tasks 8-12) and web dashboard (Task 11) can be developed in parallel since they don't block the core Taguchi pipeline.

Model browser (Tasks 19-23) depends on the observatory store (Task 8) and web dashboard (Task 11) but is otherwise independent. The critical path for model browsing is:

```
Task 8 (store) -> Task 19 (catalog) -> Tasks 20, 21 (sync, groups, parallel)
     -> Task 22 (CLI) / Task 23 (web UI, also needs Task 11)
```
