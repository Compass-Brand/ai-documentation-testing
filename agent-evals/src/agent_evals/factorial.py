"""Factorial design generator for multi-axis evaluation.

Generates fractional and full factorial designs for evaluating
index variants across the top-scoring axes. Supports pre-registered
pruning rules to exclude invalid configurations.

Design ref: DESIGN.md Story 7.1 -- 2^(5-1) Resolution V design
Generator: E = ABCD
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class Factor:
    """A single factor in the factorial design.

    Each factor represents the top 2 candidates from one eval axis.
    """

    name: str
    levels: tuple[str, str]
    axis: int


@dataclass
class PruningRule:
    """A pre-registered rule for excluding invalid configurations.

    Example: 'YAML + flat structure excluded -- YAML requires hierarchy'
    """

    description: str
    check: Callable[[dict[str, str]], bool]
    reason: str


@dataclass
class FactorialRun:
    """A single run (row) in the factorial design matrix."""

    run_id: int
    factor_assignments: dict[str, str]
    excluded: bool = False
    exclusion_reason: str = ""


@dataclass
class FactorialDesign:
    """Complete factorial design with all runs."""

    factors: list[Factor]
    runs: list[FactorialRun]
    resolution: str
    generator: str
    n_runs: int = field(init=False)

    def __post_init__(self) -> None:
        self.n_runs = len(self.runs)


def _build_design_matrix(n_base: int) -> list[tuple[int, ...]]:
    """Build a full factorial design matrix for *n_base* two-level factors.

    Returns rows of coded values (-1, +1).
    """
    return list(itertools.product((-1, 1), repeat=n_base))


def _code_to_level(code: int, levels: tuple[str, str]) -> str:
    """Map a coded value (-1 or +1) to the corresponding level name."""
    return levels[0] if code == -1 else levels[1]


def generate_fractional_factorial(
    factors: list[Factor],
    generator: str = "E=ABCD",
) -> FactorialDesign:
    """Generate a 2^(5-1) Resolution V fractional factorial design.

    Parameters
    ----------
    factors:
        Exactly 5 factors, one per eval axis.
    generator:
        Defining relation. Default ``"E=ABCD"`` means the 5th column
        is the element-wise product of columns A-D.

    Raises
    ------
    ValueError
        If the number of factors is not exactly 5.

    Returns
    -------
    FactorialDesign
        Design with 16 runs (2^4 base rows, 5th column generated).
    """
    if len(factors) != 5:
        msg = f"Fractional factorial requires exactly 5 factors, got {len(factors)}"
        raise ValueError(msg)

    # Build 2^4 base matrix for factors A, B, C, D
    base_matrix = _build_design_matrix(4)

    runs: list[FactorialRun] = []
    for run_id, row in enumerate(base_matrix, start=1):
        a, b, c, d = row
        # Generator: E = A * B * C * D
        e = a * b * c * d

        codes = (*row, e)
        assignments = {
            factor.name: _code_to_level(code, factor.levels)
            for factor, code in zip(factors, codes, strict=True)
        }

        runs.append(FactorialRun(run_id=run_id, factor_assignments=assignments))

    return FactorialDesign(
        factors=list(factors),
        runs=runs,
        resolution="V",
        generator=generator,
    )


def generate_full_factorial(factors: list[Factor]) -> FactorialDesign:
    """Generate a full 2^k factorial design.

    Parameters
    ----------
    factors:
        Any number of two-level factors.

    Raises
    ------
    ValueError
        If no factors are provided.

    Returns
    -------
    FactorialDesign
        Design with 2^k runs.
    """
    if not factors:
        msg = "At least one factor is required"
        raise ValueError(msg)

    k = len(factors)
    matrix = _build_design_matrix(k)

    runs: list[FactorialRun] = []
    for run_id, row in enumerate(matrix, start=1):
        assignments = {
            factor.name: _code_to_level(code, factor.levels)
            for factor, code in zip(factors, row, strict=True)
        }
        runs.append(FactorialRun(run_id=run_id, factor_assignments=assignments))

    return FactorialDesign(
        factors=list(factors),
        runs=runs,
        resolution="full",
        generator="none",
    )


def apply_pruning(
    design: FactorialDesign,
    rules: list[PruningRule],
) -> FactorialDesign:
    """Apply pruning rules to a factorial design.

    Runs that match a rule are marked as excluded but **not** removed,
    preserving the full design matrix for analysis.

    Parameters
    ----------
    design:
        The factorial design to prune.
    rules:
        Pre-registered pruning rules.

    Returns
    -------
    FactorialDesign
        New design instance with matching runs marked excluded.
    """
    new_runs: list[FactorialRun] = []
    for run in design.runs:
        excluded = run.excluded
        reason = run.exclusion_reason

        if not excluded:
            for rule in rules:
                if rule.check(run.factor_assignments):
                    excluded = True
                    reason = rule.reason
                    break

        new_runs.append(
            FactorialRun(
                run_id=run.run_id,
                factor_assignments=dict(run.factor_assignments),
                excluded=excluded,
                exclusion_reason=reason,
            )
        )

    return FactorialDesign(
        factors=list(design.factors),
        runs=new_runs,
        resolution=design.resolution,
        generator=design.generator,
    )


def get_active_runs(design: FactorialDesign) -> list[FactorialRun]:
    """Return only non-excluded runs from the design.

    Parameters
    ----------
    design:
        A (possibly pruned) factorial design.

    Returns
    -------
    list[FactorialRun]
        Runs where ``excluded`` is ``False``.
    """
    return [run for run in design.runs if not run.excluded]
