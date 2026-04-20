# Initiative Routing Workflow

<critical>The workflow engine is governed by: {project-root}/_bmad/core/module.yaml</critical>
<critical>You MUST have already loaded and resolved: {project-root}/_bmad/compass/planning/bmad-compass-initiative-routing/workflow.yaml</critical>
<critical>Communicate all responses in {communication_language}</critical>

## Goal

Turn an approved workspace or orchestration phase into explicit concurrent repo-targeted initiative workstreams without writing repo-local delivery artifacts into the wrong repo.

Use this workflow only when the active phase in `{phase_state_file}` has:

- `execution_scope: workspace`, or
- `execution_scope: orchestration`

## Step 1: Load Routing Inputs

Read:

- `{planning_repositories_file}`
- `{phase_snapshot_file}`
- `{phase_state_file}`
- the active phase entry from `roadmap.yaml`

Confirm:

- `repo_targets` is populated
- the active phase is approved and active
- each repo target exists in `{planning_repositories_file}`

If the active phase is `execution_scope: repo`, stop and recommend local repo execution instead of initiative routing.

## Step 2: Build Initiative Workstreams

For each routed initiative or workstream, derive:

- stable `initiative_id`
- title
- `primary_repo_id`
- `repo_targets`
- dependency edges
- overlap domains
- integration gates
- blocked-by rules if another initiative already touches the same repo, interface, or release boundary

Keep initiative folders concise and routing-oriented. Do not create PRDs, architecture docs, or story files here.

## Step 3: Seed Initiative Folders

For each initiative:

1. Create `{planning_initiatives_root}/{initiative_id}/` if missing.
2. Create or update:
   - `{planning_initiatives_root}/{initiative_id}/phase.md`
   - `{planning_initiatives_root}/{initiative_id}/phase-state.yaml`
3. Copy the active orchestration scope, repo targets, dependencies, and gates into those files.

These initiative phase files are routing and coordination artifacts, not replacements for repo-local planning in target repos.

## Step 4: Update Initiative Index

Update `{planning_initiative_index_file}` with:

- repo id and repo type for the current orchestration root
- active initiatives
- blocked initiatives
- overlap records
- integration gates
- `last_updated`

`initiative-index.yaml` is the machine authority for concurrent initiative routing.

## Step 5: Update Parent Phase State

Update `{phase_state_file}` with:

- `workflow_status.initiative_routing: complete`
- `repo_targets`
- `repo_workstreams`
- `blocked_workstreams`
- `integration_gates`
- `routing_decisions`
- `next_checkpoint`

Routing checkpoint rules:

- if repo-local delivery can begin immediately, set `next_checkpoint: repo_phase_sync`
- if overlap or integration gates must be cleared first, set `next_checkpoint: routing_gate_review`

## Step 6: Emit Routing Report

Write `{default_output_file}` including:

- active orchestration phase
- routed initiatives and target repos
- overlap gates
- blocked workstreams
- required repo-local next steps
- recommended next action for each target repo: run `/bmad-bmm-phase-sync` in the authoritative repo root
