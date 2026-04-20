# Initialize Docs Workflow

<critical>The workflow engine is governed by: {project-root}/_bmad/core/module.yaml</critical>
<critical>You MUST have already loaded and resolved: {project-root}/_bmad/compass/documentation/bmad-compass-init-docs/workflow.yaml</critical>
<critical>Communicate all responses in {communication_language}</critical>

## Goal

Migrate existing repository documentation into the Compass deployed documentation layout under `{docs_root}` while preserving all legacy content in a dated migration snapshot under `{docs_tmp_migration_root}`.

Use the canonical documentation framework in `{docs_framework_root}` as the standards source. In `compass-engine` this framework is authored in `docs/`, but deployed project outputs belong in `docs/`.

## Step 1: Preflight and Snapshot Date

1. Resolve `snapshot_date` in `YYYY-MM-DD` format.
2. Set `snapshot_root` = `{docs_tmp_migration_root}/{snapshot_date}`.
3. Confirm migration mode with user:
   - default: keep migration snapshot indefinitely
   - optional cleanup allowed only when explicitly requested and `docs_tmp_cleanup_enabled` is true

## Step 2: Discover Existing Docs Inputs

Discover all documentation candidates to migrate:

- root-level docs: `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`, `CODE_OF_CONDUCT.md`, `LICENSE`
- folder docs: `docs/**`, `documentation/**`, `docs/**`
- any markdown files in top-level operational folders that clearly function as product documentation

Before building the candidate list, detect whether the repo already has the Compass docs control plane installed in place. Treat these as live aligned state, not legacy migration inputs:

- `{docs_human_root}/**`
- `{docs_ai_root}/README.md`
- `{docs_root}/BMAD-integration.md`
- required Compass scaffold files already living under `{docs_root}` such as:
  - `{docs_root}/README.md`
  - `{docs_architecture_dir}/README.md`
  - `{docs_architecture_decisions_dir}/README.md`
  - `{docs_development_dir}/README.md`
  - `{docs_getting_started_dir}/README.md`
  - `{docs_getting_started_dir}/installation.md`
  - `{docs_getting_started_dir}/quickstart.md`
  - `{docs_guides_dir}/README.md`
  - `{docs_reference_dir}/README.md`

Rules:

- If the repo only contains the already-aligned Compass docs control plane and no extra legacy docs outside it, the migration candidate list may be empty.
- Do not treat the active root `README.md` as a migration candidate by default in a fresh or already-aligned repo. Only migrate it when the user confirms it is legacy documentation that should move under `docs/`.
- Exclude already-aligned Compass control-plane files from the candidate list even when other legacy docs must still be migrated.

Produce a candidate list before moving files.

## Step 3: Move Legacy Docs to Snapshot

1. If the candidate list is empty, skip snapshot creation and record `no legacy docs migrated` in `{migration_manifest}`.
2. If legacy docs are present, create `{snapshot_root}`.
3. Move discovered legacy docs into the snapshot, preserving relative structure.
4. Do not delete snapshot content after move.
5. Record moved paths in `{migration_manifest}`.

## Step 4: Scaffold Required Docs Structure

Ensure all required Compass docs directories and index files exist:

- `{docs_root}/README.md`
- `{docs_architecture_dir}/README.md`
- `{docs_architecture_decisions_dir}/README.md`
- `{docs_development_dir}/README.md`
- `{docs_getting_started_dir}/README.md`
- `{docs_getting_started_dir}/installation.md`
- `{docs_getting_started_dir}/quickstart.md`
- `{docs_guides_dir}/README.md`
- `{docs_reference_dir}/README.md`

For newly created index files, use the applicable templates from `{docs_framework_human_templates_dir}`.
Ensure `{docs_root}/README.md` records docs ownership, review cadence, and the repo docs ownership model.

Use these starter templates when creating greenfield scaffolding:

- `readme-docs-index.md` -> `{docs_root}/README.md`
- `docs-architecture-index.md` -> `{docs_architecture_dir}/README.md`
- `docs-architecture-decisions-index.md` -> `{docs_architecture_decisions_dir}/README.md`
- `docs-development-index.md` -> `{docs_development_dir}/README.md`
- `docs-getting-started-index.md` -> `{docs_getting_started_dir}/README.md`
- `docs-getting-started-installation.md` -> `{docs_getting_started_dir}/installation.md`
- `docs-getting-started-quickstart.md` -> `{docs_getting_started_dir}/quickstart.md`
- `docs-guides-index.md` -> `{docs_guides_dir}/README.md`
- `docs-reference-index.md` -> `{docs_reference_dir}/README.md`
- `docs-user-overrides.md` -> `{docs_human_overrides_file}`

Scaffold files created from these templates MUST stay generic to the current target repo. Do not hardcode `compass-engine`, `compass-forge`, or a submodule layout unless the current repo genuinely requires that wording.

## Step 5: Sync Built-In Policy and Template Assets

1. Copy baseline policy files from `{docs_framework_human_policies_dir}` to `{docs_human_policies_dir}`.
2. Copy baseline templates from `{docs_framework_human_templates_dir}` to `{docs_human_templates_dir}`.
3. Copy `{docs_framework_ai_root}/README.md` to `{docs_ai_root}/README.md` if missing.
4. Ensure `{docs_human_overrides_file}` exists with placeholder content if missing, using `docs-user-overrides.md` when available.

These files are the project-local documentation control plane. They support the live deployed docs tree but do not replace the reader-facing docs under the primary `docs/*` destinations.

## Step 6: Transform Legacy Content into Target Structure

Using moved source material in `{snapshot_root}`, generate structured docs under `{docs_root}`:

- architecture outputs -> `{docs_architecture_dir}` and `{docs_architecture_decisions_dir}`
- development/setup outputs -> `{docs_development_dir}` and `{docs_getting_started_dir}`
- guides/how-tos/tutorials -> `{docs_guides_dir}`
- inventories, API, data models, deep dives, migration logs -> `{docs_reference_dir}`

When useful, reuse native extraction heuristics from:

- `{legacy_requirements_csv}`
- `{legacy_full_scan_instructions}`
- `{legacy_deep_dive_instructions}`

While transforming content:

- choose a primary Diataxis mode for each new guide or reference document
- create or update ADRs in `{docs_architecture_decisions_dir}` when a major decision is expensive to reverse
- add lifecycle state and owner/review metadata when a document is becoming an active project doc
- record promotion gaps when a planning artifact is not yet stable enough to become canonical docs

## Step 7: Build Navigation and Cross-links

1. Update `{docs_root}/README.md` to index major docs sections.
2. Ensure each docs subdirectory `README.md` links to contained docs.
3. Ensure internal links are relative.
4. Add related links between explanation, how-to, tutorial, and reference pages when operationally relevant.

## Step 8: Emit Initialization Report

Write `{default_output_file}` including:

- snapshot path
- migrated inputs count
- generated/updated outputs count
- docs owner and ownership-model status
- lifecycle or promotion gaps still open
- unresolved migration gaps
- recommended follow-up command: `/bmad-bmm-update-docs`

## Step 9: Optional Cleanup (Explicit Only)

If user explicitly requests cleanup and `docs_tmp_cleanup_enabled` is true, remove the selected snapshot folder. Otherwise keep `{snapshot_root}` unchanged.
