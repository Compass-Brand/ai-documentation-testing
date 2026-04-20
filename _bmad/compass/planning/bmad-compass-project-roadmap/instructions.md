# Project Roadmap Workflow

<critical>The workflow engine is governed by: {project-root}/_bmad/core/module.yaml</critical>
<critical>You MUST have already loaded and resolved: {project-root}/_bmad/compass/planning/bmad-compass-project-roadmap/workflow.yaml</critical>
<critical>Communicate all responses in {communication_language}</critical>

## Goal

Turn high-level analysis into the authoritative roadmap control surface:

- human summary in `{roadmap_summary_file}`
- machine state in `{roadmap_state_file}`

This workflow is the project-level continuity layer that decides:

- what slice is active now
- what comes next
- what is deferred
- what depends on prior phases
- whether the slice is repo-local or orchestration-scoped
- which repos are targeted when orchestration is required
- which Beads parent or phase issues should own the approved active slice

Treat this workflow as operating on the current target repo, not on `compass-engine` as the source bundle. Any proposal, roadmap state, roadmap summary, or update report written by this workflow MUST derive the project/repo identity from the current `{project-root}` directory name or an already-present approved target-repo identifier inside the live planning files. Do not hardcode `compass-engine` unless the current repo actually is `compass-engine`.

## Step 1: Gather Roadmap Inputs

Inspect the roadmap-level source artifacts:

- `{roadmap_brainstorming_dir}`
- `{roadmap_market_research_dir}`
- `{roadmap_domain_research_dir}`
- `{roadmap_technical_research_dir}`
- `{roadmap_strategy_dir}`
- `{roadmap_storytelling_dir}` when storytelling is enabled
- `{roadmap_product_brief_dir}`
- existing `{roadmap_summary_file}` and `{roadmap_state_file}` if present
- `{planning_repositories_file}` when repo routing or child-repo orchestration is needed

If brownfield planning snapshots exist, use them as background context, not as the new source of truth.

## Scope-Awareness Guard

Before generating any multi-phase structure, assess the scope of the user's inputs. If the user's scope is narrow (single feature, smoke test, validation, or a single-phase deliverable), produce a single-slice roadmap without expanding into future phases or deferred opportunities. Only generate multi-phase planning when the scope naturally requires phased delivery or the user explicitly requests a broader roadmap.

## Step 2: Identify Candidate Phases and Sequencing

From the gathered inputs, derive:

- candidate roadmap slices or phases (a single slice when scope is narrow)
- a recommended ordering
- dependencies between phases (when multiple phases exist)
- the recommended active phase
- deferred or future opportunities (only when the scope warrants multi-phase planning)
- execution scope for each phase (`repo`, `orchestration`, or `workspace`)
- repo targets when execution scope is not `repo`
- major risks or assumptions that affect ordering

Keep the roadmap phase list concise and execution-oriented. Do not turn the roadmap into a backlog dump. For narrow-scope projects, a single-phase roadmap is the expected output.

## Step 3: Draft the Roadmap Proposal

Write `{roadmap_proposal_file}` before changing authoritative roadmap state.

Include:

- target repo identity derived from the current `{project-root}`
- proposed phase list with ids, titles, and objectives
- execution scope for each proposed phase
- repo targets for any workspace or orchestration phase
- proposed Beads parent or phase tracking issue strategy when new slices are being activated
- recommended active phase
- recommended next phase
- dependencies
- deferred work
- rationale for the ordering
- any gaps in the high-level inputs

Do not update `{roadmap_state_file}` yet.

## Step 4: Approval Checkpoint

Obtain explicit approval for:

- phase ordering
- active phase selection
- deferred or requeued work
- dependency chain

If the proposal is not approved:

- revise the proposal
- keep `{roadmap_state_file}` and `{roadmap_summary_file}` unchanged
- record unresolved gaps in `{default_output_file}` only if asked to emit a draft report

## Step 5: Update Authoritative Roadmap State

After approval:

1. Update `{roadmap_state_file}` first.
2. Set:
   - `version`
   - `project`
   - `owner`
   - `last_updated`
   - `active_phase_id`
   - `phases[]`
3. For each phase entry, populate at minimum:
   - `id`
   - `slug`
   - `title`
   - `status`
   - `execution_scope`
   - `objective`
   - `roadmap_order`
   - `depends_on`
   - `repo_targets`
   - `workstreams`
   - `dependency_edges`
   - `overlap_domains`
   - `integration_gates`
   - `entry_criteria`
   - `exit_criteria`
   - `supporting_docs`

Only approved state belongs in `{roadmap_state_file}`.

For downstream repos, the `project` field MUST describe the current target repo, not the source bundle that shipped the workflow.

## Step 6: Update the Human Roadmap Summary

Update `{roadmap_summary_file}` second so it matches the approved machine state.

Ensure it includes:

- project identity aligned with the approved target repo
- current horizon
- active phase and objective
- roadmap sequence table
- phase index
- deferred or future opportunities (only when the scope warrants multi-phase planning)
- source artifact list
- change log entry for this update

If `{roadmap_state_file}` and `{roadmap_summary_file}` disagree, the YAML must win.
When rendering repo targets in the human summary, copy the approved `repo_targets` values literally from `{roadmap_state_file}`. Do not replace them with aliases such as `self`, `current repo`, or other shorthand.

## Step 7: Emit Roadmap Update Report

Write `{default_output_file}` including:

- target repo identity derived from the current `{project-root}`
- source artifacts inspected
- approved active phase
- approved next phase
- approved execution scope
- approved repo targets
- deferred work
- key sequencing rationale
- remaining gaps or assumptions
- recommended next command: `/bmad-bmm-phase-sync`

All emitted text in the proposal, summary, and report MUST stay target-repo-safe. It may refer to validating the Compass Engine deployment path, but it must not relabel the current repo itself as `compass-engine` unless that is truly the current repo.

## Step 8: Boundary Rule

Do not update `current/phase.md` or `current/phase-state.yaml` here.

Roadmap work stays in `roadmap/`.
`Phase Sync` owns activation of the approved active slice into `current/`.
