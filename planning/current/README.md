# Current Phase

`current/` contains the active roadmap slice only.

## Control Files

- `phase.md`: human-readable phase brief
- `phase-state.yaml`: machine-readable active-phase state
- `initiative-index.yaml`: machine-readable initiative routing index for workspace or orchestration scope

## Working Areas

- `brainstorming/detailed/`: detailed brainstorming for the active slice
- `research/project-context/`: generated project context artifacts
- `research/market/`: detailed market research
- `research/domain/`: detailed domain research
- `research/technical/`: detailed technical research
- `research/strategy/`: detailed innovation strategy and opportunity framing
- `research/implementation/`: implementation-focused research
- `planning/brief/`: detailed product brief artifacts
- `planning/prd/`: PRD drafts, validations, and edits
- `planning/ux-design/`: WDS outputs including trigger mapping, scenarios, conceptual specs, and design delivery
- `planning/architecture/`: architecture, threat modeling, and security review outputs
- `planning/epics/`: epic drafts and approved epic sets
- `implementation/stories/`: story drafts and approved stories
- `implementation/evidence/`: review evidence, CI/CD alignment notes, traceability support, automation runtime files, and automation reports
- `implementation/retrospectives/`: epic and phase retrospectives
- `testing/test-design/`: system-level and epic-level test design
- `testing/automation/`: automation plans and outputs
- `testing/reviews/`: test reviews and related review artifacts
- `testing/gates/`: readiness, release, and other gate packages
- `testing/gates/draft/security/`: pending secure readiness gate packages
- `testing/gates/security/readiness/`: approved secure readiness gate reports
- `testing/gates/security/release/`: secure release gate reports
- `initiatives/`: per-initiative concurrent workstreams when the repo is orchestrating multiple targets

## Lifecycle

When a phase is complete:

1. finalize `phase-state.yaml` and `phase.md`
2. update roadmap state
3. move the frozen phase snapshot to `previous/<phase-slug>-<YYYY-MM-DD>/`
4. extract reusable lessons into `lessons/<phase-slug>-<YYYY-MM-DD>/`
5. create a clean `current/` scaffold for the next active slice

Automation runtime files and gate reports that belong to the closed phase move with that frozen snapshot unless they were explicitly promoted into an approved canonical gate location before closeout.
