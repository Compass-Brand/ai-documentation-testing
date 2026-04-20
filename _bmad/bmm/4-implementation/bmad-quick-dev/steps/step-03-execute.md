---
name: 'step-03-execute'
description: 'Execute implementation - iterate through tasks, write code, run tests'

nextStepFile: './step-04-self-check.md'
---

# Step 3: Execute Implementation

**Goal:** Implement all tasks, write tests, follow patterns, handle errors.

**Critical:** Continue through ALL tasks without stopping for milestones.

---

## AVAILABLE STATE

From previous steps:

- `{baseline_commit}` - Git HEAD at workflow start
- `{execution_mode}` - "tech-spec" or "direct"
- `{tech_spec_path}` - Tech-spec file (if Mode A)
- `{project_context}` - Project patterns (if exists)
- `{epic_context_path}` - Compiled epic context file (Mode A with epic; unset otherwise)
- `{continuity_context}` - Prior-story continuity summary (Mode A with epic + done predecessor; unset otherwise)
- `{planning_context_files}` - Planning artifacts selectively loaded by step-01 (Mode B). **Precedence:** if `{epic_context_path}` is set, IGNORE this array — step-02 will have already resolved the precedence and the epic context supersedes raw planning docs.

From context:

- Mode A: Tasks and AC extracted from tech-spec
- Mode B: Tasks and AC from step-02 mental plan

---

## EXECUTION LOOP

For each task:

### 1. Load Context

- Read files relevant to this task
- Review patterns from project-context or observed code
- Understand dependencies
- **If `{epic_context_path}` is set:** read it once and keep its Requirements & Constraints + Technical Decisions in working context for every task — it is the binding epic-level reference.
- **If `{continuity_context}` is set:** read it once and keep it in working context for every task. It contains four named sections assembled from the most recent `status: done` sibling spec:
  - **Code Map** — reuse the module / file / symbol patterns the prior story established; align with its structure instead of introducing a parallel one.
  - **Design Notes** — honor the recorded constraints (invariants, trade-offs, decisions) as binding unless the current tech-spec explicitly overrides them.
  - **Spec Change Log** — do not reintroduce anything already resolved; treat entries as closed decisions.
  - **Tasks** — cross-reference against the current task list so you don't duplicate work that previously shipped.

### 2. Implement

- Write code following existing patterns
- Handle errors appropriately
- Follow conventions observed in codebase
- Add appropriate comments where non-obvious

### 3. Test

- Write tests if appropriate for the change
- Run existing tests to catch regressions
- Verify the specific AC for this task

### 4. Mark Complete

- Check off task: `- [x] Task N`
- Continue to next task immediately

---

## HALT CONDITIONS

**HALT and request guidance if:**

- 3 consecutive failures on same task
- Tests fail and fix is not obvious
- Blocking dependency discovered
- Ambiguity that requires user decision

**Do NOT halt for:**

- Minor issues that can be noted and continued
- Warnings that don't block functionality
- Style preferences (follow existing patterns)

---

## CONTINUOUS EXECUTION

**Critical:** Do not stop between tasks for approval.

- Execute all tasks in sequence
- Only halt for blocking issues
- Tests failing = fix before continuing
- Track all completed work for self-check

---

## NEXT STEP

When ALL tasks are complete (or halted on blocker), read fully and follow: `{project-root}/_bmad/bmm/4-implementation/bmad-quick-dev/steps/step-04-self-check.md`.

---

## SUCCESS METRICS

- All tasks attempted
- Code follows existing patterns
- Error handling appropriate
- Tests written where appropriate
- Tests passing
- No unnecessary halts

## FAILURE MODES

- Stopping for approval between tasks
- Ignoring existing patterns
- Not running tests after changes
- Giving up after first failure
- Not following project-context rules (if exists)
