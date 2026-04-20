# Sync Repositories Workflow

<critical>The workflow engine is governed by: {project-root}/_bmad/core/module.yaml</critical>
<critical>You MUST have already loaded and resolved: {project-root}/_bmad/compass/planning/bmad-compass-sync-repositories/workflow.yaml</critical>
<critical>Communicate all responses in {communication_language}</critical>

## Goal

Maintain `{planning_repositories_file}` as the approved machine-readable repo topology registry.

Use this workflow when:

- a repo was added
- a repo was removed
- a repo path changed
- a parent-child relationship changed
- the registry appears incomplete or stale

This workflow must not silently rewrite `{planning_repositories_file}`.

## Step 1: Validate Scope

Determine whether the current repo is:

- `workspace`
- `orchestration`
- `delivery`

Rules:

- if the current repo is `delivery`, stop and report that repo-topology sync belongs in the parent or workspace root
- only continue in `workspace` or `orchestration` scope

## Step 2: Load Current Registry and Topology

Read:

- `{planning_repositories_file}` when present
- `.gitmodules` in the current repo root when present

Build the discovered topology from the current repo root by identifying:

- direct child repos
- nested child repos listed through the current orchestration tree
- observed path changes

Treat `.gitmodules` as the discovery source and `{planning_repositories_file}` as the approved canonical state.

## Step 3: Compare Approved vs Discovered State

Detect:

- repos present in `.gitmodules` but missing from `{planning_repositories_file}`
- repos present in `{planning_repositories_file}` but not currently discovered
- repo path changes
- parent-child relationship changes
- repo-type mismatches
- title or domain fields that need follow-up review

Do not update the canonical registry yet.

## Step 4: Draft the Topology Proposal

Write `{topology_proposal_file}` before changing `{planning_repositories_file}`.

Include:

- added repos
- removed repos
- moved repos
- relationship changes
- unresolved classification questions
- recommended canonical updates

For removed repos:

- propose removal from the active registry
- do not silently delete related planning history

## Step 5: Approval Checkpoint

Obtain explicit approval for:

- newly added repos
- removed repos
- path changes
- parent-child relationship changes
- repo-type classification changes

If approval is denied or incomplete:

- leave `{planning_repositories_file}` unchanged
- report the unresolved gaps in `{default_output_file}`

## Step 6: Update Canonical Registry

After approval:

1. update `{planning_repositories_file}`
2. ensure the approved topology is represented canonically
3. keep the registry focused on live authoritative repo roots

Do not create planning or docs scaffolds here. This workflow updates topology only.

## Step 7: Emit Sync Report

Write `{default_output_file}` including:

- current repo scope
- registry entries reviewed
- topology additions
- topology removals
- topology moves
- relationship changes
- unresolved follow-up items
- recommended next step:
  - `/bmad-bmm-workspace-bootstrap` when newly added repos now need initialization
  - `/bmad-bmm-project-roadmap` when topology is current and planning can proceed
