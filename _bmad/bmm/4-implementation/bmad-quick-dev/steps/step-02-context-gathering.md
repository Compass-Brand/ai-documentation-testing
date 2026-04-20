---
name: 'step-02-context-gathering'
description: 'Quick context gathering for direct mode - identify files, patterns, dependencies'

nextStepFile: './step-03-execute.md'
---

# Step 2: Context Gathering (Direct Mode)

**Goal:** Quickly gather context for direct instructions - files, patterns, dependencies.

**Note:** This step only runs for Mode B (direct instructions). If `{execution_mode}` is "tech-spec", this step was skipped.

---

## AVAILABLE STATE

From step-01:

- `{baseline_commit}` - Git HEAD at workflow start
- `{execution_mode}` - Should be "direct"
- `{project_context}` - Loaded if exists
- `{epic_context_path}` - Compiled epic context file (Mode A only; normally unset here since this step runs in Mode B, but respected if carried over)
- `{continuity_context}` - Prior-story continuity summary (Mode A only; same caveat as above)
- `{planning_context_files}` - Planning artifacts selectively loaded by step-01 B.0 (Mode B)

---

## EXECUTION SEQUENCE

### 0. Load Context

Before identifying files, incorporate any pre-loaded context from step-01:

**Precedence rule (MANDATORY):** If `{epic_context_path}` is set, READ that file and use it as the planning-artifact reference. IGNORE `{planning_context_files}` entirely in this case — the epic context already summarizes the same planning docs (PRD / architecture / UX / epics / brief) and re-loading would duplicate content.

- **IF `{epic_context_path}` is set:**
  - Read the file at `{epic_context_path}`.
  - Treat its Goal / Requirements & Constraints / Technical Decisions / UX sections as the binding planning reference for this run.
  - Do NOT load `{planning_context_files}`, even if that array is non-empty.
- **ELSE IF `{planning_context_files}` is set (Mode B common case):**
  - For each path in `{planning_context_files}`, read the file body and extract the constraints / decisions / requirements relevant to the user's direct instructions.
  - Fold those constraints into the mental plan in step 4 below.
- **ELSE:** no pre-loaded planning context; proceed with code-only gathering.

If `{continuity_context}` is set, treat it as authoritative prior-story guidance: reuse patterns from its Code Map, honor constraints from its Design Notes, and align tasks with its Spec Change Log.

### 1. Identify Files to Modify

Based on user's direct instructions:

- Search for relevant files using glob/grep
- Identify the specific files that need changes
- Note file locations and purposes

### 2. Find Relevant Patterns

Examine the identified files and their surroundings:

- Code style and conventions used
- Existing patterns for similar functionality
- Import/export patterns
- Error handling approaches
- Test patterns (if tests exist nearby)

**If `{continuity_context}` is set**, consult it first as an authoritative prior-story source before inferring patterns from code:

- **Code Map section** — reuse the module / file / symbol patterns it names; prefer aligning with the prior story's structure over introducing a parallel one.
- **Design Notes section** — honor the constraints recorded there (invariants, trade-offs, decisions). Treat them as binding unless the current spec explicitly overrides them.
- **Spec Change Log section** — do not reintroduce anything already resolved; treat entries as closed decisions.
- **Tasks section** — cross-reference with the current task list to avoid duplicating work already completed.

Code-derived patterns supplement, not replace, continuity guidance when the two conflict.

### 3. Note Dependencies

Identify:

- External libraries used
- Internal module dependencies
- Configuration files that may need updates
- Related files that might be affected

### 4. Create Mental Plan

Synthesize gathered context into:

- List of tasks to complete
- Acceptance criteria (inferred from user request)
- Order of operations
- Files to touch

---

## PRESENT PLAN

Display to user:

```
**Context Gathered:**

**Files to modify:**
- {list files}

**Patterns identified:**
- {key patterns}

**Plan:**
1. {task 1}
2. {task 2}
...

**Inferred AC:**
- {acceptance criteria}

Ready to execute? (y/n/adjust)
```

- **y:** Proceed to execution
- **n:** Gather more context or clarify
- **adjust:** Modify the plan based on feedback

---

## NEXT STEP DIRECTIVE

**CRITICAL:** When user confirms ready, explicitly state:

- **y:** "**NEXT:** Read fully and follow: `{project-root}/_bmad/bmm/4-implementation/bmad-quick-dev/steps/step-03-execute.md`"
- **n/adjust:** Continue gathering context, then re-present plan

---

## SUCCESS METRICS

- Files to modify identified
- Relevant patterns documented
- Dependencies noted
- Mental plan created with tasks and AC
- User confirmed readiness to proceed

## FAILURE MODES

- Executing this step when Mode A (tech-spec)
- Proceeding without identifying files to modify
- Not presenting plan for user confirmation
- Missing obvious patterns in existing code
