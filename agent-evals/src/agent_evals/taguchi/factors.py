"""Map variant axes and models to Taguchi factors and build experimental designs."""

from __future__ import annotations

from dataclasses import dataclass, field

from agent_evals.taguchi.catalog import get_oa, select_oa


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
    """Convert variant axes (and optional models) to Taguchi factor defs.

    Args:
        axes: Mapping of axis number to list of variant names.
        models: Optional list of model names. Adds a "model" factor
            only when more than one model is provided.

    Returns:
        List of TaguchiFactorDef, sorted by axis number, with an
        optional model factor appended.
    """
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
        oa_override: Force a specific OA (e.g. "L9") instead of auto-select.

    Returns:
        A TaguchiDesign with all rows and factor assignments.
    """
    factors = build_factors_from_axes(axes, models)
    level_counts = [f.n_levels for f in factors]

    if oa_override:
        oa = get_oa(oa_override)
    else:
        oa = select_oa(level_counts)

    # Assign OA columns to factors (greedy: match level requirement)
    col_assignments: list[int] = []
    used_cols: set[int] = set()
    for factor in factors:
        assigned = False
        for col_idx in range(oa.n_columns):
            if col_idx in used_cols:
                continue
            if oa.column_levels(col_idx) >= factor.n_levels:
                col_assignments.append(col_idx)
                used_cols.add(col_idx)
                assigned = True
                break
        if not assigned:
            raise ValueError(
                f"Cannot assign factor '{factor.name}' ({factor.n_levels} "
                f"levels) to OA '{oa.name}': no suitable column available"
            )

    # Build rows
    rows: list[TaguchiExperimentRow] = []
    for run_id in range(oa.n_runs):
        assignments: dict[str, str] = {}
        for factor, col_idx in zip(factors, col_assignments, strict=True):
            raw_level = int(oa.matrix[run_id, col_idx])
            # Map OA level (0-indexed) to actual level name (mod n_levels)
            mapped_level = raw_level % factor.n_levels
            assignments[factor.name] = factor.level_names[mapped_level]
        rows.append(TaguchiExperimentRow(
            run_id=run_id + 1,
            assignments=assignments,
        ))

    return TaguchiDesign(
        oa_name=oa.name,
        n_runs=oa.n_runs,
        factors=factors,
        rows=rows,
        level_counts=level_counts,
    )
