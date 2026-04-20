# Workspace Bootstrap Workflow

<critical>The workflow engine is governed by: {project-root}/_bmad/core/module.yaml</critical>
<critical>You MUST have already loaded and resolved: {project-root}/_bmad/compass/planning/bmad-compass-workspace-bootstrap/workflow.yaml</critical>
<critical>Communicate all responses in {communication_language}</critical>

## Goal

Bootstrap selected repos from a workspace or orchestration root into the Compass BMAD structure without manually editing each repo.

Default behavior:

- initialize planning and docs
- use targeted repo selection, not global fan-out
- preserve existing material through the safe migration rules from `init-planning` and `init-docs`

This workflow is the top-level safety-net command. It must reuse existing initialization semantics instead of inventing a second bootstrap system.

## Step 1: Validate Current Root Scope

Read:

- `{planning_repositories_file}` when it exists
- `.gitmodules` in the current repo root when present
- `{phase_snapshot_file}` and `{phase_state_file}` when present
- confirm `bd` is available before fan-out so issue tracking can be reconciled during bootstrap reports

Determine whether the current repo is:

- `workspace`
- `orchestration`
- `delivery`

Rules:

- if the current repo is `delivery`, stop and recommend:
  - `/bmad-bmm-init-planning`
  - `/bmad-bmm-init-docs`
- only continue when the current repo is `workspace` or `orchestration`

## Step 2: Normalize the Current Root First

Before any child-repo fan-out:

1. Ensure the current root has the live planning control surface.
2. Reuse `init-planning` behavior for the current root:
   - scaffold the planning structure if missing
   - preserve existing authority files if already present
   - create `repositories.yaml` and `initiative-index.yaml` when the current root coordinates child repos
3. If docs initialization is requested for the current root, reuse `init-docs` behavior after planning is in place.

Do not skip current-root normalization. Child fan-out depends on it.

## Step 3: Refresh Repository Topology

Refresh topology before selecting targets.

Read:

- approved `{planning_repositories_file}` when present
- `.gitmodules` from the current repo root

Compare the approved registry with the discovered repo topology.

Write `{topology_proposal_file}` before changing `{planning_repositories_file}`.

Include:

- discovered repo roots
- missing registry entries
- removed or no-longer-present entries
- changed paths
- changed parent-child relationships
- proposed repo types
- any ambiguity that needs approval

Approval rules:

- do not silently update `{planning_repositories_file}`
- obtain explicit approval for topology changes first
- after approval, update `{planning_repositories_file}` and continue

## Step 4: Select Bootstrap Targets

After the topology registry is approved:

1. build the target set from approved repo ids or repo groups
2. default to targeted selection, not all known repos
3. allow the current root only when no child repo targets are requested

Write `{bootstrap_selection_file}` including:

- selected repo ids
- skipped repo ids
- whether docs bootstrap is enabled
- whether planning bootstrap is enabled
- which repos appear already aligned and will only be checked

If a selected repo is not in `{planning_repositories_file}`, stop and resolve the topology gap first.

## Step 5: Bootstrap Each Target Repo

For each selected repo:

1. resolve the authoritative repo root path from `{planning_repositories_file}`
2. inspect whether the repo already has:
   - `planning/roadmap/`
   - `planning/current/`
   - `planning/previous/`
   - `planning/lessons/`
   - root `docs/`
3. if planning bootstrap is enabled, reuse `init-planning` semantics for that repo
4. if docs bootstrap is enabled, reuse `init-docs` semantics for that repo

Per-repo rules:

- planning bootstrap runs before docs bootstrap
- preserve live authority files if already present
- move legacy docs or planning artifacts into dated migration snapshots instead of overwriting them
- if the repo is already aligned, record `already_aligned` rather than rewriting

Do not create repo-local PRDs, architecture docs, stories, or implementation evidence here.

## Step 6: Aggregate Results

For each target repo, classify the result as one of:

- `initialized`
- `already_aligned`
- `partially_migrated`
- `failed`
- `skipped`

If one repo fails:

- continue only for independent remaining targets
- record the failed repo as blocked in the aggregate report
- do not mark the entire run successful

## Step 7: Emit Workspace Bootstrap Report

Write `{default_output_file}` including:

- current root scope
- topology changes applied
- selected targets
- per-repo bootstrap status
- Beads availability status for the current environment
- planning snapshot locations
- docs snapshot locations
- blocked or failed repos
- repos intentionally skipped
- recommended next step for newly initialized workspace or parent repos:
  - `/bmad-bmm-project-roadmap`
- recommended next step for newly initialized delivery repos:
  - `/bmad-bmm-project-roadmap` or `/bmad-bmm-phase-sync` depending on repo readiness

## Step 8: Resume Rules

On rerun:

- reuse the approved `{planning_repositories_file}`
- skip repos already marked `initialized` or `already_aligned` unless explicitly reopened
- rerun only failed, blocked, or newly targeted repos by default
- do not regenerate snapshots for unchanged repos just because the aggregate workflow was rerun
