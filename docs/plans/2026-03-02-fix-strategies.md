# Fix Strategies for Observatory & Agent-Evals Known Issues

**Date:** 2026-03-02
**Companion to:** `2026-03-02-observatory-known-issues.md`
**Research sources:** Context7 (rapidfuzz, FastAPI, Chart.js, TanStack Query, PyYAML, Pydantic), web research, codebase exploration

---

## A. Scoring System Fixes

### S1. Compositional scorer — replace substring with fuzzy matching (HIGH)

**Current code:** `agent-evals/src/agent_evals/tasks/compositional.py:68-96`

```python
# CURRENT (broken — 70% false zeros)
if expected_answer.lower() in response_lower:
    score += 1.0
```

**Recommended approach: rapidfuzz token_set_ratio**

Add `rapidfuzz` as a dependency. Use `fuzz.token_set_ratio()` which handles word reordering, extra words, and partial paraphrasing. This is the best general-purpose matcher because it treats one string as a subset of another.

```python
from rapidfuzz import fuzz, utils

def score_sub_answer(expected: str, response: str) -> float:
    """Score a single sub-answer against the full response."""
    # 1. Try exact containment first (fast path)
    if expected.lower() in response.lower():
        return 1.0

    # 2. Extract keywords from expected answer
    keywords = extract_keywords(expected)
    if not keywords:
        return 0.0

    # 3. Fuzzy keyword coverage
    matched = 0
    for kw in keywords:
        # Check if keyword appears fuzzy-matched in response
        score = fuzz.partial_ratio(
            kw.lower(), response.lower(),
            processor=utils.default_process,
            score_cutoff=80.0  # Require 80%+ similarity
        )
        if score > 0:
            matched += 1

    return matched / len(keywords)
```

**Why `token_set_ratio` over alternatives:**
- `fuzz.ratio()` — too sensitive to length differences (response is much longer than expected)
- `fuzz.partial_ratio()` — better for keyword-in-haystack matching (our use case)
- `fuzz.token_set_ratio()` — best when expected is a subset of the response
- `WRatio()` — auto-selects strategy, good general fallback

**Trade-offs:**
- Pro: Immediately fixes the 70% false-zero rate without requiring LLM calls
- Pro: rapidfuzz is C-optimized, ~100x faster than `difflib` (no measurable latency impact)
- Con: May produce some false positives on vague keywords — mitigate with score_cutoff
- Con: New dependency (~2MB wheel)

**Complexity:** LOW — single file change + dependency addition

---

### S2. Negative scorer — graduate to rubric scoring (MEDIUM)

**Current code:** `agent-evals/src/agent_evals/tasks/negative.py:118-135`

```python
# CURRENT (binary only)
if any(phrase in response_lower for phrase in _ABSTENTION_PHRASES):
    return 1.0
return 0.0
```

**Recommended approach: Graduated rubric with phrase categorization**

Categorize the ~35 existing abstention phrases into tiers, then assign partial scores based on the strongest signal found.

```python
# Categorized phrase tiers
_FIRM_REFUSAL = [
    "i cannot", "i'm unable to", "no information", "does not contain",
    "not mentioned", "not provided", "i don't have",
]
_HEDGE_WITH_CAVEAT = [
    "i'm not certain", "i cannot confirm", "it's unclear",
    "the documentation doesn't explicitly",
]
_ANSWER_WITH_DISCLAIMER = [
    "based on limited information", "this may not be accurate",
    "i'm making an assumption",
]

def score_response(self, response: str) -> float:
    response_lower = response.lower()

    # Check tiers in order of strength
    if any(p in response_lower for p in _FIRM_REFUSAL):
        return 1.0
    if any(p in response_lower for p in _HEDGE_WITH_CAVEAT):
        return 0.7
    if any(p in response_lower for p in _ANSWER_WITH_DISCLAIMER):
        return 0.3

    # No abstention signal — confident hallucination
    return 0.0
```

**Alternative: LLM-as-judge secondary scorer**

The judge infrastructure (`judge/calibrator.py`) already has a rubric for `negative` tasks. Use it as a fallback when the heuristic returns 0.0:

```python
def score_response(self, response: str) -> float:
    heuristic = self._heuristic_score(response)
    if heuristic > 0.0:
        return heuristic
    # Heuristic says hallucination — but verify with LLM judge
    # (only for ambiguous cases, not all trials)
    return self._judge_score(response)  # Uses calibrator.py
```

**Trade-offs:**
- Rubric approach: free, deterministic, testable — but still phrase-list-dependent
- LLM-judge approach: better accuracy — but adds cost (~$0.001/trial) and latency (~2s)
- Hybrid: best of both — use rubric first, LLM only for edge cases

**Complexity:** LOW (rubric) / MEDIUM (LLM fallback integration)

---

### S3. Disambiguation scorer — replace cliff threshold with continuous scoring (MEDIUM)

**Current code:** `agent-evals/src/agent_evals/tasks/disambiguation.py:55-105`

**Recommended approach: Continuous keyword coverage fraction**

```python
def score_response(self, response: str) -> float:
    response_lower = response.lower()
    keywords = extract_keywords(self.expected_answer)
    if not keywords:
        return 0.0

    matched = sum(1 for kw in keywords if kw.lower() in response_lower)
    coverage = matched / len(keywords)

    # Check for explicit ambiguity acknowledgment (bonus)
    ambiguity_bonus = 0.0
    ambiguity_phrases = ["ambiguous", "multiple interpretations", "could mean"]
    if any(p in response_lower for p in ambiguity_phrases):
        ambiguity_bonus = 0.1

    return min(1.0, coverage + ambiguity_bonus)
```

**Trade-offs:**
- Pro: Eliminates the 0.0→1.0 cliff at 50% threshold
- Pro: Produces a continuous distribution for better variant discrimination
- Con: Very short expected answers may produce coarse fractions

**Complexity:** LOW — single file change

---

### S4. Multi-hop scorer — require minimum keyword coverage per step (MEDIUM)

**Current code:** `agent-evals/src/agent_evals/tasks/multi_hop.py`

The current scorer checks if ANY single keyword from each reasoning step appears in the response. With verbose LLM output, common technical terms trivially match.

**Recommended approach: Minimum coverage threshold per step**

```python
STEP_COVERAGE_THRESHOLD = 0.30  # Require >=30% of step keywords

def score_response(self, response: str) -> float:
    response_lower = response.lower()
    step_scores = []

    for step in self.reasoning_chain:
        keywords = extract_keywords(step["expected"])
        if not keywords:
            step_scores.append(1.0)
            continue

        matched = sum(1 for kw in keywords if kw.lower() in response_lower)
        coverage = matched / len(keywords)

        # Step passes if coverage >= threshold
        step_scores.append(coverage if coverage >= STEP_COVERAGE_THRESHOLD else 0.0)

    return sum(step_scores) / len(step_scores) if step_scores else 0.0
```

**Alternative: Weighted keyword importance**

Weight keywords by inverse document frequency (rarer words are more discriminating):

```python
# Pre-compute keyword frequencies across all responses in the run
keyword_idf = compute_keyword_idf(all_responses)
weighted_coverage = sum(keyword_idf[kw] for kw in matched_kws) / sum(keyword_idf[kw] for kw in all_kws)
```

**Trade-offs:**
- Coverage threshold: simple, deterministic — may still be too lenient with 30%
- IDF weighting: better discrimination — requires corpus-level computation (more complex)

**Complexity:** LOW (threshold) / MEDIUM (IDF weighting)

---

### S5. Fact extraction scorer — add fuzzy/token-overlap matching (LOW)

**Current code:** `agent-evals/src/agent_evals/tasks/fact_extraction.py:54-87`

**Recommended approach: Layered matching with rapidfuzz**

```python
from rapidfuzz import fuzz, utils

def score_response(self, response: str) -> float:
    response_lower = response.lower()
    expected = self.expected_answer.lower()

    # Layer 1: Exact containment (current fast path)
    if expected in response_lower:
        return 1.0

    # Layer 2: Alias matching (current)
    for alias in self.aliases:
        if alias.lower() in response_lower:
            return 1.0

    # Layer 3: Fuzzy matching (NEW)
    fuzzy_score = fuzz.token_set_ratio(
        expected, response_lower,
        processor=utils.default_process
    )
    if fuzzy_score >= 85.0:
        return 0.9  # High confidence fuzzy match
    if fuzzy_score >= 70.0:
        return 0.7  # Moderate confidence

    # Layer 4: Keyword coverage fallback (current)
    keywords = extract_keywords(self.expected_answer)
    if not keywords:
        return 0.0
    matched = sum(1 for kw in keywords if kw.lower() in response_lower)
    return matched / len(keywords)
```

**Trade-offs:**
- Pro: Fills the gap between exact match (1.0) and keyword fallback (noisy 0.x)
- Pro: Catches paraphrases like "Python 3.11" vs "Python version 3.11"
- Con: Fuzzy threshold tuning needed — 85% and 70% are starting points

**Complexity:** LOW — builds on S1's rapidfuzz dependency

---

### S6. LLM-as-judge infrastructure — activate as secondary scorer (LOW)

**Existing code:** `agent-evals/src/agent_evals/judge/calibrator.py`, `judge/poll.py`

The judge module has complete rubrics for all 11 task types and a PoLL panel mechanism. None of this runs during trial scoring.

**Recommended approach: Phased activation**

**Phase 1 — Validation sample (no cost at scale):**

```python
# In runner.py, after scoring:
if trial_index % 50 == 0:  # Sample 2% of trials
    judge_score = calibrator.score(task_type, question, response, rubric)
    trial.metrics["judge_score"] = judge_score.score
    trial.metrics["judge_rationale"] = judge_score.rationale
```

This populates `TrialResult.metrics` (fixes E6) and provides data to measure heuristic accuracy.

**Phase 2 — Fallback on zero (cost: ~$0.001/zero-score trial):**

```python
heuristic_score = task.score_response(response)
if heuristic_score == 0.0 and not is_empty_response(response):
    judge_result = calibrator.score(task_type, question, response, rubric)
    final_score = judge_result.score
else:
    final_score = heuristic_score
```

**Phase 3 — PoLL panel for contested scores:**

Use the 3-model panel (GPT-5-mini, Claude Haiku 4.5, Gemini 2.5 Flash) for scores that differ significantly between heuristic and single-judge.

**Trade-offs:**
- Phase 1: Zero additional cost, provides calibration data
- Phase 2: ~$0.50/run additional cost (only for zero-score non-empty responses)
- Phase 3: ~$1.50/run for panel evaluation on contested scores
- All phases: Adds latency for judged trials (~2-5s per LLM call)

**Complexity:** MEDIUM — requires wiring judge into runner, adding config flags

---

### S7. Compositional denominator inflated by empty-answer sub-tasks (MEDIUM)

**Current code:** `agent-evals/src/agent_evals/tasks/compositional.py:85-95`

```python
# CURRENT (buggy denominator)
matched = 0
for sub_task in self.sub_tasks:
    expected: str = sub_task.get("expected_answer", "")
    if not expected:
        continue                          # Skipped — but still counted below
    if expected.lower() in response_lower:
        matched += 1

score = matched / len(self.sub_tasks)     # BUG: includes empty sub-tasks
```

If 5 sub-tasks exist but 1 has an empty answer, the maximum possible score is 4/5 = 0.80, never 1.0. This compounds S1's false-zero problem.

**Recommended approach: Track scored count separately**

```python
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
    return 1.0  # No scorable sub-tasks — vacuously correct

score = matched / scored_count
return max(0.0, min(1.0, score))
```

**Trade-offs:**
- Pro: Correct denominator — perfect responses can actually score 1.0
- Pro: Trivial change, no new dependencies
- Con: None — this is a clear bug fix

**Complexity:** TRIVIAL — 3-line change (add `scored_count`, use it in division)

---

### S8. Negative scorer false-positive abstention phrases (MEDIUM)

**Current code:** `agent-evals/src/agent_evals/tasks/negative.py:64-65`

```python
# In _ABSTENTION_PHRASES tuple:
"based on the available",       # Line 64 — overly broad
"the provided documentation",   # Line 65 — overly broad
```

A response like "Based on the available documentation, the answer is Python 3.11" matches line 64 and scores 1.0 (correct abstention), even though the model is confidently answering. This inflates the 64.8% abstention detection rate.

**Recommended approach: Remove broad phrases + add co-occurrence requirement**

```python
# Option A: Simply remove the two problematic phrases
# Remove "based on the available" and "the provided documentation"
# from _ABSTENTION_PHRASES. This is the safest immediate fix.

# Option B: Require co-occurrence with an uncertainty marker
_UNCERTAINTY_MARKERS = frozenset({
    "cannot", "can't", "unable", "not sure", "unclear",
    "no information", "doesn't", "does not", "not found",
    "not mentioned", "not specified",
})

_CONTEXTUAL_PHRASES = (
    "based on the available",
    "the provided documentation",
    "from the documentation",
    "according to the docs",
)

def _detect_abstention(response_lower: str) -> bool:
    # Strong phrases: standalone triggers
    if any(p in response_lower for p in _STRONG_ABSTENTION_PHRASES):
        return True

    # Contextual phrases: only trigger with a co-occurring uncertainty marker
    if any(p in response_lower for p in _CONTEXTUAL_PHRASES):
        return any(m in response_lower for m in _UNCERTAINTY_MARKERS)

    return False
```

**Trade-offs:**
- Option A (remove): simplest, may miss some genuine soft abstentions
- Option B (co-occurrence): more nuanced, catches "based on the available info, I cannot determine..." while passing "based on the available code, the answer is X"
- Both options: should be paired with the S2 graduated rubric for best results

**Complexity:** LOW — phrase list modification (Option A: trivial; Option B: low)

---

### S9. Code generation scorer gives 0.0 match_rate for empty test patterns (LOW)

**Current code:** `agent-evals/src/agent_evals/tasks/code_generation.py:115-137`

```python
# CURRENT
if patterns:
    matched = sum(1 for pat in patterns if _match_pattern(pat, response))
    match_rate = matched / len(patterns)
else:
    match_rate = 0.0  # BUG: no patterns → 0.0 → max score capped at 0.3

score = match_rate * 0.7 + (1.0 - violation_rate) * 0.2 + syntax_bonus * 0.1
```

When `test` is empty, `match_rate = 0.0`, and the maximum possible score is `0.0 * 0.7 + 1.0 * 0.2 + 1.0 * 0.1 = 0.3` regardless of response quality.

**Recommended approach: Redistribute weights when a component is inapplicable**

```python
# Option A: Default match_rate to 1.0 when no patterns (vacuous truth)
if patterns:
    matched = sum(1 for pat in patterns if _match_pattern(pat, response))
    match_rate = matched / len(patterns)
else:
    match_rate = 1.0  # No test patterns → nothing to fail

# Option B: Dynamic weight redistribution
has_tests = bool(patterns)
has_forbidden = bool(self.forbidden_patterns)

if has_tests and has_forbidden:
    score = match_rate * 0.7 + (1 - violation_rate) * 0.2 + syntax_bonus * 0.1
elif has_tests:  # No forbidden patterns
    score = match_rate * 0.8 + syntax_bonus * 0.2
elif has_forbidden:  # No test patterns
    score = (1 - violation_rate) * 0.8 + syntax_bonus * 0.2
else:  # Neither — syntax only
    score = syntax_bonus
```

**Trade-offs:**
- Option A: simplest — "no test = nothing to fail" is logically sound
- Option B: more principled — each component gets proportional weight based on what's available
- Both: also fix docstring to reflect actual 0.7/0.2/0.1 weights (currently documents 0.8/0.2)

**Complexity:** TRIVIAL (Option A) / LOW (Option B)

---

### S10. Agentic `_parse_json_or_list` fallback for non-JSON strings (LOW)

**Current code:** `agent-evals/src/agent_evals/tasks/agentic.py:44-53`

```python
# CURRENT
if isinstance(value, str) and value.strip():
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        return [str(parsed)]
    except json.JSONDecodeError:
        return []  # BUG: silently drops non-JSON strings
return []
```

**Note:** The `json.JSONDecodeError` IS caught (contrary to the issue description), but it returns `[]` instead of falling back to whitespace splitting. A string like `"test_foo test_bar"` (space-separated test names, common in SWE-bench format) returns empty rather than `["test_foo", "test_bar"]`.

**Recommended approach: Fall back to whitespace splitting on parse failure**

```python
if isinstance(value, str) and value.strip():
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
        return [str(parsed)]
    except json.JSONDecodeError:
        # Fall back to whitespace splitting for space/newline-separated values
        return [token for token in value.strip().split() if token]
return []
```

**Trade-offs:**
- Pro: Handles SWE-bench-style space-separated test names
- Pro: No behavior change for valid JSON or empty strings
- Con: Could produce unexpected results if value contains prose with spaces — but task metadata is typically structured, not prose

**Complexity:** TRIVIAL — one-line change in except block

---

### S11. Agentic scorer zero-base for missing metadata components (LOW)

**Current code:** `agent-evals/src/agent_evals/tasks/agentic.py:129-197`

```python
# CURRENT — fixed weights regardless of data availability
composite = (
    file_mention_score * 0.4    # Returns 0.0 if self.files is empty
    + content_score * 0.4       # Returns 0.0 if self.files is empty
    + correctness_score * 0.2   # Returns 0.0 if self.fail_to_pass is empty
)
```

When `files` is empty, both `file_mention_score` and `content_score` return 0.0 (lines 145-146, 168-169), capping the max score at 0.2. When `fail_to_pass` is also empty, the max is 0.0 regardless of output quality.

**Recommended approach: Dynamic weight redistribution**

```python
def score_response(self, response: str) -> float:
    components: list[tuple[float, float]] = []  # (score, base_weight)

    if self.files:
        components.append((self._score_file_mentions(response), 0.4))
        components.append((self._score_content(response), 0.4))

    if self.fail_to_pass:
        components.append((self._score_correctness(response), 0.2))

    # Always include tool detection if expected_tools is populated
    if self.expected_tools:
        components.append((self._score_tools(response), 0.2))

    if not components:
        # No metadata to score against — generous default
        return 0.5

    # Normalize weights to sum to 1.0
    total_weight = sum(w for _, w in components)
    composite = sum(score * (weight / total_weight) for score, weight in components)
    return max(0.0, min(1.0, composite))
```

**Alternative: Simpler "vacuous truth" approach**

Instead of restructuring the scoring, return 1.0 (or a neutral sentinel) from sub-scorers when they have no data:

```python
def _score_file_mentions(self, response: str) -> float:
    if not self.files:
        return 1.0  # Vacuously satisfied — no files expected
    # ... existing logic

def _score_content(self, response: str) -> float:
    if not self.files:
        return 1.0  # Vacuously satisfied
    # ... existing logic

def _score_correctness(self, response: str) -> float:
    if not self.fail_to_pass:
        return 1.0  # Vacuously satisfied
    # ... existing logic
```

**Trade-offs:**
- Dynamic redistribution: more principled, only scores on what's measurable
- Vacuous truth: simpler change, preserves fixed weight structure — but inflates scores when no data exists
- Both: significantly improve the current agentic mean of 0.389

**Complexity:** LOW (vacuous truth) / MEDIUM (dynamic redistribution)

---

## B. Infrastructure & Runtime Fixes

### I1 & I2. Stalled/stuck runs — manual cleanup (IMMEDIATE)

**Fix approach:** Use existing API endpoints.

```bash
# Mark stalled run as failed
curl -X POST http://localhost:8765/api/runs/9b51360baeb5/finish \
  -H "Content-Type: application/json" \
  -d '{"status": "failed"}'

# Same for 4-day-old stuck run
curl -X POST http://localhost:8765/api/runs/b1ca3c026030/finish \
  -H "Content-Type: application/json" \
  -d '{"status": "failed"}'
```

**Complexity:** TRIVIAL — one-time API calls

---

### I3. Stale-run detection — heartbeat mechanism (MEDIUM)

**Current state:** No heartbeat, no watchdog. Both I1 and I2 are symptoms.

**Recommended approach: Runner heartbeat + server-side reaper**

**Runner side (in `orchestrator.py`):**

```python
import threading

class HeartbeatThread(threading.Thread):
    """Periodically update run heartbeat in store."""

    def __init__(self, store, run_id, interval=30):
        super().__init__(daemon=True)
        self._store = store
        self._run_id = run_id
        self._interval = interval
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.wait(self._interval):
            self._store.update_heartbeat(self._run_id)

    def stop(self):
        self._stop_event.set()
```

**Store side (in `store.py`):**

```python
def update_heartbeat(self, run_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with self._lock, self._connect() as conn:
        conn.execute(
            "UPDATE runs SET heartbeat_at = ? WHERE run_id = ?",
            (now, run_id),
        )

def reap_stale_runs(self, max_age_seconds: int = 300) -> list[str]:
    """Mark runs as failed if heartbeat is older than max_age_seconds."""
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)).isoformat()
    with self._lock, self._connect() as conn:
        stale = conn.execute(
            "SELECT run_id FROM runs WHERE status = 'active' AND heartbeat_at < ?",
            (cutoff,),
        ).fetchall()
        for (run_id,) in stale:
            conn.execute(
                "UPDATE runs SET status = 'failed', finished_at = ? WHERE run_id = ?",
                (datetime.now(timezone.utc).isoformat(), run_id),
            )
    return [r[0] for r in stale]
```

**Server side — periodic reaper (in `routes.py` lifespan):**

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start reaper task
    async def reaper():
        while True:
            await asyncio.sleep(60)  # Check every minute
            reaped = store.reap_stale_runs(max_age_seconds=300)
            if reaped:
                logger.info("Reaped stale runs: %s", reaped)

    task = asyncio.create_task(reaper())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)
```

**Schema migration:**
```sql
ALTER TABLE runs ADD COLUMN heartbeat_at TEXT;
```

**Trade-offs:**
- Pro: Automatically handles all future stale runs
- Pro: 30s heartbeat interval + 5min threshold = reasonable detection speed
- Con: Requires schema migration (ADD COLUMN is safe in SQLite)
- Con: Heartbeat thread adds minimal overhead per run

**Complexity:** MEDIUM — touches store, orchestrator, routes, schema

---

### I4. API returns hardcoded `config: {}` despite DB having config (MEDIUM)

**Updated finding:** Config IS stored in the DB correctly. The issue is that `_enrich_run()` in `routes.py:188` hardcodes `"config": {}`, and `RunSummary` in `store.py` does not include a `config` field.

**Recommended approach: Expose stored config through the API**

```python
# In orchestrator.py, when creating run:
config_dict = {
    "mode": config.mode,
    "model": config.model,
    "repetitions": config.repetitions,
    "task_limit": config.task_limit,
    "temperature": config.temperature,
    "max_tokens": config.max_tokens,
    "continue_on_error": config.continue_on_error,
}
self.store.create_run(run_id, run_type, json.dumps(config_dict), phase, pipeline_id)
```

Or if `OrchestratorConfig` is a Pydantic model:

```python
config_json = config.model_dump_json()
self.store.create_run(run_id, run_type, config_json, phase, pipeline_id)
```

**Complexity:** LOW — single-line fix in orchestrator

---

### I5. Failed run with null `finished_at` (LOW)

**Recommended approach:** Set `finished_at` in all terminal state transitions.

```python
# In store.py finish_run():
def finish_run(self, run_id: str, status: str = "completed") -> None:
    now = datetime.now(timezone.utc).isoformat()
    with self._lock, self._connect() as conn:
        conn.execute(
            "UPDATE runs SET status = ?, finished_at = ? WHERE run_id = ?",
            (status, now, run_id),
        )
```

Ensure this is called in all error paths (try/except/finally in orchestrator).

**Complexity:** TRIVIAL

---

### I6. No model name validation on run submission (LOW)

**Recommended approach: Validate model format at submission**

```python
# In routes.py or run_manager.py:
import re

MODEL_PATTERN = re.compile(r"^[\w.-]+/[\w./-]+$")  # provider/model format

def validate_model_name(model: str) -> None:
    """Validate model string follows LiteLLM provider/model format."""
    for m in model.split(","):
        m = m.strip()
        if not MODEL_PATTERN.match(m):
            raise ValueError(
                f"Invalid model name '{m}'. "
                f"Expected format: 'provider/model' (e.g., 'openrouter/anthropic/claude-sonnet-4.5')"
            )
```

Or validate against the model catalog:

```python
known_models = catalog.get_active_models()
known_ids = {m["id"] for m in known_models}
if model not in known_ids:
    raise ValueError(f"Unknown model: {model}")
```

**Trade-offs:**
- Regex validation: fast, catches obvious errors like "test"
- Catalog validation: more thorough but requires sync'd catalog

**Complexity:** LOW

---

### I7. No persistent logging (LOW)

**Recommended approach: RotatingFileHandler + structured JSON**

```python
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import json

def setup_logging(log_dir: Path, level: str = "INFO") -> None:
    """Configure file + console logging for Observatory."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "observatory.log"

    # JSON formatter for structured logging
    class JSONFormatter(logging.Formatter):
        def format(self, record):
            return json.dumps({
                "timestamp": self.formatTime(record),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "line": record.lineno,
            })

    # File handler with rotation (10MB, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
    )
    file_handler.setFormatter(JSONFormatter())

    # Configure root logger
    root = logging.getLogger("agent_evals")
    root.setLevel(getattr(logging, level.upper()))
    root.addHandler(file_handler)
```

**Best practices applied:**
- `RotatingFileHandler` prevents disk exhaustion (10MB x 5 = 50MB max)
- JSON format enables log aggregation and search
- Module-level loggers (`logging.getLogger(__name__)`) already in use
- Default location: `~/.observatory/observatory.log`

**Trade-offs:**
- Pro: Zero runtime cost (logging is buffered)
- Pro: JSON format works with any log viewer
- Con: File logging less useful in containers (prefer stdout there)

**Complexity:** LOW — new utility function + call from server startup

---

### I8. Stale model catalog (LOW)

**Recommended approach: Auto-sync on server startup**

```python
# In routes.py lifespan:
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Sync model catalog on startup
    try:
        await sync_model_catalog(catalog)
        logger.info("Model catalog synced on startup")
    except Exception as e:
        logger.warning("Model catalog sync failed: %s", e)

    yield
```

**Complexity:** TRIVIAL — one line in lifespan

---

## C. Evaluation Framework Fixes

### E1. `fnmatch.fnmatch` glob inconsistency on Linux (MEDIUM)

**Current state:** `*` matches `/` on Linux with fnmatch, inconsistent with `**` regex branch.

**Recommended approach: Use `pathlib.PurePosixPath.match()` or `glob.translate()`**

Python 3.13+ added `glob.translate()` which correctly handles path separators:

```python
import re
from pathlib import PurePosixPath

def _simple_glob_match(pattern: str, path: str) -> bool:
    """Cross-platform glob matching where * does not cross /."""
    # Use PurePosixPath.match for consistent behavior
    return PurePosixPath(path).match(pattern)
```

For Python < 3.13, implement manually:

```python
def _simple_glob_match(pattern: str, path: str) -> bool:
    """Match glob pattern against path, * does not cross directories."""
    # Split both into segments
    pat_parts = PurePosixPath(pattern).parts
    path_parts = PurePosixPath(path).parts

    if len(pat_parts) != len(path_parts):
        return False

    import fnmatch
    return all(
        fnmatch.fnmatch(p, pat) for p, pat in zip(path_parts, pat_parts)
    )
```

**Known CPython issue:** [python/cpython#118701](https://github.com/python/cpython/issues/118701) documents this inconsistency.

**Trade-offs:**
- `PurePosixPath.match()`: cleaner API but changed behavior in Python 3.12+ (now matches full path)
- Per-segment fnmatch: explicit, works consistently across Python versions
- `wcmatch` library: comprehensive glob matching — but adds a dependency

**Complexity:** LOW — single function replacement

---

### E2. Absolute path matching in validate.py and autodetect.py (MEDIUM)

**Recommended approach: Use relative paths from project root**

```python
# CURRENT (buggy)
if any(part in item.parts for part in IGNORE_DIRS):
    continue

# FIXED — use relative path from project root
try:
    rel = item.relative_to(project_root)
except ValueError:
    continue  # Outside project root

if any(part in rel.parts for part in IGNORE_DIRS):
    continue
```

**Complexity:** LOW — pass `project_root` to affected functions

---

### E3. YAML variant generates invalid YAML with colons (MEDIUM)

**Recommended approach: Use `yaml.safe_dump()` instead of manual formatting**

PyYAML's `safe_dump()` automatically quotes strings containing colons:

```python
import yaml

# CURRENT (broken)
output = f"  summary: {summary}"  # Breaks if summary contains ":"

# FIXED — let PyYAML handle quoting
data = {"summary": summary}
output = yaml.safe_dump(data, default_flow_style=False)
# Produces: summary: 'This is a summary: with a colon'
```

If building YAML manually is necessary, quote strings that contain special characters:

```python
def yaml_safe_string(value: str) -> str:
    """Quote string for YAML if it contains special characters."""
    special_chars = ":{}\[]|>*&!%#@`"
    if any(c in value for c in special_chars) or value.startswith(("'", '"')):
        # Use single quotes; escape embedded single quotes
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    return value
```

**Complexity:** LOW — use yaml.safe_dump for the variant output

---

### E4. Pipe-delimited and markdown table variants break with `|` (MEDIUM)

**Recommended approach: Escape pipe characters in content**

```python
def escape_pipe(text: str) -> str:
    """Escape pipe characters for table cell content."""
    return text.replace("|", "\\|")

# In markdown table variant:
row = f"| {escape_pipe(col1)} | {escape_pipe(col2)} | {escape_pipe(col3)} |"

# In pipe-delimited variant:
row = "|".join(escape_pipe(cell) for cell in cells)
```

**Complexity:** TRIVIAL

---

### E5. `variant.teardown()` not called on trial exception (LOW)

**Current state:** In `runner.py`, when `continue_on_error=False` and a trial raises, `variant.teardown()` is skipped.

**Note:** The Taguchi runner already has this correct:
```python
# taguchi/runner.py — correct pattern
finally:
    composite.teardown()
```

**Recommended approach:** The `EvalRunner.run()` method already has a try/finally around the ThreadPoolExecutor:

```python
try:
    with ThreadPoolExecutor(...) as executor:
        # ... trial execution
finally:
    for variant in variants:
        variant.teardown()
```

**Verify this is still correct after recent changes.** If the teardown is outside the finally block, move it in:

```python
try:
    for variant in variants:
        variant.setup(doc_tree)

    with ThreadPoolExecutor(...) as executor:
        # ... execute trials
finally:
    for variant in variants:
        try:
            variant.teardown()
        except Exception:
            logger.warning("Teardown failed for %s", variant.name, exc_info=True)
```

**Complexity:** TRIVIAL — verify/add finally block

---

### E6. `TrialResult.metrics` always empty (LOW)

**Recommended approach: Wire metrics into runner trial path**

Populate metrics during `_run_trial()`:

```python
# In runner.py _run_trial():
metrics = {
    "prompt_build_ms": prompt_build_time * 1000,
    "scoring_ms": scoring_time * 1000,
    "keywords_matched": matched_count,  # From scorer
    "keywords_total": total_keywords,
}

# If judge validation is active (from S6):
if judge_score is not None:
    metrics["judge_score"] = judge_score.score

return TrialResult(..., metrics=metrics)
```

**Complexity:** LOW — add timing calls and keyword tracking in scorer return values

---

### E7. `bootstrap_ci` does not handle NaN data (LOW)

**Recommended approach: Filter NaN before computation**

```python
import numpy as np

def bootstrap_ci(data, confidence=0.95, n_resamples=9999):
    """Compute BCa bootstrap confidence interval, filtering NaN."""
    clean = [x for x in data if not (isinstance(x, float) and np.isnan(x))]

    if len(clean) < 2:
        return BootstrapResult(low=float("nan"), high=float("nan"), n_valid=len(clean))

    result = scipy.stats.bootstrap(
        (clean,), np.mean, confidence_level=confidence, n_resamples=n_resamples
    )
    return BootstrapResult(
        low=result.confidence_interval.low,
        high=result.confidence_interval.high,
        n_valid=len(clean),
    )
```

**Complexity:** TRIVIAL

---

### E8. Robustness tasks missing `base_task_id` metadata (LOW)

**Recommended approach: Batch metadata update**

```python
# Script to add base_task_id to all 30 robustness tasks
for task in robustness_tasks:
    # Parse the task_id to extract the base task reference
    # e.g., "robustness_001_noise" -> base is "retrieval_001"
    base_id = task.metadata.get("derived_from") or infer_base_task_id(task.task_id)
    task.metadata["base_task_id"] = base_id
```

The mapping likely exists in the task definition files or can be inferred from naming conventions.

**Complexity:** LOW — data update, no logic changes

---

## D. Data Quality Fixes

### D1 & D2. Bimodal scores / compositional underscoring (HIGH)

**Fix:** Addressed by S1-S5 scorer improvements. After fixing the scorers, re-run the evaluation to get accurate statistics. The current 0.62 mean score is unreliable.

**Validation plan:**
1. Fix S1 (compositional), re-run subset of 100 compositional trials
2. Compare score distribution — expect mean to rise from 0.114 to ~0.5-0.7
3. If distribution is still bimodal, investigate whether the model genuinely struggles

**Complexity:** N/A — dependent on scorer fixes

---

### D3. SSE stream emits duplicate events on reconnect (LOW)

**Recommended approach: Add event sequence number**

```python
# In routes.py SSE generator:
_seq_counter = itertools.count(1)

async def _generator():
    yield {
        "event": "connected",
        "id": str(next(_seq_counter)),  # SSE `id` field
        "data": json.dumps({"run_id": run_id}),
    }
    while True:
        event = await queue.get()
        yield {
            "event": event["event_type"],
            "id": str(next(_seq_counter)),  # Monotonic sequence
            "data": json.dumps(event["data"]),
        }
```

**Frontend deduplication (in `useSSE.ts`):**

```typescript
const lastEventIdRef = useRef(0);

source.addEventListener("trial_completed", (e: MessageEvent) => {
  const eventId = parseInt(e.lastEventId, 10);
  if (eventId <= lastEventIdRef.current) return; // Skip duplicate
  lastEventIdRef.current = eventId;
  // ... process event
});
```

The SSE spec's `id` field + `Last-Event-ID` header provide built-in deduplication when clients reconnect.

**Complexity:** LOW

---

### D4. Perfect-score latency — manual review needed (LOW)

**Fix:** No code change required. Sample 20 perfect-score trials across task types and review manually. If template/gaming patterns are found, add a response diversity check to the scorer.

**Complexity:** N/A — manual audit

---

### D5. Pipeline view shows nothing (LOW)

**Recommended approach: Investigate pipeline record creation**

```sql
-- Check if pipeline record exists
SELECT * FROM pipelines WHERE pipeline_id = '83973e5dca97';

-- If missing, the pipeline wasn't registered when the run started
-- Fix: Ensure orchestrator creates pipeline record before creating runs
```

The fix likely requires ensuring `create_pipeline()` is called before `create_run()` with a `pipeline_id`.

**Complexity:** LOW — likely a missing method call

---

## E. UX Polish Fixes

### U1. Chart entry animations (LOW)

**From Chart.js docs (Context7):**

```javascript
// Add to all chart option objects
const chartOptions = {
  animation: {
    duration: 800,
    easing: 'easeOutQuart',
  },
  // For datasets appearing one at a time:
  transitions: {
    active: {
      animation: {
        duration: 200,
      },
    },
  },
  // ... existing options
};
```

**Files to update:**
- `Observatory.tsx`
- `LiveMonitor.tsx`
- `ResultsExplorer.tsx`
- `History.tsx`
- `FactorAnalysis.tsx`

**Pattern: Extract shared defaults**

```typescript
// chartDefaults.ts
export const CHART_ANIMATION = {
  duration: 800,
  easing: 'easeOutQuart' as const,
};

// Usage in each page:
const options = {
  animation: CHART_ANIMATION,
  // ... page-specific options
};
```

**Complexity:** TRIVIAL — shared constant + apply to 5 files

---

### U2. CompassCheckbox inline CSS cleanup (LOW)

**File:** `CompassCheckbox.tsx:59-78`

Move remaining inline SVG styles to the component's CSS module or Tailwind classes.

**Complexity:** TRIVIAL

---

### U3. SlideOutPanel close button focus style (LOW)

**From Radix UI accessibility docs:**

```tsx
// SlideOutPanel.tsx:45
<button
  onClick={onClose}
  className="... focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
>
```

Using `outline-offset: 2px` ensures the focus ring doesn't overlap the button content.

**Complexity:** TRIVIAL — single className addition

---

## F. Cross-Cutting Concerns

### React Query tuning (already fixed in hooks.ts)

**From TanStack Query v5 docs (Context7):**

The tiered staleTime approach already applied is correct:
- Frequently changing data (runs, trials): `staleTime: 5_000`
- Semi-static data (models, groups): `staleTime: 30_000`
- Static data (task types): `staleTime: 60_000`

**gcTime best practice:** Should be >= staleTime. The applied 5-minute gcTime is reasonable. For persistence, can go up to 24 hours: `gcTime: 1000 * 60 * 60 * 24`.

### Pydantic v2 validation for API responses

**From Pydantic docs (Context7):**

Use `TypeAdapter` for validating API response shapes without requiring BaseModel subclasses:

```python
from pydantic import TypeAdapter

RunSummaryAdapter = TypeAdapter(list[RunSummary])

# In API client:
data = response.json()
validated = RunSummaryAdapter.validate_python(data)
```

This is useful for the frontend's API client (`client.ts`) — but since it's TypeScript, use Zod or io-ts instead of Pydantic. Pydantic validation is more relevant for the Python backend's internal data flow.

### FastAPI pagination (already fixed in routes.py)

The applied `limit`/`offset` pagination is correct for the current scale. For larger datasets, consider cursor-based pagination:

```python
# Cursor-based (future improvement)
@router.get("/api/runs")
async def list_runs(after: str | None = None, limit: int = 50):
    runs = store.get_runs(after_id=after, limit=limit + 1)
    has_next = len(runs) > limit
    return {"data": runs[:limit], "next_cursor": runs[-1]["run_id"] if has_next else None}
```

---

## Priority Matrix

| Issue | Priority | Complexity | Impact on Data Quality |
|-------|----------|-----------|----------------------|
| S1 (compositional scorer) | HIGH | LOW | Fixes 70% false zeros |
| S7 (compositional denominator) | MEDIUM | TRIVIAL | Fixes impossible-to-reach 1.0 scores |
| S8 (negative false positives) | MEDIUM | LOW | Reduces inflated abstention rate |
| S4 (multi-hop ceiling) | MEDIUM | LOW | Restores variant discrimination |
| S3 (disambiguation cliff) | MEDIUM | LOW | Continuous scoring distribution |
| S2 (negative rubric) | MEDIUM | LOW | Partial credit for hedging |
| I3 (heartbeat/reaper) | MEDIUM | MEDIUM | Prevents future stale runs |
| I4 (config persistence) | MEDIUM | LOW | Run reproducibility |
| S5 (fact extraction fuzzy) | LOW | LOW | Better paraphrase handling |
| S6 (judge activation) | LOW | MEDIUM | Validation/calibration data |
| S9 (code gen empty test) | LOW | TRIVIAL | Correct weight distribution |
| S10 (agentic JSON parse) | LOW | TRIVIAL | Handles non-JSON metadata |
| S11 (agentic zero-base) | LOW | LOW | Correct agentic scoring |
| E3 (YAML colons) | MEDIUM | LOW | Correct variant output |
| E4 (pipe escaping) | MEDIUM | TRIVIAL | Correct variant output |
| All UX (U1-U3) | LOW | TRIVIAL | Visual polish |
| I7 (logging) | LOW | LOW | Debugging capability |

**Recommended sprint order:**
1. S1 + S7 + rapidfuzz dependency (biggest data quality impact — fix together since both in compositional.py)
2. S2 + S8 scorer improvements (fix together since both in negative.py)
3. S3-S5, S9-S11 scorer improvements (complete scorer overhaul)
4. I3 + I4 + I5 (infrastructure stability)
5. E3 + E4 + E5 (framework correctness)
6. S6 (judge integration — needs scorer fixes first for calibration)
7. Everything else (polish)
