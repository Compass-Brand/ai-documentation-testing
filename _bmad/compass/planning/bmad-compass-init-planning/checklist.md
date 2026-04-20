# Init Planning Checklist

## Preconditions

- [ ] `planning_root` resolves correctly
- [ ] `snapshot_date` is `YYYY-MM-DD`
- [ ] Snapshot path is under `{planning_tmp_migration_root}`

## Migration Safety

- [ ] Legacy planning inputs were inventoried before migration
- [ ] Live framework files inside `{planning_root}` were not moved into the snapshot
- [ ] Migration manifest written to `{migration_manifest}`

## Structure Compliance

- [ ] `current/`, `roadmap/`, `previous/`, and `lessons/` exist
- [ ] Active-phase working lanes exist under `{planning_current}`
- [ ] `initiatives/` exists when repo scope is `workspace` or `orchestration` (skip for `delivery`)
- [ ] Roadmap lanes exist under `{planning_roadmap}`
- [ ] Archive lanes exist under `{planning_roadmap}/archive/`

## Control Surface

- [ ] `{roadmap_summary_file}` exists
- [ ] `{roadmap_state_file}` exists
- [ ] `{phase_snapshot_file}` exists
- [ ] `{phase_state_file}` exists
- [ ] `{planning_repositories_file}` exists when repo scope is `workspace` or `orchestration` (skip for `delivery` -- do not flag absence)
- [ ] `{planning_initiative_index_file}` exists when repo scope is `workspace` or `orchestration` (skip for `delivery` -- do not flag absence)
- [ ] Live framework files were preserved when already present
- [ ] Missing or incomplete live files were reported instead of silently overwritten
- [ ] For `delivery` scope: orchestration files were not seeded, migrated, or reported as gaps

## Oversight Substrate

- [ ] When `{oversight_mode}` is `true`: `{current_oversight_dir}` exists
- [ ] When `{oversight_mode}` is `true`: `{current_oversight_dir}/risks.yaml` exists (copied from template)
- [ ] When `{oversight_mode}` is `true`: `{current_oversight_dir}/assumptions.yaml` exists (copied from template)
- [ ] When `{oversight_mode}` is `false`: oversight directory was not created

## Outputs

- [ ] Initialization report written to `{default_output_file}`
- [ ] Initialization report identifies the current target repo correctly and does not leak `compass-engine` into downstream output
- [ ] Recommended next step is `/bmad-bmm-project-roadmap`
