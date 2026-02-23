"""Catalog of standard Taguchi orthogonal arrays with auto-selection.

Provides a library of published Taguchi OAs (L4 through L81) as NumPy arrays,
plus an auto-selector that picks the smallest array accommodating a given
factor-level structure.

OA sources: Taguchi & Konishi (1987), Hedayat et al. (1999).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

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


# ---- OA Builders ----


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
    # Standard Plackett-Burman L12 from published tables
    first_row = [1, 1, 0, 1, 1, 1, 0, 0, 0, 1, 0]
    rows = [[0] * 11]
    current = list(first_row)
    for _ in range(10):
        rows.append(list(current))
        current = [current[-1]] + current[:-1]
    rows.append([1] * 11)
    matrix = np.array(rows, dtype=np.int32)
    return OrthogonalArray(
        name="L12", n_runs=12, n_columns=11, max_levels=2,
        matrix=matrix, level_structure=(2,) * 11,
    )


def _build_l16() -> OrthogonalArray:
    """L16(2^15): 16 runs, 15 two-level columns."""
    base = np.array(list(np.ndindex(*(2,) * 4)), dtype=np.int32)
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
    rows = []
    for i in range(5):
        for j in range(5):
            rows.append([
                i, j,
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
    base = np.array(list(np.ndindex(*(3,) * 3)), dtype=np.int32)
    cols = [base[:, i] for i in range(3)]
    all_cols = list(cols)
    for i in range(3):
        for j in range(i + 1, 3):
            all_cols.append((cols[i] + cols[j]) % 3)
            all_cols.append((cols[i] + 2 * cols[j]) % 3)
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

    Workhorse array for mixed-level experiments.
    23 columns total: 11 at 2 levels, 12 at 3 levels.
    """
    l4_base = np.array(list(np.ndindex(*(2,) * 2)), dtype=np.int32)
    l9_base = np.array(list(np.ndindex(*(3,) * 2)), dtype=np.int32)

    rows = []
    for i in range(4):
        for j in range(9):
            a, b = int(l4_base[i, 0]), int(l4_base[i, 1])
            c, d = int(l9_base[j, 0]), int(l9_base[j, 1])
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
    l27 = _build_l27()
    rows = []
    for a in range(2):
        for row_idx in range(27):
            base = list(l27.matrix[row_idx])
            extended = [a] + base + [
                (base[k] + a) % 3 for k in range(min(12, len(base)))
            ]
            rows.append(extended[:26])
    matrix = np.array(rows, dtype=np.int32)
    n_cols = matrix.shape[1]
    return OrthogonalArray(
        name="L54", n_runs=54, n_columns=n_cols, max_levels=3,
        matrix=matrix, level_structure=(2,) + (3,) * (n_cols - 1),
    )


def _build_l64() -> OrthogonalArray:
    """L64(4^21): 64 runs, 21 four-level columns."""
    base = np.array(list(np.ndindex(*(4,) * 3)), dtype=np.int32)
    cols = [base[:, i] for i in range(3)]
    all_cols = list(cols)
    for i in range(3):
        for j in range(i + 1, 3):
            for mult in range(1, 4):
                all_cols.append((cols[i] + mult * cols[j]) % 4)
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
    base = np.array(list(np.ndindex(*(3,) * 4)), dtype=np.int32)
    cols = [base[:, i] for i in range(4)]
    all_cols = list(cols)
    # 2-way interactions: C(4,2)*2 = 12
    for i in range(4):
        for j in range(i + 1, 4):
            all_cols.append((cols[i] + cols[j]) % 3)
            all_cols.append((cols[i] + 2 * cols[j]) % 3)
    # 3-way interactions: C(4,3)*2*2 = 16
    for i in range(4):
        for j in range(i + 1, 4):
            for k in range(j + 1, 4):
                for m1 in [1, 2]:
                    for m2 in [1, 2]:
                        all_cols.append(
                            (cols[i] + m1 * cols[j] + m2 * cols[k]) % 3
                        )
    # 4-way interactions: 2^3 = 8
    for m1 in [1, 2]:
        for m2 in [1, 2]:
            for m3 in [1, 2]:
                all_cols.append(
                    (cols[0] + m1 * cols[1] + m2 * cols[2] + m3 * cols[3]) % 3
                )
    matrix = np.column_stack(all_cols[:40]).astype(np.int32)
    return OrthogonalArray(
        name="L81", n_runs=81, n_columns=40, max_levels=3,
        matrix=matrix, level_structure=(3,) * 40,
    )


# ---- Registry ----

_OA_BUILDERS: dict[str, Callable[[], OrthogonalArray]] = {
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
        available_levels = sorted(
            [oa.column_levels(i) for i in range(oa.n_columns)],
            reverse=True,
        )
        needed = sorted(level_counts, reverse=True)
        if all(a >= n for a, n in zip(available_levels[:n_factors], needed, strict=True)):
            return oa

    msg = (
        f"No suitable orthogonal array found for {n_factors} factors "
        f"with max {max_level} levels. Consider reducing factor levels."
    )
    raise ValueError(msg)
