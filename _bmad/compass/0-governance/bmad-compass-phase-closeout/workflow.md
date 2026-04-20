---
name: phase-closeout
description: 'Close the active phase and archive artifacts into previous/ with lessons capture and roadmap updates. Use when the user says "close this phase" or "run phase closeout".'
---

# Phase Closeout Workflow

**Goal:** Close the active phase by archiving current artifacts, capturing lessons, updating roadmap state, and preparing the next phase scaffold.

**Your Role:** You are a sprint or phase facilitator executing closeout rigorously using Compass planning conventions.

## CONFIGURATION

Load config from `{project-root}/_bmad/bmm/module.yaml` and resolve:
- `planning_root`, `planning_current`, `planning_previous`, `planning_lessons`, `planning_roadmap`
- `planning_initiative_index_file`
- `phase_snapshot_file`, `phase_state_file`, `current_evidence_dir`
- `user_name`, `communication_language`
- `date` as a system-generated value (`YYYY-MM-DD`)

## PREREQUISITES

Verify active-phase artifacts exist (or explicitly confirm intentional gaps):
- `{planning_current}/planning/prd/`
- `{planning_current}/planning/brief/`
- `{planning_current}/planning/ux-design/`
- `{planning_current}/planning/architecture/`
- `{planning_current}/planning/epics/`
- `{planning_current}/implementation/stories/`
- `{planning_current}/implementation/evidence/`
- `{planning_current}/testing/`
- `{planning_current}/research/`
- `{phase_snapshot_file}`
- `{phase_state_file}`
- `{planning_initiative_index_file}` when the closed phase operated in workspace or orchestration scope

## EXECUTION

1. Read `{phase_snapshot_file}` and `{phase_state_file}` and extract:
   - phase slug (lowercase kebab-case)
   - completion date (`YYYY-MM-DD`, default `{{date}}` if not provided)
   - open risks, outstanding decisions, and closeout status
   - Beads parent issue, phase issue, and follow-up issue references
2. Update `{phase_state_file}` first with closeout-state values before archival:
   - `status: closed`
   - `workflow_status.closeout: complete`
   - `next_checkpoint: ""`
   - `last_updated: {{date}}`
3. Update `{phase_snapshot_file}` second with matching human-readable closeout notes:
   - `Status: closed`
   - `Last Updated: {{date}}`
   - final notes, accepted residual risks, and roadmap follow-up summary
4. Create archive targets:
   - `{planning_previous}/{phase_slug}-{completion_date}/`
   - `{planning_lessons}/{phase_slug}-{completion_date}/`
5. Write a closeout report to:
   - `{current_evidence_dir}/phase-closeout-{completion_date}.md`
   Include:
   - completed scope
   - open or accepted residual risks
   - deltas vs goals
   - roadmap follow-up
   - Beads closure and carry-over actions
   - archival actions taken
6. Reconcile Beads tracking:
   - close the Beads phase issue when the phase is complete
   - create or preserve Beads follow-up issues for deferred, requeued, or blocked work
   - keep parent initiative issues open when other child workstreams remain active
   - update `beads.follow_up_issue_ids` and `beads.last_synced_at`
   - run `bd sync` after issue updates are complete
7. Update roadmap state:
   - update `{planning_roadmap}/roadmap.yaml` first with completed, deferred, or requeued state
   - update `{planning_roadmap}/roadmap.md` second to match the approved roadmap state
8. If the phase used workspace or orchestration scope, update `{planning_initiative_index_file}` to archive or remove closed initiative workstreams and preserve any still-active blocked workstreams.
9. Move all active phase artifacts from `{planning_current}/` into:
   - `{planning_previous}/{phase_slug}-{completion_date}/`
10. Create lessons file:
   - `{planning_lessons}/{phase_slug}-{completion_date}/lessons.md`
   With sections:
   - what worked
   - what failed
   - what to change next phase
   - reusable patterns and guardrails
11. If roadmap-level artifacts were superseded, move them to dated archive lanes:
   - `{planning_roadmap}/archive/brainstorming/{completion_date}/`
   - `{planning_roadmap}/archive/research/market/{completion_date}/`
   - `{planning_roadmap}/archive/research/domain/{completion_date}/`
   - `{planning_roadmap}/archive/research/technical/{completion_date}/`
   - `{planning_roadmap}/archive/strategy/{completion_date}/`
   - `{planning_roadmap}/archive/storytelling/{completion_date}/`
   - `{planning_roadmap}/archive/product-brief/{completion_date}/`
12. Recreate a clean current scaffold:
   - `brainstorming/detailed/`
   - `research/project-context/`
   - `research/market/`
   - `research/domain/`
   - `research/technical/`
   - `research/strategy/`
   - `research/implementation/`
   - `planning/prd/`
   - `planning/brief/`
   - `planning/ux-design/`
   - `planning/architecture/`
   - `planning/epics/draft/`
   - `implementation/stories/draft/`
   - `implementation/evidence/`
   - `implementation/retrospectives/`
   - `testing/test-design/`
   - `testing/automation/`
   - `testing/reviews/`
   - `testing/gates/draft/`
   - `testing/gates/draft/security/`
   - `testing/gates/security/readiness/`
   - `testing/gates/security/release/`
   - `initiatives/`
13. Initialize new `{phase_snapshot_file}` with placeholder content for the next slice, but keep it non-active until the next `phase-sync`.
14. Initialize new `{phase_state_file}` with `status: planned`, reset workflow status to the start of the phase loop, clear the active Beads issue refs, and leave activation to the next `phase-sync`.

## OUTPUT RULES

- Never use relative dates in folder or file names.
- Do not leave closed-phase artifacts in `{planning_current}`.
- Keep phase snapshot naming strictly: `{phase_slug}-{YYYY-MM-DD}`.
- Closeout write order is:
  1. update `{phase_state_file}`
  2. update `{phase_snapshot_file}`
  3. update `roadmap.yaml`
  4. update `roadmap.md`
