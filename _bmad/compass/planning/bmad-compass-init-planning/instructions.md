# Initialize Planning Workflow

<critical>The workflow engine is governed by: {project-root}/_bmad/core/module.yaml</critical>
<critical>You MUST have already loaded and resolved: {project-root}/_bmad/compass/planning/bmad-compass-init-planning/workflow.yaml</critical>
<critical>Communicate all responses in {communication_language}</critical>

## Goal

Normalize planning in the Compass roadmap-driven structure rooted at `{planning_root}`.

Use this workflow to:

- scaffold the live planning framework for a greenfield repo
- scaffold orchestration control surfaces when the repo coordinates child repos
- migrate brownfield planning artifacts into dated snapshots before normalization
- guarantee the four control-surface files exist:
  - `{roadmap_summary_file}`
  - `{roadmap_state_file}`
  - `{phase_snapshot_file}`
  - `{phase_state_file}`

Treat this workflow as operating on the current target repo, not on `compass-engine` as the source bundle. Any report or summary written by this workflow MUST derive the repo identity from the current `{project-root}` directory name or an already-present target-repo identifier inside the live planning files. Do not hardcode `compass-engine` unless the current repo actually is `compass-engine`.

## Step 1: Preflight and Snapshot Date

1. Resolve `snapshot_date` in `YYYY-MM-DD` format.
2. Set `snapshot_root` = `{planning_tmp_migration_root}/{snapshot_date}`.
3. Determine initialization mode:
   - `greenfield`: no legacy planning candidates outside `{planning_root}`
   - `brownfield`: existing planning artifacts need migration or normalization
4. Determine repo operating scope:
   - `workspace`: top-level repo coordinating multiple child repos across domains
   - `orchestration`: parent repo coordinating child repos
   - `delivery`: repo-local execution only
5. Verify `bd` is available in the environment. Record the detected version or the missing dependency for the initialization report.
6. Confirm migration mode with user:
   - default: keep planning snapshot indefinitely
   - optional cleanup allowed only when explicitly requested and `{planning_tmp_cleanup_enabled}` is true

## Step 2: Discover Existing Planning Inputs

Discover planning candidates that should migrate into the new structure.

Look for:

- `{project-root}/planning/` when it is not the same path as `{planning_root}`
- `{project-root}/roadmap/`
- `{project-root}/plans/`
- legacy planning staging directories created by earlier Compass migrations, if they exist
- root-level files that clearly function as planning state, such as:
  - `*roadmap*.md`
  - `*roadmap*.yaml`
  - `*plan*.md`
  - `*phase*.md`

Exclude:

- `{planning_root}`
- `{planning_templates_root}`
- the source-bundle path used by `compass-engine` maintainers when updating the shipped planning bundle
- any shipped Compass framework source directories

**Orchestration file handling by scope:**

When repo operating scope is `delivery`:

- If orchestration files (`repositories.yaml`, `initiative-index.yaml`) or an `initiatives/` directory are discovered, do **not** treat them as primary planning candidates. They are optional context that may have been inherited or seeded from a parent workspace.
- Do not flag their absence. Do not include them in the migration candidate list.
- If they exist, leave them in place silently -- do not move, migrate, or report them as gaps.

When repo operating scope is `workspace` or `orchestration`:

- Include orchestration files in the discovery and migration candidate list as normal.

Produce a candidate list before moving files.

## Step 3: Snapshot Legacy Planning

1. Create `{snapshot_root}` when brownfield inputs are found.
2. Move discovered legacy planning artifacts into the snapshot, preserving relative structure.
3. Do not move files already inside `{planning_root}`.
4. Record moved paths, reasons, and original locations in `{migration_manifest}`.

## Step 4: Scaffold the Live Planning Framework

Ensure these directories exist:

- `{planning_root}`
- `{planning_current}`
- `{planning_initiatives_root}`
- `{planning_roadmap}`
- `{planning_previous}`
- `{planning_lessons}`
- `{planning_current}/brainstorming/detailed/`
- `{planning_current}/research/project-context/`
- `{planning_current}/research/market/`
- `{planning_current}/research/domain/`
- `{planning_current}/research/technical/`
- `{planning_current}/research/strategy/`
- `{planning_current}/research/implementation/`
- `{planning_current}/planning/brief/`
- `{planning_current}/planning/prd/`
- `{planning_current}/planning/ux-design/trigger-mapping/`
- `{planning_current}/planning/ux-design/outline-scenarios/`
- `{planning_current}/planning/ux-design/conceptual-specifications/`
- `{planning_current}/planning/ux-design/design-delivery/test-scenarios/`
- `{planning_current}/planning/ux-design/design-delivery/handoff/`
- `{planning_current}/planning/ux-design/_progress/agent-dialogs/`
- `{planning_current}/planning/architecture/threat-modeling/`
- `{planning_current}/planning/architecture/security-review/`
- `{planning_current}/planning/epics/draft/`
- `{planning_current}/implementation/stories/draft/`
- `{planning_current}/implementation/evidence/`
- `{planning_current}/implementation/retrospectives/`
- `{planning_current}/testing/test-design/`
- `{planning_current}/testing/automation/`
- `{planning_current}/testing/reviews/`
- `{planning_current}/testing/gates/draft/security/`
- `{planning_current}/testing/gates/security/readiness/`
- `{planning_current}/testing/gates/security/release/`
- `{planning_current}/oversight/`
- `{planning_roadmap}/brainstorming/`
- `{planning_roadmap}/research/market/`
- `{planning_roadmap}/research/domain/`
- `{planning_roadmap}/research/technical/`
- `{planning_roadmap}/strategy/`
- `{planning_roadmap}/storytelling/`
- `{planning_roadmap}/product-brief/`
- `{planning_roadmap}/archive/brainstorming/`
- `{planning_roadmap}/archive/research/market/`
- `{planning_roadmap}/archive/research/domain/`
- `{planning_roadmap}/archive/research/technical/`
- `{planning_roadmap}/archive/strategy/`
- `{planning_roadmap}/archive/storytelling/`
- `{planning_roadmap}/archive/product-brief/`

### Step 4a: Scaffold Oversight Directory

<critical>This step is mandatory when `{oversight_mode}` is `true` (the default).</critical>

When `{oversight_mode}` is `true`:

1. Create `{current_oversight_dir}` if it does not exist.
2. Copy `{planning_templates_root}/oversight/risks.yaml` into `{current_oversight_dir}/risks.yaml` if it does not already exist.
3. Copy `{planning_templates_root}/oversight/assumptions.yaml` into `{current_oversight_dir}/assumptions.yaml` if it does not already exist.

When `{oversight_mode}` is `false`, skip this step.

## Step 5: Seed or Preserve the Authority Files

Use `{planning_templates_root}` as the starter source for the four authority files:

- `roadmap/roadmap.md`
- `roadmap/roadmap.yaml`
- `current/phase.md`
- `current/phase-state.yaml`

For workspace and orchestration repos also seed:

- `orchestration/repositories.yaml` -> `{planning_repositories_file}`
- `orchestration/initiative-index.yaml` -> `{planning_initiative_index_file}`

For delivery repos: do **not** seed orchestration files. If `{planning_repositories_file}` or `{planning_initiative_index_file}` already exist from a prior run or parent-workspace inheritance, leave them in place but do not flag their presence or absence in the report.

Rules:

1. If a live authority file is missing, create it from the matching template.
2. If a live authority file already exists, preserve it in place.
3. Do not overwrite live framework files just to refresh template wording.
4. If a preserved live file is materially incomplete, record the gap in the initialization report rather than clobbering the file.

## Step 6: Validate the Control Surface

Confirm:

- `{roadmap_summary_file}` exists
- `{roadmap_state_file}` exists
- `{phase_snapshot_file}` exists
- `{phase_state_file}` exists
- `{planning_repositories_file}` exists when repo scope is `workspace` or `orchestration`
- `{planning_initiative_index_file}` exists when repo scope is `workspace` or `orchestration`
- roadmap artifacts live under `{planning_roadmap}`
- active-phase artifacts live under `{planning_current}`
- snapshot and lesson destinations exist for later closeout

When repo scope is `delivery`: skip validation of `{planning_repositories_file}` and `{planning_initiative_index_file}` entirely. Do not report their absence as a gap or validation failure.

If any legacy planning had to be moved, record which old planning lanes should now map to:

- roadmap-level artifacts
- active-phase artifacts
- previous-phase snapshots
- lessons

## Step 7: Emit Initialization Report

Write `{default_output_file}` including:

- target repo name derived from the current `{project-root}`
- operating mode: greenfield or brownfield
- repo operating scope: workspace, orchestration, or delivery
- snapshot path
- migrated inputs count
- created directories count
- created authority files
- created orchestration files (only when repo scope is `workspace` or `orchestration`)
- preserved authority files
- Beads availability status and recommended next `bd` command (`bd prime` when available)
- unresolved normalization gaps
- recommended next command: `/bmad-bmm-project-roadmap`

The report MUST describe the current target repo generically. Do not refer to source-bundle authoring paths or call the target repo `compass-engine` unless that is truly the current repo.

## Step 8: Optional Cleanup (Explicit Only)

If the user explicitly requests cleanup and `{planning_tmp_cleanup_enabled}` is true, remove the selected snapshot folder. Otherwise keep `{snapshot_root}` unchanged.
