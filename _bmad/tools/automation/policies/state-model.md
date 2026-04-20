# Automation State Model

## Purpose

Define the canonical state model for Compass BMAD automation wrappers so approvals, resume behavior, stale-output handling, and draft promotion are deterministic.

## Core Rules

1. Automation wraps the canonical BMAD workflow. It does not replace it.
2. The state model is BMAD artifacts plus `bd`, not TodoWrite.
3. Human-readable state and machine-readable state must never compete for authority.
4. Draft artifacts must remain draft until the relevant approval checkpoint is accepted.
5. `auto-plan-report.md` and other reviewer-facing markdown reports are never resume sources.
6. `bd` is authoritative for task and issue lifecycle; BMAD state files remain authoritative for planning and automation state.

## Authority Order

- `roadmap.yaml` is the machine source of truth for roadmap state.
- `roadmap.md` is the human-readable summary of approved roadmap state.
- `phase-state.yaml` is the machine source of truth for the active phase after `Phase Sync`.
- `phase.md` is the human-readable brief for the active phase.
- `auto-plan-state.yaml` is the machine source of truth for `auto-plan` runtime state before and after `Phase Sync`.

If files disagree:

- `roadmap.yaml` wins over `roadmap.md`
- `phase-state.yaml` wins over `phase.md`
- `auto-plan-state.yaml` wins over reviewer-facing draft gate documents

## Runtime State Files

### `auto-plan-state.yaml`

Required machine runtime file for `auto-plan`. It must carry:

- command identity
- phase id
- run status
- lane decisions and lane outcomes
- approval markers
- review artifact paths
- beads issue references
- artifact paths
- artifact revisions
- automation state
- workflow status
- next checkpoint
- draft artifact tracking

### `phase-state.yaml`

Canonical machine state for the active phase once `Phase Sync` has run. It mirrors the live phase and is updated at each accepted checkpoint.

## Required `bd` Tracking Model

`phase-state.yaml` and `auto-plan-state.yaml` should both include a `beads` object with:

- `parent_issue_id`
- `phase_issue_id`
- `active_epic_issue_id`
- `active_story_issue_id`
- `follow_up_issue_ids`
- `last_synced_at`

Rules:

- `parent_issue_id` is the parent initiative or orchestration issue when the current work is routed from a workspace or parent repo.
- `phase_issue_id` is the active Beads issue for the current roadmap slice in the current repo scope.
- `active_epic_issue_id` is set when epic execution is approved to start.
- `active_story_issue_id` is set when a story is claimed for implementation.
- `follow_up_issue_ids` records issues created for discovered blockers, review findings, carry-over, or deferred work.
- `last_synced_at` records the last successful `bd sync` or explicit issue reconciliation checkpoint.
- These fields are references into Beads, not a replacement for Beads. Status, assignee, dependency, and closure truth stay in `bd`.

## Required Approval Model

Each gate is an object, not a scalar. Required fields:

- `status`
- `requested_revision`
- `approved_revision`
- `reviewed_by`
- `reviewed_at`

Supported gates:

- `roadmap`
- `prd`
- `architecture`
- `readiness`

Allowed statuses:

- `not_requested`
- `pending`
- `approved`
- `rejected`

## Required Automation State Model

`automation_state` must include:

- `last_completed_step`
- `last_completed_checkpoint`
- `pending_approval`
- `stale_outputs`
- `last_failure_report`
- `derived_from`

### `pending_approval`

Must be either `null` or an object with:

- `gate`
- `requested_revision`
- `review_artifact`
- `requested_at`

Allowed gate values:

- `roadmap`
- `prd`
- `architecture`
- `readiness`

### `stale_outputs`

Must be a structured array. Each entry must include:

- `artifact_key`
- `path`
- `reason`
- `caused_by_gate`
- `caused_by_revision`
- `stale_at`

Allowed reasons:

- `roadmap_changed`
- `prd_changed`
- `architecture_changed`
- `approval_rejected`
- `manual_reopen`

### `derived_from`

Must be a keyed map. Each entry must include:

- `artifact_revision`
- `source_revisions`

This is the contract that tells automation whether an output still matches its upstream inputs.

## Artifact Tracking Rules

### `artifact_paths`

Each artifact entry must be an object with:

- `current`
- `canonical`
- `draft`

### `artifact_revisions`

Each artifact entry must be an object with:

- `current`
- `approved`
- `state`
- `updated_at`

Allowed states:

- `not_started`
- `draft`
- `approved`
- `superseded`

## Draft Artifact Rules

Draft outputs are not executable work products. They may be reviewed, revised, invalidated, or promoted, but they must not be consumed by downstream execution workflows as if they were approved.

At minimum, `auto-plan` draft artifacts must track:

- roadmap proposal
- PRD gate package
- architecture gate package
- draft epics
- draft stories
- readiness gate package

Each draft artifact entry must include:

- `path`
- `revision`
- `derived_from`
- `status`
- `supersedes`

## Rejection And Invalidation Rules

- Rejected roadmap changes must not mutate canonical roadmap state.
- Rejected PRD changes must invalidate WDS outputs and every downstream artifact derived from that PRD revision.
- Rejected architecture changes must invalidate security review, test design, draft epics/stories, and readiness outputs tied to that architecture revision.
- Rejected readiness must keep epics, stories, and readiness outputs in draft locations.
- Resume must regenerate every stale output before continuing.

## Hard Stops

Automation must stop and require human approval when:

- roadmap activation or major roadmap reordering is pending
- PRD approval is pending
- architecture approval is pending
- readiness approval is pending
- a blocking risk affects the current checkpoint
- a risky story change triggers a hard-stop category

## `bd` Integration Rule

- `bd` is the issue and task system of record for automation-related work tracking.
- Automation should verify `bd` availability before execution, claim active work with `bd update ... --status in_progress`, create follow-up work with `bd create`, close completed work with `bd close`, and finish stateful runs with `bd sync`.
- Active phases, epics, and implementation stories should have corresponding Beads issue references recorded in the runtime or phase state when the workflow reaches that layer.
- TodoWrite is explicitly rejected as the state model for Compass automation.
