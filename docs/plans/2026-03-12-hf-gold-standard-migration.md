# HF Dataset Gold Standard Migration

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Promote HF dataset adapters to be the gold standard evaluation source, replacing hand-crafted YAML tasks that have insufficient discrimination (code_generation and fact_extraction always score 1.0).

**Architecture:** The `--source gold_standard` default changes from loading hand-crafted YAMLs to loading prepared HF datasets. Each of the 9 HF adapters maps to a task type. The old hand-crafted tasks move to a `legacy/` directory as supplementary. Dataset preparation becomes a first-class setup step. Synthetic adapters (perturbation, synthetic-efficiency) auto-generate from prepared HF data.

**Tech Stack:** Python 3.12, pytest, HuggingFace datasets, UV workspace

---

## Task 1: Audit dataset-to-task-type coverage

Before migrating, confirm every task type has an HF adapter that produces it.

**Files:**
- Read: `agent-evals/src/agent_evals/datasets/*.py` (all adapter files)
- Read: `agent-evals/src/agent_evals/tasks/base.py:23-35` (VALID_TASK_TYPES)

### Step 1: Map current coverage

Current mapping (from adapter `task_type()` methods):

| Task Type | HF Adapter | Status |
|---|---|---|
| disambiguation | ambigqa | Covered |
| compositional | bigcodebench | Covered |
| retrieval | code-rag-bench | Covered |
| code_generation | ds1000 | Covered |
| fact_extraction | ibm-techqa | Covered |
| multi_hop | multihop-rag | Covered |
| negative | repliqa | Covered |
| agentic | swe-bench | Covered |
| conflicting | wikicontradict | Covered |
| robustness | perturbation (synthetic) | Synthetic — needs source tasks |
| efficiency | synthetic-efficiency | Synthetic — needs source tasks |

**Gap analysis:** 9/11 types have direct HF adapters. 2 types (robustness, efficiency) are synthetic generators that transform tasks from other adapters. This is fine — they'll auto-generate from prepared HF data (Task 5).

### Step 2: Verify adapter quality

For each adapter, check that metadata fields produce meaningful scorer discrimination:

```bash
# Prepare each dataset with small limit
uv run agent-evals --prepare-datasets "ambigqa,bigcodebench,ds1000,multihop-rag,repliqa,swe-bench,wikicontradict" --dataset-limit 10

# ibm-techqa separate (requires TECHQA_DIR)
uv run agent-evals --prepare-datasets ibm-techqa --dataset-limit 10

# code-rag-bench separate
uv run agent-evals --prepare-datasets code-rag-bench --dataset-limit 10
```

### Step 3: Inspect prepared task YAMLs

```bash
# Check a sample from each adapter
for dir in ~/.agent-evals/datasets/*/tasks/; do
    echo "=== $(basename $(dirname $dir)) ==="
    head -30 "$dir"/*.yaml 2>/dev/null | head -50
done
```

Verify each adapter populates the metadata fields its scorer needs (expected_answer, test patterns, etc.).

### Step 4: Document findings

Create a coverage matrix noting any adapters that need metadata improvements before they can serve as gold standard.

### Step 5: Commit

```bash
git add docs/plans/2026-03-12-hf-gold-standard-migration.md
git commit -m "docs: HF gold standard migration plan

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Create dataset preparation infrastructure

Add a `prepare-gold-standard` command that downloads and prepares all HF datasets as a first-class setup step.

**Files:**
- Create: `agent-evals/src/agent_evals/datasets/gold_standard.py` (gold standard dataset manager)
- Test: `agent-evals/tests/test_dataset_gold_standard.py`

### Step 1: Write failing test for GoldStandardManager

Add to `agent-evals/tests/test_dataset_gold_standard.py`:

```python
from agent_evals.datasets.gold_standard import GoldStandardManager


class TestGoldStandardManager:
    def test_get_required_adapters_returns_nine(self):
        """All 9 HF adapters are required for gold standard."""
        mgr = GoldStandardManager()
        adapters = mgr.required_adapters()
        assert len(adapters) == 9
        assert "ds1000" in adapters
        assert "ibm-techqa" in adapters

    def test_is_prepared_false_when_missing(self, tmp_path):
        mgr = GoldStandardManager(cache_dir=tmp_path)
        assert mgr.is_prepared() is False

    def test_is_prepared_true_when_all_present(self, tmp_path):
        mgr = GoldStandardManager(cache_dir=tmp_path)
        # Simulate all 9 adapters being prepared
        for name in mgr.required_adapters():
            marker = tmp_path / name / ".prepared"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("task_count=10\nprepared_at=2026-03-12T00:00:00+00:00\n")
        assert mgr.is_prepared() is True

    def test_missing_adapters_lists_unprepared(self, tmp_path):
        mgr = GoldStandardManager(cache_dir=tmp_path)
        # Prepare only ds1000
        marker = tmp_path / "ds1000" / ".prepared"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("task_count=10\n")
        missing = mgr.missing_adapters()
        assert "ds1000" not in missing
        assert len(missing) == 8
```

### Step 2: Run test to verify it fails

```bash
uv run pytest agent-evals/tests/test_dataset_gold_standard.py -v
```

### Step 3: Implement GoldStandardManager

Create `agent-evals/src/agent_evals/datasets/gold_standard.py`:

```python
"""Gold standard dataset manager.

The gold standard is the union of all 9 HF dataset adapters.
Each adapter maps to one task type, providing battle-tested
evaluation criteria from established benchmarks.
"""

from __future__ import annotations

from pathlib import Path

from agent_evals.datasets import get_adapter, load_all
from agent_evals.datasets.cache import DatasetCache

# All non-synthetic HF adapters required for gold standard
_REQUIRED_ADAPTERS: tuple[str, ...] = (
    "ambigqa",
    "bigcodebench",
    "code-rag-bench",
    "ds1000",
    "ibm-techqa",
    "multihop-rag",
    "repliqa",
    "swe-bench",
    "wikicontradict",
)

# Per-adapter default limits (ibm-techqa needs capping)
_DEFAULT_LIMITS: dict[str, int] = {
    "ibm-techqa": 50,
}

# General default when no per-adapter limit specified
_GENERAL_DEFAULT_LIMIT: int = 100


class GoldStandardManager:
    """Manages HF dataset preparation and loading as gold standard."""

    def __init__(
        self,
        cache_dir: Path | None = None,
        limits: dict[str, int] | None = None,
    ) -> None:
        self._cache = DatasetCache(cache_dir)
        self._limits = {**_DEFAULT_LIMITS, **(limits or {})}

    def required_adapters(self) -> tuple[str, ...]:
        """Return names of all required HF adapters."""
        return _REQUIRED_ADAPTERS

    def is_prepared(self) -> bool:
        """True if all required adapters have been prepared."""
        return len(self.missing_adapters()) == 0

    def missing_adapters(self) -> list[str]:
        """Return names of adapters that haven't been prepared."""
        return [
            name
            for name in _REQUIRED_ADAPTERS
            if not self._cache.is_prepared(name)
        ]

    def prepare_all(
        self,
        default_limit: int | None = None,
    ) -> dict[str, int]:
        """Prepare all required adapters. Returns {name: task_count}."""
        load_all()
        results: dict[str, int] = {}
        effective_default = default_limit or _GENERAL_DEFAULT_LIMIT

        for name in _REQUIRED_ADAPTERS:
            if self._cache.is_prepared(name):
                results[name] = 0  # already prepared
                continue

            adapter = get_adapter(name)
            limit = self._limits.get(name, effective_default)
            output_dir = self._cache.task_dir(name)
            count = adapter.convert_tasks(output_dir, limit=limit)

            # Save doc_tree.json (matches --prepare-datasets behavior in cli.py)
            doc_tree = adapter.build_doc_tree(limit=limit)
            dt_path = self._cache.doc_tree_path(name)
            dt_path.write_text(
                doc_tree.model_dump_json(indent=2), encoding="utf-8",
            )

            self._cache.mark_prepared(name, task_count=count)
            results[name] = count

        return results

    def limit_for(self, adapter_name: str) -> int:
        """Return the configured limit for an adapter."""
        return self._limits.get(adapter_name, _GENERAL_DEFAULT_LIMIT)
```

### Step 4: Run test to verify it passes

```bash
uv run pytest agent-evals/tests/test_dataset_gold_standard.py -v
```

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/datasets/gold_standard.py \
  agent-evals/tests/test_dataset_gold_standard.py
git commit -m "feat: add GoldStandardManager for HF dataset preparation

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Rewire `--source gold_standard` to load HF datasets

Change the default `gold_standard` source to load from prepared HF datasets instead of hand-crafted YAMLs.

> **Architecture note:** The CLI uses `agent_evals.source` (top-level), NOT `agent_evals.datasets.source`.
> There are TWO source files:
> - `agent-evals/src/agent_evals/source.py` — CLI routing (`load_tasks_for_source`, `load_doc_tree_for_source`)
> - `agent-evals/src/agent_evals/datasets/source.py` — Dataset-level loading (`load_from_source`, `MixedSourceLoader`)
>
> This task modifies the **top-level** `source.py` since that's what the CLI calls.

**Files:**
- Modify: `agent-evals/src/agent_evals/source.py` (main routing change — `load_tasks_for_source` and `load_doc_tree_for_source`)
- Modify: `agent-evals/src/agent_evals/cli.py` (update `--source` help text)
- Test: `agent-evals/tests/test_source.py` (new tests for gold_standard routing)

### Step 1: Write failing test for new gold_standard routing

Add to `agent-evals/tests/test_source.py`:

```python
from agent_evals.source import load_tasks_for_source, load_doc_tree_for_source


class TestGoldStandardFromDatasets:
    def test_gold_standard_loads_from_prepared_datasets(self, tmp_path, monkeypatch):
        """gold_standard source loads HF datasets when prepared."""
        from agent_evals.datasets.gold_standard import GoldStandardManager

        mgr = GoldStandardManager(cache_dir=tmp_path)
        # Mock all 9 adapters as prepared with sample tasks
        for name in mgr.required_adapters():
            task_dir = tmp_path / name / "tasks"
            task_dir.mkdir(parents=True)
            # Write a minimal valid task YAML
            _write_sample_task(task_dir, name)
            marker = tmp_path / name / ".prepared"
            marker.write_text("task_count=1\n")

        # Patch the GoldStandardManager to use tmp_path
        monkeypatch.setattr(
            "agent_evals.source._gold_standard_cache_dir", tmp_path,
        )
        tasks = load_tasks_for_source("gold_standard")
        assert len(tasks) > 0

    def test_gold_standard_falls_back_to_legacy_when_not_prepared(self, tmp_path, monkeypatch):
        """gold_standard falls back to legacy YAMLs when datasets not prepared."""
        monkeypatch.setattr(
            "agent_evals.source._gold_standard_cache_dir", tmp_path,
        )
        # Should fall back to legacy (load from _GOLD_STANDARD_DIR)
        tasks = load_tasks_for_source("gold_standard")
        assert len(tasks) > 0  # Legacy tasks loaded

    def test_legacy_source_loads_hand_crafted_yamls(self):
        """--source legacy explicitly loads old hand-crafted tasks."""
        tasks = load_tasks_for_source("legacy")
        assert len(tasks) > 0  # Loads from gold_standard/ directory
```

### Step 2: Run test to verify it fails

```bash
uv run pytest agent-evals/tests/test_source.py::TestGoldStandardFromDatasets -v
```

### Step 3: Update source routing

In `agent-evals/src/agent_evals/source.py`, update `load_tasks_for_source`:

```python
def load_tasks_for_source(source: str = DEFAULT_SOURCE) -> list[Any]:
    """Load evaluation tasks for the given *source*."""
    from agent_evals.tasks.loader import load_tasks

    if source == "legacy":
        if not _GOLD_STANDARD_DIR.is_dir():
            raise FileNotFoundError(
                f"Gold standard directory not found: {_GOLD_STANDARD_DIR}"
            )
        return load_tasks(_GOLD_STANDARD_DIR)

    if source == DEFAULT_SOURCE:
        from agent_evals.datasets.gold_standard import GoldStandardManager

        mgr = GoldStandardManager()
        if mgr.is_prepared():
            return _load_gold_standard_tasks(mgr)
        # Fall back to legacy when datasets not prepared
        logger.warning(
            "HF datasets not prepared. Falling back to legacy gold standard. "
            "Run 'agent-evals --prepare-datasets all' to prepare."
        )
        if not _GOLD_STANDARD_DIR.is_dir():
            raise FileNotFoundError(
                f"Gold standard directory not found: {_GOLD_STANDARD_DIR}"
            )
        return load_tasks(_GOLD_STANDARD_DIR)

    # Existing dataset/comma-list routing...
    names = [n.strip() for n in source.split(",")]
    # ... (unchanged) ...
```

Similarly update `load_doc_tree_for_source`:

```python
def load_doc_tree_for_source(source: str = DEFAULT_SOURCE) -> Any:
    """Load the doc_tree for the given *source*."""
    if source == "legacy":
        from agent_evals.fixtures import load_sample_doc_tree
        return load_sample_doc_tree()

    if source == DEFAULT_SOURCE:
        from agent_evals.datasets.gold_standard import GoldStandardManager
        mgr = GoldStandardManager()
        if mgr.is_prepared():
            return _load_gold_standard_doc_tree(mgr)
        # Fall back to legacy fixture
        from agent_evals.fixtures import load_sample_doc_tree
        return load_sample_doc_tree()

    # Existing dataset routing...
```

### Step 4: Implement gold standard loading helpers

```python
def _load_gold_standard_tasks(mgr: GoldStandardManager) -> list[Any]:
    """Load tasks from all 9 prepared HF adapters."""
    from agent_evals.tasks.loader import load_tasks

    all_tasks: list[Any] = []
    for name in mgr.required_adapters():
        task_dir = mgr._cache.task_dir(name)
        all_tasks.extend(load_tasks(task_dir))
    return all_tasks


def _load_gold_standard_doc_tree(mgr: GoldStandardManager) -> Any:
    """Merge DocTrees from all 9 HF adapters, namespacing files."""
    from datetime import UTC, datetime

    from agent_index.models import DocTree

    merged_files: dict[str, Any] = {}
    total_tokens = 0

    for name in mgr.required_adapters():
        dt_path = mgr._cache.doc_tree_path(name)
        if not dt_path.exists():
            continue
        dt = DocTree.model_validate_json(
            dt_path.read_text(encoding="utf-8")
        )
        for rel_path, doc_file in dt.files.items():
            merged_files[f"{name}/{rel_path}"] = doc_file
        total_tokens += dt.total_tokens or 0

    return DocTree(
        files=merged_files,
        scanned_at=datetime.now(tz=UTC),
        source="gold_standard",
        total_tokens=total_tokens,
    )
```

> **Note:** This follows the same merge pattern as `MixedSourceLoader.build_merged_doc_tree()` in
> `datasets/source.py:90-110` and `load_doc_tree_for_source` multi-dataset path (lines 105-120).
> `DocTree.files` is a `dict[str, DocFile]` (not a list), so we use dict assignment, not `.extend()`.
> The `DatasetCache` attribute is `cache_dir` (not `_base_dir`).

### Step 5: Update `--source` help text in CLI

In `agent-evals/src/agent_evals/cli.py`, update only the help text (keep `default=None` — the runtime default is applied at line 831):

```python
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help=(
            "Task source: gold_standard (default, loads HF datasets), "
            "'legacy' (hand-crafted YAMLs), dataset name, "
            "or comma-separated list"
        ),
    )
```

### Step 6: Run tests, fix regressions

```bash
uv run pytest agent-evals/tests/test_source.py -v
uv run pytest agent-evals/tests/ -x -q  # full suite regression check
```

### Step 7: Commit

```bash
git add agent-evals/src/agent_evals/source.py \
  agent-evals/src/agent_evals/cli.py \
  agent-evals/tests/test_source.py
git commit -m "feat: rewire --source gold_standard to load HF datasets

Modifies load_tasks_for_source() and load_doc_tree_for_source() in
source.py to check GoldStandardManager first. Falls back to legacy
YAMLs when datasets not prepared. Adds --source legacy for explicit
access to hand-crafted tasks.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Move hand-crafted YAMLs to legacy directory

Relocate hand-crafted gold standard tasks to `gold_standard_legacy/` to clarify they're supplementary.

**Files:**
- Move: `agent-evals/gold_standard/` → `agent-evals/gold_standard_legacy/`
- Modify: `agent-evals/src/agent_evals/source.py` (update `_GOLD_STANDARD_DIR` path at line 17-19)
- Test: `agent-evals/tests/` (update any tests referencing gold_standard path)

> **Note:** The path is defined in `agent-evals/src/agent_evals/source.py:17-19`:
> ```python
> _GOLD_STANDARD_DIR = (
>     Path(__file__).resolve().parent.parent.parent / "gold_standard"
> )
> ```
> Change `"gold_standard"` to `"gold_standard_legacy"`. No other files hardcode this path —
> `loader.py` receives a `directory` parameter, not a hardcoded path.

### Step 1: Move the directory

```bash
mv agent-evals/gold_standard agent-evals/gold_standard_legacy
```

### Step 2: Update path references

In `agent-evals/src/agent_evals/source.py`, update `_GOLD_STANDARD_DIR`:

```python
_GOLD_STANDARD_DIR = (
    Path(__file__).resolve().parent.parent.parent / "gold_standard_legacy"
)
```

Also search for any other references:

```bash
# Find all references
grep -rn "gold_standard" agent-evals/src/ --include="*.py" | grep -v "__pycache__"
```

### Step 3: Run full test suite

```bash
uv run pytest agent-evals/tests/ -x -q
```

Fix any broken path references.

### Step 4: Commit

```bash
git add -A
git commit -m "refactor: move hand-crafted tasks to gold_standard_legacy/

HF datasets are now the primary gold standard. Legacy tasks remain
available via --source legacy for backwards compatibility.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Wire synthetic adapters to auto-generate from HF data (Bead #166)

The perturbation and synthetic-efficiency adapters need to auto-generate from prepared HF datasets instead of requiring manual source directories.

**Files:**
- Modify: `agent-evals/src/agent_evals/datasets/synthetic_efficiency.py`
- Modify: `agent-evals/src/agent_evals/datasets/perturbation.py`
- Modify: `agent-evals/src/agent_evals/datasets/gold_standard.py` (add synthetic generation step)
- Test: `agent-evals/tests/test_dataset_efficiency.py`, `agent-evals/tests/test_dataset_perturbation.py`

### Step 1: Write failing test

```python
class TestSyntheticAutoGeneration:
    def test_efficiency_generates_from_prepared_fact_extraction(self, tmp_path):
        """Synthetic efficiency adapter should auto-source from ibm-techqa tasks."""
        # Setup: create mock ibm-techqa prepared tasks
        task_dir = tmp_path / "ibm-techqa" / "tasks"
        task_dir.mkdir(parents=True)
        _write_sample_fact_extraction_task(task_dir / "techqa_fact_extraction_001.yaml")

        adapter = SyntheticEfficiencyAdapter()
        output_dir = tmp_path / "synthetic-efficiency" / "tasks"
        output_dir.mkdir(parents=True)
        count = adapter.convert_tasks(output_dir, limit=5, source_dir=task_dir)
        assert count > 0

    def test_perturbation_generates_from_prepared_retrieval(self, tmp_path):
        """Perturbation adapter should auto-source from prepared retrieval tasks."""
        # Similar pattern for perturbation
        pass
```

### Step 2: Implement auto-source in GoldStandardManager.prepare_all

After preparing the 9 HF adapters, auto-generate synthetic tasks:

```python
    def prepare_all(self, default_limit: int | None = None) -> dict[str, int]:
        # ... prepare 9 HF adapters (existing code) ...

        # Auto-generate synthetic tasks from prepared data
        results.update(self._generate_synthetic_tasks(effective_default))
        return results

    def _generate_synthetic_tasks(self, limit: int) -> dict[str, int]:
        """Generate synthetic adapter tasks from prepared HF data."""
        results: dict[str, int] = {}

        # Efficiency: generate from ibm-techqa (fact_extraction)
        if self._cache.is_prepared("ibm-techqa"):
            source_dir = self._cache.task_dir("ibm-techqa")
            adapter = get_adapter("synthetic-efficiency")
            output_dir = self._cache.task_dir("synthetic-efficiency")
            count = adapter.convert_tasks(output_dir, limit=limit, source_dir=source_dir)
            self._cache.mark_prepared("synthetic-efficiency", task_count=count)
            results["synthetic-efficiency"] = count

        # Perturbation: generate from multiple sources
        if self._cache.is_prepared("code-rag-bench"):
            source_dir = self._cache.task_dir("code-rag-bench")
            adapter = get_adapter("perturbation")
            output_dir = self._cache.task_dir("perturbation")
            count = adapter.convert_tasks(output_dir, limit=limit, source_dir=source_dir)
            self._cache.mark_prepared("perturbation", task_count=count)
            results["perturbation"] = count

        return results
```

### Step 3: Run tests

```bash
uv run pytest agent-evals/tests/test_dataset_efficiency.py agent-evals/tests/test_dataset_perturbation.py -v
```

### Step 4: Commit

```bash
git add agent-evals/src/agent_evals/datasets/synthetic_efficiency.py \
  agent-evals/src/agent_evals/datasets/perturbation.py \
  agent-evals/src/agent_evals/datasets/gold_standard.py \
  agent-evals/tests/
git commit -m "feat: auto-generate synthetic tasks from prepared HF data

Closes bead #166. Synthetic-efficiency generates from ibm-techqa,
perturbation generates from code-rag-bench. Both wired into
GoldStandardManager.prepare_all().

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Add `--prepare-datasets all` support

Enable a single command to prepare the entire gold standard.

**Files:**
- Modify: `agent-evals/src/agent_evals/cli.py` (handle "all" in --prepare-datasets)
- Test: `agent-evals/tests/test_evals_cli.py`

### Step 1: Write failing test

```python
class TestPrepareAll:
    def test_prepare_all_invokes_gold_standard_manager(self, monkeypatch):
        """--prepare-datasets all should prepare all 9 HF adapters."""
        prepared = []
        def mock_prepare(self, default_limit=None):
            prepared.append("all")
            return {"ds1000": 10, "ambigqa": 10}

        monkeypatch.setattr(GoldStandardManager, "prepare_all", mock_prepare)
        # Invoke CLI with --prepare-datasets all
        # ... assert prepared == ["all"]
```

### Step 2: Implement in CLI

In `agent-evals/src/agent_evals/cli.py`, add the "all" case **inside** the existing `--prepare-datasets` handler block (around line 704-734). Insert before the `names = [n.strip() ...]` line:

```python
    # --prepare-datasets: download + convert without running evals (no model needed)
    prepare = resolved.get("prepare_datasets")
    if prepare is not None:
        if prepare == "all":
            from agent_evals.datasets.gold_standard import GoldStandardManager

            cache_dir = resolved.get("dataset_cache_dir")
            mgr = GoldStandardManager(
                cache_dir=Path(cache_dir) if cache_dir else None,
            )
            results = mgr.prepare_all(
                default_limit=resolved.get("dataset_limit"),
            )
            for name, count in results.items():
                logger.info("Prepared %d tasks for '%s'", count, name)
            return 0

        # ... existing per-adapter preparation logic (unchanged) ...
```

### Step 3: Run tests

```bash
uv run pytest agent-evals/tests/test_evals_cli.py -v
```

### Step 4: Commit

```bash
git add agent-evals/src/agent_evals/cli.py agent-evals/tests/test_evals_cli.py
git commit -m "feat: --prepare-datasets all prepares entire gold standard

Uses GoldStandardManager to download and prepare all 9 HF adapters
plus auto-generate synthetic tasks in a single command.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Update setup scripts and documentation

Update the setup flow so new users prepare datasets as part of initial setup.

**Files:**
- Modify: `scripts/setup.sh` (add dataset preparation step)
- Modify: `CLAUDE.md` (update commands section)
- Modify: `agent-evals/src/agent_evals/cli.py` (add helpful error when datasets not prepared)

### Step 1: Add dataset preparation to setup.sh

```bash
# After uv sync --dev
echo "Preparing gold standard datasets..."
uv run agent-evals --prepare-datasets all --dataset-limit 100
```

### Step 2: Verify helpful error message

The warning message is already added in Task 3's `load_tasks_for_source()` update. Verify it includes the list of missing adapters:

```python
    # In source.py load_tasks_for_source(), already added in Task 3:
    mgr = GoldStandardManager()
    if mgr.is_prepared():
        return _load_gold_standard_tasks(mgr)
    missing = mgr.missing_adapters()
    logger.warning(
        "HF datasets not prepared (missing: %s). Falling back to legacy. "
        "Run: agent-evals --prepare-datasets all",
        ", ".join(missing),
    )
```

If Task 3 didn't include the missing adapter names, update it now.

### Step 3: Update CLAUDE.md commands section

Update the commands reference:

```markdown
# First-time setup (after uv sync --dev)
agent-evals --prepare-datasets all --dataset-limit 100

# Run evaluation (uses HF datasets as gold standard)
agent-evals --model openrouter/provider/name

# Run with legacy hand-crafted tasks
agent-evals --source legacy --model openrouter/provider/name
```

### Step 4: Commit

```bash
git add scripts/setup.sh CLAUDE.md agent-evals/src/agent_evals/cli.py
git commit -m "docs: update setup flow for HF gold standard

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 8: Fix remaining issues from sprint review

Address other issues discovered during the scoring fixes sprint that aren't part of the gold standard migration but should be fixed.

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/efficiency.py` (add fuzzy matching)
- Modify: `agent-evals/src/agent_evals/judge/calibrator.py` (fix zip strict in extract_judge_metadata for compositional)
- Test: `agent-evals/tests/test_task_efficiency.py`, `agent-evals/tests/test_judge_calibration.py`

### Step 1: Add fuzzy matching to efficiency scorer

The efficiency scorer uses exact/alias/keyword matching only — no rapidfuzz. Import and use `fuzzy_to_continuous_score` from `_utils.py` (the same helper we extracted in the scoring sprint).

```python
# Add imports at the top of efficiency.py:
from rapidfuzz import fuzz
from rapidfuzz import utils as fuzz_utils

from agent_evals.tasks._utils import fuzzy_to_continuous_score

# In score_response(), after alias check fails but before keyword fallback:
fuzzy_score = fuzz.token_set_ratio(norm_expected, norm_response, processor=fuzz_utils.default_process)
continuous = fuzzy_to_continuous_score(fuzzy_score)
if continuous is not None:
    base_score = continuous
else:
    # Fall through to keyword matching
    ...
```

### Step 2: Fix zip strict in extract_judge_metadata

In `agent-evals/src/agent_evals/judge/calibrator.py`, the `extract_judge_metadata` function for compositional type uses `zip(sub_questions, expected_answers)` without `strict=True`. While `CompositionalTask.__init__` validates lengths match, defensive coding says use `strict=False` explicitly and handle the mismatch:

```python
# Use zip without strict for defensive handling of mismatched lengths
for i, (q, a) in enumerate(zip(sub_questions, expected_answers), 1):
    parts.append(f"{i}. {q}: {a}")
```

This is already the behavior (no `strict` keyword = no error on mismatch), but add a comment documenting the intentional choice.

### Step 3: Write tests for efficiency fuzzy matching

```python
class TestEfficiencyFuzzyScoring:
    def test_fuzzy_match_gets_partial_credit(self):
        """Efficiency scorer should use fuzzy matching for near-matches."""
        task = _efficiency_task(expected_answer="connection pooling strategy")
        score = task.score_response("the connection pooling approach")
        assert score > 0.7  # fuzzy match, not zero
```

### Step 4: Run tests

```bash
uv run pytest agent-evals/tests/test_task_efficiency.py agent-evals/tests/test_judge_calibration.py -v
```

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/tasks/efficiency.py \
  agent-evals/src/agent_evals/judge/calibrator.py \
  agent-evals/tests/test_task_efficiency.py \
  agent-evals/tests/test_judge_calibration.py
git commit -m "feat: add fuzzy matching to efficiency scorer

Uses fuzzy_to_continuous_score helper for near-match partial credit.
Also documents intentional zip behavior in extract_judge_metadata.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 9: End-to-end validation with HF gold standard

After migration, run a validation to confirm HF datasets produce better score discrimination.

### Step 1: Prepare all datasets

```bash
uv run agent-evals --prepare-datasets all --dataset-limit 50
```

### Step 2: Dry run

```bash
uv run agent-evals --mode taguchi --limit 3 --repetitions 1 --dry-run \
  --model openrouter/arcee-ai/trinity-large-preview:free
```

Verify: task count reflects HF dataset tasks, not legacy 355.

### Step 3: Run evaluation

```bash
uv run agent-evals --mode taguchi \
  --model openrouter/arcee-ai/trinity-large-preview:free \
  --judge-enabled \
  --judge-model openrouter/stepfun/step-3.5-flash:free \
  --judge-primary-types code_generation,compositional,agentic \
  --judge-sample-rate 5 \
  --limit 1 --repetitions 1 \
  --max-connections 3 \
  --report both \
  --continue-on-error --store-traces --verbose
```

### Step 4: Validate results

Check observatory for pass criteria:
- **code_generation**: Score variance > 0.01 (not all 1.0)
- **fact_extraction**: Score variance > 0.01 (not all 1.0)
- All 11 task types present
- Judge coverage: 100% for primary types, ~20% for others
- At least 2 factors with main effect range > 0.10

```bash
uv run python -c "
import sqlite3
conn = sqlite3.connect('observatory.db')
cur = conn.cursor()
cur.execute('SELECT run_id FROM runs ORDER BY created_at DESC LIMIT 1')
run_id = cur.fetchone()[0]
cur.execute('''SELECT task_type, COUNT(*), ROUND(AVG(score),4),
    ROUND(MIN(score),4), ROUND(MAX(score),4),
    ROUND(AVG(score*score)-AVG(score)*AVG(score),6) as variance
    FROM trials WHERE run_id = ? AND error IS NULL
    GROUP BY task_type ORDER BY task_type''', (run_id,))
for row in cur.fetchall():
    print(row)
"
```

### Step 5: Compare with pre-migration run

Compare run `f3d527daa263` (legacy gold standard) against the new HF gold standard run. Key metric: score variance per task type should be higher for code_generation and fact_extraction.

---

## Implementation Order

| Order | Task | Risk | Dependencies |
|---|---|---|---|
| 1 | Task 1: Audit coverage | None | — |
| 2 | Task 2: GoldStandardManager | Low | — |
| 3 | Task 3: Rewire gold_standard source | Medium | Task 2 |
| 4 | Task 4: Move legacy YAMLs | Low | Task 3 |
| 5 | Task 5: Synthetic auto-generation | Medium | Task 2, bead #166 |
| 6 | Task 6: --prepare-datasets all | Low | Task 2 |
| 7 | Task 7: Setup scripts & docs | Low | Tasks 3, 6 |
| 8 | Task 8: Remaining sprint issues | Low | — (independent) |
| 9 | Task 9: Validation run | None | Tasks 1-7 |

## Known Risks

1. **ibm-techqa requires TECHQA_DIR env var** — The dataset is not publicly downloadable via HF. Users need the TechQA corpus locally. The setup script should check for this and warn if missing.

2. **HF download failures** — Network issues during `--prepare-datasets all` could leave partial state. The `.prepared` marker system handles this (only marks after success), but the user experience could be confusing. Consider adding `--prepare-datasets <name> --force` to re-prepare a single adapter.

3. **Dataset size variation** — ibm-techqa has 28K files, others have 50-1000. `--dataset-limit` normalizes this, but the default limit (100) may be too low for statistical power or too high for ibm-techqa rendering.

4. **Contamination risk** — ambigqa and wikicontradict are flagged HIGH contamination risk. Models may have seen these during training, inflating scores. Document this and consider weighting low-contamination datasets higher.
