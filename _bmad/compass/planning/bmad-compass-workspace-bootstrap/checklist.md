# Workspace Bootstrap Checklist

## Preconditions

- [ ] Current repo scope is `workspace` or `orchestration`
- [ ] Current root planning was normalized before child fan-out
- [ ] `.gitmodules` was inspected when present

## Registry Discipline

- [ ] Repository topology changes were written to `{topology_proposal_file}` before `{planning_repositories_file}` changed
- [ ] `repositories.yaml` was explicitly approved before canonical updates
- [ ] Unapproved topology was not written to `{planning_repositories_file}`

## Targeting

- [ ] Target repo ids came from the approved `repositories.yaml`
- [ ] Bootstrap selection was recorded in `{bootstrap_selection_file}`
- [ ] Fan-out used targeted selection rather than implicit all-repo execution

## Per-Repo Safety

- [ ] Planning bootstrap ran before docs bootstrap for each selected repo
- [ ] Safe migration behavior was preserved for existing docs or planning artifacts
- [ ] Already-aligned repos were not rewritten
- [ ] No repo-local delivery artifacts were created by this workflow

## Outputs

- [ ] Aggregate bootstrap report written to `{default_output_file}`
- [ ] Each selected repo was classified as initialized, already aligned, partially migrated, failed, or skipped
- [ ] Recommended next steps were recorded for the current root and targeted repos
