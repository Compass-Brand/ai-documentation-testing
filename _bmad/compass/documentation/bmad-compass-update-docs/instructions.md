# Update Docs Workflow

<critical>The workflow engine is governed by: {project-root}/_bmad/core/module.yaml</critical>
<critical>You MUST have already loaded and resolved: {project-root}/_bmad/compass/documentation/bmad-compass-update-docs/workflow.yaml</critical>
<critical>Communicate all responses in {communication_language}</critical>

## Goal

Apply incremental documentation updates across `{docs_root}` based on current phase artifacts and selected update scope.

Use the canonical framework in `{docs_framework_human_policies_dir}` and `{docs_framework_human_templates_dir}` as the source standards. In deployed repos, the live documentation output remains the root `docs/` tree.

## Step 1: Discover Current Inputs

Load current artifacts from:

- `{current_prd_dir}`
- `{current_ux_dir}`
- `{current_architecture_dir}`
- `{current_epics_dir}`
- `{current_story_dir}`
- `{current_evidence_dir}`
- `{current_testing_dir}`
- `{current_research_dir}`

## Step 2: Determine Delta Targets

Map discovered deltas to docs destinations:

- architecture and technical decisions -> `{docs_architecture_dir}`
- implementation process updates -> `{docs_development_dir}`
- onboarding or run instructions -> `{docs_getting_started_dir}`
- operator/developer guides -> `{docs_guides_dir}`
- reference artifacts, inventories, validation records -> `{docs_reference_dir}`

For each new or materially changed document, also determine:

- primary Diataxis mode: tutorial, how-to, reference, or explanation
- lifecycle state impact
- whether the change requires an ADR or architecture deep-dive update
- whether the source is a promoted planning artifact that must retain promotion evidence

## Step 3: Apply Updates

1. Update only sections impacted by current deltas.
2. Preserve existing valid content unless stale or contradictory.
3. Ensure all modified docs remain aligned to policy files in `{docs_human_policies_dir}`.
4. Use framework templates for newly created docs or README indexes.
5. Maintain owner, lifecycle, and `Last reviewed` metadata where policy or local standards require it.
6. When planning artifacts graduate into docs, preserve owner, lifecycle state, destination, and replacement or archive note in the update evidence.

## Step 4: Maintain Navigation

- Update `README.md` files for changed directories.
- Ensure new documents are linked from parent indexes.
- Ensure links remain relative.
- Add related links between explanation, how-to, tutorial, and reference pages when behavior overlaps.

## Step 5: Capture Report

Write `{default_output_file}` including:

- update scope
- files changed
- source artifacts used
- docs destinations selected
- Diataxis mode for new or materially changed docs
- lifecycle, owner, and review metadata updates
- ADRs created or updated
- promotion candidates or blockers
- unresolved documentation gaps
- recommendation to run `/bmad-bmm-validate-docs`
