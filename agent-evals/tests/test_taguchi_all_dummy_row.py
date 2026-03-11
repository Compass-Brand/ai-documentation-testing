"""Bug #195: TaguchiRunner._build_composite crashes if all factors are dummy level.

When every factor in an OA row gets DUMMY_LEVEL, _build_composite tries to
create CompositeVariant({}) which raises ValueError.  All-dummy rows should
be skipped gracefully.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from agent_evals.runner import EvalRunConfig
from agent_evals.taguchi.factors import (
    DUMMY_LEVEL,
    TaguchiDesign,
    TaguchiExperimentRow,
    TaguchiFactorDef,
)
from agent_evals.taguchi.runner import TaguchiRunner
from conftest import make_mock_client, make_mock_task, make_mock_variant


def _make_design_with_all_dummy_row() -> TaguchiDesign:
    """Create a design where one row has all factors set to DUMMY_LEVEL."""
    factors = [
        TaguchiFactorDef(
            name="axis_1", n_levels=2, level_names=["flat", "2tier"], axis=1,
        ),
        TaguchiFactorDef(
            name="axis_2", n_levels=2, level_names=["path", "summary"], axis=2,
        ),
    ]
    rows = [
        # Normal row
        TaguchiExperimentRow(
            run_id=1,
            assignments={"axis_1": "flat", "axis_2": "path"},
        ),
        # All-dummy row -- every axis factor is DUMMY_LEVEL
        TaguchiExperimentRow(
            run_id=2,
            assignments={"axis_1": DUMMY_LEVEL, "axis_2": DUMMY_LEVEL},
            dummy_factors={"axis_1", "axis_2"},
        ),
        # Normal row
        TaguchiExperimentRow(
            run_id=3,
            assignments={"axis_1": "2tier", "axis_2": "summary"},
        ),
    ]
    return TaguchiDesign(
        oa_name="L4",
        n_runs=3,
        factors=factors,
        rows=rows,
        level_counts=[2, 2],
    )


def _make_variant_lookup() -> dict[str, MagicMock]:
    """Create variant lookup for the test design."""
    return {
        "flat": make_mock_variant("flat", 1),
        "2tier": make_mock_variant("2tier", 1),
        "path": make_mock_variant("path", 2),
        "summary": make_mock_variant("summary", 2),
    }


class TestAllDummyRowSkipped:
    """Bug #195: all-dummy OA rows should be skipped, not crash."""

    def test_should_not_crash_when_row_has_all_dummy_factors(self) -> None:
        """_build_composite must not crash when all factors are DUMMY_LEVEL."""
        design = _make_design_with_all_dummy_row()
        variants = _make_variant_lookup()
        client = make_mock_client()
        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        # This should NOT raise ValueError from CompositeVariant({})
        result = runner.run(tasks, doc_tree)

        # Only rows 1 and 3 should produce trials (row 2 is all-dummy)
        assert len(result.trials) == 2

    def test_should_produce_trials_for_non_dummy_rows_only(self) -> None:
        """Trials should only come from rows with at least one real factor."""
        design = _make_design_with_all_dummy_row()
        variants = _make_variant_lookup()
        client = make_mock_client()
        config = EvalRunConfig(repetitions=2, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        tasks = [make_mock_task()]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        # 2 non-dummy rows * 1 task * 2 reps = 4 trials
        assert len(result.trials) == 4

        # All trials should have oa_row_id of 1 or 3 (not 2)
        row_ids = {int(t.metrics["oa_row_id"]) for t in result.trials}
        assert row_ids == {1, 3}

    def test_build_composite_returns_none_for_all_dummy(self) -> None:
        """_build_composite should return None when all factors are dummy."""
        design = _make_design_with_all_dummy_row()
        variants = _make_variant_lookup()
        client = make_mock_client()
        config = EvalRunConfig(repetitions=1, max_connections=1)

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        all_dummy_row = design.rows[1]  # row with run_id=2
        result = runner._build_composite(all_dummy_row)
        assert result is None
