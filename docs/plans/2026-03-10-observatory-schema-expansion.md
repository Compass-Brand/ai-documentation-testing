# Observatory Schema Expansion — 8 New Tables/Features

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close all data gaps in the observatory database so every piece of evaluation telemetry is persisted, queryable, and exportable.

**Architecture:** 5 new tables + 3 columns on `phase_results` + 1 new analysis module + 2 CLI subcommands. All additions use the existing idempotent migration pattern in `ObservatoryStore._migrate_schema()`. Each task is self-contained with its own schema, store methods, wiring, and tests.

**Tech Stack:** SQLite (WAL mode), Pydantic v2 dataclasses, pytest, argparse CLI

---

## Dependency Graph

```text
Task 1 (factor_definitions)  ──┐
Task 2 (task_metadata)        ──┤
Task 3 (phase cost totals)    ──┼── all independent ──► Task 8 (export/import)
Task 4 (report_artifacts)     ──┤
Task 5 (interaction_effects)  ──┤
Task 6 (llm_call_details)    ──┘
                                     Task 7 (dashboard endpoints) after Tasks 1-6
```

Tasks 1-6 are fully independent and can be parallelised. Task 7 adds API endpoints for the new data. Task 8 (export/import) depends on all tables existing.

---

## Task 1: Factor Definitions + Variant Axis Map

**Purpose:** Persist the mapping from factor names → axis IDs → level names with human-readable descriptions. Currently levels are opaque strings like `"level_2_of_3"` with no reverse lookup.

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/store.py`
- Modify: `agent-evals/src/agent_evals/observatory/tracker.py`
- Test: `agent-evals/tests/test_observatory_store.py`

### Step 1: Write failing test — save and retrieve factor definitions

```python
# In test_observatory_store.py, new class TestFactorDefinitions

class TestFactorDefinitions:
    def test_save_and_get_factor_definitions(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", "taguchi", {})
        definitions = [
            {
                "factor_name": "structure",
                "axis_id": 1,
                "level_index": 0,
                "level_name": "flat",
                "description": "Flat file listing with no hierarchy",
            },
            {
                "factor_name": "structure",
                "axis_id": 1,
                "level_index": 1,
                "level_name": "nested",
                "description": "Nested directory tree structure",
            },
            {
                "factor_name": "format",
                "axis_id": 2,
                "level_index": 0,
                "level_name": "markdown",
                "description": "Standard markdown table format",
            },
        ]
        store.save_factor_definitions("run_001", definitions)
        result = store.get_factor_definitions("run_001")
        assert len(result) == 3
        assert result[0]["factor_name"] == "structure"
        assert result[0]["level_name"] == "flat"
        assert result[2]["axis_id"] == 2

    def test_get_factor_definitions_empty(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", "taguchi", {})
        result = store.get_factor_definitions("run_001")
        assert result == []

    def test_factor_definitions_replaced_on_rewrite(
        self, store: ObservatoryStore
    ) -> None:
        store.create_run("run_001", "taguchi", {})
        store.save_factor_definitions("run_001", [
            {"factor_name": "f", "axis_id": 1, "level_index": 0,
             "level_name": "a", "description": "old"},
        ])
        store.save_factor_definitions("run_001", [
            {"factor_name": "f", "axis_id": 1, "level_index": 0,
             "level_name": "b", "description": "new"},
        ])
        result = store.get_factor_definitions("run_001")
        assert len(result) == 1
        assert result[0]["level_name"] == "b"
```

Run: `uv run pytest agent-evals/tests/test_observatory_store.py::TestFactorDefinitions -v`
Expected: FAIL — `save_factor_definitions` does not exist.

### Step 2: Implement schema + store methods

**Schema** (add to `_SCHEMA` in `store.py`):

```sql
CREATE TABLE IF NOT EXISTS factor_definitions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL REFERENCES runs(run_id),
    factor_name  TEXT NOT NULL,
    axis_id      INTEGER NOT NULL,
    level_index  INTEGER NOT NULL,
    level_name   TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_factor_defs_run
    ON factor_definitions (run_id);
```

**Store methods** (add to `ObservatoryStore`):

```python
def save_factor_definitions(
    self, run_id: str, definitions: list[dict]
) -> None:
    """Save factor/level definitions for a run. Replaces existing."""
    with self._lock, self._connect() as conn:
        conn.execute(
            "DELETE FROM factor_definitions WHERE run_id = ?", (run_id,)
        )
        conn.executemany(
            "INSERT INTO factor_definitions "
            "(run_id, factor_name, axis_id, level_index, level_name, description) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    run_id, d["factor_name"], d["axis_id"],
                    d["level_index"], d["level_name"],
                    d.get("description", ""),
                )
                for d in definitions
            ],
        )

def get_factor_definitions(self, run_id: str) -> list[dict]:
    """Return factor definitions for a run, ordered by axis then level."""
    with self._connect() as conn:
        rows = conn.execute(
            "SELECT factor_name, axis_id, level_index, level_name, description "
            "FROM factor_definitions WHERE run_id = ? "
            "ORDER BY axis_id, level_index",
            (run_id,),
        ).fetchall()
    return [dict(r) for r in rows]
```

Add migration for existing databases in `_migrate_schema()`:

```python
# In the migrations list — the CREATE TABLE in _SCHEMA handles new DBs,
# but _migrate_schema ensures the index exists for upgraded DBs.
```

The `CREATE TABLE IF NOT EXISTS` in `_SCHEMA` handles this table for both new and existing DBs. Add the index to the `indexes` list in `_migrate_schema`.

### Step 3: Run tests — verify pass

Run: `uv run pytest agent-evals/tests/test_observatory_store.py::TestFactorDefinitions -v`
Expected: PASS (3 tests)

### Step 4: Wire into pipeline — populate at run creation

**Modify:** `agent-evals/src/agent_evals/pipeline.py`

In `DOEPipeline.run_screening()`, after creating the run, build and save factor definitions from the variants list:

```python
# After the run is created and before trials start:
def _save_factor_defs(self, run_id: str, variants: list) -> None:
    """Extract and persist factor definitions from variant metadata."""
    if self._store is None:
        return
    from collections import defaultdict
    axes: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for v in variants:
        meta = v.metadata()
        entry = (meta.name, meta.description)
        if entry not in axes[meta.axis]:
            axes[meta.axis].append(entry)
    definitions = []
    for axis_id in sorted(axes):
        for idx, (name, desc) in enumerate(axes[axis_id]):
            definitions.append({
                "factor_name": name.split("-")[0] if "-" in name else name,
                "axis_id": axis_id,
                "level_index": idx,
                "level_name": name,
                "description": desc,
            })
    self._store.save_factor_definitions(run_id, definitions)
```

Call `self._save_factor_defs(result.run_id, variants)` after run creation in `run_screening()`.

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/observatory/store.py \
       agent-evals/src/agent_evals/pipeline.py \
       agent-evals/tests/test_observatory_store.py
git commit -m "feat(observatory): add factor_definitions table with axis/level semantics"
```

---

## Task 2: Task Metadata Table

**Purpose:** Persist task-level attributes (domain, difficulty, word count, tag count) so queries can slice trial results by task complexity without re-loading task definitions.

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/store.py`
- Modify: `agent-evals/src/agent_evals/observatory/tracker.py`
- Test: `agent-evals/tests/test_observatory_store.py`

### Step 1: Write failing test

```python
class TestTaskMetadata:
    def test_save_and_get_task_metadata(self, store: ObservatoryStore) -> None:
        metadata_list = [
            {
                "task_id": "retrieval_001",
                "task_type": "retrieval",
                "domain": "API",
                "difficulty": "medium",
                "word_count": 42,
                "tag_count": 3,
            },
            {
                "task_id": "code_gen_005",
                "task_type": "code_generation",
                "domain": "SDK",
                "difficulty": "hard",
                "word_count": 128,
                "tag_count": 5,
            },
        ]
        store.save_task_metadata(metadata_list)
        result = store.get_task_metadata()
        assert len(result) == 2
        assert result[0]["task_id"] == "code_gen_005"  # sorted by task_id
        assert result[1]["word_count"] == 42

    def test_task_metadata_upsert(self, store: ObservatoryStore) -> None:
        store.save_task_metadata([
            {"task_id": "t1", "task_type": "retrieval", "domain": "API",
             "difficulty": "easy", "word_count": 10, "tag_count": 1},
        ])
        store.save_task_metadata([
            {"task_id": "t1", "task_type": "retrieval", "domain": "API",
             "difficulty": "hard", "word_count": 20, "tag_count": 2},
        ])
        result = store.get_task_metadata()
        assert len(result) == 1
        assert result[0]["difficulty"] == "hard"

    def test_get_task_metadata_by_type(self, store: ObservatoryStore) -> None:
        store.save_task_metadata([
            {"task_id": "r1", "task_type": "retrieval", "domain": "API",
             "difficulty": "easy", "word_count": 10, "tag_count": 1},
            {"task_id": "c1", "task_type": "code_generation", "domain": "SDK",
             "difficulty": "hard", "word_count": 50, "tag_count": 2},
        ])
        result = store.get_task_metadata(task_type="retrieval")
        assert len(result) == 1
        assert result[0]["task_id"] == "r1"
```

Run: `uv run pytest agent-evals/tests/test_observatory_store.py::TestTaskMetadata -v`
Expected: FAIL

### Step 2: Implement schema + store methods

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS task_metadata (
    task_id    TEXT PRIMARY KEY,
    task_type  TEXT NOT NULL,
    domain     TEXT NOT NULL DEFAULT '',
    difficulty TEXT NOT NULL DEFAULT '',
    word_count INTEGER NOT NULL DEFAULT 0,
    tag_count  INTEGER NOT NULL DEFAULT 0
);
```

**Store methods:**

```python
def save_task_metadata(self, metadata_list: list[dict]) -> None:
    """Upsert task metadata. Replaces existing rows on conflict."""
    with self._lock, self._connect() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO task_metadata "
            "(task_id, task_type, domain, difficulty, word_count, tag_count) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    m["task_id"], m["task_type"], m.get("domain", ""),
                    m.get("difficulty", ""), m.get("word_count", 0),
                    m.get("tag_count", 0),
                )
                for m in metadata_list
            ],
        )

def get_task_metadata(
    self, *, task_type: str | None = None
) -> list[dict]:
    """Return task metadata, optionally filtered by type."""
    query = "SELECT * FROM task_metadata"
    params: list[str] = []
    if task_type is not None:
        query += " WHERE task_type = ?"
        params.append(task_type)
    query += " ORDER BY task_id"
    with self._connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]
```

### Step 3: Wire into runner — populate at task load

**Modify:** `agent-evals/src/agent_evals/orchestrator.py` (or wherever tasks are first iterated)

After tasks are loaded and before trials begin, extract and save metadata:

```python
def _persist_task_metadata(self, tasks: list, store: ObservatoryStore) -> None:
    metadata = []
    for task in tasks:
        defn = task.definition
        metadata.append({
            "task_id": defn.task_id,
            "task_type": defn.type,
            "domain": defn.domain,
            "difficulty": defn.difficulty,
            "word_count": len(defn.question.split()),
            "tag_count": len(defn.tags),
        })
    store.save_task_metadata(metadata)
```

### Step 4: Run tests — verify pass

Run: `uv run pytest agent-evals/tests/test_observatory_store.py::TestTaskMetadata -v`
Expected: PASS (3 tests)

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/observatory/store.py \
       agent-evals/src/agent_evals/orchestrator.py \
       agent-evals/tests/test_observatory_store.py
git commit -m "feat(observatory): add task_metadata table for task-level attributes"
```

---

## Task 3: Phase Cost Totals Persistence

**Purpose:** Persist per-phase cost/token/elapsed totals so pipeline resume doesn't lose them. Currently `save_phase_results()` exists but is never called from production code, and it lacks cost fields.

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/store.py`
- Modify: `agent-evals/src/agent_evals/pipeline.py`
- Test: `agent-evals/tests/test_observatory_store.py`
- Test: `agent-evals/tests/test_pipeline_integration.py`

### Step 1: Write failing test — save/get with cost totals

```python
class TestPhaseResultsCost:
    def test_save_phase_results_with_cost(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", "taguchi", {})
        store.save_phase_results(
            run_id="run_001",
            main_effects={"structure": {"flat": 2.5}},
            anova={"factors": []},
            optimal={"structure": "flat"},
            significant_factors=["structure"],
            quality_type="larger_is_better",
            total_cost=12.50,
            total_tokens=500000,
            elapsed_seconds=3600.0,
        )
        result = store.get_phase_results("run_001")
        assert result is not None
        assert result["total_cost"] == 12.50
        assert result["total_tokens"] == 500000
        assert result["elapsed_seconds"] == 3600.0

    def test_phase_results_cost_defaults_to_zero(
        self, store: ObservatoryStore
    ) -> None:
        store.create_run("run_001", "taguchi", {})
        store.save_phase_results(
            run_id="run_001",
            main_effects={},
            anova={},
            optimal={},
            significant_factors=[],
            quality_type="larger_is_better",
        )
        result = store.get_phase_results("run_001")
        assert result["total_cost"] == 0.0
        assert result["total_tokens"] == 0
        assert result["elapsed_seconds"] == 0.0
```

Run: `uv run pytest agent-evals/tests/test_observatory_store.py::TestPhaseResultsCost -v`
Expected: FAIL — `save_phase_results` does not accept `total_cost` kwarg.

### Step 2: Implement — add columns + modify methods

**Add columns to `phase_results`** (migration in `_migrate_schema`):

```python
"ALTER TABLE phase_results ADD COLUMN total_cost REAL DEFAULT 0.0",
"ALTER TABLE phase_results ADD COLUMN total_tokens INTEGER DEFAULT 0",
"ALTER TABLE phase_results ADD COLUMN elapsed_seconds REAL DEFAULT 0.0",
```

**Update `save_phase_results()`** — add the 3 new keyword params with defaults of 0:

```python
def save_phase_results(
    self,
    *,
    run_id: str,
    main_effects: dict,
    anova: dict,
    optimal: dict,
    significant_factors: list[str],
    quality_type: str,
    total_cost: float = 0.0,
    total_tokens: int = 0,
    elapsed_seconds: float = 0.0,
) -> None:
```

Update the INSERT to include the 3 new columns.

**Update `get_phase_results()`** — add the 3 fields to the return dict:

```python
return {
    "main_effects": _safe_json("main_effects"),
    "anova": _safe_json("anova"),
    "optimal": _safe_json("optimal"),
    "significant_factors": _safe_json("significant_factors"),
    "quality_type": row["quality_type"],
    "total_cost": row["total_cost"] or 0.0,
    "total_tokens": row["total_tokens"] or 0,
    "elapsed_seconds": row["elapsed_seconds"] or 0.0,
}
```

### Step 3: Wire `save_phase_results()` into pipeline

**Modify:** `agent-evals/src/agent_evals/pipeline.py`

After each phase completes (screening, confirmation, refinement), call save:

```python
# At end of run_screening(), run_confirmation(), run_refinement():
if self._store is not None:
    self._store.save_phase_results(
        run_id=result.run_id,
        main_effects=result.main_effects or {},
        anova=result.anova or {},
        optimal=result.optimal or {},
        significant_factors=result.significant_factors,
        quality_type=self.config.quality_type,
        total_cost=result.total_cost,
        total_tokens=result.total_tokens,
        elapsed_seconds=result.elapsed_seconds,
    )
```

**On resume**, load prior phase cost totals from `get_phase_results()` instead of reconstructing empty PhaseResults.

### Step 4: Run full test suite for store + pipeline

Run: `uv run pytest agent-evals/tests/test_observatory_store.py agent-evals/tests/test_pipeline_integration.py -v`
Expected: PASS

### Step 5: Commit

```bash
git commit -m "feat(observatory): persist phase cost/token totals and wire save_phase_results into pipeline"
```

---

## Task 4: Report Artifacts Persistence

**Purpose:** Persist computed report outputs (KV-cache analysis, hallucination summaries, cross-strategy synthesis) so they're queryable later without re-computation.

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/store.py`
- Modify: `agent-evals/src/agent_evals/reports/cache_analysis.py`
- Modify: `agent-evals/src/agent_evals/reports/cross_strategy_synthesis.py`
- Test: `agent-evals/tests/test_observatory_store.py`

### Step 1: Write failing test

```python
class TestReportArtifacts:
    def test_save_and_get_report_artifact(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", "taguchi", {})
        store.save_report_artifact(
            run_id="run_001",
            artifact_type="cache_analysis",
            data={"flat": {"mean_hit_rate": 0.85, "total_trials": 10}},
        )
        result = store.get_report_artifact("run_001", "cache_analysis")
        assert result is not None
        assert result["data"]["flat"]["mean_hit_rate"] == 0.85

    def test_get_nonexistent_artifact(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", "taguchi", {})
        result = store.get_report_artifact("run_001", "cache_analysis")
        assert result is None

    def test_list_report_artifacts(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", "taguchi", {})
        store.save_report_artifact("run_001", "cache_analysis", {"a": 1})
        store.save_report_artifact("run_001", "hallucination_summary", {"b": 2})
        result = store.list_report_artifacts("run_001")
        assert len(result) == 2
        types = {r["artifact_type"] for r in result}
        assert types == {"cache_analysis", "hallucination_summary"}

    def test_artifact_upsert(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", "taguchi", {})
        store.save_report_artifact("run_001", "cache_analysis", {"v": 1})
        store.save_report_artifact("run_001", "cache_analysis", {"v": 2})
        result = store.get_report_artifact("run_001", "cache_analysis")
        assert result["data"]["v"] == 2
```

Run: `uv run pytest agent-evals/tests/test_observatory_store.py::TestReportArtifacts -v`
Expected: FAIL

### Step 2: Implement schema + store methods

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS report_artifacts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL REFERENCES runs(run_id),
    artifact_type TEXT NOT NULL,
    data_json     TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    UNIQUE(run_id, artifact_type)
);
CREATE INDEX IF NOT EXISTS idx_report_artifacts_run
    ON report_artifacts (run_id);
```

**Store methods:**

```python
def save_report_artifact(
    self, run_id: str, artifact_type: str, data: dict
) -> None:
    """Save or replace a report artifact for a run."""
    now = datetime.now(timezone.utc).isoformat()
    with self._lock, self._connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO report_artifacts "
            "(run_id, artifact_type, data_json, created_at) "
            "VALUES (?, ?, ?, ?)",
            (run_id, artifact_type, json.dumps(data), now),
        )

def get_report_artifact(
    self, run_id: str, artifact_type: str
) -> dict | None:
    """Retrieve a specific report artifact."""
    with self._connect() as conn:
        row = conn.execute(
            "SELECT data_json, created_at FROM report_artifacts "
            "WHERE run_id = ? AND artifact_type = ?",
            (run_id, artifact_type),
        ).fetchone()
    if row is None:
        return None
    return {
        "data": json.loads(row["data_json"]),
        "created_at": row["created_at"],
    }

def list_report_artifacts(self, run_id: str) -> list[dict]:
    """List all report artifacts for a run."""
    with self._connect() as conn:
        rows = conn.execute(
            "SELECT artifact_type, created_at FROM report_artifacts "
            "WHERE run_id = ? ORDER BY artifact_type",
            (run_id,),
        ).fetchall()
    return [dict(r) for r in rows]
```

### Step 3: Wire into report generation

After `build_cache_report()` and `generate_cross_strategy_recommendation()` are called, save their outputs:

```python
# In the report generation path (wherever these are called):
if store is not None:
    store.save_report_artifact(run_id, "cache_analysis", cache_report)
    store.save_report_artifact(run_id, "hallucination_summary", hallucination_data)
    store.save_report_artifact(run_id, "cross_strategy_synthesis", synthesis_report)
```

The exact call sites depend on where reports are generated — look for calls to `build_cache_report()` in the pipeline or CLI. The store reference needs to be threaded through. If reports are generated outside the pipeline (e.g., post-hoc CLI), the wiring happens in the CLI command handler.

### Step 4: Run tests — verify pass

Run: `uv run pytest agent-evals/tests/test_observatory_store.py::TestReportArtifacts -v`
Expected: PASS (4 tests)

### Step 5: Commit

```bash
git commit -m "feat(observatory): add report_artifacts table for persisting computed reports"
```

---

## Task 5: Interaction Effects (2-Way ANOVA)

**Purpose:** Compute and store 2-way interaction effects during refinement phase. The refinement runs full factorial — the data exists but interactions are not computed.

**Files:**
- Modify: `agent-evals/src/agent_evals/taguchi/analysis.py`
- Modify: `agent-evals/src/agent_evals/pipeline.py`
- Modify: `agent-evals/src/agent_evals/observatory/store.py`
- Test: `agent-evals/tests/test_taguchi_analysis.py`
- Test: `agent-evals/tests/test_observatory_store.py`

### Step 1: Write failing test — interaction computation

```python
# In test_taguchi_analysis.py

class TestInteractionEffects:
    def test_compute_two_way_interactions_basic(self) -> None:
        """Two factors with 2 levels each — one interaction pair."""
        from agent_evals.taguchi.analysis import compute_interactions

        # 2x2 full factorial: 4 cells, 2 reps each = 8 observations
        design_rows = [
            {"structure": "flat", "format": "markdown"},
            {"structure": "flat", "format": "yaml"},
            {"structure": "nested", "format": "markdown"},
            {"structure": "nested", "format": "yaml"},
        ]
        # Scores with clear interaction: flat+markdown is best by far
        sn_ratios = [10.0, 4.0, 3.0, 8.0]

        result = compute_interactions(design_rows, sn_ratios)
        assert len(result) == 1  # one pair: (structure, format)
        interaction = result[0]
        assert interaction.factor1 == "format"  # sorted alphabetically
        assert interaction.factor2 == "structure"
        assert interaction.ss > 0
        assert interaction.df == 1  # (2-1)*(2-1)

    def test_no_interactions_single_factor(self) -> None:
        from agent_evals.taguchi.analysis import compute_interactions

        design_rows = [{"structure": "flat"}, {"structure": "nested"}]
        sn_ratios = [10.0, 5.0]
        result = compute_interactions(design_rows, sn_ratios)
        assert result == []

    def test_interactions_three_factors(self) -> None:
        """Three factors → 3 interaction pairs."""
        from agent_evals.taguchi.analysis import compute_interactions

        factors = ["a", "b", "c"]
        # 2^3 = 8 rows
        design_rows = [
            {"a": "0", "b": "0", "c": "0"},
            {"a": "0", "b": "0", "c": "1"},
            {"a": "0", "b": "1", "c": "0"},
            {"a": "0", "b": "1", "c": "1"},
            {"a": "1", "b": "0", "c": "0"},
            {"a": "1", "b": "0", "c": "1"},
            {"a": "1", "b": "1", "c": "0"},
            {"a": "1", "b": "1", "c": "1"},
        ]
        sn_ratios = [5.0, 6.0, 7.0, 3.0, 4.0, 8.0, 2.0, 9.0]
        result = compute_interactions(design_rows, sn_ratios)
        assert len(result) == 3  # C(3,2) = 3 pairs
        pair_names = {(r.factor1, r.factor2) for r in result}
        assert ("a", "b") in pair_names
        assert ("a", "c") in pair_names
        assert ("b", "c") in pair_names
```

Run: `uv run pytest agent-evals/tests/test_taguchi_analysis.py::TestInteractionEffects -v`
Expected: FAIL — `compute_interactions` does not exist.

### Step 2: Implement `compute_interactions()`

**Add dataclass** (in `analysis.py`):

```python
@dataclass
class InteractionEffect:
    factor1: str  # alphabetically first
    factor2: str
    ss: float
    df: int
    ms: float
    f_ratio: float
    p_value: float
```

**Add function** (in `analysis.py`):

```python
def compute_interactions(
    design_rows: list[dict[str, str]],
    sn_ratios: list[float],
) -> list[InteractionEffect]:
    """Compute 2-way interaction effects from full factorial data.

    For each pair of factors (A, B), the interaction SS is:
        SS_AB = SS_cells(A,B) - SS_A - SS_B

    where SS_cells is the between-cells sum of squares for the
    A×B contingency table.
    """
    if len(design_rows) < 2:
        return []

    factors = sorted(design_rows[0].keys())
    if len(factors) < 2:
        return []

    grand_mean = sum(sn_ratios) / len(sn_ratios)

    # Pre-compute main-effect SS for each factor
    main_ss: dict[str, float] = {}
    for factor in factors:
        level_sums: dict[str, list[float]] = defaultdict(list)
        for row, sn in zip(design_rows, sn_ratios):
            level_sums[row[factor]].append(sn)
        ss = sum(
            len(vals) * (sum(vals) / len(vals) - grand_mean) ** 2
            for vals in level_sums.values()
        )
        main_ss[factor] = ss

    # Compute interaction for each factor pair
    results = []
    for i, f1 in enumerate(factors):
        for f2 in factors[i + 1:]:
            # Cell means for f1 × f2
            cell_sums: dict[tuple[str, str], list[float]] = defaultdict(list)
            for row, sn in zip(design_rows, sn_ratios):
                cell_sums[(row[f1], row[f2])].append(sn)

            ss_cells = sum(
                len(vals) * (sum(vals) / len(vals) - grand_mean) ** 2
                for vals in cell_sums.values()
            )
            ss_interaction = ss_cells - main_ss[f1] - main_ss[f2]
            ss_interaction = max(0.0, ss_interaction)  # numerical safety

            levels_f1 = len({row[f1] for row in design_rows})
            levels_f2 = len({row[f2] for row in design_rows})
            df = (levels_f1 - 1) * (levels_f2 - 1)
            ms = ss_interaction / df if df > 0 else 0.0

            # F-ratio uses residual MS from the full model
            # (passed separately or computed here)
            # For now, compute a simple F against within-cell variance
            within_ss = sum(
                sum((v - sum(vals)/len(vals))**2 for v in vals)
                for vals in cell_sums.values()
            )
            within_df = len(sn_ratios) - len(cell_sums)
            ms_within = within_ss / within_df if within_df > 0 else 1.0
            f_ratio = ms / ms_within if ms_within > 0 else 0.0

            from scipy import stats as sp_stats
            p_value = (
                1.0 - sp_stats.f.cdf(f_ratio, df, within_df)
                if df > 0 and within_df > 0 and f_ratio > 0
                else 1.0
            )

            results.append(InteractionEffect(
                factor1=f1, factor2=f2,
                ss=ss_interaction, df=df, ms=ms,
                f_ratio=f_ratio, p_value=p_value,
            ))

    return results
```

### Step 3: Run tests — verify pass

Run: `uv run pytest agent-evals/tests/test_taguchi_analysis.py::TestInteractionEffects -v`
Expected: PASS

### Step 4: Wire into refinement + store

**In `pipeline.py:_analyse_refinement()`**, after `run_anova()`:

```python
# After line ~153 (anova = run_anova(...)):
from agent_evals.taguchi.analysis import compute_interactions

# Build design_rows from the design object
design_rows = [
    {f: row[f] for f in design.factor_names}
    for row in design.rows
]
interactions = compute_interactions(design_rows, sn_ratios)
```

Add `interactions` to the return dict. Then in `save_phase_results`, serialize interactions into the `anova` JSON (or add a separate `interaction_effects TEXT` column to `phase_results`).

**Recommended:** Add column to `phase_results`:

```python
# Migration:
"ALTER TABLE phase_results ADD COLUMN interaction_effects TEXT DEFAULT '[]'",
```

Update `save_phase_results()` to accept `interaction_effects: list[dict] | None = None` and `get_phase_results()` to return it.

### Step 5: Commit

```bash
git commit -m "feat(taguchi): compute 2-way interaction effects in refinement phase"
```

---

## Task 6: Sub-Trial LLM Call Breakdown

**Purpose:** Store per-call metrics for multi-call trials (tool_based strategy makes multiple LLM calls per trial). Currently only the aggregate `llm_calls` count is stored.

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/store.py`
- Modify: `agent-evals/src/agent_evals/observatory/tracker.py`
- Modify: `agent-evals/src/agent_evals/llm/client.py` (minor)
- Modify: `agent-evals/src/agent_evals/runner.py`
- Test: `agent-evals/tests/test_observatory_store.py`

### Step 1: Write failing test

```python
class TestLLMCallDetails:
    def test_save_and_get_llm_calls(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", "taguchi", {})
        trial_id = store.record_trial(**_make_trial_kwargs("run_001"))
        calls = [
            {
                "call_index": 0,
                "prompt_tokens": 80,
                "completion_tokens": 40,
                "cost": 0.0005,
                "api_call_ms": 1200.0,
                "cached_tokens": 60,
                "model": "claude",
                "provider": "anthropic",
            },
            {
                "call_index": 1,
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "cost": 0.0003,
                "api_call_ms": 800.0,
                "cached_tokens": 100,
                "model": "claude",
                "provider": "anthropic",
            },
        ]
        store.save_llm_call_details(trial_id, calls)
        result = store.get_llm_call_details(trial_id)
        assert len(result) == 2
        assert result[0]["call_index"] == 0
        assert result[1]["cached_tokens"] == 100

    def test_get_empty_calls(self, store: ObservatoryStore) -> None:
        store.create_run("run_001", "taguchi", {})
        trial_id = store.record_trial(**_make_trial_kwargs("run_001"))
        result = store.get_llm_call_details(trial_id)
        assert result == []
```

Run: `uv run pytest agent-evals/tests/test_observatory_store.py::TestLLMCallDetails -v`
Expected: FAIL

### Step 2: Implement schema + store methods

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS llm_call_details (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    trial_id          INTEGER NOT NULL REFERENCES trials(trial_id),
    call_index        INTEGER NOT NULL,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    cost              REAL,
    api_call_ms       REAL NOT NULL DEFAULT 0.0,
    cached_tokens     INTEGER NOT NULL DEFAULT 0,
    model             TEXT NOT NULL DEFAULT '',
    provider          TEXT
);
CREATE INDEX IF NOT EXISTS idx_llm_calls_trial
    ON llm_call_details (trial_id);
```

**Store methods:**

```python
def save_llm_call_details(
    self, trial_id: int, calls: list[dict]
) -> None:
    """Save per-call LLM metrics for a trial."""
    with self._lock, self._connect() as conn:
        conn.executemany(
            "INSERT INTO llm_call_details "
            "(trial_id, call_index, prompt_tokens, completion_tokens, "
            "cost, api_call_ms, cached_tokens, model, provider) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    trial_id, c["call_index"],
                    c.get("prompt_tokens", 0),
                    c.get("completion_tokens", 0),
                    c.get("cost"),
                    c.get("api_call_ms", 0.0),
                    c.get("cached_tokens", 0),
                    c.get("model", ""),
                    c.get("provider"),
                )
                for c in calls
            ],
        )

def get_llm_call_details(self, trial_id: int) -> list[dict]:
    """Return per-call details for a trial, ordered by call_index."""
    with self._connect() as conn:
        rows = conn.execute(
            "SELECT call_index, prompt_tokens, completion_tokens, "
            "cost, api_call_ms, cached_tokens, model, provider "
            "FROM llm_call_details WHERE trial_id = ? "
            "ORDER BY call_index",
            (trial_id,),
        ).fetchall()
    return [dict(r) for r in rows]
```

### Step 3: Wire into runner

The runner needs to collect `GenerationResult` objects from each LLM call within a trial and pass them to the tracker. The `GenerationResult` dataclass already contains `prompt_tokens`, `completion_tokens`, `cost`, `api_call_ms`, `cached_tokens`, `provider`.

**Approach:** The `EventTracker.record_trial()` method gains an optional `llm_call_results: list[dict] | None` parameter. When provided, it calls `self._store.save_llm_call_details(trial_id, llm_call_results)` after recording the trial.

The runner already has access to `GenerationResult` — it just needs to accumulate them into a list and pass them through. For single-call trials (most strategies), this is a 1-element list. For `tool_based` strategy with multi-turn, it's N elements.

**Key modification in runner:** Where `GenerationResult` is received, serialize it to a dict and append to a per-trial list. Pass that list when recording the trial.

### Step 4: Run tests — verify pass

Run: `uv run pytest agent-evals/tests/test_observatory_store.py::TestLLMCallDetails -v`
Expected: PASS

### Step 5: Commit

```bash
git commit -m "feat(observatory): add llm_call_details table for sub-trial LLM metrics"
```

---

## Task 7: Dashboard API Endpoints for New Data

**Purpose:** Expose the new tables through the dashboard REST API so the web UI can display factor definitions, task metadata, interaction effects, and report artifacts.

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/web/routes.py`
- Test: `agent-evals/tests/test_observatory_web.py`

### Step 1: Write failing tests for new endpoints

```python
class TestNewEndpoints:
    def test_get_factor_definitions(self, client, _store) -> None:
        _store.create_run("run_001", "taguchi", {})
        _store.save_factor_definitions("run_001", [
            {"factor_name": "structure", "axis_id": 1, "level_index": 0,
             "level_name": "flat", "description": "Flat listing"},
        ])
        resp = client.get("/api/runs/run_001/factors")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["factors"]) == 1

    def test_get_task_metadata(self, client, _store) -> None:
        _store.save_task_metadata([
            {"task_id": "t1", "task_type": "retrieval", "domain": "API",
             "difficulty": "easy", "word_count": 10, "tag_count": 1},
        ])
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        assert len(resp.json()["tasks"]) == 1

    def test_get_report_artifacts(self, client, _store) -> None:
        _store.create_run("run_001", "taguchi", {})
        _store.save_report_artifact("run_001", "cache_analysis", {"hit_rate": 0.9})
        resp = client.get("/api/runs/run_001/reports")
        assert resp.status_code == 200
        assert len(resp.json()["artifacts"]) == 1

    def test_get_report_artifact_by_type(self, client, _store) -> None:
        _store.create_run("run_001", "taguchi", {})
        _store.save_report_artifact("run_001", "cache_analysis", {"hit_rate": 0.9})
        resp = client.get("/api/runs/run_001/reports/cache_analysis")
        assert resp.status_code == 200
        assert resp.json()["data"]["hit_rate"] == 0.9

    def test_get_llm_call_details(self, client, _store) -> None:
        _store.create_run("run_001", "taguchi", {})
        trial_id = _store.record_trial(**_make_trial_kwargs("run_001"))
        _store.save_llm_call_details(trial_id, [
            {"call_index": 0, "prompt_tokens": 100, "completion_tokens": 50,
             "cost": 0.001, "api_call_ms": 500.0, "cached_tokens": 80,
             "model": "claude", "provider": "anthropic"},
        ])
        resp = client.get(f"/api/trials/{trial_id}/calls")
        assert resp.status_code == 200
        assert len(resp.json()["calls"]) == 1

    def test_get_interaction_effects(self, client, _store) -> None:
        _store.create_run("run_001", "taguchi", {}, phase="refinement")
        _store.save_phase_results(
            run_id="run_001",
            main_effects={}, anova={}, optimal={},
            significant_factors=[], quality_type="larger_is_better",
            interaction_effects=[
                {"factor1": "a", "factor2": "b", "ss": 1.5, "df": 1,
                 "ms": 1.5, "f_ratio": 3.0, "p_value": 0.08},
            ],
        )
        resp = client.get("/api/runs/run_001/interactions")
        assert resp.status_code == 200
        assert len(resp.json()["interactions"]) == 1
```

Run: `uv run pytest agent-evals/tests/test_observatory_web.py::TestNewEndpoints -v`
Expected: FAIL — routes don't exist.

### Step 2: Implement route handlers

**Add to `routes.py`:**

```python
@app.get("/api/runs/{run_id}/factors")
async def get_factors(run_id: str):
    factors = store.get_factor_definitions(run_id)
    return {"run_id": run_id, "factors": factors}

@app.get("/api/tasks")
async def get_tasks(task_type: str | None = None):
    tasks = store.get_task_metadata(task_type=task_type)
    return {"tasks": tasks}

@app.get("/api/runs/{run_id}/reports")
async def list_reports(run_id: str):
    artifacts = store.list_report_artifacts(run_id)
    return {"run_id": run_id, "artifacts": artifacts}

@app.get("/api/runs/{run_id}/reports/{artifact_type}")
async def get_report(run_id: str, artifact_type: str):
    result = store.get_report_artifact(run_id, artifact_type)
    if result is None:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return result

@app.get("/api/trials/{trial_id}/calls")
async def get_trial_calls(trial_id: int):
    calls = store.get_llm_call_details(trial_id)
    return {"trial_id": trial_id, "calls": calls}

@app.get("/api/runs/{run_id}/interactions")
async def get_interactions(run_id: str):
    phase = store.get_phase_results(run_id)
    if phase is None:
        return {"run_id": run_id, "interactions": []}
    interactions = phase.get("interaction_effects", [])
    return {"run_id": run_id, "interactions": interactions}
```

### Step 3: Run tests — verify pass

Run: `uv run pytest agent-evals/tests/test_observatory_web.py::TestNewEndpoints -v`
Expected: PASS

### Step 4: Commit

```bash
git commit -m "feat(dashboard): add API endpoints for factors, tasks, reports, calls, interactions"
```

---

## Task 8: Experiment Export/Import

**Purpose:** Export a complete experiment (run + trials + all associated data) as a self-contained JSON bundle. Import back for reproducibility or sharing.

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/export.py`
- Modify: `agent-evals/src/agent_evals/cli.py`
- Test: `agent-evals/tests/test_observatory_export.py`

### Step 1: Write failing test — round-trip export/import

```python
# test_observatory_export.py

import json
from pathlib import Path
from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.export import export_run, import_run


class TestExportImport:
    def test_export_produces_valid_json(self, tmp_path: Path) -> None:
        store = ObservatoryStore(db_path=tmp_path / "obs.db")
        store.create_run("run_001", "taguchi", {"model": "claude"})
        store.record_trial(
            run_id="run_001", task_id="t1", task_type="retrieval",
            variant_name="flat", repetition=1, score=0.85,
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=0.001, latency_seconds=1.5, model="claude",
        )
        out_path = tmp_path / "export.json"
        export_run(store, "run_001", out_path)

        data = json.loads(out_path.read_text())
        assert data["format_version"] == 1
        assert data["run"]["run_id"] == "run_001"
        assert len(data["trials"]) == 1

    def test_round_trip_preserves_data(self, tmp_path: Path) -> None:
        src = ObservatoryStore(db_path=tmp_path / "src.db")
        src.create_run("run_001", "taguchi", {"model": "claude"})
        src.record_trial(
            run_id="run_001", task_id="t1", task_type="retrieval",
            variant_name="flat", repetition=1, score=0.85,
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=0.001, latency_seconds=1.5, model="claude",
        )
        src.save_factor_definitions("run_001", [
            {"factor_name": "structure", "axis_id": 1, "level_index": 0,
             "level_name": "flat", "description": "Flat listing"},
        ])
        src.save_report_artifact("run_001", "cache_analysis", {"hit": 0.9})

        export_path = tmp_path / "bundle.json"
        export_run(src, "run_001", export_path)

        dst = ObservatoryStore(db_path=tmp_path / "dst.db")
        import_run(dst, export_path)

        trials = dst.get_trials("run_001")
        assert len(trials) == 1
        assert trials[0].score == 0.85

        factors = dst.get_factor_definitions("run_001")
        assert len(factors) == 1

        artifact = dst.get_report_artifact("run_001", "cache_analysis")
        assert artifact["data"]["hit"] == 0.9

    def test_import_rejects_duplicate_run(self, tmp_path: Path) -> None:
        store = ObservatoryStore(db_path=tmp_path / "obs.db")
        store.create_run("run_001", "taguchi", {})
        store.record_trial(
            run_id="run_001", task_id="t1", task_type="retrieval",
            variant_name="flat", repetition=1, score=0.85,
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
            cost=0.001, latency_seconds=1.5, model="claude",
        )
        path = tmp_path / "export.json"
        export_run(store, "run_001", path)

        import pytest
        with pytest.raises(ValueError, match="already exists"):
            import_run(store, path)

    def test_import_with_force_replaces(self, tmp_path: Path) -> None:
        store = ObservatoryStore(db_path=tmp_path / "obs.db")
        store.create_run("run_001", "taguchi", {})
        path = tmp_path / "export.json"
        export_run(store, "run_001", path)

        import_run(store, path, force=True)  # Should not raise
        summary = store.get_run_summary("run_001")
        assert summary.run_id == "run_001"
```

Run: `uv run pytest agent-evals/tests/test_observatory_export.py -v`
Expected: FAIL — `export` module does not exist.

### Step 2: Implement `export.py`

```python
"""Export/import experiment bundles as self-contained JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent_evals.observatory.store import ObservatoryStore

FORMAT_VERSION = 1


def export_run(store: ObservatoryStore, run_id: str, path: Path) -> None:
    """Export a run and all associated data to a JSON file."""
    summary = store.get_run_summary(run_id)
    trials = store.get_trials(run_id)
    phase_results = store.get_phase_results(run_id)
    factors = store.get_factor_definitions(run_id)
    artifacts = store.list_report_artifacts(run_id)

    # Fetch full artifact data
    full_artifacts = []
    for art in artifacts:
        data = store.get_report_artifact(run_id, art["artifact_type"])
        if data:
            full_artifacts.append({
                "artifact_type": art["artifact_type"],
                **data,
            })

    # Fetch traces and call details for each trial
    trial_data = []
    for t in trials:
        entry = {
            "task_id": t.task_id,
            "task_type": t.task_type,
            "variant_name": t.variant_name,
            "repetition": t.repetition,
            "score": t.score,
            "prompt_tokens": t.prompt_tokens,
            "completion_tokens": t.completion_tokens,
            "total_tokens": t.total_tokens,
            "cost": t.cost,
            "latency_seconds": t.latency_seconds,
            "model": t.model,
            "source": t.source,
            "error": t.error,
            "oa_row_id": t.oa_row_id,
            "phase": t.phase,
            "context_strategy": t.context_strategy,
            "llm_calls": t.llm_calls,
            "strategy_metadata": t.strategy_metadata,
        }
        trace = store.get_trace(t.trial_id)
        if trace:
            entry["trace"] = trace
        calls = store.get_llm_call_details(t.trial_id)
        if calls:
            entry["call_details"] = calls
        trial_data.append(entry)

    bundle = {
        "format_version": FORMAT_VERSION,
        "run": {
            "run_id": summary.run_id,
            "run_type": summary.run_type,
            "status": summary.status,
            "config": summary.config,
            "created_at": summary.created_at,
            "finished_at": summary.finished_at,
            "pipeline_id": summary.pipeline_id,
            "phase": summary.phase,
        },
        "trials": trial_data,
        "phase_results": phase_results,
        "factor_definitions": factors,
        "report_artifacts": full_artifacts,
    }

    path.write_text(json.dumps(bundle, indent=2))


def import_run(
    store: ObservatoryStore, path: Path, *, force: bool = False
) -> str:
    """Import a run bundle. Returns the run_id.

    Raises ValueError if run already exists (unless force=True).
    """
    bundle = json.loads(path.read_text())
    run = bundle["run"]
    run_id = run["run_id"]

    if force:
        # Delete existing run data (cascade manually since SQLite
        # foreign keys don't cascade by default)
        _delete_run(store, run_id)

    store.create_run(
        run_id=run_id,
        run_type=run["run_type"],
        config=run.get("config", {}),
        phase=run.get("phase"),
        pipeline_id=run.get("pipeline_id"),
    )

    for trial in bundle.get("trials", []):
        trial_id = store.record_trial(
            run_id=run_id,
            task_id=trial["task_id"],
            task_type=trial["task_type"],
            variant_name=trial["variant_name"],
            repetition=trial["repetition"],
            score=trial["score"],
            prompt_tokens=trial["prompt_tokens"],
            completion_tokens=trial["completion_tokens"],
            total_tokens=trial["total_tokens"],
            cost=trial.get("cost"),
            latency_seconds=trial["latency_seconds"],
            model=trial["model"],
            source=trial.get("source", "gold_standard"),
            error=trial.get("error"),
            oa_row_id=trial.get("oa_row_id"),
            phase=trial.get("phase"),
            context_strategy=trial.get("context_strategy", "full_context"),
            llm_calls=trial.get("llm_calls", 1),
            strategy_metadata=trial.get("strategy_metadata"),
        )
        if "trace" in trial:
            store.record_trace(
                trial_id=trial_id,
                prompt_json=trial["trace"]["prompt_json"],
                response_text=trial["trace"]["response_text"],
            )
        if "call_details" in trial:
            store.save_llm_call_details(trial_id, trial["call_details"])

    if bundle.get("factor_definitions"):
        store.save_factor_definitions(run_id, bundle["factor_definitions"])

    if bundle.get("phase_results"):
        pr = bundle["phase_results"]
        store.save_phase_results(
            run_id=run_id,
            main_effects=pr.get("main_effects", {}),
            anova=pr.get("anova", {}),
            optimal=pr.get("optimal", {}),
            significant_factors=pr.get("significant_factors", []),
            quality_type=pr.get("quality_type", "larger_is_better"),
            total_cost=pr.get("total_cost", 0.0),
            total_tokens=pr.get("total_tokens", 0),
            elapsed_seconds=pr.get("elapsed_seconds", 0.0),
            interaction_effects=pr.get("interaction_effects"),
        )

    for art in bundle.get("report_artifacts", []):
        store.save_report_artifact(
            run_id, art["artifact_type"], art["data"]
        )

    return run_id


def _delete_run(store: ObservatoryStore, run_id: str) -> None:
    """Delete all data for a run (for force-import)."""
    with store._lock, store._connect() as conn:
        # Order matters: children first
        conn.execute(
            "DELETE FROM llm_call_details WHERE trial_id IN "
            "(SELECT trial_id FROM trials WHERE run_id = ?)", (run_id,)
        )
        conn.execute(
            "DELETE FROM trial_traces WHERE trial_id IN "
            "(SELECT trial_id FROM trials WHERE run_id = ?)", (run_id,)
        )
        conn.execute("DELETE FROM trials WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM phase_results WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM factor_definitions WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM report_artifacts WHERE run_id = ?", (run_id,))
        conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
```

### Step 3: Add CLI subcommands

**Modify:** `agent-evals/src/agent_evals/cli.py`

Add `export` and `import` subcommands:

```python
# In argument parser setup:
export_parser = subparsers.add_parser("export", help="Export a run to JSON")
export_parser.add_argument("run_id", help="Run ID to export")
export_parser.add_argument("-o", "--output", required=True, help="Output file path")
export_parser.add_argument("--db", help="Observatory DB path")

import_parser = subparsers.add_parser("import", help="Import a run from JSON")
import_parser.add_argument("file", help="JSON bundle file to import")
import_parser.add_argument("--db", help="Observatory DB path")
import_parser.add_argument("--force", action="store_true", help="Replace existing run")
```

**Handler functions:**

```python
def _run_export(args):
    store = ObservatoryStore(db_path=Path(args.db or "~/.observatory/observatory.db").expanduser())
    from agent_evals.observatory.export import export_run
    export_run(store, args.run_id, Path(args.output))
    print(f"Exported run {args.run_id} to {args.output}")
    return 0

def _run_import(args):
    store = ObservatoryStore(db_path=Path(args.db or "~/.observatory/observatory.db").expanduser())
    from agent_evals.observatory.export import import_run
    run_id = import_run(store, Path(args.file), force=args.force)
    print(f"Imported run {run_id}")
    return 0
```

### Step 4: Run tests — verify pass

Run: `uv run pytest agent-evals/tests/test_observatory_export.py -v`
Expected: PASS (4 tests)

### Step 5: Commit

```bash
git commit -m "feat(observatory): add experiment export/import with CLI subcommands"
```

---

## Execution Notes

### Parallelisation Strategy

Tasks 1-6 modify `store.py` but touch **different methods and schema sections**. To avoid merge conflicts:

- Each agent adds its table to `_SCHEMA` at the end
- Each agent adds its migrations to the end of the `migrations` list
- Each agent adds its index to the end of the `indexes` list
- Each agent adds its store methods at the end of the class
- **Task 7** (dashboard routes) runs after 1-6 merge since it calls their methods
- **Task 8** (export/import) runs last since it calls all store methods

### Test Commands

```bash
# Per-task verification:
uv run pytest agent-evals/tests/test_observatory_store.py -v -k "TestFactorDefinitions"
uv run pytest agent-evals/tests/test_observatory_store.py -v -k "TestTaskMetadata"
uv run pytest agent-evals/tests/test_observatory_store.py -v -k "TestPhaseResultsCost"
uv run pytest agent-evals/tests/test_observatory_store.py -v -k "TestReportArtifacts"
uv run pytest agent-evals/tests/test_taguchi_analysis.py -v -k "TestInteractionEffects"
uv run pytest agent-evals/tests/test_observatory_store.py -v -k "TestLLMCallDetails"
uv run pytest agent-evals/tests/test_observatory_web.py -v -k "TestNewEndpoints"
uv run pytest agent-evals/tests/test_observatory_export.py -v

# Full suite after all tasks:
uv run pytest --tb=short -q
```

### Beads to Create

Before starting, create beads for each task:
- "Add factor_definitions table with axis/level semantics"
- "Add task_metadata table for task-level attributes"
- "Persist phase cost/token totals in phase_results"
- "Add report_artifacts table for persisting computed reports"
- "Compute and store 2-way interaction effects in refinement"
- "Add llm_call_details table for sub-trial metrics"
- "Add dashboard API endpoints for new observatory tables"
- "Add experiment export/import with CLI subcommands"
