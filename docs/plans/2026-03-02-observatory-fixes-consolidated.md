# Observatory & Agent-Evals Fixes — Consolidated Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all 44 open issues in the Observatory and agent-evals system — scoring correctness, infrastructure stability, new frontend/backend bugs, variant format correctness, evaluation framework bugs, and UX polish.

**Architecture:** Issues are organized into 10 sprints by priority. Scorer fixes are highest-priority because they invalidate current evaluation results. Infrastructure fixes prevent future data loss. All fixes follow TDD: write a failing test first, then implement the minimum fix, then commit.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, React/TypeScript, Chart.js, TanStack Query v5, rapidfuzz (new dep), PyYAML, pytest, Vitest

**Reference Documents:**
- Issues register: `docs/plans/2026-03-02-observatory-known-issues.md`
- Fix strategies: `docs/plans/2026-03-02-fix-strategies.md`
- Test suite: `agent-evals/tests/` (flat — no subdirectories)

---

## Task 0: TaskDefinition Pattern (Reference — No Code Change)

> **Read this before Sprint 1.** All task type tests must use this pattern.

All `EvalTask` subclasses (`CompositionalTask`, `NegativeTask`, `DisambiguationTask`, etc.) accept a single `TaskDefinition` object — NOT keyword arguments.

```python
from agent_evals.tasks.base import TaskDefinition
from agent_evals.tasks.compositional import CompositionalTask

defn = TaskDefinition(
    task_id="compositional_001",    # Must match pattern: ^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*_\d+$
    type="compositional",
    question="What is the version?",
    domain="framework_api",         # Must be one of VALID_DOMAINS — use "framework_api" in tests
    difficulty="easy",
    metadata={"sub_tasks": [{"question": "Q", "expected_answer": "Python 3.11"}]},
)
task = CompositionalTask(defn)
```

The `metadata` dict carries task-type-specific fields. Check existing tests in `agent-evals/tests/test_task_*.py` for the exact metadata structure each type expects.

**`ObservatoryStore` pattern:**
```python
# Tests use a real temp path (not ":memory:")
def test_something(tmp_path):
    store = ObservatoryStore(db_path=tmp_path / "test.db")
    store.create_run("run1", "full", {}, phase="screening")  # config is dict, phase/pipeline_id are keyword-only
```

**`_run_wrapper` signature:**
```python
def _run_wrapper(self, run_id: str, request: StartRunRequest) -> None:
# Tests call: manager._run_wrapper("run1", request=MagicMock())
```

**`RunManager` constructor requires both `store` and `tracker`:**
```python
from agent_evals.observatory.tracker import EventTracker
# In tests — always construct both:
store = ObservatoryStore(db_path=tmp_path / "test.db")
tracker = EventTracker(store=store)          # real tracker
manager = RunManager(store=store, tracker=tracker)
# Or mock it:
tracker = MagicMock(spec=EventTracker)
manager = RunManager(store=store, tracker=tracker)
```

**`start_run` signature — no `run_id` parameter:**
```python
# start_run generates run_id internally — do NOT pass run_id
manager.start_run(request=StartRunRequest(model="openrouter/anthropic/claude-haiku-4-5-20251001", task_limit=1))
```

**`_parse_json_or_list` is a module-level function:**
```python
from agent_evals.tasks.agentic import _parse_json_or_list
result = _parse_json_or_list("test_foo test_bar")
```

---

## IMMEDIATE — Before Any Sprint

These are one-time database state corrections. Do this before writing any code:

```bash
# Mark 93.1%-complete stalled run as failed (I1)
curl -X POST http://localhost:8765/api/runs/9b51360baeb5/finish \
  -H "Content-Type: application/json" \
  -d '{"status": "failed"}'

# Mark 6-day-old stuck run as failed (I2)
curl -X POST http://localhost:8765/api/runs/b1ca3c026030/finish \
  -H "Content-Type: application/json" \
  -d '{"status": "failed"}'

# Fix null finished_at on already-failed run ba37a9ac39d6 (I5 one-time correction)
curl -X POST http://localhost:8765/api/runs/ba37a9ac39d6/finish \
  -H "Content-Type: application/json" \
  -d '{"status": "failed"}'

# Verify all three
curl http://localhost:8765/api/runs | jq '.runs[] | select(.run_id | startswith("9b5") or startswith("b1c") or startswith("ba3")) | {run_id, status, finished_at}'
```

Expected: all three show `"status": "failed"` and a non-null `finished_at`.

---

## Sprint 1 — Scoring System: Compositional (Highest Impact)

> **Why first:** Compositional scorer has 70% false-zero rate (818 of 1,170 trials). Fixes S7 and S1 together — S7 first since it's a prerequisite for S1 to reach 1.0.

---

### Task 1: Fix compositional denominator (S7 — TRIVIAL)

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/compositional.py:85-95`
- Test: `agent-evals/tests/test_task_compositional.py` (add to existing)

> **Context:** `task_id` must match `^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*_\d+$`, use `domain="framework_api"`.
> ```python
> from agent_evals.tasks.base import TaskDefinition
> from agent_evals.tasks.compositional import CompositionalTask
> defn = TaskDefinition(task_id="compositional_001", type="compositional", question="Q?", domain="framework_api", difficulty="easy", metadata={...})
> task = CompositionalTask(defn)
> ```

**Step 1 [RED]:** Write the failing test

```python
def test_empty_sub_task_excluded_from_denominator():
    """Max achievable score must be 1.0 when a sub-task has empty expected_answer."""
    defn = TaskDefinition(
        task_id="compositional_001", type="compositional", question="Q",
        domain="framework_api", difficulty="easy",
        metadata={"sub_tasks": [
            {"question": "A", "expected_answer": "Python 3.11"},
            {"question": "B", "expected_answer": ""},   # empty — must not count
        ]},
    )
    task = CompositionalTask(defn)
    score = task.score_response("The version is Python 3.11 and nothing else.")
    assert score == 1.0, f"Expected 1.0 (empty sub-task excluded), got {score}"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing
uv run pytest agent-evals/tests/test_task_compositional.py::test_empty_sub_task_excluded_from_denominator -v
```
Expected: `FAILED — AssertionError: 0.5 != 1.0`

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

In `compositional.py`, find the scoring loop and change:

```python
# BEFORE
matched = 0
for sub_task in self.sub_tasks:
    expected: str = sub_task.get("expected_answer", "")
    if not expected:
        continue
    if expected.lower() in response_lower:
        matched += 1
score = matched / len(self.sub_tasks)

# AFTER
matched = 0
scored_count = 0
for sub_task in self.sub_tasks:
    expected: str = sub_task.get("expected_answer", "")
    if not expected:
        continue
    scored_count += 1
    if expected.lower() in response_lower:
        matched += 1
if scored_count == 0:
    return 1.0
score = matched / scored_count
```

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_task_compositional.py -v
```
Expected: all PASS

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Is `scored_count == 0` the right edge case, or should an all-empty task return 0.0 instead?
- Check: Is the float accumulation for `matched` consistent between this fix and the fuzzy matching added in Task 3?
- Check: Are score values clamped to [0.0, 1.0]? The `matched / scored_count` formula is safe but verify it stays bounded when Task 3 fuzzy partial scores are mixed in.
- Check: Is the `return 1.0` for all-empty tasks backward-compatible — any other caller that depends on a zero score for empty sub-tasks?
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works against real compositional task data

```bash
uv run python -c "
from agent_evals.fixtures import load_sample_doc_tree
from agent_evals.tasks.loader import load_tasks_from_dir
tasks = [t for t in load_tasks_from_dir('agent-evals/gold_standard/') if t.definition.type == 'compositional'][:5]
print(f'Loaded {len(tasks)} compositional tasks')
from agent_evals.variants.flat import Flat
v = Flat()
doc_tree = load_sample_doc_tree()
v.setup(doc_tree)
rendered = v.render(doc_tree)
for task in tasks:
    score = task.score_response(rendered)
    print(f'  {task.definition.task_id}: score={score:.3f}')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/tasks/compositional.py agent-evals/tests/test_task_compositional.py
git commit -m "fix(scoring): exclude empty sub-tasks from compositional denominator (S7)"
```

---

### Task 2: Add rapidfuzz dependency (S1 prerequisite)

> This is a dependency task — no logic test required. Verify with a smoke test.

**Files:**
- Modify: `agent-evals/pyproject.toml`

**Step 1 [GREEN]:** Write the minimal implementation to make the test pass

In `agent-evals/pyproject.toml` under `[project] dependencies`:
```toml
"rapidfuzz>=3.0",
```

**Step 2 [GREEN]:** Run to confirm tests pass

```bash
# Run from workspace root, not from agent-evals/
cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing
uv sync
```

**Step 3 [GREEN]:** Smoke test

```bash
uv run python -c "from rapidfuzz import fuzz, utils; print('rapidfuzz OK')"
```
Expected: `rapidfuzz OK`

**Step 4 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Is `rapidfuzz>=3.0` the right version pin? Verify the API (`fuzz.partial_ratio`, `utils.default_process`) exists in 3.x vs 2.x.
- Check: Is the dependency placed in the right section of `pyproject.toml` (runtime `[project] dependencies`, not dev-only)?
- Check: Will `uv.lock` be committed? It should be, to ensure reproducible installs.
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 5 [VERIFY]:** Confirm the import works in the actual eval context

```bash
uv run python -c "
from rapidfuzz import fuzz, utils as fuzz_utils
test_score = fuzz.partial_ratio('Python 3.11', 'The runtime uses Python version 3.11', processor=fuzz_utils.default_process, score_cutoff=80.0)
print(f'rapidfuzz OK — sample score={test_score}')
"
```
Expected: prints `rapidfuzz OK — sample score=` with a non-zero value.

**Step 6: Commit**

```bash
git add agent-evals/pyproject.toml uv.lock
git commit -m "feat(deps): add rapidfuzz>=3.0 for fuzzy answer matching (S1 prerequisite)"
```

---

### Task 3: Replace compositional substring match with fuzzy matching (S1 — HIGH)

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/compositional.py`
- Test: `agent-evals/tests/test_task_compositional.py`

> **Context:** `task_id` must match `^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*_\d+$`, use `domain="framework_api"`.
> ```python
> from agent_evals.tasks.base import TaskDefinition
> from agent_evals.tasks.compositional import CompositionalTask
> defn = TaskDefinition(task_id="compositional_002", type="compositional", question="Q?", domain="framework_api", difficulty="easy", metadata={...})
> task = CompositionalTask(defn)
> ```

**Step 1 [RED]:** Write the failing tests

```python
def test_fuzzy_match_catches_paraphrase():
    """'Python version 3.11' must score > 0 for expected 'Python 3.11'."""
    defn = TaskDefinition(
        task_id="compositional_002", type="compositional", question="Q",
        domain="framework_api", difficulty="easy",
        metadata={"sub_tasks": [{"question": "version?", "expected_answer": "Python 3.11"}]},
    )
    task = CompositionalTask(defn)
    score = task.score_response("The runtime uses Python version 3.11 as its base.")
    assert score > 0.0, f"Expected > 0.0 for paraphrase, got {score}"

def test_exact_match_still_scores_one():
    defn = TaskDefinition(
        task_id="compositional_003", type="compositional", question="Q",
        domain="framework_api", difficulty="easy",
        metadata={"sub_tasks": [{"question": "version?", "expected_answer": "Python 3.11"}]},
    )
    task = CompositionalTask(defn)
    assert task.score_response("Python 3.11 is used.") == 1.0
```

**Step 2 [RED]:** Run to confirm the paraphrase test fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_task_compositional.py::test_fuzzy_match_catches_paraphrase -v
```
Expected: `FAILED — assert 0.0 > 0.0`

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

Add these imports at the top of `compositional.py`:
```python
from rapidfuzz import fuzz, utils as fuzz_utils
from agent_evals.tasks._utils import extract_keywords
```

Add the helper method to `CompositionalTask`:
```python
def _score_sub_answer(self, expected: str, response_lower: str) -> float:
    """Score one sub-answer using exact containment, then fuzzy keyword coverage."""
    if expected.lower() in response_lower:
        return 1.0
    keywords = extract_keywords(expected)
    if not keywords:
        return 0.0
    matched = 0
    for kw in keywords:
        score = fuzz.partial_ratio(
            kw.lower(), response_lower,
            processor=fuzz_utils.default_process,
            score_cutoff=80.0,
        )
        if score > 0:
            matched += 1
    return matched / len(keywords)
```

In the scoring loop from Task 1, replace the binary check with:
```python
matched += self._score_sub_answer(expected, response_lower)
```
(Note: `matched` is now a float accumulator.)

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_task_compositional.py -v
```
Expected: all PASS

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Is the `score_cutoff=80.0` threshold appropriate? Too low means false positives (unrelated words match); too high means the paraphrase improvement is negligible.
- Check: Are score values from `_score_sub_answer` always in [0.0, 1.0]? The keyword coverage fraction is naturally bounded, but verify with mixed exact+fuzzy cases.
- Check: Is the `extract_keywords` function filtering stop words correctly? Short expected answers (1-2 words) may extract zero keywords and return 0.0 unexpectedly.
- Check: Is `matched` being used correctly as a float accumulator after this change — does the denominator `scored_count` (from Task 1) still work with float `matched` values?
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works against real compositional task data

```bash
uv run python -c "
from agent_evals.fixtures import load_sample_doc_tree
from agent_evals.tasks.loader import load_tasks_from_dir
tasks = [t for t in load_tasks_from_dir('agent-evals/gold_standard/') if t.definition.type == 'compositional'][:5]
print(f'Loaded {len(tasks)} compositional tasks')
from agent_evals.variants.flat import Flat
v = Flat()
doc_tree = load_sample_doc_tree()
v.setup(doc_tree)
rendered = v.render(doc_tree)
for task in tasks:
    score = task.score_response(rendered)
    print(f'  {task.definition.task_id}: score={score:.3f}')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/tasks/compositional.py agent-evals/tests/test_task_compositional.py
git commit -m "fix(scoring): replace substring with rapidfuzz fuzzy matching in compositional (S1)"
```

---

## Sprint 2 — Scoring System: Negative Scorer (S2 + S8)

---

### Task 4: Remove false-positive abstention phrases (S8 — MEDIUM)

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/negative.py:64-65`
- Test: `agent-evals/tests/test_task_negative.py`

> **Context:** `task_id` must match `^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*_\d+$`, use `domain="framework_api"`.
> ```python
> from agent_evals.tasks.base import TaskDefinition
> from agent_evals.tasks.negative import NegativeTask
> defn = TaskDefinition(task_id="negative_001", type="negative", question="Q?", domain="framework_api", difficulty="easy", metadata={})
> task = NegativeTask(defn)
> ```

**Step 1 [RED]:** Write the failing test

```python
def test_confident_answer_not_scored_as_abstention():
    """'Based on the available documentation, the answer is X' must NOT score 1.0."""
    defn = TaskDefinition(
        task_id="negative_001", type="negative", question="What is the version?",
        domain="framework_api", difficulty="easy", metadata={},
    )
    task = NegativeTask(defn)
    score = task.score_response(
        "Based on the available documentation, the answer is Python 3.11."
    )
    assert score < 1.0, f"False positive — confident answer scored {score}"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_task_negative.py::test_confident_answer_not_scored_as_abstention -v
```
Expected: `FAILED — 1.0 is not < 1.0`

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

In `negative.py`, find `_ABSTENTION_PHRASES` (around lines 22-66) and remove exactly these two entries:
- `"based on the available"` (line 64)
- `"the provided documentation"` (line 65)

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_task_negative.py -v
```
Expected: all PASS

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Are there other phrases in `_ABSTENTION_PHRASES` that also appear in confident answers (similar false-positive pattern to the two removed)?
- Check: Is removing these phrases backward-compatible — are there existing tests that depend on either phrase triggering an abstention score?
- Check: The count goes from 37 to 35 phrases — does any comment or docstring in the file say "37 phrases" that now needs updating?
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works against real negative task data

```bash
uv run python -c "
from agent_evals.fixtures import load_sample_doc_tree
from agent_evals.tasks.loader import load_tasks_from_dir
tasks = [t for t in load_tasks_from_dir('agent-evals/gold_standard/') if t.definition.type == 'negative'][:5]
print(f'Loaded {len(tasks)} negative tasks')
from agent_evals.variants.flat import Flat
v = Flat()
doc_tree = load_sample_doc_tree()
v.setup(doc_tree)
rendered = v.render(doc_tree)
for task in tasks:
    score = task.score_response(rendered)
    print(f'  {task.definition.task_id}: score={score:.3f}')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/tasks/negative.py agent-evals/tests/test_task_negative.py
git commit -m "fix(scoring): remove false-positive abstention phrases from negative scorer (S8)"
```

---

### Task 5: Graduate negative scorer to rubric scoring (S2 — MEDIUM)

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/negative.py:118-135`
- Test: `agent-evals/tests/test_task_negative.py`

> **Context:** `task_id` must match `^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*_\d+$`, use `domain="framework_api"`.
> ```python
> from agent_evals.tasks.base import TaskDefinition
> from agent_evals.tasks.negative import NegativeTask
> defn = TaskDefinition(task_id="negative_002", type="negative", question="Q?", domain="framework_api", difficulty="easy", metadata={})
> task = NegativeTask(defn)
> ```

**Step 1 [RED]:** Write the failing tests

```python
def test_hedge_with_caveat_scores_exactly_0_7():
    """'I'm not certain...' must score exactly 0.7 (hedge tier)."""
    defn = TaskDefinition(
        task_id="negative_002", type="negative", question="Q",
        domain="framework_api", difficulty="easy", metadata={},
    )
    task = NegativeTask(defn)
    score = task.score_response("I'm not certain about this, but it might be X.")
    assert score == 0.7, f"Expected 0.7 for hedge tier, got {score}"

def test_confident_hallucination_scores_zero():
    defn = TaskDefinition(
        task_id="negative_003", type="negative", question="Q",
        domain="framework_api", difficulty="easy", metadata={},
    )
    task = NegativeTask(defn)
    assert task.score_response("The answer is definitely 42.") == 0.0

def test_firm_refusal_scores_one():
    defn = TaskDefinition(
        task_id="negative_004", type="negative", question="Q",
        domain="framework_api", difficulty="easy", metadata={},
    )
    task = NegativeTask(defn)
    assert task.score_response("I cannot answer — no information available.") == 1.0
```

**Step 2 [RED]:** Run to confirm hedge test fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_task_negative.py::test_hedge_with_caveat_scores_exactly_0_7 -v
```
Expected: `FAILED — 0.0 != 0.7`

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

> **IMPORTANT — delete the pre-existing `test_score_is_binary` test first.** That test asserts scores are always 0.0 or 1.0, which directly contradicts the tiered rubric. It is at line ~198 of `test_task_negative.py`. Delete it before implementing the rubric, or your GREEN step will be blocked by a conflicting passing test turning into a failing test.

Replace the binary scoring logic with categorized tiers. `_FIRM_REFUSAL` must contain ALL 35 phrases from the original `_ABSTENTION_PHRASES` **minus the two removed by Task 4** (37 original − 2 = 35). The complete list is shown below — copy it verbatim:

```python
# Replace _ABSTENTION_PHRASES with three categorized frozensets:
# (Task 4 already removed "based on the available" and "the provided documentation")
_FIRM_REFUSAL: frozenset[str] = frozenset([
    # -- Explicit refusal / inability --
    "cannot be determined",
    "cannot answer",
    "cannot determine",
    "unable to find",
    "unable to determine",
    "unanswerable",
    # -- "don't / do not" variants --
    "don't know",
    "do not know",
    "don't have enough",
    "do not have enough",
    "doesn't contain",
    "does not contain",
    "doesn't include",
    "does not include",
    # -- Information absence --
    "no information",
    "no relevant information",
    "no mention",
    "no data",
    "not available",
    "not found",
    "not mentioned",
    "not provided",
    "not specified",
    "not documented",
    "not covered",
    "not addressed",
    "not explicitly stated",
    # -- Search / lookup failure --
    "couldn't find",
    "could not find",
    "not in the documentation",
    "the documentation does not specify",
    # -- Uncertainty hedging --
    "i'm not sure",
    "i am not sure",
    "not clear from",
    "insufficient information",
])
_HEDGE_WITH_CAVEAT: frozenset[str] = frozenset([
    "i'm not certain", "i cannot confirm", "it's unclear",
    "the documentation doesn't explicitly",
])
_ANSWER_WITH_DISCLAIMER: frozenset[str] = frozenset([
    "based on limited information", "this may not be accurate",
    "i'm making an assumption",
])

def score_response(self, response: str) -> float:
    response_lower = response.lower()
    if any(p in response_lower for p in _FIRM_REFUSAL):
        return 1.0
    if any(p in response_lower for p in _HEDGE_WITH_CAVEAT):
        return 0.7
    if any(p in response_lower for p in _ANSWER_WITH_DISCLAIMER):
        return 0.3
    return 0.0
```

**Step 4 [GREEN]:** Run all negative tests

```bash
uv run pytest agent-evals/tests/test_task_negative.py -v
```
Expected: all PASS

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Are the three tier boundaries (1.0 / 0.7 / 0.3 / 0.0) semantically reasonable? A response with both `_FIRM_REFUSAL` and `_HEDGE_WITH_CAVEAT` phrases returns 1.0 (priority order) — is this correct?
- Check: Are the phrase sets stored as module-level `frozenset` (not inside `score_response`)? Frozensets should be defined once at module scope for performance.
- Check: Is there a risk of phrase overlap between the three tiers? Scan for any phrase that appears in more than one set.
- Check: The 0.3 tier (`_ANSWER_WITH_DISCLAIMER`) is new — does it have sufficient test coverage (at least one test per phrase category)?
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works against real negative task data

```bash
uv run python -c "
from agent_evals.fixtures import load_sample_doc_tree
from agent_evals.tasks.loader import load_tasks_from_dir
tasks = [t for t in load_tasks_from_dir('agent-evals/gold_standard/') if t.definition.type == 'negative'][:5]
print(f'Loaded {len(tasks)} negative tasks')
from agent_evals.variants.flat import Flat
v = Flat()
doc_tree = load_sample_doc_tree()
v.setup(doc_tree)
rendered = v.render(doc_tree)
for task in tasks:
    score = task.score_response(rendered)
    print(f'  {task.definition.task_id}: score={score:.3f}')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/tasks/negative.py agent-evals/tests/test_task_negative.py
git commit -m "fix(scoring): graduate negative scorer to tiered rubric with partial credit (S2)"
```

---

## Sprint 3 — Scoring System: Remaining Scorers (S3–S5, S9–S11)

---

### Task 6: Disambiguation — continuous scoring, preserve label path (S3 — MEDIUM)

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/disambiguation.py:88-105`
- Test: `agent-evals/tests/test_task_disambiguation.py`

> **Context:** `task_id` must match `^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*_\d+$`, use `domain="framework_api"`.
> ```python
> from agent_evals.tasks.base import TaskDefinition
> from agent_evals.tasks.disambiguation import DisambiguationTask
> defn = TaskDefinition(task_id="disambiguation_001", type="disambiguation", question="Q?", domain="framework_api", difficulty="easy", metadata={...})
> task = DisambiguationTask(defn)
> ```

**Step 1 [RED]:** Write the failing test

```python
def test_49_percent_keyword_coverage_not_binary():
    """Coverage below 50% must produce a partial score, not 0.0."""
    # 1 of 4 keywords matched = 25% coverage — old cliff gives 0.0
    defn = TaskDefinition(
        task_id="disambiguation_001", type="disambiguation", question="Q",
        domain="framework_api", difficulty="easy",
        metadata={"expected_interpretation": "alpha", "interpretations": [
            {"label": "alpha", "answer": "alpha beta gamma delta"}
        ]},
    )
    task = DisambiguationTask(defn)
    score = task.score_response("Only alpha is mentioned here.")
    assert 0.0 < score < 1.0, f"Expected partial score for 25% coverage, got {score}"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_task_disambiguation.py::test_49_percent_keyword_coverage_not_binary -v
```

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass — replace cliff threshold, preserve label_score path

Read the existing `score_response` implementation in `disambiguation.py` carefully. Keep the `label_score` path unchanged. Only replace the `answer_score` cliff:

```python
# REPLACE only the answer_score block (the part with `if coverage >= 0.5: answer_score = 1.0`)
# with continuous coverage:
answer_score = 0.0
if expected_answer:
    keywords = extract_keywords(expected_answer)
    if keywords:
        hits = sum(1 for kw in keywords if kw.lower() in response_lower)
        coverage = hits / len(keywords)
        # Continuous score instead of cliff
        ambiguity_bonus = 0.1 if any(
            p in response_lower
            for p in ["ambiguous", "multiple interpretations", "could mean"]
        ) else 0.0
        answer_score = min(1.0, coverage + ambiguity_bonus)

# label_score path — DO NOT CHANGE; keep as-is from existing code
# The final return `max(answer_score, label_score)` must be preserved
```

**Step 4 [GREEN]:** Run all disambiguation tests

```bash
uv run pytest agent-evals/tests/test_task_disambiguation.py -v
```
Expected: mostly PASS — **but `test_partial_keyword_coverage_below_threshold` will fail.** That test expects `score == 0.0` for 1/3 keyword coverage, which the old cliff produced. With continuous scoring, 1/3 coverage = 0.33. Update that test's assertion to:
```python
assert score == pytest.approx(1/3, abs=0.01)
```
Then re-run and confirm all PASS.

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Is `min(1.0, coverage + ambiguity_bonus)` the right formula? The bonus is 0.1 — verify a full-coverage response (1.0) with an ambiguity phrase doesn't get clamped awkwardly.
- Check: Is the `label_score` path completely unchanged? The `max(answer_score, label_score)` combinator must remain intact — verify by adding a test that exercises the label path.
- Check: Are error messages in the assertion helpers clear enough to diagnose what failed if keyword extraction returns an unexpected set?
- Check: Is `extract_keywords` imported at the top of `disambiguation.py` (not inside the method)?
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works against real disambiguation task data

```bash
uv run python -c "
from agent_evals.fixtures import load_sample_doc_tree
from agent_evals.tasks.loader import load_tasks_from_dir
tasks = [t for t in load_tasks_from_dir('agent-evals/gold_standard/') if t.definition.type == 'disambiguation'][:5]
print(f'Loaded {len(tasks)} disambiguation tasks')
from agent_evals.variants.flat import Flat
v = Flat()
doc_tree = load_sample_doc_tree()
v.setup(doc_tree)
rendered = v.render(doc_tree)
for task in tasks:
    score = task.score_response(rendered)
    print(f'  {task.definition.task_id}: score={score:.3f}')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/tasks/disambiguation.py agent-evals/tests/test_task_disambiguation.py
git commit -m "fix(scoring): replace cliff threshold with continuous coverage in disambiguation (S3)"
```

---

### Task 7: Multi-hop — require 30% keyword coverage per step (S4 — MEDIUM)

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/multi_hop.py:105`
- Test: `agent-evals/tests/test_task_multi_hop.py`

> **Context:** `task_id` must match `^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*_\d+$`, use `domain="framework_api"`.
> ```python
> from agent_evals.tasks.base import TaskDefinition
> from agent_evals.tasks.multi_hop import MultiHopTask
> defn = TaskDefinition(task_id="multi_hop_001", type="multi_hop", question="Q?", domain="framework_api", difficulty="easy", metadata={...})
> task = MultiHopTask(defn)
> ```

**Step 1 [RED]:** Write the failing test

```python
def test_single_keyword_hit_does_not_pass_step():
    """A step with 5 keywords must not pass on a single keyword match."""
    defn = TaskDefinition(
        task_id="multi_hop_001", type="multi_hop", question="Q",
        domain="framework_api", difficulty="easy",
        metadata={"reasoning_chain": [
            {"expected": "alpha beta gamma delta epsilon"}
        ]},
    )
    task = MultiHopTask(defn)
    # Only "alpha" appears — 1/5 = 20% < 30% threshold
    score = task.score_response("alpha is mentioned but nothing else.")
    assert score == 0.0, f"Expected 0.0 for 20% coverage, got {score}"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_task_multi_hop.py::test_single_keyword_hit_does_not_pass_step -v
```
Expected: `FAILED — currently scores 1.0`

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

```python
STEP_COVERAGE_THRESHOLD = 0.30

# Replace the `any()` check at line 105:
matched = sum(1 for kw in keywords if kw.lower() in response_lower)
coverage = matched / len(keywords)
step_scores.append(coverage if coverage >= STEP_COVERAGE_THRESHOLD else 0.0)
```

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_task_multi_hop.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Is `STEP_COVERAGE_THRESHOLD = 0.30` a named constant at module level (not a magic number inside the method)?
- Check: Does the step score cliff (0.0 below threshold, continuous above) produce sensible scores at the boundary? A step with exactly 30% coverage gets its raw coverage score (0.3), not 1.0 — is this the intended behavior?
- Check: What happens when a step has 0 keywords (empty `expected` string)? Does the code handle `len(keywords) == 0` gracefully without a ZeroDivisionError?
- Check: Are existing tests for the multi-hop scorer still valid, or do any need updating to match the 30% threshold behavior?
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works against real multi_hop task data

```bash
uv run python -c "
from agent_evals.fixtures import load_sample_doc_tree
from agent_evals.tasks.loader import load_tasks_from_dir
tasks = [t for t in load_tasks_from_dir('agent-evals/gold_standard/') if t.definition.type == 'multi_hop'][:5]
print(f'Loaded {len(tasks)} multi_hop tasks')
from agent_evals.variants.flat import Flat
v = Flat()
doc_tree = load_sample_doc_tree()
v.setup(doc_tree)
rendered = v.render(doc_tree)
for task in tasks:
    score = task.score_response(rendered)
    print(f'  {task.definition.task_id}: score={score:.3f}')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/tasks/multi_hop.py agent-evals/tests/test_task_multi_hop.py
git commit -m "fix(scoring): require 30% keyword coverage per step in multi-hop (S4)"
```

---

### Task 8: Fact extraction — add fuzzy matching layer (S5 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/fact_extraction.py:73-87`
- Test: `agent-evals/tests/test_task_fact_extraction.py`

> **Context:** `task_id` must match `^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*_\d+$`, use `domain="framework_api"`.
> ```python
> from agent_evals.tasks.base import TaskDefinition
> from agent_evals.tasks.fact_extraction import FactExtractionTask
> defn = TaskDefinition(task_id="fact_extraction_001", type="fact_extraction", question="Q?", domain="framework_api", difficulty="easy", metadata={...})
> task = FactExtractionTask(defn)
> ```

**Step 1 [RED]:** Write the failing test

```python
def test_paraphrase_scores_above_0_7():
    """'Python version 3.11' should score >= 0.7 for expected 'Python 3.11'."""
    defn = TaskDefinition(
        task_id="fact_extraction_001", type="fact_extraction", question="Q",
        domain="framework_api", difficulty="easy",
        metadata={"expected_answer": "Python 3.11", "aliases": []},
    )
    task = FactExtractionTask(defn)
    score = task.score_response("The environment runs Python version 3.11 natively.")
    assert score >= 0.7, f"Expected >= 0.7 for paraphrase, got {score}"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_task_fact_extraction.py::test_paraphrase_scores_above_0_7 -v
```

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

Add after alias matching, before keyword fallback in `fact_extraction.py`:
```python
from rapidfuzz import fuzz, utils as fuzz_utils

# Layer 3: Fuzzy matching (after exact and alias checks)
fuzzy_score = fuzz.token_set_ratio(
    self.expected_answer.lower(),
    response.lower(),
    processor=fuzz_utils.default_process,
)
if fuzzy_score >= 85.0:
    return 0.9
if fuzzy_score >= 70.0:
    return 0.7
```

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_task_fact_extraction.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Is the fuzzy layer inserted at the correct position in the scoring cascade (after exact, after alias, before keyword fallback)? The order determines which higher-quality match takes precedence.
- Check: Are the 0.9 and 0.7 return values consistent with the overall scoring scale used across other task types? Having a cap at 0.9 (instead of 1.0) for fuzzy matches is intentional — verify the docstring or comment explains this.
- Check: Does `fuzz.token_set_ratio` handle the case where `self.expected_answer` is a single word (like "yes" or "no") without producing unexpectedly high scores against any response?
- Check: Is the `from rapidfuzz` import at the top of the file, not inside the method?
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works against real fact_extraction task data

```bash
uv run python -c "
from agent_evals.fixtures import load_sample_doc_tree
from agent_evals.tasks.loader import load_tasks_from_dir
tasks = [t for t in load_tasks_from_dir('agent-evals/gold_standard/') if t.definition.type == 'fact_extraction'][:5]
print(f'Loaded {len(tasks)} fact_extraction tasks')
from agent_evals.variants.flat import Flat
v = Flat()
doc_tree = load_sample_doc_tree()
v.setup(doc_tree)
rendered = v.render(doc_tree)
for task in tasks:
    score = task.score_response(rendered)
    print(f'  {task.definition.task_id}: score={score:.3f}')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/tasks/fact_extraction.py agent-evals/tests/test_task_fact_extraction.py
git commit -m "fix(scoring): add rapidfuzz fuzzy layer to fact extraction scorer (S5)"
```

---

### Task 9: Code generation — default match_rate to 1.0 when no patterns (S9 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/code_generation.py:115-121`
- Test: `agent-evals/tests/test_task_code_generation.py`

> **Context:** `task_id` must match `^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*_\d+$`, use `domain="framework_api"`.
> ```python
> from agent_evals.tasks.base import TaskDefinition
> from agent_evals.tasks.code_generation import CodeGenerationTask
> defn = TaskDefinition(task_id="code_generation_001", type="code_generation", question="Q?", domain="framework_api", difficulty="easy", metadata={...})
> task = CodeGenerationTask(defn)
> ```

**Step 1 [RED]:** Write the failing test

```python
def test_no_test_patterns_does_not_cap_score_at_0_3():
    """With no test patterns, score should exceed 0.3."""
    defn = TaskDefinition(
        task_id="code_generation_001", type="code_generation", question="Write a function",
        domain="framework_api", difficulty="easy",
        metadata={"test": [], "forbidden_patterns": []},
    )
    task = CodeGenerationTask(defn)
    score = task.score_response("def add(a, b):\n    return a + b")
    assert score > 0.3, f"Expected > 0.3, got {score}"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_task_code_generation.py::test_no_test_patterns_does_not_cap_score_at_0_3 -v
```

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

```python
# In code_generation.py, change the else branch:
if patterns:
    matched = sum(1 for pat in patterns if _match_pattern(pat, response))
    match_rate = matched / len(patterns)
else:
    match_rate = 1.0  # No patterns → vacuously satisfied
```

Also update the docstring formula comment from `0.8 + 0.2` to `0.7 + 0.2 + 0.1`.

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_task_code_generation.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Is `match_rate = 1.0` for empty patterns the right semantic? It means "vacuously satisfied" — is this documented with a comment so future developers understand the intent?
- Check: Does the combined score formula (after `match_rate = 1.0`) produce a result in [0.0, 1.0]? Trace through the full formula to verify no sub-component can push total above 1.0.
- Check: Is the docstring formula comment updated to match the new weight distribution (0.7 + 0.2 + 0.1)?
- Check: Are there existing tests that set empty `test` patterns and expect a low score — those would now fail and should be updated.
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works against real code_generation task data

```bash
uv run python -c "
from agent_evals.fixtures import load_sample_doc_tree
from agent_evals.tasks.loader import load_tasks_from_dir
tasks = [t for t in load_tasks_from_dir('agent-evals/gold_standard/') if t.definition.type == 'code_generation'][:5]
print(f'Loaded {len(tasks)} code_generation tasks')
from agent_evals.variants.flat import Flat
v = Flat()
doc_tree = load_sample_doc_tree()
v.setup(doc_tree)
rendered = v.render(doc_tree)
for task in tasks:
    score = task.score_response(rendered)
    print(f'  {task.definition.task_id}: score={score:.3f}')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/tasks/code_generation.py agent-evals/tests/test_task_code_generation.py
git commit -m "fix(scoring): default match_rate to 1.0 when no test patterns defined (S9)"
```

---

### Task 10: Agentic — whitespace fallback in _parse_json_or_list (S10 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/agentic.py` (around line 47)
- Test: `agent-evals/tests/test_task_agentic.py`

> **Context:** `task_id` must match `^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*_\d+$`, use `domain="framework_api"`.
> ```python
> from agent_evals.tasks.base import TaskDefinition
> from agent_evals.tasks.agentic import AgenticTask
> from agent_evals.tasks.agentic import _parse_json_or_list   # module-level function
> defn = TaskDefinition(task_id="agentic_001", type="agentic", question="Q?", domain="framework_api", difficulty="easy", metadata={...})
> task = AgenticTask(defn)
> ```

**Step 1 [RED]:** Write the failing test

```python
def test_space_separated_test_names_parsed_correctly():
    """'test_foo test_bar' must parse as ['test_foo', 'test_bar']."""
    from agent_evals.tasks.agentic import _parse_json_or_list
    result = _parse_json_or_list("test_foo test_bar")
    assert result == ["test_foo", "test_bar"], f"Got: {result}"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_task_agentic.py::test_space_separated_test_names_parsed_correctly -v
```
Expected: `FAILED — [] != ['test_foo', 'test_bar']`

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

In `agentic.py`, in the `except json.JSONDecodeError` branch of `_parse_json_or_list`:
```python
except json.JSONDecodeError:
    return [token for token in value.strip().split() if token]
```

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_task_agentic.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Does the whitespace split handle edge cases — empty string, all-whitespace string, newlines, tabs? `value.strip().split()` handles all of these correctly (Python `str.split()` without an arg splits on any whitespace).
- Check: Is `_parse_json_or_list` a module-level function? The import in the test (`from agent_evals.tasks.agentic import _parse_json_or_list`) confirms it must be at module level, not a method.
- Check: What happens if the input is a comma-separated string like `"test_foo, test_bar"`? The whitespace split would return `["test_foo,", "test_bar"]` with a trailing comma — is this an edge case that needs a test?
- Check: Is there a newline-separated case that should also be handled? `split()` handles `\n` already.
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works against real agentic task data

```bash
uv run python -c "
from agent_evals.fixtures import load_sample_doc_tree
from agent_evals.tasks.loader import load_tasks_from_dir
tasks = [t for t in load_tasks_from_dir('agent-evals/gold_standard/') if t.definition.type == 'agentic'][:5]
print(f'Loaded {len(tasks)} agentic tasks')
from agent_evals.variants.flat import Flat
v = Flat()
doc_tree = load_sample_doc_tree()
v.setup(doc_tree)
rendered = v.render(doc_tree)
for task in tasks:
    score = task.score_response(rendered)
    print(f'  {task.definition.task_id}: score={score:.3f}')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/tasks/agentic.py agent-evals/tests/test_task_agentic.py
git commit -m "fix(scoring): fall back to whitespace split in agentic _parse_json_or_list (S10)"
```

---

### Task 11: Agentic — dynamic weight redistribution for missing metadata (S11 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/agentic.py` (score_response method, around line 108)
- Test: `agent-evals/tests/test_task_agentic.py`

> **Context:** `task_id` must match `^[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)*_\d+$`, use `domain="framework_api"`.
> ```python
> from agent_evals.tasks.base import TaskDefinition
> from agent_evals.tasks.agentic import AgenticTask
> defn = TaskDefinition(task_id="agentic_001", type="agentic", question="Q?", domain="framework_api", difficulty="easy", metadata={...})
> task = AgenticTask(defn)
> ```

**Step 1 [RED]:** Write the failing test

```python
def test_agentic_score_redistributes_weights_when_no_files():
    """With only expected_tools metadata, score must reflect full tool detection weight."""
    defn = TaskDefinition(
        task_id="agentic_001", type="agentic", question="Q",
        domain="framework_api", difficulty="easy",
        metadata={"expected_tools": ["read_file"], "files": [], "fail_to_pass": []},
    )
    task = AgenticTask(defn)
    # Response mentions the expected tool — should score high, not be capped at 0.2
    score = task.score_response("I would use read_file to read the configuration.")
    assert score >= 0.8, f"Expected >= 0.8 with tool match and redistributed weights, got {score}"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_task_agentic.py::test_agentic_score_redistributes_weights_when_no_files -v
```

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

Refactor `score_response` in `agentic.py`:
```python
def score_response(self, response: str) -> float:
    components: list[tuple[float, float]] = []  # (score, base_weight)
    if self.files:
        components.append((self._score_file_mentions(response), 0.4))
        components.append((self._score_content(response), 0.4))
    if self.fail_to_pass:
        components.append((self._score_correctness(response), 0.2))
    if self.expected_tools:
        components.append((self._score_tools(response), 0.2))
    if not components:
        return 0.5
    total_weight = sum(w for _, w in components)
    return max(0.0, min(1.0, sum(s * (w / total_weight) for s, w in components)))
```

**Step 4 [GREEN]:** Run all agentic tests

```bash
uv run pytest agent-evals/tests/test_task_agentic.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Is the `return 0.5` for empty components (no metadata at all) the right fallback? Should it return 0.0 (no evidence of correct behavior) rather than 0.5 (neutral)?
- Check: Are the base weights (0.4 + 0.4 + 0.2 + 0.2) used only for relative proportion via `w / total_weight`? The redistribution is correct as long as no individual component exceeds 1.0.
- Check: Is `max(0.0, min(1.0, ...))` needed here, or are the individual component scores already in [0.0, 1.0]? Keep the clamp as a defensive guard.
- Check: Does the `components` variable name and pattern make the logic readable? Add a brief comment explaining the redistribution.
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works against real agentic task data

```bash
uv run python -c "
from agent_evals.fixtures import load_sample_doc_tree
from agent_evals.tasks.loader import load_tasks_from_dir
tasks = [t for t in load_tasks_from_dir('agent-evals/gold_standard/') if t.definition.type == 'agentic'][:5]
print(f'Loaded {len(tasks)} agentic tasks')
from agent_evals.variants.flat import Flat
v = Flat()
doc_tree = load_sample_doc_tree()
v.setup(doc_tree)
rendered = v.render(doc_tree)
for task in tasks:
    score = task.score_response(rendered)
    print(f'  {task.definition.task_id}: score={score:.3f}')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/tasks/agentic.py agent-evals/tests/test_task_agentic.py
git commit -m "fix(scoring): dynamic weight redistribution in agentic scorer for missing metadata (S11)"
```

---

## Sprint 4 — Infrastructure: Run Lifecycle Reliability (I10, I9, I13, I3)

---

### Task 12: Add fail_run() to ObservatoryStore (I10 — prerequisite for I9)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/store.py`
- Test: `agent-evals/tests/test_observatory_store.py` (add to existing)

> **Context:**
> ```python
> from agent_evals.observatory.store import ObservatoryStore
> from agent_evals.observatory.tracker import EventTracker
> # Always use real tmp_path (not :memory:)
> store = ObservatoryStore(db_path=tmp_path / "test.db")
> tracker = EventTracker(store=store)
> store.create_run("r1", "full", {}, phase="screening")
> # record_trial() keyword-only args — required: run_id, task_id, task_type, variant_name, repetition, score,
> #   prompt_tokens, completion_tokens, total_tokens, cost, latency_seconds, model
> ```

**Step 1 [RED]:** Write the failing test

```python
def test_fail_run_sets_failed_status_and_finished_at(tmp_path):
    store = ObservatoryStore(db_path=tmp_path / "test.db")
    store.create_run("run1", "full", {}, phase="screening")
    store.fail_run("run1", error="Runner crashed")
    summary = store.get_run_summary("run1")
    assert summary.status == "failed"
    assert summary.finished_at is not None
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_observatory_store.py::test_fail_run_sets_failed_status_and_finished_at -v
```
Expected: `AttributeError: 'ObservatoryStore' has no attribute 'fail_run'`

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

In `store.py`, add after `finish_run()`:
```python
def fail_run(self, run_id: str, error: str | None = None) -> None:
    """Mark a run as failed with optional error message and current timestamp."""
    now = datetime.now(timezone.utc).isoformat()
    with self._lock, self._connect() as conn:
        conn.execute(
            "UPDATE runs SET status = 'failed', finished_at = ? WHERE run_id = ?",
            (now, run_id),
        )
        if error:
            conn.execute(
                "UPDATE runs SET config = json_set(COALESCE(config, '{}'), '$.error', ?) "
                "WHERE run_id = ?",
                (error, run_id),
            )
```

Also verify `finish_run()` sets `finished_at` for the success path. If it doesn't already, add it:
```python
def finish_run(self, run_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with self._lock, self._connect() as conn:
        conn.execute(
            "UPDATE runs SET status = 'completed', finished_at = ? WHERE run_id = ?",
            (now, run_id),
        )
```

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_observatory_store.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Are SQL column names (`status`, `finished_at`, `config`) consistent with the actual schema? Confirm against `_init_db()`.
- Check: Is the `json_set(COALESCE(config, '{}'), ...)` pattern safe — does it work when `config` is already a JSON object vs NULL?
- Check: Is the error string sanitized before storing in the JSON config field? Embedded quotes could break the JSON structure.
- Check: Is `finished_at` stored as an ISO 8601 UTC string — consistent with how other timestamps are stored and read back?
- Check: Does `get_run_summary()` return `finished_at` in the `RunSummary` dataclass — confirm the field is populated from the SELECT.
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works via the store API

```bash
uv run python -c "
import pathlib, tempfile
from agent_evals.observatory.store import ObservatoryStore
tmp = pathlib.Path(tempfile.mkdtemp())
store = ObservatoryStore(tmp / 'verify.db')
store.create_run('run1', 'full', {}, phase='screening')
store.fail_run('run1', error='Runner crashed')
summary = store.get_run_summary('run1')
print(f'status={summary.status}, finished_at={summary.finished_at}')
assert summary.status == 'failed'
assert summary.finished_at is not None
print('Store operation succeeded')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/store.py agent-evals/tests/test_observatory_store.py
git commit -m "feat(store): add fail_run() method; ensure finish_run() sets finished_at (I10+I5)"
```

---

### Task 13: Fix _run_wrapper to mark failed runs in DB (I9 — MEDIUM)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/run_manager.py:145-155`
- Test: `agent-evals/tests/test_run_manager.py`

> **Context:**
> ```python
> from agent_evals.observatory.store import ObservatoryStore
> from agent_evals.observatory.tracker import EventTracker
> from agent_evals.observatory.run_manager import RunManager, StartRunRequest
> from unittest.mock import MagicMock
> store = ObservatoryStore(db_path=tmp_path / "test.db")
> tracker = MagicMock(spec=EventTracker)
> manager = RunManager(store=store, tracker=tracker)
> # start_run() generates run_id internally — do NOT pass run_id:
> manager.start_run(request=StartRunRequest(model="openrouter/anthropic/claude-haiku-4-5-20251001", task_limit=1))
> ```

**Step 1 [RED]:** Write the failing test

```python
def test_run_wrapper_marks_run_failed_on_exception(tmp_path):
    """When _execute_run raises, the run must be marked failed in the DB."""
    from agent_evals.observatory.tracker import EventTracker
    store = ObservatoryStore(db_path=tmp_path / "test.db")
    store.create_run("run1", "full", {}, phase="screening")
    tracker = EventTracker(store=store)          # RunManager requires tracker
    manager = RunManager(store=store, tracker=tracker)
    with patch.object(manager, "_execute_run", side_effect=RuntimeError("crash")):
        manager._run_wrapper("run1", request=MagicMock(spec=StartRunRequest))
    summary = store.get_run_summary("run1")
    assert summary.status == "failed", f"Expected failed, got {summary.status}"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_run_manager.py::test_run_wrapper_marks_run_failed_on_exception -v
```

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

In `run_manager.py` `_run_wrapper`, wrap the `_execute_run()` call:
```python
try:
    self._execute_run(run_id, request)
except Exception as e:
    logger.error("Run %s failed: %s", run_id, e, exc_info=True)
    try:
        self._store.fail_run(run_id, error=str(e))
    except Exception:
        logger.exception("Failed to update DB status for run %s", run_id)
finally:
    self._runs.pop(run_id, None)
```

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_run_manager.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Does the `finally: self._runs.pop(run_id, None)` execute even when `fail_run()` itself raises? The nested try/except ensures it does — verify the exception path doesn't suppress this cleanup.
- Check: Is `str(e)` safe for all exception types? Some exceptions have non-string `args[0]` values — `str(e)` is generally safe but verify it doesn't produce `None` for exceptions with no message.
- Check: Is the error stored in the DB (via `fail_run(error=...)`) truncated if very long (e.g., a full traceback)? Consider a character limit.
- Check: Is the exception re-raised or swallowed? The current implementation swallows it — is that correct for a background thread?
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works via the store API

```bash
uv run python -c "
import pathlib, tempfile
from unittest.mock import patch, MagicMock
from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker
from agent_evals.observatory.run_manager import RunManager
from agent_evals.observatory.web.routes import StartRunRequest
tmp = pathlib.Path(tempfile.mkdtemp())
store = ObservatoryStore(tmp / 'obs.db')
store.create_run('run1', 'full', {}, phase='screening')
tracker = EventTracker(store=store)
manager = RunManager(store=store, tracker=tracker)
with patch.object(manager, '_execute_run', side_effect=RuntimeError('crash')):
    manager._run_wrapper('run1', request=MagicMock(spec=StartRunRequest))
summary = store.get_run_summary('run1')
assert summary.status == 'failed', f'Expected failed, got {summary.status}'
print('Run failure DB update verified')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/run_manager.py agent-evals/tests/test_run_manager.py
git commit -m "fix(runner): mark run as failed in DB when _run_wrapper catches exception (I9)"
```

---

### Task 14: Raise RunSetupError from early returns in _execute_run (I13 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/run_manager.py:157-244`
- Test: `agent-evals/tests/test_run_manager.py`

> **Context:**
> ```python
> from agent_evals.observatory.store import ObservatoryStore
> from agent_evals.observatory.tracker import EventTracker
> from agent_evals.observatory.run_manager import RunManager, StartRunRequest
> from unittest.mock import MagicMock
> store = ObservatoryStore(db_path=tmp_path / "test.db")
> tracker = MagicMock(spec=EventTracker)
> manager = RunManager(store=store, tracker=tracker)
> # start_run() generates run_id internally — do NOT pass run_id:
> manager.start_run(request=StartRunRequest(model="openrouter/anthropic/claude-haiku-4-5-20251001", task_limit=1))
> ```

**Step 1 [RED]:** Write the failing test

```python
def test_missing_api_key_marks_run_failed(tmp_path, monkeypatch):
    """Early return on missing API key must mark run failed, not silently succeed."""
    from agent_evals.observatory.tracker import EventTracker
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    store = ObservatoryStore(db_path=tmp_path / "test.db")
    store.create_run("run1", "full", {}, phase="screening")
    tracker = EventTracker(store=store)          # RunManager requires tracker
    manager = RunManager(store=store, tracker=tracker)
    # Call _run_wrapper directly (synchronously) to avoid threading/timing issues
    manager._run_wrapper("run1", request=MagicMock(spec=StartRunRequest))
    summary = store.get_run_summary("run1")
    assert summary.status == "failed", f"Expected failed, got {summary.status}"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_run_manager.py::test_missing_api_key_marks_run_failed -v
```

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

At top of `run_manager.py`, define:
```python
class RunSetupError(RuntimeError):
    """Raised when run setup fails; causes _run_wrapper to mark run as failed."""
```

Replace all early `return` paths in `_execute_run` with `raise RunSetupError(reason)`:
- No API key → `raise RunSetupError("OPENROUTER_API_KEY not set")`
- No gold_standard dir → `raise RunSetupError("gold_standard directory not found")`
- No tasks loaded → `raise RunSetupError("no tasks loaded from gold_standard")`
- No variants loaded → `raise RunSetupError("no variants configured")`

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_run_manager.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Is `RunSetupError` exported from `run_manager.py` (i.e., importable by callers that want to catch setup failures specifically)?
- Check: Are all four early-return paths converted to `raise RunSetupError`? Do a quick search for remaining bare `return` in `_execute_run`.
- Check: Does `_run_wrapper`'s except clause (from Task 13) catch `RunSetupError` correctly? Since `RunSetupError` extends `RuntimeError` extends `Exception`, it will be caught — verify this.
- Check: Are the error messages clear enough to diagnose the root cause from just the DB record (no log access)?
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works via the store API

```bash
uv run python -c "
import pathlib, tempfile, os
from unittest.mock import MagicMock
from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker
from agent_evals.observatory.run_manager import RunManager
from agent_evals.observatory.web.routes import StartRunRequest
os.environ.pop('OPENROUTER_API_KEY', None)
tmp = pathlib.Path(tempfile.mkdtemp())
store = ObservatoryStore(tmp / 'obs.db')
store.create_run('run1', 'full', {}, phase='screening')
tracker = EventTracker(store=store)
manager = RunManager(store=store, tracker=tracker)
manager._run_wrapper('run1', request=MagicMock(spec=StartRunRequest))
summary = store.get_run_summary('run1')
assert summary.status == 'failed', f'Expected failed, got {summary.status}'
print('RunSetupError path verified — run marked failed')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/run_manager.py agent-evals/tests/test_run_manager.py
git commit -m "fix(runner): raise RunSetupError from early exits so wrapper marks run failed (I13)"
```

---

### Task 15a: Add heartbeat columns and store methods (I3 — MEDIUM, Part 1 of 2)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/store.py`
- Test: `agent-evals/tests/test_observatory_store.py`

> **Context:**
> ```python
> from agent_evals.observatory.store import ObservatoryStore
> from agent_evals.observatory.tracker import EventTracker
> # Always use real tmp_path (not :memory:)
> store = ObservatoryStore(db_path=tmp_path / "test.db")
> tracker = EventTracker(store=store)
> store.create_run("r1", "full", {}, phase="screening")
> # record_trial() keyword-only args — required: run_id, task_id, task_type, variant_name, repetition, score,
> #   prompt_tokens, completion_tokens, total_tokens, cost, latency_seconds, model
> ```

**Step 1 [RED]:** Write the failing tests

```python
def test_update_heartbeat_sets_timestamp(tmp_path):
    store = ObservatoryStore(db_path=tmp_path / "test.db")
    store.create_run("run1", "full", {}, phase="screening")
    store.update_heartbeat("run1")
    # Use the public get_run_summary, not private _connect()
    summary = store.get_run_summary("run1")
    assert summary.heartbeat_at is not None

def test_reap_stale_runs_marks_stale_active_runs_failed(tmp_path):
    import time
    store = ObservatoryStore(db_path=tmp_path / "test.db")
    store.create_run("stale", "full", {}, phase="screening")
    store.update_heartbeat("stale")
    # Reap with a 0-second threshold — anything with a heartbeat is instantly stale
    reaped = store.reap_stale_runs(max_age_seconds=0)
    assert "stale" in reaped
    summary = store.get_run_summary("stale")
    assert summary.status == "failed"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_observatory_store.py::test_update_heartbeat_sets_timestamp -v
```
Expected: `AttributeError` — no `update_heartbeat` method and no `heartbeat_at` on RunSummary

**Step 3 [GREEN]:** Add schema migration

In `store.py` `_init_db()`, add a safe schema migration:
```python
try:
    conn.execute("ALTER TABLE runs ADD COLUMN heartbeat_at TEXT")
except Exception:
    pass  # Column already exists
```

Add `heartbeat_at: str | None = None` to the `RunSummary` dataclass.

**Step 4 [GREEN]:** Add store methods

```python
def update_heartbeat(self, run_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with self._lock, self._connect() as conn:
        conn.execute(
            "UPDATE runs SET heartbeat_at = ? WHERE run_id = ?",
            (now, run_id),
        )

def reap_stale_runs(self, max_age_seconds: int = 300) -> list[str]:
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)).isoformat()
    with self._lock, self._connect() as conn:
        stale = conn.execute(
            "SELECT run_id FROM runs WHERE status = 'active' "
            "AND heartbeat_at IS NOT NULL AND heartbeat_at < ?",
            (cutoff,),
        ).fetchall()
        now = datetime.now(timezone.utc).isoformat()
        for (run_id,) in stale:
            conn.execute(
                "UPDATE runs SET status = 'failed', finished_at = ? WHERE run_id = ?",
                (now, run_id),
            )
    return [r[0] for r in stale]
```

**Step 5 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_observatory_store.py -v
```

**Step 6 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Is the `ALTER TABLE` migration wrapped in a try/except that silently ignores "duplicate column" errors but still propagates other errors (like connection failures)?
- Check: Are both `update_heartbeat` and `reap_stale_runs` protected by `self._lock`? Concurrent heartbeat writes + reaper reads could cause race conditions otherwise.
- Check: Does `reap_stale_runs` correctly filter to only `status = 'active'` runs? Already-failed or completed runs should not be reaped.
- Check: Is `heartbeat_at` populated in `get_run_summary()`'s SELECT query (not just `list_runs`)? The test uses `get_run_summary` — verify this path.
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 7 [VERIFY]:** Confirm the fix works via the store API

```bash
uv run python -c "
import pathlib, tempfile
from agent_evals.observatory.store import ObservatoryStore
tmp = pathlib.Path(tempfile.mkdtemp())
store = ObservatoryStore(tmp / 'verify.db')
store.create_run('run1', 'full', {}, phase='screening')
store.update_heartbeat('run1')
summary = store.get_run_summary('run1')
assert summary.heartbeat_at is not None, 'heartbeat_at not set'
reaped = store.reap_stale_runs(max_age_seconds=0)
assert 'run1' in reaped, f'run1 not reaped: {reaped}'
summary2 = store.get_run_summary('run1')
assert summary2.status == 'failed', f'Expected failed, got {summary2.status}'
print('Heartbeat and reaper verified')
"
```

**Step 8: Commit (store changes only)**

```bash
git add agent-evals/src/agent_evals/observatory/store.py agent-evals/tests/test_observatory_store.py
git commit -m "feat(store): add heartbeat column, update_heartbeat() and reap_stale_runs() (I3 part 1)"
```

---

### Task 15b: Wire heartbeat into runner and add server-side reaper (I3 — MEDIUM, Part 2 of 2)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/run_manager.py` (add HeartbeatThread class; wire into _execute_run)
- Modify: `agent-evals/src/agent_evals/observatory/web/routes.py` (add reaper to lifespan)
- Test: `agent-evals/tests/test_run_manager.py`

> **Context:**
> ```python
> from agent_evals.observatory.store import ObservatoryStore
> from agent_evals.observatory.tracker import EventTracker
> from agent_evals.observatory.run_manager import RunManager, StartRunRequest
> from unittest.mock import MagicMock
> store = ObservatoryStore(db_path=tmp_path / "test.db")
> tracker = MagicMock(spec=EventTracker)
> manager = RunManager(store=store, tracker=tracker)
> # start_run() generates run_id internally — do NOT pass run_id:
> manager.start_run(request=StartRunRequest(model="openrouter/anthropic/claude-haiku-4-5-20251001", task_limit=1))
> ```

**Step 1 [RED]:** Write the failing test

```python
def test_heartbeat_updates_during_run(tmp_path):
    """HeartbeatThread must call update_heartbeat while running."""
    store = ObservatoryStore(db_path=tmp_path / "test.db")
    store.create_run("run1", "full", {}, phase="screening")
    thread = HeartbeatThread(store=store, run_id="run1", interval=0.01)
    thread.start()
    time.sleep(0.05)  # Allow a few heartbeat cycles
    thread.stop()
    thread.join(timeout=1.0)
    summary = store.get_run_summary("run1")
    assert summary.heartbeat_at is not None
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_run_manager.py::test_heartbeat_updates_during_run -v
```

**Step 3 [GREEN]:** Add HeartbeatThread to run_manager.py

```python
import threading

class HeartbeatThread(threading.Thread):
    """Periodically writes a heartbeat timestamp for a run."""
    def __init__(self, store, run_id: str, interval: int = 30):
        super().__init__(daemon=True, name=f"heartbeat-{run_id}")
        self._store = store
        self._run_id = run_id
        self._interval = interval
        self._stop_event = threading.Event()

    def run(self) -> None:
        while not self._stop_event.wait(self._interval):
            try:
                self._store.update_heartbeat(self._run_id)
            except Exception:
                pass

    def stop(self) -> None:
        self._stop_event.set()
```

Start and stop it in `_execute_run`:
```python
heartbeat = HeartbeatThread(self._store, run_id)
heartbeat.start()
try:
    # ... existing execution logic
finally:
    heartbeat.stop()
    heartbeat.join(timeout=5.0)
```

**Step 4 [GREEN]:** Add async reaper to routes.py lifespan

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async def _reaper():
        while True:
            await asyncio.sleep(60)
            reaped = store.reap_stale_runs(max_age_seconds=300)
            if reaped:
                logger.info("Reaped stale runs: %s", reaped)
    task = asyncio.create_task(_reaper())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
```

**Step 5 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_run_manager.py -v
```

**Step 6 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Is `daemon=True` correct for the HeartbeatThread? A daemon thread will be killed abruptly on process exit — this is fine since the `finally` block calls `stop()` + `join()` before the process exits normally.
- Check: Does the `_stop_event.wait(self._interval)` pattern correctly exit the loop when `stop()` is called? The `wait()` returns `True` if the event is set, breaking the `while not` loop immediately.
- Check: Is the reaper task in `routes.py` properly cancelled on server shutdown? The `task.cancel()` + `suppress(CancelledError)` pattern is correct — verify no other lifespan already exists that would conflict.
- Check: Is `HeartbeatThread` exported from `run_manager.py` so the test file can import it directly?
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 7 [VERIFY]:** Confirm heartbeat wiring works end-to-end

```bash
uv run pytest agent-evals/tests/test_run_manager.py -v -k "heartbeat"
# Also confirm import chain has no circular imports
uv run python -c "from agent_evals.observatory.run_manager import HeartbeatThread; print('Import OK')"
```

**Step 8: Commit (wiring changes only)**

```bash
git add agent-evals/src/agent_evals/observatory/run_manager.py \
        agent-evals/src/agent_evals/observatory/web/routes.py \
        agent-evals/tests/test_run_manager.py
git commit -m "feat(runner): wire HeartbeatThread and server-side reaper for stale run detection (I3 part 2)"
```

---

## Sprint 5 — Infrastructure: API Quality (I4, I6, I11/N4, N5/I12, N6)

---

### Task 16: Expose stored config through API (I4 — MEDIUM)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/store.py` (add config to RunSummary)
- Modify: `agent-evals/src/agent_evals/observatory/web/routes.py:188`
- Test: `agent-evals/tests/test_observatory_web.py`

> **Context:**
> ```python
> from fastapi.testclient import TestClient
> from agent_evals.observatory.store import ObservatoryStore
> from agent_evals.observatory.tracker import EventTracker
> from agent_evals.observatory.web.server import create_app
> store = ObservatoryStore(tmp_path / "obs.db")
> tracker = EventTracker(store=store)
> app = create_app(store=store, tracker=tracker)   # pass catalog=, model_sync= etc. if needed
> client = TestClient(app)
> ```

**Step 1 [RED]:** Write the failing test

```python
def test_run_detail_includes_config(client, created_run_id):
    resp = client.get(f"/api/runs/{created_run_id}")
    data = resp.json()
    assert data.get("config") != {}, "config must not be hardcoded empty dict"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_observatory_web.py::test_run_detail_includes_config -v
```

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

In `store.py` `RunSummary` dataclass, add `config: dict = field(default_factory=dict)`.

Populate it in `list_runs()` and `get_run_summary()` by parsing the stored JSON config string.

In `routes.py` `_enrich_run()`, replace `"config": {}` with `"config": run.config`.

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_observatory_web.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Is the JSON config string parsed with `json.loads(config_str or '{}')` with a safe fallback for NULL values? A NULL config in the DB should return `{}`, not raise a `JSONDecodeError`.
- Check: Are both `list_runs()` and `get_run_summary()` updated, or just one? If only one is updated, the API response will be inconsistent between the list endpoint and the detail endpoint.
- Check: Is the `config` field added to `RunSummary` with `field(default_factory=dict)` (not `= {}`) to avoid the mutable default argument anti-pattern?
- Check: Is the `config` stored value trusted (internal data, not user input)? If it could contain user-supplied data, consider sanitizing before returning.
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works via the HTTP API

```bash
uv run python -c "
import pathlib, tempfile
from fastapi.testclient import TestClient
from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker
from agent_evals.observatory.web.server import create_app
tmp = pathlib.Path(tempfile.mkdtemp())
store = ObservatoryStore(tmp / 'obs.db')
tracker = EventTracker(store=store)
store.create_run('r1', 'full', {'model': 'test-model', 'task_limit': 10}, phase='screening')
app = create_app(store=store, tracker=tracker)
client = TestClient(app)
resp = client.get('/api/runs/r1')
data = resp.json()
print('config =', data.get('config'))
assert data.get('config') != {}, 'config must not be empty'
print('API response verified')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/store.py \
        agent-evals/src/agent_evals/observatory/web/routes.py
git commit -m "fix(api): expose stored run config in API response instead of hardcoded {} (I4)"
```

---

### Task 17: Validate model name on run submission (I6 — LOW)

> **Note:** I5 (null `finished_at` on failed run `ba37a9ac39d6`) is already handled by Task 12's `fail_run()` implementation and its ensure-`finish_run`-sets-`finished_at` fix. No additional code change is needed here for I5.

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/run_manager.py`
- Test: `agent-evals/tests/test_run_manager.py`

> **Context:**
> ```python
> from agent_evals.observatory.store import ObservatoryStore
> from agent_evals.observatory.tracker import EventTracker
> from agent_evals.observatory.run_manager import RunManager, StartRunRequest
> from unittest.mock import MagicMock
> store = ObservatoryStore(db_path=tmp_path / "test.db")
> tracker = MagicMock(spec=EventTracker)
> manager = RunManager(store=store, tracker=tracker)
> # start_run() generates run_id internally — do NOT pass run_id:
> manager.start_run(request=StartRunRequest(model="openrouter/anthropic/claude-haiku-4-5-20251001", task_limit=1))
> ```

**Step 1 [RED]:** Write the failing test

```python
def test_model_name_without_slash_rejected(tmp_path):
    """Model string 'test' (no slash) must be rejected before run starts."""
    from agent_evals.observatory.tracker import EventTracker
    store = ObservatoryStore(db_path=tmp_path / "test.db")
    tracker = EventTracker(store=store)          # RunManager requires tracker
    manager = RunManager(store=store, tracker=tracker)
    with pytest.raises(ValueError, match="Invalid model"):
        # start_run takes only `request` — it generates run_id internally
        manager.start_run(request=StartRunRequest(model="test", task_limit=1))
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_run_manager.py::test_model_name_without_slash_rejected -v
```

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

```python
import re
_MODEL_PATTERN = re.compile(r"^[\w.-]+/[\w./-]+$")

def _validate_model_name(model: str) -> None:
    for m in (m.strip() for m in model.split(",")):
        if not _MODEL_PATTERN.match(m):
            raise ValueError(
                f"Invalid model name '{m}'. "
                "Expected LiteLLM format: 'provider/model' "
                "(e.g., 'openrouter/anthropic/claude-sonnet-4.5')."
            )
```

Call `_validate_model_name(request.model)` at the start of `start_run()`.

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_run_manager.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Is `_MODEL_PATTERN` a module-level compiled regex (not recompiled inside `_validate_model_name` on each call)?
- Check: Does the regex allow all valid LiteLLM model formats? Test edge cases: `openrouter/anthropic/claude-3-haiku-4-5-20251001`, `ollama/llama3.2`, `azure/gpt-4o`. Verify none of these are accidentally rejected.
- Check: Is the comma-split handling correct for multi-model strings? What if the model string is empty after stripping?
- Check: Is `_validate_model_name` called before `create_run()` in `start_run()` so an invalid model never creates a DB record?
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works via the HTTP API

```bash
uv run python -c "
import pathlib, tempfile
from fastapi.testclient import TestClient
from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker
from agent_evals.observatory.web.server import create_app
tmp = pathlib.Path(tempfile.mkdtemp())
store = ObservatoryStore(tmp / 'obs.db')
tracker = EventTracker(store=store)
app = create_app(store=store, tracker=tracker)
client = TestClient(app)
resp = client.post('/api/runs', json={'model': 'invalid-model-no-slash', 'task_limit': 1})
print('Status:', resp.status_code)
assert resp.status_code in (400, 422), f'Expected 4xx, got {resp.status_code}'
print('Model validation endpoint verified')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/run_manager.py agent-evals/tests/test_run_manager.py
git commit -m "fix(api): validate model name follows LiteLLM provider/model format on submission (I6)"
```

---

### Task 18: Move trial aggregation to SQL in _enrich_run (I11/N4 — MEDIUM)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/store.py`
- Modify: `agent-evals/src/agent_evals/observatory/web/routes.py:141` (and the full `_enrich_run` body)
- Test: `agent-evals/tests/test_observatory_store.py`

> **Context:**
> ```python
> from agent_evals.observatory.store import ObservatoryStore
> from agent_evals.observatory.tracker import EventTracker
> # Always use real tmp_path (not :memory:)
> store = ObservatoryStore(db_path=tmp_path / "test.db")
> tracker = EventTracker(store=store)
> store.create_run("r1", "full", {}, phase="screening")
> # record_trial() keyword-only args — required: run_id, task_id, task_type, variant_name, repetition, score,
> #   prompt_tokens, completion_tokens, total_tokens, cost, latency_seconds, model
> ```

**Step 1 [RED]:** Write the failing test

```python
def test_get_run_aggregates_returns_correct_statistics(tmp_path):
    store = ObservatoryStore(db_path=tmp_path / "test.db")
    store.create_run("r", "full", {}, phase="screening")
    for i in range(100):
        store.record_trial(   # use record_trial() — not save_trial()
            run_id="r",
            task_id=f"compositional_{i:03d}",
            task_type="compositional",
            variant_name="v1",
            repetition=1,          # REQUIRED keyword arg
            score=i / 100.0,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,       # REQUIRED keyword arg (prompt_tokens + completion_tokens)
            cost=0.001,
            latency_seconds=0.5,   # column is latency_seconds — not latency_ms
            model="openrouter/anthropic/claude-haiku-4-5-20251001",
            source="gold_standard",
        )
    aggs = store.get_run_aggregates("r")
    assert aggs["trial_count"] == 100
    assert abs(aggs["mean_score"] - 0.495) < 0.01
    assert len(aggs["by_variant"]) == 1
    assert aggs["by_variant"][0]["variant"] == "v1"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_observatory_store.py::test_get_run_aggregates_returns_correct_statistics -v
```

**Step 3 [GREEN]:** Add `get_run_aggregates()` to store

```python
def get_run_aggregates(self, run_id: str) -> dict:
    """Return SQL-aggregated trial statistics without loading individual records."""
    with self._connect() as conn:
        row = conn.execute(
            """SELECT COUNT(*), AVG(score),
                      SUM(prompt_tokens + completion_tokens), AVG(latency_seconds)
               FROM trials WHERE run_id = ?""",   # column is latency_seconds
            (run_id,),
        ).fetchone()
        by_variant = conn.execute(
            """SELECT variant_name, COUNT(*), AVG(score)
               FROM trials WHERE run_id = ?
               GROUP BY variant_name""",
            (run_id,),
        ).fetchall()
    return {
        "trial_count": row[0] or 0,
        "mean_score": row[1] or 0.0,
        "total_tokens": row[2] or 0,
        "mean_latency_seconds": row[3] or 0.0,    # key matches column name
        "by_variant": [
            {"variant": r[0], "count": r[1], "mean_score": r[2]}
            for r in by_variant
        ],
    }
```

**Step 4 [GREEN]:** Update `_enrich_run` in routes.py

Read the existing `_enrich_run` function fully first. Replace the `store.get_trials(run_id)` call and all downstream Python-level aggregation with a single call to `store.get_run_aggregates(run_id)`. Map the returned dict fields to the existing response shape.

**Step 5 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_observatory_store.py agent-evals/tests/test_observatory_web.py -v
```

**Step 6 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Are SQL column names used in the aggregate query consistent with the actual schema? Confirm `latency_seconds` (not `latency_ms`) and `prompt_tokens + completion_tokens` are correct.
- Check: Does `get_run_aggregates()` need `self._lock`? It's a read-only operation, but if other threads are writing concurrently, the lock ensures consistency.
- Check: Is the `_enrich_run` replacement backward-compatible with the existing API response shape? Check that all fields consumed by the frontend are still present.
- Check: Is there a test for `_enrich_run` with zero trials? The `AVG(score)` returns NULL in SQL for an empty table — verify the `or 0.0` fallback handles this.
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 7 [VERIFY]:** Confirm the fix works via the HTTP API

```bash
uv run python -c "
import pathlib, tempfile
from fastapi.testclient import TestClient
from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker
from agent_evals.observatory.web.server import create_app
tmp = pathlib.Path(tempfile.mkdtemp())
store = ObservatoryStore(tmp / 'obs.db')
tracker = EventTracker(store=store)
store.create_run('r1', 'full', {})
app = create_app(store=store, tracker=tracker)
client = TestClient(app)
resp = client.get('/api/runs/r1')
data = resp.json()
print('trial_count =', data.get('trial_count', 'MISSING'))
print('mean_score =', data.get('mean_score', 'MISSING'))
print('API aggregation response verified')
"
```

**Step 8: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/store.py \
        agent-evals/src/agent_evals/observatory/web/routes.py
git commit -m "perf(api): move trial aggregation to SQL in _enrich_run (I11/N4)"
```

---

### Task 19: Real SQL pagination in list_runs + eliminate list_pipelines N+1 (N5/I12 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/store.py`
- Modify: `agent-evals/src/agent_evals/observatory/web/routes.py:111-112, 384-401`
- Test: `agent-evals/tests/test_observatory_web.py`

> **Context:**
> ```python
> from agent_evals.observatory.store import ObservatoryStore
> from agent_evals.observatory.tracker import EventTracker
> from agent_evals.observatory.run_manager import RunManager, StartRunRequest
> from unittest.mock import MagicMock
> store = ObservatoryStore(db_path=tmp_path / "test.db")
> tracker = MagicMock(spec=EventTracker)
> manager = RunManager(store=store, tracker=tracker)
> # start_run() generates run_id internally — do NOT pass run_id:
> manager.start_run(request=StartRunRequest(model="openrouter/anthropic/claude-haiku-4-5-20251001", task_limit=1))
> ```

**Step 1 [RED]:** Write the failing tests (one per bug)

```python
def test_list_runs_pagination_uses_sql_limit_offset(tmp_path):
    """SQL LIMIT/OFFSET must be used, not Python slicing."""
    store = ObservatoryStore(db_path=tmp_path / "test.db")
    for i in range(20):
        store.create_run(f"run{i}", "full", {})
    # Ask for page 2 with limit=5 (offset=5)
    page2 = store.list_runs(limit=5, offset=5)
    page1 = store.list_runs(limit=5, offset=0)
    assert len(page2) == 5
    assert page2[0].run_id != page1[0].run_id

def test_list_pipelines_does_not_make_per_run_queries(tmp_path):
    """list_pipelines must not call _get_pipeline_id() N times."""
    store = ObservatoryStore(db_path=tmp_path / "test.db")
    # Create 3 runs in the same pipeline
    for i in range(3):
        store.create_run(f"run{i}", "full", {}, pipeline_id="pipe1")
    pipelines = store.list_pipelines()
    # pipeline_id must be available without per-run lookups
    assert any(p.get("pipeline_id") == "pipe1" for p in pipelines)
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_observatory_web.py::test_list_runs_pagination_uses_sql_limit_offset -v
```

**Step 3 [GREEN]:** Add `limit`/`offset` to `store.list_runs()` SQL

Add `pipeline_id` to the `RunSummary` dataclass and include it in the `list_runs()` SQL (join if needed) to eliminate per-run lookups in `list_pipelines`.

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_observatory_web.py agent-evals/tests/test_observatory_store.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Does `list_runs(limit=None, offset=0)` (the default no-limit case) still work correctly? Add `LIMIT -1` or omit the LIMIT clause when `limit` is None to avoid breaking the existing default behavior.
- Check: Is `pipeline_id` now returned from a JOIN or a subquery? Confirm it doesn't introduce a new N+1 by joining against a separate pipelines table.
- Check: Is the sort order deterministic for pagination? Without an `ORDER BY` clause, `LIMIT/OFFSET` results are undefined. Confirm the SQL has `ORDER BY created_at DESC` or similar.
- Check: Are the new `limit` and `offset` parameters added to `list_runs()` with safe integer types (not user-controlled strings) to prevent SQL injection?
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works via the HTTP API

```bash
uv run python -c "
import pathlib, tempfile
from fastapi.testclient import TestClient
from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker
from agent_evals.observatory.web.server import create_app
tmp = pathlib.Path(tempfile.mkdtemp())
store = ObservatoryStore(tmp / 'obs.db')
tracker = EventTracker(store=store)
for i in range(10):
    store.create_run(f'run{i}', 'full', {})
app = create_app(store=store, tracker=tracker)
client = TestClient(app)
resp = client.get('/api/runs?limit=5&offset=0')
data = resp.json()
print('Page 1 count:', len(data.get('runs', [])))
resp2 = client.get('/api/runs?limit=5&offset=5')
data2 = resp2.json()
print('Page 2 count:', len(data2.get('runs', [])))
assert len(data.get('runs', [])) == 5
assert len(data2.get('runs', [])) == 5
print('Pagination endpoint verified')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/store.py \
        agent-evals/src/agent_evals/observatory/web/routes.py
git commit -m "fix(api): push pagination into SQL; add pipeline_id to RunSummary to fix N+1 (N5+I12)"
```

---

### Task 20: Add oa_row_id and phase to TrialRecord (N6 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/store.py:18-35`
- Test: `agent-evals/tests/test_observatory_store.py`

> **Context:**
> ```python
> from agent_evals.observatory.store import ObservatoryStore
> from agent_evals.observatory.tracker import EventTracker
> # Always use real tmp_path (not :memory:)
> store = ObservatoryStore(db_path=tmp_path / "test.db")
> tracker = EventTracker(store=store)
> store.create_run("r1", "full", {}, phase="screening")
> # record_trial() keyword-only args — required: run_id, task_id, task_type, variant_name, repetition, score,
> #   prompt_tokens, completion_tokens, total_tokens, cost, latency_seconds, model
> ```

**Step 1 [RED]:** Write the failing test

```python
def test_trial_record_includes_oa_row_id_and_phase(tmp_path):
    store = ObservatoryStore(db_path=tmp_path / "test.db")
    store.create_run("r", "taguchi", {}, phase="screening")
    # Use record_trial() (not save_trial — that doesn't exist); all args keyword-only
    store.record_trial(
        run_id="r",
        task_id="negative_001",
        task_type="negative",
        variant_name="baseline",
        repetition=1,
        score=0.5,
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        cost=0.001,
        latency_seconds=0.1,
        model="openrouter/anthropic/claude-haiku-4-5-20251001",
        source="gold_standard",
        oa_row_id=3,
        phase="screening",
    )
    trials = store.get_trials("r")
    assert trials[0].oa_row_id == 3
    assert trials[0].phase == "screening"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_observatory_store.py::test_trial_record_includes_oa_row_id_and_phase -v
```

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

Add to `TrialRecord` dataclass (after the last existing field):
```python
oa_row_id: int | None = None
phase: str | None = None
```

Then in `get_trials()`, the constructor call maps row fields by name. Locate the `TrialRecord(...)` constructor call inside `get_trials()` and add two keyword arguments:
```python
oa_row_id=r["oa_row_id"],
phase=r["phase"],
```
The database schema already has these columns (`oa_row_id INTEGER` and `phase TEXT`) — the SELECT uses `SELECT *` so the values are already in `r`, they're just not mapped. No SQL change needed.

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_observatory_store.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Are nullable fields (`oa_row_id: int | None`, `phase: str | None`) using the correct Python 3.10+ union syntax, or the `Optional[int]` form — be consistent with the rest of the dataclass.
- Check: Does the `SELECT *` in `get_trials()` guarantee `oa_row_id` and `phase` are always returned even if older DB files don't have these columns? If the DB was created before the migration, SELECT * would fail or return None — verify the schema migration in `_init_db()` adds these columns safely.
- Check: Is `r["oa_row_id"]` safe when the value is NULL in SQLite? SQLite maps NULL to Python `None` via `sqlite3.Row` — this should work correctly.
- Check: Is there a test for the case where `oa_row_id` and `phase` are NOT passed to `record_trial()` (i.e., they're optional)? The default should be `None`.
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works via the store API

```bash
uv run python -c "
import pathlib, tempfile
from agent_evals.observatory.store import ObservatoryStore
tmp = pathlib.Path(tempfile.mkdtemp())
store = ObservatoryStore(tmp / 'verify.db')
store.create_run('r', 'taguchi', {}, phase='screening')
store.record_trial(
    run_id='r', task_id='negative_001', task_type='negative',
    variant_name='baseline', repetition=1, score=0.5,
    prompt_tokens=10, completion_tokens=5, total_tokens=15,
    cost=0.001, latency_seconds=0.1,
    model='openrouter/anthropic/claude-haiku-4-5-20251001',
    source='gold_standard', oa_row_id=3, phase='screening',
)
trials = store.get_trials('r')
assert trials[0].oa_row_id == 3, f'Expected 3, got {trials[0].oa_row_id}'
assert trials[0].phase == 'screening', f'Expected screening, got {trials[0].phase}'
print('TrialRecord fields verified')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/store.py agent-evals/tests/test_observatory_store.py
git commit -m "fix(store): add oa_row_id and phase fields to TrialRecord (N6)"
```

---

## Sprint 6 — New Frontend Bugs (N1, N2, N3, N7)

> **Frontend testing pattern:** All SSE hook tests must use EventSource mocking. Do NOT reference `__handleEvent`, `__simulateError`, or `addTrial` — these do not exist on hook return values.
>
> Install EventSource mock if not already present: `npm install --save-dev mock-eventsource` (or the package the project already uses for SSE testing — check `package.json` devDependencies first).

All `npm test` commands must be run from the UI directory:
```bash
cd agent-evals/src/agent_evals/observatory/web/ui
```

---

### Task 21: Wrap JSON.parse in try/catch in useSSE (N1 — MEDIUM)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/web/ui/src/hooks/useSSE.ts:50, 62`
- Test: `agent-evals/src/agent_evals/observatory/web/ui/src/__tests__/hooks/useSSE.test.ts`

> **Context:** Test file already has module-level `MockEventSource` class (with `emit(event, data)` method)
> and `createWrapper()` function. Tests use `async import` pattern. `useSSE` takes an options object:
> `useSSE({ runId: "run-1", onTrialComplete?, onRunComplete?, onError?, onAlert? })` — NOT a bare string.
> `MockEventSource.emit("event", data)` calls the registered listeners — use this, NOT `dispatchEvent()`.

**Step 1 [RED]:** Write the failing test

```typescript
// The project defines MockEventSource inline in useSSE.test.ts (not an npm package).
// useSSE takes an OPTIONS OBJECT — not a bare string. Its mock uses emit() not dispatchEvent().
// To send malformed JSON, bypass emit() (which JSON.stringifies) and call the listener directly.

it("does not crash when SSE delivers malformed JSON", async () => {
  const { useSSE } = await import("../../hooks/useSSE");
  const wrapper = createWrapper();
  // useSSE takes { runId } object (not a bare string)
  renderHook(() => useSSE({ runId: "run1" }), { wrapper });

  const source = MockEventSource.instances[0];
  // Call the trial_completed listener directly with a bad-JSON MessageEvent
  expect(() => {
    act(() => {
      const handlers = source?.listeners["trial_completed"] ?? [];
      for (const handler of handlers) {
        handler(new MessageEvent("trial_completed", { data: "{not json!!" }));
      }
    });
  }).not.toThrow();
});
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
cd agent-evals/src/agent_evals/observatory/web/ui
npm test -- --testPathPattern=useSSE
```
Expected: test throws `SyntaxError: Unexpected token`

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

In `useSSE.ts`, wrap both `JSON.parse(e.data)` calls:
```typescript
try {
  const parsed = JSON.parse(e.data);
  // ... existing logic
} catch (err) {
  console.error("[useSSE] malformed JSON event, skipping:", err);
}
```

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
npm test -- --testPathPattern=useSSE
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Are BOTH `JSON.parse(e.data)` calls wrapped (the plan says "both" — confirm there are two separate parse calls in the file)?
- Check: Is the error logged with enough context (`[useSSE]` prefix, event type) to diagnose the source in production?
- Check: Are TypeScript types correct — `parsed` should be typed as `unknown` (not `any`) after the JSON.parse, then narrowed before use?
- Check: Does the catch block swallow ALL errors, or only `SyntaxError`? Swallowing all is fine here since malformed data is not a programming error.
- Run the full frontend test suite:
  ```bash
  npm test
  ```

**Step 6 [VERIFY]:** Build check to confirm no TypeScript errors

```bash
cd agent-evals/src/agent_evals/observatory/web/ui
npm run build 2>&1 | tail -5
# Expected: build succeeds with 0 errors (warnings OK)
# Manual: npm run dev, open localhost:5173, trigger the SSE stream to confirm no crashes
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/hooks/useSSE.ts \
        "agent-evals/src/agent_evals/observatory/web/ui/src/__tests__/hooks/useSSE.test.ts"
git commit -m "fix(frontend): wrap JSON.parse in try/catch in useSSE event handlers (N1)"
```

---

### Task 22: Cap scores array at 1000 entries (N2 — MEDIUM)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/web/ui/src/hooks/useLiveMonitorState.ts:78`
- Test: existing test file for useLiveMonitorState

> **Context:** Test file has module-level `mockUseActiveRuns`, `mockUseRun`, `mockUseTrials` (vi.fn()).
> `beforeEach` stubs EventSource with MockEventSource, sets fake timers, and sets:
> `mockUseActiveRuns.mockReturnValue({ data: { runs: [{ run_id: "run-1", mode: "taguchi", models: [], started_at: "" }], count: 1 } })`.
> New tests drop into the existing `describe("useLiveMonitorState", ...)` block — no re-stubs needed.
> Hook signature: `useLiveMonitorState(totalTasksOverride?: number)` — gets runId internally from `useActiveRuns()`.

**Step 1 [RED]:** Write the failing test

Add this test INSIDE the existing `describe("useLiveMonitorState", ...)` block in
`agent-evals/src/agent_evals/observatory/web/ui/src/__tests__/hooks/useLiveMonitorState.test.ts`.

The file already declares `mockUseActiveRuns`, `mockUseRun`, `mockUseTrials` at module level
(lines 36-38) and its `beforeEach` already stubs `EventSource`, `fetch`, fake timers, and
mocks all three hooks — do NOT re-declare or re-stub any of those.

The `beforeEach` sets `mockUseActiveRuns` to return `run-1`, which causes the hook to
auto-connect an `EventSource` to `/api/runs/run-1/stream`. `MockEventSource.instances[0]`
is therefore populated as soon as `renderHook` renders.

```typescript
it("scores array stays bounded after many trials", async () => {
  const { useLiveMonitorState } = await import("../../hooks/useLiveMonitorState");
  const wrapper = createWrapper();
  // beforeEach already: stubs EventSource, sets mockUseActiveRuns → run-1, fake timers
  const { result } = renderHook(() => useLiveMonitorState(), { wrapper });
  act(() => {
    for (let i = 0; i < 1500; i++) {
      // emit() calls the registered trial_completed handler with a MessageEvent
      MockEventSource.instances[0]?.emit("trial_completed", { score: 0.5, task_id: `t${i}` });
    }
  });
  expect(result.current.scores.length).toBeLessThanOrEqual(1000);
});
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
npm test -- --testPathPattern=useLiveMonitorState
```

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

```typescript
const MAX_SCORES = 1000;

// Change line 78:
setScores((prev) => {
  const next = [...prev, trial.score];
  return next.length > MAX_SCORES ? next.slice(-MAX_SCORES) : next;
});
```

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
npm test -- --testPathPattern=useLiveMonitorState
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Is `MAX_SCORES = 1000` a module-level named constant (not a magic number inline)?
- Check: Does `next.slice(-MAX_SCORES)` correctly keep the MOST RECENT 1000 scores (tail), not the oldest 1000 (head)? Verify the slice direction is intentional.
- Check: Is the scores array used elsewhere in the hook's state? If other consumers depend on the full unbounded array, this change affects them.
- Check: Is there a matching cap on other unbounded arrays in the hook (e.g., trial records, task IDs)? If scores is bounded at 1000 but trials isn't, the memory problem still exists.
- Run the full frontend test suite:
  ```bash
  npm test
  ```

**Step 6 [VERIFY]:** Build check to confirm no TypeScript errors

```bash
cd agent-evals/src/agent_evals/observatory/web/ui
npm run build 2>&1 | tail -5
# Expected: build succeeds with 0 errors
# Manual: npm run dev, stream 1000+ trials, confirm UI does not slow down
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/hooks/useLiveMonitorState.ts
git commit -m "fix(frontend): cap scores array at MAX_SCORES=1000 in useLiveMonitorState (N2)"
```

---

### Task 23: Migrate deleteGroup to fetchApi wrapper (N3 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/web/ui/src/api/client.ts:274`
- Test: existing client test file

> **Context:** TypeScript frontend test. Add to existing `client.test.ts`. `fetchApi` is the internal
> wrapper in `api/client.ts` — mock `global.fetch` to test timeout and error handling behavior.

**Step 1 [RED]:** Write the failing test

```typescript
it("deleteGroup uses fetchApi not raw fetch", async () => {
  const fetchSpy = vi.spyOn(globalThis, "fetch");
  // Also mock fetchApi if it's exported
  await deleteGroup("group1");
  // fetchApi uses AbortController + timeout; raw fetch does not
  // The test verifies the timeout header/signal is present
  expect(fetchSpy).toHaveBeenCalledWith(
    expect.stringContaining("group1"),
    expect.objectContaining({ signal: expect.any(AbortSignal) })
  );
});
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
npm test -- --testPathPattern=client
```

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

```typescript
export async function deleteGroup(groupId: string): Promise<void> {
  await fetchApi<void>(`/api/groups/${groupId}`, { method: "DELETE" });
}
```

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
npm test -- --testPathPattern=client
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Is `fetchApi<void>` the correct generic type — does `fetchApi` handle a void/empty 204 response without trying to parse JSON?
- Check: Is the URL path `/api/groups/${groupId}` correct? Verify against the backend route in `routes.py`.
- Check: Does this change break any callers of `deleteGroup` that previously expected the raw `fetch` behavior (no AbortSignal)?
- Check: Are TypeScript types correct — `Promise<void>` return type matches `fetchApi<void>`.
- Run the full frontend test suite:
  ```bash
  npm test
  ```

**Step 6 [VERIFY]:** Build check to confirm no TypeScript errors

```bash
cd agent-evals/src/agent_evals/observatory/web/ui
npm run build 2>&1 | tail -5
# Expected: build succeeds with 0 errors
# Manual: npm run dev, open localhost:5173, delete a group, confirm no timeout errors
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/api/client.ts
git commit -m "fix(frontend): migrate deleteGroup to use fetchApi wrapper with timeout (N3)"
```

---

### Task 24: Clear poll interval when max SSE reconnects reached (N7 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/web/ui/src/hooks/useSSE.ts:69-100`
- Test: `useSSE.test.ts`

> **Context:** Test file already has module-level `MockEventSource` class (with `emit(event, data)` method)
> and `createWrapper()` function. Tests use `async import` pattern. `useSSE` takes an options object:
> `useSSE({ runId: "run-1", onTrialComplete?, onRunComplete?, onError?, onAlert? })` — NOT a bare string.
> `MockEventSource.emit("event", data)` calls the registered listeners — use this, NOT `dispatchEvent()`.

**Step 1 [RED]:** Write the failing test

```typescript
// IMPORTANT: The test file already has beforeEach/afterEach managing fake timers and
// EventSource stub — do NOT duplicate those calls inside the test body.
// useSSE takes an OPTIONS OBJECT { runId, ... } — NOT a bare string.
// MockEventSource has no dispatchEvent() method — call source.emit("error", {}) instead.
// renderHook needs the QueryClient wrapper from createWrapper().
it("clears the poll interval when MAX_RECONNECTS is reached", async () => {
  const { useSSE } = await import("../../hooks/useSSE");
  const wrapper = createWrapper();
  const clearSpy = vi.spyOn(globalThis, "clearInterval");
  renderHook(() => useSSE({ runId: "run1" }), { wrapper });
  // Trigger MAX_RECONNECTS (=10) errors by calling the registered error handler directly
  act(() => {
    for (let i = 0; i <= 10; i++) {
      // MockEventSource.emit() calls all listeners for the event — use it, NOT dispatchEvent()
      MockEventSource.instances[0]?.emit("error", {});
      vi.advanceTimersByTime(1000);
    }
  });
  expect(clearSpy).toHaveBeenCalled();
});
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
npm test -- --testPathPattern=useSSE
```

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

Store poll interval ID in a ref:
```typescript
const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
// When starting: pollIntervalRef.current = setInterval(...);
// In max-reconnect branch:
if (reconnectCount >= MAX_RECONNECTS) {
  disconnect();
  if (pollIntervalRef.current !== null) {
    clearInterval(pollIntervalRef.current);
    pollIntervalRef.current = null;
  }
  setError("Max reconnects reached");
}
```

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
npm test -- --testPathPattern=useSSE
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Is `pollIntervalRef` cleaned up in the `useEffect` cleanup function (returned cleanup)? If the component unmounts before MAX_RECONNECTS, the interval must still be cleared.
- Check: Is `MAX_RECONNECTS` a named constant at the top of `useSSE.ts` (not a magic number `10` inline)?
- Check: After calling `clearInterval`, is `pollIntervalRef.current` set to `null` to prevent double-clearing?
- Check: Does clearing the poll interval when max reconnects is reached prevent further SSE reconnect attempts? Verify the reconnect loop terminates completely.
- Run the full frontend test suite:
  ```bash
  npm test
  ```

**Step 6 [VERIFY]:** Build check to confirm no TypeScript errors

```bash
cd agent-evals/src/agent_evals/observatory/web/ui
npm run build 2>&1 | tail -5
# Expected: build succeeds with 0 errors
# Manual: npm run dev, open localhost:5173, disconnect network repeatedly to trigger reconnects
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/hooks/useSSE.ts
git commit -m "fix(frontend): clear poll interval when max SSE reconnects reached (N7)"
```

---

## Sprint 7 — Evaluation Framework Bugs (E3, E4, E6, E7, E8, S6)

---

### Task 25: Fix YAML variant colon content (E3 — MEDIUM)

**Files:**
- Modify: `agent-evals/src/agent_evals/variants/format_yaml.py:60`
- Test: `agent-evals/tests/test_format_yaml.py` (**create new file**)

> **Context:**
> ```python
> from agent_evals.fixtures import load_sample_doc_tree   # returns DocTree
> from agent_evals.variants.format_yaml import FormatYaml
> doc_tree = load_sample_doc_tree()
> # render() takes DocTree, not list[DocFile]:
> rendered = FormatYaml().render(doc_tree)
> # Get first DocFile for mutation:
> doc = next(iter(doc_tree.files.values()))
> ```

**Step 0: Create the test file**

`agent-evals/tests/test_format_yaml.py` does not yet exist. Create it with:
```python
"""Tests for the YAML format variant."""
import pytest
import yaml
from agent_evals.variants.format_yaml import FormatYaml   # NOT FormatYamlVariant
from agent_evals.fixtures import load_sample_doc_tree
from agent_index.models import DocTree


def make_doc_tree(summary: str = "test summary") -> DocTree:
    """Return a DocTree with the first file's summary set for testing.

    render() takes DocTree NOT list[DocFile] — always pass the full DocTree.
    """
    doc_tree = load_sample_doc_tree()
    doc = next(iter(doc_tree.files.values()))   # DocTree.files is a dict[str, DocFile]
    doc.summary = summary
    return doc_tree   # Return the whole tree, not just the DocFile
```

**Step 1 [RED]:** Write the failing test

```python
def test_yaml_summary_with_colon_is_parseable():
    import yaml
    variant = FormatYaml()   # NOT FormatYamlVariant()
    doc_tree = make_doc_tree(summary="JWT auth: token-based login")
    output = variant.render(doc_tree)   # render() takes DocTree, NOT list[DocFile]
    parsed = yaml.safe_load(output)  # Must not raise ScannerError
    assert parsed is not None
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_format_yaml.py::test_yaml_summary_with_colon_is_parseable -v
```
Expected: `yaml.scanner.ScannerError`

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

```python
import yaml

# Replace the manual f-string line:
# f"    summary: {summary}"
# WITH: (uses safe_dump exclusively — never yaml.dump)
summary_value = yaml.safe_dump(summary).strip()
output_line = f"    summary: {summary_value}"
```

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_format_yaml.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Does `yaml.safe_dump(summary).strip()` produce a quoted string for summaries containing colons? Test `yaml.safe_dump("JWT auth: token-based login")` in a Python REPL to verify the output — it should produce `'JWT auth: token-based login'\n` which after strip becomes `'JWT auth: token-based login'`.
- Check: Is `yaml.safe_dump` used exclusively (not `yaml.dump`)? The plan says "uses safe_dump exclusively — never yaml.dump".
- Check: Does the output YAML remain valid for summaries without colons? A plain summary "Hello world" should not gain unnecessary quotes.
- Check: Are other text fields in the YAML output (like `title`, `path`) also vulnerable to colon injection? If so, they need the same fix.
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works with the actual variant and sample data

```bash
uv run python -c "
from agent_evals.fixtures import load_sample_doc_tree
from agent_evals.variants.format_yaml import FormatYaml
import yaml
v = FormatYaml()
doc_tree = load_sample_doc_tree()
# Inject a colon into the first doc's summary
doc = next(iter(doc_tree.files.values()))
doc.summary = 'JWT auth: token-based login'
rendered = v.render(doc_tree)
print('Rendered length:', len(rendered))
parsed = yaml.safe_load(rendered)
assert parsed is not None, 'YAML parse failed'
print('YAML valid — no ScannerError')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/variants/format_yaml.py agent-evals/tests/test_format_yaml.py
git commit -m "fix(variants): use yaml.safe_dump for summary to handle colon content (E3)"
```

---

### Task 26: Escape pipe characters in table variants (E4 — TRIVIAL)

**Files:**
- Modify: `agent-evals/src/agent_evals/variants/format_pipe_delimited.py:52-53`
- Also modify: `agent-evals/src/agent_evals/variants/format_markdown_table.py` (same bug)
- Test: `agent-evals/tests/test_format_pipe_delimited.py` (**create new file**)

> **Context:**
> ```python
> from agent_evals.fixtures import load_sample_doc_tree   # returns DocTree
> from agent_evals.variants.format_pipe_delimited import FormatPipeDelimited
> doc_tree = load_sample_doc_tree()
> # render() takes DocTree, not list[DocFile]:
> rendered = FormatPipeDelimited().render(doc_tree)
> # Get first DocFile for mutation:
> doc = next(iter(doc_tree.files.values()))
> ```

**Step 0: Create the test file**

`agent-evals/tests/test_format_pipe_delimited.py` does not yet exist. Create it with:
```python
"""Tests for the pipe-delimited format variant."""
import pytest
from agent_evals.variants.format_pipe_delimited import FormatPipeDelimited  # NOT PipeDelimitedVariant
from agent_evals.fixtures import load_sample_doc_tree
from agent_index.models import DocTree


def make_doc_tree(summary: str = "test summary") -> DocTree:
    """Return a DocTree with the first file's summary set for testing.

    render() takes DocTree NOT list[DocFile] — always pass the full DocTree.
    """
    doc_tree = load_sample_doc_tree()
    doc = next(iter(doc_tree.files.values()))
    doc.summary = summary
    return doc_tree   # Return the whole tree, not just the DocFile


# Check the actual header in format_pipe_delimited.py to determine EXPECTED_PIPE_COUNT:
# head -30 agent-evals/src/agent_evals/variants/format_pipe_delimited.py
# Count the | characters in the header row (e.g., "path|section|tier|tokens|summary" → 4 pipes)
EXPECTED_PIPE_COUNT = 4  # placeholder — verify against actual header before running
```

**Step 1 [RED]:** Write the failing test

```python
def test_pipe_in_summary_does_not_add_extra_columns():
    variant = FormatPipeDelimited()   # NOT PipeDelimitedVariant()
    doc_tree = make_doc_tree(summary="A|B comparison")
    output = variant.render(doc_tree)   # render() takes DocTree, NOT list[DocFile]
    data_rows = [r for r in output.splitlines() if "comparison" in r]
    assert len(data_rows) == 1
    assert data_rows[0].count("|") == EXPECTED_PIPE_COUNT
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_format_pipe_delimited.py::test_pipe_in_summary_does_not_add_extra_columns -v
```

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

Add helper in both variant files:
```python
def _escape_cell(text: str) -> str:
    return text.replace("|", "\\|")
```

Apply to all cell values in row-building code.

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_format_pipe_delimited.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Is `_escape_cell` applied to ALL cell values in the row builder (not just `summary`)? Other fields like `path` or `section` could also contain `|` characters.
- Check: Is `_escape_cell` defined as a module-level helper function, or a method? Module-level is preferable for a pure string transformation.
- Check: Does the markdown table variant (`format_markdown_table.py`) also apply `_escape_cell`? The plan says both files have the same bug — confirm both are fixed.
- Check: Is `\\|` the correct escape for the pipe-delimited format? In a `|`-delimited file, `\|` prevents column splitting. In a markdown table, `\|` is the standard escape.
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works with the actual variant and sample data

```bash
uv run python -c "
from agent_evals.fixtures import load_sample_doc_tree
from agent_evals.variants.format_pipe_delimited import FormatPipeDelimited
v = FormatPipeDelimited()
doc_tree = load_sample_doc_tree()
doc = next(iter(doc_tree.files.values()))
doc.summary = 'A|B comparison with C|D'
rendered = v.render(doc_tree)
print('Rendered length:', len(rendered))
print('First 300 chars:', rendered[:300])
rows = [r for r in rendered.splitlines() if 'comparison' in r]
assert len(rows) == 1, f'Expected 1 row, got {len(rows)}'
print('Pipe escape verified')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/variants/format_pipe_delimited.py \
        agent-evals/src/agent_evals/variants/format_markdown_table.py \
        agent-evals/tests/test_format_pipe_delimited.py
git commit -m "fix(variants): escape pipe characters in table cell content (E4)"
```

---

### Task 27: Populate TrialResult.metrics with timing data (E6 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/runner.py:263, 631`
- Test: `agent-evals/tests/test_runner.py`

> **Context:**
> ```python
> from agent_evals.runner import EvalRunner, EvalRunConfig
> # EvalRunner(client, config=config) — client is FIRST positional arg
> # EvalRunConfig fields: repetitions, max_connections, max_tasks, temperature,
> #   max_tokens, use_cache, cache_dir, output_dir, output_format, display_mode, continue_on_error
> # Test helpers (already in test_runner.py): _make_mock_task(), _make_mock_variant(),
> #   _make_mock_client(), _make_sample_doc_tree()
> config = EvalRunConfig(use_cache=False)
> runner = EvalRunner(_make_mock_client(), config=config)
> ```

**Step 1 [RED]:** Write the failing test

```python
def test_trial_result_metrics_contains_timing_keys():
    """TrialResult.metrics must be populated after a successful trial."""
    # Use the helpers already in test_runner.py — make_trial_spec() does NOT exist
    task = _make_mock_task()
    variant = _make_mock_variant()
    doc_tree = _make_sample_doc_tree()
    client = _make_mock_client()
    # EvalRunConfig has NO model/task_types/task_limit fields — use actual fields:
    # repetitions, max_connections, max_tasks, temperature, max_tokens, use_cache, etc.
    config = EvalRunConfig(max_tasks=1, repetitions=1, use_cache=False)
    # EvalRunner takes client as FIRST positional arg, config as keyword arg
    runner = EvalRunner(client, config=config)
    result = runner._run_trial(task, variant, doc_tree, repetition=1)
    assert result.metrics != {}, "metrics dict must not be empty"
    assert "scoring_ms" in result.metrics, "scoring_ms must be present"
    assert "prompt_build_ms" in result.metrics, "prompt_build_ms must be present"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_runner.py::test_trial_result_metrics_contains_timing_keys -v
```

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

In `runner.py`, add timing around prompt construction and scoring:
```python
import time
prompt_build_start = time.monotonic()
# ... prompt building code ...
prompt_build_ms = (time.monotonic() - prompt_build_start) * 1000

score_start = time.monotonic()
score = task.score_response(response)
scoring_ms = (time.monotonic() - score_start) * 1000
```

Replace `metrics={}` on lines 263 and 631 with:
```python
metrics={"scoring_ms": round(scoring_ms, 2), "prompt_build_ms": round(prompt_build_ms, 2)}
```

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_runner.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Are BOTH `metrics={}` locations (lines 263 and 631) updated? If only one is updated, some code paths will still return empty metrics.
- Check: Is `time.monotonic()` used (not `time.time()`)? `monotonic()` is correct for measuring elapsed time; `time()` can go backward with NTP adjustments.
- Check: Are the timing variables (`prompt_build_start`, `scoring_ms`) initialized in the right scope? They must be defined before the try/except blocks that wrap prompt building and scoring.
- Check: Is `round(scoring_ms, 2)` sufficient precision? Sub-millisecond tasks will round to 0.0 — is this acceptable?
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works via the runner module

```bash
uv run pytest agent-evals/tests/test_runner.py -v -k "not slow"
# Also: confirm import chain has no circular imports
uv run python -c "from agent_evals.runner import EvalRunner; print('Import OK')"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/runner.py agent-evals/tests/test_runner.py
git commit -m "fix(runner): populate TrialResult.metrics with timing data (E6)"
```

---

### Task 28: Filter NaN in bootstrap_ci (E7 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/scoring.py:257-318`
- Test: `agent-evals/tests/test_scoring.py`

> **Context:**
> ```python
> from agent_evals.scoring import bootstrap_ci, BootstrapResult
> ```

**Step 1 [RED]:** Write the failing test

```python
def test_bootstrap_ci_handles_nan_without_producing_nan_output():
    import math
    data = [0.5, 0.6, float("nan"), 0.7, 0.8]
    result = bootstrap_ci(data)
    assert not math.isnan(result.low), "CI low must not be NaN"
    assert not math.isnan(result.high), "CI high must not be NaN"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_scoring.py::test_bootstrap_ci_handles_nan_without_producing_nan_output -v
```

**Step 3 [GREEN]:** Write the minimal implementation to make the test pass

Before the `np.asarray` line in `bootstrap_ci`:
```python
clean = [x for x in data if not (isinstance(x, float) and np.isnan(x))]
if len(clean) < 2:
    return BootstrapResult(low=float("nan"), high=float("nan"), n_valid=len(clean))
# use `clean` in np.asarray instead of `data`
arr = np.asarray(clean, dtype=np.float64)
```

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_scoring.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Does `BootstrapResult` have an `n_valid` field? If it doesn't, add it — or remove the `n_valid=` kwarg from the fallback return.
- Check: Is the `len(clean) < 2` threshold correct? Bootstrap CI requires at least 2 samples; with exactly 1 sample the CI would have zero width — returning NaN for 0 or 1 valid samples is correct.
- Check: Does `isinstance(x, float) and np.isnan(x)` handle numpy float64 NaN values correctly? `np.float64` is not a Python `float` — use `np.isnan(x)` alone to handle both Python and numpy NaN.
- Check: Is the clean data filter placed before any other computation that might touch `data` directly?
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works via the scoring module

```bash
uv run python -c "
import math
from agent_evals.scoring import bootstrap_ci
data = [0.5, 0.6, float('nan'), 0.7, 0.8]
result = bootstrap_ci(data)
print(f'low={result.low:.3f}, high={result.high:.3f}')
assert not math.isnan(result.low), 'CI low is NaN'
assert not math.isnan(result.high), 'CI high is NaN'
print('NaN filtering verified')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/scoring.py agent-evals/tests/test_scoring.py
git commit -m "fix(scoring): filter NaN values before bootstrap_ci computation (E7)"
```

---

### Task 29: Add base_task_id to robustness task metadata (E8 — LOW)

**Files:**
- Modify: `agent-evals/gold_standard/robustness/robustness_*.yaml` (30 files)
- Test: `agent-evals/tests/test_gold_standard_schema.py` (add to existing)

> **Context:** Robustness tasks are standalone hand-authored files — no source task in gold_standard/.
> `base_task_id` must be `""` (empty string) for all 30. The `RobustnessTask` class reads it as
> `meta.get("base_task_id", "")` so empty string is the correct sentinel.
> Fix script: `scripts/add_robustness_base_task_ids.py` (run once, delete after).

**Step 1 [RED]:** Check actual task ID format first, then write the failing test

```bash
ls agent-evals/gold_standard/robustness/ | head -5
```

Note the exact filename pattern (e.g., `robustness_001.yaml`) before writing the script. Then add this test to `test_gold_standard_schema.py`:

```python
def test_all_robustness_tasks_have_base_task_id():
    """Every robustness task must have base_task_id in metadata."""
    tasks = load_tasks_from_dir("agent-evals/gold_standard/robustness/")
    missing = [t["task_id"] for t in tasks if "base_task_id" not in t.get("metadata", {})]
    assert not missing, f"Missing base_task_id in {len(missing)} tasks: {missing[:5]}"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_gold_standard_schema.py::test_all_robustness_tasks_have_base_task_id -v
```

**Step 3 [GREEN]:** Run the fix script

These 30 robustness tasks are hand-authored standalones — they were NOT generated from
existing gold standard tasks. Cross-referencing `original_question` against every other
gold standard task confirmed zero matches. Therefore `base_task_id` is `""` (empty string)
for all 30, signalling "standalone — no source task". The `RobustnessTask` class reads this
field with `meta.get("base_task_id", "")`, so empty string is the correct sentinel value.

```python
# scripts/add_robustness_base_task_ids.py (run once, then delete)
import yaml
from pathlib import Path

gold_dir = Path("agent-evals/gold_standard/robustness")
updated = 0
for f in sorted(gold_dir.glob("robustness_*.yaml")):
    data = yaml.safe_load(f.read_text())
    if "base_task_id" not in data.get("metadata", {}):
        # Empty string = standalone (no source task exists in gold_standard/)
        data.setdefault("metadata", {})["base_task_id"] = ""
        f.write_text(yaml.safe_dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False))
        updated += 1
print(f"Updated {updated} files — base_task_id='' added to all standalone robustness tasks")
```

Run it:
```bash
uv run python scripts/add_robustness_base_task_ids.py
```

**Review the diff manually:**
```bash
git diff agent-evals/gold_standard/robustness/ | head -60
# Expected: each file gains exactly one new line: `base_task_id: ''`
```

**Step 4 [GREEN]:** Run test to verify

```bash
uv run pytest agent-evals/tests/test_gold_standard_schema.py -v
```

**Step 5 [REFACTOR]:** Review the data changes while keeping tests green

- Check: Does `git diff` show exactly one new `base_task_id: ''` line per file — nothing else changed?
- Check: Does `yaml.safe_dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False)` preserve the original YAML key order?
- Check: Are any existing `base_task_id` values being overwritten by the script? The `if "base_task_id" not in` guard prevents this, but verify.
- Check: Is the fix script deleted after running? It should not be committed.
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Load the data through the CLI to confirm no validation errors

```bash
uv run python -c "
from agent_evals.tasks.loader import load_tasks_from_dir
tasks = load_tasks_from_dir('agent-evals/gold_standard/robustness/')
missing = [t.definition.task_id for t in tasks if 'base_task_id' not in (t.definition.metadata or {})]
print(f'{len(tasks)} robustness tasks loaded — {len(missing)} missing base_task_id')
assert not missing, f'Still missing: {missing[:5]}'
print('All robustness tasks have base_task_id')
"
```

**Step 7: Commit**

```bash
git add agent-evals/gold_standard/robustness/
git commit -m "fix(data): add base_task_id to all 30 robustness task metadata files (E8)"
```

---

### Task 40: Activate LLM-as-judge as 2% validation sample (S6 — LOW)

> Place in Sprint 7 after all scorer fixes are complete. Phase 1 only — zero additional cost at scale.

**Files:**
- Modify: `agent-evals/src/agent_evals/runner.py`
- Test: `agent-evals/tests/test_runner.py`

> **Context:**
> ```python
> from agent_evals.runner import EvalRunner, EvalRunConfig
> # EvalRunner(client, config=config) — client is FIRST positional arg
> # EvalRunConfig fields: repetitions, max_connections, max_tasks, temperature,
> #   max_tokens, use_cache, cache_dir, output_dir, output_format, display_mode, continue_on_error
> # Test helpers (already in test_runner.py): _make_mock_task(), _make_mock_variant(),
> #   _make_mock_client(), _make_sample_doc_tree()
> config = EvalRunConfig(use_cache=False)
> runner = EvalRunner(_make_mock_client(), config=config)
> ```

**Step 1 [RED]:** Write the failing test

> **⚠️ ARCHITECTURE WARNING — Read before writing any code:**
>
> The test below references APIs that do NOT exist:
> - `runner.run_batch()` — no such method; `EvalRunner.run()` is the top-level entry point
> - `make_trial_spec(index=i)` — no such helper in test_runner.py
> - `make_test_config(sample_judge_rate=50)` — `sample_judge_rate` is not an existing `EvalRunConfig` field
> - `trial_index` is not available inside the concurrent ThreadPoolExecutor loop
>
> **Before implementing,** read `runner.py` lines 230-260 and determine where to hook in:
> - `_run_trial()` is called concurrently — add a `trial_index: int` param there, OR
> - Track a thread-safe counter in the `EvalRunner` and pass it through, OR
> - Move sampling to the orchestrator where sequential indexing is easier
>
> The test must be adapted to match whichever approach is chosen. Below is the intent — adjust the test API to match the real runner:

```python
def test_judge_score_sampled_into_metrics(monkeypatch):
    """When JUDGE_SAMPLE_RATE is set, every Nth trial must have judge_score in its metrics."""
    from agent_evals.judge.calibrator import JudgeScore
    mock_judge_score = JudgeScore(
        example_id="test", judge_model="mock", score=0.8,
        rationale="good", raw_response="Score: 0.8\nRationale: good",
    )
    monkeypatch.setattr(
        # _call_judge is an INSTANCE METHOD on EvalRunner, not a module-level function
        "agent_evals.runner.EvalRunner._call_judge",
        lambda self, task_type, question, response: mock_judge_score,
    )
    # EvalRunConfig has NO model/task_types fields — use actual runner config fields only
    # EvalRunner takes client as FIRST positional arg, not keyword
    task = _make_mock_task()
    variant = _make_mock_variant()
    doc_tree = _make_sample_doc_tree()
    client = _make_mock_client()
    config = EvalRunConfig(use_cache=False)   # no model/task_types — those are CLI-level
    runner = EvalRunner(client, config=config)  # client is FIRST positional arg
    # Run enough trials that at least one hits the sampling rate (JUDGE_SAMPLE_RATE=50)
    # NOTE: _run_trial() returns metrics={} by default — Step 3 must change that
    # NOTE: After adding trial_index param in Step 3, this call MUST include trial_index=i
    results = [runner._run_trial(task, variant, doc_tree, repetition=i, trial_index=i) for i in range(1, 55)]
    judged = [r for r in results if "judge_score" in r.metrics]
    assert len(judged) >= 1, "At least one trial must be judge-sampled"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_runner.py::test_judge_score_sampled_into_metrics -v
```

**Step 3 [GREEN]:** Implement Phase 1 sampling

Four concrete changes to `agent-evals/src/agent_evals/runner.py`:

**3a. Add two module-level constants** after the existing imports (around line 50, before the
`EvalRunConfig` class):

```python
JUDGE_SAMPLE_RATE = 50  # Call judge for 1 in every 50 trials (2%)
JUDGE_MODEL = "openrouter/openai/gpt-4o-mini"  # Cheap grading model
```

**3b. Add `_call_judge` as a private instance method on `EvalRunner`** — place it immediately
before `_run_trial` (currently around line 516). It MUST be on the class (not module-level)
because it needs `self._client`. Add this entire method:

```python
def _call_judge(self, task_type: str, question: str, response: str) -> "JudgeScore":
    """Call LLM judge to score one trial response.

    Imports are local to avoid circular import issues.
    - build_judge_prompt() returns list[dict[str,str]] (NOT a str prompt)
    - parse_judge_response() takes a str, returns tuple[float, str]
    - self._client.complete() takes list[dict], returns GenerationResult with .content
    """
    from agent_evals.judge.calibrator import (
        JudgeScore, build_judge_prompt, parse_judge_response,
    )
    messages = build_judge_prompt(
        task_type=task_type,
        question=question,
        response=response,
        rubric=None,
    )
    raw = self._client.complete(messages).content
    score, rationale = parse_judge_response(raw)
    return JudgeScore(
        example_id="",
        judge_model=JUDGE_MODEL,
        score=score,
        rationale=rationale,
        raw_response=raw,
    )
```

**3c. Update `_run_trial` signature** (currently at line 516) — add `trial_index: int = 0`
as the last parameter (default 0 preserves backward compatibility with any existing callers):

```python
def _run_trial(
    self,
    task: EvalTask,
    variant: IndexVariant,
    doc_tree: DocTree,
    repetition: int,
    source: str = "gold_standard",
    trial_index: int = 0,           # ADD THIS LINE
) -> TrialResult:
```

Then find `metrics={}` at line 631 (inside `_run_trial`, in the `return TrialResult(...)` call)
and replace the two lines `metrics={},` with the sampling block:

```python
        metrics: dict[str, object] = {}
        if trial_index > 0 and trial_index % JUDGE_SAMPLE_RATE == 0:
            try:
                judge_result = self._call_judge(
                    task.definition.type,
                    task.definition.question,
                    generation.content,
                )
                metrics["judge_score"] = judge_result.score
                metrics["judge_heuristic_delta"] = abs(judge_result.score - score)
            except Exception:
                pass  # Judge failure must never affect trial outcome

        return TrialResult(
            task_id=task.definition.task_id,
            task_type=task.definition.type,
            variant_name=variant_name,
            repetition=repetition,
            score=score,
            metrics=metrics,          # was metrics={}
            prompt_tokens=generation.prompt_tokens,
            completion_tokens=generation.completion_tokens,
            total_tokens=generation.total_tokens,
            cost=generation.cost,
            latency_seconds=latency,
            response=generation.content,
            cached=cached,
            source=source,
        )
```

**3d. Replace the ThreadPoolExecutor dict comprehension** (lines 236-241 in `run()`) with an
explicit for-loop that tracks `trial_index`. The current code is:

```python
# CURRENT (lines 236-241) — replace this entire block:
future_to_item = {
    executor.submit(
        self._run_trial, task, variant, doc_tree, rep, source
    ): (task, variant, rep)
    for task, variant, rep in work_items
}
```

Replace with:

```python
# REPLACEMENT — enumerates work_items so trial_index is available:
future_to_item = {}
for idx, (task, variant, rep) in enumerate(work_items, 1):
    future = executor.submit(
        self._run_trial, task, variant, doc_tree, rep, source, trial_index=idx
    )
    future_to_item[future] = (task, variant, rep)
```

`enumerate(work_items, 1)` starts at 1, so `idx=50` is the first multiple of
`JUDGE_SAMPLE_RATE=50` that triggers judging.

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_runner.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Are `JUDGE_SAMPLE_RATE = 50` and `JUDGE_MODEL = "openrouter/openai/gpt-4o-mini"` module-level constants (not hardcoded inline)?
- Check: Is the judge call wrapped in a broad `except Exception: pass` to ensure judge failures never affect trial outcomes? Confirm the exception is swallowed, not re-raised.
- Check: Is `_call_judge` an instance method on `EvalRunner` (not a module-level function)? The monkeypatch in the test targets `EvalRunner._call_judge` — confirm the location.
- Check: Does the `trial_index=0` default in `_run_trial` mean the first trial (index 0) never calls the judge? Since `0 % 50 == 0`, a guard `trial_index > 0` is needed to prevent judging trial 0.
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the framework works end-to-end

```bash
uv run pytest agent-evals/tests/test_runner.py -v -k "not slow"
# Also: confirm import chain has no circular imports
uv run python -c "from agent_evals.runner import EvalRunner; print('Import OK')"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/runner.py agent-evals/tests/test_runner.py
git commit -m "feat(runner): activate LLM-as-judge as 2% validation sample in trial metrics (S6)"
```

---

## Sprint 8 — Infrastructure: Logging + Model Catalog (I7, I8)

---

### Task 30: Add rotating file logging (I7 — LOW)

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/logging_config.py`
- Modify: `agent-evals/src/agent_evals/observatory/web/routes.py` (call in lifespan)
- Test: `agent-evals/tests/test_observatory_logging_config.py` (**create new file**)

**Step 0: Create the test file**

`agent-evals/tests/test_observatory_logging_config.py` does not yet exist. Create it with:
```python
"""Tests for Observatory logging configuration."""
import logging
import pytest
from pathlib import Path
```

**Step 1 [RED]:** Write the failing test

```python
def test_setup_logging_creates_log_file_on_first_write(tmp_path):
    from agent_evals.observatory.logging_config import setup_logging
    import logging
    setup_logging(log_dir=tmp_path)
    logger = logging.getLogger("agent_evals")
    logger.info("test message")
    for handler in logger.handlers:
        handler.flush()
    # File must exist after a real write
    assert (tmp_path / "observatory.log").exists()
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_observatory_logging_config.py::test_setup_logging_creates_log_file_on_first_write -v
```
Expected: `ModuleNotFoundError: No module named 'agent_evals.observatory.logging_config'`

**Step 3 [GREEN]:** Create logging_config.py

```python
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        })


def setup_logging(log_dir: Path, level: str = "INFO") -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "observatory.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    handler.setFormatter(_JSONFormatter())
    root = logging.getLogger("agent_evals")
    root.setLevel(getattr(logging, level.upper()))
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        root.addHandler(handler)
```

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_observatory_logging_config.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green

- Check: Does the `if not any(isinstance(h, RotatingFileHandler) ...)` guard prevent duplicate handlers if `setup_logging` is called multiple times? Test this scenario.
- Check: Is the `_JSONFormatter` class private (underscore prefix) to prevent accidental direct use? Good — keep it internal.
- Check: Is `maxBytes=10 * 1024 * 1024` (10MB) and `backupCount=5` appropriate for the production use case (50MB max total)?
- Check: Is `setup_logging` called in `routes.py` lifespan at the correct point (before any logging calls, at startup)?
- Check: Is the test cleaning up logging handlers after running (to prevent handler leakage between tests)? Consider adding a `yield` fixture that removes the handlers after the test.
- Run the full test suite to confirm nothing regressed:
  ```bash
  uv run pytest agent-evals/tests/ -x -q
  ```

**Step 6 [VERIFY]:** Confirm the fix works via the logging module

```bash
uv run python -c "
import pathlib, tempfile, logging
from agent_evals.observatory.logging_config import setup_logging
tmp = pathlib.Path(tempfile.mkdtemp())
setup_logging(log_dir=tmp)
logger = logging.getLogger('agent_evals')
logger.info('test message from VERIFY step')
for handler in logger.handlers:
    handler.flush()
log_file = tmp / 'observatory.log'
assert log_file.exists(), 'Log file not created'
print('Log file contents:', log_file.read_text()[:200])
print('Logging setup verified')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/logging_config.py \
        agent-evals/src/agent_evals/observatory/web/routes.py \
        agent-evals/tests/test_observatory_logging_config.py
git commit -m "feat(infra): add rotating JSON file logging to Observatory (I7)"
```

---

### Task 31: Auto-sync model catalog on server startup (I8 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/web/server.py` (NOT routes.py)
- Test: `agent-evals/tests/test_model_browser_web.py` (add to existing file)

> **Context:**
> ```python
> from agent_evals.observatory.model_catalog import ModelCatalog
> from agent_evals.observatory.model_sync import ModelSync
> catalog = ModelCatalog(tmp_path / "models.db")
> sync = ModelSync(catalog=catalog)
> # Sync method: model_sync.run_sync() — returns a SyncResult dataclass
> # ModelCatalog has NO sync() method — always go through ModelSync.run_sync()
> ```

**Architecture note:** The startup sync lives in `server.py`'s `create_app()` — NOT in `routes.py`.
`create_app()` already accepts `model_sync: ModelSync | None` and passes it to `create_router()`.
The sync call belongs in a FastAPI `lifespan` on the app, not the router.

The sync method is `model_sync.run_sync()` (on the `ModelSync` class, NOT on `ModelCatalog`).
`ModelCatalog` has no sync method — `ModelSync` is the sync coordinator.

`launch_dashboard()` (lines 102-105 of `server.py`) already calls `model_sync.run_sync()` but
only when the catalog is empty. This task moves that call into a lifespan so it runs on
every startup, then removes the old conditional from `launch_dashboard()`.

**Step 1 [RED]:** Write the failing test

Add this class to `agent-evals/tests/test_model_browser_web.py` (after the existing imports):

```python
from unittest.mock import MagicMock

class TestStartupSync:
    """ModelSync.run_sync() is called during server startup lifespan."""

    def test_model_sync_run_sync_called_on_startup(self, tmp_path: Path) -> None:
        store = ObservatoryStore(tmp_path / "obs.db")
        tracker = EventTracker(store=store)
        catalog = ModelCatalog(tmp_path / "models.db")
        mock_sync = MagicMock(spec=ModelSync)   # run_sync() is a method on ModelSync

        app = create_app(
            store=store, tracker=tracker, catalog=catalog, model_sync=mock_sync
        )
        with TestClient(app):           # TestClient triggers the lifespan startup
            mock_sync.run_sync.assert_called_once()
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (not an import error or wrong exception)

```bash
uv run pytest agent-evals/tests/test_model_browser_web.py::TestStartupSync -v
```

Expected: FAIL — `run_sync` never called (no lifespan yet).

**Step 3 [GREEN]:** Add lifespan to `create_app()` in `server.py`

Add two imports at the top of `server.py` (after the existing `import threading`):

```python
import asyncio
from contextlib import asynccontextmanager
```

Then replace the `def create_app(...)` function body's first line (`app = FastAPI(...)`) with:

```python
def create_app(
    store: ObservatoryStore,
    tracker: EventTracker,
    catalog: ModelCatalog | None = None,
    group_manager: ModelGroupManager | None = None,
    model_sync: ModelSync | None = None,
    run_manager: RunManager | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if model_sync is not None:
            try:
                await asyncio.to_thread(model_sync.run_sync)
                logger.info("Model catalog synced on startup")
            except Exception as exc:
                logger.warning("Model catalog sync failed on startup: %s", exc)
        yield   # Application serves requests here

    app = FastAPI(title="Observatory Dashboard", lifespan=lifespan)
    # ... rest of create_app() is UNCHANGED
```

Also remove the now-redundant conditional from `launch_dashboard()` (lines 102-105):

```python
# DELETE these 4 lines from launch_dashboard():
if config.auto_sync and not catalog.get_active_models():
    logger.info("Model catalog empty — running initial sync")
    model_sync.run_sync()
```

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
uv run pytest agent-evals/tests/test_model_browser_web.py -v
```

**Step 5 [REFACTOR]:** Review the implementation while keeping tests green
- `lifespan` is a closure over `model_sync` — no need to store it as an attribute
- `asyncio.to_thread()` wraps the blocking `run_sync()` call correctly — no `await model_sync.run_sync()` needed since it's synchronous
- The old conditional in `launch_dashboard()` is fully removed — no duplicate sync calls
- Exception from `run_sync()` is caught and logged as a warning, not re-raised (startup continues even if sync fails)

**Step 6 [VERIFY]:** Confirm the lifespan wiring works end-to-end

```bash
uv run python -c "
from unittest.mock import MagicMock
import pathlib, tempfile
from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker
from agent_evals.observatory.model_catalog import ModelCatalog, ModelSync
from agent_evals.observatory.web.server import create_app
from fastapi.testclient import TestClient

tmp = pathlib.Path(tempfile.mkdtemp())
store = ObservatoryStore(tmp / 'obs.db')
tracker = EventTracker(store=store)
catalog = ModelCatalog(tmp / 'models.db')
mock_sync = MagicMock(spec=ModelSync)

app = create_app(store=store, tracker=tracker, catalog=catalog, model_sync=mock_sync)
with TestClient(app):
    mock_sync.run_sync.assert_called_once()
print('model_sync.run_sync called once on startup — PASS')
"
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/server.py \
        agent-evals/tests/test_model_browser_web.py
git commit -m "feat(infra): auto-sync model catalog on server startup via FastAPI lifespan (I8)"
```

---

## Sprint 9 — UX Polish + Data Quality (U1–U3, D3)

---

### Task 32: Add chart animation defaults (U1 — LOW)

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/web/ui/src/utils/chartDefaults.ts`
- Modify: `Observatory.tsx`, `LiveMonitor.tsx`, `ResultsExplorer.tsx`, `History.tsx`, `FactorAnalysis.tsx`
- Test: add to relevant chart component tests

> **Context:** TypeScript/Vitest frontend tests in `agent-evals/src/agent_evals/observatory/web/ui/`.
> Run tests: `npm test` from the `ui/` directory. Build: `npm run build`.
> All chart/component tests import from `../../utils/chartDefaults` or `../../components/`.

**Step 1 [RED]:** Write the failing test

> **Note:** `vi.spyOn(Chart, "constructor")` will NOT work — Chart.js is mocked at module level in this project, making constructor spying incompatible. Instead, test the `CHART_ANIMATION` constant directly (simpler and more reliable). Check `vitest.setup.ts` or existing chart tests to see how Chart.js is mocked before writing component-level tests.

```typescript
// Option A (preferred): Test the constant directly — no Chart.js mocking needed
import { CHART_ANIMATION } from "../utils/chartDefaults";

it("CHART_ANIMATION has duration 800 and easeOutQuart easing", () => {
  expect(CHART_ANIMATION.duration).toBe(800);
  expect(CHART_ANIMATION.easing).toBe("easeOutQuart");
});

// Option B (component-level): Check that Chart.defaults is applied
// (only viable if existing tests already show how to access Chart.defaults with the mock in place)
// it("chart defaults are applied on Observatory mount", () => {
//   render(<Observatory />);
//   expect(Chart.defaults.animation).toEqual(expect.objectContaining({ duration: 800 }));
// });
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure is the RIGHT error (module not found, or constant undefined), not a syntax error

```bash
cd agent-evals/src/agent_evals/observatory/web/ui
npm test -- --testPathPattern=Observatory
```

**Step 3 [GREEN]:** Create chartDefaults.ts

```typescript
export const CHART_ANIMATION = {
  duration: 800,
  easing: "easeOutQuart" as const,
} as const;
```

Apply to all chart option objects in the 5 pages listed above.

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
npm test
```

**Step 5 [REFACTOR]:** Review the implementation
- `chartDefaults.ts` is a single-purpose utility — all chart pages import from it (no duplication)
- Confirm `as const` is used on both the inner object and the export so TypeScript infers the literal types
- Verify none of the 5 pages still have inline `animation: { duration: ... }` objects

**Step 6 [VERIFY]:** Build check to confirm no TypeScript errors introduced

```bash
cd agent-evals/src/agent_evals/observatory/web/ui
npm run build 2>&1 | tail -5
npm test -- --reporter=verbose 2>&1 | tail -20
# Expected: build succeeds with 0 errors; all chart-related tests pass
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/utils/chartDefaults.ts \
        agent-evals/src/agent_evals/observatory/web/ui/src/pages/
git commit -m "feat(ux): add 800ms easeOutQuart chart animation to all chart views (U1)"
```

---

### Task 33: Clean up CompassCheckbox inline CSS (U2 — TRIVIAL)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/web/ui/src/components/CompassCheckbox.tsx`
- Test: component tests

> **Context:** TypeScript/Vitest frontend tests in `agent-evals/src/agent_evals/observatory/web/ui/`.
> Run tests: `npm test` from the `ui/` directory. Build: `npm run build`.
> All chart/component tests import from `../../utils/chartDefaults` or `../../components/`.

**Step 1 [RED]:** Read the file first, then write the failing test

```bash
cat agent-evals/src/agent_evals/observatory/web/ui/src/components/CompassCheckbox.tsx
```

Identify any remaining `style={{...}}` attributes on SVG elements (the file is ~61 lines).

```typescript
it("CompassCheckbox has no inline style attributes on any element", () => {
  const { container } = render(<CompassCheckbox checked={false} onChange={vi.fn()} />);
  const inlineStyled = container.querySelectorAll("[style]");
  expect(inlineStyled.length).toBe(0);
});
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure shows `inlineStyled.length` > 0, not a render error

```bash
npm test -- --testPathPattern=CompassCheckbox
```

**Step 3 [GREEN]:** Move any remaining inline styles to Tailwind classes

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
npm test -- --testPathPattern=CompassCheckbox
```

**Step 5 [REFACTOR]:** Review the implementation
- All `style={{...}}` attributes removed — confirmed by the test assertion
- Tailwind classes used instead (e.g. `fill-current`, `w-4 h-4`, `opacity-0`)
- No new class names that duplicate existing Tailwind utilities

**Step 6 [VERIFY]:** Build check to confirm no TypeScript or CSS errors

```bash
cd agent-evals/src/agent_evals/observatory/web/ui
npm run build 2>&1 | tail -5
npm test -- --reporter=verbose 2>&1 | tail -20
# Expected: build succeeds; CompassCheckbox test reports 0 inline-styled elements
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/components/CompassCheckbox.tsx
git commit -m "fix(ux): remove remaining inline styles from CompassCheckbox (U2)"
```

---

### Task 34: Add focus-visible style to SlideOutPanel close button (U3 — TRIVIAL)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/web/ui/src/components/SlideOutPanel.tsx:45`
- Test: component tests

> **Context:** TypeScript/Vitest frontend tests in `agent-evals/src/agent_evals/observatory/web/ui/`.
> Run tests: `npm test` from the `ui/` directory. Build: `npm run build`.
> All chart/component tests import from `../../utils/chartDefaults` or `../../components/`.

**Step 1 [RED]:** Write the failing test

```typescript
// SlideOutPanel props: { open: boolean, onClose: () => void, title: string, children }
// NOT isOpen — the actual prop is `open`. Also `title` is REQUIRED.
// Dialog.Close renders a Radix UI button — it IS queryable via getByRole("button").
it("SlideOutPanel close button has focus-visible styling", () => {
  const { getByRole } = render(
    <SlideOutPanel open onClose={vi.fn()} title="Test Panel">content</SlideOutPanel>
  );
  // Dialog.Close renders as a <button> — accessible via role "button"
  const closeBtn = getByRole("button");
  expect(closeBtn.className).toMatch(/focus-visible/);
});
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure shows `className` does not match `/focus-visible/`, not a render error

```bash
npm test -- --testPathPattern=SlideOutPanel
```

**Step 3 [GREEN]:** Add focus-visible classes to the close button

```tsx
<button
  onClick={onClose}
  className="... focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
>
```

**Step 4 [GREEN]:** Run to confirm tests pass

```bash
npm test -- --testPathPattern=SlideOutPanel
```

**Step 5 [REFACTOR]:** Review the implementation
- The `focus-visible:` prefix ensures the outline only appears on keyboard focus (not mouse click)
- `outline-ring` uses the design token — not a hardcoded color
- `outline-offset-2` ensures the outline doesn't overlap the button border

**Step 6 [VERIFY]:** Build check and full test run

```bash
cd agent-evals/src/agent_evals/observatory/web/ui
npm run build 2>&1 | tail -5
npm test -- --reporter=verbose 2>&1 | tail -20
# Expected: build succeeds; SlideOutPanel test reports className matches /focus-visible/
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/components/SlideOutPanel.tsx
git commit -m "fix(a11y): add focus-visible outline to SlideOutPanel close button (U3)"
```

---

### Task 35: Add SSE event sequence numbers (D3 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/web/routes.py` (SSE generator)
- Modify: `agent-evals/src/agent_evals/observatory/web/ui/src/hooks/useSSE.ts`
- Test: both backend and frontend tests

> **Context:**
> ```python
> from fastapi.testclient import TestClient
> from agent_evals.observatory.web.server import create_app
> from agent_evals.observatory.store import ObservatoryStore
> from agent_evals.observatory.tracker import EventTracker
> # SSE endpoint: GET /api/runs/{run_id}/stream
> # Sequence numbers are module-level state in routes.py — reset between tests
> ```

> **Note:** The sequence counter is module-level and resets on server restart. After a restart, clients that see ID 1 again will correctly treat it as fresh (their `lastEventId` ref is per-session). This is acceptable behavior.

**Step 1 [RED]:** Write the failing test (backend)

```python
def test_sse_events_include_monotonic_id(client):
    with client.stream("GET", f"/api/runs/run1/stream") as resp:
        lines = list(itertools.islice(resp.iter_lines(), 20))
    id_lines = [l for l in lines if l.startswith("id:")]
    assert len(id_lines) > 0, "SSE events must include id: fields"
    ids = [int(l.split(":")[1].strip()) for l in id_lines]
    assert ids == sorted(ids), "SSE event IDs must be monotonically increasing"
```

**Step 2 [RED]:** Run to confirm it fails — verify the failure shows `len(id_lines) == 0` (no `id:` lines emitted), not a connection error

```bash
uv run pytest agent-evals/tests/test_observatory_web.py::test_sse_events_include_monotonic_id -v
```

**Step 3 [GREEN]:** Add sequence counter to SSE generator in routes.py and deduplication in useSSE.ts

```python
import itertools
_sse_seq = itertools.count(1)

# In each SSE yield:
{"event": event_type, "id": str(next(_sse_seq)), "data": json.dumps(data)}
```

> **IMPORTANT:** `useSSE.ts` already has existing `addEventListener` handlers for `trial_completed` and other events (see lines 48-65). Do NOT add a second, separate `addEventListener` call. Instead, add the deduplication guard at the TOP of the existing `trial_completed` handler body.

```typescript
// Add ONCE at the hook level (inside useEffect, before the EventSource creation):
const lastEventIdRef = useRef(0);

// Then INSIDE the existing trial_completed addEventListener handler, add at the TOP:
source.addEventListener("trial_completed", (e: MessageEvent) => {
  // --- Deduplication guard (add this block at the start) ---
  const eventId = parseInt(e.lastEventId, 10);
  if (!isNaN(eventId) && eventId <= lastEventIdRef.current) return;
  lastEventIdRef.current = eventId;
  // --- End guard --- then the existing JSON.parse + dispatch logic follows unchanged
  // ... existing handler content here
});
```

**Step 4 [GREEN]:** Run both test suites to confirm they pass

```bash
uv run pytest agent-evals/tests/test_observatory_web.py -v
cd agent-evals/src/agent_evals/observatory/web/ui && npm test -- --testPathPattern=useSSE
```

**Step 5 [REFACTOR]:** Review the implementation
- `_sse_seq = itertools.count(1)` is module-level — resets on server restart (acceptable, documented in task note above)
- The deduplication guard uses `<=` (not `<`) so a repeated ID at the same value is also dropped
- `lastEventIdRef` is inside the `useEffect` closure — it is NOT shared across hook instances, which is correct
- Confirm the `id:` field is emitted on every SSE event type (not just `trial_completed`)

**Step 6 [VERIFY]:** Smoke test both layers

```bash
# Backend: confirm id: lines present and monotonic
uv run python -c "
import itertools, httpx
# Use TestClient for a quick sync check
from fastapi.testclient import TestClient
from agent_evals.observatory.web.server import create_app
client = TestClient(create_app())
with client.stream('GET', '/api/runs/run1/stream') as resp:
    lines = list(itertools.islice(resp.iter_lines(), 20))
id_lines = [l for l in lines if l.startswith('id:')]
print(f'id: lines found: {len(id_lines)}')
ids = [int(l.split(':')[1].strip()) for l in id_lines]
print(f'monotonic: {ids == sorted(ids)}, values: {ids[:5]}')
"

# Frontend: confirm deduplication guard present in build
cd agent-evals/src/agent_evals/observatory/web/ui
npm run build 2>&1 | tail -5
npm test -- --reporter=verbose 2>&1 | tail -20
# Expected: build succeeds; useSSE tests pass with deduplication working
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/routes.py \
        agent-evals/src/agent_evals/observatory/web/ui/src/hooks/useSSE.ts \
        agent-evals/tests/test_observatory_web.py
git commit -m "fix(sse): add event sequence IDs to prevent duplicate counting on reconnect (D3)"
```

---

## Sprint 10 — React Router Warning (W1)

> **Note on task numbering:** Task 36 was removed during plan consolidation. Tasks continue at 37.

---

### Task 37: Opt into React Router v7 future flags (W1 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/web/ui/src/main.tsx` (or wherever the router is created)

> **Context:** TypeScript/Vitest frontend tests in `agent-evals/src/agent_evals/observatory/web/ui/`.
> Run tests: `npm test` from the `ui/` directory. Build: `npm run build`.
> All chart/component tests import from `../../utils/chartDefaults` or `../../components/`.

**Step 1 [RED]:** Locate the router creation and write a test asserting the future flags are set

```bash
grep -r "createBrowserRouter\|BrowserRouter" agent-evals/src/agent_evals/observatory/web/ui/src/ --include="*.tsx"
```

Because `createBrowserRouter` is a configuration call (not a function with testable output), the "test" here is a build-time TypeScript check: adding flags that do not exist in the types will cause a compile error. Confirm that `npm run build` currently does NOT complain about missing flags (i.e. the property exists in the type) and that the flags are NOT yet set (the warning is currently visible in the dev console).

**Step 2 [RED]:** Confirm the warning is currently present

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npm run build 2>&1 | grep -i "router\|warning" | head -5
# Expected before fix: React Router future flag warnings printed to stderr
```

**Step 3 [GREEN]:** Add future flags to the router creation call

```typescript
createBrowserRouter(routes, {
  future: {
    v7_startTransition: true,
    v7_relativeSplatPath: true,
  },
})
```

**Step 4 [GREEN]:** Rebuild to confirm TypeScript accepts the flags and no new errors introduced

```bash
npm run build 2>&1 | tail -5
```

**Step 5 [REFACTOR]:** Review the implementation
- Both `v7_startTransition` and `v7_relativeSplatPath` are set — these are the two flags that silence the React Router v6→v7 migration warnings
- No other router options changed
- If a test file mocks `createBrowserRouter`, verify the mock still typechecks

**Step 6 [VERIFY]:** Full test suite and build check

```bash
cd agent-evals/src/agent_evals/observatory/web/ui
npm run build 2>&1 | tail -5
npm test -- --reporter=verbose 2>&1 | tail -20
# Expected: build succeeds with 0 errors; no React Router deprecation warnings in output
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/main.tsx
git commit -m "fix(frontend): opt into React Router v7 future flags (W1)"
```

---

## Sprint 11 — Validation: Confirm Scorer Fixes Work (D1, D2)

> **Run after all Sprint 1-3 scorer fixes are committed.** D1 (bimodal distribution) and D2 (compositional underscoring) are caused by scorer bugs — not independent code changes. This sprint validates the fixes actually worked.

---

### Task 41: Re-run compositional evaluation to confirm score distribution improved (D1, D2)

> ⚠️ **HUMAN-ONLY — Do not execute automatically.**
> This task makes live LLM API calls, costs real money (~$2–5), and takes 10–30 minutes.
> Execute manually only after ALL of Tasks 1–11 are complete and their unit tests pass.
> An automated agent must skip this task entirely.

**This requires a live LLM call (not `--dry-run`).**

**Step 1 [RED]:** Establish the pre-fix baseline — confirm current scores are still broken

```bash
echo $OPENROUTER_API_KEY | head -c 20
# Confirm key is set before proceeding
```

The "failing test" here is the known bad distribution: mean ~0.114 and ~70% zero-score rate from Sprint 1-3 bugs. If you have not yet run all scorer fixes (Tasks 1-11), stop and complete those first.

**Step 2 [RED]:** Document expected failure criteria before running

- Mean score < 0.30 = FAIL (still broken)
- Zero rate > 30% = FAIL (still broken)

**Step 3 [GREEN]:** Run a real evaluation on 100 compositional trials after all scorer fixes are applied

```bash
uv run agent-evals \
  --model openrouter/anthropic/claude-haiku-4-5-20251001 \
  --task-types compositional \
  --task-limit 100 \
  --output-format json \
  --output-path /tmp/compositional_validation.json
```

**Step 4 [GREEN]:** Check mean score and zero rate against expected outcomes

```bash
uv run python -c "
import json
data = json.load(open('/tmp/compositional_validation.json'))
scores = [t['score'] for t in data['trials']]
zeros = sum(1 for s in scores if s == 0.0)
mean = sum(scores)/len(scores)
zero_rate = zeros/len(scores)
print(f'Mean: {mean:.3f}  (must be > 0.30, was 0.114)')
print(f'Zero rate: {zeros}/{len(scores)} = {zero_rate:.1%}  (must be < 30%, was 70%)')
assert mean > 0.30, f'FAIL: mean {mean:.3f} still too low'
assert zero_rate < 0.30, f'FAIL: zero rate {zero_rate:.1%} still too high'
print('PASS: both thresholds met')
"
```

**Expected outcomes:**
- Mean score must be > 0.30 (was 0.114)
- Zero rate must be < 30% (was 70%)

**Step 5 [REFACTOR]:** Sanity-check the result distribution

```bash
uv run python -c "
import json
data = json.load(open('/tmp/compositional_validation.json'))
scores = [t['score'] for t in data['trials']]
buckets = {'0.0': 0, '0.0-0.25': 0, '0.25-0.5': 0, '0.5-0.75': 0, '0.75-1.0': 0, '1.0': 0}
for s in scores:
    if s == 0.0: buckets['0.0'] += 1
    elif s < 0.25: buckets['0.0-0.25'] += 1
    elif s < 0.5: buckets['0.25-0.5'] += 1
    elif s < 0.75: buckets['0.5-0.75'] += 1
    elif s < 1.0: buckets['0.75-1.0'] += 1
    else: buckets['1.0'] += 1
for k, v in buckets.items():
    print(f'  {k}: {v}')
# Expected: distribution should look roughly normal (not bimodal with spike at 0)
"
```

**Step 6 [VERIFY]:** Document results and close the validation

Update `docs/plans/2026-03-02-observatory-known-issues.md` section D1/D2 with the post-fix distribution output from Step 5. Then confirm the unit test suite still passes end-to-end:

```bash
uv run pytest agent-evals/tests/ -v --tb=short 2>&1 | tail -20
# Expected: all tests pass with no regressions from scorer changes
```

---

## Sprint 12 — Dataset Integration & CLI Cleanup

> **Why these are bugs, not features:** The `--source` flag is parsed but its value is never read — the CLI silently ignores it and always loads from `gold_standard/`. Running `agent-evals --source repliqa` produces the same results as `agent-evals`, making the flag a lie. The CLI also has 13 flags that are either completely dead (parsed, never read from `resolved`) or expose Taguchi internals with no sensible user-facing meaning (S/N ratio quality type, ANOVA alpha, OA override). Both issues make the tool misleading and hard to use correctly.

---

### Task 42: Wire `--source` to load from dataset adapters (E9 — HIGH)

**Files:**
- Modify: `agent-evals/src/agent_evals/cli.py` (lines 714–764, the task+doc_tree loading block)
- Modify: `agent-evals/tests/test_evals_cli.py` (new tests for `--source` routing)

> **Context:** The `DatasetCache` class lives in `agent_evals.datasets.cache`:
> ```python
> from agent_evals.datasets.cache import DatasetCache
> cache = DatasetCache()           # defaults to ~/.agent-evals/datasets/
> cache.is_prepared("repliqa")    # bool — True if --prepare-datasets was run
> cache.task_dir("repliqa")       # Path → .../repliqa/tasks/   (YAML files)
> cache.doc_tree_path("repliqa")  # Path → .../repliqa/doc_tree.json
> ```
> Load the DocTree from JSON:
> ```python
> from agent_index.models import DocTree
> doc_tree = DocTree.model_validate_json(cache.doc_tree_path("repliqa").read_text())
> ```
> The fixture fallback:
> ```python
> from agent_evals.fixtures import load_sample_doc_tree
> doc_tree = load_sample_doc_tree()
> ```
> The existing task loader:
> ```python
> from agent_evals.tasks.loader import load_tasks
> tasks = load_tasks(some_dir)   # returns list of task instances
> ```

**Step 1 [RED]:** Write failing tests in `test_evals_cli.py`

```python
class TestSourceRouting:
    """--source flag routes task and doc_tree loading correctly."""

    def test_no_source_loads_gold_standard(self, monkeypatch, tmp_path):
        """When --source is absent, loads from gold_standard dir."""
        gold_dir = tmp_path / "gold_standard"
        gold_dir.mkdir()
        loaded_dirs: list = []

        monkeypatch.setattr(
            "agent_evals.cli.load_tasks",
            lambda d: (loaded_dirs.append(d), [])[1],
        )
        monkeypatch.setattr(
            "agent_evals.cli.load_sample_doc_tree", lambda: object()
        )
        monkeypatch.setattr(
            "agent_evals.cli.Path",
            lambda *a, **kw: gold_dir if "gold_standard" in str(a) else Path(*a, **kw),
        )
        from agent_evals.cli import _run_evaluation
        _run_evaluation({"model": "m", "dry_run": True})
        assert any("gold_standard" in str(d) for d in loaded_dirs)

    def test_source_dataset_loads_from_cache_task_dir(self, monkeypatch, tmp_path):
        """When --source repliqa, tasks come from DatasetCache.task_dir."""
        task_dir = tmp_path / "repliqa" / "tasks"
        task_dir.mkdir(parents=True)
        dt_path = tmp_path / "repliqa" / "doc_tree.json"

        from agent_index.models import DocTree
        from datetime import UTC, datetime
        dt = DocTree(files={}, scanned_at=datetime.now(tz=UTC), source="repliqa", total_tokens=0)
        dt_path.write_text(dt.model_dump_json())

        loaded_dirs: list = []
        monkeypatch.setattr(
            "agent_evals.cli.load_tasks",
            lambda d: (loaded_dirs.append(d), [])[1],
        )

        class FakeCache:
            def is_prepared(self, name): return True
            def task_dir(self, name): return task_dir
            def doc_tree_path(self, name): return dt_path

        monkeypatch.setattr("agent_evals.cli.DatasetCache", lambda: FakeCache())
        from agent_evals.cli import _run_evaluation
        _run_evaluation({"model": "m", "source": "repliqa", "dry_run": True})
        assert task_dir in loaded_dirs

    def test_source_dataset_not_prepared_returns_error(self, monkeypatch):
        """When dataset not prepared, returns exit code 1 with helpful message."""
        class FakeCache:
            def is_prepared(self, name): return False
            def task_dir(self, name): raise AssertionError("should not call task_dir")
            def doc_tree_path(self, name): raise AssertionError("should not call doc_tree_path")

        monkeypatch.setattr("agent_evals.cli.DatasetCache", lambda: FakeCache())
        from agent_evals.cli import _run_evaluation
        result = _run_evaluation({"model": "m", "source": "repliqa"})
        assert result == 1

    def test_source_dataset_loads_correct_doc_tree(self, monkeypatch, tmp_path):
        """When --source repliqa, doc_tree is from cache, NOT load_sample_doc_tree."""
        task_dir = tmp_path / "repliqa" / "tasks"
        task_dir.mkdir(parents=True)
        dt_path = tmp_path / "repliqa" / "doc_tree.json"

        from agent_index.models import DocTree
        from datetime import UTC, datetime
        sentinel_source = "REPLIQA_SENTINEL"
        dt = DocTree(files={}, scanned_at=datetime.now(tz=UTC), source=sentinel_source, total_tokens=0)
        dt_path.write_text(dt.model_dump_json())

        captured_doc_tree: list = []

        class FakeRunner:
            def __init__(self, **kw): pass
            def run(self, tasks, variants, doc_tree, **kw):
                captured_doc_tree.append(doc_tree)
                from agent_evals.runner import EvalResult
                return EvalResult(trials=[], total_cost=0.0, elapsed_seconds=0.0)

        class FakeCache:
            def is_prepared(self, name): return True
            def task_dir(self, name): return task_dir
            def doc_tree_path(self, name): return dt_path

        monkeypatch.setattr("agent_evals.cli.DatasetCache", lambda: FakeCache())
        monkeypatch.setattr("agent_evals.cli.load_tasks", lambda d: [])
        monkeypatch.setattr("agent_evals.cli.EvalRunner", FakeRunner)
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        from agent_evals.cli import _run_evaluation
        _run_evaluation({"model": "m", "source": "repliqa"})
        # Must NOT have called load_sample_doc_tree (sentinel proves we used cache)
        assert captured_doc_tree and captured_doc_tree[0].source == sentinel_source
```

**Step 2 [RED]:** Run to confirm failures

```bash
uv run pytest agent-evals/tests/test_evals_cli.py::TestSourceRouting -v
# Expected: FAIL — source is ignored, always loads gold_standard
```

**Step 3 [GREEN]:** Replace the task+doc_tree loading block in `_run_evaluation` (cli.py lines 714–764)

Replace the current hardcoded block:
```python
    # Load tasks
    gold_standard_dir = Path(__file__).resolve().parent.parent.parent / "gold_standard"
    if not gold_standard_dir.is_dir():
        logger.error("Gold standard directory not found: %s", gold_standard_dir)
        return 1

    tasks = load_tasks(gold_standard_dir)

    ...

    # Load doc_tree
    from agent_evals.fixtures import load_sample_doc_tree

    doc_tree = load_sample_doc_tree()
```

With the new source-aware block:
```python
    from agent_evals.tasks.loader import load_tasks

    source = resolved.get("source") or "gold_standard"

    if source == "gold_standard":
        gold_standard_dir = Path(__file__).resolve().parent.parent.parent / "gold_standard"
        if not gold_standard_dir.is_dir():
            logger.error("Gold standard directory not found: %s", gold_standard_dir)
            return 1
        tasks = load_tasks(gold_standard_dir)
        from agent_evals.fixtures import load_sample_doc_tree
        doc_tree = load_sample_doc_tree()
    else:
        from agent_evals.datasets import load_all as _load_all_datasets
        from agent_evals.datasets.cache import DatasetCache
        from agent_index.models import DocTree

        _load_all_datasets()
        cache = DatasetCache()
        if not cache.is_prepared(source):
            logger.error(
                "Dataset '%s' has not been prepared. Run first:\n"
                "  agent-evals --prepare-datasets %s",
                source, source,
            )
            return 1
        tasks = load_tasks(cache.task_dir(source))
        doc_tree = DocTree.model_validate_json(
            cache.doc_tree_path(source).read_text(encoding="utf-8")
        )
```

> Note: `load_tasks` import is moved inside `_run_evaluation` because it was already imported inside the function for the gold_standard branch. Keep it consistent — move the import to just before the `source` branch (it's already there in the existing code at line 704 in the outer import block).

**Step 4 [GREEN]:** Run tests to confirm they pass

```bash
uv run pytest agent-evals/tests/test_evals_cli.py::TestSourceRouting -v
# Expected: all 4 tests PASS
```

**Step 5 [REFACTOR]:** Review the implementation
- Single `source` value only — no comma-separated mixing. Different datasets have different corpora; mixing would use the wrong doc_tree for half the tasks.
- The error message when not prepared tells the user exactly what command to run.
- `_load_all_datasets()` must be called before `DatasetCache` is queried so adapters register themselves.
- If `source == "gold_standard"` explicitly, uses the fixture (same as no `--source`).

**Step 6 [VERIFY]:** Dry-run smoke test

```bash
# Confirm gold_standard still works (no --source)
uv run agent-evals --model openrouter/anthropic/claude-haiku-4-5-20251001 --dry-run 2>&1 | grep -E "tasks|source|error"
# Expected: no errors, prints task count from gold_standard

# Confirm unprepared dataset gives clear error
uv run agent-evals --model openrouter/anthropic/claude-haiku-4-5-20251001 --source repliqa --dry-run 2>&1
# Expected: "Dataset 'repliqa' has not been prepared. Run first: agent-evals --prepare-datasets repliqa"

# Prepare and confirm it works
uv run agent-evals --prepare-datasets repliqa --dataset-limit 10 2>&1
uv run agent-evals --model openrouter/anthropic/claude-haiku-4-5-20251001 --source repliqa --dry-run 2>&1 | grep -E "tasks|error"
# Expected: loads 10 tasks from repliqa, no errors
```

**Step 7: Commit**

```bash
git add agent-evals/src/agent_evals/cli.py \
        agent-evals/tests/test_evals_cli.py
git commit -m "fix(cli): wire --source to load tasks and doc_tree from dataset cache (E9)"
```

---

### Task 43: Remove dead CLI flags (E10 — MEDIUM)

Removes 7 flags that are either parsed but never read from `resolved`, or are stubs with no implementation. **Does not remove** flags that are genuinely used (`--oa-type`, `--quality-type`, `--alpha`, `--top-k`, `--model-budgets`, `--dataset-cache-dir` — all confirmed read from `resolved` in the evaluation logic).

**Files:**
- Modify: `agent-evals/src/agent_evals/cli.py` (`_add_run_args`, `_CONFIG_KEYS`)
- Modify: `agent-evals/tests/test_evals_cli.py` (remove tests for deleted flags, add tests that deleted flags error)

> **Context:**
> ```python
> from agent_evals.cli import build_parser, _CONFIG_KEYS, resolve_config
> parser = build_parser()
> args = parser.parse_args(["--model", "m"])
> resolved = resolve_config(args, {})
> # After cleanup, these keys must NOT be in resolved or _CONFIG_KEYS:
> # model_config, judge_model, max_cost, confirmation_runs, phase, parent_run
> # --mode must not accept 'factorial'
> ```

**Flags to remove** (7 total — confirmed never read from `resolved`):

| Flag | Evidence it is dead |
|------|---------------------|
| `--model-config` | In `_CONFIG_KEYS` at line 433; `resolved.get("model_config")` appears nowhere in evaluation logic |
| `--judge-model` | In `_CONFIG_KEYS` at line 434; `resolved.get("judge_model")` appears nowhere in evaluation logic |
| `--max-cost` | In `_CONFIG_KEYS` at line 441; `resolved.get("max_cost")` appears nowhere (`--budget` is the live budget flag) |
| `--confirmation-runs` | In `_CONFIG_KEYS` at line 455; `resolved.get("confirmation_runs")` appears nowhere |
| `--parent-run` | In `_CONFIG_KEYS` at line 458; `resolved.get("parent_run")` appears nowhere |
| `--phase` | Dead because `--parent-run` (needed to link phases) is dead; `_run_pipeline` handles full flow automatically |
| `factorial` (from `--mode`) | Listed as a choice but there is no `_run_factorial`; falls through silently to full mode |

**Flags explicitly kept** (confirmed read from `resolved` and genuinely useful):

| Flag | Why kept |
|------|----------|
| `--oa-type` | Read at lines 671, 839, 955 — forces specific Taguchi OA table for reproducibility |
| `--quality-type` | Read at line 952 — S/N ratio type (users may test `smaller_is_better` for latency) |
| `--alpha` | Read at line 953 — ANOVA significance threshold (researchers legitimately change this) |
| `--top-k` | Read at line 954 — Phase 3 factor count (valid to explore more/fewer factors) |
| `--model-budgets` | Read at lines 855, 926 — per-model budget caps for multi-model runs |
| `--dataset-cache-dir` | Read at line 592 — override cache location (valid for CI environments) |

**Step 1 [RED]:** Write failing tests confirming removed flags are gone

```python
class TestRemovedFlags:
    """Confirmed-dead flags must not exist in parser or _CONFIG_KEYS."""

    REMOVED_FLAGS = [
        "--model-config",
        "--judge-model",
        "--max-cost",
        "--confirmation-runs",
        "--phase",
        "--parent-run",
    ]
    REMOVED_KEYS = [
        "model_config", "judge_model", "max_cost",
        "confirmation_runs", "phase", "parent_run",
    ]

    @pytest.mark.parametrize("flag", REMOVED_FLAGS)
    def test_removed_flag_raises_system_exit(self, flag):
        """Passing a removed flag must cause argparse to exit (unrecognized)."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([flag, "value"])

    @pytest.mark.parametrize("key", REMOVED_KEYS)
    def test_removed_key_not_in_config_keys(self, key):
        """Removed flags must not appear in _CONFIG_KEYS."""
        from agent_evals.cli import _CONFIG_KEYS
        assert key not in _CONFIG_KEYS

    def test_mode_factorial_is_not_a_valid_choice(self):
        """factorial is removed from --mode choices."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--mode", "factorial"])

    def test_kept_flags_still_exist(self):
        """Flags that ARE used must remain in the parser."""
        parser = build_parser()
        args = parser.parse_args([
            "--oa-type", "L54",
            "--quality-type", "larger_is_better",
            "--alpha", "0.05",
            "--top-k", "3",
            "--model-budgets", "claude=20.00",
            "--dataset-cache-dir", "/tmp/cache",
        ])
        assert args.oa_type == "L54"
        assert args.quality_type == "larger_is_better"
        assert args.alpha == 0.05
        assert args.top_k == 3
        assert args.model_budgets == "claude=20.00"
        assert args.dataset_cache_dir == "/tmp/cache"
```

**Step 2 [RED]:** Delete obsolete tests for removed flags from `test_evals_cli.py`

Find and delete test methods that reference the removed flags:
```bash
grep -n "model_config\|judge_model\|max_cost\|confirmation_runs\|parent_run\|\"phase\"\|factorial" \
    agent-evals/tests/test_evals_cli.py
# Delete all matching test methods
```

**Step 3 [RED]:** Run to confirm failures

```bash
uv run pytest agent-evals/tests/test_evals_cli.py::TestRemovedFlags -v
# Expected: FAIL — flags still exist in current parser
```

**Step 4 [GREEN]:** Remove the 7 dead flags from `_add_run_args` in `cli.py`

Delete the `parser.add_argument` blocks for:
- `--model-config` (lines 59–63)
- `--judge-model` (lines 64–68)
- `--max-cost` (lines 110–115)
- `--confirmation-runs` (lines 215–219)
- `--phase` (lines 228–232)
- `--parent-run` (lines 233–237)

Change `--mode` choices from `["full", "taguchi", "factorial"]` to `["full", "taguchi"]`.

**Step 5 [GREEN]:** Remove 6 dead keys from `_CONFIG_KEYS`

Delete these lines from the `_CONFIG_KEYS` dict:
```python
# DELETE these 6 lines:
"model_config": str,
"judge_model": str,
"max_cost": float,
"confirmation_runs": int,
"phase": str,
"parent_run": str,
```

**Step 6 [GREEN]:** Run all tests

```bash
uv run pytest agent-evals/tests/test_evals_cli.py -v
# Expected: TestRemovedFlags all PASS; no failures from removed flag tests
uv run pytest agent-evals/tests/ -v --tb=short 2>&1 | tail -20
# Expected: all tests pass
```

**Step 7 [REFACTOR]:** Review
- `_CONFIG_KEYS` no longer has `model_config`, `judge_model`, `max_cost`, `confirmation_runs`, `phase`, `parent_run`
- `--mode` only accepts `full` and `taguchi`
- No changes to `_run_taguchi` or `_run_pipeline` — they already didn't use the removed keys
- Kept flags (`--oa-type`, `--quality-type`, `--alpha`, `--top-k`, `--model-budgets`, `--dataset-cache-dir`) unchanged

**Step 8 [VERIFY]:** Confirm `--help` is clean

```bash
uv run agent-evals --help 2>&1
# Expected: no mention of model-config, judge-model, max-cost,
#           confirmation-runs, phase, parent-run
#           --mode shows: {full,taguchi}   (no factorial)

uv run agent-evals --model openrouter/anthropic/claude-haiku-4-5-20251001 --dry-run 2>&1
# Expected: runs successfully with no unexpected errors
```

**Step 9: Commit**

```bash
git add agent-evals/src/agent_evals/cli.py \
        agent-evals/tests/test_evals_cli.py
git commit -m "fix(cli): remove 7 confirmed-dead CLI flags, drop factorial mode stub (E10)"
```

---

## Sprint 13 — Dashboard Source Selection & Real Dataset Verification

**Goal:** Complete the dataset integration loop: expose `--source` in the dashboard UI, prepare all real datasets, and verify the full Taguchi pipeline runs correctly end-to-end with real data.

**Tasks:** 44, 45, 46

---

### Task 44: Wire `--source` into dashboard RunConfig (E11 — HIGH)

**Goal:** Add dataset source selection to the Run Configuration page so users can choose which dataset to evaluate against from the UI. Mirrors Task 42 (CLI path) but for the dashboard path.

**Key files:**
- Modify: `agent-evals/src/agent_evals/observatory/run_manager.py` — add `source` to `StartRunRequest`, fix `_execute_run`
- Modify: `agent-evals/src/agent_evals/observatory/web/routes.py` — add `GET /api/datasets` endpoint
- Modify: `agent-evals/src/agent_evals/observatory/web/ui/src/api/client.ts` — add `source?` to `StartRunPayload`, add `listDatasets()`
- Modify: `agent-evals/src/agent_evals/observatory/web/ui/src/api/hooks.ts` — add `useDatasets()` hook
- Modify: `agent-evals/src/agent_evals/observatory/web/ui/src/pages/RunConfig.tsx` — add "Data Source" select
- Test: `agent-evals/tests/test_run_manager.py`
- Test: `agent-evals/tests/test_observatory_web.py`
- Test: `agent-evals/src/agent_evals/observatory/web/ui/src/__tests__/pages/RunConfig.test.tsx`

**Key imports / architecture (self-contained):**

```python
# run_manager.py — existing imports already in file:
from agent_evals.observatory.store import ObservatoryStore
from agent_evals.observatory.tracker import EventTracker
from pydantic import BaseModel, Field
from typing import Literal

# New imports needed in _execute_run (inside function, same as Task 42):
from agent_evals.datasets import load_all as _load_all_datasets, list_available
from agent_evals.datasets.cache import DatasetCache
from agent_index.models import DocTree
```

```typescript
// client.ts — existing type that needs source field added:
export interface StartRunPayload {
  mode: "taguchi" | "full";
  model: string;
  repetitions: number;
  task_limit: number;
  oa_override?: string;
  pipeline_mode?: "auto" | "semi";
  quality_type?: string;
  top_k?: number;
  alpha?: number;
  // ADD THIS:
  source?: string;  // e.g. "gold_standard", "repliqa", "ambigqa"
}
```

---

**Step 1 [RED]: Write the failing backend tests**

File: `agent-evals/tests/test_run_manager.py`

```python
# Add to existing test file (or create if absent)

def test_start_run_request_has_source_field():
    """StartRunRequest must accept a source field."""
    req = StartRunRequest(model="openrouter/anthropic/claude-haiku-4-5-20251001", source="repliqa")
    assert req.source == "repliqa"

def test_start_run_request_source_defaults_to_gold_standard():
    """source defaults to gold_standard for backward compatibility."""
    req = StartRunRequest(model="openrouter/anthropic/claude-haiku-4-5-20251001")
    assert req.source == "gold_standard"
```

File: `agent-evals/tests/test_observatory_web.py`

```python
def test_get_datasets_endpoint_returns_list(client):
    """GET /api/datasets returns a list of available datasets with prepared status."""
    resp = client.get("/api/datasets")
    assert resp.status_code == 200
    data = resp.json()
    assert "datasets" in data
    assert isinstance(data["datasets"], list)
    # gold_standard always appears
    names = [d["name"] for d in data["datasets"]]
    assert "gold_standard" in names

def test_get_datasets_includes_prepared_field(client):
    """Each dataset entry has a 'prepared' boolean field."""
    resp = client.get("/api/datasets")
    datasets = resp.json()["datasets"]
    for d in datasets:
        assert "name" in d
        assert "prepared" in d
        assert isinstance(d["prepared"], bool)
```

**Step 2 [VERIFY RED]:** Run the failing tests

```bash
uv run pytest agent-evals/tests/test_run_manager.py -k "source" -v
# Expected: AttributeError — StartRunRequest has no field 'source'
uv run pytest agent-evals/tests/test_observatory_web.py -k "datasets" -v
# Expected: FAIL — 404 Not Found on GET /api/datasets
```

**Step 3 [GREEN]: Add `source` field to `StartRunRequest`**

File: `agent-evals/src/agent_evals/observatory/run_manager.py`

In the `StartRunRequest` Pydantic model (after `alpha` field):

```python
# In StartRunRequest, add after alpha field:
source: str = "gold_standard"
```

In `_execute_run` (lines 178-205), replace the hardcoded gold_standard block:

```python
# REPLACE THIS (lines 178-205 of run_manager.py):
#   gold_standard_dir = (
#       Path(__file__).resolve().parent.parent.parent.parent / "gold_standard"
#   )
#   if not gold_standard_dir.is_dir():
#       logger.error(...)
#       return
#   tasks = load_tasks(gold_standard_dir)
#   ...
#   doc_tree = load_sample_doc_tree()

# WITH THIS:
source = request.source or "gold_standard"

if source == "gold_standard":
    gold_standard_dir = (
        Path(__file__).resolve().parent.parent.parent.parent / "gold_standard"
    )
    if not gold_standard_dir.is_dir():
        logger.error("Gold standard directory not found: %s", gold_standard_dir)
        return
    tasks = load_tasks(gold_standard_dir)
    doc_tree = load_sample_doc_tree()
else:
    from agent_evals.datasets import load_all as _load_all_datasets
    from agent_evals.datasets.cache import DatasetCache
    from agent_index.models import DocTree

    _load_all_datasets()
    cache = DatasetCache()
    if not cache.is_prepared(source):
        logger.error(
            "Dataset '%s' not prepared. Run first:\n"
            "  agent-evals --prepare-datasets %s",
            source, source,
        )
        return
    tasks = load_tasks(cache.task_dir(source))
    doc_tree = DocTree.model_validate_json(
        cache.doc_tree_path(source).read_text(encoding="utf-8")
    )
```

**Step 4 [GREEN]: Add `GET /api/datasets` endpoint to routes.py**

File: `agent-evals/src/agent_evals/observatory/web/routes.py`

Add after the `GET /api/runs/active` route (around line 130):

```python
@router.get("/api/datasets")
def list_datasets() -> dict:
    """Return all registered dataset adapters with their prepared status."""
    from agent_evals.datasets import load_all as _load_all_datasets, list_available
    from agent_evals.datasets.cache import DatasetCache

    _load_all_datasets()
    cache = DatasetCache()
    adapters = list_available()

    datasets = [
        {
            "name": "gold_standard",
            "task_type": "mixed",
            "domain": "compass_brand",
            "license": "internal",
            "prepared": True,  # always available
        }
    ]
    for adapter in adapters:
        datasets.append({
            **adapter,
            "prepared": cache.is_prepared(adapter["name"]),
        })
    return {"datasets": datasets}
```

**Step 5 [VERIFY GREEN — backend]:** Run backend tests

```bash
uv run pytest agent-evals/tests/test_run_manager.py -k "source" -v
# Expected: PASS
uv run pytest agent-evals/tests/test_observatory_web.py -k "datasets" -v
# Expected: PASS
```

**Step 6 [COMMIT — backend]:**

```bash
git add agent-evals/src/agent_evals/observatory/run_manager.py \
        agent-evals/src/agent_evals/observatory/web/routes.py \
        agent-evals/tests/test_run_manager.py \
        agent-evals/tests/test_observatory_web.py
git commit -m "feat(dashboard): add source field to StartRunRequest and GET /api/datasets endpoint (E11)"
```

**Step 7 [RED]: Write failing frontend tests**

File: `agent-evals/src/agent_evals/observatory/web/ui/src/__tests__/pages/RunConfig.test.tsx`

Add to existing test file:

```typescript
it("renders Data Source select", () => {
  render(<RunConfig />);
  expect(screen.getByLabelText(/data source/i)).toBeInTheDocument();
});

it("sends source field in start run payload", async () => {
  const mockMutate = vi.fn();
  vi.mocked(useStartRun).mockReturnValue({
    mutate: mockMutate,
    isPending: false,
  } as any);
  // Mock useDatasets to return gold_standard + repliqa
  vi.mocked(useDatasets).mockReturnValue({
    data: {
      datasets: [
        { name: "gold_standard", prepared: true },
        { name: "repliqa", prepared: true },
      ],
    },
  } as any);

  render(<RunConfig />);
  // Fill required model field
  await userEvent.type(screen.getByLabelText(/model/i), "openrouter/anthropic/claude-haiku-4-5-20251001");
  // Change source to repliqa
  await userEvent.selectOptions(screen.getByLabelText(/data source/i), "repliqa");
  // Submit
  await userEvent.click(screen.getByRole("button", { name: /start evaluation/i }));

  expect(mockMutate).toHaveBeenCalledWith(
    expect.objectContaining({ source: "repliqa" }),
    expect.anything(),
  );
});
```

**Step 8 [VERIFY RED]:** Run the failing frontend tests

```bash
cd agent-evals/src/agent_evals/observatory/web/ui
npm test -- --run 2>&1 | grep -E "PASS|FAIL|source|Data Source"
# Expected: FAIL — useDatasets not defined, no Data Source element
```

**Step 9 [GREEN]: Update client.ts — add `source` to payload and `listDatasets()`**

File: `agent-evals/src/agent_evals/observatory/web/ui/src/api/client.ts`

In the `StartRunPayload` interface, add `source?: string` after `alpha`:

```typescript
// In StartRunPayload interface, add:
source?: string;  // e.g. "gold_standard", "repliqa"
```

Add a new `listDatasets` function to the `api` object:

```typescript
listDatasets: async (): Promise<{ datasets: Array<{ name: string; prepared: boolean; task_type?: string; domain?: string }> }> => {
  const resp = await fetch(`${BASE}/api/datasets`);
  if (!resp.ok) throw new Error(`listDatasets: ${resp.status}`);
  return resp.json();
},
```

**Step 10 [GREEN]: Add `useDatasets()` hook to hooks.ts**

File: `agent-evals/src/agent_evals/observatory/web/ui/src/api/hooks.ts`

Add after `useActiveRuns`:

```typescript
export function useDatasets() {
  return useQuery({
    queryKey: ["datasets"],
    queryFn: api.listDatasets,
    staleTime: STALE_LONG,
    gcTime: GC_TIME,
  });
}
```

**Step 11 [GREEN]: Add "Data Source" select to RunConfig.tsx**

File: `agent-evals/src/agent_evals/observatory/web/ui/src/pages/RunConfig.tsx`

Add `source` state and `useDatasets` import:

```typescript
// Add to imports:
import { useStartRun, useActiveRuns, useDatasets } from "../api/hooks";

// Add to state declarations:
const [source, setSource] = useState("gold_standard");
const datasetsQuery = useDatasets();
const datasets = datasetsQuery.data?.datasets ?? [{ name: "gold_standard", prepared: true }];
const preparedDatasets = datasets.filter((d) => d.prepared);
```

Add `source` to the form payload in `handleSubmit`:

```typescript
// In handleSubmit, add source to payload:
const payload: StartRunPayload = {
  mode,
  model: model.trim(),
  repetitions,
  task_limit: taskLimit,
  source,  // ADD THIS
};
```

Add the UI element inside the left column Card (after the Model input):

```tsx
<div className="mt-sp-6">
  <label
    htmlFor="source"
    className="mb-sp-2 block text-body-sm font-medium text-brand-charcoal"
  >
    Data Source
  </label>
  <Select
    aria-label="Data Source"
    value={source}
    onValueChange={setSource}
    options={preparedDatasets.map((d) => ({
      value: d.name,
      label: d.name === "gold_standard"
        ? "Gold Standard (Compass Brand internal)"
        : d.name,
    }))}
  />
  <p className="mt-sp-1 text-caption text-brand-slate">
    Dataset to evaluate against. Only prepared datasets are shown.
    Run <code>agent-evals --prepare-datasets &lt;name&gt;</code> to add more.
  </p>
</div>
```

**Step 12 [VERIFY GREEN — frontend]:** Run the frontend tests

```bash
cd agent-evals/src/agent_evals/observatory/web/ui
npm test -- --run 2>&1 | grep -E "PASS|FAIL|RunConfig"
# Expected: RunConfig tests PASS
```

**Step 13 [REFACTOR]:** Review
- `source` defaults to `"gold_standard"` everywhere — no behaviour change for existing runs
- Dashboard and CLI now both route to real datasets when `source != "gold_standard"`
- `/api/datasets` always lists `gold_standard` first (always prepared)
- Unprepared datasets appear in the API (`prepared: false`) but RunConfig.tsx filters them with `.filter(d => d.prepared)` — only shows runnable sources

**Step 14 [VERIFY]:** Smoke test

```bash
# Backend endpoint smoke test
uv run python -m agent_evals.observatory.server --port 8765 &
SERVER_PID=$!
sleep 2
curl -s http://localhost:8765/api/datasets | python -m json.tool
# Expected: { "datasets": [{ "name": "gold_standard", "prepared": true }, ...] }
kill $SERVER_PID

# Test that gold_standard still works (backward compat)
uv run pytest agent-evals/tests/test_run_manager.py agent-evals/tests/test_observatory_web.py -v --tb=short
```

**Step 15: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/api/client.ts \
        agent-evals/src/agent_evals/observatory/web/ui/src/api/hooks.ts \
        agent-evals/src/agent_evals/observatory/web/ui/src/pages/RunConfig.tsx \
        agent-evals/src/agent_evals/observatory/web/ui/src/__tests__/pages/RunConfig.test.tsx
git commit -m "feat(ui): add Data Source selector to RunConfig with useDatasets hook (E11)"
```

---

### Task 45: Prepare all real datasets (E12 — HIGH)

**Goal:** Download and cache all dataset adapters so real benchmarks are available for evaluation and testing. Create an idempotent setup script so this can be re-run safely.

**Key files:**
- Create: `scripts/prepare-datasets.sh`
- No source code changes — this is a data preparation task

**Key imports / architecture (self-contained):**

```bash
# The prepare-datasets command invokes DatasetCache.mark_prepared() after
# calling adapter.convert_tasks(cache.task_dir(name)) and
#       adapter.build_doc_tree() -> saved to cache.doc_tree_path(name)
# Cache location: ~/.agent-evals/datasets/{name}/
# Marker file:    ~/.agent-evals/datasets/{name}/.prepared
# Task YAMLs:     ~/.agent-evals/datasets/{name}/tasks/*.yaml
# Doc tree:       ~/.agent-evals/datasets/{name}/doc_tree.json

# Available adapters (from agent_evals/datasets/):
# repliqa, ambigqa, ibm-techqa, multihop-rag, ds1000,
# bigcodebench, swe-bench, wikicontradict, perturbation,
# synthetic-efficiency, code-rag-bench
```

---

**Step 1: Check what adapters are registered**

```bash
uv run python -c "
from agent_evals.datasets import load_all, list_available
load_all()
for a in list_available():
    print(a['name'], '|', a['license'], '|', a['task_type'])
"
# Note the exact names — these are the values to pass to --prepare-datasets
```

**Step 2: Check which datasets are already prepared**

```bash
uv run python -c "
from agent_evals.datasets import load_all, list_available
from agent_evals.datasets.cache import DatasetCache
load_all()
cache = DatasetCache()
for a in list_available():
    status = 'READY' if cache.is_prepared(a['name']) else 'NOT PREPARED'
    print(f'{status}: {a[\"name\"]}')
"
```

**Step 3: Create `scripts/prepare-datasets.sh`**

```bash
#!/usr/bin/env bash
# prepare-datasets.sh — idempotent dataset preparation script
# Run from the workspace root (ai-documentation-testing/)
# Usage: bash scripts/prepare-datasets.sh [--limit N]
#
# Downloads and caches all registered dataset adapters.
# Already-prepared datasets are skipped automatically (idempotent).
# Default limit: 200 tasks per dataset. Override with --limit N.

set -euo pipefail

LIMIT="${1:-200}"
if [[ "${1:-}" == "--limit" ]]; then
    LIMIT="$2"
fi

echo "=== Preparing datasets (limit: ${LIMIT} tasks each) ==="

# Prepare each dataset individually so one failure does not block others
DATASETS=(
  repliqa
  ambigqa
  ibm-techqa
  multihop-rag
  ds1000
  bigcodebench
  swe-bench
  wikicontradict
)

FAILED=()
for DATASET in "${DATASETS[@]}"; do
    echo ""
    echo "--- Preparing: ${DATASET} ---"
    if uv run agent-evals --prepare-datasets "${DATASET}" --dataset-limit "${LIMIT}"; then
        echo "OK: ${DATASET}"
    else
        echo "FAILED: ${DATASET} (continuing with others)"
        FAILED+=("${DATASET}")
    fi
done

echo ""
echo "=== Dataset preparation complete ==="

# Final status report
uv run python -c "
from agent_evals.datasets import load_all, list_available
from agent_evals.datasets.cache import DatasetCache
load_all()
cache = DatasetCache()
ready = []
missing = []
for a in list_available():
    if cache.is_prepared(a['name']):
        ready.append(a['name'])
    else:
        missing.append(a['name'])
print(f'Ready ({len(ready)}): {ready}')
print(f'Missing ({len(missing)}): {missing}')
"

if [[ ${#FAILED[@]} -gt 0 ]]; then
    echo ""
    echo "WARNING: Failed to prepare: ${FAILED[*]}"
    echo "These datasets may require network access, HuggingFace authentication,"
    echo "or special download permissions. Check error messages above."
    exit 1
fi
```

**Step 4: Make the script executable and run it**

```bash
chmod +x scripts/prepare-datasets.sh
bash scripts/prepare-datasets.sh --limit 200
# This will download from HuggingFace. May take 5-30 minutes depending on network.
# Each dataset is idempotent — already-prepared datasets are skipped.
```

**Step 5: Verify task counts after preparation**

```bash
uv run python -c "
from agent_evals.datasets import load_all, list_available
from agent_evals.datasets.cache import DatasetCache
from agent_evals.tasks.loader import load_tasks
load_all()
cache = DatasetCache()
for a in list_available():
    name = a['name']
    if cache.is_prepared(name):
        tasks = load_tasks(cache.task_dir(name))
        print(f'{name}: {len(tasks)} tasks')
    else:
        print(f'{name}: NOT PREPARED')
"
# Expected: each prepared dataset shows > 0 tasks (up to 200)
```

**Step 6: Verify a quick dry-run evaluation loads correctly**

```bash
# Test gold_standard still works (must not regress)
uv run agent-evals --model openrouter/anthropic/claude-haiku-4-5-20251001 --dry-run 2>&1 | grep -E "tasks loaded|error"

# Test repliqa source (or whichever was prepared first)
uv run agent-evals --model openrouter/anthropic/claude-haiku-4-5-20251001 \
  --source repliqa \
  --task-limit 5 \
  --dry-run \
  2>&1 | grep -E "tasks loaded|error|repliqa"
# Expected: loads repliqa tasks, no errors
```

**Step 7: Commit**

```bash
git add scripts/prepare-datasets.sh
git commit -m "chore(datasets): add idempotent prepare-datasets.sh setup script (E12)"
```

**Note on HuggingFace access:** Some datasets (SWE-Bench, BigCodeBench) require `huggingface-hub` authentication. If download fails:
1. Run `huggingface-cli login` with a read token from huggingface.co/settings/tokens
2. Re-run `bash scripts/prepare-datasets.sh` — already-prepared datasets are skipped

---

### Task 46: End-to-end Taguchi verification with real datasets (E13 — HIGH)

**Goal:** Verify 100% confidence that the complete Taguchi pipeline (screening → confirmation/retesting) works correctly with real datasets. This task has automated integration tests (TDD) plus human-only full-scale verification steps.

**Key files:**
- Test: `agent-evals/tests/test_taguchi_e2e.py` (new file — integration tests)
- No production code changes unless a bug is found

**Key imports / architecture (self-contained):**

```python
# The DOE pipeline runs in three phases:
# Phase 1 — Taguchi Screening: builds orthogonal array, runs trials
# Phase 2 — ANOVA Analysis: identifies significant factors
# Phase 3 — Confirmation/Retesting: validates optimal config found in Phase 1
#
# The "retesting" = Phase 3 (confirmation run).
# --pipeline auto  -> all phases run automatically
# --pipeline semi  -> UI pauses between phases for approval
#
# Key classes:
from agent_evals.pipeline import DOEPipeline, PipelineConfig
from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig
from agent_evals.taguchi.factors import build_design
from agent_evals.tasks.loader import load_tasks
from agent_evals.datasets import load_all as load_all_datasets
from agent_evals.datasets.cache import DatasetCache
from agent_index.models import DocTree
```

---

**Step 1 [RED]: Write failing integration tests**

File: `agent-evals/tests/test_taguchi_e2e.py` (new)

```python
"""End-to-end integration tests for the Taguchi evaluation pipeline.

Uses real datasets (small limits) to verify the complete evaluation loop:
  dataset load -> trial execution -> scoring -> ANOVA analysis -> confirmation.

Requires OPENROUTER_API_KEY and at least one prepared dataset.
Skips gracefully when neither is available so CI passes without credentials.
"""

from __future__ import annotations

import os
import pytest
from pathlib import Path

from agent_evals.datasets import load_all as load_all_datasets, list_available
from agent_evals.datasets.cache import DatasetCache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        pytest.skip("OPENROUTER_API_KEY not set — skipping live evaluation tests")
    return key


@pytest.fixture(scope="module")
def prepared_dataset_name() -> str:
    """Return the name of the first prepared dataset, or skip."""
    load_all_datasets()
    cache = DatasetCache()
    for adapter in list_available():
        if cache.is_prepared(adapter["name"]):
            return adapter["name"]
    pytest.skip("No datasets prepared — run scripts/prepare-datasets.sh first")


# ---------------------------------------------------------------------------
# Source routing tests (no API key needed — validates data loading only)
# ---------------------------------------------------------------------------

class TestSourceRouting:
    """Verify that source routing loads correct tasks and doc_tree."""

    def test_gold_standard_loads(self):
        """gold_standard source loads tasks from the gold_standard/ directory."""
        gold_dir = Path(__file__).resolve().parents[3] / "gold_standard"
        if not gold_dir.is_dir():
            pytest.skip("gold_standard directory not found")
        from agent_evals.tasks.loader import load_tasks
        tasks = load_tasks(gold_dir)
        assert len(tasks) > 0, "gold_standard must have at least one task"

    def test_dataset_source_loads_tasks(self, prepared_dataset_name):
        """Prepared dataset source loads task YAML files from cache."""
        from agent_evals.tasks.loader import load_tasks
        cache = DatasetCache()
        task_dir = cache.task_dir(prepared_dataset_name)
        tasks = load_tasks(task_dir)
        assert len(tasks) > 0, f"Dataset '{prepared_dataset_name}' has no tasks"

    def test_dataset_source_loads_doc_tree(self, prepared_dataset_name):
        """Prepared dataset source loads doc_tree.json from cache."""
        from agent_index.models import DocTree
        cache = DatasetCache()
        doc_tree_path = cache.doc_tree_path(prepared_dataset_name)
        assert doc_tree_path.exists(), f"doc_tree.json missing for {prepared_dataset_name}"
        doc_tree = DocTree.model_validate_json(doc_tree_path.read_text(encoding="utf-8"))
        assert doc_tree is not None
        assert len(doc_tree.files) > 0, "DocTree must contain at least one file"

    def test_unprepared_source_cache_reports_false(self):
        """Cache.is_prepared() returns False for an unknown dataset name."""
        cache = DatasetCache()
        assert not cache.is_prepared("__test_nonexistent_dataset__")


# ---------------------------------------------------------------------------
# Taguchi pipeline smoke tests (require API key — small limits)
# ---------------------------------------------------------------------------

class TestTaguchiPipelineSmoke:
    """Smoke tests for the full Taguchi pipeline with minimal data."""

    def test_taguchi_screening_runs_with_prepared_dataset(
        self, api_key, prepared_dataset_name
    ):
        """Taguchi screening phase completes without exception using a real dataset.

        Uses task-limit=2, repetitions=1 to minimize API calls.
        Verifies: trials execute, scores are returned, no crash.
        """
        from agent_evals.datasets.cache import DatasetCache
        from agent_evals.observatory.store import ObservatoryStore
        from agent_evals.observatory.tracker import EventTracker
        from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig
        from agent_evals.runner import EvalRunConfig
        from agent_evals.taguchi.factors import build_design
        from agent_evals.tasks.loader import load_tasks
        from agent_evals.variants.registry import get_all_variants, load_all
        from agent_index.models import DocTree

        load_all_datasets()
        load_all()

        cache = DatasetCache()
        tasks = list(load_tasks(cache.task_dir(prepared_dataset_name)))[:2]
        doc_tree = DocTree.model_validate_json(
            cache.doc_tree_path(prepared_dataset_name).read_text(encoding="utf-8")
        )
        variants = get_all_variants()

        axes: dict[int, list[str]] = {}
        for v in variants:
            m = v.metadata()
            if m.axis == 0:
                continue
            if m.axis not in axes:
                axes[m.axis] = []
            if m.name not in axes[m.axis]:
                axes[m.axis].append(m.name)
        design = build_design(axes, models=None, oa_override=None)

        eval_config = EvalRunConfig(repetitions=1, continue_on_error=True, temperature=0.3)
        store = ObservatoryStore()
        tracker = EventTracker(store=store)
        orch_config = OrchestratorConfig(
            mode="taguchi",
            models=["openrouter/anthropic/claude-haiku-4-5-20251001"],
            api_key=api_key,
            temperature=0.3,
            eval_config=eval_config,
            store=store,
            tracker=tracker,
            run_id="test-e2e-smoke",
        )
        orchestrator = EvalOrchestrator(orch_config)
        variant_lookup = {v.metadata().name: v for v in variants}

        # Should not raise
        orchestrator.run(
            tasks=tasks,
            variants=variants,
            doc_tree=doc_tree,
            design=design,
            variant_lookup=variant_lookup,
            source=prepared_dataset_name,
        )

        trials = store.get_trials(run_id="test-e2e-smoke")
        assert len(trials) > 0, "No trials recorded — Taguchi screening failed silently"

    def test_trial_scores_are_nonzero(self, api_key, prepared_dataset_name):
        """At least some trials in a real evaluation produce non-zero scores.

        If all scores are 0.0, the scorer is broken (the original D1/D2 bug).
        """
        from agent_evals.datasets.cache import DatasetCache
        from agent_evals.observatory.store import ObservatoryStore
        from agent_evals.observatory.tracker import EventTracker
        from agent_evals.orchestrator import EvalOrchestrator, OrchestratorConfig
        from agent_evals.runner import EvalRunConfig
        from agent_evals.tasks.loader import load_tasks
        from agent_evals.variants.registry import get_all_variants, load_all
        from agent_index.models import DocTree

        load_all_datasets()
        load_all()

        cache = DatasetCache()
        tasks = list(load_tasks(cache.task_dir(prepared_dataset_name)))[:3]
        doc_tree = DocTree.model_validate_json(
            cache.doc_tree_path(prepared_dataset_name).read_text(encoding="utf-8")
        )
        variants = get_all_variants()
        baselines = [v for v in variants if v.metadata().axis == 0][:1]

        eval_config = EvalRunConfig(repetitions=1, continue_on_error=True, temperature=0.3)
        store = ObservatoryStore()
        tracker = EventTracker(store=store)
        orch_config = OrchestratorConfig(
            mode="full",
            models=["openrouter/anthropic/claude-haiku-4-5-20251001"],
            api_key=api_key,
            temperature=0.3,
            eval_config=eval_config,
            store=store,
            tracker=tracker,
            run_id="test-e2e-scores",
        )
        orchestrator = EvalOrchestrator(orch_config)
        orchestrator.run(
            tasks=tasks,
            variants=baselines,
            doc_tree=doc_tree,
            source=prepared_dataset_name,
        )

        trials = store.get_trials(run_id="test-e2e-scores")
        assert trials, "No trials recorded"
        scores = [t.score for t in trials if t.score is not None]
        assert scores, "No scores recorded"
        nonzero = [s for s in scores if s > 0.0]
        assert len(nonzero) > 0, (
            f"All {len(scores)} scores are 0.0 — scorer is broken. "
            "Check that scorer fix tasks (D1/D2) were applied first."
        )
```

**Step 2 [VERIFY RED]:** Run the failing tests

```bash
uv run pytest agent-evals/tests/test_taguchi_e2e.py -v --tb=short
# Expected with no API key: live tests SKIP; source routing tests PASS or SKIP
# Expected with API key but no prepared datasets: prepared_dataset_name fixture SKIPs
# Expected with API key + prepared datasets: may FAIL on scorer if D1/D2 not yet applied
```

**Step 3 [GREEN]: Fix any failures found**

**Scenario A — Tests PASS:** Pipeline works. Proceed to Step 4.

**Scenario B — Tests FAIL:** File a beads issue immediately, fix it (TDD), return to this step.

Common failure modes and fixes:
- `source` kwarg not accepted by `orchestrator.run()` → add as optional kwarg with default `"gold_standard"`
- `store.get_trials(run_id=...)` method missing → check `ObservatoryStore` API for the correct method name
- All scores 0.0 → scorer fix from Tasks D1/D2 not applied first — apply those tasks before this one

**Step 4 [VERIFY]:** CLI smoke — full mode with real dataset

```bash
uv run agent-evals \
  --model openrouter/anthropic/claude-haiku-4-5-20251001 \
  --source repliqa \
  --mode full \
  --task-limit 2 \
  --repetitions 1 \
  --output-format json \
  --output-path /tmp/e2e_full_smoke.json

uv run python -c "
import json
data = json.load(open('/tmp/e2e_full_smoke.json'))
trials = data.get('trials', [])
print(f'Trials: {len(trials)}')
scores = [t['score'] for t in trials if t.get('score') is not None]
nonzero = [s for s in scores if s > 0]
print(f'Non-zero scores: {len(nonzero)}/{len(scores)}')
assert nonzero, 'ERROR: all scores are 0 — scorer is broken'
print('PASS: scorer producing non-zero scores')
"
```

**Step 5 [VERIFY]:** CLI smoke — Taguchi screening with real dataset

```bash
uv run agent-evals \
  --model openrouter/anthropic/claude-haiku-4-5-20251001 \
  --source repliqa \
  --mode taguchi \
  --task-limit 5 \
  --repetitions 1 \
  --output-format json \
  --output-path /tmp/e2e_taguchi_smoke.json

uv run python -c "
import json
data = json.load(open('/tmp/e2e_taguchi_smoke.json'))
trials = data.get('trials', [])
print(f'Trials: {len(trials)}')
assert len(trials) > 1, f'Expected multiple OA trials, got {len(trials)}'
print('PASS: Taguchi screening generated multiple trials')
"
```

**Step 6 [VERIFY — Human-only]:** Full DOE pipeline with confirmation/retesting

> This step requires human monitoring and is **not automated**.
> Run during a work session so you can respond to the semi-mode approval prompt.

```bash
# Semi mode: pauses between phases for your approval
uv run agent-evals \
  --model openrouter/anthropic/claude-haiku-4-5-20251001 \
  --source repliqa \
  --mode taguchi \
  --pipeline semi \
  --task-limit 20 \
  --repetitions 2 \
  --quality-type larger_is_better \
  --top-k 3 \
  --alpha 0.05 \
  --output-format json \
  --output-path /tmp/e2e_pipeline_full.json

# After all phases complete:
uv run python -c "
import json
data = json.load(open('/tmp/e2e_pipeline_full.json'))
report = data.get('report', {})
phases = report.get('phases', [])
print(f'Phases completed: {len(phases)}')
for p in phases:
    print(f'  {p.get(\"name\")}: {p.get(\"status\")}')
confirmation = next((p for p in phases if 'confirm' in p.get('name','').lower()), None)
assert confirmation, 'ERROR: no confirmation/retesting phase in report'
print(f'Confirmation status: {confirmation.get(\"status\")}')
optimal = report.get('optimal_config', {})
print('Optimal config:', optimal)
print('PASS: Full Taguchi pipeline with retesting completed')
"
```

**Step 7 [VERIFY — Human-only]:** Auto-pipeline overnight run

```bash
# Auto mode — all phases without human intervention
uv run agent-evals \
  --model openrouter/anthropic/claude-haiku-4-5-20251001 \
  --source repliqa \
  --mode taguchi \
  --pipeline auto \
  --task-limit 50 \
  --repetitions 3 \
  --quality-type larger_is_better \
  --top-k 3 \
  --alpha 0.05 \
  --output-format both \
  --output-path /tmp/e2e_pipeline_auto
# Produces: /tmp/e2e_pipeline_auto.json and /tmp/e2e_pipeline_auto.csv
```

**Step 8 [COMMIT]:** Commit integration tests

```bash
git add agent-evals/tests/test_taguchi_e2e.py
git commit -m "test(e2e): add Taguchi pipeline integration tests with real datasets (E13)"
```

**Step 9 [REFACTOR]:** Full test suite check

```bash
uv run pytest --tb=short 2>&1 | tail -20
# Expected: all tests pass (skips for missing API key/datasets are acceptable)

uv run pytest --cov=agent_evals --cov-report=term-missing -q 2>&1 | tail -10
# Expected: >= 80% overall coverage
```

**Step 10: Final commit**

```bash
git add -p
git commit -m "test(e2e): fix any coverage gaps from integration test review (E13)"
```

---

## Manual Investigations (No Code Change)

### Task 38: Review perfect-score latency anomaly (D4)

1. Query for 20 random perfect-score trials across task types from the DB
2. Review response content for templated/gamed patterns
3. If patterns found, create a beads issue for a response diversity check

### Task 39: Investigate pipeline view empty data (D5)

1. Check DB: `SELECT * FROM pipelines WHERE pipeline_id = '83973e5dca97';`
2. Check: `SELECT * FROM phase_results WHERE pipeline_id = '83973e5dca97';`
3. Trace `create_pipeline()` call order vs `create_run()` in orchestrator
4. Create a beads issue once root cause is identified

---

## Appendix: Full Verification Checklist

Run after all sprints are complete:

```bash
# 1. Python test suite (must have 0 failures, coverage >= 80%)
uv run pytest --cov=agent_evals --cov-report=term-missing -v 2>&1 | tail -20

# 2. Frontend test suite
cd agent-evals/src/agent_evals/observatory/web/ui
npm test -- --coverage 2>&1 | tail -20

# 3. Type checking
cd /path/to/workspace
uv run mypy agent-index/src agent-evals/src

# 4. Linting
uv run ruff check .

# 5. Server smoke test (verify server starts after infrastructure changes)
uv run python -m agent_evals.observatory.server --port 8765 &
SERVER_PID=$!
sleep 2
curl -s http://localhost:8765/api/runs | jq '.runs | length'
kill $SERVER_PID

# 6. REAL scorer validation (requires API key — not dry-run)
uv run agent-evals \
  --model openrouter/anthropic/claude-haiku-4-5-20251001 \
  --task-types compositional \
  --task-limit 100 \
  --output-format json \
  --output-path /tmp/post_fix_check.json
uv run python -c "
import json; data = json.load(open('/tmp/post_fix_check.json'))
scores = [t['score'] for t in data['trials']]
zeros = sum(1 for s in scores if s == 0.0)
print(f'Post-fix mean: {sum(scores)/len(scores):.3f} (must be > 0.30)')
print(f'Post-fix zero rate: {zeros/len(scores):.1%} (must be < 30%)')
assert sum(scores)/len(scores) > 0.30, 'Scorer fix did not improve compositional mean!'
"
```

**Regression check:** Verify test count did not decrease:
```bash
uv run pytest --collect-only -q 2>&1 | tail -3
# Note total test count and compare to before
```

**Dataset integration check (Tasks 42 + 43):**
```bash
# Confirm --source gold_standard still works (backward compat)
uv run agent-evals --model openrouter/anthropic/claude-haiku-4-5-20251001 --dry-run 2>&1 | grep -E "tasks|error"

# Confirm removed flags are gone
uv run agent-evals --model-config foo.yaml --dry-run 2>&1 | grep -E "unrecognized|error"
# Expected: "unrecognized arguments: --model-config"

# Confirm dataset source works
uv run agent-evals --prepare-datasets repliqa --dataset-limit 10
uv run agent-evals --model openrouter/anthropic/claude-haiku-4-5-20251001 --source repliqa --dry-run 2>&1 | grep -E "tasks|error"
# Expected: loads 10 repliqa tasks, no errors
```

**Dashboard source integration check (Tasks 44-46):**
```bash
# 7. Verify GET /api/datasets endpoint returns gold_standard + all adapters
uv run python -m agent_evals.observatory.server --port 8765 &
SERVER_PID=$!
sleep 2
curl -s http://localhost:8765/api/datasets | python -m json.tool
# Expected: {"datasets": [{"name": "gold_standard", "prepared": true}, ...]}
kill $SERVER_PID

# 8. Verify datasets are prepared
uv run python -c "
from agent_evals.datasets import load_all, list_available
from agent_evals.datasets.cache import DatasetCache
load_all()
cache = DatasetCache()
prepared = [a['name'] for a in list_available() if cache.is_prepared(a['name'])]
print(f'Prepared datasets ({len(prepared)}): {prepared}')
assert prepared, 'ERROR: no datasets prepared — run scripts/prepare-datasets.sh'
"

# 9. End-to-end smoke: repliqa source loads correctly
uv run agent-evals \
  --model openrouter/anthropic/claude-haiku-4-5-20251001 \
  --source repliqa \
  --task-limit 2 \
  --repetitions 1 \
  --mode full \
  --output-format json \
  --output-path /tmp/e2e_final_check.json
uv run python -c "
import json
data = json.load(open('/tmp/e2e_final_check.json'))
scores = [t['score'] for t in data.get('trials', []) if t.get('score') is not None]
nonzero = [s for s in scores if s > 0]
print(f'Non-zero scores: {len(nonzero)}/{len(scores)}')
assert nonzero, 'ERROR: all scores 0 with real dataset — scorer broken'
print('PASS: real dataset evaluation working end-to-end')
"

# 10. Integration tests pass (skip if no API key/datasets in CI)
uv run pytest agent-evals/tests/test_taguchi_e2e.py -v --tb=short
# Expected: source routing tests PASS; live tests SKIP if no API key
```

**Investigation tasks (D4, D5):** Tasks 38 and 39 are manual investigations with no automated tests. They are complete when a beads issue has been filed with root cause identified. They do not appear in the test suite pass/fail count.
