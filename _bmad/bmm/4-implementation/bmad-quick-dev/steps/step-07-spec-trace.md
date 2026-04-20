---
name: 'step-07-spec-trace'
description: 'Write spec-{slug}.md trace with status: done after standard pipeline completes'

state_vars:
  - baseline_commit
  - execution_mode
  - tech_spec_path
  - spec_file
---

# Step 7: Spec Trace (standard pipeline)

**Goal:** After `step-06-resolve-findings.md` completes, write a spec-trace markdown file at `{implementation_artifacts}/spec-{slug}.md` with `route: 'standard'` and `status: 'done'`. This is the **write-back** point for the quick-dev spec lifecycle — without it, Feature 2's previous-story continuity scan finds zero candidates.

> **Lifecycle reminder:** `draft → ready-for-dev → in-progress → in-review → done`. Only this step (or `step-oneshot.md` on the one-shot route) flips `status` to `done`. `step-06-resolve-findings.md` does NOT touch frontmatter.

---

## AVAILABLE STATE

From previous steps:

- `{baseline_commit}` - Git HEAD at workflow start (used to derive the change set for Suggested Review Order).
- `{execution_mode}` - `"tech-spec"` or `"direct"`.
- `{tech_spec_path}` - Tech-spec file (Mode A). On Mode A runs, `{spec_file}` defaults to this path; the status flip updates it in place. On Mode B runs, no prior spec exists — this step **creates** a fresh spec-trace at `{implementation_artifacts}/spec-{slug}.md`.
- Findings summary from step-06 (for the Intent section's Approach line).

---

## ENTRY CONDITION

Runs for **ALL** completed standard-pipeline runs, regardless of mode. Even trivial direct-mode changes produce a spec-trace so the continuity scan (Feature 2) always has `status: done` candidates to pick up.

**Do NOT run this step** if the workflow arrived from `step-oneshot.md` — that branch writes its own trace inline.

---

## EXECUTION SEQUENCE

### 1. Resolve `{spec_file}` path

- **If Mode A (tech-spec):** `{spec_file}` = `{tech_spec_path}`. The existing spec keeps its filename; this step updates it in place.
- **If Mode B (direct):** derive a slug from the user's original intent using `deriveSpecSlug(intent, { existingSlugs })` from `tools/quick-dev-scan.js`. Compose `{spec_file}` = `{implementation_artifacts}/spec-{slug}.md`. If the file already exists, the helper's collision rule appends `-2`, `-3`, ...

### 2. Construct change set

Build `changes[]` from the diff since `{baseline_commit}`:

```bash
git diff --name-only {baseline_commit}
```

For each changed file, pick one or more stop lines (entry point for the design intent; hotspots worth review). Assign each stop a `concern` label derived from what it accomplishes (e.g., "validation", "schema", "UI binding", "Tests", "Config"). Use concern names matching the peripheral regex (`test(s)`, `config`, `type(s)`, `style`, `lint`, `doc(s)`, `fixture(s)`) to route stops to the end of the review order.

Write one ≤15-word framing sentence per stop.

### 3. Generate and write the trace

Invoke the shared helper:

```js
import { generateSpecTrace } from './tools/quick-dev-scan.js';

const body = generateSpecTrace({
  intent,          // original user intent string
  route: 'standard',
  changes,         // from step 2
  slug,            // from step 1 (Mode B) or extracted from {tech_spec_path} basename (Mode A)
  title,           // concise title derived from intent
  problem,         // one-sentence problem statement
  approach,        // one-sentence approach summary (reuse findings summary from step-06)
  specFileDir,     // directory containing {spec_file}, for relative link computation
});
```

Write `body` to `{spec_file}`. On Mode A, this overwrites the existing tech-spec; preserve any human-authored sections not emitted by `generateSpecTrace` by merging rather than replacing (append `## Suggested Review Order` after the last existing section, update frontmatter fields in place). The helper's output is the canonical template — consult `./suggested-review-order.md` for the shared rules.

### 4. Verify the write-back

Read `{spec_file}` back and assert:

- Frontmatter contains `status: 'done'` and `route: 'standard'`.
- Body contains `## Suggested Review Order`.

On mismatch, HALT and surface the diff for operator inspection.

### 5. Sync sprint status (optional)

If the project ships `sync-sprint-status.md` and `{spec_file}` references a sprint story, follow that task with `{target_status}` = `done`. If the task is absent, skip silently.

---

## PRESENT

Display to the user:

```
**Spec trace written:** {spec_file}
Frontmatter: route=standard, status=done
Suggested Review Order: {N} stops across {M} concerns
```

Offer to open `{spec_file}` in the editor (see step-oneshot.md's Present section for the `code -r` invocation; reuse the same convention).

---

## NEXT STEP DIRECTIVE

This is the **final step** of the standard pipeline. No further step files. The Quick Dev workflow is complete.

---

## SUCCESS METRICS

- `{spec_file}` exists at `{implementation_artifacts}/spec-{slug}.md` (Mode B) or the Mode A tech-spec path.
- Frontmatter contains `status: 'done'` and `route: 'standard'`.
- Body contains `# Title`, `## Intent` (with Problem + Approach), and `## Suggested Review Order`.
- Step-06 did NOT touch frontmatter — this step is the sole write-back site for the standard pipeline.

## FAILURE MODES

- Skipping this step for "trivial" runs — breaks Feature 2 continuity.
- Running this step AND step-oneshot.md in the same workflow — routes are mutually exclusive.
- Letting step-06-resolve-findings.md write the `done` status — violates the single-writer rule.
