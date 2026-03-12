# Scoring & Pipeline Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 4 systemic issues that prevent the Taguchi DOE framework from producing statistically significant results: the `--limit` bug, broken code_generation scoring, blind judge prompts, and coarse scoring granularity.

**Architecture:** The `--limit` flag is fixed at the CLI layer. The judge is promoted from sampling-validator to primary scorer for semantic task types (code_generation, compositional, agentic) by passing gold standard metadata into reference-aware prompts. The heuristic scorers for remaining types get granularity improvements. Score routing in the pipeline uses judge_score when available for judge-primary types.

**Tech Stack:** Python 3.12, pytest, LiteLLM, SciPy/NumPy, rapidfuzz, SQLite (observatory)

---

## Task 1: Fix `--limit` flag (total vs per-type)

The `--limit N` flag is documented as "Max tasks per type" but the implementation caps at N tasks total via round-robin. With `--limit 5`, you get 5 tasks across 5 types instead of 55 tasks (5 per type x 11 types).

**Files:**
- Modify: `agent-evals/src/agent_evals/cli.py:813-835` (round-robin limit block — lines 808-811 are the task_id filter, keep those)
- Test: `agent-evals/tests/test_evals_cli.py`

> **Note:** `--limit` is separate from `--dataset-limit` (which caps HF dataset rows before task creation). This fix only affects `--limit`.

### Step 1: Extract limit logic into testable function

Add a **module-level** function (above `_run_evaluation`, NOT inside it — needed for test import `from agent_evals.cli import _apply_task_limit`):

```python
def _apply_task_limit(
    tasks: list,
    limit: int | None,
) -> list:
    """Return up to *limit* tasks per task type.

    When *limit* is ``None``, returns all tasks unchanged.
    """
    if limit is None:
        return tasks

    from collections import defaultdict

    by_type: dict[str, list] = defaultdict(list)
    for t in tasks:
        by_type[t.definition.type].append(t)

    selected: list = []
    for task_type in sorted(by_type.keys()):
        selected.extend(by_type[task_type][:limit])
    return selected
```

Then replace lines 813-835 (the round-robin block only) with:

```python
    tasks = _apply_task_limit(tasks, resolved.get("limit"))
```

### Step 2: Write failing tests

Add to `agent-evals/tests/test_evals_cli.py`:

```python
from unittest.mock import MagicMock
from agent_evals.cli import _apply_task_limit


def _make_task(task_type: str, task_id: str) -> MagicMock:
    t = MagicMock()
    t.definition.type = task_type
    t.definition.task_id = task_id
    return t


class TestApplyTaskLimit:
    def test_limit_none_returns_all(self):
        tasks = [_make_task("retrieval", f"r_{i}") for i in range(10)]
        result = _apply_task_limit(tasks, None)
        assert len(result) == 10

    def test_limit_caps_per_type(self):
        tasks = (
            [_make_task("retrieval", f"r_{i}") for i in range(5)]
            + [_make_task("code_generation", f"cg_{i}") for i in range(5)]
            + [_make_task("agentic", f"a_{i}") for i in range(5)]
        )
        result = _apply_task_limit(tasks, 2)
        assert len(result) == 6  # 2 per type x 3 types

    def test_limit_preserves_small_types(self):
        tasks = (
            [_make_task("retrieval", f"r_{i}") for i in range(10)]
            + [_make_task("canaries", "c_0")]
        )
        result = _apply_task_limit(tasks, 5)
        assert len(result) == 6  # 5 retrieval + 1 canary

    def test_limit_larger_than_type_count(self):
        tasks = [_make_task("retrieval", f"r_{i}") for i in range(3)]
        result = _apply_task_limit(tasks, 10)
        assert len(result) == 3

    def test_types_are_sorted(self):
        tasks = (
            [_make_task("z_type", "z_0")]
            + [_make_task("a_type", "a_0")]
        )
        result = _apply_task_limit(tasks, 1)
        assert result[0].definition.type == "a_type"
```

### Step 3: Run tests, verify pass

```bash
uv run pytest agent-evals/tests/test_evals_cli.py::TestApplyTaskLimit -v
```

### Step 4: Verify existing tests still pass

```bash
uv run pytest agent-evals/tests/test_evals_cli.py -v
```

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/cli.py agent-evals/tests/test_evals_cli.py
git commit -m "fix: --limit flag now caps per type, not total

The help text said 'Max tasks per type' but the round-robin
implementation capped at N total. Extracted _apply_task_limit()
and replaced with per-type slicing.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Reference-aware judge prompts

The judge currently receives only question + response, with no access to expected answers, test criteria, or canonical solutions. This makes it useless as a primary scorer.

**Files:**
- Modify: `agent-evals/src/agent_evals/judge/calibrator.py:303-333`
- Test: `agent-evals/tests/test_judge_calibration.py`

### Step 1: Write failing tests for new `build_judge_prompt` signature

Add to `agent-evals/tests/test_judge_calibration.py`:

```python
class TestBuildJudgePromptWithReference:
    def test_expected_answer_included_in_prompt(self):
        messages = build_judge_prompt(
            task_type="retrieval",
            question="What is X?",
            response="X is Y.",
            expected_answer="X is Y, discovered in 1990.",
        )
        user_content = messages[1]["content"]
        assert "Expected Answer" in user_content
        assert "X is Y, discovered in 1990." in user_content

    def test_canonical_solution_included_for_code(self):
        messages = build_judge_prompt(
            task_type="code_generation",
            question="Write a function...",
            response="def foo(): pass",
            canonical_solution="def foo():\n    return 42",
        )
        user_content = messages[1]["content"]
        assert "Reference Solution" in user_content
        assert "return 42" in user_content

    def test_test_criteria_included_for_code(self):
        messages = build_judge_prompt(
            task_type="code_generation",
            question="Write a function...",
            response="def foo(): pass",
            test_criteria={"entry_point": "foo", "test_patterns": ["return 42"]},
        )
        user_content = messages[1]["content"]
        assert "entry_point" in user_content.lower() or "Entry Point" in user_content
        assert "foo" in user_content

    def test_no_reference_fields_backward_compatible(self):
        messages = build_judge_prompt(
            task_type="retrieval",
            question="What is X?",
            response="X is Y.",
        )
        assert len(messages) == 2
        assert "Expected Answer" not in messages[1]["content"]

    def test_rubric_updated_for_reference_scoring(self):
        messages = build_judge_prompt(
            task_type="code_generation",
            question="Write...",
            response="def foo(): pass",
            canonical_solution="def foo(): return 42",
        )
        system_content = messages[0]["content"]
        assert "reference" in system_content.lower() or "canonical" in system_content.lower()
```

### Step 2: Run tests, verify they fail

```bash
uv run pytest agent-evals/tests/test_judge_calibration.py::TestBuildJudgePromptWithReference -v
```

### Step 3: Update `build_judge_prompt` signature and implementation

In `agent-evals/src/agent_evals/judge/calibrator.py`, update the function at line 303:

```python
def build_judge_prompt(
    task_type: str,
    question: str,
    response: str,
    rubric: str | None = None,
    *,
    expected_answer: str | None = None,
    canonical_solution: str | None = None,
    test_criteria: dict | None = None,
) -> list[dict[str, str]]:
    """Build the prompt for the LLM judge.

    When reference material (expected_answer, canonical_solution,
    test_criteria) is provided, the judge performs reference-based
    evaluation — scoring the response against the ground truth rather
    than relying on subjective quality assessment.
    """
    has_reference = any([expected_answer, canonical_solution, test_criteria])

    if has_reference:
        effective_rubric = rubric or _REFERENCE_RUBRICS.get(
            task_type, _DEFAULT_RUBRICS.get(task_type, _GENERIC_RUBRIC)
        )
    else:
        effective_rubric = rubric or _DEFAULT_RUBRICS.get(task_type, _GENERIC_RUBRIC)

    system_msg = _SYSTEM_TEMPLATE.format(
        task_type=task_type,
        rubric=effective_rubric,
    )

    # Build user message with optional reference sections
    parts = [f"## Question\n{question}"]

    if expected_answer:
        parts.append(f"## Expected Answer\n{expected_answer}")

    if canonical_solution:
        parts.append(f"## Reference Solution\n```\n{canonical_solution}\n```")

    if test_criteria:
        criteria_lines = []
        if "entry_point" in test_criteria:
            criteria_lines.append(f"- Entry Point: `{test_criteria['entry_point']}`")
        if "test_patterns" in test_criteria:
            for pat in test_criteria["test_patterns"]:
                criteria_lines.append(f"- Must contain: `{pat}`")
        if "libs" in test_criteria:
            criteria_lines.append(f"- Expected libraries: {', '.join(test_criteria['libs'])}")
        if "forbidden_patterns" in test_criteria:
            for pat in test_criteria["forbidden_patterns"]:
                criteria_lines.append(f"- Must NOT contain: `{pat}`")
        if criteria_lines:
            parts.append("## Test Criteria\n" + "\n".join(criteria_lines))

    parts.append(f"## Response to Evaluate\n{response}")

    user_msg = "\n\n".join(parts)

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]
```

### Step 4: Add reference-aware rubrics

Add above `_DEFAULT_RUBRICS` in `calibrator.py`:

```python
_REFERENCE_RUBRICS: dict[str, str] = {
    "code_generation": (
        "Score the code against the provided reference solution and test "
        "criteria. Check: (1) Does it define the expected entry point? "
        "(2) Does it match the test patterns? (3) Is it functionally "
        "equivalent to the reference? (4) Does it avoid forbidden patterns? "
        "Score 1.0 for a correct implementation, 0.0 for non-functional code."
    ),
    "compositional": (
        "Score the response against the expected answer. Check that ALL "
        "sub-parts of the question are addressed correctly. Score based on "
        "the fraction of sub-answers that match the expected answer."
    ),
    "agentic": (
        "Score the response against the expected answer. Evaluate the "
        "reasoning chain, tool usage, and final answer. Compare against "
        "the reference to determine correctness, not just plausibility."
    ),
}
```

### Step 5: Run tests, verify pass

```bash
uv run pytest agent-evals/tests/test_judge_calibration.py::TestBuildJudgePromptWithReference -v
```

### Step 6: Run all judge tests

```bash
uv run pytest agent-evals/tests/test_judge_calibration.py agent-evals/tests/test_judge_poll.py agent-evals/tests/test_judge_graduation.py -v
```

### Step 7: Commit

```bash
git add agent-evals/src/agent_evals/judge/calibrator.py agent-evals/tests/test_judge_calibration.py
git commit -m "feat: reference-aware judge prompts

build_judge_prompt() now accepts expected_answer, canonical_solution,
and test_criteria kwargs. When provided, the judge evaluates against
ground truth instead of subjective quality. Adds _REFERENCE_RUBRICS
for code_generation, compositional, and agentic types.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Judge-primary score routing

Add configuration and plumbing so certain task types use judge_score as the primary score for ANOVA/S/N calculations.

**Files:**
- Modify: `agent-evals/src/agent_evals/runner.py:98-134` (EvalRunConfig)
- Modify: `agent-evals/src/agent_evals/pipeline.py:45-65` (PipelineConfig — add `judge_primary_types` here too)
- Modify: `agent-evals/src/agent_evals/cli.py` (new CLI flag)
- Modify: `agent-evals/src/agent_evals/taguchi/runner.py:340-379` (always judge for primary types)
- Modify: `agent-evals/src/agent_evals/taguchi/runner.py:441-467` (pass metadata to judge)
- Modify: `agent-evals/src/agent_evals/pipeline.py` — `run_screening()` at line ~440 (screening score grouping) and `_group_refinement_scores()` at line ~216 (refinement score grouping)
- Modify: `agent-evals/src/agent_evals/runner.py:798` (EvalRunner._call_judge — returns `JudgeScore`, not `tuple`)
- Test: `agent-evals/tests/test_pipeline.py`, `agent-evals/tests/test_taguchi_runner.py`

> **Important:** `DOEPipeline.config` is `PipelineConfig` (line 45), NOT `EvalRunConfig`. Both need the field.
> `EvalRunner._call_judge` returns `JudgeScore` (a dataclass with `.score`, `.rationale`), not `tuple[float, str]` like `TaguchiRunner._call_judge`. Adapt accordingly.

### Step 1: Add config fields

In `agent-evals/src/agent_evals/runner.py`, add to `EvalRunConfig`:

```python
    judge_primary_types: frozenset[str] = field(default_factory=frozenset)
```

In `agent-evals/src/agent_evals/pipeline.py`, add to `PipelineConfig` (line ~65):

```python
    judge_primary_types: frozenset[str] = field(default_factory=frozenset)
```

> **Note:** Use `frozenset` (not `set`) for JSON serialization safety — `dataclasses.asdict()` converts frozenset to tuple, which is JSON-serializable. The CLI parsing converts the comma-separated string to `frozenset(...)`.  Alternatively use `tuple[str, ...]`.

### Step 2: Add CLI flag

In `agent-evals/src/agent_evals/cli.py`, in `_add_run_args()`:

```python
    parser.add_argument(
        "--judge-primary-types",
        type=str,
        default=None,
        help="Comma-separated task types that use judge as primary scorer "
             "(e.g. 'code_generation,compositional,agentic'). "
             "Implies --judge-enabled for those types.",
    )
```

In the config builder, parse the comma-separated string into a set:

```python
    judge_primary_raw = resolved.get("judge_primary_types")
    judge_primary_types = (
        frozenset(t.strip() for t in judge_primary_raw.split(",") if t.strip())
        if judge_primary_raw
        else frozenset()
    )
```

And set it on EvalRunConfig. If `judge_primary_types` is non-empty, force `judge_enabled = True`.

### Step 3: Write failing test for always-judge behavior in TaguchiRunner

In `agent-evals/tests/test_taguchi_runner.py` (or the appropriate test file):

```python
class TestJudgePrimaryRouting:
    def test_judge_always_called_for_primary_types(self):
        """Judge should fire on every trial for judge-primary task types,
        not just at sample_rate intervals."""
        axes = {1: ["flat", "2tier", "3tier"]}
        design = _make_simple_design(n_rows=3, axes=axes)
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(
            repetitions=1, max_connections=1,
            judge_enabled=True, judge_sample_rate=100,  # high rate = sampling would skip
            judge_model="openrouter/test/judge-model",
            judge_primary_types=frozenset({"code_generation"}),
        )

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        judge_calls: list[str] = []

        def tracking_judge(self_inner, client, task_type, question, response, **kwargs):
            judge_calls.append(task_type)
            return 0.85, "good answer"

        runner._call_judge = tracking_judge.__get__(runner)  # bind as method

        # code_generation tasks are judge-primary
        tasks = [make_mock_task(f"cg_{i:03d}", task_type="code_generation") for i in range(3)]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        # 3 rows * 3 tasks * 1 rep = 9 trials; trial_index 0 always skipped
        assert len(result.trials) == 9
        judged = [t for t in result.trials if t.metrics.get("judge_score") is not None]
        assert len(judged) >= 8, (
            f"Expected >= 8 judged trials for judge-primary type, got {len(judged)}"
        )

    def test_judge_sampled_for_non_primary_types(self):
        """Non-primary types should still use sampling."""
        axes = {1: ["flat", "2tier", "3tier"]}
        design = _make_simple_design(n_rows=3, axes=axes)
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(
            repetitions=1, max_connections=1,
            judge_enabled=True, judge_sample_rate=5,
            judge_model="openrouter/test/judge-model",
            judge_primary_types=frozenset({"code_generation"}),  # retrieval NOT primary
        )

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        judge_calls: list[str] = []

        def tracking_judge(self_inner, client, task_type, question, response, **kwargs):
            judge_calls.append(task_type)
            return 0.80, "ok"

        runner._call_judge = tracking_judge.__get__(runner)

        # retrieval tasks — NOT judge-primary
        tasks = [make_mock_task(f"ret_{i:03d}", task_type="retrieval") for i in range(4)]
        doc_tree = MagicMock()

        result = runner.run(tasks, doc_tree)

        # 3 rows * 4 tasks * 1 rep = 12 trials
        assert len(result.trials) == 12
        judged = [t for t in result.trials if t.metrics.get("judge_score") is not None]
        # sample_rate=5 → only trial indices 5, 10 fire (index 0 skipped)
        assert len(judged) <= 3, (
            f"Expected <= 3 judged trials for sampled non-primary type, got {len(judged)}"
        )

    def test_judge_metadata_passed_for_primary_types(self):
        """Judge prompt should include expected_answer and test_criteria
        for judge-primary task types."""
        axes = {1: ["flat"]}
        design = _make_simple_design(n_rows=1, axes=axes)
        variants = _make_variant_lookup(axes)
        client = make_mock_client()
        config = EvalRunConfig(
            repetitions=2, max_connections=1,
            judge_enabled=True, judge_sample_rate=1,
            judge_model="openrouter/test/judge-model",
            judge_primary_types=frozenset({"code_generation"}),
        )

        runner = TaguchiRunner(
            clients={"mock-model": client},
            config=config,
            design=design,
            variant_lookup=variants,
        )

        captured_kwargs: list[dict] = []

        def capture_judge(self_inner, client, task_type, question, response, **kwargs):
            captured_kwargs.append(kwargs)
            return 0.8, "mocked"

        runner._call_judge = capture_judge.__get__(runner)

        # Create a code_generation task with explicit metadata
        task = make_mock_task("cg_001", task_type="code_generation")
        task.definition.metadata = {
            "expected_answer": "def foo(): return 42",
            "canonical_solution": "def foo():\n    return 42",
            "entry_point": "foo",
            "test": "assert foo() == 42",
            "libs": ["math"],
            "forbidden_patterns": ["eval("],
        }
        doc_tree = MagicMock()

        runner.run([task], doc_tree)

        assert len(captured_kwargs) >= 1, "Judge should have been called at least once"
        kw = captured_kwargs[0]
        assert kw.get("expected_answer") == "def foo(): return 42"
        assert kw.get("canonical_solution") == "def foo():\n    return 42"
        assert "test_criteria" in kw
        assert kw["test_criteria"]["entry_point"] == "foo"
```

### Step 4: Modify TaguchiRunner._run_trial for always-judge

In `agent-evals/src/agent_evals/taguchi/runner.py`, update the judge activation logic at line ~355:

```python
            is_judge_primary = (
                task.definition.type in self._config.judge_primary_types
            )
            judge_active = (
                self._config.judge_enabled
                and trial_index > 0
                and (
                    is_judge_primary
                    or trial_index % sample_rate == 0
                )
            )
```

### Step 5: Pass task metadata to judge for primary types

Update `_call_judge` in TaguchiRunner (line ~441) to accept and pass metadata:

```python
    def _call_judge(
        self,
        client: LLMClient,
        task_type: str,
        question: str,
        response: str,
        *,
        expected_answer: str | None = None,
        canonical_solution: str | None = None,
        test_criteria: dict | None = None,
    ) -> tuple[float, str]:
        from agent_evals.judge.calibrator import (
            build_judge_prompt,
            parse_judge_response,
        )

        judge_model = self._config.judge_model
        messages = build_judge_prompt(
            task_type=task_type,
            question=question,
            response=response,
            rubric=None,
            expected_answer=expected_answer,
            canonical_solution=canonical_solution,
            test_criteria=test_criteria,
        )
        raw = client.complete(messages, model=judge_model).content
        score, rationale = parse_judge_response(raw)
        return score, rationale
```

Update the call site (line ~365) to extract metadata from the task definition:

```python
            if judge_active:
                try:
                    question = getattr(task.definition, "question", None) or ""
                    meta = task.definition.metadata or {}
                    task_type = task.definition.type

                    judge_kwargs = {}
                    if is_judge_primary:
                        # Type-specific metadata extraction:
                        # Gold standard schemas differ by task type.
                        if task_type == "code_generation":
                            # Keys: expected_answer, canonical_solution, entry_point, test, libs, forbidden_patterns
                            judge_kwargs["expected_answer"] = meta.get("expected_answer")
                            judge_kwargs["canonical_solution"] = meta.get("canonical_solution")
                            test_criteria = {}
                            if meta.get("entry_point"):
                                test_criteria["entry_point"] = meta["entry_point"]
                            if meta.get("test"):
                                test_criteria["test_patterns"] = [
                                    p for p in meta["test"].split("\n") if p.strip()
                                ]
                            if meta.get("libs"):
                                test_criteria["libs"] = meta["libs"]
                            if meta.get("forbidden_patterns"):
                                test_criteria["forbidden_patterns"] = meta["forbidden_patterns"]
                            if test_criteria:
                                judge_kwargs["test_criteria"] = test_criteria

                        elif task_type == "compositional":
                            # Keys: sub_questions (list), expected_answers (list)
                            expected_answers = meta.get("expected_answers", [])
                            sub_questions = meta.get("sub_questions", [])
                            if expected_answers:
                                # Join into a structured reference string
                                parts = []
                                for i, (q, a) in enumerate(
                                    zip(sub_questions, expected_answers), 1
                                ):
                                    parts.append(f"{i}. {q}: {a}")
                                judge_kwargs["expected_answer"] = "\n".join(parts)

                        elif task_type == "agentic":
                            # Keys: expected_tools, files, FAIL_TO_PASS, PASS_TO_PASS
                            expected_tools = meta.get("expected_tools", [])
                            files = meta.get("files", {})
                            fail_to_pass = meta.get("FAIL_TO_PASS", [])
                            ref_parts = []
                            if expected_tools:
                                ref_parts.append(
                                    "Expected tools: " + ", ".join(
                                        t.get("name", "") for t in expected_tools
                                    )
                                )
                            if files:
                                ref_parts.append(
                                    "Key files: " + ", ".join(files.keys())
                                )
                            if fail_to_pass:
                                ref_parts.append(
                                    "Must-pass tests: " + ", ".join(fail_to_pass)
                                )
                            if ref_parts:
                                judge_kwargs["expected_answer"] = "\n".join(ref_parts)

                    judge_score, _rationale = self._call_judge(
                        client, task.definition.type,
                        question, strategy_result.final_response,
                        **judge_kwargs,
                    )
                    metrics["judge_score"] = judge_score
                    metrics["judge_heuristic_delta"] = round(
                        abs(judge_score - score), 4,
                    )
                except Exception:
                    logger.warning(
                        "Judge call failed (row %d, %s)",
                        row.run_id, task.definition.task_id,
                        exc_info=True,
                    )
```

### Step 6: Update pipeline score aggregation

In `agent-evals/src/agent_evals/pipeline.py`, update the **screening** row_scores loop in `run_screening()` (line ~443, the `for trial in result.trials` loop):

```python
            # Use judge_score for judge-primary types when available
            effective_score = trial.score
            if (
                trial.task_type in self.config.judge_primary_types
                and trial.metrics
                and "judge_score" in trial.metrics
            ):
                effective_score = trial.metrics["judge_score"]

            row_scores[int(row_id)].append(effective_score)
```

Apply the same pattern to the **refinement** aggregation in `_group_refinement_scores()` (line ~216). **Critical:** This method is a `@staticmethod` — it has no `self` and cannot access `self.config`. Two options:

**Option A (recommended):** Add a `judge_primary_types` parameter to the static method signature:

```python
    @staticmethod
    def _group_refinement_scores(
        trials: list[Any],
        design: Any,
        judge_primary_types: frozenset[str] = frozenset(),
    ) -> dict[int, list[float]]:
```

Update all callers of `_group_refinement_scores` to pass `judge_primary_types=self.config.judge_primary_types`.

**Option B:** Remove `@staticmethod` and convert to an instance method with `self` access. This is a larger change and may break existing callers.

**With either option**, this method has **four separate `trial.score` append sites** (fast path at line 262, composite name at 273, composite sorted at 285, single-variant at 296). Extract a helper to compute effective score once and use it at ALL four append sites:

```python
def _effective_score(
    trial: Any, judge_primary_types: frozenset[str],
) -> float:
    """Return judge_score for judge-primary types, else trial.score."""
    if (
        trial.task_type in judge_primary_types
        and trial.metrics
        and "judge_score" in trial.metrics
    ):
        return trial.metrics["judge_score"]
    return trial.score
```

Then in `_group_refinement_scores`, right after `if trial.error is not None: continue`:

```python
            score = _effective_score(trial, judge_primary_types)
```

And replace all four `trial.score` references in append calls with `score`.

Use the same `_effective_score` helper in `run_screening()` (line ~447) for consistency.

> **Note:** No `hasattr` guard needed — `PipelineConfig.judge_primary_types` defaults to empty `frozenset()`, so the `in` check is always safe.

### Step 7: Adapt EvalRunner._call_judge (different return type, two code paths)

Apply equivalent changes to `agent-evals/src/agent_evals/runner.py` for the full-mode runner. **Key differences from TaguchiRunner:**

1. `EvalRunner._call_judge` (line 798) returns a `JudgeScore` dataclass (with `.score`, `.rationale` attributes), not `tuple[float, str]`
2. It has **two internal `build_judge_prompt` call sites**:
   - **Poll mode** (line ~823): inside `for model in poll_config.panel_models` loop
   - **Routine mode** (line ~851): single call

Both must receive the new kwargs.

- Add `expected_answer`, `canonical_solution`, `test_criteria` kwargs to the signature
- Pass them through to `build_judge_prompt()` at **both** call sites (poll and routine)
- The caller at line ~1067 already uses `judge_result.score`, so the return type stays the same
- Update the judge activation logic to always call for `judge_primary_types`
- Extract metadata from `task.definition.metadata` before calling

### Step 7b: Wire `judge_primary_types` into PipelineConfig construction sites

In `cli.py`, pass `judge_primary_types=judge_primary_types` to **both** `PipelineConfig(...)` calls:
- Line ~1144 (taguchi pipeline construction)
- Line ~1233 (multi-strategy pipeline construction)

Also check `observatory/run_manager.py:368` if it constructs `PipelineConfig`.

### Step 7c: Write tests for EvalRunner judge-primary routing

Add to `agent-evals/tests/test_runner.py` (alongside the existing `test_judge_score_sampled_into_metrics` at line ~1616):

```python
class TestEvalRunnerJudgePrimary:
    def test_judge_always_called_for_primary_types(self, monkeypatch) -> None:
        """EvalRunner should call judge on every trial for judge-primary types."""
        config = EvalRunConfig(
            repetitions=1,
            max_connections=1,
            judge_enabled=True,
            judge_sample_rate=100,  # high rate — would normally skip
            judge_model="openrouter/test/judge",
            judge_primary_types=frozenset({"code_generation"}),
        )
        runner = EvalRunner(config=config, client=make_mock_client())

        judge_call_count = 0
        original = runner._call_judge

        def counting_judge(task_type, question, response, **kwargs):
            nonlocal judge_call_count
            judge_call_count += 1
            return original(task_type, question, response, **kwargs)

        monkeypatch.setattr(runner, "_call_judge", counting_judge)

        tasks = [make_mock_task(f"cg_{i}", task_type="code_generation") for i in range(3)]
        variants = [make_mock_variant()]
        doc_tree = MagicMock()

        result = runner.run(tasks, variants, doc_tree)

        # Every code_generation trial should invoke judge (not sampled)
        cg_trials = [t for t in result.trials if t.task_type == "code_generation"]
        assert judge_call_count >= len(cg_trials) - 1  # index 0 may be skipped

    def test_judge_kwargs_passed_to_build_prompt(self, monkeypatch) -> None:
        """EvalRunner should pass metadata kwargs to build_judge_prompt for primary types."""
        config = EvalRunConfig(
            repetitions=1,
            max_connections=1,
            judge_enabled=True,
            judge_sample_rate=1,
            judge_model="openrouter/test/judge",
            judge_primary_types=frozenset({"code_generation"}),
        )
        runner = EvalRunner(config=config, client=make_mock_client())

        captured_kwargs: list[dict] = []
        original = runner._call_judge

        def capture_judge(task_type, question, response, **kwargs):
            captured_kwargs.append(kwargs)
            return original(task_type, question, response, **kwargs)

        monkeypatch.setattr(runner, "_call_judge", capture_judge)

        task = make_mock_task("cg_001", task_type="code_generation")
        task.definition.metadata = {
            "expected_answer": "def foo(): return 42",
            "canonical_solution": "def foo():\n    return 42",
            "entry_point": "foo",
            "test": "assert foo() == 42\nfoo()",
        }
        variants = [make_mock_variant()]
        doc_tree = MagicMock()

        runner.run([task], variants, doc_tree)

        assert len(captured_kwargs) >= 1
        kw = captured_kwargs[0]
        assert kw.get("expected_answer") == "def foo(): return 42"
```

### Step 8: Run tests

```bash
uv run pytest agent-evals/tests/test_pipeline.py agent-evals/tests/test_taguchi_runner.py agent-evals/tests/test_runner.py -v
```

### Step 9: Run full test suite

```bash
uv run pytest agent-evals/tests/ -x -q
```

### Step 10: Commit

```bash
git add agent-evals/src/agent_evals/runner.py \
  agent-evals/src/agent_evals/cli.py \
  agent-evals/src/agent_evals/taguchi/runner.py \
  agent-evals/src/agent_evals/pipeline.py \
  agent-evals/src/agent_evals/observatory/run_manager.py \
  agent-evals/tests/test_pipeline.py \
  agent-evals/tests/test_taguchi_runner.py \
  agent-evals/tests/test_runner.py
git commit -m "feat: judge-primary scoring for semantic task types

Adds --judge-primary-types CLI flag. For specified types, the judge
runs on every trial (not sampled) and its score is used for S/N
ratio and ANOVA instead of the heuristic score. Task metadata
(expected_answer, test_criteria, canonical_solution) is passed to
the judge prompt for reference-based evaluation.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Scoring granularity — multi_hop (P0)

Replace binary per-step threshold with continuous partial credit.

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/multi_hop.py:112`
- Test: `agent-evals/tests/test_task_multi_hop.py`

### Step 1: Write failing tests

Add to `agent-evals/tests/test_task_multi_hop.py`:

```python
class TestMultiHopContinuousScoring:
    def test_below_threshold_gets_partial_credit(self):
        """Coverage below 30% threshold should get partial credit, not zero."""
        task = _multi_hop_task(
            reasoning_chain=["alpha bravo charlie delta echo"],
        )
        # Response has 1/5 keywords = 20% coverage (below 30% threshold)
        score = task.score_response("alpha")
        assert 0.0 < score < 0.3  # partial credit, not zero

    def test_above_threshold_gets_full_coverage(self):
        """Coverage above threshold should still use actual coverage value."""
        task = _multi_hop_task(
            reasoning_chain=["alpha bravo charlie delta echo"],
        )
        # 3/5 keywords = 60% coverage
        score = task.score_response("alpha bravo charlie")
        assert score >= 0.5

    def test_zero_coverage_still_zero(self):
        """No keywords matched should still score 0.0."""
        task = _multi_hop_task(
            reasoning_chain=["alpha bravo charlie"],
        )
        score = task.score_response("xyz nothing here")
        assert score == 0.0

    def test_monotonic_with_coverage(self):
        """Higher coverage always produces higher or equal score."""
        task = _multi_hop_task(
            reasoning_chain=["alpha bravo charlie delta echo"],
        )
        s1 = task.score_response("alpha")          # 1/5 = 20%
        s2 = task.score_response("alpha bravo")     # 2/5 = 40%
        s3 = task.score_response("alpha bravo charlie delta echo")  # 5/5
        assert s1 <= s2 <= s3
```

### Step 2: Run tests, verify they fail

```bash
uv run pytest agent-evals/tests/test_task_multi_hop.py::TestMultiHopContinuousScoring -v
```

### Step 3: Implement continuous scoring

In `agent-evals/src/agent_evals/tasks/multi_hop.py`, replace line 112:

```python
            score_sum += coverage if coverage >= STEP_COVERAGE_THRESHOLD else 0.0
```

with:

```python
            if coverage >= STEP_COVERAGE_THRESHOLD:
                score_sum += coverage
            elif coverage > 0:
                # Below threshold: quadratic ramp gives partial credit
                # while still penalizing weak coverage.
                # At threshold boundary: ramp == coverage (continuous).
                score_sum += coverage * (coverage / STEP_COVERAGE_THRESHOLD)
            # coverage == 0: contributes 0.0 (no change needed)
```

### Step 4: Fix breaking existing test

Line 343 of `test_task_multi_hop.py` asserts `score == 0.0` for 20% coverage. After the quadratic ramp, 20% coverage produces `0.20 * (0.20 / 0.30) ≈ 0.133`. Update:

```python
# Line 343: change from
assert score == 0.0, f"Expected 0.0 for 20% coverage, got {score}"
# to
assert 0.0 < score < 0.3, f"Expected partial credit for 20% coverage, got {score}"
```

### Step 5: Run all multi_hop tests, verify pass

```bash
uv run pytest agent-evals/tests/test_task_multi_hop.py -v
```

### Step 6: Commit

```bash
git add agent-evals/src/agent_evals/tasks/multi_hop.py agent-evals/tests/test_task_multi_hop.py
git commit -m "feat: continuous scoring for multi_hop steps

Replace binary threshold with quadratic ramp below 30%. Coverage
at 20% now gets partial credit (~0.13) instead of 0.0. Maintains
continuity at the threshold boundary.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Scoring granularity — fact_extraction/robustness (P1)

Replace step-function cascade with linear interpolation within fuzzy-score bands. Also extract shared logic to eliminate code duplication between fact_extraction and robustness.

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/fact_extraction.py:92-117`
- Modify: `agent-evals/src/agent_evals/tasks/robustness.py` (equivalent section)
- Test: `agent-evals/tests/test_task_fact_extraction.py`, `agent-evals/tests/test_task_robustness.py`

### Step 1: Write failing tests

Add to `agent-evals/tests/test_task_fact_extraction.py`:

```python
class TestFuzzyScoreContinuous:
    """Tests for linear interpolation within fuzzy-score bands.

    IMPORTANT: token_set_ratio returns 100.0 whenever ALL tokens of the
    expected string appear in the response. To test specific bands, the
    response must be MISSING at least one expected token (replaced with
    a synonym) so the fuzzy score lands in the desired range.

    All inputs below were verified empirically:
      - "database connection pooling strategy" vs "...pooling approach..."  -> 85.71
      - "distributed cache invalidation broadcast notification service handler"
        vs "...service processor"  -> 93.8
      - "database connection pooling strategy" vs "...pooling mechanism..." -> 75.0
    """

    def test_fuzzy_85_scores_above_0_9(self):
        """Fuzzy=85.71 should map to ~0.905 via [85,100] -> [0.9,1.0]."""
        task = _fact_task(
            expected_answer="database connection pooling strategy",
            answer_aliases=[],
        )
        # Missing "strategy", has "approach" instead → fuzzy=85.71, no exact match
        score = task.score_response(
            "the database connection pooling approach handles resources"
        )
        assert score >= 0.9, f"Expected >= 0.9 for fuzzy=85.71, got {score}"

    def test_fuzzy_94_scores_between_0_9_and_1(self):
        """Fuzzy=93.8 should map to ~0.959, strictly between 0.9 and 1.0."""
        task = _fact_task(
            expected_answer=(
                "distributed cache invalidation broadcast notification service handler"
            ),
            answer_aliases=[],
        )
        # Missing "handler", has "processor" instead → fuzzy=93.8, no exact match
        score = task.score_response(
            "the distributed cache invalidation broadcast notification service processor"
        )
        assert 0.9 < score < 1.0, (
            f"Expected strictly between 0.9 and 1.0 for fuzzy=93.8, got {score}"
        )

    def test_fuzzy_75_scores_between_0_7_and_0_9(self):
        """Fuzzy=75.0 should map to ~0.767 via [70,85) -> [0.7,0.9)."""
        task = _fact_task(
            expected_answer="database connection pooling strategy",
            answer_aliases=[],
        )
        # Missing "connection" and "strategy" → fuzzy=75.0, no exact match
        score = task.score_response(
            "a database pooling mechanism for connections"
        )
        assert 0.7 <= score < 0.9, (
            f"Expected between 0.7 and 0.9 for fuzzy=75.0, got {score}"
        )

    def test_monotonic_with_fuzzy_score(self):
        """Higher fuzzy score always produces higher or equal final score."""
        task = _fact_task(
            expected_answer="database connection pooling strategy",
            answer_aliases=[],
        )
        # fuzzy=85.71 (missing "strategy") → score ~0.905
        s_high = task.score_response(
            "the database connection pooling approach handles resources"
        )
        # fuzzy=75.0 (missing "connection" + "strategy") → score ~0.767
        s_mid = task.score_response(
            "a database pooling mechanism for connections"
        )
        # fuzzy=65.38 (only 2/4 tokens match) → score ~0.654
        s_low = task.score_response(
            "the database has a caching strategy"
        )
        assert s_low <= s_mid <= s_high, (
            f"Monotonicity violated: low={s_low}, mid={s_mid}, high={s_high}"
        )
```

### Step 2: Implement linear interpolation

In `agent-evals/src/agent_evals/tasks/fact_extraction.py`, replace the step-function thresholds only (lines 113-116 — keep lines 104-112 which compute `fuzzy_score`):

```python
        # Layer 3: Continuous fuzzy matching
        fuzzy_score = fuzz.token_set_ratio(
            norm_expected,
            norm_response,
            processor=fuzz_utils.default_process,
        )
        if fuzzy_score >= 85.0:
            # Map [85, 100] -> [0.9, 1.0]
            return 0.9 + 0.1 * (fuzzy_score - 85.0) / 15.0
        if fuzzy_score >= 70.0:
            # Map [70, 85) -> [0.7, 0.9)
            return 0.7 + 0.2 * (fuzzy_score - 70.0) / 15.0
        if fuzzy_score >= 50.0:
            # Map [50, 70) -> [0.5, 0.7)
            return 0.5 + 0.2 * (fuzzy_score - 50.0) / 20.0
        # Below 50: falls through to keyword fallback (Layer 4, lines 118+)
        # This is intentional — fuzzy and keyword scoring are different algorithms
        # so there may be a small discontinuity at the 50-point boundary.
```

Apply the same change to `robustness.py`.

### Step 3: Run tests, verify pass

```bash
uv run pytest agent-evals/tests/test_task_fact_extraction.py agent-evals/tests/test_task_robustness.py -v
```

### Step 4: Update any tests that assert exact step values

Existing tests that assert `== 0.9` or `== 0.7` need to become range assertions (e.g., `>= 0.9` or `0.7 <= score < 0.9`).

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/tasks/fact_extraction.py agent-evals/src/agent_evals/tasks/robustness.py \
  agent-evals/tests/test_task_fact_extraction.py agent-evals/tests/test_task_robustness.py
git commit -m "feat: continuous fuzzy scoring for fact_extraction and robustness

Replace step-function cascade (0.7/0.9 bands) with linear interpolation.
fuzzy=77.5 now scores ~0.8 instead of flat 0.7. Adds [50,70) band to
fill the dead zone between keyword fallback and fuzzy matching.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Scoring granularity — conflicting (P1)

Add source awareness and strategy recognition axes.

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/conflicting.py`
- Test: `agent-evals/tests/test_task_conflicting.py`

### Step 1: Write failing tests

```python
class TestConflictingMultiAxis:
    def test_correct_resolution_plus_sources_scores_higher(self):
        """Response mentioning sources should score higher than bare answer."""
        task = _conflicting_task(
            expected_resolution="use version 2",
            sources=[
                {"name": "config.yaml", "claim": "version 1", "authority": 3},
                {"name": "README.md", "claim": "version 2", "authority": 5},
            ],
        )
        bare = task.score_response("use version 2")
        with_sources = task.score_response(
            "config.yaml says version 1 but README.md says version 2. use version 2"
        )
        assert with_sources > bare

    def test_wrong_resolution_with_sources_gets_partial(self):
        """Wrong answer but acknowledging sources gets partial credit."""
        task = _conflicting_task(
            expected_resolution="use version 2",
            sources=[
                {"name": "config.yaml", "claim": "version 1", "authority": 3},
                {"name": "README.md", "claim": "version 2", "authority": 5},
            ],
        )
        score = task.score_response(
            "config.yaml and README.md conflict. I recommend version 1."
        )
        assert 0.0 < score < 0.5  # partial from source awareness
```

### Step 2: Implement 3-axis scoring

Update `score_response` in `conflicting.py`:

```python
    def score_response(self, response: str, **kwargs: object) -> float:
        response_lower = response.lower()

        # Axis 1: Resolution correctness (50%)
        resolution_score = self._score_resolution(response_lower)

        # Axis 2: Source awareness (30%)
        source_score = self._score_source_awareness(response_lower)

        # Axis 3: Strategy recognition (20%)
        strategy_score = self._score_strategy(response_lower)

        score = (
            resolution_score * 0.5
            + source_score * 0.3
            + strategy_score * 0.2
        )
        return max(0.0, min(1.0, score))
```

Where `_score_resolution` contains the existing logic **including pipe-separated alternative handling** from `_score_alternatives` (e.g., `expected_resolution="use v2|adopt version 2"` must try all alternatives), `_score_source_awareness` checks if source `"name"` values from the metadata `sources` list appear in the response (use `source.get("name")` — gold standard schema uses `name`, NOT `file`), and `_score_strategy` checks for resolution-strategy phrases (e.g., "conflict", "contradicts", "defer to", "higher authority").

> **Critical:** Do NOT drop the pipe-separated alternative logic from `_score_alternatives` (lines 97-123 of current code). It must be incorporated into `_score_resolution`.

### Step 3: Update existing `_conflicting_task` test helper

The existing `_conflicting_task()` helper at line 27 of `test_task_conflicting.py` uses `"file"` and `"authority_level"` keys, but the gold standard schema uses `"name"` and `"authority"`. Update the helper to match:

```python
def _conflicting_task(**meta_overrides: Any) -> ConflictingTask:
    meta: dict[str, Any] = {
        "sources": [
            {"name": "config.md", "claim": "The timeout is 30 seconds", "authority": 3},
            {"name": "api-reference.md", "claim": "The timeout is 60 seconds", "authority": 5},
        ],
        "expected_resolution": "The timeout is 60 seconds",
        "resolution_strategy": "highest_authority",
    }
    meta.update(meta_overrides)
    ...
```

### Step 4: Run tests, fix any regressions

```bash
uv run pytest agent-evals/tests/test_task_conflicting.py -v
```

### Step 5: Commit

```bash
git add agent-evals/src/agent_evals/tasks/conflicting.py agent-evals/tests/test_task_conflicting.py
git commit -m "feat: 3-axis scoring for conflicting tasks

Decompose into resolution correctness (50%), source awareness (30%),
and strategy recognition (20%). Increases distinct score values from
~10 (N/11 fractions) to continuous distribution.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Scoring granularity — compositional (P0)

Add integration quality axis to measure cross-sub-task coherence.

**Files:**
- Modify: `agent-evals/src/agent_evals/tasks/compositional.py`
- Test: `agent-evals/tests/test_task_compositional.py`

### Step 1: Write failing tests

```python
class TestCompositionalMultiAxis:
    def test_integrated_response_scores_higher(self):
        """Response weaving sub-answers together should score higher than
        segregated answers."""
        task = _compositional_task(sub_tasks=[
            {"question": "What is X?", "expected_answer": "alpha beta"},
            {"question": "What is Y?", "expected_answer": "gamma delta"},
        ])
        segregated = task.score_response("alpha beta. gamma delta.")
        integrated = task.score_response(
            "alpha beta relates to gamma delta through their shared properties."
        )
        assert integrated >= segregated

    def test_organized_response_scores_higher(self):
        """Response with structure indicators (First..., Second...) should
        score higher than flat text."""
        task = _compositional_task(sub_tasks=[
            {"question": "Q1", "expected_answer": "answer one"},
            {"question": "Q2", "expected_answer": "answer two"},
        ])
        flat = task.score_response("answer one answer two")
        organized = task.score_response(
            "First, answer one. Second, answer two."
        )
        assert organized >= flat
```

### Step 2: Implement 3-axis scoring

Update `score_response` in `compositional.py`:

```python
    def score_response(self, response: str, **kwargs: object) -> float:
        if not self.sub_tasks:
            return 1.0

        response_lower = response.lower()

        # Axis 1: Sub-task completeness (50%) — wraps existing loop
        # over sub_tasks calling _score_sub_answer (which uses rapidfuzz
        # partial_ratio matching). Preserve that fuzzy matching.
        completeness = self._score_completeness(response_lower)

        # Axis 2: Integration quality (30%) — cross-sub-task keyword co-occurrence.
        # Algorithm: For each pair of adjacent sub-tasks, check if keywords from
        # both appear within the same sentence (split on ". "). Fraction of
        # adjacent pairs with co-occurrence = integration score.
        integration = self._score_integration(response_lower)

        # Axis 3: Response organization (20%) — structural markers
        organization = self._score_organization(response_lower)

        score = completeness * 0.5 + integration * 0.3 + organization * 0.2
        return max(0.0, min(1.0, score))
```

### Step 3: Run tests, fix regressions

```bash
uv run pytest agent-evals/tests/test_task_compositional.py -v
```

### Step 4: Commit

```bash
git add agent-evals/src/agent_evals/tasks/compositional.py agent-evals/tests/test_task_compositional.py
git commit -m "feat: 3-axis scoring for compositional tasks

Decompose into completeness (50%), integration quality (30%),
and organization (20%). Increases distinct score values from
6 (sub-task fractions) to continuous distribution.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Task 8: Confirm numpy bool fix and commit pipeline bug

The numpy `bool_` serialization fix from earlier this session needs a bead. Also create a bead for the `--resume-pipeline` bug discovered during testing.

**Files:**
- Already committed: `agent-evals/src/agent_evals/taguchi/analysis.py`

### Step 1: Create beads for discovered bugs

```bash
bd create --title="numpy bool_ not JSON serializable in ConfirmationResult" --type=bug --priority=0
bd close <id> --reason="Fixed: cast all ConfirmationResult fields to native Python types"

bd create --title="--resume-pipeline starts fresh screening instead of resuming" --type=bug --priority=2
```

### Step 2: Verify all tests pass

```bash
uv run pytest agent-evals/tests/ -x -q
```

---

## Task 9: End-to-end validation run

After all fixes are implemented, run a Taguchi screening to validate the improvements.

### Step 1: Dry run to verify trial count

```bash
uv run agent-evals --mode taguchi --limit 5 --repetitions 1 --dry-run \
  --model openrouter/arcee-ai/trinity-large-preview:free
```

Expected: ~55 tasks (5 per type x 11 types) instead of 5 total.

### Step 2: Full test run with judge-primary

```bash
uv run agent-evals --mode taguchi --pipeline auto \
  --model openrouter/arcee-ai/trinity-large-preview:free \
  --judge-enabled --judge-model openrouter/stepfun/step-3.5-flash:free \
  --judge-primary-types code_generation,compositional,agentic \
  --judge-sample-rate 5 \
  --limit 3 --repetitions 1 \
  --continue-on-error --store-traces --verbose
```

> **Rate-limit note:** With `--limit 3`, this produces ~33 tasks × 50 OA rows = 1650 trials. ~450 of those will be judge calls to the free model (all code_generation/compositional/agentic trials). Free models have rate limits — expect this to take a while. Use `--continue-on-error` to handle transient failures.

### Step 3: Validate results

Check observatory for these **quantitative pass criteria**:
- All 11 task types present (not just 2-5)
- code_generation score standard deviation > 0.1 (not all 1.0)
- Judge scores present for 100% of code_generation/compositional/agentic trials
- Judge scores present for ~20% of other types (sample_rate=5)
- ANOVA phase results stored (confirmation fix working)
- At least 2 factors with p < 0.10 (approaching significance)

```bash
uv run python -c "
import sqlite3, json
conn = sqlite3.connect('observatory.db')
cur = conn.cursor()
cur.execute('''SELECT task_type, COUNT(*), AVG(score),
    SUM(CASE WHEN judge_score IS NOT NULL THEN 1 ELSE 0 END)
    FROM trials WHERE run_id = (SELECT run_id FROM runs ORDER BY created_at DESC LIMIT 1)
    GROUP BY task_type ORDER BY task_type''')
for row in cur.fetchall():
    print(row)
"
```

---

## Known Accepted Risks

1. **code_generation heuristic scorer still inflated:** When judge calls fail (network errors, rate limits) or when running without `--judge-enabled`, `code_generation` tasks still use the heuristic scorer with overly generic test patterns that match nearly any response. The gold-standard YAML files should eventually be audited to tighten test patterns, but that is out of scope for this plan. The judge-primary routing (Task 3) is the primary mitigation.

2. **`efficiency` scorer is keyword-based with no fuzzy matching:** The `efficiency.py` scorer uses exact/alias match → keyword fraction → length penalty. It has no `rapidfuzz` import and no fuzzy matching band. This produces coarser scores than `fact_extraction` but has continuous keyword fractions (not step-functions), so it's lower priority. Consider adding fuzzy matching in a follow-up.

---

## Implementation Order

| Order | Task | Risk | Time Est |
|-------|------|------|----------|
| 1 | Task 1: Fix --limit | Very low | 15 min |
| 2 | Task 2: Reference-aware judge prompts | Low | 30 min |
| 3 | Task 3: Judge-primary score routing | Medium | 45 min |
| 4 | Task 4: multi_hop continuous scoring | Very low | 15 min |
| 5 | Task 5: fact_extraction/robustness interpolation | Low | 20 min |
| 6 | Task 6: conflicting 3-axis scoring | Low | 25 min |
| 7 | Task 7: compositional 3-axis scoring | Low | 25 min |
| 8 | Task 8: Beads and bug tracking | None | 5 min |
| 9 | Task 9: End-to-end validation run | None | ~30 min (run time) |
