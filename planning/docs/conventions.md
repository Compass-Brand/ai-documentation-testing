# Planning Conventions

These conventions are mandatory for all artifacts in `planning/`.

## Naming

- phase snapshot folder: `<phase-slug>-<YYYY-MM-DD>`
- lesson folder: `<phase-slug>-<YYYY-MM-DD>`
- roadmap archive folder: `<YYYY-MM-DD>`
- `phase-slug` and phase ids MUST be lowercase kebab-case

Examples:

- `platform-hardening-2026-02-25`
- `release-readiness-2026-03-14`

## Dates And Timestamps

- file-system dates MUST use `YYYY-MM-DD`
- do not use relative dates such as `today` or `next-week` in filenames
- machine-state timestamps SHOULD use ISO 8601 with timezone offset

## Status Tags

Use one of these status markers at the top of working markdown files:

- `Status: draft`
- `Status: active`
- `Status: final`
- `Status: archived`

## Ownership

Each major artifact SHOULD include:

- `Owner: <name or team>`
- `Last Updated: <YYYY-MM-DD>`

## Authority Rules

- `repositories.yaml` is authoritative for repo ids, parent/child relationships, and repo-root ownership
- `roadmap.yaml` is authoritative over `roadmap.md`
- `phase-state.yaml` is authoritative over `phase.md`
- `initiative-index.yaml` is authoritative over initiative folder discovery when multiple initiatives are active
- machine files update first and human files update second
- roadmap files must only contain approved roadmap state
- phase files must reflect the active approved slice
- instantiated files in `planning/` are authoritative over `planning/templates/`
- template files are starter copies only and must not be treated as live state

## File Lifecycle

1. draft and refine artifacts in `current/` or `roadmap/`
2. keep unapproved machine-state changes out of canonical yaml files
3. in workspace or orchestration scope, keep concurrent initiative routing in `current/initiative-index.yaml` and `current/initiatives/`
4. finalize approved phase outputs in `current/`
5. freeze and move the closed phase snapshot into `previous/`
6. extract reusable insights into `lessons/`
7. archive superseded roadmap artifacts in `roadmap/archive/`

## Draft And Promotion Rules

- pre-readiness epic outputs belong in `current/planning/epics/draft/`
- pre-readiness story outputs belong in `current/implementation/stories/draft/`
- pre-readiness gate packages belong in `current/testing/gates/draft/`
- pre-readiness secure gate packages belong in `current/testing/gates/draft/security/`
- approved secure readiness gate reports belong in `current/testing/gates/security/readiness/`
- approved secure release gate reports belong in `current/testing/gates/security/release/`
- once approved, `artifact_paths.current` must point to the canonical non-draft location

## Automation Conventions

- automation runtime state files live in `current/implementation/evidence/`
- reviewer-facing automation gate packages live in `current/implementation/evidence/` or `current/testing/gates/draft/` depending on scope
- `auto-plan-state.yaml` is machine state, not a human summary
- report markdown files are evidence artifacts, not resume state
- automation wrappers must respect the same draft-versus-canonical promotion rules as manual workflows

## Planning-To-Docs Promotion Rules

- stable planning artifacts may move into the repo `docs/` tree only with an owner, lifecycle state, approved destination, and replacement or archive note
- promoted docs must link back to the source planning artifact or recorded decision that stabilized them
- project-specific roadmap, phase, automation runtime, and gate artifacts do not promote into the reusable engine bundle sources

## Path Rules

- active phase content MUST NOT be written under `previous/`
- historical content MUST NOT remain in `current/` after closeout
- roadmap artifacts belong in `roadmap/`, not inside phase snapshots
- detailed phase research and planning artifacts belong in their lane-specific folders, not generic dump folders
- orchestration repos keep concurrent initiative folders under `current/initiatives/`; delivery repos do not create them unless they are acting as an orchestration root
