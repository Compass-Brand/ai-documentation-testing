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

**Step 1: Write the failing test**

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

**Step 2: Run to confirm it fails**

```bash
cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing
uv run pytest agent-evals/tests/test_task_compositional.py::test_empty_sub_task_excluded_from_denominator -v
```
Expected: `FAILED — AssertionError: 0.5 != 1.0`

**Step 3: Implement fix**

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

**Step 4: Run test**

```bash
uv run pytest agent-evals/tests/test_task_compositional.py -v
```
Expected: all PASS

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/tasks/compositional.py agent-evals/tests/test_task_compositional.py
git commit -m "fix(scoring): exclude empty sub-tasks from compositional denominator (S7)"
```

---

### Task 2: Add rapidfuzz dependency (S1 prerequisite)

> This is a dependency task — no logic test required. Verify with a smoke test.

**Files:**
- Modify: `agent-evals/pyproject.toml`

**Step 1: Add dependency**

In `agent-evals/pyproject.toml` under `[project] dependencies`:
```toml
"rapidfuzz>=3.0",
```

**Step 2: Sync from workspace root**

```bash
# Run from workspace root, not from agent-evals/
cd /home/trevor-leigh/Projects/compass_brand/compass-tests/ai-documentation-testing
uv sync
```

**Step 3: Smoke test**

```bash
uv run python -c "from rapidfuzz import fuzz, utils; print('rapidfuzz OK')"
```
Expected: `rapidfuzz OK`

**Step 4: Commit**

```bash
git add agent-evals/pyproject.toml uv.lock
git commit -m "feat(deps): add rapidfuzz>=3.0 for fuzzy answer matching (S1 prerequisite)"
```

---

### Task 3: Replace compositional substring match with fuzzy matching (S1 — HIGH)

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/compositional.py`
- Test: `agent-evals/tests/test_task_compositional.py`

**Step 1: Write failing tests**

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

**Step 2: Run to confirm the paraphrase test fails**

```bash
uv run pytest agent-evals/tests/test_task_compositional.py::test_fuzzy_match_catches_paraphrase -v
```
Expected: `FAILED — assert 0.0 > 0.0`

**Step 3: Implement fix**

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

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_task_compositional.py -v
```
Expected: all PASS

**Step 5: Commit**

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

**Step 1: Write failing test**

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

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_task_negative.py::test_confident_answer_not_scored_as_abstention -v
```
Expected: `FAILED — 1.0 is not < 1.0`

**Step 3: Implement**

In `negative.py`, find `_ABSTENTION_PHRASES` (around lines 22-66) and remove exactly these two entries:
- `"based on the available"` (line 64)
- `"the provided documentation"` (line 65)

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_task_negative.py -v
```
Expected: all PASS

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/tasks/negative.py agent-evals/tests/test_task_negative.py
git commit -m "fix(scoring): remove false-positive abstention phrases from negative scorer (S8)"
```

---

### Task 5: Graduate negative scorer to rubric scoring (S2 — MEDIUM)

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/negative.py:118-135`
- Test: `agent-evals/tests/test_task_negative.py`

**Step 1: Write failing tests**

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

**Step 2: Run to confirm hedge test fails**

```bash
uv run pytest agent-evals/tests/test_task_negative.py::test_hedge_with_caveat_scores_exactly_0_7 -v
```
Expected: `FAILED — 0.0 != 0.7`

**Step 3: Implement graduated rubric**

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

**Step 4: Run all negative tests**

```bash
uv run pytest agent-evals/tests/test_task_negative.py -v
```
Expected: all PASS

**Step 5: Commit**

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

**Step 1: Write failing test**

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

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_task_disambiguation.py::test_49_percent_keyword_coverage_not_binary -v
```

**Step 3: Implement — replace cliff threshold, preserve label_score path**

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

**Step 4: Run all disambiguation tests**

```bash
uv run pytest agent-evals/tests/test_task_disambiguation.py -v
```
Expected: mostly PASS — **but `test_partial_keyword_coverage_below_threshold` will fail.** That test expects `score == 0.0` for 1/3 keyword coverage, which the old cliff produced. With continuous scoring, 1/3 coverage = 0.33. Update that test's assertion to:
```python
assert score == pytest.approx(1/3, abs=0.01)
```
Then re-run and confirm all PASS.

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/tasks/disambiguation.py agent-evals/tests/test_task_disambiguation.py
git commit -m "fix(scoring): replace cliff threshold with continuous coverage in disambiguation (S3)"
```

---

### Task 7: Multi-hop — require 30% keyword coverage per step (S4 — MEDIUM)

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/multi_hop.py:105`
- Test: `agent-evals/tests/test_task_multi_hop.py`

**Step 1: Write failing test**

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

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_task_multi_hop.py::test_single_keyword_hit_does_not_pass_step -v
```
Expected: `FAILED — currently scores 1.0`

**Step 3: Implement**

```python
STEP_COVERAGE_THRESHOLD = 0.30

# Replace the `any()` check at line 105:
matched = sum(1 for kw in keywords if kw.lower() in response_lower)
coverage = matched / len(keywords)
step_scores.append(coverage if coverage >= STEP_COVERAGE_THRESHOLD else 0.0)
```

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_task_multi_hop.py -v
```

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/tasks/multi_hop.py agent-evals/tests/test_task_multi_hop.py
git commit -m "fix(scoring): require 30% keyword coverage per step in multi-hop (S4)"
```

---

### Task 8: Fact extraction — add fuzzy matching layer (S5 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/fact_extraction.py:73-87`
- Test: `agent-evals/tests/test_task_fact_extraction.py`

**Step 1: Write failing test**

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

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_task_fact_extraction.py::test_paraphrase_scores_above_0_7 -v
```

**Step 3: Implement**

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

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_task_fact_extraction.py -v
```

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/tasks/fact_extraction.py agent-evals/tests/test_task_fact_extraction.py
git commit -m "fix(scoring): add rapidfuzz fuzzy layer to fact extraction scorer (S5)"
```

---

### Task 9: Code generation — default match_rate to 1.0 when no patterns (S9 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/code_generation.py:115-121`
- Test: `agent-evals/tests/test_task_code_generation.py`

**Step 1: Write failing test**

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

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_task_code_generation.py::test_no_test_patterns_does_not_cap_score_at_0_3 -v
```

**Step 3: Implement**

```python
# In code_generation.py, change the else branch:
if patterns:
    matched = sum(1 for pat in patterns if _match_pattern(pat, response))
    match_rate = matched / len(patterns)
else:
    match_rate = 1.0  # No patterns → vacuously satisfied
```

Also update the docstring formula comment from `0.8 + 0.2` to `0.7 + 0.2 + 0.1`.

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_task_code_generation.py -v
```

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/tasks/code_generation.py agent-evals/tests/test_task_code_generation.py
git commit -m "fix(scoring): default match_rate to 1.0 when no test patterns defined (S9)"
```

---

### Task 10: Agentic — whitespace fallback in _parse_json_or_list (S10 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/agentic.py` (around line 47)
- Test: `agent-evals/tests/test_task_agentic.py`

**Step 1: Write failing test**

```python
def test_space_separated_test_names_parsed_correctly():
    """'test_foo test_bar' must parse as ['test_foo', 'test_bar']."""
    from agent_evals.tasks.agentic import _parse_json_or_list
    result = _parse_json_or_list("test_foo test_bar")
    assert result == ["test_foo", "test_bar"], f"Got: {result}"
```

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_task_agentic.py::test_space_separated_test_names_parsed_correctly -v
```
Expected: `FAILED — [] != ['test_foo', 'test_bar']`

**Step 3: Implement**

In `agentic.py`, in the `except json.JSONDecodeError` branch of `_parse_json_or_list`:
```python
except json.JSONDecodeError:
    return [token for token in value.strip().split() if token]
```

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_task_agentic.py -v
```

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/tasks/agentic.py agent-evals/tests/test_task_agentic.py
git commit -m "fix(scoring): fall back to whitespace split in agentic _parse_json_or_list (S10)"
```

---

### Task 11: Agentic — dynamic weight redistribution for missing metadata (S11 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/agentic.py` (score_response method, around line 108)
- Test: `agent-evals/tests/test_task_agentic.py`

**Step 1: Write failing test**

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

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_task_agentic.py::test_agentic_score_redistributes_weights_when_no_files -v
```

**Step 3: Implement dynamic weight redistribution**

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

**Step 4: Run all agentic tests**

```bash
uv run pytest agent-evals/tests/test_task_agentic.py -v
```

**Step 5: Commit**

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

**Step 1: Write failing test**

```python
def test_fail_run_sets_failed_status_and_finished_at(tmp_path):
    store = ObservatoryStore(db_path=tmp_path / "test.db")
    store.create_run("run1", "full", {}, phase="screening")
    store.fail_run("run1", error="Runner crashed")
    summary = store.get_run_summary("run1")
    assert summary.status == "failed"
    assert summary.finished_at is not None
```

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_observatory_store.py::test_fail_run_sets_failed_status_and_finished_at -v
```
Expected: `AttributeError: 'ObservatoryStore' has no attribute 'fail_run'`

**Step 3: Implement**

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

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_observatory_store.py -v
```

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/store.py agent-evals/tests/test_observatory_store.py
git commit -m "feat(store): add fail_run() method; ensure finish_run() sets finished_at (I10+I5)"
```

---

### Task 13: Fix _run_wrapper to mark failed runs in DB (I9 — MEDIUM)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/run_manager.py:145-155`
- Test: `agent-evals/tests/test_run_manager.py`

**Step 1: Write failing test**

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

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_run_manager.py::test_run_wrapper_marks_run_failed_on_exception -v
```

**Step 3: Implement**

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

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_run_manager.py -v
```

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/run_manager.py agent-evals/tests/test_run_manager.py
git commit -m "fix(runner): mark run as failed in DB when _run_wrapper catches exception (I9)"
```

---

### Task 14: Raise RunSetupError from early returns in _execute_run (I13 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/run_manager.py:157-244`
- Test: `agent-evals/tests/test_run_manager.py`

**Step 1: Write failing test**

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

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_run_manager.py::test_missing_api_key_marks_run_failed -v
```

**Step 3: Implement**

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

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_run_manager.py -v
```

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/run_manager.py agent-evals/tests/test_run_manager.py
git commit -m "fix(runner): raise RunSetupError from early exits so wrapper marks run failed (I13)"
```

---

### Task 15a: Add heartbeat columns and store methods (I3 — MEDIUM, Part 1 of 2)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/store.py`
- Test: `agent-evals/tests/test_observatory_store.py`

**Step 1: Write failing tests**

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

**Step 2: Run to confirm fails**

```bash
uv run pytest agent-evals/tests/test_observatory_store.py::test_update_heartbeat_sets_timestamp -v
```
Expected: `AttributeError` — no `update_heartbeat` method and no `heartbeat_at` on RunSummary

**Step 3: Add schema migration**

In `store.py` `_init_db()`, add a safe schema migration:
```python
try:
    conn.execute("ALTER TABLE runs ADD COLUMN heartbeat_at TEXT")
except Exception:
    pass  # Column already exists
```

Add `heartbeat_at: str | None = None` to the `RunSummary` dataclass.

**Step 4: Add store methods**

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

**Step 5: Run tests**

```bash
uv run pytest agent-evals/tests/test_observatory_store.py -v
```

**Step 6: Commit (store changes only)**

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

**Step 1: Write failing test**

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

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_run_manager.py::test_heartbeat_updates_during_run -v
```

**Step 3: Add HeartbeatThread to run_manager.py**

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

**Step 4: Add async reaper to routes.py lifespan**

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

**Step 5: Run tests**

```bash
uv run pytest agent-evals/tests/test_run_manager.py -v
```

**Step 6: Commit (wiring changes only)**

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

**Step 1: Write failing test**

```python
def test_run_detail_includes_config(client, created_run_id):
    resp = client.get(f"/api/runs/{created_run_id}")
    data = resp.json()
    assert data.get("config") != {}, "config must not be hardcoded empty dict"
```

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_observatory_web.py::test_run_detail_includes_config -v
```

**Step 3: Implement**

In `store.py` `RunSummary` dataclass, add `config: dict = field(default_factory=dict)`.

Populate it in `list_runs()` and `get_run_summary()` by parsing the stored JSON config string.

In `routes.py` `_enrich_run()`, replace `"config": {}` with `"config": run.config`.

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_observatory_web.py -v
```

**Step 5: Commit**

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

**Step 1: Write failing test**

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

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_run_manager.py::test_model_name_without_slash_rejected -v
```

**Step 3: Implement**

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

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_run_manager.py -v
```

**Step 5: Commit**

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

**Step 1: Write failing test**

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
            score=i / 100.0,
            response="ok",
            prompt_tokens=10,
            completion_tokens=5,
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

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_observatory_store.py::test_get_run_aggregates_returns_correct_statistics -v
```

**Step 3: Add `get_run_aggregates()` to store**

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

**Step 4: Update `_enrich_run` in routes.py**

Read the existing `_enrich_run` function fully first. Replace the `store.get_trials(run_id)` call and all downstream Python-level aggregation with a single call to `store.get_run_aggregates(run_id)`. Map the returned dict fields to the existing response shape.

**Step 5: Run tests**

```bash
uv run pytest agent-evals/tests/test_observatory_store.py agent-evals/tests/test_observatory_web.py -v
```

**Step 6: Commit**

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

**Step 1: Write failing tests (one per bug)**

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

**Step 2: Run to confirm fails**

```bash
uv run pytest agent-evals/tests/test_observatory_web.py::test_list_runs_pagination_uses_sql_limit_offset -v
```

**Step 3: Add `limit`/`offset` to `store.list_runs()` SQL**

Add `pipeline_id` to the `RunSummary` dataclass and include it in the `list_runs()` SQL (join if needed) to eliminate per-run lookups in `list_pipelines`.

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_observatory_web.py agent-evals/tests/test_observatory_store.py -v
```

**Step 5: Commit**

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

**Step 1: Write failing test**

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

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_observatory_store.py::test_trial_record_includes_oa_row_id_and_phase -v
```

**Step 3: Implement**

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

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_observatory_store.py -v
```

**Step 5: Commit**

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

**Step 1: Write failing test**

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

**Step 2: Run to confirm fail**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui
npm test -- --testPathPattern=useSSE
```
Expected: test throws `SyntaxError: Unexpected token`

**Step 3: Implement**

In `useSSE.ts`, wrap both `JSON.parse(e.data)` calls:
```typescript
try {
  const parsed = JSON.parse(e.data);
  // ... existing logic
} catch (err) {
  console.error("[useSSE] malformed JSON event, skipping:", err);
}
```

**Step 4: Run tests**

```bash
npm test -- --testPathPattern=useSSE
```

**Step 5: Commit**

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

**Step 1: Write failing test**

```typescript
// useLiveMonitorState takes: useLiveMonitorState(totalTasksOverride?: number)
// It does NOT take { runId } — it selects the run ID internally via useActiveRuns().
// To test this hook in isolation, the test must mock useActiveRuns() to return a run ID.
// Read useLiveMonitorState.ts fully before writing this test to understand its internal queries.

it("scores array stays bounded after many trials", async () => {
  // Step A: Read useLiveMonitorState.ts to find which queries need mocking
  // (useActiveRuns, useRun, useTrials are all internal — must mock at TanStack Query level)
  // Step B: Mock useActiveRuns to return a fake run ID
  // Step C: Set up MockEventSource so trial_completed events are fired
  // The pattern below is a sketch — adjust to the actual internal dependencies:
  const { useLiveMonitorState } = await import("../../hooks/useLiveMonitorState");
  const wrapper = createWrapper();
  // Hook signature: useLiveMonitorState(totalTasksOverride?: number)
  // Run ID comes from internal useActiveRuns() — mock that query to return "run1"
  vi.mock("../../api/hooks", async () => {
    const actual = await vi.importActual("../../api/hooks");
    return { ...actual, useActiveRuns: () => [{ run_id: "run1", status: "active" }] };
  });
  const { result } = renderHook(() => useLiveMonitorState(), { wrapper });
  act(() => {
    for (let i = 0; i < 1500; i++) {
      MockEventSource.instances[0]?.emit("trial_completed", {
        score: 0.5, task_id: `t${i}`,
      });
    }
  });
  expect(result.current.scores.length).toBeLessThanOrEqual(1000);
});
```

**Step 2: Run to confirm fail**

```bash
npm test -- --testPathPattern=useLiveMonitorState
```

**Step 3: Implement**

```typescript
const MAX_SCORES = 1000;

// Change line 78:
setScores((prev) => {
  const next = [...prev, trial.score];
  return next.length > MAX_SCORES ? next.slice(-MAX_SCORES) : next;
});
```

**Step 4: Run tests**

```bash
npm test -- --testPathPattern=useLiveMonitorState
```

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/hooks/useLiveMonitorState.ts
git commit -m "fix(frontend): cap scores array at MAX_SCORES=1000 in useLiveMonitorState (N2)"
```

---

### Task 23: Migrate deleteGroup to fetchApi wrapper (N3 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/web/ui/src/api/client.ts:274`
- Test: existing client test file

**Step 1: Write failing test**

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

**Step 2: Run to confirm fail**

```bash
npm test -- --testPathPattern=client
```

**Step 3: Implement**

```typescript
export async function deleteGroup(groupId: string): Promise<void> {
  await fetchApi<void>(`/api/groups/${groupId}`, { method: "DELETE" });
}
```

**Step 4: Run tests**

```bash
npm test -- --testPathPattern=client
```

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/api/client.ts
git commit -m "fix(frontend): migrate deleteGroup to use fetchApi wrapper with timeout (N3)"
```

---

### Task 24: Clear poll interval when max SSE reconnects reached (N7 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/web/ui/src/hooks/useSSE.ts:69-100`
- Test: `useSSE.test.ts`

**Step 1: Write failing test**

```typescript
it("clears the poll interval when MAX_RECONNECTS is reached", () => {
  vi.useFakeTimers();
  const clearSpy = vi.spyOn(globalThis, "clearInterval");
  vi.stubGlobal("EventSource", MockEventSource);
  const { result } = renderHook(() => useSSE("run1"));
  // Trigger MAX_RECONNECTS errors via the mock EventSource
  act(() => {
    for (let i = 0; i <= 10; i++) {
      MockEventSource.instances[0]?.dispatchEvent(new Event("error"));
      vi.advanceTimersByTime(1000);
    }
  });
  expect(clearSpy).toHaveBeenCalled();
  vi.useRealTimers();
});
```

**Step 2: Run to confirm fail**

```bash
npm test -- --testPathPattern=useSSE
```

**Step 3: Implement**

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

**Step 4: Run tests**

```bash
npm test -- --testPathPattern=useSSE
```

**Step 5: Commit**

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

**Step 1: Write failing test**

```python
def test_yaml_summary_with_colon_is_parseable():
    import yaml
    variant = FormatYaml()   # NOT FormatYamlVariant()
    doc_tree = make_doc_tree(summary="JWT auth: token-based login")
    output = variant.render(doc_tree)   # render() takes DocTree, NOT list[DocFile]
    parsed = yaml.safe_load(output)  # Must not raise ScannerError
    assert parsed is not None
```

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_format_yaml.py::test_yaml_summary_with_colon_is_parseable -v
```
Expected: `yaml.scanner.ScannerError`

**Step 3: Implement**

```python
import yaml

# Replace the manual f-string line:
# f"    summary: {summary}"
# WITH: (uses safe_dump exclusively — never yaml.dump)
summary_value = yaml.safe_dump(summary).strip()
output_line = f"    summary: {summary_value}"
```

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_format_yaml.py -v
```

**Step 5: Commit**

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

**Step 1: Write failing test**

```python
def test_pipe_in_summary_does_not_add_extra_columns():
    variant = FormatPipeDelimited()   # NOT PipeDelimitedVariant()
    doc_tree = make_doc_tree(summary="A|B comparison")
    output = variant.render(doc_tree)   # render() takes DocTree, NOT list[DocFile]
    data_rows = [r for r in output.splitlines() if "comparison" in r]
    assert len(data_rows) == 1
    assert data_rows[0].count("|") == EXPECTED_PIPE_COUNT
```

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_format_pipe_delimited.py::test_pipe_in_summary_does_not_add_extra_columns -v
```

**Step 3: Implement**

Add helper in both variant files:
```python
def _escape_cell(text: str) -> str:
    return text.replace("|", "\\|")
```

Apply to all cell values in row-building code.

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_format_pipe_delimited.py -v
```

**Step 5: Commit**

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

**Step 1: Write failing test**

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

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_runner.py::test_trial_result_metrics_contains_timing_keys -v
```

**Step 3: Implement**

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

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_runner.py -v
```

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/runner.py agent-evals/tests/test_runner.py
git commit -m "fix(runner): populate TrialResult.metrics with timing data (E6)"
```

---

### Task 28: Filter NaN in bootstrap_ci (E7 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/scoring.py:257-318`
- Test: `agent-evals/tests/test_scoring.py`

**Step 1: Write failing test**

```python
def test_bootstrap_ci_handles_nan_without_producing_nan_output():
    import math
    data = [0.5, 0.6, float("nan"), 0.7, 0.8]
    result = bootstrap_ci(data)
    assert not math.isnan(result.low), "CI low must not be NaN"
    assert not math.isnan(result.high), "CI high must not be NaN"
```

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_scoring.py::test_bootstrap_ci_handles_nan_without_producing_nan_output -v
```

**Step 3: Implement**

Before the `np.asarray` line in `bootstrap_ci`:
```python
clean = [x for x in data if not (isinstance(x, float) and np.isnan(x))]
if len(clean) < 2:
    return BootstrapResult(low=float("nan"), high=float("nan"), n_valid=len(clean))
# use `clean` in np.asarray instead of `data`
arr = np.asarray(clean, dtype=np.float64)
```

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_scoring.py -v
```

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/scoring.py agent-evals/tests/test_scoring.py
git commit -m "fix(scoring): filter NaN values before bootstrap_ci computation (E7)"
```

---

### Task 29: Add base_task_id to robustness task metadata (E8 — LOW)

**Files:**
- Modify: `agent-evals/gold_standard/robustness/robustness_*.yaml` (30 files)
- Test: `agent-evals/tests/test_gold_standard_schema.py` (add to existing)

**Step 1: Check actual task ID format first**

```bash
ls agent-evals/gold_standard/robustness/ | head -5
```

Note the exact filename pattern (e.g., `robustness_001.yaml`) before writing the script.

**Step 2: Write failing test**

```python
def test_all_robustness_tasks_have_base_task_id():
    """Every robustness task must have base_task_id in metadata."""
    tasks = load_tasks_from_dir("agent-evals/gold_standard/robustness/")
    missing = [t["task_id"] for t in tasks if "base_task_id" not in t.get("metadata", {})]
    assert not missing, f"Missing base_task_id in {len(missing)} tasks: {missing[:5]}"
```

**Step 3: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_gold_standard_schema.py::test_all_robustness_tasks_have_base_task_id -v
```

**Step 4: Write and run fix script**

After inspecting actual task IDs and existing metadata to understand the naming convention:

```python
# scripts/add_robustness_base_task_ids.py (run once, then delete)
import yaml
from pathlib import Path

gold_dir = Path("agent-evals/gold_standard/robustness")
for f in sorted(gold_dir.glob("robustness_*.yaml")):
    data = yaml.safe_load(f.read_text())
    if "base_task_id" not in data.get("metadata", {}):
        # Inspect data["metadata"] to find the correct base task reference
        # e.g., if metadata has "original_task_id", use that
        # Otherwise infer from the task's metadata["derived_from"] or task_id pattern
        # VERIFY the inferred value against the gold_standard/ directory before applying
        base_id = data["metadata"].get("derived_from") or data["task_id"].replace("robustness_", "")
        data.setdefault("metadata", {})["base_task_id"] = base_id
        f.write_text(yaml.safe_dump(data, default_flow_style=False, allow_unicode=True))
print("Done. Review git diff before committing.")
```

**Review the diff manually:**
```bash
git diff agent-evals/gold_standard/robustness/ | head -60
```

**Step 5: Run test to verify**

```bash
uv run pytest agent-evals/tests/test_gold_standard_schema.py -v
```

**Step 6: Commit**

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

**Step 1: Write failing test**

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
    results = [runner._run_trial(task, variant, doc_tree, repetition=i) for i in range(1, 55)]
    judged = [r for r in results if "judge_score" in r.metrics]
    assert len(judged) >= 1, "At least one trial must be judge-sampled"
```

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_runner.py::test_judge_score_sampled_into_metrics -v
```

**Step 3: Implement Phase 1 sampling**

Add `_call_judge` as a **private method on `EvalRunner`** (NOT a module-level function — it needs access to `self._client`):

```python
from agent_evals.judge.calibrator import build_judge_prompt, parse_judge_response, JudgeScore

JUDGE_SAMPLE_RATE = 50  # 1 in every 50 trials (2%)
JUDGE_MODEL = "openrouter/openai/gpt-5-mini"  # cheap routine model

# Add to EvalRunner class as a method (NOT module-level — needs self._client):
def _call_judge(self, task_type: str, question: str, response: str) -> JudgeScore:
    """Call LLM judge for one trial.

    - build_judge_prompt() returns list[dict] messages (NOT a str)
    - parse_judge_response() takes str, returns tuple[float, str]
    - LLMClient.complete() takes list[dict], returns GenerationResult with .content
    """
    messages = build_judge_prompt(
        task_type=task_type,   # REQUIRED first arg
        question=question,
        response=response,
        rubric=None,
    )
    raw = self._client.complete(messages).content  # complete() takes list[dict]
    score, rationale = parse_judge_response(raw)   # unpack tuple[float, str]
    return JudgeScore(
        example_id="",
        judge_model=JUDGE_MODEL,
        score=score,
        rationale=rationale,
        raw_response=raw,
    )
```

Then add sampling to `_run_trial()` — the method already returns `metrics={}` (line 631). Change it to:
```python
# Add a trial_index parameter to _run_trial() so sampling is deterministic.
# In the ThreadPoolExecutor submission loop (runner.py ~lines 230-241), enumerate the submissions
# and pass the index as trial_index. Then inside _run_trial():
metrics: dict[str, object] = {}
if trial_index % JUDGE_SAMPLE_RATE == 0:
    try:
        judge_result = self._call_judge(
            task.definition.type,
            task.definition.question,
            generation.content,
        )
        metrics["judge_score"] = judge_result.score
        metrics["judge_heuristic_delta"] = abs(judge_result.score - score)
    except Exception:
        pass  # Judge failure must not affect trial outcome

return TrialResult(
    ...
    metrics=metrics,   # replace the hardcoded metrics={}
    ...
)
```

> **Implementation checklist:**
> 1. Add `trial_index: int` parameter to `_run_trial()` signature
> 2. Pass `trial_index=idx` from the futures submission loop (read lines 230-241)
> 3. Add `_call_judge` as an instance method on `EvalRunner`
> 4. Change `metrics={}` (line 631) to the populated dict above
> 5. Monkeypatch target in test: `"agent_evals.runner.EvalRunner._call_judge"` (not `"agent_evals.runner._call_judge"`)

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_runner.py -v
```

**Step 5: Commit**

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

**Step 1: Write failing test**

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

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_observatory_logging_config.py::test_setup_logging_creates_log_file_on_first_write -v
```
Expected: `ModuleNotFoundError: No module named 'agent_evals.observatory.logging_config'`

**Step 3: Create logging_config.py**

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

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_observatory_logging_config.py -v
```

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/logging_config.py \
        agent-evals/src/agent_evals/observatory/web/routes.py \
        agent-evals/tests/test_observatory_logging_config.py
git commit -m "feat(infra): add rotating JSON file logging to Observatory (I7)"
```

---

### Task 31: Auto-sync model catalog on server startup (I8 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/web/routes.py` (lifespan)
- Test: `agent-evals/tests/test_observatory_web.py`

**⚠️ Pre-implementation investigation required — read this FIRST:**

Verification found that `routes.py` and `server.py` currently have **NO lifespan context manager** and `ModelCatalog` has **NO `sync()` method**. Before writing the test, the implementer MUST:

1. **Check if Task 15b (HeartbeatThread) adds a lifespan.** If Task 15b adds a `@asynccontextmanager` lifespan to the FastAPI app, Task 31 can add the catalog sync to it. If Task 15b was NOT implemented yet, implement it first.

2. **Check ModelCatalog for the actual sync method name.** Read `agent-evals/src/agent_evals/observatory/model_catalog.py`. There is also a separate `ModelSync` class (`model_sync.py`) and `model_sync: ModelSync | None = None` parameter in `create_router()`. The "sync" may go through `ModelSync.sync_models()` or a different method name — verify before writing the test.

3. **Adjust the test to match the real method name.**

**Step 0: Investigate**
```bash
# Check ModelCatalog for sync-like methods
grep -n "def " agent-evals/src/agent_evals/observatory/model_catalog.py
# Check ModelSync
grep -n "def " agent-evals/src/agent_evals/observatory/model_sync.py
# Check if lifespan exists (added by Task 15b)
grep -n "lifespan\|asynccontextmanager" agent-evals/src/agent_evals/observatory/web/routes.py
```

**Step 1: Write failing test**

Once the actual method name and lifespan existence are confirmed, the test pattern is:
```python
@pytest.fixture
def mock_catalog():
    """Return a MagicMock for ModelCatalog."""
    from unittest.mock import MagicMock
    from agent_evals.observatory.model_catalog import ModelCatalog
    return MagicMock()  # use MagicMock() not spec=ModelCatalog if sync() doesn't exist yet

def test_model_catalog_sync_called_on_startup(mock_catalog, tmp_path):
    """Model catalog sync must be called during server lifespan startup."""
    from agent_evals.observatory.store import ObservatoryStore
    from agent_evals.observatory.tracker import EventTracker
    from agent_evals.observatory.web.routes import create_router
    from fastapi import FastAPI
    store = ObservatoryStore(db_path=tmp_path / "test.db")
    tracker = EventTracker(store=store)
    # Inject mock catalog into the router at creation time (create_router accepts catalog kwarg)
    router = create_router(store=store, tracker=tracker, catalog=mock_catalog)
    test_app = FastAPI()
    test_app.include_router(router)
    with TestClient(test_app) as _client:
        # Replace .sync with the actual method name confirmed in Step 0
        mock_catalog.sync.assert_called_once()
```

**Step 2: Run to confirm fail**

```bash
uv run pytest agent-evals/tests/test_observatory_web.py::test_model_catalog_sync_called_on_startup -v
```

**Step 3: Add sync call to lifespan**

In `routes.py`, ensure the lifespan (from Task 15b) includes:
```python
try:
    if catalog is not None:
        await asyncio.to_thread(catalog.sync)  # replace .sync() with actual method name
        logger.info("Model catalog synced on startup")
except Exception as e:
    logger.warning("Model catalog sync failed on startup: %s", e)
```

**Step 4: Run tests**

```bash
uv run pytest agent-evals/tests/test_observatory_web.py -v
```

**Step 5: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/routes.py
git commit -m "feat(infra): auto-sync model catalog on server startup (I8)"
```

---

## Sprint 9 — UX Polish + Data Quality (U1–U3, D3)

---

### Task 32: Add chart animation defaults (U1 — LOW)

**Files:**
- Create: `agent-evals/src/agent_evals/observatory/web/ui/src/utils/chartDefaults.ts`
- Modify: `Observatory.tsx`, `LiveMonitor.tsx`, `ResultsExplorer.tsx`, `History.tsx`, `FactorAnalysis.tsx`
- Test: add to relevant chart component tests

**Step 1: Write failing test**

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

**Step 2: Run to confirm fail**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui
npm test -- --testPathPattern=Observatory
```

**Step 3: Create chartDefaults.ts**

```typescript
export const CHART_ANIMATION = {
  duration: 800,
  easing: "easeOutQuart" as const,
} as const;
```

Apply to all chart option objects in the 5 pages listed above.

**Step 4: Run tests**

```bash
npm test
```

**Step 5: Commit**

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

**Step 1: Read the file first**

```bash
cat agent-evals/src/agent_evals/observatory/web/ui/src/components/CompassCheckbox.tsx
```

Identify any remaining `style={{...}}` attributes on SVG elements (the file is ~61 lines).

**Step 2: Write failing test if inline styles exist**

```typescript
it("CompassCheckbox has no inline style attributes on any element", () => {
  const { container } = render(<CompassCheckbox checked={false} onChange={vi.fn()} />);
  const inlineStyled = container.querySelectorAll("[style]");
  expect(inlineStyled.length).toBe(0);
});
```

**Step 3: Run to confirm fail**

```bash
npm test -- --testPathPattern=CompassCheckbox
```

**Step 4: Move any remaining inline styles to Tailwind classes**

**Step 5: Run tests + commit**

```bash
npm test -- --testPathPattern=CompassCheckbox
git add agent-evals/src/agent_evals/observatory/web/ui/src/components/CompassCheckbox.tsx
git commit -m "fix(ux): remove remaining inline styles from CompassCheckbox (U2)"
```

---

### Task 34: Add focus-visible style to SlideOutPanel close button (U3 — TRIVIAL)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/web/ui/src/components/SlideOutPanel.tsx:45`
- Test: component tests

**Step 1: Write failing test**

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

**Step 2: Run to confirm fail**

```bash
npm test -- --testPathPattern=SlideOutPanel
```

**Step 3: Implement**

```tsx
<button
  onClick={onClose}
  className="... focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
>
```

**Step 4: Run tests + commit**

```bash
npm test -- --testPathPattern=SlideOutPanel
git add agent-evals/src/agent_evals/observatory/web/ui/src/components/SlideOutPanel.tsx
git commit -m "fix(a11y): add focus-visible outline to SlideOutPanel close button (U3)"
```

---

### Task 35: Add SSE event sequence numbers (D3 — LOW)

**Files:**
- Modify: `agent-evals/src/agent_evals/observatory/web/routes.py` (SSE generator)
- Modify: `agent-evals/src/agent_evals/observatory/web/ui/src/hooks/useSSE.ts`
- Test: both backend and frontend tests

> **Note:** The sequence counter is module-level and resets on server restart. After a restart, clients that see ID 1 again will correctly treat it as fresh (their `lastEventId` ref is per-session). This is acceptable behavior.

**Step 1: Write failing test (backend)**

```python
def test_sse_events_include_monotonic_id(client):
    with client.stream("GET", f"/api/runs/run1/stream") as resp:
        lines = list(itertools.islice(resp.iter_lines(), 20))
    id_lines = [l for l in lines if l.startswith("id:")]
    assert len(id_lines) > 0, "SSE events must include id: fields"
    ids = [int(l.split(":")[1].strip()) for l in id_lines]
    assert ids == sorted(ids), "SSE event IDs must be monotonically increasing"
```

**Step 2: Add sequence counter to SSE generator in routes.py**

```python
import itertools
_sse_seq = itertools.count(1)

# In each SSE yield:
{"event": event_type, "id": str(next(_sse_seq)), "data": json.dumps(data)}
```

**Step 3: Add deduplication in useSSE.ts**

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

**Step 4: Run both test suites**

```bash
uv run pytest agent-evals/tests/test_observatory_web.py -v
cd agent-evals/src/agent_evals/observatory/web/ui && npm test -- --testPathPattern=useSSE
```

**Step 5: Commit**

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

**Step 1: Locate the router creation**

```bash
grep -r "createBrowserRouter\|BrowserRouter" agent-evals/src/agent_evals/observatory/web/ui/src/ --include="*.tsx"
```

**Step 2: Add future flags**

```typescript
createBrowserRouter(routes, {
  future: {
    v7_startTransition: true,
    v7_relativeSplatPath: true,
  },
})
```

**Step 3: Start dev server and verify warnings are gone**

```bash
cd agent-evals/src/agent_evals/observatory/web/ui && npm run dev
# Check browser console — React Router warnings must be absent
```

**Step 4: Commit**

```bash
git add agent-evals/src/agent_evals/observatory/web/ui/src/main.tsx
git commit -m "fix(frontend): opt into React Router v7 future flags (W1)"
```

---

## Sprint 11 — Validation: Confirm Scorer Fixes Work (D1, D2)

> **Run after all Sprint 1-3 scorer fixes are committed.** D1 (bimodal distribution) and D2 (compositional underscoring) are caused by scorer bugs — not independent code changes. This sprint validates the fixes actually worked.

---

### Task 41: Re-run compositional evaluation to confirm score distribution improved (D1, D2)

**This requires a live LLM call (not `--dry-run`).**

**Step 1: Confirm API key is set**

```bash
echo $OPENROUTER_API_KEY | head -c 20
```

**Step 2: Run a real evaluation on 100 compositional trials**

```bash
uv run agent-evals \
  --model openrouter/anthropic/claude-haiku-4-5-20251001 \
  --task-types compositional \
  --task-limit 100 \
  --output-format json \
  --output-path /tmp/compositional_validation.json
```

**Step 3: Check mean score and zero rate**

```bash
uv run python -c "
import json
data = json.load(open('/tmp/compositional_validation.json'))
scores = [t['score'] for t in data['trials']]
zeros = sum(1 for s in scores if s == 0.0)
print(f'Mean: {sum(scores)/len(scores):.3f}')
print(f'Zero rate: {zeros}/{len(scores)} = {zeros/len(scores):.1%}')
print(f'Mean before fix was 0.114 with 70% zeros — verify both improved')
"
```

**Expected outcomes:**
- Mean score must be > 0.30 (was 0.114)
- Zero rate must be < 30% (was 70%)

**Step 4: Document results**

Update `docs/plans/2026-03-02-observatory-known-issues.md` section D1/D2 with the post-fix distribution.

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

**Investigation tasks (D4, D5):** Tasks 38 and 39 are manual investigations with no automated tests. They are complete when a beads issue has been filed with root cause identified. They do not appear in the test suite pass/fail count.
