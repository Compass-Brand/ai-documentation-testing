---
name: 'step-oneshot'
description: 'Short-circuit route: implement, self-check, write spec trace (status: done), commit, present'

state_vars:
  - baseline_commit
  - execution_mode
  - spec_file

deferred_work_file: '{implementation_artifacts}/deferred-work.md'
---

# Step One-Shot: Implement, Review, Present

**Goal:** A single-pass short-circuit for trivial changes. Skips `step-02-context-gathering.md` through `step-06-resolve-findings.md` entirely. Mirrors upstream `BMAD-METHOD/src/bmm-skills/4-implementation/bmad-quick-dev/step-oneshot.md` with Compass-specific adaptations (shared trace template via `../suggested-review-order.md`, our adversarial-review skill surface).

> **Lifecycle reminder:** `draft → ready-for-dev → in-progress → in-review → done`. This step writes `status: 'done'` as part of the inline trace generation. `step-06-resolve-findings.md` is not visited on this route, so there is no competing write site.

---

## RULES

- YOU MUST ALWAYS SPEAK OUTPUT in your Agent communication style with the config `{communication_language}`.
- **NEVER auto-push.**
- This route is mutually exclusive with `step-07-spec-trace.md` — only one of the two produces the spec-trace for any given run.

---

## AVAILABLE STATE

- `{baseline_commit}` - Git HEAD at workflow start (Mode B).
- `{execution_mode}` = `"direct"` (one-shot is only selectable from Mode B).
- `{planning_context_files}` - Optional; selectively loaded by B.0 when the intent warranted it. If set, skim as context but do NOT over-invest — this route is for trivial changes.
- `{continuity_context}` - Almost always unset on this route (continuity belongs to Mode A tech-spec flows). Respect if somehow carried over.

---

## INSTRUCTIONS

### 1. Implement

Implement the clarified intent directly against the working tree. Keep the change minimal and focused — one-shot assumes the change is trivial. If during implementation the scope turns out larger than expected, HALT and recommend escalating back to the standard pipeline (offer the user a choice to rerun with `[E] Execute directly` for the linear flow).

### 2. Self-check

Run a quick adversarial self-review. Invoke the `bmad-review-adversarial-general` skill in a subagent with the changed files. The subagent gets NO conversation context — to avoid anchoring bias. Launch at the same model capability as the current session. If no sub-agents are available, write the changed files to a review prompt file under `{implementation_artifacts}/` and HALT; ask the human to run the review in a separate session and paste back the findings.

### 3. Classify

Deduplicate all findings. Three categories only:

- **patch** — trivially fixable. Auto-fix immediately.
- **defer** — pre-existing issue not caused by this change. Append to `{deferred_work_file}`.
- **reject** — noise. Drop silently.

If a finding is caused by this change but too significant for a trivial patch, HALT and present it to the human for decision before proceeding.

### 4. Generate Spec Trace

Derive:

- `{slug}` from the clarified intent using `deriveSpecSlug(intent, { existingSlugs })` from `tools/quick-dev-scan.js`.
- `{spec_file}` = `{implementation_artifacts}/spec-{slug}.md`.
- `{title}` — a concise human-readable title derived from the intent.
- `{problem}` and `{approach}` — one sentence each, reusing the summary you produced during implementation.

Build `changes[]` by walking the diff since `{baseline_commit}`. For each stop, assign a `concern` label and a ≤15-word framing. Route peripheral stops (tests, config, types, style, lint, docs, fixtures) into concern names that match the peripheral regex so the helper orders them last.

Invoke the shared helper:

```js
import { generateSpecTrace } from './tools/quick-dev-scan.js';

const body = generateSpecTrace({
  intent,
  route: 'one-shot',
  changes,
  slug,
  title,
  problem,
  approach,
  specFileDir,   // directory containing {spec_file}
});
```

Write `body` to `{spec_file}`. See `../suggested-review-order.md` for the shared rules governing the `## Suggested Review Order` section — this is the same template `step-07-spec-trace.md` consumes, so the two routes produce structurally identical traces apart from the `route` frontmatter value.

Verify the write-back: read `{spec_file}` back and assert frontmatter has `status: 'done'` and `route: 'one-shot'`; body contains `# {title}`, `## Intent`, and `## Suggested Review Order`. On mismatch, HALT.

### 5. Commit

If version control is available and the tree is dirty, create a local commit with a conventional message derived from the intent (e.g., `feat: {title}` / `fix: {title}` / `refactor: {title}`). If VCS is unavailable, skip.

**Never push automatically.**

### 6. Present

1. Open the spec in the user's editor so they can click through the Suggested Review Order:

   - Resolve two absolute paths: (1) the repository root (`git rev-parse --show-toplevel` — returns the worktree root when in a worktree; if it fails, fall back to the current working directory), (2) `{spec_file}`.
   - Run `code -r "{absolute-root}" "{absolute-spec-file}"` — the root first so VS Code opens in the right context, then the spec file. Always double-quote paths to handle spaces and special characters.
   - If `code` is not available (command fails), skip gracefully and tell the user the spec file path instead.

2. Display a summary in conversation output, including:

   - The commit hash (if one was created).
   - List of files changed with one-line descriptions. Any file paths shown in conversation/terminal output must use CWD-relative format (no leading `/`) with `:line` notation (e.g., `src/path/file.ts:42`) for terminal clickability — this differs from spec-file links which use spec-file-relative paths.
   - Review findings breakdown: patches applied, items deferred, items rejected. If all findings were rejected, say so.
   - A note that the spec is open in their editor (or the file path if it couldn't be opened). Mention that `{spec_file}` now contains a Suggested Review Order.
   - **Navigation tip:** "Ctrl+click (Cmd+click on macOS) the links in the Suggested Review Order to jump to each stop."

3. Offer to push and/or create a pull request.

HALT and wait for human input.

---

## NEXT STEP DIRECTIVE

This is the **final step** of the one-shot route. No further step files. The Quick Dev workflow is complete.

---

## SUCCESS METRICS

- `{spec_file}` written with `route: 'one-shot'`, `status: 'done'`, `# Title`, `## Intent` (Problem + Approach), `## Suggested Review Order`.
- Local commit created (if VCS available) — never auto-pushed.
- Summary presented including commit hash, files changed, findings breakdown, and editor-open note.

## FAILURE MODES

- Auto-pushing without explicit user request.
- Skipping the spec trace — breaks the write-back lifecycle and Feature 2 continuity.
- Running both this step AND `step-07-spec-trace.md` for the same workflow.
- Running this route for scope that should have been tech-spec'd.
