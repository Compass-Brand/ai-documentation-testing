# Planning Framework

This directory defines the roadmap-driven Compass BMAD planning framework.

In deployed project repositories this bundle lives under root `planning/`. The editable source is maintained in compass-engine under `src/planning/`.

## Purpose

- provide the deployed layout for project-level and phase-level planning
- separate reusable framework guidance from live project planning state
- support repeatable multi-phase development instead of one-off MVP planning

## Domains

- the root `planning/` control surface is the live planning framework layout
- `docs/` contains usage guidance, conventions, and lifecycle rationale
- `templates/` contains starter artifacts for roadmap, phase, and implementation support work

Workspace and parent repos may also use orchestration-specific control surfaces:

- `repositories.yaml`
- `current/initiative-index.yaml`
- `current/initiatives/`

## Primary Entry Commands

- use `/bmad-bmm-init-planning` to scaffold or normalize the live planning framework
- use `/bmad-bmm-sync-repositories` to refresh the approved repo-topology registry when repos are added, moved, or missed
- use `/bmad-bmm-workspace-bootstrap` from workspace or parent repos to initialize selected child repos into the BMAD planning and docs structure
- use `/bmad-bmm-project-roadmap` to create or update approved roadmap state before `Phase Sync`
- use templates directly only when a remaining planning step does not yet have a dedicated workflow

## Read Order

1. `README.md`
2. `docs/how-to-use.md`
3. `docs/workflow-map.md`
4. `templates/README.md`
5. `roadmap/roadmap.md`
6. `current/phase.md`

When machine state matters, also load:

1. `repositories.yaml` when repo routing or ownership matters
1. `roadmap/roadmap.yaml`
2. `current/phase-state.yaml`
3. `current/initiative-index.yaml` when multiple concurrent initiatives are active

## Structure

```text
planning/
├── README.md
├── repositories.yaml
├── current/
├── previous/
├── lessons/
├── roadmap/
├── docs/
├── templates/
└── ...
```
