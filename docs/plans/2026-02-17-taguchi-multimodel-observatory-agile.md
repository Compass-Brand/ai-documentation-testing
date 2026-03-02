# Taguchi DOE, Multi-Model, Observatory & Reports -- Agile Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Taguchi orthogonal array design, multi-model evaluation, a cost/telemetry observatory with web dashboard, model discovery & browser, and publication-grade research reports to agent-evals.

**Architecture:** Three new subsystems added alongside the existing runner. See `2026-02-17-taguchi-multimodel-observatory-design.md` for the full design document.

**Tech Stack:** Python 3.11+, NumPy/SciPy, FastAPI, Chart.js, Jinja2, SQLite, Plotly, matplotlib, httpx, datasets/huggingface-hub (already in pyproject.toml)

---

## Product Backlog

### Epics

| ID | Epic | Stories | Priority |
|----|------|---------|----------|
| E1 | Taguchi DOE Engine | 5 | P0 -- Critical path |
| E2 | Multi-Model Support | 3 | P0 -- Critical path |
| E3 | Observatory & Telemetry | 7 | P1 -- High value |
| E4 | Research Report Generator | 5 | P1 -- High value |
| E5 | Integration & Orchestration | 2 | P0 -- Ties everything together |
| E6 | Model Discovery & Browser | 5 | P1 -- High value |

### Sprint Plan

| Sprint | Duration | Focus | Stories | Deliverable |
|--------|----------|-------|---------|-------------|
| 1 | Foundation | E1-S1, E1-S2, E1-S3, E2-S1 | Taguchi catalog, factors, composite, client pool |
| 2 | Core Pipeline | E1-S4, E1-S5, E2-S2 | TaguchiRunner, S/N + ANOVA, CLI flags |
| 3 | Observatory | E3-S1, E3-S2, E3-S3, E6-S1, E6-S2 | SQLite store, tracker, terminal dashboard, model catalog, model sync |
| 4 | Reports | E4-S1, E4-S2, E4-S3, E4-S4, E6-S3, E6-S4 | Aggregator, stats engine, HTML + MD renderers, model groups, model browser CLI |
| 5 | Web & History | E3-S4, E3-S5, E3-S6, E3-S7, E4-S5, E6-S5 | Web dashboard, historical analytics, reconciliation, observatory CLI, chart lib, model browser web UI |
| 6 | Ship It | E5-S1, E5-S2, E2-S3 | Orchestrator, integration tests, end-to-end validation |

### Definition of Done (per story)

- [ ] All acceptance tests written FIRST (RED)
- [ ] Minimal implementation passes all tests (GREEN)
- [ ] Code cleaned up, no duplication (REFACTOR)
- [ ] `~/.local/bin/uv run pytest` -- all project tests pass (no regressions)
- [ ] `~/.local/bin/uv run ruff check .` -- no lint errors
- [ ] Committed with conventional commit message
- [ ] No modifications to files currently under test run (existing source files)
- [ ] Taguchi engine modules: 100% coverage
- [ ] Observatory store/tracker: 90%+ coverage
- [ ] Model catalog/sync/groups: 90%+ coverage
- [ ] Model browser CLI: 80%+ coverage
- [ ] Model browser web UI: 80%+ coverage
- [ ] Report renderers: 80%+ coverage
- [ ] Web dashboard routes: 80%+ coverage

### Dataset Compatibility Notes (added 2026-02-23)

Cross-cutting constraints for all stories arising from the dataset adapter system
merged after this plan was written:

1. **Dataset adapters exist:** `agent-evals/src/agent_evals/datasets/` contains 11 adapters
   (RepLiQA, CodeRAG-Bench, IBM TechQA, DS-1000, MultiHop-RAG, BigCodeBench,
   SWE-bench, AmbigQA, WikiContradict, Perturbation, Efficiency). These are standard
   deps: `datasets>=2.14`, `huggingface-hub>=0.20` (already in `pyproject.toml`).

2. **`TrialResult.source` field:** The `TrialResult` dataclass now includes
   `source: str = "gold_standard"`. Any new code that creates, copies, or
   aggregates `TrialResult` objects must preserve this field.

3. **Runner `source` parameter:** `EvalRunner.run()` and `_run_trial()` accept
   `source: str = "gold_standard"`. `TaguchiRunner` must mirror this contract.

4. **Existing CLI flags:** `--source`, `--dataset-limit`, `--dataset-cache-dir`,
   `--prepare-datasets`, and `--list-datasets` are already registered in
   `build_parser()`. New flags must not collide with these names.

5. **Observatory and reports:** When tasks come from multiple sources, the
   observatory store and report aggregator should segment analysis by source.

---

## Sprint 1: Foundation

**Goal:** Build the standalone building blocks that everything else depends on. These modules have zero dependencies on existing source files.

---

### E1-S1: Taguchi Orthogonal Array Catalog

**User Story:** As a developer, I want a catalog of standard Taguchi orthogonal arrays so that the system can select the right array for any factor-level combination.

**Acceptance Criteria:**

```gherkin
Feature: Orthogonal Array Catalog

  Scenario: Retrieve a known OA by name
    Given the OA catalog is loaded
    When I request OA "L18"
    Then I receive an array with 18 runs
    And the matrix has shape (18, 8)
    And column 0 has 2 levels
    And columns 1-7 have 3 levels each

  Scenario: List all available arrays
    Given the OA catalog is loaded
    When I list available arrays
    Then I receive at least 10 standard arrays
    And they include L4, L8, L9, L12, L16, L18, L25, L27, L36, L50, L54, L64, L81

  Scenario: Request unknown array
    Given the OA catalog is loaded
    When I request OA "L999"
    Then a KeyError is raised with message containing "L999"

  Scenario: Auto-select for simple 2-level factors
    Given 3 factors with 2 levels each
    When I call select_oa([2, 2, 2])
    Then I receive an OA with at most 8 runs
    And at least 3 usable columns

  Scenario: Auto-select for mixed-level factors
    Given factors with levels [2, 3, 3, 2, 3]
    When I call select_oa([2, 3, 3, 2, 3])
    Then I receive an OA with at most 36 runs
    And at least 5 usable columns

  Scenario: Auto-select for full 10-axis problem
    Given the real problem: levels [5, 4, 5, 4, 5, 5, 4, 4, 3, 4]
    When I call select_oa with those levels
    Then I receive an OA with at least 10 columns
    And each assigned column supports the required number of levels

  Scenario: Auto-select for 10 axes + 3 models
    Given levels [5, 4, 5, 4, 5, 5, 4, 4, 3, 4, 3]
    When I call select_oa with those levels
    Then I receive an OA with at least 11 columns

  Scenario: Impossible request fails gracefully
    Given 100 factors with 10 levels each
    When I call select_oa([10] * 100)
    Then a ValueError is raised with message "No suitable"

  Scenario: OA matrix values are valid
    Given any OA from the catalog
    When I inspect the matrix
    Then all values are >= 0
    And all values in column i are < column_levels(i)

  Scenario: OA matrix has correct orthogonality
    Given OA "L9" (3^4)
    When I check column pair (0, 1)
    Then every combination of levels (0,0), (0,1), ..., (2,2) appears equally often
```

**Files:**
- Create: `agent-evals/src/agent_evals/taguchi/__init__.py`
- Create: `agent-evals/src/agent_evals/taguchi/catalog.py`
- Test: `agent-evals/tests/test_taguchi_catalog.py`

**TDD Cycle:**

**RED 1 -- OrthogonalArray data model tests**
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


class TestOrthogonalArrayModel:
    """The OrthogonalArray dataclass stores array metadata and matrix."""

    def test_has_name_and_dimensions(self):
        oa = get_oa("L4")
        assert oa.name == "L4"
        assert oa.n_runs == 4
        assert oa.n_columns == 3

    def test_matrix_shape_matches_metadata(self):
        oa = get_oa("L4")
        assert oa.matrix.shape == (oa.n_runs, oa.n_columns)

    def test_matrix_dtype_is_int(self):
        oa = get_oa("L4")
        assert oa.matrix.dtype == np.int32

    def test_values_are_zero_indexed(self):
        oa = get_oa("L4")
        assert oa.matrix.min() == 0

    def test_values_within_level_bounds(self):
        oa = get_oa("L4")
        for col in range(oa.n_columns):
            col_max = oa.matrix[:, col].max()
            assert col_max < oa.column_levels(col)

    def test_column_levels_returns_correct_count(self):
        oa = get_oa("L18")
        assert oa.column_levels(0) == 2  # first column is 2-level
        assert oa.column_levels(1) == 3  # rest are 3-level
```

Run: `~/.local/bin/uv run pytest agent-evals/tests/test_taguchi_catalog.py::TestOrthogonalArrayModel -v`
Expected: FAIL -- `ModuleNotFoundError: No module named 'agent_evals.taguchi'`

**GREEN 1 -- Create package and OrthogonalArray dataclass + L4 builder**

Create `agent-evals/src/agent_evals/taguchi/__init__.py` (empty) and `catalog.py` with the `OrthogonalArray` dataclass, `_build_l4()`, `_build_l18()`, `get_oa()`, and the `_OA_BUILDERS` registry. Only implement enough builders to pass these tests.

Run: `~/.local/bin/uv run pytest agent-evals/tests/test_taguchi_catalog.py::TestOrthogonalArrayModel -v`
Expected: PASS

**RED 2 -- Retrieval tests for specific arrays**
```python
class TestGetOA:
    """Retrieve specific OAs by name."""

    def test_l4_has_4_runs_2_levels(self):
        oa = get_oa("L4")
        assert oa.n_runs == 4
        assert oa.max_levels == 2

    def test_l8_has_8_runs_7_columns(self):
        oa = get_oa("L8")
        assert oa.n_runs == 8
        assert oa.n_columns == 7

    def test_l9_has_9_runs_3_levels(self):
        oa = get_oa("L9")
        assert oa.n_runs == 9
        assert oa.max_levels == 3

    def test_l12_has_12_runs_11_columns(self):
        oa = get_oa("L12")
        assert oa.n_runs == 12
        assert oa.n_columns == 11

    def test_l18_has_18_runs_8_columns(self):
        oa = get_oa("L18")
        assert oa.n_runs == 18
        assert oa.n_columns == 8

    def test_l25_has_25_runs_5_levels(self):
        oa = get_oa("L25")
        assert oa.n_runs == 25
        assert oa.max_levels == 5

    def test_l27_has_27_runs_13_columns(self):
        oa = get_oa("L27")
        assert oa.n_runs == 27
        assert oa.n_columns == 13

    def test_l36_has_36_runs_mixed_levels(self):
        oa = get_oa("L36")
        assert oa.n_runs == 36

    def test_l54_has_54_runs(self):
        oa = get_oa("L54")
        assert oa.n_runs == 54

    def test_l64_has_64_runs(self):
        oa = get_oa("L64")
        assert oa.n_runs == 64

    def test_unknown_oa_raises_keyerror(self):
        with pytest.raises(KeyError, match="L999"):
            get_oa("L999")
```

Run, expect failures for unimplemented arrays.

**GREEN 2 -- Implement all OA builders** (L4, L8, L9, L12, L16, L18, L25, L27, L36, L50, L54, L64, L81)

**RED 3 -- Listing and auto-selection tests**
```python
class TestGetAvailableArrays:
    """List all OAs in the catalog."""

    def test_returns_nonempty(self):
        arrays = get_available_arrays()
        assert len(arrays) >= 10

    def test_sorted_by_run_count(self):
        arrays = get_available_arrays()
        run_counts = [a.n_runs for a in arrays]
        assert run_counts == sorted(run_counts)

    def test_includes_key_arrays(self):
        names = {a.name for a in get_available_arrays()}
        for expected in ["L4", "L9", "L18", "L36", "L54", "L64", "L81"]:
            assert expected in names


class TestSelectOA:
    """Auto-select the smallest suitable OA for a factor-level structure."""

    def test_three_2level_factors_selects_small_oa(self):
        oa = select_oa([2, 2, 2])
        assert oa.n_runs <= 8
        assert oa.n_columns >= 3

    def test_four_3level_factors(self):
        oa = select_oa([3, 3, 3, 3])
        assert oa.n_runs <= 27
        assert oa.n_columns >= 4

    def test_mixed_levels(self):
        oa = select_oa([2, 3, 3, 2, 3])
        assert oa.n_runs <= 36
        assert oa.n_columns >= 5

    def test_real_10_axis_problem(self):
        levels = [5, 4, 5, 4, 5, 5, 4, 4, 3, 4]
        oa = select_oa(levels)
        assert oa.n_columns >= 10
        # Verify each column can hold its factor
        available = sorted(
            [oa.column_levels(i) for i in range(oa.n_columns)],
            reverse=True,
        )
        needed = sorted(levels, reverse=True)
        for a, n in zip(available, needed):
            assert a >= n

    def test_10_axes_plus_3_models(self):
        levels = [5, 4, 5, 4, 5, 5, 4, 4, 3, 4, 3]
        oa = select_oa(levels)
        assert oa.n_columns >= 11

    def test_impossible_request_raises(self):
        with pytest.raises(ValueError, match="No suitable"):
            select_oa([10] * 100)

    def test_oa_selection_reference_mappings(self):
        """Verify expected OA selections for common configurations."""
        # 1 model, 10 axes
        oa = select_oa([5, 4, 5, 4, 5, 5, 4, 4, 3, 4])
        assert oa.name in ("L36", "L50", "L54", "L64", "L81")

        # 3 models, 10 axes
        oa = select_oa([5, 4, 5, 4, 5, 5, 4, 4, 3, 4, 3])
        assert oa.name in ("L54", "L64", "L81")


class TestOrthogonalityProperty:
    """Verify the fundamental OA property: balanced level combinations."""

    def test_l9_pairwise_balance(self):
        oa = get_oa("L9")
        # For any two columns, every level pair appears equally often
        for c1 in range(oa.n_columns):
            for c2 in range(c1 + 1, oa.n_columns):
                pairs = list(zip(oa.matrix[:, c1], oa.matrix[:, c2]))
                from collections import Counter
                counts = Counter(pairs)
                freq = list(counts.values())
                # All pair frequencies should be equal
                assert len(set(freq)) == 1, (
                    f"Columns ({c1},{c2}) not balanced: {counts}"
                )

    def test_l4_pairwise_balance(self):
        oa = get_oa("L4")
        for c1 in range(oa.n_columns):
            for c2 in range(c1 + 1, oa.n_columns):
                pairs = list(zip(oa.matrix[:, c1], oa.matrix[:, c2]))
                from collections import Counter
                counts = Counter(pairs)
                freq = list(counts.values())
                assert len(set(freq)) == 1
```

**GREEN 3 -- Implement `get_available_arrays()` and `select_oa()`**

**REFACTOR -- Clean up builders, extract shared construction helpers**

Run full suite: `~/.local/bin/uv run pytest agent-evals/tests/test_taguchi_catalog.py -v`
Run project-wide: `~/.local/bin/uv run pytest` (verify no regressions)

**Commit:**
```bash
git add agent-evals/src/agent_evals/taguchi/ agent-evals/tests/test_taguchi_catalog.py
git commit -m "feat(taguchi): add orthogonal array catalog with auto-selection

Catalog includes standard Taguchi OAs L4 through L81 with auto-selector
that picks the smallest array accommodating any factor-level structure.
Supports mixed-level designs for the 10-axis + model evaluation problem.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E1-S2: Factor Mapper

**User Story:** As a developer, I want to map variant axes (and optional model list) to Taguchi factors so that the OA selector receives the correct level structure.

**Acceptance Criteria:**

```gherkin
Feature: Factor Mapping

  Scenario: Single axis becomes one factor
    Given axis 1 with variants ["flat", "2tier", "3tier", "4tier", "inline"]
    When I build factors
    Then I get 1 factor named "axis_1" with 5 levels

  Scenario: Multiple axes become multiple factors
    Given axes {1: ["flat","2tier"], 2: ["path","summary","tokens"]}
    When I build factors
    Then I get 2 factors with level counts [2, 3]

  Scenario: Models become an additional factor
    Given axis 1 with 2 variants and models ["claude", "gpt-4o", "gemini"]
    When I build factors with models
    Then I get 2 factors total
    And the second factor is named "model" with 3 levels

  Scenario: Single model does not create a factor
    Given axis 1 with 2 variants and models ["claude"]
    When I build factors with models
    Then I get 1 factor (no model factor)

  Scenario: Design has correct number of rows
    Given axes and optional models
    When I build a TaguchiDesign
    Then the number of rows equals the selected OA's n_runs

  Scenario: Each row assigns valid level names
    Given axis 1 with variants ["flat", "2tier", "3tier"]
    When I build a design
    Then every row's axis_1 assignment is one of ["flat", "2tier", "3tier"]

  Scenario: Design with models assigns model names
    Given models ["claude", "gpt"]
    When I build a design with models
    Then every row has a "model" key with value "claude" or "gpt"
```

**Files:**
- Create: `agent-evals/src/agent_evals/taguchi/factors.py`
- Test: `agent-evals/tests/test_taguchi_factors.py`

**TDD Cycle:**

**RED 1 -- Factor definition tests**
```python
# agent-evals/tests/test_taguchi_factors.py
"""Tests for factor mapping from variant axes to Taguchi factors."""

import pytest

from agent_evals.taguchi.factors import (
    TaguchiDesign,
    TaguchiExperimentRow,
    TaguchiFactorDef,
    build_design,
    build_factors_from_axes,
)


class TestBuildFactorsFromAxes:
    """Convert variant axis definitions to Taguchi factor definitions."""

    def test_single_axis_one_factor(self):
        axes = {1: ["flat", "2tier", "3tier", "4tier", "inline"]}
        factors = build_factors_from_axes(axes)
        assert len(factors) == 1
        assert factors[0].name == "axis_1"
        assert factors[0].n_levels == 5
        assert factors[0].level_names == ["flat", "2tier", "3tier", "4tier", "inline"]

    def test_multiple_axes(self):
        axes = {1: ["flat", "2tier"], 2: ["path", "summary", "tokens"]}
        factors = build_factors_from_axes(axes)
        assert len(factors) == 2
        assert factors[0].n_levels == 2
        assert factors[1].n_levels == 3

    def test_axes_sorted_by_number(self):
        axes = {3: ["a", "b"], 1: ["c", "d"]}
        factors = build_factors_from_axes(axes)
        assert factors[0].name == "axis_1"
        assert factors[1].name == "axis_3"

    def test_models_add_model_factor(self):
        axes = {1: ["flat", "2tier"]}
        factors = build_factors_from_axes(axes, models=["claude", "gpt", "gemini"])
        assert len(factors) == 2
        model_f = factors[-1]
        assert model_f.name == "model"
        assert model_f.n_levels == 3
        assert model_f.axis is None

    def test_single_model_no_factor(self):
        axes = {1: ["flat", "2tier"]}
        factors = build_factors_from_axes(axes, models=["claude"])
        assert len(factors) == 1  # no model factor

    def test_no_models_no_factor(self):
        axes = {1: ["flat", "2tier"]}
        factors = build_factors_from_axes(axes, models=None)
        assert len(factors) == 1
```

Run: `~/.local/bin/uv run pytest agent-evals/tests/test_taguchi_factors.py::TestBuildFactorsFromAxes -v`
Expected: FAIL

**GREEN 1 -- Implement `build_factors_from_axes()`**

**RED 2 -- Design building tests**
```python
class TestBuildDesign:
    """Build a complete Taguchi experimental design from axes."""

    def test_design_has_rows(self):
        axes = {1: ["flat", "2tier", "3tier"], 2: ["path", "summary", "tokens"]}
        design = build_design(axes)
        assert design.n_runs > 0
        assert len(design.rows) == design.n_runs

    def test_rows_have_all_factors(self):
        axes = {1: ["a", "b", "c"], 2: ["x", "y"]}
        design = build_design(axes)
        for row in design.rows:
            assert "axis_1" in row.assignments
            assert "axis_2" in row.assignments

    def test_assignments_use_valid_names(self):
        axes = {1: ["flat", "2tier", "3tier"]}
        design = build_design(axes)
        for row in design.rows:
            assert row.assignments["axis_1"] in ["flat", "2tier", "3tier"]

    def test_design_with_models(self):
        axes = {1: ["flat", "2tier"]}
        design = build_design(axes, models=["claude", "gpt"])
        for row in design.rows:
            assert row.assignments["model"] in ["claude", "gpt"]

    def test_design_records_oa_name(self):
        axes = {1: ["a", "b"]}
        design = build_design(axes)
        assert design.oa_name is not None
        assert design.oa_name.startswith("L")

    def test_oa_override(self):
        axes = {1: ["a", "b", "c"]}
        design = build_design(axes, oa_override="L9")
        assert design.oa_name == "L9"
        assert design.n_runs == 9

    def test_run_ids_are_sequential(self):
        axes = {1: ["a", "b", "c"]}
        design = build_design(axes)
        ids = [r.run_id for r in design.rows]
        assert ids == list(range(1, len(ids) + 1))
```

**GREEN 2 -- Implement `build_design()`**

**REFACTOR -- Clean up, verify with ruff**

**Commit:**
```bash
git add agent-evals/src/agent_evals/taguchi/factors.py agent-evals/tests/test_taguchi_factors.py
git commit -m "feat(taguchi): add factor mapper for axes and models

Maps variant axes (with 3-5 levels each) and optional model list
to TaguchiFactorDef objects. build_design() selects an OA and
produces row-level assignments.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E1-S3: Composite Variant

**User Story:** As a developer, I want a variant that combines one variant from each axis into a single rendered output so that Taguchi runs test complete configurations.

**Acceptance Criteria:**

```gherkin
Feature: Composite Variant

  Scenario: Combine two single-axis variants
    Given a Structure variant producing "STRUCTURE_OUTPUT"
    And a Metadata variant producing "METADATA_OUTPUT"
    When I create a CompositeVariant and call render()
    Then the output contains "STRUCTURE_OUTPUT"
    And the output contains "METADATA_OUTPUT"

  Scenario: Metadata name reflects all components
    Given components from axes 1 and 2 named "flat" and "summary"
    When I get the composite's metadata
    Then the name contains "flat" and "summary"

  Scenario: Setup delegates to all components
    Given two components that track setup calls
    When I call composite.setup(doc_tree)
    Then both components received setup()

  Scenario: Teardown delegates to all components
    Given two components that track teardown calls
    When I call composite.teardown()
    Then both components received teardown()

  Scenario: Empty components rejected
    When I create a CompositeVariant with empty components
    Then a ValueError is raised

  Scenario: Axis number preserved in metadata
    Given components from axes 1, 3, and 7
    When I get the composite's metadata
    Then axis is 0 (composite = synthetic baseline)
```

**Files:**
- Create: `agent-evals/src/agent_evals/taguchi/composite.py`
- Test: `agent-evals/tests/test_composite_variant.py`

**TDD Cycle:**

**RED 1 -- Core behavior**
```python
# agent-evals/tests/test_composite_variant.py
"""Tests for CompositeVariant combining multiple axis variants."""

import pytest

from agent_evals.taguchi.composite import CompositeVariant
from agent_evals.variants.base import IndexVariant, VariantMetadata


class StubVariant(IndexVariant):
    """Minimal test stub."""

    def __init__(self, name: str, axis: int, output: str):
        self._name = name
        self._axis = axis
        self._output = output
        self.setup_called = False
        self.teardown_called = False

    def metadata(self) -> VariantMetadata:
        return VariantMetadata(
            name=self._name, axis=self._axis,
            category="test", description="stub",
        )

    def render(self, doc_tree):
        return self._output

    def setup(self, doc_tree):
        self.setup_called = True

    def teardown(self):
        self.teardown_called = True


class TestCompositeVariantCreation:
    """Creating a CompositeVariant from component variants."""

    def test_accepts_valid_components(self):
        v1 = StubVariant("flat", 1, "output1")
        composite = CompositeVariant(components={1: v1})
        assert composite is not None

    def test_rejects_empty_components(self):
        with pytest.raises(ValueError, match="at least one"):
            CompositeVariant(components={})


class TestCompositeVariantMetadata:
    """Metadata reflects the combination of components."""

    def test_name_contains_all_component_names(self):
        v1 = StubVariant("flat", 1, "")
        v2 = StubVariant("summary", 2, "")
        composite = CompositeVariant(components={1: v1, 2: v2})
        meta = composite.metadata()
        assert "flat" in meta.name
        assert "summary" in meta.name

    def test_axis_is_zero_for_composite(self):
        v1 = StubVariant("flat", 1, "")
        composite = CompositeVariant(components={1: v1})
        assert composite.metadata().axis == 0

    def test_category_is_composite(self):
        v1 = StubVariant("flat", 1, "")
        composite = CompositeVariant(components={1: v1})
        assert composite.metadata().category == "composite"


class TestCompositeVariantRender:
    """Render combines all component outputs."""

    def test_output_contains_all_components(self):
        v1 = StubVariant("flat", 1, "STRUCT_MARKER")
        v2 = StubVariant("summary", 2, "META_MARKER")
        composite = CompositeVariant(components={1: v1, 2: v2})
        result = composite.render(None)
        assert "STRUCT_MARKER" in result
        assert "META_MARKER" in result

    def test_output_is_nonempty(self):
        v1 = StubVariant("flat", 1, "content")
        composite = CompositeVariant(components={1: v1})
        assert len(composite.render(None)) > 0


class TestCompositeVariantLifecycle:
    """Setup and teardown delegate to all components."""

    def test_setup_calls_all_components(self):
        v1 = StubVariant("a", 1, "")
        v2 = StubVariant("b", 2, "")
        composite = CompositeVariant(components={1: v1, 2: v2})
        composite.setup(None)
        assert v1.setup_called
        assert v2.setup_called

    def test_teardown_calls_all_components(self):
        v1 = StubVariant("a", 1, "")
        v2 = StubVariant("b", 2, "")
        composite = CompositeVariant(components={1: v1, 2: v2})
        composite.teardown()
        assert v1.teardown_called
        assert v2.teardown_called
```

Run: FAIL.
Implement. Run: PASS. Refactor. Commit.

```bash
git commit -m "feat(taguchi): add CompositeVariant for multi-axis combinations

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E2-S1: Multi-Model LLM Client Pool

**User Story:** As a developer, I want a pool of LLM clients (one per model) so that multi-model Taguchi runs can route each OA row to the correct model.

**Acceptance Criteria:**

```gherkin
Feature: LLM Client Pool

  Scenario: Create pool with multiple models
    Given models ["claude-sonnet", "gpt-4o", "gemini-flash"]
    When I create an LLMClientPool
    Then it holds 3 clients

  Scenario: Get client by model name
    Given a pool with model "claude-sonnet"
    When I call get_client("claude-sonnet")
    Then I receive an LLMClient with model="claude-sonnet"

  Scenario: Unknown model raises KeyError
    Given a pool with model "claude-sonnet"
    When I call get_client("unknown-model")
    Then a KeyError is raised

  Scenario: Models property lists all models
    Given a pool with ["a", "b", "c"]
    When I access pool.models
    Then I get ["a", "b", "c"]
```

**Files:**
- Create: `agent-evals/src/agent_evals/llm/client_pool.py`
- Test: `agent-evals/tests/test_client_pool.py`

**TDD Cycle:**

**RED**
```python
# agent-evals/tests/test_client_pool.py
"""Tests for LLMClientPool managing multiple model clients."""

import pytest

from agent_evals.llm.client_pool import LLMClientPool


class TestLLMClientPool:
    """Pool of LLMClient instances for multi-model runs."""

    def test_create_with_models(self):
        pool = LLMClientPool(
            models=["model-a", "model-b"],
            api_key="test-key",
        )
        assert len(pool.models) == 2

    def test_get_client_returns_correct_model(self):
        pool = LLMClientPool(models=["model-a"], api_key="test-key")
        client = pool.get_client("model-a")
        assert client.model == "model-a"

    def test_get_unknown_model_raises(self):
        pool = LLMClientPool(models=["model-a"], api_key="test-key")
        with pytest.raises(KeyError, match="model-b"):
            pool.get_client("model-b")

    def test_models_property(self):
        pool = LLMClientPool(
            models=["a", "b", "c"], api_key="test-key",
        )
        assert pool.models == ["a", "b", "c"]

    def test_temperature_passed_to_all_clients(self):
        pool = LLMClientPool(
            models=["a", "b"], api_key="key", temperature=0.7,
        )
        assert pool.get_client("a").temperature == 0.7
        assert pool.get_client("b").temperature == 0.7
```

GREEN, REFACTOR, Commit.

```bash
git commit -m "feat(llm): add LLMClientPool for multi-model evaluation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Sprint 2: Core Pipeline

**Goal:** Wire the Taguchi engine into a working runner, add statistical analysis, and expose via CLI.

---

### E1-S4: Taguchi Runner

**User Story:** As a developer, I want a runner that executes trials based on OA rows (composite variants + models) instead of the full Cartesian product so that evaluation runs are orders of magnitude smaller.

**Acceptance Criteria:**

```gherkin
Feature: Taguchi Runner

  Scenario: Work items generated from OA rows
    Given a TaguchiDesign with 9 rows
    And 10 tasks and 5 repetitions
    When I build work items
    Then there are 9 * 10 * 5 = 450 items (not 47 * 10 * 5)

  Scenario: Each trial uses the correct composite variant
    Given OA row 3 assigns axis_1=flat and axis_2=summary
    When trial runs for row 3
    Then the variant used is CompositeVariant({1: flat, 2: summary})

  Scenario: Each trial uses the correct model
    Given OA row 3 assigns model=gpt-4o
    When trial runs for row 3
    Then the LLM client used is the gpt-4o client

  Scenario: Results grouped by OA row
    Given a completed Taguchi run
    When I access results
    Then trials are groupable by oa_row_id

  Scenario: Single-model run uses same client for all rows
    Given 1 model configured
    When the Taguchi run executes
    Then all trials use the same LLMClient

  Scenario: Progress callback fires per trial
    Given a progress callback
    When trials complete
    Then callback receives (completed_count, total_count, trial_result)

  Scenario: TaguchiRunner passes through source parameter
    Given a TaguchiDesign with tasks from source "repliqa"
    When I call TaguchiRunner.run(source="repliqa")
    Then all resulting TrialResults have source="repliqa"
```

> **Note (2026-02-23):** `EvalRunner.run()` and `_run_trial()` now accept a
> `source: str = "gold_standard"` parameter, and `TrialResult` has a
> `source` field. `TaguchiRunner` must pass `source` through to every trial
> it creates, mirroring the existing runner contract.

**Files:**
- Create: `agent-evals/src/agent_evals/taguchi/runner.py`
- Test: `agent-evals/tests/test_taguchi_runner.py`

**TDD Cycle:** Write tests using a mock LLMClient that returns canned responses. Implementation reuses the trial execution logic pattern from `EvalRunner._run_trial()` but generates work items from OA rows. Each test class focuses on one scenario above.

**Key implementation detail:** `TaguchiRunner` holds a `dict[str, LLMClient]` (from the pool) and a `dict[str, IndexVariant]` (all registered variants by name). For each OA row, it:
1. Looks up the variant for each axis assignment
2. Creates a `CompositeVariant`
3. Looks up the LLMClient for the model assignment
4. Runs all tasks x reps against that combo

```bash
git commit -m "feat(taguchi): add TaguchiRunner with OA-based work item generation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E1-S5: S/N Ratio and ANOVA Analysis

**User Story:** As a researcher, I want S/N ratios and ANOVA decomposition computed from Taguchi results so that I can identify which axes matter most and what the optimal configuration is.

**Acceptance Criteria:**

```gherkin
Feature: S/N Ratio and ANOVA

  Scenario: S/N ratio for "larger is better"
    Given row scores {1: [0.8, 0.9, 0.85], 2: [0.5, 0.6, 0.55]}
    When I compute S/N ratios with quality_type="larger_is_better"
    Then row 1 has higher S/N than row 2

  Scenario: Main effects show best level per factor
    Given a design with factor "axis_1" levels ["flat", "3tier"]
    And "3tier" rows consistently score higher
    When I compute main effects
    Then axis_1 main effect for "3tier" > "flat"

  Scenario: ANOVA produces F-ratios and p-values
    Given a completed design with real score variance
    When I run ANOVA
    Then each factor has an F-ratio > 0
    And each factor has a p-value between 0 and 1

  Scenario: ANOVA eta-squared sums to approximately 1
    Given ANOVA results
    When I sum all eta_squared values plus error
    Then the total is approximately 1.0 (within 0.01)

  Scenario: Optimal prediction selects highest S/N levels
    Given main effects showing "3tier" best for axis_1 and "yaml" best for axis_3
    When I predict optimal
    Then the config includes axis_1="3tier" and axis_3="yaml"

  Scenario: Predicted S/N is additive
    Given main effects and a grand mean
    When I compute predicted S/N for the optimal config
    Then predicted = grand_mean + sum(level_effect - factor_mean for each factor)

  Scenario: Prediction interval computed for optimal configuration
    Given main effects and error variance from ANOVA
    When I compute prediction_interval for optimal S/N
    Then I get a (lower, upper) interval at 95% confidence

  Scenario: Confirmation runs flagged when outside prediction interval
    Given predicted S/N = 5.2 with interval (4.8, 5.6)
    And confirmation run observed S/N = 4.1 (>2 sigma below)
    When I validate_confirmation
    Then flag="requires_further_investigation" is set
```

**Files:**
- Create: `agent-evals/src/agent_evals/taguchi/analysis.py`
- Test: `agent-evals/tests/test_taguchi_analysis.py`

**TDD Cycle:** Write tests with hand-computed expected values from simple 2-3 factor designs where you can verify ANOVA by hand. Use `scipy.stats.f_oneway` as a cross-check for the F-ratio on simple cases.

```bash
git commit -m "feat(taguchi): add S/N ratio, ANOVA decomposition, and optimal prediction

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E2-S2: CLI Mode and Models Flags

**User Story:** As a user, I want `--mode taguchi` and `--models` CLI flags so that I can run Taguchi experiments with multiple AIs from the command line.

**Acceptance Criteria:**

```gherkin
Feature: CLI Flags

  Scenario: --mode taguchi is accepted
    When I pass --mode taguchi to the parser
    Then args.mode == "taguchi"

  Scenario: --mode defaults to "full"
    When I pass no --mode flag
    Then resolved config has mode="full"

  Scenario: --models accepts comma-separated list
    When I pass --models "claude,gpt-4o,gemini"
    Then resolved config has models=["claude", "gpt-4o", "gemini"]

  Scenario: --models in YAML config
    Given config YAML with models: ["claude", "gpt-4o"]
    When config is resolved
    Then models=["claude", "gpt-4o"]

  Scenario: --oa-type forces specific array
    When I pass --oa-type L54
    Then resolved config has oa_type="L54"

  Scenario: --confirmation-runs sets count
    When I pass --confirmation-runs 3
    Then resolved config has confirmation_runs=3

  Scenario: --report accepts valid formats
    When I pass --report both
    Then resolved config has report="both"

  Scenario: --budget sets dollar cap
    When I pass --budget 50.00
    Then resolved config has budget=50.0

  Scenario: --dashboard enables web UI
    When I pass --dashboard
    Then resolved config has dashboard=True

  Scenario: --model-budgets accepts per-model caps
    When I pass --model-budgets "claude=20.00,gpt-4o=30.00"
    Then resolved config has model_budgets={"claude": 20.0, "gpt-4o": 30.0}

  Scenario: Per-model budgets in YAML config
    Given config YAML with:
      model_budgets:
        claude: 20.00
        gpt-4o: 30.00
    When config is resolved
    Then model_budgets={"claude": 20.0, "gpt-4o": 30.0}

  Scenario: Full mode with multiple models runs sequentially
    Given --mode full --models mock_a,mock_b
    When the run executes
    Then the full Cartesian sweep runs once for mock_a
    And then once for mock_b sequentially

  Scenario: Backward compat -- old flags still work
    When I pass --model claude --axis 3
    Then the run executes in full mode with single model

  Scenario: Existing dataset flags preserved alongside new flags
    When I pass --source repliqa --mode taguchi --models "claude,gpt"
    Then resolved config has source="repliqa" and mode="taguchi"
    And models=["claude", "gpt"]
    And existing flags --dataset-limit, --dataset-cache-dir, --prepare-datasets, --list-datasets still work
```

> **Note (2026-02-23):** The CLI already has dataset flags (`--source`,
> `--dataset-limit`, `--dataset-cache-dir`, `--prepare-datasets`,
> `--list-datasets`) added with the dataset adapter system. New Taguchi/multi-model
> flags (`--mode`, `--models`, `--oa-type`, etc.) must coexist without
> overwriting these. Verify no argument name collisions in `build_parser()`.

**Files:**
- Modify: `agent-evals/src/agent_evals/cli.py`
- Modify: `agent-evals/tests/test_evals_cli.py`

**TDD Cycle:** Write tests for `build_parser()` and `resolve_config()` first, verifying new flags parse correctly. Then test routing logic in `_run_evaluation()` with mocked runners.

```bash
git commit -m "feat(cli): add --mode, --models, --oa-type, --report, --dashboard flags

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Sprint 3: Observatory

**Goal:** Build the telemetry backbone -- persistent storage, event tracking, and terminal monitoring.

---

### E3-S1: Observatory SQLite Store

**User Story:** As a developer, I want a persistent SQLite store for trial-level telemetry so that data survives across runs and is queryable.

**Acceptance Criteria:**

```gherkin
Feature: Observatory Store

  Scenario: Create a run record
    Given an empty observatory database
    When I create_run("run_001", "taguchi", config={...})
    Then the runs table has 1 row

  Scenario: Record trial events
    Given an active run "run_001"
    When I record 3 trial events
    Then the trials table has 3 rows for run_001

  Scenario: Finish a run
    Given an active run "run_001"
    When I finish_run("run_001")
    Then the run status is "completed" with a finished_at timestamp

  Scenario: List all runs
    Given 3 completed runs in the database
    When I list_runs()
    Then I get 3 RunSummary objects with stats

  Scenario: Get run summary with aggregates
    Given run "run_001" with 100 trials
    When I get_run_summary("run_001")
    Then summary includes total_trials=100, total_cost, avg_latency

  Scenario: Filter trials by model
    Given run "run_001" with trials from "claude" and "gpt"
    When I get_trials("run_001", model="claude")
    Then I only get claude trials

  Scenario: Database created on first use
    Given no observatory.db file exists
    When I instantiate ObservatoryStore
    Then observatory.db is created with the correct schema

  Scenario: Concurrent writes don't corrupt
    Given an active run
    When 10 threads record trials simultaneously
    Then all trials are recorded without errors

  Scenario: Observatory tracks cost per source
    Given run "run_001" with trials from source "gold_standard" and "repliqa"
    When I get_run_summary("run_001")
    Then summary includes per-source cost breakdowns
    And the trials table includes a source column
    And cost breakdowns can be filtered by source
```

> **Note (2026-02-23):** `TrialResult` now includes `source: str = "gold_standard"`.
> The trials table schema must include a `source TEXT` column so that cost
> and performance breakdowns can be segmented by task source (e.g.,
> gold_standard vs. repliqa vs. swe-bench).

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/__init__.py`
- Create: `agent-evals/src/agent_evals/observatory/store.py`
- Test: `agent-evals/tests/test_observatory_store.py`

**TDD Cycle:** Each scenario becomes a test method. Use `tmp_path` fixture for test databases. Test concurrency with `ThreadPoolExecutor`.

```bash
git commit -m "feat(observatory): add SQLite store for trial telemetry

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E3-S2: Observatory Event Tracker

**User Story:** As a developer, I want a thread-safe event tracker with real-time listeners so that dashboards can update as trials complete.

**Acceptance Criteria:**

```gherkin
Feature: Event Tracker

  Scenario: Record events thread-safely
    Given a tracker with a store
    When 10 threads record events concurrently
    Then all events are persisted without data loss

  Scenario: Listeners notified on each event
    Given a tracker with a registered listener
    When I record an event
    Then the listener callback receives the event

  Scenario: Multiple listeners all notified
    Given a tracker with 3 registered listeners
    When I record an event
    Then all 3 listeners receive it

  Scenario: Stats aggregate correctly
    Given a tracker with 5 recorded events
    When I check tracker.stats
    Then total_trials=5 and total_cost matches sum

  Scenario: Stats include per-model breakdown
    Given events from "claude" and "gpt"
    When I check tracker.stats
    Then per_model includes both with correct counts

  Scenario: Anomaly detection flags expensive calls
    Given running average cost for "claude" is $0.02 per call
    When a call costs $0.08 (>3x average)
    Then an anomaly_alert is emitted with the call details

  Scenario: Burn rate alert triggers when rate exceeds threshold
    Given a running tracker with average burn rate $1.50/min
    When a burst of expensive calls pushes rate to $3.50/min
    Then a burn_rate_alert is emitted to listeners

  Scenario: Per-model budget enforcement halts model when exceeded
    Given model_budgets={"claude": 5.0, "gpt": 10.0}
    And "claude" has accumulated $4.90 in costs
    When a trial for "claude" costs $0.15 (total $5.05 > $5.0 budget)
    Then a model_budget_exceeded event is emitted for "claude"
    And subsequent "claude" trials are skipped
    And "gpt" trials continue normally
```

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/tracker.py`
- Test: `agent-evals/tests/test_observatory_tracker.py`

```bash
git commit -m "feat(observatory): add thread-safe event tracker with listeners

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E3-S3: Observatory Terminal Dashboard

**User Story:** As a user, I want a Rich terminal dashboard showing live progress, per-model stats, and budget during eval runs.

**Acceptance Criteria:**

```gherkin
Feature: Terminal Dashboard

  Scenario: Dashboard renders without errors
    Given a tracker with some events
    When I create a TerminalDashboard and call render()
    Then it produces a Rich renderable without exceptions

  Scenario: Progress bar reflects completion
    Given 50 of 100 trials complete
    When the dashboard renders
    Then progress shows 50%

  Scenario: Per-model table shows all models
    Given events from ["claude", "gpt", "gemini"]
    When the dashboard renders
    Then the model table has 3 rows

  Scenario: Budget display shows spend vs cap
    Given budget=$30 and $12 spent
    When the dashboard renders
    Then budget section shows "$12.00 / $30.00"

  Scenario: Alerts appear in feed
    Given a budget warning alert
    When the dashboard renders
    Then the alert text is visible
```

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/terminal.py`
- Test: `agent-evals/tests/test_observatory_terminal.py`

**Note:** Tests focus on the data model and rendering logic, not actual terminal output. Use `rich.console.Console(file=StringIO())` to capture output.

```bash
git commit -m "feat(observatory): add Rich terminal dashboard

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E6-S1: Model Catalog Store

**User Story:** As a developer, I want a persistent store of OpenRouter model metadata so that model information is available for browsing, filtering, and test configuration.

**Acceptance Criteria:**

```gherkin
Feature: Model Catalog Store

  Scenario: Store a model and retrieve it by ID
    Given an empty model catalog
    When I store a model with id "anthropic/claude-sonnet-4.5"
    And I retrieve by id "anthropic/claude-sonnet-4.5"
    Then I receive the stored model metadata

  Scenario: Upsert updates existing model metadata without losing first_seen
    Given a model stored with first_seen="2026-01-15"
    When I upsert the same model with updated pricing
    Then the pricing is updated
    And first_seen remains "2026-01-15"

  Scenario: Mark models as removed
    Given a model "old-model" in the catalog
    When I mark_removed("old-model")
    Then the model has removed_at set to a timestamp
    And the model record is preserved (not deleted)

  Scenario: Get all active models excludes removed
    Given 5 models in the catalog, 1 marked as removed
    When I get_active_models()
    Then I receive 4 models

  Scenario: Filter models by price range (free)
    Given models with prompt_price 0.0 and 0.003
    When I filter with free=True
    Then only the zero-cost model is returned

  Scenario: Filter models by price range (max price)
    Given models with prompt_price 0.001, 0.005, 0.010
    When I filter with max_price=0.005
    Then models with prompt_price <= 0.005 are returned

  Scenario: Filter models by minimum context length
    Given models with context_length 4096, 32768, 200000
    When I filter with min_context=32768
    Then only models with context_length >= 32768 are returned

  Scenario: Filter models by modality
    Given models with modality "text" and "text+image"
    When I filter with modality="text+image"
    Then only multimodal models are returned

  Scenario: Filter models by supported capabilities (AND logic)
    Given models with various supported_params
    When I filter with capabilities=["tools", "json_mode"]
    Then only models supporting both capabilities are returned

  Scenario: Filter models by provider/tokenizer
    Given models with tokenizer "claude" and "gpt"
    When I filter with tokenizer="claude"
    Then only Claude-tokenizer models are returned

  Scenario: Combine multiple filters simultaneously (AND)
    Given a diverse set of models
    When I filter with free=True AND min_context=32768
    Then only models matching both criteria are returned

  Scenario: Log a sync run with counts
    Given a sync operation that added 5 and removed 2 models
    When I log_sync(added=5, removed=2, total=150)
    Then the sync_log table has a new entry

  Scenario: Retrieve sync history
    Given 3 previous sync runs logged
    When I get_sync_history()
    Then I receive 3 entries ordered by timestamp descending
```

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/model_catalog.py`
- Test: `agent-evals/tests/test_model_catalog.py`

**TDD Cycle:**

**RED 1 -- Model storage and retrieval tests**
```python
# agent-evals/tests/test_model_catalog.py
"""Tests for model catalog store with filtering and sync logging."""

import sqlite3

import pytest

from agent_evals.observatory.model_catalog import ModelCatalog


class TestModelStorage:
    """Store and retrieve model metadata."""

    def test_store_and_retrieve_by_id(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(
            id="anthropic/claude-sonnet-4.5",
            name="Claude Sonnet 4.5",
            context_length=200000,
            prompt_price=0.003,
            completion_price=0.015,
            modality="text+image",
            tokenizer="claude",
        )
        model = catalog.get_model("anthropic/claude-sonnet-4.5")
        assert model["name"] == "Claude Sonnet 4.5"
        assert model["context_length"] == 200000

    def test_upsert_preserves_first_seen(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(id="m1", name="M1", context_length=4096,
                             prompt_price=0.001, completion_price=0.002)
        first = catalog.get_model("m1")["first_seen"]
        catalog.upsert_model(id="m1", name="M1 Updated", context_length=8192,
                             prompt_price=0.002, completion_price=0.004)
        updated = catalog.get_model("m1")
        assert updated["first_seen"] == first
        assert updated["name"] == "M1 Updated"

    def test_mark_removed_sets_timestamp(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(id="old", name="Old", context_length=4096,
                             prompt_price=0.0, completion_price=0.0)
        catalog.mark_removed("old")
        model = catalog.get_model("old")
        assert model["removed_at"] is not None

    def test_get_active_excludes_removed(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        for i in range(5):
            catalog.upsert_model(id=f"m{i}", name=f"M{i}", context_length=4096,
                                 prompt_price=0.0, completion_price=0.0)
        catalog.mark_removed("m0")
        active = catalog.get_active_models()
        assert len(active) == 4
        assert all(m["id"] != "m0" for m in active)
```

Run: `~/.local/bin/uv run pytest agent-evals/tests/test_model_catalog.py::TestModelStorage -v`
Expected: FAIL -- `ModuleNotFoundError: No module named 'agent_evals.observatory.model_catalog'`

**GREEN 1 -- Create ModelCatalog class with SQLite schema and basic CRUD**

Create `agent-evals/src/agent_evals/observatory/model_catalog.py` with the `ModelCatalog` class, `models` table (id TEXT PK, name TEXT, created INTEGER, context_length INTEGER, prompt_price REAL, completion_price REAL, modality TEXT, tokenizer TEXT, supported_params TEXT JSON, raw_json TEXT, first_seen TEXT, last_seen TEXT, removed_at TEXT nullable), and `sync_log` table (timestamp, models_added, models_removed, total_count).

Run: PASS.

**RED 2 -- Filtering tests**
```python
class TestModelFiltering:
    """Filter models by various criteria."""

    def test_filter_free_models(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(id="free", name="Free", context_length=4096,
                             prompt_price=0.0, completion_price=0.0)
        catalog.upsert_model(id="paid", name="Paid", context_length=4096,
                             prompt_price=0.003, completion_price=0.015)
        results = catalog.filter_models(free=True)
        assert len(results) == 1
        assert results[0]["id"] == "free"

    def test_filter_max_price(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        for price in [0.001, 0.005, 0.010]:
            catalog.upsert_model(id=f"m{price}", name=f"M", context_length=4096,
                                 prompt_price=price, completion_price=price)
        results = catalog.filter_models(max_price=0.005)
        assert len(results) == 2

    def test_filter_min_context(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        for ctx in [4096, 32768, 200000]:
            catalog.upsert_model(id=f"m{ctx}", name=f"M", context_length=ctx,
                                 prompt_price=0.0, completion_price=0.0)
        results = catalog.filter_models(min_context=32768)
        assert len(results) == 2

    def test_filter_modality(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(id="text", name="T", context_length=4096,
                             prompt_price=0.0, completion_price=0.0, modality="text")
        catalog.upsert_model(id="multi", name="M", context_length=4096,
                             prompt_price=0.0, completion_price=0.0,
                             modality="text+image")
        results = catalog.filter_models(modality="text+image")
        assert len(results) == 1
        assert results[0]["id"] == "multi"

    def test_filter_capabilities_and_logic(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(id="full", name="Full", context_length=4096,
                             prompt_price=0.0, completion_price=0.0,
                             supported_params=["tools", "json_mode", "streaming"])
        catalog.upsert_model(id="partial", name="Partial", context_length=4096,
                             prompt_price=0.0, completion_price=0.0,
                             supported_params=["tools"])
        results = catalog.filter_models(capabilities=["tools", "json_mode"])
        assert len(results) == 1
        assert results[0]["id"] == "full"

    def test_filter_tokenizer(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(id="c1", name="C1", context_length=4096,
                             prompt_price=0.0, completion_price=0.0,
                             tokenizer="claude")
        catalog.upsert_model(id="g1", name="G1", context_length=4096,
                             prompt_price=0.0, completion_price=0.0,
                             tokenizer="gpt")
        results = catalog.filter_models(tokenizer="claude")
        assert len(results) == 1
        assert results[0]["id"] == "c1"

    def test_combine_multiple_filters(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(id="match", name="Match", context_length=100000,
                             prompt_price=0.0, completion_price=0.0)
        catalog.upsert_model(id="no_ctx", name="No", context_length=4096,
                             prompt_price=0.0, completion_price=0.0)
        catalog.upsert_model(id="no_price", name="No", context_length=100000,
                             prompt_price=0.005, completion_price=0.005)
        results = catalog.filter_models(free=True, min_context=32768)
        assert len(results) == 1
        assert results[0]["id"] == "match"
```

Run: FAIL. Implement filtering. Run: PASS.

**RED 3 -- Sync logging tests**
```python
class TestSyncLogging:
    """Log and retrieve sync run history."""

    def test_log_sync_run(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.log_sync(added=5, removed=2, total=150)
        history = catalog.get_sync_history()
        assert len(history) == 1
        assert history[0]["models_added"] == 5

    def test_sync_history_ordered_descending(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.log_sync(added=1, removed=0, total=10)
        catalog.log_sync(added=2, removed=1, total=11)
        catalog.log_sync(added=0, removed=3, total=8)
        history = catalog.get_sync_history()
        assert len(history) == 3
        assert history[0]["models_added"] == 0  # most recent first
```

Run: FAIL. Implement. Run: PASS.

**REFACTOR -- Clean up, verify with ruff**

Run full suite: `~/.local/bin/uv run pytest agent-evals/tests/test_model_catalog.py -v`
Run project-wide: `~/.local/bin/uv run pytest` (verify no regressions)

**Commit:**
```bash
git add agent-evals/src/agent_evals/observatory/model_catalog.py agent-evals/tests/test_model_catalog.py
git commit -m "feat(models): add model catalog store with filtering

SQLite-backed model catalog with upsert, soft-delete, multi-criteria
filtering (price, context, modality, capabilities, tokenizer), and
sync run logging. Supports AND logic for combined filters.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E6-S2: Background Model Sync

**User Story:** As a user, I want the model catalog to automatically sync with OpenRouter so that I always have up-to-date model information without manual intervention.

**Acceptance Criteria:**

```gherkin
Feature: Background Model Sync

  Scenario: Fetch all models from OpenRouter
    Given the OpenRouter API is available
    When I call fetch_remote_models()
    Then I receive a list of model metadata dicts

  Scenario: Detect newly added models
    Given local catalog has models ["a", "b"]
    And remote has models ["a", "b", "c"]
    When I compute_diff(local, remote)
    Then added=["c"]

  Scenario: Detect removed models
    Given local catalog has models ["a", "b", "c"]
    And remote has models ["a", "b"]
    When I compute_diff(local, remote)
    Then removed=["c"]

  Scenario: Detect price changes between syncs
    Given local model "a" has prompt_price=0.003
    And remote model "a" has prompt_price=0.005
    When I compute_diff(local, remote)
    Then price_changes includes {"id": "a", "old": 0.003, "new": 0.005}

  Scenario: Run immediate sync on dashboard startup
    Given the dashboard is starting
    When sync_on_startup() is called
    Then a full sync executes immediately

  Scenario: Schedule periodic sync at configurable interval
    Given sync_interval_hours=6
    When I start_periodic_sync()
    Then a background task is scheduled to run every 6 hours

  Scenario: Cancel scheduled sync on shutdown
    Given a periodic sync is running
    When I call stop_periodic_sync()
    Then the background task is cancelled cleanly

  Scenario: CLI triggers one-time sync
    When I run "agent-evals models sync"
    Then a sync executes and reports added/removed counts

  Scenario: CLI shows last sync info
    When I run "agent-evals models sync --status"
    Then I see the timestamp, added, removed, and total from last sync

  Scenario: SSE notification sent when sync completes
    Given a web dashboard SSE connection
    When a sync completes
    Then an SSE event with type "sync_complete" is sent

  Scenario: Handle OpenRouter API errors gracefully
    Given the OpenRouter API returns a 500 error
    When sync runs
    Then an error is logged
    And the sync does not crash
    And a retry is scheduled
```

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/model_sync.py`
- Test: `agent-evals/tests/test_model_sync.py`

**TDD Cycle:**

**RED 1 -- Fetch and diff tests**
```python
# agent-evals/tests/test_model_sync.py
"""Tests for background model sync with OpenRouter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_evals.observatory.model_sync import ModelSync, SyncDiff


class TestSyncDiff:
    """Compute differences between local and remote model lists."""

    def test_detect_added_models(self):
        local = {"a": {}, "b": {}}
        remote = {"a": {}, "b": {}, "c": {"id": "c", "name": "C"}}
        diff = ModelSync.compute_diff(local, remote)
        assert "c" in diff.added

    def test_detect_removed_models(self):
        local = {"a": {}, "b": {}, "c": {}}
        remote = {"a": {}, "b": {}}
        diff = ModelSync.compute_diff(local, remote)
        assert "c" in diff.removed

    def test_detect_price_changes(self):
        local = {"a": {"prompt_price": 0.003}}
        remote = {"a": {"id": "a", "prompt_price": 0.005}}
        diff = ModelSync.compute_diff(local, remote)
        assert len(diff.price_changes) == 1
        assert diff.price_changes[0]["old"] == 0.003
        assert diff.price_changes[0]["new"] == 0.005

    def test_no_changes(self):
        local = {"a": {"prompt_price": 0.003}}
        remote = {"a": {"id": "a", "prompt_price": 0.003}}
        diff = ModelSync.compute_diff(local, remote)
        assert len(diff.added) == 0
        assert len(diff.removed) == 0
        assert len(diff.price_changes) == 0
```

Run: `~/.local/bin/uv run pytest agent-evals/tests/test_model_sync.py::TestSyncDiff -v`
Expected: FAIL

**GREEN 1 -- Implement SyncDiff and compute_diff()**

**RED 2 -- Sync execution tests**
```python
class TestModelSyncExecution:
    """Execute sync against catalog store."""

    def test_sync_adds_new_models(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        sync = ModelSync(catalog=catalog)
        with patch.object(sync, "fetch_remote_models", return_value=[
            {"id": "new", "name": "New", "context_length": 4096,
             "pricing": {"prompt": "0.001", "completion": "0.002"}},
        ]):
            result = sync.run_sync()
        assert result.added_count == 1
        assert catalog.get_model("new") is not None

    def test_sync_marks_removed_models(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.upsert_model(id="old", name="Old", context_length=4096,
                             prompt_price=0.0, completion_price=0.0)
        sync = ModelSync(catalog=catalog)
        with patch.object(sync, "fetch_remote_models", return_value=[]):
            result = sync.run_sync()
        assert result.removed_count == 1
        model = catalog.get_model("old")
        assert model["removed_at"] is not None

    def test_sync_logs_to_catalog(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        sync = ModelSync(catalog=catalog)
        with patch.object(sync, "fetch_remote_models", return_value=[]):
            sync.run_sync()
        history = catalog.get_sync_history()
        assert len(history) == 1

    def test_api_error_handled_gracefully(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        sync = ModelSync(catalog=catalog)
        with patch.object(sync, "fetch_remote_models",
                          side_effect=Exception("API error")):
            result = sync.run_sync()
        assert result.error is not None
```

Run: FAIL. Implement. Run: PASS.

**RED 3 -- Periodic sync and CLI tests**
```python
class TestPeriodicSync:
    """Schedule and cancel periodic sync."""

    def test_start_periodic_creates_task(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        sync = ModelSync(catalog=catalog, interval_hours=6)
        sync.start_periodic()
        assert sync.is_running
        sync.stop_periodic()

    def test_stop_periodic_cancels_task(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        sync = ModelSync(catalog=catalog, interval_hours=6)
        sync.start_periodic()
        sync.stop_periodic()
        assert not sync.is_running


class TestModelSyncCLI:
    """CLI subcommands for model sync."""

    def test_sync_command_triggers_sync(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        sync = ModelSync(catalog=catalog)
        with patch.object(sync, "fetch_remote_models", return_value=[]):
            result = sync.run_sync()
        assert result is not None

    def test_sync_status_shows_last_run(self, tmp_path):
        catalog = ModelCatalog(tmp_path / "models.db")
        catalog.log_sync(added=3, removed=1, total=50)
        history = catalog.get_sync_history()
        assert history[0]["models_added"] == 3
```

Run: FAIL. Implement. Run: PASS.

**REFACTOR -- Clean up, verify with ruff**

Run full suite: `~/.local/bin/uv run pytest agent-evals/tests/test_model_sync.py -v`
Run project-wide: `~/.local/bin/uv run pytest` (verify no regressions)

**Commit:**
```bash
git add agent-evals/src/agent_evals/observatory/model_sync.py agent-evals/tests/test_model_sync.py
git commit -m "feat(models): add background sync with change detection

Syncs model catalog with OpenRouter /api/v1/models endpoint. Detects
added/removed models and price changes. Supports periodic scheduling,
CLI trigger, and graceful error handling with retries.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Sprint 4: Reports

**Goal:** Build the research report pipeline: data aggregation, statistical analysis, and dual-format rendering.

---

### E4-S1: Report Data Aggregator

**User Story:** As a developer, I want to aggregate raw trial results into the statistical summaries needed for report generation.

**Acceptance Criteria:**

```gherkin
Feature: Report Data Aggregator

  Scenario: Aggregates per-variant scores
    Given 100 trials across 5 variants
    When I aggregate
    Then by_variant has 5 entries with mean scores

  Scenario: Aggregates per-task-type scores
    Given trials across 3 task types
    When I aggregate
    Then by_task_type has 3 entries

  Scenario: Aggregates per-model scores
    Given trials from 2 models
    When I aggregate
    Then per_model_scores has 2 entries with per-type breakdowns

  Scenario: Includes Taguchi analysis when available
    Given a Taguchi run result
    When I aggregate
    Then anova, main_effects, and sn_ratios are populated

  Scenario: Captures reproducibility metadata
    Given a completed run
    When I aggregate
    Then software_versions includes python, numpy, scipy versions
    And config_dump contains the full resolved config

  Scenario: Captures model versions from API responses
    Given trials from "claude-sonnet-4.5" returning model="claude-3-5-sonnet-20241022"
    When I aggregate
    Then model_versions includes {"claude-sonnet-4.5": "claude-3-5-sonnet-20241022"}

  Scenario: Report segments analysis by source when multiple sources present
    Given a run with tasks from source "gold_standard" and "repliqa"
    When I aggregate
    Then by_source has 2 entries with per-source mean scores
    And per-source variant breakdowns are included
    And the executive summary notes multiple task sources were used
```

> **Note (2026-02-23):** `TrialResult.source` (default `"gold_standard"`)
> already exists. The aggregator must group by `source` when multiple sources
> are present. The `model_versions` field must be preserved alongside
> `source` -- both are populated per-trial by the runner.

**Files:**
- Create: `agent-evals/src/agent_evals/report/__init__.py`
- Create: `agent-evals/src/agent_evals/report/aggregator.py`
- Test: `agent-evals/tests/test_report_aggregator.py`

```bash
git commit -m "feat(report): add data aggregator for research reports

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E4-S2: Report Statistical Engine

**User Story:** As a researcher, I want the report to include power analysis, assumptions testing, effect sizes, and multiple comparison corrections so that findings are scientifically rigorous.

**Acceptance Criteria:**

```gherkin
Feature: Statistical Engine

  Scenario: Power analysis computes required sample size
    Given 5 groups and effect_size=0.25
    When I run power_analysis
    Then power is between 0 and 1
    And n_required is a positive integer

  Scenario: Shapiro-Wilk detects non-normal residuals
    Given residuals drawn from a uniform distribution
    When I test_assumptions
    Then normality_p < 0.05 (normality rejected)

  Scenario: Shapiro-Wilk passes for normal residuals
    Given residuals drawn from N(0,1)
    When I test_assumptions
    Then normality_p > 0.05

  Scenario: Levene's test detects unequal variance
    Given group 1 with variance 1 and group 2 with variance 100
    When I test_assumptions
    Then homogeneity_p < 0.05

  Scenario: Cohen's d computed for pairwise results
    Given two groups with known means and SDs
    When I compute_effect_sizes
    Then Cohen's d matches the expected value

  Scenario: Effect size interpretation labels correct
    Given d=0.15 (small), d=0.55 (medium), d=0.95 (large)
    When I compute interpretations
    Then labels are "small", "medium", "large"

  Scenario: Tukey HSD returns all pairwise comparisons
    Given 4 groups
    When I run tukey_hsd
    Then I get 6 pairwise results (4 choose 2)

  Scenario: Benjamini-Hochberg controls FDR
    Given 20 p-values with 5 true positives
    When I apply BH correction at alpha=0.05
    Then significant results are a subset of true positives (approximately)

  Scenario: Rank-biserial r computed for non-parametric comparisons
    Given two groups of ordinal scores
    When I compute_effect_sizes with method="nonparametric"
    Then rank-biserial r is returned alongside Cohen's d

  Scenario: Omega-squared computed for ANOVA factors
    Given ANOVA results with F-ratios
    When I compute omega_squared
    Then each factor has an omega_squared value less biased than eta_squared

  Scenario: Methodology text is auto-generated
    Given a ReportData object
    When I call generate_methodology_text
    Then the text mentions the OA name, n_trials, statistical tests used
```

**Files:**
- Create: `agent-evals/src/agent_evals/report/statistics.py`
- Test: `agent-evals/tests/test_report_statistics.py`

**TDD Cycle:** Tests use known distributions (e.g., `np.random.default_rng(42).normal(...)`) with pre-computed expected values. Cross-check Tukey HSD against `scipy.stats.tukey_hsd`.

```bash
git commit -m "feat(report): add statistical engine with power analysis and assumptions testing

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E4-S3: Report HTML Renderer

**User Story:** As a user, I want a self-contained HTML report with interactive charts so that I can explore results in a browser.

**Acceptance Criteria:**

```gherkin
Feature: HTML Report

  Scenario: Produces valid HTML
    Given a populated ReportData
    When I render to HTML
    Then the output starts with "<!DOCTYPE html>"
    And it contains <html>, <body>, </html>

  Scenario: All sections present
    Given a ReportData with Taguchi analysis
    When I render to HTML
    Then the output contains headings for all 9 report sections:
      1. Executive Summary
      2. Experimental Design
      3. ANOVA Results
      4. Main Effects Analysis
      5. Interaction Effects
      6. Model Comparison
      7. Optimal Configuration
      8. Robustness Analysis
      9. Appendix (includes methodology subsection)

  Scenario: Charts embedded as Plotly JSON
    Given a ReportData with main effects data
    When I render to HTML
    Then the output contains "Plotly.newPlot"

  Scenario: Self-contained (no external file deps)
    Given the rendered HTML
    When I check for external resource links
    Then only CDN scripts (plotly) are external
    And CSS is inline

  Scenario: Executive summary highlights optimal config
    Given optimal_config = {"axis_1": "3tier", "axis_3": "yaml"}
    When I render
    Then the executive summary mentions "3tier" and "yaml"

  Scenario: ANOVA table renders with significance flags
    Given an ANOVA result with p < 0.001 for axis_3
    When I render
    Then the table shows "***" for axis_3
```

**Files:**
- Create: `agent-evals/src/agent_evals/report/html_renderer.py`
- Create: `agent-evals/src/agent_evals/report/charts.py`
- Create: `agent-evals/src/agent_evals/report/templates/report.html`
- Test: `agent-evals/tests/test_report_html.py`

**New dependencies in pyproject.toml:** `jinja2>=3.1`, `plotly>=5.0`

```bash
git commit -m "feat(report): add HTML renderer with embedded Plotly charts

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E4-S4: Report Markdown Renderer

**User Story:** As a user, I want a Markdown report with chart images so that I can commit results to git and view on GitHub.

**Acceptance Criteria:**

```gherkin
Feature: Markdown Report

  Scenario: Produces valid Markdown
    Given a populated ReportData
    When I render to Markdown
    Then the output starts with "# " (heading)

  Scenario: Tables use pipe format
    Given ANOVA data
    When I render
    Then the output contains "| Axis |" table syntax

  Scenario: Chart images saved alongside
    Given a ReportData with main effects
    When I render to /tmp/test_report/
    Then charts/ directory contains PNG files
    And the Markdown references them with ![](charts/...)

  Scenario: All sections present
    Given a full ReportData
    When I render
    Then headings for all 9 sections are present:
      1. Executive Summary
      2. Experimental Design
      3. ANOVA Results
      4. Main Effects Analysis
      5. Interaction Effects
      6. Model Comparison
      7. Optimal Configuration
      8. Robustness Analysis
      9. Appendix (includes methodology subsection)
```

**Files:**
- Create: `agent-evals/src/agent_evals/report/markdown_renderer.py`
- Test: `agent-evals/tests/test_report_markdown.py`

**New dependency:** `matplotlib>=3.7`

```bash
git commit -m "feat(report): add Markdown renderer with matplotlib chart images

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E6-S3: Model Groups

**User Story:** As a user, I want to save named groups of models so that I can reuse common model selections across test runs without re-specifying them each time.

**Acceptance Criteria:**

```gherkin
Feature: Model Groups

  Scenario: Create a group with name and description
    Given an empty model groups store
    When I create_group("fast-models", description="Low-latency models")
    Then the group exists with name "fast-models"

  Scenario: Add models to a group
    Given a group "fast-models"
    When I add_model("fast-models", "anthropic/claude-haiku")
    Then the group contains "anthropic/claude-haiku"

  Scenario: Remove models from a group
    Given a group "fast-models" with model "anthropic/claude-haiku"
    When I remove_model("fast-models", "anthropic/claude-haiku")
    Then the group no longer contains "anthropic/claude-haiku"

  Scenario: List all groups
    Given groups "fast-models" and "premium-models"
    When I list_groups()
    Then I receive 2 groups

  Scenario: Show group details with member models
    Given a group "fast-models" with 3 models
    When I get_group("fast-models")
    Then I receive the group with its 3 member model IDs

  Scenario: Delete a group
    Given a group "fast-models"
    When I delete_group("fast-models")
    Then the group no longer exists

  Scenario: CLI --model-group flag selects a saved group
    Given a group "fast-models" with models ["a", "b"]
    When I pass --model-group fast-models
    Then resolved config has models=["a", "b"]

  Scenario: Combine --model-group and --models (union)
    Given a group "fast-models" with models ["a", "b"]
    When I pass --model-group fast-models --models "c"
    Then resolved config has models=["a", "b", "c"]

  Scenario: Validate group models against catalog on run start
    Given a group with model "nonexistent-model"
    When validation runs
    Then a warning is logged
    And the missing model is skipped

  Scenario: Reject duplicate group names
    Given a group "fast-models" already exists
    When I create_group("fast-models")
    Then a ValueError is raised with message containing "already exists"

  Scenario: CLI subcommands for group management
    When I run "agent-evals models group create fast-models"
    Then the group is created
    When I run "agent-evals models group list"
    Then all groups are displayed
    When I run "agent-evals models group show fast-models"
    Then group details are displayed
    When I run "agent-evals models group delete fast-models"
    Then the group is deleted

  Scenario: Create group from web UI
    When I POST /api/models/groups with {"name": "fast-models", "models": ["a"]}
    Then the group is created and 201 is returned
```

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/model_groups.py`
- Test: `agent-evals/tests/test_model_groups.py`

**TDD Cycle:**

**RED 1 -- Group CRUD tests**
```python
# agent-evals/tests/test_model_groups.py
"""Tests for model groups with persistence and CLI integration."""

import pytest

from agent_evals.observatory.model_groups import ModelGroupStore


class TestGroupCRUD:
    """Create, read, update, delete model groups."""

    def test_create_group(self, tmp_path):
        store = ModelGroupStore(tmp_path / "models.db")
        store.create_group("fast-models", description="Low-latency models")
        groups = store.list_groups()
        assert len(groups) == 1
        assert groups[0]["name"] == "fast-models"

    def test_add_model_to_group(self, tmp_path):
        store = ModelGroupStore(tmp_path / "models.db")
        store.create_group("fast-models")
        store.add_model("fast-models", "anthropic/claude-haiku")
        group = store.get_group("fast-models")
        assert "anthropic/claude-haiku" in group["models"]

    def test_remove_model_from_group(self, tmp_path):
        store = ModelGroupStore(tmp_path / "models.db")
        store.create_group("fast-models")
        store.add_model("fast-models", "anthropic/claude-haiku")
        store.remove_model("fast-models", "anthropic/claude-haiku")
        group = store.get_group("fast-models")
        assert "anthropic/claude-haiku" not in group["models"]

    def test_list_groups(self, tmp_path):
        store = ModelGroupStore(tmp_path / "models.db")
        store.create_group("fast-models")
        store.create_group("premium-models")
        groups = store.list_groups()
        assert len(groups) == 2

    def test_show_group_details(self, tmp_path):
        store = ModelGroupStore(tmp_path / "models.db")
        store.create_group("fast-models")
        for m in ["a", "b", "c"]:
            store.add_model("fast-models", m)
        group = store.get_group("fast-models")
        assert len(group["models"]) == 3

    def test_delete_group(self, tmp_path):
        store = ModelGroupStore(tmp_path / "models.db")
        store.create_group("fast-models")
        store.delete_group("fast-models")
        groups = store.list_groups()
        assert len(groups) == 0

    def test_reject_duplicate_names(self, tmp_path):
        store = ModelGroupStore(tmp_path / "models.db")
        store.create_group("fast-models")
        with pytest.raises(ValueError, match="already exists"):
            store.create_group("fast-models")
```

Run: `~/.local/bin/uv run pytest agent-evals/tests/test_model_groups.py::TestGroupCRUD -v`
Expected: FAIL -- `ModuleNotFoundError: No module named 'agent_evals.observatory.model_groups'`

**GREEN 1 -- Implement ModelGroupStore with SQLite schema**

Schema: `model_groups` (id INTEGER PK, name TEXT UNIQUE, description TEXT, created_at TEXT, updated_at TEXT), `model_group_members` (group_id FK, model_id FK).

Run: PASS.

**RED 2 -- CLI integration tests**
```python
class TestGroupCLIIntegration:
    """Model group integration with CLI config resolution."""

    def test_model_group_resolves_to_models(self, tmp_path):
        store = ModelGroupStore(tmp_path / "models.db")
        store.create_group("fast-models")
        store.add_model("fast-models", "a")
        store.add_model("fast-models", "b")
        group = store.get_group("fast-models")
        assert group["models"] == ["a", "b"]

    def test_combine_group_and_explicit_models(self, tmp_path):
        store = ModelGroupStore(tmp_path / "models.db")
        store.create_group("fast-models")
        store.add_model("fast-models", "a")
        store.add_model("fast-models", "b")
        group_models = store.get_group("fast-models")["models"]
        explicit = ["c"]
        combined = list(dict.fromkeys(group_models + explicit))
        assert combined == ["a", "b", "c"]

    def test_validate_warns_on_missing_models(self, tmp_path):
        store = ModelGroupStore(tmp_path / "models.db")
        store.create_group("test")
        store.add_model("test", "nonexistent")
        group = store.get_group("test")
        # Validation logic checks against catalog
        assert "nonexistent" in group["models"]


class TestGroupValidation:
    """Validate group models against the model catalog."""

    def test_missing_models_logged_and_skipped(self, tmp_path):
        store = ModelGroupStore(tmp_path / "models.db")
        store.create_group("test")
        store.add_model("test", "exists")
        store.add_model("test", "missing")
        catalog_ids = {"exists"}
        group = store.get_group("test")
        valid = [m for m in group["models"] if m in catalog_ids]
        assert valid == ["exists"]
```

Run: FAIL. Implement. Run: PASS.

**REFACTOR -- Clean up, verify with ruff**

Run full suite: `~/.local/bin/uv run pytest agent-evals/tests/test_model_groups.py -v`
Run project-wide: `~/.local/bin/uv run pytest` (verify no regressions)

**Commit:**
```bash
git add agent-evals/src/agent_evals/observatory/model_groups.py agent-evals/tests/test_model_groups.py
git commit -m "feat(models): add model groups with CLI and persistence

SQLite-backed model groups with CRUD operations, CLI --model-group flag
for reusing saved selections, union with --models, and validation against
the model catalog with graceful skip on missing models.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E6-S4: Model Browser CLI

**User Story:** As a developer, I want to browse and search models from the terminal so that I can quickly find and compare models without opening a web browser.

**Acceptance Criteria:**

```gherkin
Feature: Model Browser CLI

  Scenario: List all models in Rich table format
    Given a catalog with 10 active models
    When I run "agent-evals models list"
    Then a Rich table displays with columns: name, price in/out, context, date

  Scenario: Sort by any column ascending
    When I run "agent-evals models list --sort price"
    Then models are sorted by prompt_price ascending

  Scenario: Sort descending with - prefix
    When I run "agent-evals models list --sort -created"
    Then models are sorted by created date descending

  Scenario: Sort by context length
    When I run "agent-evals models list --sort context"
    Then models are sorted by context_length ascending

  Scenario: Sort by name
    When I run "agent-evals models list --sort name"
    Then models are sorted alphabetically by name

  Scenario: Filter --free shows only zero-cost models
    When I run "agent-evals models list --free"
    Then only models with prompt_price=0 and completion_price=0 are shown

  Scenario: Filter --max-price N
    When I run "agent-evals models list --max-price 0.005"
    Then only models with prompt_price <= 0.005 are shown

  Scenario: Filter --min-context N
    When I run "agent-evals models list --min-context 100000"
    Then only models with context_length >= 100000 are shown

  Scenario: Filter --modality
    When I run "agent-evals models list --modality text+image"
    Then only multimodal models are shown

  Scenario: Filter --capability with AND logic
    When I run "agent-evals models list --capability tools,json_mode"
    Then only models supporting both tools AND json_mode are shown

  Scenario: Filter --provider
    When I run "agent-evals models list --provider anthropic"
    Then only Anthropic-authored models are shown

  Scenario: Filter --tokenizer
    When I run "agent-evals models list --tokenizer claude"
    Then only Claude-tokenizer models are shown

  Scenario: Filter --new shows recently added models
    When I run "agent-evals models list --new"
    Then only models added since last sync are shown

  Scenario: Filter --search does fuzzy match
    When I run "agent-evals models list --search sonnet"
    Then models with "sonnet" in name, ID, or description are shown

  Scenario: Show model detail with live provider endpoints
    When I run "agent-evals models show anthropic/claude-sonnet-4.5"
    Then full metadata for that model is displayed
    And provider endpoints are fetched from OpenRouter /models/{author}/{slug}/endpoints
    And each provider row shows name, pricing, uptime, latency, quantization, and ZDR support

  Scenario: Show model detail when provider endpoint fetch fails
    Given OpenRouter /models/{author}/{slug}/endpoints returns a non-200 response
    When I run "agent-evals models show anthropic/claude-sonnet-4.5"
    Then full metadata for that model is displayed
    And a warning indicates provider endpoint data is unavailable
    And no provider endpoint table is shown

  Scenario: Output --format json
    When I run "agent-evals models list --format json"
    Then valid JSON array is produced

  Scenario: Output --format csv
    When I run "agent-evals models list --format csv"
    Then valid CSV is produced
```

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/model_cli.py`
- Test: `agent-evals/tests/test_model_cli.py`

**TDD Cycle:**

**RED 1 -- Filter and sort logic tests**
```python
# agent-evals/tests/test_model_cli.py
"""Tests for CLI model browser with filtering and sorting."""

import json

import pytest

from agent_evals.observatory.model_cli import (
    format_models_csv,
    format_models_json,
    format_models_table,
    fuzzy_search,
    sort_models,
)


SAMPLE_MODELS = [
    {"id": "a/cheap", "name": "Cheap", "prompt_price": 0.0,
     "completion_price": 0.0, "context_length": 4096, "created": 1700000000,
     "modality": "text", "tokenizer": "gpt"},
    {"id": "b/mid", "name": "Mid", "prompt_price": 0.003,
     "completion_price": 0.015, "context_length": 100000, "created": 1710000000,
     "modality": "text+image", "tokenizer": "claude"},
    {"id": "c/premium", "name": "Premium", "prompt_price": 0.010,
     "completion_price": 0.030, "context_length": 200000, "created": 1720000000,
     "modality": "text+image", "tokenizer": "claude"},
]


class TestSortModels:
    """Sort model lists by various columns."""

    def test_sort_by_price_ascending(self):
        result = sort_models(SAMPLE_MODELS, "price")
        prices = [m["prompt_price"] for m in result]
        assert prices == sorted(prices)

    def test_sort_by_created_descending(self):
        result = sort_models(SAMPLE_MODELS, "-created")
        dates = [m["created"] for m in result]
        assert dates == sorted(dates, reverse=True)

    def test_sort_by_context(self):
        result = sort_models(SAMPLE_MODELS, "context")
        contexts = [m["context_length"] for m in result]
        assert contexts == sorted(contexts)

    def test_sort_by_name(self):
        result = sort_models(SAMPLE_MODELS, "name")
        names = [m["name"] for m in result]
        assert names == sorted(names)


class TestFuzzySearch:
    """Fuzzy text search across model fields."""

    def test_search_by_name(self):
        results = fuzzy_search(SAMPLE_MODELS, "premium")
        assert len(results) == 1
        assert results[0]["id"] == "c/premium"

    def test_search_by_id(self):
        results = fuzzy_search(SAMPLE_MODELS, "b/mid")
        assert len(results) == 1

    def test_search_case_insensitive(self):
        results = fuzzy_search(SAMPLE_MODELS, "CHEAP")
        assert len(results) == 1

    def test_search_no_match(self):
        results = fuzzy_search(SAMPLE_MODELS, "nonexistent")
        assert len(results) == 0
```

Run: `~/.local/bin/uv run pytest agent-evals/tests/test_model_cli.py::TestSortModels -v`
Expected: FAIL

**GREEN 1 -- Implement sort_models() and fuzzy_search()**

**RED 2 -- Output format tests**
```python
class TestOutputFormats:
    """Output models in different formats."""

    def test_json_output_valid(self):
        output = format_models_json(SAMPLE_MODELS)
        parsed = json.loads(output)
        assert len(parsed) == 3
        assert parsed[0]["id"] == "a/cheap"

    def test_csv_output_valid(self):
        output = format_models_csv(SAMPLE_MODELS)
        lines = output.strip().split("\n")
        assert len(lines) == 4  # header + 3 rows
        assert "id" in lines[0]

    def test_table_output_nonempty(self):
        output = format_models_table(SAMPLE_MODELS)
        assert len(output) > 0
        assert "Cheap" in output


class TestModelDetail:
    """Show detailed model information."""

    def test_show_model_returns_formatted_detail(self):
        from agent_evals.observatory.model_cli import format_model_detail
        detail = format_model_detail(SAMPLE_MODELS[1])
        assert "Mid" in detail
        assert "100000" in detail


class TestFilterCombination:
    """Combine multiple CLI filters."""

    def test_all_filters_combine(self):
        from agent_evals.observatory.model_cli import apply_cli_filters
        results = apply_cli_filters(
            SAMPLE_MODELS,
            free=False, max_price=0.010, min_context=100000,
            modality="text+image", tokenizer="claude",
        )
        assert len(results) == 2  # mid and premium

    def test_free_filter_only(self):
        from agent_evals.observatory.model_cli import apply_cli_filters
        results = apply_cli_filters(SAMPLE_MODELS, free=True)
        assert len(results) == 1
        assert results[0]["id"] == "a/cheap"
```

Run: FAIL. Implement. Run: PASS.

**RED 3 -- Provider endpoint fetch tests**
```python
class TestProviderEndpoints:
    """Fetch and display live provider endpoint data in detail view."""

    def test_detail_includes_provider_endpoint_data(self, mocker):
        from agent_evals.observatory.model_cli import format_model_detail
        mock_endpoints = {
            "endpoints": [
                {
                    "provider": "Anthropic",
                    "prompt_price": 0.003,
                    "completion_price": 0.015,
                    "uptime": 99.8,
                    "latency_ms": 420,
                    "quantization": "none",
                    "zdr": True,
                },
            ],
        }
        mocker.patch(
            "agent_evals.observatory.model_cli.fetch_provider_endpoints",
            return_value=mock_endpoints,
        )
        detail = format_model_detail(SAMPLE_MODELS[1], fetch_endpoints=True)
        assert "Anthropic" in detail
        assert "99.8" in detail
        assert "420" in detail
        assert "ZDR" in detail or "zdr" in detail.lower()

    def test_detail_warns_on_endpoint_fetch_failure(self, mocker):
        from agent_evals.observatory.model_cli import format_model_detail
        mocker.patch(
            "agent_evals.observatory.model_cli.fetch_provider_endpoints",
            return_value=None,
        )
        detail = format_model_detail(SAMPLE_MODELS[1], fetch_endpoints=True)
        assert "Mid" in detail
        assert "provider" in detail.lower() and "unavailable" in detail.lower()

    def test_detail_without_fetch_endpoints_flag_skips_call(self, mocker):
        from agent_evals.observatory.model_cli import format_model_detail
        mock_fetch = mocker.patch(
            "agent_evals.observatory.model_cli.fetch_provider_endpoints",
        )
        detail = format_model_detail(SAMPLE_MODELS[1], fetch_endpoints=False)
        mock_fetch.assert_not_called()
        assert "Mid" in detail
```

Run: `~/.local/bin/uv run pytest agent-evals/tests/test_model_cli.py::TestProviderEndpoints -v`
Expected: FAIL

**GREEN 3 -- Implement fetch_provider_endpoints() and update format_model_detail()**

**REFACTOR -- Clean up, verify with ruff**

Run full suite: `~/.local/bin/uv run pytest agent-evals/tests/test_model_cli.py -v`
Run project-wide: `~/.local/bin/uv run pytest` (verify no regressions)

**Commit:**
```bash
git add agent-evals/src/agent_evals/observatory/model_cli.py agent-evals/tests/test_model_cli.py
git commit -m "feat(models): add CLI model browser with filtering, sorting, and provider endpoints

Rich table output with sortable columns, multi-criteria filtering
(price, context, modality, capability, provider, tokenizer, fuzzy search),
model detail view with live provider endpoint data from OpenRouter
(latency, uptime, quantization, ZDR support), and JSON/CSV export formats.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Sprint 5: Web Dashboard & Advanced Features

**Goal:** Build the web-based observatory UI and advanced features.

---

### E3-S4: Observatory Web Dashboard

**User Story:** As a user, I want a web dashboard at localhost:8080 that shows live run progress, results, cost telemetry, and historical analytics.

**Acceptance Criteria:**

```gherkin
Feature: Web Dashboard

  Scenario: Dashboard serves on localhost:8080
    Given the web server is started
    When I GET http://localhost:8080/
    Then I receive a 200 response with HTML content

  Scenario: API lists runs
    When I GET /api/runs
    Then I receive JSON with a list of run summaries

  Scenario: API streams live events via SSE
    Given an active run
    When I connect to /api/runs/{id}/stream
    Then I receive Server-Sent Events as trials complete

  Scenario: Run configuration page
    When I GET /
    Then the page includes a "Start Run" form with mode, models, reps fields

  Scenario: Results explorer shows report data
    Given a completed run
    When I GET /api/runs/{id}/report
    Then I receive the full ReportData as JSON

  Scenario: Historical cost trends
    Given 5 completed runs
    When I GET /api/history/cost-trend
    Then I receive cost data points per run

  Scenario: Model drift detection
    Given 5 runs with "claude" data
    When I GET /api/history/model-drift?model=claude
    Then I receive per-run scores showing the trend

  Scenario: Run comparison
    Given runs "run_001" and "run_002"
    When I GET /api/compare?ids=run_001,run_002
    Then I receive side-by-side comparison data
```

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/web/__init__.py`
- Create: `agent-evals/src/agent_evals/observatory/web/server.py`
- Create: `agent-evals/src/agent_evals/observatory/web/routes.py`
- Create: `agent-evals/src/agent_evals/observatory/web/templates/dashboard.html`
- Test: `agent-evals/tests/test_observatory_web.py`

**New dependencies:** `fastapi>=0.100`, `uvicorn[standard]>=0.20`, `sse-starlette>=1.6`

**TDD Cycle:** Use FastAPI's `TestClient` for API endpoint tests. The dashboard HTML is tested by checking for key elements (forms, chart containers, section IDs).

```bash
git commit -m "feat(observatory): add web dashboard with FastAPI and SSE

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E3-S5: Observatory Historical Analytics

**User Story:** As a user, I want to compare runs, detect model performance drift, and track cost trends over time.

**Acceptance Criteria:**

```gherkin
Feature: Historical Analytics

  Scenario: Compare two runs side by side
    Given runs "run_001" (score 0.72) and "run_002" (score 0.78)
    When I compare_runs(["run_001", "run_002"])
    Then I get per-variant and per-model deltas

  Scenario: Detect model drift
    Given 5 runs where "claude" scores [0.75, 0.74, 0.73, 0.65, 0.64]
    When I detect_model_drift("claude")
    Then drift_detected=True with direction="declining"

  Scenario: No drift when scores are stable
    Given 5 runs where "claude" scores [0.75, 0.74, 0.76, 0.75, 0.74]
    When I detect_model_drift("claude")
    Then drift_detected=False

  Scenario: Cost trend over time
    Given runs with costs [$5, $8, $12, $10, $15]
    When I compute cost_trends()
    Then I get a time series of costs with running average

  Scenario: Regression detection
    Given a run where "gpt" scored 0.60 vs running average 0.72
    When I detect_regressions(threshold=0.05)
    Then alert flagged for "gpt" with delta=-0.12
```

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/history.py`
- Test: `agent-evals/tests/test_observatory_history.py`

```bash
git commit -m "feat(observatory): add historical analytics and drift detection

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E3-S6: OpenRouter Cost Reconciliation

**User Story:** As a user, I want actual API billing reconciled against reported costs so that my cost data is accurate.

**Acceptance Criteria:**

```gherkin
Feature: OpenRouter Reconciliation

  Scenario: Fetch generation stats for a known ID
    Given a valid generation_id from a previous call
    When I call get_generation_stats(generation_id)
    Then I receive actual_tokens and actual_cost

  Scenario: Reconcile a full run
    Given a run with 10 trials having generation_ids
    When I reconcile_run(run_id)
    Then I get a report with per-trial reported_cost vs actual_cost

  Scenario: Flag cost discrepancies
    Given reported_cost=$0.05 but actual_cost=$0.08
    When reconciliation completes
    Then the discrepancy is flagged with delta=$0.03

  Scenario: Handle missing generation_ids gracefully
    Given a trial with generation_id=None (cached result)
    When reconciliation runs
    Then that trial is skipped with a note
```

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/openrouter.py`
- Test: `agent-evals/tests/test_openrouter_reconciliation.py`

**TDD Cycle:** Mock the httpx client in tests. Use `respx` or manual mocking.

```bash
git commit -m "feat(observatory): add OpenRouter cost reconciliation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E3-S7: Observatory CLI Subcommand

**User Story:** As a user, I want an `agent-evals observatory` CLI subcommand so that I can list runs, compare results, track model drift, and reconcile costs from the terminal.

**Acceptance Criteria:**

```gherkin
Feature: Observatory CLI Subcommand

  Scenario: List all runs
    When I run "agent-evals observatory --list"
    Then I see a table of all completed runs with timestamps and stats

  Scenario: Compare runs
    When I run "agent-evals observatory --compare run_001,run_002"
    Then I see side-by-side comparison output

  Scenario: Model drift
    When I run "agent-evals observatory --model-drift claude-sonnet"
    Then I see performance trend for that model across runs

  Scenario: Cost trend
    When I run "agent-evals observatory --cost-trend"
    Then I see cost over time for all runs

  Scenario: Reconcile costs
    When I run "agent-evals observatory --reconcile-costs run_001"
    Then reported costs are compared against OpenRouter actuals
```

**Files:**
- Modify: `agent-evals/src/agent_evals/cli.py` (add observatory subcommand)
- Create: `agent-evals/src/agent_evals/observatory/cli.py`
- Test: `agent-evals/tests/test_observatory_cli.py`

```bash
git commit -m "feat(observatory): add CLI subcommand for run management and analytics

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E4-S5: Chart Library

**User Story:** As a developer, I want a shared chart library that generates both Plotly (for HTML) and matplotlib (for images) versions of each chart type.

**Acceptance Criteria:**

```gherkin
Feature: Chart Library

  Scenario: Main effects bar chart (Plotly)
    Given main effects data for 3 factors
    When I generate_main_effects_plotly(data)
    Then I get valid Plotly JSON for 3 bar charts

  Scenario: Main effects bar chart (matplotlib)
    Given main effects data
    When I generate_main_effects_image(data, path)
    Then a PNG file is saved at path

  Scenario: Interaction plot
    Given interaction data for axis_1 x axis_3
    When I generate_interaction_plot(data)
    Then the chart shows lines crossing (or not)

  Scenario: Model comparison radar
    Given per-model per-type scores for 3 models
    When I generate_radar_chart(data)
    Then the chart has 3 traces on a polar axis

  Scenario: Score distribution box plots
    Given per-variant score lists
    When I generate_box_plots(data)
    Then each variant has a box with median, quartiles, whiskers

  Scenario: Cost burn chart
    Given cumulative cost over time
    When I generate_burn_chart(data)
    Then the chart shows a line plot with budget cap horizontal line

  Scenario: S/N response table
    Given S/N ratios per factor level
    When I generate_sn_response_table(data)
    Then I get a tabular display of S/N values per factor per level

  Scenario: Confirmation run predicted vs actual chart
    Given predicted S/N = 5.2 and observed S/N = 5.0
    When I generate_confirmation_chart(data)
    Then the chart shows predicted and observed with confidence band
```

**Files:**
- Create: `agent-evals/src/agent_evals/report/charts.py` (extend from Task 15)
- Test: `agent-evals/tests/test_report_charts.py`

```bash
git commit -m "feat(report): add shared chart library for Plotly and matplotlib

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E6-S5: Model Browser Web UI

**User Story:** As a user, I want a model browser page in the web dashboard so that I can visually explore, filter, compare, and select models for test runs.

**Acceptance Criteria:**

```gherkin
Feature: Model Browser Web UI

  Scenario: Models page appears in navigation bar
    When I GET /
    Then the navigation bar includes a "Models" link (page 6)

  Scenario: API returns all active models
    When I GET /api/models
    Then I receive JSON with all active models from catalog

  Scenario: API returns single model detail
    When I GET /api/models/anthropic/claude-sonnet-4.5
    Then I receive JSON with full model metadata

  Scenario: API proxies endpoint data from OpenRouter
    When I GET /api/models/anthropic/claude-sonnet-4.5/endpoints
    Then I receive live latency and uptime data from OpenRouter

  Scenario: API returns all saved groups
    When I GET /api/models/groups
    Then I receive JSON with all model groups

  Scenario: API creates a new group
    When I POST /api/models/groups with {"name": "test", "models": ["a"]}
    Then the group is created and 201 is returned

  Scenario: API triggers manual sync
    When I POST /api/models/sync
    Then a sync executes and the result is returned

  Scenario: Filter panel price range works
    Given models with various prices
    When I apply the price range filter via query params
    Then only models within the price range are returned

  Scenario: Filter panel context length range works
    Given models with various context lengths
    When I apply the context length filter
    Then only models within the range are returned

  Scenario: Filter panel modality checkboxes work
    When I filter by modality="text+image"
    Then only multimodal models are shown

  Scenario: Filter panel capability checkboxes use AND logic
    When I filter by capabilities=["tools", "json_mode"]
    Then only models supporting both are shown

  Scenario: Filter panel provider multi-select works
    When I filter by provider=["anthropic", "openai"]
    Then only models from those providers are shown

  Scenario: Filter panel tokenizer multi-select works
    When I filter by tokenizer="claude"
    Then only Claude-tokenizer models are shown

  Scenario: Filter panel release date range works
    When I filter by date_from and date_to
    Then only models created within that range are shown

  Scenario: All filters combine simultaneously with live count
    When I apply price, context, and modality filters
    Then results match all criteria (AND logic)
    And the result count updates

  Scenario: Text search bar fuzzy matches
    When I type "sonnet" in the search bar
    Then models matching "sonnet" in name/ID/description are shown

  Scenario: Table view has sortable columns
    When I click a column header
    Then models sort by that column ascending
    When I click again
    Then models sort descending

  Scenario: Card grid view displays model cards
    When I switch to card view
    Then models display as cards with key stats

  Scenario: View toggle preserves selection and filters
    Given I have selected 3 models and applied a price filter
    When I toggle from table to card view
    Then the selection and filter are preserved

  Scenario: Select All respects current filters
    Given 5 models visible after filtering
    When I click "Select All"
    Then only the 5 visible models are selected

  Scenario: Run Selected navigates to Run Config
    Given 3 models selected
    When I click "Run Selected"
    Then I navigate to Run Config with those models pre-filled

  Scenario: Save as Group dialog creates group via API
    Given 3 models selected
    When I click "Save as Group" and enter name "my-group"
    Then POST /api/models/groups is called with the 3 models

  Scenario: New model badge on recently added models
    Given a model added in the last sync
    When the model list renders
    Then the model has a "NEW" badge

  Scenario: Filter state persisted in URL query params
    Given I apply price and modality filters
    When I copy the URL and navigate to it
    Then the same filters are applied (bookmarkable)

  Scenario: Model detail slide-out panel
    When I click a model row
    Then a slide-out panel opens with Overview, Providers, and History tabs

  Scenario: Providers tab auto-refreshes
    Given the detail panel is open on the Providers tab
    When 60 seconds elapse
    Then the endpoint data refreshes automatically
```

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/web/routes.py` (add model API routes)
- Modify: `agent-evals/src/agent_evals/observatory/web/templates/dashboard.html` (add page 6)
- Test: `agent-evals/tests/test_model_browser_web.py`

**TDD Cycle:**

**RED 1 -- API endpoint tests**
```python
# agent-evals/tests/test_model_browser_web.py
"""Tests for web model browser API endpoints and HTML elements."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestModelAPIEndpoints:
    """REST API endpoints for model browsing."""

    def test_get_models_returns_list(self, client):
        response = client.get("/api/models")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_model_by_id(self, client):
        response = client.get("/api/models/test-model")
        assert response.status_code == 200
        assert response.json()["id"] == "test-model"

    def test_get_model_not_found(self, client):
        response = client.get("/api/models/nonexistent")
        assert response.status_code == 404

    def test_get_model_endpoints(self, client):
        response = client.get("/api/models/test-model/endpoints")
        assert response.status_code == 200

    def test_get_groups(self, client):
        response = client.get("/api/models/groups")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_group(self, client):
        response = client.post("/api/models/groups", json={
            "name": "test-group", "models": ["a", "b"],
        })
        assert response.status_code == 201

    def test_trigger_sync(self, client):
        response = client.post("/api/models/sync")
        assert response.status_code == 200
```

Run: `~/.local/bin/uv run pytest agent-evals/tests/test_model_browser_web.py::TestModelAPIEndpoints -v`
Expected: FAIL

**GREEN 1 -- Add model routes to FastAPI app**

**RED 2 -- Filter API tests**
```python
class TestModelFilterAPI:
    """Filter models via query parameters."""

    def test_filter_by_price_range(self, client):
        response = client.get("/api/models?max_price=0.005")
        assert response.status_code == 200
        for m in response.json():
            assert m["prompt_price"] <= 0.005

    def test_filter_by_context_length(self, client):
        response = client.get("/api/models?min_context=100000")
        assert response.status_code == 200
        for m in response.json():
            assert m["context_length"] >= 100000

    def test_filter_by_modality(self, client):
        response = client.get("/api/models?modality=text%2Bimage")
        assert response.status_code == 200

    def test_filter_by_capabilities(self, client):
        response = client.get("/api/models?capabilities=tools,json_mode")
        assert response.status_code == 200

    def test_filter_by_provider(self, client):
        response = client.get("/api/models?provider=anthropic")
        assert response.status_code == 200

    def test_combined_filters(self, client):
        response = client.get("/api/models?max_price=0.005&min_context=32768")
        assert response.status_code == 200

    def test_search_query(self, client):
        response = client.get("/api/models?search=sonnet")
        assert response.status_code == 200
```

Run: FAIL. Implement. Run: PASS.

**RED 3 -- HTML element presence tests**
```python
class TestModelBrowserHTML:
    """Dashboard HTML includes model browser elements."""

    def test_navigation_includes_models_link(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "Models" in response.text

    def test_models_page_has_filter_panel(self, client):
        response = client.get("/")
        assert "model-filter" in response.text or "filter-panel" in response.text

    def test_models_page_has_search_bar(self, client):
        response = client.get("/")
        assert "model-search" in response.text or "search" in response.text

    def test_models_page_has_table_view(self, client):
        response = client.get("/")
        assert "model-table" in response.text or "table-view" in response.text

    def test_models_page_has_card_view(self, client):
        response = client.get("/")
        assert "card-view" in response.text or "grid-view" in response.text

    def test_models_page_has_select_all(self, client):
        response = client.get("/")
        assert "select-all" in response.text or "Select All" in response.text

    def test_models_page_has_run_selected_button(self, client):
        response = client.get("/")
        assert "Run Selected" in response.text

    def test_models_page_has_save_group_button(self, client):
        response = client.get("/")
        assert "Save as Group" in response.text

    def test_models_page_has_view_toggle(self, client):
        response = client.get("/")
        assert "view-toggle" in response.text or "toggle" in response.text

    def test_models_page_has_detail_panel(self, client):
        response = client.get("/")
        assert "detail-panel" in response.text or "slide-out" in response.text
```

Run: FAIL. Implement. Run: PASS.

**REFACTOR -- Clean up, verify with ruff**

Run full suite: `~/.local/bin/uv run pytest agent-evals/tests/test_model_browser_web.py -v`
Run project-wide: `~/.local/bin/uv run pytest` (verify no regressions)

**Commit:**
```bash
git add agent-evals/src/agent_evals/observatory/web/routes.py agent-evals/src/agent_evals/observatory/web/templates/dashboard.html agent-evals/tests/test_model_browser_web.py
git commit -m "feat(models): add web model browser with filtering, groups, and detail panel

Page 6 'Models' in web dashboard with REST API for browsing, filtering,
and group management. Filter panel supports price, context, modality,
capabilities, provider, tokenizer, and date range. Table/card views with
sortable columns, fuzzy search, model selection, and detail slide-out.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Sprint 6: Ship It

**Goal:** Wire everything together, run integration tests, validate end-to-end.

---

### E5-S1: Orchestrator

**User Story:** As a developer, I want a top-level orchestrator that coordinates mode selection, observatory initialization, runner execution, and report generation.

**Acceptance Criteria:**

```gherkin
Feature: Orchestrator

  Scenario: Full mode routes to EvalRunner
    Given mode="full" in resolved config
    When the orchestrator runs
    Then EvalRunner is used (not TaguchiRunner)

  Scenario: Taguchi mode routes to TaguchiRunner
    Given mode="taguchi" in resolved config
    When the orchestrator runs
    Then TaguchiRunner is used with OA design

  Scenario: Observatory initialized for all modes
    Given any mode
    When the orchestrator runs
    Then an ObservatoryStore and Tracker are created

  Scenario: Dashboard started when --dashboard flag set
    Given dashboard=True
    When the orchestrator starts
    Then web server starts on port 8080 in background thread

  Scenario: Report generated after run completes
    Given report="both"
    When the run finishes
    Then HTML and Markdown reports are saved

  Scenario: Observatory run finalized
    Given a completed run
    When the orchestrator finishes
    Then the observatory run status is "completed"

  Scenario: Confirmation runs execute after Taguchi analysis
    Given mode="taguchi" and confirmation_runs=3
    When the main run finishes
    Then 3 additional trials run at the predicted optimal configuration

  Scenario: Full mode with multiple models runs each sequentially
    Given mode="full" and models=["a", "b"]
    When the orchestrator runs
    Then EvalRunner executes with model "a" first
    And then EvalRunner executes with model "b"
```

**Files:**
- Create: `agent-evals/src/agent_evals/orchestrator.py`
- Modify: `agent-evals/src/agent_evals/cli.py` (route to orchestrator)
- Test: `agent-evals/tests/test_orchestrator.py`

```bash
git commit -m "feat: add EvalOrchestrator coordinating all subsystems

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E5-S2: Integration Tests

**User Story:** As a developer, I want end-to-end integration tests validating the complete pipeline from CLI to report output.

**Acceptance Criteria:**

```gherkin
Feature: End-to-End Integration

  Scenario: Taguchi dry run
    Given --mode taguchi --models mock_a,mock_b --dry-run
    When I run the CLI
    Then it exits 0 and logs the OA selection and trial count estimate

  Scenario: Taguchi run with mock LLM
    Given a mock LLM returning canned responses
    And --mode taguchi --repetitions 2 --limit 3
    When I run the full pipeline
    Then trials are generated from OA rows
    And observatory.db contains trial records
    And reports/ contains JSON + CSV

  Scenario: Report generation from fixture data
    Given a pre-built ReportData fixture
    When I render HTML and Markdown
    Then both files are created without errors
    And HTML contains all 9 sections (Executive Summary, Experimental Design, ANOVA Results, Main Effects Analysis, Interaction Effects, Model Comparison, Optimal Configuration, Robustness Analysis, Appendix)
    And Markdown references chart images

  Scenario: Observatory web API responds
    Given a completed run in the store
    When I query /api/runs
    Then the run appears in the list

  Scenario: Multi-model run produces per-model stats
    Given --models mock_a,mock_b with Taguchi mode
    When the run completes
    Then the report includes model comparison data
    And observatory has per-model breakdowns

  Scenario: Full backward compatibility
    Given --model mock_a (singular, no --mode flag)
    When I run the CLI
    Then it executes in full mode with the existing EvalRunner
```

**Files:**
- Create: `agent-evals/tests/test_integration_taguchi.py`
- Create: `agent-evals/tests/test_integration_observatory.py`
- Create: `agent-evals/tests/test_integration_report.py`

```bash
git commit -m "test: add end-to-end integration tests for Taguchi, observatory, and reports

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### E2-S3: Multi-Model YAML Config

**User Story:** As a user, I want to configure multi-model runs via YAML config so that I don't need long CLI commands.

**Acceptance Criteria:**

```gherkin
Feature: Multi-Model YAML Config

  Scenario: Models as YAML list
    Given config with models: ["claude", "gpt", "gemini"]
    When resolved
    Then models=["claude", "gpt", "gemini"]

  Scenario: Per-model overrides
    Given config with model_overrides: {gpt: {temperature: 0.5}}
    When the gpt client is created
    Then its temperature is 0.5 (not the global default)

  Scenario: Full example config
    Given the config:
      mode: taguchi
      models:
        - openrouter/anthropic/claude-sonnet-4.5
        - openrouter/openai/gpt-4o
      repetitions: 10
      confirmation_runs: 3
      report: both
      budget: 50.00
      dashboard: true
    When parsed and resolved
    Then all fields map correctly
```

**Files:**
- Modify: `agent-evals/src/agent_evals/cli.py`
- Create: `agent-evals/examples/taguchi-config.yaml`
- Modify: `agent-evals/tests/test_evals_cli.py`

```bash
git commit -m "feat(cli): add multi-model YAML config with per-model overrides

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Dependency Graph (New Files)

```toml
# New dependencies for agent-evals/pyproject.toml
[project]
dependencies = [
    # existing...
    "jinja2>=3.1",
    "plotly>=5.0",
    "matplotlib>=3.7",
    "fastapi>=0.100",
    "uvicorn[standard]>=0.20",
    "sse-starlette>=1.6",
    "httpx>=0.24",
]
```

## New File Tree

```
agent-evals/src/agent_evals/
├── taguchi/
│   ├── __init__.py          # E1-S1
│   ├── catalog.py           # E1-S1: OA catalog + auto-selector
│   ├── factors.py           # E1-S2: axis-to-factor mapper
│   ├── composite.py         # E1-S3: CompositeVariant
│   ├── runner.py            # E1-S4: TaguchiRunner
│   └── analysis.py          # E1-S5: S/N, ANOVA, optimal prediction
├── observatory/
│   ├── __init__.py          # E3-S1
│   ├── store.py             # E3-S1: SQLite persistence
│   ├── tracker.py           # E3-S2: thread-safe event tracker
│   ├── terminal.py          # E3-S3: Rich terminal dashboard
│   ├── model_catalog.py     # E6-S1: model metadata store with filtering
│   ├── model_sync.py        # E6-S2: background OpenRouter sync
│   ├── model_groups.py      # E6-S3: named model groups
│   ├── model_cli.py         # E6-S4: CLI model browser
│   ├── history.py           # E3-S5: cross-run analytics
│   ├── openrouter.py        # E3-S6: cost reconciliation
│   ├── cli.py               # E3-S7: observatory CLI subcommand
│   └── web/
│       ├── __init__.py      # E3-S4
│       ├── server.py        # E3-S4: FastAPI app
│       ├── routes.py        # E3-S4 + E6-S5: API + SSE + model browser endpoints
│       └── templates/
│           └── dashboard.html  # E3-S4 + E6-S5: includes model browser page
├── report/
│   ├── __init__.py          # E4-S1
│   ├── aggregator.py        # E4-S1: data collection
│   ├── statistics.py        # E4-S2: scientific rigor engine
│   ├── charts.py            # E4-S5: Plotly + matplotlib charts
│   ├── html_renderer.py     # E4-S3: HTML report
│   ├── markdown_renderer.py # E4-S4: Markdown report
│   └── templates/
│       └── report.html
├── llm/
│   └── client_pool.py       # E2-S1: multi-model client pool
└── orchestrator.py           # E5-S1: top-level coordinator

agent-evals/tests/
├── test_taguchi_catalog.py           # E1-S1 (~25 tests)
├── test_taguchi_factors.py           # E1-S2 (~15 tests)
├── test_composite_variant.py         # E1-S3 (~12 tests)
├── test_taguchi_runner.py            # E1-S4 (~20 tests)
├── test_taguchi_analysis.py          # E1-S5 (~25 tests)
├── test_client_pool.py               # E2-S1 (~8 tests)
├── test_observatory_store.py         # E3-S1 (~18 tests)
├── test_observatory_tracker.py       # E3-S2 (~12 tests)
├── test_observatory_terminal.py      # E3-S3 (~10 tests)
├── test_observatory_web.py           # E3-S4 (~20 tests)
├── test_observatory_history.py       # E3-S5 (~15 tests)
├── test_openrouter_reconciliation.py # E3-S6 (~10 tests)
├── test_observatory_cli.py          # E3-S7 (~10 tests)
├── test_model_catalog.py             # E6-S1 (~18 tests)
├── test_model_sync.py                # E6-S2 (~14 tests)
├── test_model_groups.py              # E6-S3 (~14 tests)
├── test_model_cli.py                 # E6-S4 (~16 tests)
├── test_model_browser_web.py         # E6-S5 (~24 tests)
├── test_report_aggregator.py         # E4-S1 (~15 tests)
├── test_report_statistics.py         # E4-S2 (~25 tests)
├── test_report_html.py               # E4-S3 (~12 tests)
├── test_report_markdown.py           # E4-S4 (~10 tests)
├── test_report_charts.py             # E4-S5 (~12 tests)
├── test_orchestrator.py              # E5-S1 (~15 tests)
├── test_integration_taguchi.py       # E5-S2 (~10 tests)
├── test_integration_observatory.py   # E5-S2 (~8 tests)
└── test_integration_report.py        # E5-S2 (~8 tests)

Estimated total: ~421 new tests
```

---

## Sprint Summary

| Sprint | Stories | New Tests | Key Deliverable |
|--------|---------|-----------|-----------------|
| 1 | E1-S1, E1-S2, E1-S3, E2-S1 | ~60 | OA catalog, factors, composite, client pool |
| 2 | E1-S4, E1-S5, E2-S2 | ~60 | Working Taguchi pipeline end-to-end |
| 3 | E3-S1, E3-S2, E3-S3, E6-S1, E6-S2 | ~72 | Observable eval runs with terminal UI, model catalog + sync |
| 4 | E4-S1, E4-S2, E4-S3, E4-S4, E6-S3, E6-S4 | ~92 | Publication-grade research reports, model groups + browser CLI |
| 5 | E3-S4, E3-S5, E3-S6, E3-S7, E4-S5, E6-S5 | ~91 | Web dashboard + advanced analytics + observatory CLI + model browser web UI |
| 6 | E5-S1, E5-S2, E2-S3 | ~46 | Full integration, backward compat |
| **Total** | **27 stories** | **~421** | |
