---
name: 'step-01-mode-detection'
description: 'Determine execution mode (tech-spec vs direct), handle escalation, set state variables'

nextStepFile_modeA: './step-03-execute.md'
nextStepFile_modeB: './step-02-context-gathering.md'

state_vars:
  - baseline_commit
  - execution_mode
  - tech_spec_path
  - epic_num
  - story_num
  - epic_context_path
  - continuity_context
  - planning_context_files
---

# Step 1: Mode Detection

**Goal:** Determine execution mode, capture baseline, handle escalation if needed.

---

## STATE VARIABLES (capture now, persist throughout)

These variables MUST be set in this step and available to all subsequent steps:

- `{baseline_commit}` - Git HEAD at workflow start (or "NO_GIT" if not a git repo)
- `{execution_mode}` - "tech-spec" or "direct"
- `{tech_spec_path}` - Path to tech-spec file (if Mode A)
- `{epic_num}` - Epic number inferred from the tech-spec (Mode A, A.1). Unset if not derivable.
- `{story_num}` - Story number inferred from the tech-spec (Mode A, A.1). Unset if not derivable.
- `{epic_context_path}` - Absolute path to the compiled epic context file (Mode A, A.1). Unset when A.1 falls through silently. **Precedence:** when set, downstream steps IGNORE `{planning_context_files}` (Mode B, B.0) — the epic context already summarizes planning docs.
- `{continuity_context}` - Concatenated Code Map + Design Notes + Spec Change Log + Tasks sections extracted from the most recent prior `status: done` spec in the same epic (Mode A, A.2). Unset when no prior story exists or the operator skips the in-review fallback.
- `{planning_context_files}` - Array of absolute paths to planning artifacts (PRD / architecture / UX / epic / brief) selectively loaded for direct-mode relevance (Mode B, B.0). Unset when no planning directory exists or no files match. **Precedence:** downstream steps MUST ignore this var when `{epic_context_path}` is set — Feature 1's epic context already summarizes the same planning docs.

---

## EXECUTION SEQUENCE

### 1. Capture Baseline

First, check if the project uses Git version control:

**If Git repo exists** (`.git` directory present or `git rev-parse --is-inside-work-tree` succeeds):

- Run `git rev-parse HEAD` and store result as `{baseline_commit}`

**If NOT a Git repo:**

- Set `{baseline_commit}` = "NO_GIT"

### 2. Load Project Context

Check if `{project_context}` exists (`**/project-context.md`). If found, load it as a foundational reference for ALL implementation decisions.

### 3. Parse User Input

Analyze the user's input to determine mode:

**Mode A: Tech-Spec**

- User provided a path to a tech-spec file (e.g., `quick-dev tech-spec-auth.md`)
- Load the spec, extract tasks/context/AC
- Set `{execution_mode}` = "tech-spec"
- Set `{tech_spec_path}` = provided path
- Proceed to sub-section **A.1 Epic inference** below before transitioning to step-03.

#### A.1 Epic inference

**Purpose:** When the tech-spec belongs to an epic, compile (or reuse) a cached epic-context summary so step-02/03 can load it as a single concise reference instead of re-deriving from raw planning docs.

**Enter when:** `{execution_mode}` = "tech-spec" AND `{tech_spec_path}` is set.
**Exit when:** `{epic_context_path}` is either set to a validated context file OR left unset (silent fall-through). In both cases, continue to sub-section **A.2 Previous story continuity** below.

Execute these sub-items in order:

**3a. Parse tech-spec frontmatter.** Read the YAML frontmatter of `{tech_spec_path}`. Derive `{epic_num}` using the first rule that yields a positive integer:

1. `epic:` field (e.g., `epic: 3`)
2. `story:` field parsed as `E.S` (e.g., `story: 3.2` → epic 3)
3. Filename slug regex `^(\d+)-` against `basename({tech_spec_path})` (e.g., `spec-3-2-auth.md` → 3)

Also derive `{story_num}` from the `story:` field when present (e.g., `story: 3.2` → 2), or from the second digit group of the filename slug `^\d+-(\d+)-` when absent. Leave `{story_num}` unset if neither source yields a value.

If no rule yields `{epic_num}`, skip to sub-item **3e** (silent fall-through).

**3b. Check for cached epic context.** Resolve `{epic_context_path}` candidate as `{implementation_artifacts}/epic-{epic_num}-context.md`. If the file exists AND its mtime is newer than every source planning doc under `{planning_artifacts}` (PRD, architecture, UX, epics, brief), set `{epic_context_path}` to the candidate path and skip to sub-item **3d** (cache is valid).

**3c. Spawn compile-epic-context sub-agent.** Invoke sibling task `compile-epic-context.md` via the sub-agent mechanism, passing `{epic_num}` as input. The sub-agent writes the summary to `{implementation_artifacts}/epic-{epic_num}-context.md` and returns that path. Set `{epic_context_path}` to the returned path.

**3d. Verify output.** Read the first non-blank line of `{epic_context_path}`. Assert it starts with `# Epic {epic_num} Context:` (exact heading prefix, matching the compile-epic-context output contract). On mismatch: HALT, surface the assertion failure (path + actual first line), and instruct the operator to re-run or inspect.

**3e. Silent fall-through.** If `{epic_num}` could not be derived in 3a, leave `{epic_context_path}` unset and proceed. Mode A must continue to work for non-epic tech-specs with no user-visible error.

**Post-conditions for A.1:**

- `{epic_context_path}` is either unset (no epic) or points to a file whose first line matches `# Epic <N> Context:`.
- `{epic_num}` and `{story_num}` are set when derivable; otherwise unset.
- **Precedence reminder:** downstream steps that see `{epic_context_path}` set MUST ignore `{planning_context_files}` (Mode B, B.0) — the epic context already summarizes the same planning docs.

#### A.2 Previous story continuity

**Purpose:** When the current tech-spec belongs to an epic with prior completed stories, load a continuity summary (Code Map + Design Notes + Spec Change Log + Tasks) from the most recent `status: done` sibling spec so step-02/03 can reuse established patterns and honor prior constraints.

**Enter when:** Mode A is active AND `{epic_num}` is set AND `{story_num}` is set (both populated by A.1 sub-item 3a).
**Exit when:** `{continuity_context}` is either set to an assembled summary OR left unset (no candidates, or operator skipped the in-review fallback). In both cases, continue to the NEXT directive at the end of Mode A.

Execute these sub-items in order:

**3a. Glob candidate sibling specs.** List files matching `{implementation_artifacts}/spec-{epic_num}-*.md`. Exclude `{tech_spec_path}` itself from the result set. If zero candidates remain, skip to sub-item **3d** (no continuity available).

**3b. Filter by status and story number.** For each candidate, parse YAML frontmatter and extract `status` and `story` (derive story number via the same rules as A.1 sub-item 3a: `story:` field first, then filename `^\d+-(\d+)-`). Retain candidates where:

- `status == "done"` AND parsed story number is a positive integer strictly less than `{story_num}`.

From the retained set, select the candidate with the greatest story number. Ties (should not occur with one spec per story) resolve by most recent file mtime. If the retained set is empty, skip to sub-item **4** (in-review fallback).

**3c-i. Extract continuity sections by heading.** From the chosen spec file, extract the bodies of the following level-2 headings (match by exact heading text, case-sensitive, body spans until the next `## ` heading or EOF):

- `## Code Map`
- `## Design Notes`
- `## Spec Change Log`
- `## Tasks` (or `## Task List` if `## Tasks` is absent — prefer `## Tasks`)

Missing sections are recorded as empty strings; do not halt.

**3c-ii. Assemble `{continuity_context}`.** Concatenate the extracted sections in the order listed above, preserving their level-2 headings as section labels, separated by a single blank line between sections. Prefix the assembled string with a one-line provenance header:

```
> Continuity from spec-{E}-{S}-<slug>.md (status: done)
```

Set `{continuity_context}` to the assembled string.

**4. In-review fallback prompt.** Reached only when sub-item 3b yields zero `status: done` candidates. Re-run the same filter with `status == "in-review"` and the same story-number constraint. If the retained set is non-empty, select the greatest-story-number candidate and HALT with this prompt:

```
No prior `done` spec found in epic {epic_num}. An `in-review` spec exists:

  {chosen_spec_basename} (story {chosen_story_num})

Loading it as continuity context means relying on a not-yet-finalized spec.

[L] Load — proceed with in-review continuity
[S] Skip — continue without continuity context
```

- IF L: execute sub-items 3c-i and 3c-ii against the chosen in-review spec. Amend the provenance header to read `status: in-review` instead of `status: done`.
- IF S: leave `{continuity_context}` unset and proceed.
- ALWAYS halt and wait for user input before branching; do NOT auto-select.

**3d. Silent fall-through.** Reached when no candidates exist at all (3a empty) or no in-review candidates exist after a miss (4 empty). Leave `{continuity_context}` unset and proceed.

**Post-conditions for A.2:**

- `{continuity_context}` is either unset or contains the assembled sections with a provenance header naming the source spec and its status.
- No file writes occurred in A.2 — it is a pure read/scan step.

- **NEXT (after A.2 completes):** Read fully and follow: `{project-root}/_bmad/bmm/4-implementation/bmad-quick-dev/steps/step-03-execute.md`

**Mode B: Direct Instructions**

- User provided task description directly (e.g., `refactor src/foo.ts...`)
- Set `{execution_mode}` = "direct"
- Proceed to sub-section **B.0 Planning artifact scan** below before evaluating escalation.

#### B.0 Planning artifact scan

**Purpose:** In direct (freeform) mode, surface planning-artifact constraints that would otherwise require "guess from code alone" — without blindly loading everything. Selectively identify PRD / architecture / UX / epic / brief files relevant to the user's stated intent.

**Enter when:** `{execution_mode}` = "direct" AND `{planning_artifacts}` is resolvable (project config defines the planning directory).
**Exit when:** `{planning_context_files}` is either set to a non-empty array of selected paths OR left unset (silent fall-through when the directory is absent, empty, or yields no relevance match).

Execute these sub-items in order:

**2a. Enumerate candidate files.** Under `{planning_artifacts}`, list files whose basename (case-insensitive) matches any of the globs:

- `*prd*`
- `*architecture*`
- `*ux*`
- `*epic*`
- `*brief*`

If `{planning_artifacts}` does not exist or resolves to an empty match set, skip to sub-item **2c** (silent fall-through).

**2b. Score relevance against user intent and load selectively.** For each candidate, derive a relevance signal from the user's direct instructions using holistic judgment (not mechanical keyword matching):

- Read the file's title / first heading / first 20 lines.
- Judge whether its subject matter would materially inform the stated task.
- Select files with a positive signal. Deselect unrelated ones (e.g., a UX brief for an unrelated flow when the task is a backend refactor).

Push the absolute paths of selected files into `{planning_context_files}` (ordered by relevance, highest first). **Do not load the file bodies here** — downstream step-02 performs the content load when the array is set.

**Selective, not exhaustive:** if every candidate looks irrelevant, leave `{planning_context_files}` unset. Loading nothing is a valid outcome and preferable to polluting the context window.

**2c. Silent fall-through.** Reached when no candidates exist or all were deselected. Leave `{planning_context_files}` unset and proceed.

**Post-conditions for B.0:**

- `{planning_context_files}` is either unset or an array of at least one absolute path whose basename matches one of the five globs.
- No file bodies were loaded in step-01; B.0 is a path-selection step only.
- **Precedence reminder:** if Mode A ran elsewhere in this session and populated `{epic_context_path}`, downstream steps MUST ignore `{planning_context_files}`. B.0 does not attempt to reconcile with Mode A here — the precedence rule is enforced by the consumers (step-02 / step-03).

- **NEXT (after B.0 completes):** Evaluate the **One-Shot Route Decision** below. If the user declines one-shot, fall through to the **Escalation Threshold**.

---

## ONE-SHOT ROUTE DECISION (Mode B only)

**Purpose:** Offer a third path for trivial, low-risk changes that do not warrant the full Mode B pipeline (context-gathering → execute → self-check → adversarial-review → resolve-findings → spec-trace). One-shot short-circuits steps 02-06, implements inline, self-checks, and writes a `status: 'done'` spec trace in a single pass — mirroring upstream `bmad-quick-dev/step-oneshot.md`.

**Enter when:** `{execution_mode}` = "direct" AND B.0 has completed (`{planning_context_files}` either set or silently unset).
**Exit when:** the user selects a route; proceed accordingly.

Present:

```
**Select:** [P] Plan first (tech-spec)  [O] One-shot (trivial change)  [E] Execute directly
```

### Menu Handling Logic

- IF P: Direct user to `{quick_spec_workflow}`. **EXIT Quick Dev.**
- IF O: **NEXT:** Read fully and follow: `{project-root}/_bmad/bmm/4-implementation/bmad-quick-dev/steps/step-oneshot.md`. Skip step-02 through step-06 and step-07-spec-trace entirely — the one-shot step owns its own trace write-back.
- IF E: Fall through to the **Escalation Threshold** below. Do NOT skip escalation — `[E]` at this menu means "I want the standard pipeline, evaluate scope first".

### EXECUTION RULES

- ALWAYS halt and wait for user input after presenting the menu.
- ONLY proceed when the user makes a selection.
- When the user selects `[O]`, the one-shot route is mutually exclusive with `step-07-spec-trace.md` — only one of the two produces the spec trace for a given run.

---

## ESCALATION THRESHOLD (Mode B only)

Evaluate user input with minimal token usage (no file loading):

**Triggers escalation (if 2+ signals present):**

- Multiple components mentioned (dashboard + api + database)
- System-level language (platform, integration, architecture)
- Uncertainty about approach ("how should I", "best way to")
- Multi-layer scope (UI + backend + data together)
- Extended timeframe ("this week", "over the next few days")

**Reduces signal:**

- Simplicity markers ("just", "quickly", "fix", "bug", "typo", "simple")
- Single file/component focus
- Confident, specific request

Use holistic judgment, not mechanical keyword matching.

---

## ESCALATION HANDLING

### No Escalation (simple request)

Display: "**Select:** [P] Plan first (tech-spec) [E] Execute directly"

#### Menu Handling Logic:

- IF P: Direct user to `{quick_spec_workflow}`. **EXIT Quick Dev.**
- IF E: Ask for any additional guidance, then **NEXT:** Read fully and follow: `{project-root}/_bmad/bmm/4-implementation/bmad-quick-dev/steps/step-02-context-gathering.md`

#### EXECUTION RULES:

- ALWAYS halt and wait for user input after presenting menu
- ONLY proceed when user makes a selection

---

### Escalation Triggered - Level 0-2

Present: "This looks like a focused feature with multiple components."

Display:

**[P] Plan first (tech-spec)** (recommended)
**[W] Seems bigger than quick-dev** - Recommend the Full BMad Flow PRD Process
**[E] Execute directly**

#### Menu Handling Logic:

- IF P: Direct to `{quick_spec_workflow}`. **EXIT Quick Dev.**
- IF W: Direct user to run the PRD workflow instead. **EXIT Quick Dev.**
- IF E: Ask for guidance, then **NEXT:** Read fully and follow: `{project-root}/_bmad/bmm/4-implementation/bmad-quick-dev/steps/step-02-context-gathering.md`

#### EXECUTION RULES:

- ALWAYS halt and wait for user input after presenting menu
- ONLY proceed when user makes a selection

---

### Escalation Triggered - Level 3+

Present: "This sounds like platform/system work."

Display:

**[W] Start BMad Method** (recommended)
**[P] Plan first (tech-spec)** (lighter planning)
**[E] Execute directly** - feeling lucky

#### Menu Handling Logic:

- IF P: Direct to `{quick_spec_workflow}`. **EXIT Quick Dev.**
- IF W: Direct user to run the PRD workflow instead. **EXIT Quick Dev.**
- IF E: Ask for guidance, then **NEXT:** Read fully and follow: `{project-root}/_bmad/bmm/4-implementation/bmad-quick-dev/steps/step-02-context-gathering.md`

#### EXECUTION RULES:

- ALWAYS halt and wait for user input after presenting menu
- ONLY proceed when user makes a selection

---

## NEXT STEP DIRECTIVE

**CRITICAL:** When this step completes, explicitly state which step to load:

- Mode A (tech-spec, after A.1 Epic inference and A.2 Previous story continuity complete): "**NEXT:** read fully and follow: `{project-root}/_bmad/bmm/4-implementation/bmad-quick-dev/steps/step-03-execute.md`"
- Mode B (direct, [O] selected): "**NEXT:** Read fully and follow: `{project-root}/_bmad/bmm/4-implementation/bmad-quick-dev/steps/step-oneshot.md`"
- Mode B (direct, [E] selected): "**NEXT:** Read fully and follow: `{project-root}/_bmad/bmm/4-implementation/bmad-quick-dev/steps/step-02-context-gathering.md`"
- Escalation ([P] or [W]): "**EXITING Quick Dev.** Follow the directed workflow."

---

## SUCCESS METRICS

- `{baseline_commit}` captured and stored
- `{execution_mode}` determined ("tech-spec" or "direct")
- `{tech_spec_path}` set if Mode A
- A.1 Epic inference executed when Mode A: `{epic_context_path}` set to a verified summary OR left unset via silent fall-through
- A.2 Previous story continuity executed when Mode A with an epic: `{continuity_context}` assembled from prior done spec, operator-resolved via in-review fallback, or left unset via silent fall-through
- B.0 Planning artifact scan executed when Mode B: `{planning_context_files}` set to the selective relevance subset OR left unset via silent fall-through
- Project context loaded if exists
- Escalation evaluated appropriately (Mode B)
- Explicit NEXT directive provided

## FAILURE MODES

- Proceeding without capturing baseline commit
- Not setting execution_mode variable
- Loading step-02 when Mode A (tech-spec provided)
- Attempting to "return" after escalation instead of EXIT
- No explicit NEXT directive at step completion
