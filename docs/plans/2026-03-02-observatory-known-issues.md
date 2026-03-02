# Observatory & Agent-Evals — Known Issues Register

**Date:** 2026-03-02
**Sources:** E2E test report (2026-02-28), scoring audit, systems audit, data audit, code analysis, project memory
**Run under review:** `9b51360baeb5` (Taguchi screening, `arcee-ai/trinity-large-preview:free`)

---

## Summary

| Category | Open | Fixed | Total |
|----------|------|-------|-------|
| Scoring system | 11 | 0 | 11 |
| Infrastructure & runtime | 13 | 0 | 13 |
| Evaluation framework bugs | 5 | 3 | 8 |
| Data quality observations | 5 | 0 | 5 |
| New frontend code bugs | 4 | 0 | 4 |
| New backend code bugs | 3 | 0 | 3 |
| Run ID mismatch | 0 | 1 | 1 |
| Frontend code bugs (prior) | 0 | 19 | 19 |
| Backend code bugs (prior) | 0 | 8 | 8 |
| UX polish gaps | 3 | 0 | 3 |
| **Total** | **44** | **31** | **75** |

---

## Open Issues

---

### A. Scoring System — 11 issues

The scoring engine is entirely heuristic-based (no LLM-as-judge at runtime). Four of eleven task types produce binary or near-binary scores despite returning floats. One task type has a 70% false-zero rate. Five additional issues discovered during comprehensive scorer audit. These issues undermine the validity of evaluation results.

#### S1. Compositional scorer produces 70% false zeros (HIGH) — CONFIRMED

**File:** `agent-evals/src/agent_evals/tasks/compositional.py:92`

The scorer checks `expected.lower() in response_lower` (line 92) for each sub-task. This exact substring match fails when the model paraphrases correctly. Example: expected `"Python 3.11"`, model says `"Python version 3.11"` — scores 0.0.

**Evidence:** 818 of 1,170 compositional trials (70%) score 0.0, yet average token count is 19,700 (normal output length). Only 2 of 818 zeros had 0 tokens (actual errors). The model produces substantial responses that the scorer fails to credit.

**Fix:** Replace substring containment with keyword overlap or semantic similarity. The `extract_keywords` utility used by other task types already exists.

#### S2. Negative scorer is strictly binary (MEDIUM) — CONFIRMED

**File:** `agent-evals/src/agent_evals/tasks/negative.py:131-135`

Checks for ~35 abstention phrases (lines 22-66). If any phrase appears in the lowered response, score = 1.0 (line 134); otherwise 0.0 (line 135). No partial credit exists. A response that hedges ("I'm not certain, but...") scores the same 0.0 as a confident hallucination.

**Distribution:** 820 ones, 446 zeros, 0 partial scores.

**Fix:** Graduate to a rubric: firm refusal (1.0), hedge with caveat (0.7), answer with disclaimer (0.3), confident hallucination (0.0). Consider using the LLM-as-judge infrastructure in `agent_evals/judge/`.

#### S3. Disambiguation scorer has a cliff threshold (MEDIUM) — CONFIRMED

**File:** `agent-evals/src/agent_evals/tasks/disambiguation.py:95-96`

Produces only three values: 0.0, 0.5, or 1.0. The jump from 0.0 to 1.0 happens at line 95-96: `if coverage >= 0.5: answer_score = 1.0`. A response covering 49% of keywords scores 0.0; 50% scores 1.0. Label match at line 103 contributes 0.5. Final score is `max(answer_score, label_score)` (line 105).

**Distribution:** 758 ones, 382 zeros, 69 at 0.5.

**Fix:** Replace the threshold with continuous keyword coverage fraction.

#### S4. Multi-hop scorer is too lenient — 94% ceiling effect (MEDIUM) — CONFIRMED

**File:** `agent-evals/src/agent_evals/tasks/multi_hop.py:105`

Line 105: `if any(self._keyword_in_response(kw, response_lower) for kw in keywords)` — checks if ANY single keyword from each reasoning-chain step appears anywhere in the response. Verbose LLM responses trivially match common technical terms.

**Distribution:** 1,017 of 1,080 trials (94.2%) score 1.0. The task provides no discrimination between variants.

**Fix:** Require a minimum keyword coverage fraction per step (e.g., >= 30%) instead of a single keyword hit.

#### S5. Fact extraction scorer is bimodal (LOW) — CONFIRMED

**File:** `agent-evals/src/agent_evals/tasks/fact_extraction.py:73-79`

Returns 1.0 immediately on exact substring match (line 73-74) or alias match (lines 77-79), falls back to keyword fraction only when exact match fails (lines 82-87). This creates a bimodal distribution where 92% of trials land at 0.0 or 1.0.

**Distribution:** 904 ones, 430 zeros, 126 partial.

**Fix:** Add fuzzy/token-overlap matching (Levenshtein, Jaccard) before falling back to raw keyword fraction.

#### S6. LLM-as-judge infrastructure exists but is unused at scoring time (LOW) — CONFIRMED

**Files:** `agent-evals/src/agent_evals/judge/calibrator.py:239-295`, `agent-evals/src/agent_evals/judge/poll.py`

The judge infrastructure includes rubrics for all 11 task types (calibrator.py `_DEFAULT_RUBRICS` dict, lines 239-295), a `build_judge_prompt()` function, `parse_judge_response()`, a full calibration pipeline, and a PoLL panel mechanism (`poll.py` with 3-model panel), but none of this runs during trial scoring. All runtime scoring uses heuristics only.

**Fix:** Use LLM-as-judge as a secondary scorer when heuristics return 0.0, or as a validation sample to measure heuristic accuracy.

#### S7. Compositional denominator inflated by empty-answer sub-tasks (MEDIUM) — NEW

**File:** `agent-evals/src/agent_evals/tasks/compositional.py:90,95`

When a sub-task has `expected_answer=""`, line 90 skips it via `continue`, but line 95 divides `matched` by `len(self.sub_tasks)` which still counts the empty sub-task. This inflates the denominator, making perfect scores impossible. Example: 4 sub-tasks where 1 has an empty answer — the maximum achievable score is 3/4 = 0.75, not 1.0. This compounds S1's false-zero problem.

**Fix:** Use a `scored_count` variable that only increments for sub-tasks with non-empty expected answers, and divide by `scored_count` instead of `len(self.sub_tasks)`.

#### S8. Negative scorer has false-positive abstention phrases (MEDIUM) — NEW

**File:** `agent-evals/src/agent_evals/tasks/negative.py:64-65`

Two phrases in the abstention list match responses that ARE answering the question: `"based on the available"` (line 64) and `"the provided documentation"` (line 65). A response like "Based on the available documentation, the answer is X" scores 1.0 (correct abstention) even though the model is confidently answering — a false positive. This inflates the 820/1,266 (64.8%) abstention detection rate.

**Fix:** Remove or replace these overly-broad phrases. Consider requiring co-occurrence of an uncertainty marker ("cannot", "not sure", etc.) alongside contextual phrases.

#### S9. Code generation scorer gives 0.0 match_rate when no test patterns defined (LOW) — NEW

**File:** `agent-evals/src/agent_evals/tasks/code_generation.py:120-121`

When the `test` field is empty (no regex patterns defined), `match_rate = 0.0` (line 121). Since match_rate has 70% weight in the formula (line 137: `match_rate * 0.7 + (1.0 - violation_rate) * 0.2 + syntax_bonus * 0.1`), the maximum achievable score is 0.3, regardless of response quality. Also, the class docstring (line 53) documents an outdated formula (`0.8 + 0.2`) that doesn't reflect the current weights (`0.7 + 0.2 + 0.1`).

**Fix:** When no test patterns are defined, either skip the match_rate component and redistribute its weight, or default match_rate to 1.0 (no patterns = no failures).

#### S10. Agentic `_parse_json_or_list` crashes on non-JSON strings (LOW) — NEW

**File:** `agent-evals/src/agent_evals/tasks/agentic.py:47-48`

`_parse_json_or_list()` calls `json.loads(value)` (line 48) without catching `json.JSONDecodeError`. If `FAIL_TO_PASS` or `PASS_TO_PASS` metadata is a non-JSON string (e.g., space-separated test names like `"test_foo test_bar"`), the function raises an unhandled exception, crashing task initialization. The default value `""` is safe (line 46 returns `[]` for empty/whitespace strings), but non-empty non-JSON strings will crash.

**Fix:** Wrap `json.loads()` in a try/except `json.JSONDecodeError`, falling back to whitespace splitting: `return value.strip().split()`.

#### S11. Agentic scorer zero-base for missing metadata components (LOW) — NEW

**File:** `agent-evals/src/agent_evals/tasks/agentic.py:145,168,197`

When metadata fields are empty/missing, scoring sub-components return 0.0 instead of being excluded from the composite. If `files` is empty, both `file_mention_score` (line 146, weight 0.3-0.4) and `content_score` (line 169, weight 0.3-0.4) return 0.0. If `fail_to_pass` is also empty (line 198), `correctness_score` (weight 0.2) returns 0.0. Maximum achievable score with only `expected_tools`: 0.2. With the current agentic mean of 0.389, this may be a contributing factor.

**Fix:** Dynamically adjust component weights based on which metadata fields are actually populated, redistributing weight from inapplicable components to applicable ones.

---

### B. Infrastructure & Runtime — 13 issues

#### I1. Run `9b51360baeb5` stalled at 93.1% completion (HIGH) — CONFIRMED (updated)

The evaluation runner process exited while variant 14 of 14 was 3.3% complete (35 of 1,065 trials). The run remains marked `active` in the database but no process is feeding it. This is an L14 Taguchi design, not L3 as originally reported.

**Completed:** 13 of 14 variants (1,065 each = 13,845 trials). **Partial:** Variant 14 at 35/1,065 trials. **Total:** 13,880 trials of 14,910 expected (93.1%).

**Root cause:** `_run_wrapper` in `run_manager.py:145-155` does not update DB status when the runner crashes (see I9).

**Fix:** Restart the evaluation runner to complete the remaining 1,030 trials, or mark the run as failed and start fresh.

#### I2. Run `b1ca3c026030` stuck as `active` for 6+ days (MEDIUM) — CONFIRMED

Created 2026-02-24. The runner exited with variant 2 at 65.9% (702 of 1,065). Variant 1 fully complete (1,065 trials). Total: 1,767 trials. No process will complete it. The `active` status in the database is stale.

**Fix:** Mark as `failed` via the finish_run API endpoint.

#### I3. No stale-run detection or auto-cleanup (MEDIUM) — CONFIRMED

No mechanism detects when a runner process dies and leaves a run stuck as `active`. The system has no heartbeat, watchdog, or timeout to mark abandoned runs as failed. Grep of the full observatory codebase found zero matches for "heartbeat", "watchdog", or "stale". Both I1 and I2 are symptoms of this missing feature.

**Fix:** Add a heartbeat mechanism — the runner writes a timestamp periodically, and the server marks runs as `failed` if the heartbeat is older than a threshold (e.g., 5 minutes).

#### I4. API returns hardcoded `config: {}` despite DB having config (MEDIUM) — CHANGED

**Original claim:** Config stored as empty `{}` in the database.

**Updated finding:** The config IS correctly stored in the database — `9b51360baeb5` has `config: {"mode": "taguchi", "models": ["openrouter/arcee-ai/trinity-large-preview:free"]}`. However, the API still returns `config: {}` because `_enrich_run()` in `routes.py:188` hardcodes `"config": {}`, and `RunSummary` in `store.py` does not include a `config` field.

**Fix:** Add `config` field to `RunSummary` dataclass, populate it in `list_runs()` and `get_run_summary()`, and use it in `_enrich_run()` instead of the hardcoded `{}`.

#### I5. Failed run `ba37a9ac39d6` has null `finished_at` (LOW) — CONFIRMED

This debug run used the model name `"test"`, causing all 24,396 trials to fail with `LLM Provider NOT provided`. Despite `status = "failed"`, the `finished_at` timestamp is null. Verified via DB query.

**Fix:** Set `finished_at` for consistency. Add a guard in the run submission endpoint to validate that the model string is a valid provider path before starting a run.

#### I6. No model name validation on run submission (LOW) — CONFIRMED

**File:** `agent-evals/src/agent_evals/observatory/run_manager.py:32-44`

The `StartRunRequest` model accepts any string as `model: str` with no validation. The `/api/runs` POST endpoint passes it directly to the runner. The debug run `ba37a9ac39d6` used `"test"` and ran all 24,396 trial slots before every single one failed.

**Fix:** Validate the model string against the model catalog or at least check for a `/` separator (required by LiteLLM's `provider/model` format) before starting the run.

#### I7. No persistent logging (LOW) — CONFIRMED

The backend writes logs only to stdout/stderr. No log files exist in `~/.observatory/` (directory listing shows only `models.db`, `observatory.db`, and WAL/SHM files). Past errors cannot be investigated after the fact.

**Fix:** Add file-based logging to `~/.observatory/observatory.log` with rotation.

#### I8. Model catalog database is stale (LOW) — CONFIRMED

`~/.observatory/models.db` was last written 2026-02-24 10:38 (168KB). The OpenRouter model catalog may have changed since then.

**Fix:** Run a model sync (`POST /api/models/sync`), or add a periodic auto-sync.

#### I9. `_run_wrapper` doesn't mark run as failed in DB on exception (MEDIUM) — NEW

**File:** `agent-evals/src/agent_evals/observatory/run_manager.py:145-155`

When `_execute_run()` raises an exception, `_run_wrapper` logs the error and removes the run from the in-memory `_runs` dict, but does NOT update the DB status. The run stays `active` in the database forever. This is the **root cause** of I1 and I2 — crashed runs permanently appear as active.

**Fix:** Add `self._store.fail_run(run_id)` in the `except` block (requires I10 to be fixed first). Also call `finish_run` in the success path if the orchestrator doesn't already.

#### I10. No `fail_run()` method in ObservatoryStore (MEDIUM) — NEW

**File:** `agent-evals/src/agent_evals/observatory/store.py`

The store only has `finish_run()` which sets status to `'completed'`. There is no API to set status to `'failed'` with a timestamp. The `ba37a9ac39d6` run's `"failed"` status must have been set by direct DB manipulation. This is a prerequisite for fixing I9.

**Fix:** Add a `fail_run(run_id: str, error: str | None = None)` method that sets `status = 'failed'` and `finished_at` to the current time.

#### I11. `_enrich_run` loads all trials into memory (MEDIUM) — NEW (see also N4)

**File:** `agent-evals/src/agent_evals/observatory/web/routes.py:141`

`store.get_trials(run_id)` loads every `TrialRecord` into Python memory to compute aggregates (variant means, model means, token counts). For run `9b51360baeb5` with 13,880 trials, this creates 13,880 dataclass instances per API call. This endpoint is also polled every 5 seconds by the Live Monitor (see N4 in section H).

**Fix:** Add SQL-level aggregation queries (e.g., `GROUP BY variant_name` with `AVG(score)`, `SUM(total_tokens)`) to `ObservatoryStore` and use them in `_enrich_run`.

#### I12. `list_pipelines` endpoint has N+1 query pattern (LOW) — NEW

**File:** `agent-evals/src/agent_evals/observatory/web/routes.py:384-401`

The `list_pipelines` endpoint calls `store.list_runs()` (1 query), then calls `_get_pipeline_id(store, r.run_id)` for each run (N queries, each opening a new DB connection). With 3 runs this is trivial; at scale it would be a performance issue.

**Fix:** Add `pipeline_id` to the `RunSummary` dataclass and include it in the `list_runs()` SQL query, eliminating per-run lookups.

#### I13. `_run_wrapper` silently succeeds for early returns (LOW) — NEW

**File:** `agent-evals/src/agent_evals/observatory/run_manager.py:157-244`

`_execute_run()` has multiple early `return` paths (no API key, no gold_standard directory, no tasks loaded, no variants loaded) that exit without raising an exception. The `_run_wrapper` treats these as success (no exception caught), so the run is removed from memory but the DB still shows `active`. No error is recorded anywhere.

**Fix:** Raise a specific exception (e.g., `RunSetupError`) from early returns so `_run_wrapper` can properly mark the run as failed.

---

### C. Evaluation Framework Bugs — 5 open, 3 fixed

Pre-existing bugs in the agent-evals framework identified across prior sessions and documented in project memory. Three have been fixed since the original report.

#### E1. ~~`fnmatch.fnmatch` glob inconsistency on Linux~~ (MEDIUM) — FIXED

**File:** `agent-index/src/agent_index/tiers.py:177-191`

**Original issue:** `fnmatch.fnmatch` allows `*` to match `/` on Linux.

**Status:** Fixed. `_simple_glob_match` now uses `_simple_glob_to_regex()` which converts `*` to `[^/]*` (regex that does not cross directory boundaries). The comment at line 181 explicitly notes the fix: "unlike fnmatch which allows * to cross path separators on Linux".

#### E2. ~~Absolute path matching in validate.py and autodetect.py~~ (MEDIUM) — FIXED

**Files:** `agent-index/src/agent_index/validate.py:108`, `agent-index/src/agent_index/autodetect.py:197`

**Original issue:** Uses absolute `item.parts` for ignore matching.

**Status:** Fixed. Both files now use `item.relative_to(root).parts`, ensuring ignore matching operates on relative paths from the project root.

#### E3. YAML variant generates invalid YAML with colons in content (MEDIUM) — CONFIRMED

**File:** `agent-evals/src/agent_evals/variants/format_yaml.py:60`

Line 60: `f"    summary: {summary}"` — if `summary` contains colons (e.g., `"JWT auth: token-based"`) the output is `summary: JWT auth: token-based` which is invalid YAML. No quoting or escaping is applied.

**Fix:** Wrap the summary value in quotes: `f'    summary: "{summary}"'` or use a YAML library (`yaml.dump`).

#### E4. Pipe-delimited and markdown table variants break with `|` in content (MEDIUM) — CONFIRMED

**File:** `agent-evals/src/agent_evals/variants/format_pipe_delimited.py:52-53`

Line 53: `f"{doc.rel_path}|{doc.section}|{doc.tier}|{tokens}|{summary}"` — if `summary` contains `|`, the row gains extra columns. No escaping is applied.

**Fix:** Escape or replace `|` characters within cell content before generating table output.

#### E5. ~~`variant.teardown()` not called on trial exception~~ (LOW) — FIXED

**File:** `agent-evals/src/agent_evals/runner.py:278-281`

**Original issue:** `variant.teardown()` was not in a `finally` block.

**Status:** Fixed. The teardown is now in a `finally` block (lines 278-281): `finally: for variant in variants: variant.teardown()`.

#### E6. `TrialResult.metrics` always empty — metrics module not integrated (LOW) — CONFIRMED

**File:** `agent-evals/src/agent_evals/runner.py:263, 631`

Both the error path (line 263: `metrics={}`) and the success path (line 631: `metrics={}`) hardcode an empty dict. The `TrialResult.metrics` field is never populated.

**Fix:** Integrate the metrics module into the runner so that per-trial metrics (latency breakdown, token efficiency, etc.) are populated.

#### E7. `bootstrap_ci` does not handle NaN data (LOW) — CONFIRMED

**File:** `agent-evals/src/agent_evals/scoring.py:257-318`

`bootstrap_ci` at line 284 does `np.asarray(data, dtype=np.float64)` which preserves NaN values. `np.ptp(arr)` returns NaN for arrays containing NaN, so the zero-variance shortcut (line 290) is skipped. The scipy BCa bootstrap then produces NaN confidence intervals.

**Fix:** Filter NaN values before computing: `arr = arr[~np.isnan(arr)]`, or raise a clear error if NaN is present.

#### E8. All 30 robustness tasks missing `base_task_id` metadata (LOW) — CONFIRMED

**File:** `agent-evals/gold_standard/robustness/robustness_*.yaml`

Verified: all 30 YAML files lack `base_task_id` in their `metadata` dict. Sample metadata: `{perturbation_type: typo, original_question: ..., expected_answer: ..., perturbation_details: ...}`.

**Fix:** Add `base_task_id` to each robustness task's metadata.

---

### D. Data Quality Observations — 5 issues

Specific findings from the audit of run `9b51360baeb5`. Data updated with current trial counts (13,880 trials across 14 variants).

#### D1. Strongly bimodal score distribution (HIGH) — CONFIRMED (updated)

35.3% of all trials score exactly 1.0 and 17.0% score exactly 0.0. Only 47.7% produce partial-credit scores. This bimodality is driven by the scorer issues in section A, but it means the current run's aggregate statistics are unreliable as a measure of model quality.

**Token analysis confirms false zeros:** Zero-score trials average 18,967 tokens — nearly identical to partial-score (19,419) and perfect-score (19,738) trials. The model produced substantial responses that the heuristic scorers failed to credit.

| Score Category | Trials | % of Total | Avg Tokens | Avg Latency |
|----------------|--------|-----------|------------|-------------|
| Zero (0.0) | 2,354 | 17.0% | 18,967 | 14.4s |
| Partial (0-1 exclusive) | 6,624 | 47.7% | 19,419 | 13.1s |
| Perfect (1.0) | 4,905 | 35.3% | 19,738 | 7.3s |

#### D2. Compositional task type is catastrophically underscored (HIGH) — CONFIRMED (updated)

Mean score 0.114 with 70% zeros (818 of 1,170 trials). Updated with full 14-variant data.

| Task Type | Mean | Trials | Zeros | Ones | Assessment |
|-----------|------|--------|-------|------|------------|
| compositional | 0.114 | 1,170 | 818 (70%) | 0 | Scorer broken |
| agentic | 0.391 | 1,208 | 9 | 0 | Model weakness (genuine) |
| efficiency | 0.453 | 1,170 | 128 | 252 | Mixed |
| conflicting | 0.574 | 1,170 | 0 | 1 | Healthy distribution |
| robustness | 0.605 | 1,170 | 0 | 81 | Healthy distribution |
| negative | 0.648 | 1,365 | 480 | 885 | Binary scorer |
| disambiguation | 0.656 | 1,209 | 382 | 758 | Cliff threshold |
| fact_extraction | 0.665 | 1,521 | 450 | 935 | Bimodal scorer |
| retrieval | 0.832 | 1,521 | 86 | 892 | Healthy distribution |
| code_generation | 0.971 | 1,209 | 0 | 0 | Healthy distribution |
| multi_hop | 0.977 | 1,170 | 1 | 1,101 | Ceiling effect |

#### D3. SSE stream emits duplicate events on reconnect (LOW) — CONFIRMED

During the systems audit, the SSE stream sent a `connected` event followed by a duplicate of the last `trial_completed` event (same task_id, same data). This may be intentional replay-on-reconnect behavior, but clients that increment counters on each event will double-count.

**Fix:** Either document this as expected behavior and ensure the frontend deduplicates, or add an event sequence number so clients can detect replays.

#### D4. Perfect-score latency is suspiciously low (LOW) — CONFIRMED

Perfect-score trials average 7.3s latency compared to 14.4s for zero-score and 13.1s for partial-score trials. The near-2x difference is consistent across all 14 variants.

**Fix:** Sample and manually review a set of 1.0-scoring trials across task types, especially multi_hop and fact_extraction.

#### D5. Run is part of a pipeline but pipeline view shows nothing (LOW) — CONFIRMED (clarified)

Run `9b51360baeb5` has `pipeline_id = "83973e5dca97"` in the database. The backend `list_pipelines` endpoint correctly finds 2 pipelines (verified: `83973e5dca97` and `1a4598bc2e7d`). The `phase_results` table has 0 rows — no Taguchi analysis has been saved. The issue is likely that the frontend Pipeline View page either doesn't call the correct endpoint or requires phase results to display content.

**Fix:** Investigate the frontend pipeline page logic. The backend data exists but the phase results are empty because the runs didn't complete their analysis phase.

---

### E. UX Polish Gaps — 3 issues

From the 27-item UX polish audit (2026-02-24), 24 items are implemented. Three remain.

#### U1. Chart entry animations not configured (LOW)

**Files:** Chart option objects in `Observatory.tsx`, `LiveMonitor.tsx`, `ResultsExplorer.tsx`, `History.tsx`, `FactorAnalysis.tsx`

Charts render instantly. Adding `animation: { duration: 800, easing: 'easeOutQuart' }` to chart options would make data visualizations feel polished.

#### U2. CompassCheckbox inline CSS not fully cleaned up (LOW)

**File:** `CompassCheckbox.tsx:59-78`

CSS keyframe animations moved to `globals.css`, but some inline SVG styling remains in the component.

#### U3. SlideOutPanel close button missing explicit focus style (LOW)

**File:** `SlideOutPanel.tsx:45`

The close button lacks a custom `focus-visible` style. The global focus ring applies but may need `outline-offset` for adequate spacing.

---

### F. Frontend Warnings (non-blocking)

#### W1. React Router v6 to v7 future flag warnings

The console shows warnings about React Router future flags (`v7_startTransition`, `v7_relativeSplatPath`). These are non-breaking but indicate the app should opt into v7 behavior before upgrading.

---

### G. New Frontend Code Bugs — 4 issues

Discovered during fix verification audit (2026-03-02). These are distinct from the 19 frontend bugs already fixed.

#### N1. `useSSE.ts`: JSON.parse without try/catch on SSE events (MEDIUM)

**File:** `useSSE.ts:50, 62`

Lines 50 and 62 call `JSON.parse(e.data)` on SSE event data without error handling. If the server sends malformed JSON (e.g., during partial writes or connection issues), this throws an unhandled exception that crashes the SSE event handler, silently breaking the entire event stream. The REST API's JSON parsing was fixed (issue #9) but the SSE path was missed.

**Fix:** Wrap both `JSON.parse` calls in try/catch, logging the error and skipping the malformed event.

#### N2. `useLiveMonitorState.ts`: scores array grows unbounded (MEDIUM)

**File:** `useLiveMonitorState.ts:78`

`setScores((prev) => [...prev, trial.score])` grows without limit. Unlike `trialTimestamps` (capped at `MAX_TIMESTAMPS=1000`) and `recentTrials` (capped at `MAX_RECENT_TRIALS=50`), the `scores` array keeps every trial score forever. For the 24K-trial run, this means 24K+ entries in state, and the chart at `LiveMonitor.tsx:87` renders all of them as data points.

**Fix:** Cap scores to a `MAX_SCORES` window (e.g., 1000) similar to timestamps, or downsample for chart rendering.

#### N3. `client.ts`: deleteGroup bypasses fetchApi wrapper (LOW)

**File:** `client.ts:274`

`deleteGroup` uses raw `fetch()` instead of the `fetchApi` wrapper, bypassing the AbortController timeout (30s), JSON error handling, and typed error reporting that every other endpoint uses. If the backend hangs, this call will hang indefinitely.

**Fix:** Refactor to use `fetchApi<void>` with `method: "DELETE"`.

#### N7. `useSSE.ts`: poll interval continues after max reconnects (LOW)

**File:** `useSSE.ts:69-100`

When `MAX_RECONNECTS` is reached at line 94, `disconnect()` closes the EventSource, but the 5-second poll interval (started at line 69) continues running. It keeps hitting `GET /api/runs/{runId}` every 5 seconds indefinitely even though the SSE connection has been abandoned. The poll is only cleaned up on unmount (line 103) or runId change.

**Fix:** Store the interval ID in a ref and clear it in the max-reconnect branch alongside the disconnect call.

---

### H. New Backend Code Bugs — 3 issues

Discovered during fix verification audit (2026-03-02). These are distinct from the 8 backend bugs already fixed.

#### N4. `routes.py`: _enrich_run loads all trials into memory (MEDIUM) — see also I11

**File:** `routes.py:141`

`_enrich_run()` calls `store.get_trials(run_id)` which loads every trial for a run into Python memory, then iterates the full list 5+ times for different aggregations. For runs with 24K+ trials, this is ~24K objects per request. This endpoint is called on every 5-second poll from the Live Monitor, creating continuous memory pressure. Independently identified by both fix-verifier and infra-verifier audits (see I11 in section B).

**Fix:** Move aggregation to SQL (`SUM`, `COUNT`, `AVG` with `GROUP BY`) and return aggregated results from the store.

#### N5. `routes.py`: list_runs pagination is cosmetic (LOW)

**File:** `routes.py:111-112`

`store.list_runs()` executes a full SQL query with no `LIMIT`/`OFFSET`, loading all runs into Python memory. The pagination params at lines 108-109 only slice the already-loaded list. As runs accumulate, this query gets progressively slower.

**Fix:** Add `limit` and `offset` parameters to `store.list_runs()` and push them into the SQL query.

#### N6. `store.py`: TrialRecord missing oa_row_id and phase fields (LOW)

**File:** `store.py:18-35`

The `TrialRecord` dataclass has 15 fields ending at `error`, but the database schema includes `oa_row_id` (INTEGER) and `phase` (TEXT) columns. `get_trials()` at lines 357-374 constructs `TrialRecord` without these fields. Any code that needs `oa_row_id` from a retrieved trial (e.g., Taguchi factor analysis) will not have access to it.

**Fix:** Add `oa_row_id: int | None` and `phase: str | None` fields to `TrialRecord` and include them in `get_trials()` construction.

---

## Fixed Issues (2026-03-02) — ALL 28 VERIFIED

All fixes applied by parallel agent team. Not yet committed. All 28 fixes independently verified against current code by fix-verifier audit (2026-03-02).

### Run ID Mismatch — 1 issue (FIXED)

#### F0. RunManager and orchestrator generate different run IDs

**Files changed:** `orchestrator.py:65, 198`, `run_manager.py:226`

`RunManager.start_run()` generated a run_id and tracked it in memory, but never passed it to the orchestrator. The orchestrator generated its own run_id and stored it in the database. The Live Monitor queried the tracker's ID, then got 404s looking up run data under that ID.

**Fix:** Added `run_id` field to `OrchestratorConfig`. The orchestrator now uses a provided run_id when available, falling back to generating one when not.

### Frontend Code Bugs — 19 issues (FIXED)

#### LiveMonitor & SSE domain (8 fixes)

| # | Severity | Description | File | Fix |
|---|----------|-------------|------|-----|
| 2 | HIGH | Null dereference on SSE poll `summary.status` | `useSSE.ts:70-73` | Added `summary?.status` optional chaining |
| 3 | HIGH | Infinite SSE reconnect on server down | `useSSE.ts:87-89` | Added `MAX_RECONNECTS = 10` with counter and error state |
| 5 | HIGH | Division by zero in `trialsPerMin` | `useLiveMonitorState.ts:113-125` | Guard returns 0 when `elapsedMs < 1000` |
| 8 | MEDIUM | No ErrorBoundary on LiveMonitor | `LiveMonitor.tsx:46-90` | Added `LiveMonitorErrorBoundary` class component |
| 11 | MEDIUM | Unchecked `d.model`, `d.cost` in alert formatter | `useLiveMonitorState.ts:164-176` | Added optional chaining with fallback values |
| 14 | MEDIUM | `trialTimestamps` array grows unbounded | `useLiveMonitorState.ts:48, 79` | Capped at 1,000-entry sliding window |
| 21 | LOW | Unused eslint-disable comment | `useLiveMonitorState.ts:125` | Removed |
| 25 | LOW | Hardcoded `DEFAULT_TOTAL_TASKS = 355` | `useLiveMonitorState.ts:8` | Accepts `totalTasksOverride` param with fallback |

#### API Client, Hooks & Filters domain (6 fixes)

| # | Severity | Description | File | Fix |
|---|----------|-------------|------|-----|
| 6 | HIGH | `String(undefined)` creates `free=undefined` URL param | `useFilterParams.ts:37` | Explicit null/undefined check before `String()` |
| 7 | HIGH | No `staleTime` on useQuery — thundering herd | `hooks.ts:13-19` | Added tiered staleTime (5s/10s/30s) and gcTime (5min) to all 16 hooks |
| 9 | MEDIUM | `res.json() as T` with no validation | `client.ts:3-15` | try/catch around JSON parse with typed error |
| 15 | LOW | No fetch timeout — UI hangs if backend down | `client.ts` | Added AbortController with 30s timeout |
| 17 | LOW | NaN from invalid numeric URL params | `useFilterParams.ts:11-25` | `parseNum()` helper returns undefined instead of NaN |
| 24 | LOW | No React Query gcTime/staleTime defaults | `hooks.ts` | Configured alongside issue #7 |

#### Pages & Components domain (5 fixes)

| # | Severity | Description | File | Fix |
|---|----------|-------------|------|-----|
| E1 | LOW | Radio button overlay blocks programmatic clicks | `RunConfig.tsx` | Changed from `sr-only` to `absolute inset-0 opacity-0 cursor-pointer` |
| E2 | MEDIUM | Nav overflow on mobile — no scroll or hamburger | `App.tsx` | Added `overflow-x-auto` and `whitespace-nowrap` |
| 16 | LOW | Double-submission risk on error | `RunConfig.tsx:35-67` | Added `cooldown` state with 1500ms delay |
| 19 | LOW | Potential XSS in error messages | `RunConfig.tsx:329-332` | Verified safe — React JSX auto-escapes; no `dangerouslySetInnerHTML` |
| 20 | LOW | FilterPanel labels not associated with inputs | `FilterPanel.tsx:80-88` | Added `htmlFor`/`id` associations |

### Backend Code Bugs — 8 issues (FIXED)

#### Python API Routes (4 fixes)

| # | Severity | Description | File | Fix |
|---|----------|-------------|------|-----|
| 10 | MEDIUM | ZeroDivisionError in variant aggregation | `routes.py:135-200` | Added `if v["trial_count"] else 0.0` guards |
| 13 | MEDIUM | `finish_run` has no idempotency check | `routes.py:209-216` | Returns current state if already completed/failed |
| 22 | LOW | No pagination on `/api/runs` | `routes.py:106-109` | Added `limit=50, offset=0` query params |
| 23 | LOW | No pagination on `/api/models` | `routes.py` | Added `limit=100, offset=0` with total count |

#### Python Backend Core (4 fixes)

| # | Severity | Description | File | Fix |
|---|----------|-------------|------|-----|
| 1 | HIGH | SQL injection via string interpolation | `model_catalog.py:184-188` | Parameterized with `?` placeholders; removed `# noqa: S608` |
| 4 | HIGH | `remove_listener()` raises ValueError | `tracker.py:69-77` | Wrapped in try/except ValueError |
| 12 | MEDIUM | Silent swallowing of all OperationalError | `store.py:117-131` | Only suppresses "duplicate column"/"already exists"; re-raises others |
| 18 | LOW | Missing FK constraint on `parent_run_id` | `store.py:schema` | Added `REFERENCES runs(run_id)`; pragma already enabled |

---

## Appendix: Run `9b51360baeb5` Snapshot

**Original audit:** 2026-03-01 ~03:47 UTC. **Updated:** 2026-03-02 (verification audit).

| Field | Value (original) | Value (updated) |
|-------|-------------------|-----------------|
| Run ID | `9b51360baeb5` | — |
| Run Type | Taguchi (screening phase) | Taguchi L14 (screening phase) |
| Pipeline ID | `83973e5dca97` | — |
| Status | Active (stalled) | Active (stalled) |
| Model | `openrouter/arcee-ai/trinity-large-preview:free` | — |
| Config | `{}` (reported) | `{"mode": "taguchi", "models": ["openrouter/arcee-ai/trinity-large-preview:free"]}` |
| Created | 2026-02-28 20:42:57 UTC | — |
| Total Trials | 2,321 | **13,880** |
| Expected Trials | 3,195 (3 variants) | **14,910 (14 variants x 355 tasks x 3 reps)** |
| Completion | 72.6% | **93.1%** |
| Mean Score | 0.6214 | — |
| Total Cost | $0.00 | — |
| Unique Tasks | 355 / 355 | — |

### Variant Progress (updated)

14 Taguchi L14 orthogonal array rows. 13 complete, 1 partial.

| # | Variant (abbreviated) | Trials | Expected | Completion | Mean Score |
|---|----------------------|--------|----------|------------|------------|
| 1 | no-docs+2tier+markdown-table+edges+llm-compressed+noise-0 | 1,065 | 1,065 | 100% | 0.626 |
| 2 | no-docs+3tier+plain-markdown+bluf+algorithmic+noise-25 | 1,065 | 1,065 | 100% | 0.654 |
| 3 | no-docs+4tier+markdown-list+natural+tagged+noise-50 | 1,065 | 1,065 | 100% | 0.576 |
| 4 | no-docs+flat+pipe-delimited+bluf+restructured+noise-75 | 1,065 | 1,065 | 100% | 0.594 |
| 5 | no-docs+inline-required+yaml+random+passthrough+noise-0 | 1,065 | 1,065 | 100% | 0.693 |
| 6 | no-index+2tier+markdown-list+bluf+algorithmic+noise-0 | 1,065 | 1,065 | 100% | 0.658 |
| 7 | no-index+3tier+pipe-delimited+random+tagged+noise-25 | 1,065 | 1,065 | 100% | 0.577 |
| 8 | no-index+4tier+yaml+edges+restructured+noise-50 | 1,065 | 1,065 | 100% | 0.585 |
| 9 | no-index+flat+markdown-table+bluf+passthrough+noise-75 | 1,065 | 1,065 | 100% | 0.681 |
| 10 | no-index+inline-required+plain-markdown+natural+llm-compressed+noise-0 | 1,065 | 1,065 | 100% | 0.629 |
| 11 | oracle+2tier+pipe-delimited+natural+passthrough+noise-0 | 1,065 | 1,065 | 100% | 0.693 |
| 12 | oracle+3tier+yaml+bluf+llm-compressed+noise-25 | 1,065 | 1,065 | 100% | 0.613 |
| 13 | oracle+4tier+markdown-table+random+algorithmic+noise-50 | 1,065 | 1,065 | 100% | 0.653 |
| 14 | oracle+flat+plain-markdown+edges+tagged+noise-75 | **35** | 1,065 | **3.3%** | 0.452 |

### System Health at Audit Time

| Metric | Value | Assessment |
|--------|-------|------------|
| Backend PID | 807119 | Healthy (10h uptime, 330MB RSS) |
| Backend threads | 55 | Normal |
| CPU usage | 0.6% avg | Low |
| Open file descriptors | 32 / 256 | No leak |
| API response time | < 50ms | Fast |
| SSE keepalives | Every 1-1.5s | Healthy |
| DB WAL size | 41KB | Normal |
| Console errors | 0 (backend), 2 (frontend — 404s from ID mismatch) | Explained |
