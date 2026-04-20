---
name: phase-sync
description: 'Select and sync the active roadmap slice in planning/current/phase.md and phase-state.yaml. Use when the user says "sync phase", "select the next phase", "update phase goals", or "check phase metadata".'
---

# Phase Sync Workflow

**Goal:** Keep the active phase human-readable and machine-readable state current before and during delivery work.

**Your Role:** You are a planning facilitator ensuring the current roadmap slice is explicit, scoped, and execution-ready.

## CONFIGURATION

Load config from `{project-root}/_bmad/bmm/module.yaml` and resolve:
- `project_name`, `user_name`
- `communication_language`, `document_output_language`
- `planning_root`, `planning_current`, `planning_roadmap`
- `planning_repositories_file`, `planning_initiative_index_file`
- `phase_snapshot_file`, `phase_state_file`
- `date` as a system-generated value (`YYYY-MM-DD`)

## EXECUTION

1. Ensure `{planning_current}` exists.
2. Read `{planning_roadmap}/roadmap.md` and `{planning_roadmap}/roadmap.yaml` first. Confirm:
   - the active roadmap slice or phase id
   - the execution scope
   - any repo targets
   - why this slice is next
   - dependencies carried forward from prior phases
   - what is explicitly out of scope
   - any existing Beads parent or phase issue ids already associated with the slice
3. Derive lane decisions from the roadmap scope before creating or updating state files.

   **WDS mode** — evaluate whether the active slice involves user-facing interface work:
   - If the roadmap slice explicitly targets UI, UX, frontend, or user-interaction surfaces → `conditional` (WDS will activate when PRD confirms UX needs).
   - If the slice is backend-only, infrastructure, tooling, CLI, or library work with no user-facing surfaces → `skipped`.
   - If the roadmap does not clearly indicate either → set `conditional` and mark as **assumed** in the phase brief.

   **Security mode** — evaluate using the criteria in the sibling `security-activation.md` governance workflow:
   - If the scope involves authentication, authorization, sensitive data handling, public endpoints, trust boundary changes, secrets handling, or regulatory requirements → `auto` with `security_active: true`.
   - If none of those conditions apply → `auto` with `security_active: false` (security lane remains available but inactive).
   - If the roadmap scope is ambiguous on security relevance → set `auto` with `security_active: false` and mark as **assumed** in the phase brief.

   **Storytelling mode** — evaluate whether the roadmap or product brief references narrative, brand storytelling, or separate storytelling artifacts:
   - If the roadmap explicitly calls for storytelling or narrative deliverables → `separate`.
   - Otherwise → `off`.

   Record the derivation source for each decision (e.g., "roadmap slice scope: backend tooling" or "roadmap mentions public API endpoints") so the rationale is traceable. When a decision cannot be derived from the roadmap, mark it as an assumption and surface it in the phase brief under **Risks And Assumptions** so the user can confirm or override.

4. If `{phase_snapshot_file}` does not exist, create it with this structure:

```md
# Current Phase

## Status
- Phase ID:
- Title:
- Status: active
- Execution Scope:
- Primary Repo:
- Owner: {{user_name}}
- Start Date:
- Target Completion Date:
- Last Updated: {{date}}

## Why This Phase Now
-

## Objective
-

## Scope

### In Scope
-

### Out Of Scope
-

## Dependencies And Carry-Over
- Dependencies:
- Carry-Over:

## Repo Targets
-

## Required Source Artifacts
- `planning/roadmap/roadmap.md`
- `planning/roadmap/roadmap.yaml`

## Planned Deliverables
-

## Exit Criteria
-

## Lane Decisions
- WDS Mode: {{derived_wds_mode}} — {{wds_derivation_source}}
- Security Mode: {{derived_security_mode}} (active: {{derived_security_active}}) — {{security_derivation_source}}
- Storytelling Mode: {{derived_storytelling_mode}} — {{storytelling_derivation_source}}

## Risks And Assumptions
- Risks:
- Assumptions:
  - {{list any lane decisions marked as assumed, with the default value and why it could not be derived}}

## Notes And Decisions
-
```

5. If `{phase_state_file}` does not exist, create it with this baseline structure. Replace the `lane_decisions` placeholder values with the decisions derived in step 3:

```yaml
version: 1
phase_id: ""
slug: ""
title: ""
status: planned
owner: "{{user_name}}"
last_updated: "{{date}}"
repo_id: ""
repo_type: delivery
execution_scope: repo
primary_repo_id: ""
repositories_ref: ../repositories.yaml
initiative_index_ref: initiative-index.yaml
upstream_repo_id: ""
upstream_initiative_id: ""
upstream_phase_ref: ""
roadmap_ref: ../roadmap/roadmap.yaml # relative to phase-state.yaml in planning/current/
phase_doc: phase.md
in_scope: []
out_of_scope: []
dependencies: []
repo_targets: []
repo_workstreams: []
blocked_workstreams: []
integration_gates: []
routing_decisions: []
lane_decisions:
  storytelling_mode: "{{derived_storytelling_mode}}" # derived from roadmap scope — see step 3
  wds_mode: "{{derived_wds_mode}}" # derived from roadmap scope — see step 3
  security_mode: "{{derived_security_mode}}" # derived from roadmap scope — see step 3
  security_active: "{{derived_security_active}}" # derived from roadmap scope — see step 3
lane_outcomes:
  storytelling: not_applicable
  wds: not_applicable
  security: not_applicable
approval_markers:
  roadmap:
    status: not_requested
    requested_revision: ""
    approved_revision: ""
    reviewed_by: ""
    reviewed_at: ""
  prd:
    status: not_requested
    requested_revision: ""
    approved_revision: ""
    reviewed_by: ""
    reviewed_at: ""
  architecture:
    status: not_requested
    requested_revision: ""
    approved_revision: ""
    reviewed_by: ""
    reviewed_at: ""
  readiness:
    status: not_requested
    requested_revision: ""
    approved_revision: ""
    reviewed_by: ""
    reviewed_at: ""
workflow_status:
  phase_sync: in_progress
  initiative_routing: not_started
  detailed_analysis: not_started
  planning_experience: not_started
  solutioning: not_started
  implementation: not_started
  release_gate: not_started
  closeout: not_started
review_artifacts:
  roadmap_gate: ""
  prd_gate: ""
  architecture_gate: ""
  readiness_gate: ""
beads:
  parent_issue_id: ""
  phase_issue_id: ""
  active_epic_issue_id: ""
  active_story_issue_id: ""
  follow_up_issue_ids: []
  last_synced_at: ""
artifact_paths:
  project_context:
    current: ""
    canonical: ""
    draft: ""
  brief:
    current: ""
    canonical: ""
    draft: ""
  prd:
    current: ""
    canonical: ""
    draft: ""
  ux_design:
    current: ""
    canonical: ""
    draft: ""
  architecture:
    current: ""
    canonical: ""
    draft: ""
  epics:
    current: ""
    canonical: ""
    draft: ""
  stories:
    current: ""
    canonical: ""
    draft: ""
  testing:
    current: ""
    canonical: ""
    draft: ""
  evidence:
    current: ""
    canonical: ""
    draft: ""
artifact_revisions:
  brief:
    current: ""
    approved: ""
    state: not_started
    updated_at: ""
  prd:
    current: ""
    approved: ""
    state: not_started
    updated_at: ""
  ux_design:
    current: ""
    approved: ""
    state: not_started
    updated_at: ""
  architecture:
    current: ""
    approved: ""
    state: not_started
    updated_at: ""
  epics:
    current: ""
    approved: ""
    state: not_started
    updated_at: ""
  stories:
    current: ""
    approved: ""
    state: not_started
    updated_at: ""
  readiness:
    current: ""
    approved: ""
    state: not_started
    updated_at: ""
automation_state:
  last_completed_step: ""
  last_completed_checkpoint: ""
  pending_approval: null
  stale_outputs: []
  last_failure_report: ""
  derived_from: {}
open_risks: []
next_checkpoint: detailed_analysis
```

6. Update `{phase_snapshot_file}` in place with user-provided or roadmap-derived changes:
   - phase identity
   - why this phase is active now
   - objective
   - in-scope and out-of-scope boundaries
   - dependencies and carry-over
   - required source artifacts
   - planned deliverables
   - exit criteria
   - lane decisions with derivation sources (from step 3)
   - risks, assumptions, and important notes (including any assumed lane decisions)
7. Update `{phase_state_file}` in place with matching machine-readable values:
   - `phase_id`, `slug`, `title`, `status`, `owner`, `last_updated`
   - `execution_scope`, `primary_repo_id`, and any `repo_targets`
   - `in_scope`, `out_of_scope`, `dependencies`
   - `beads.parent_issue_id` and `beads.phase_issue_id` when they are already known or are created during phase activation
   - `workflow_status.phase_sync = complete`
   - `next_checkpoint = initiative_routing` when execution scope is `workspace` or `orchestration`; otherwise `detailed_analysis`
   - `lane_decisions` values derived in step 3 — never leave these as template defaults
8. Reconcile Beads tracking before detailed analysis starts:
   - if a parent initiative issue already exists for orchestration scope, record it in `beads.parent_issue_id`
   - confirm or create the Beads issue that represents this active phase and store it in `beads.phase_issue_id`
   - when the phase is being activated for work now, mark that Beads issue `in_progress`
   - update `beads.last_synced_at` when issue reconciliation or `bd sync` succeeds
9. Always set:
   - `Status: active` in `{phase_snapshot_file}`
   - `status: active` in `{phase_state_file}`
   - `Last Updated: {{date}}` in `{phase_snapshot_file}`
   - `last_updated: {{date}}` in `{phase_state_file}`
10. Confirm saved paths:
   - `{phase_snapshot_file}`
   - `{phase_state_file}`

## OUTPUT RULES

- Keep date format as `YYYY-MM-DD`.
- `phase.md` is the human brief; `phase-state.yaml` is the machine control surface.
- `phase-state.yaml` should also carry the Beads issue references for the active phase.
- Lane decisions in `phase-state.yaml` must always reflect the derivation from step 3. Never silently default to template values without evaluating the roadmap scope.
- When a lane decision is assumed rather than derived, the phase brief must list it under **Risks And Assumptions** so the user can confirm or override before downstream workflows consume it.
- Do not write active phase metadata outside `{phase_snapshot_file}` and `{phase_state_file}`.
- Do not archive in this workflow; use `phase-closeout`.
