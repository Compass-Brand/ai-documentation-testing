# BMAD Automation Specs

Status: phase-6-reference-specs-landed
Owner:
Last Updated: 2026-03-13

This directory is the shipped method-spec home for Compass BMAD automation wrappers.

These wrapper specs are intentionally not cataloged in `_bmad/bmm/module-help.csv` yet because they remain orchestration contracts, not slash-command runtime commands.

## Purpose

- define the automation wrappers around the canonical Compass BMAD workflow
- define the state, context, patching, approval, and failure contracts that those wrappers must follow
- define reusable templates for reports, handoffs, gate packages, and runtime state files

## Structure

```text
_bmad/tools/automation/
├── README.md
├── commands/
│   ├── auto-plan.md
│   ├── auto-epic-start.md
│   ├── auto-story.md
│   └── auto-epic-end.md
├── policies/
│   ├── context-budgeting.md
│   ├── patching-strategy.md
│   └── state-model.md
└── templates/
    ├── approval-gate-report.md
    ├── auto-plan-report.md
    ├── auto-plan-state.yaml
    ├── epic-end-report.md
    ├── epic-start-report.md
    ├── handoff-template.md
    ├── partial-failure-report.md
    ├── roadmap-state-update.md
    ├── story-gate-report.md
    └── story-run-report.md
```

## Command Specs

- `commands/auto-plan.md`
  - analysis through implementation-readiness wrapper with staged approvals
- `commands/auto-epic-start.md`
  - epic-start readiness, ordering, and test-design wrapper
- `commands/auto-story.md`
  - story-loop wrapper with reuse scan, ATDD, implementation, automation, and review routing
- `commands/auto-epic-end.md`
  - epic closeout, retrospective, docs delta, and next-epic preview wrapper

## Policy Specs

- `policies/state-model.md`
  - canonical automation state, authority order, and approval semantics
- `policies/context-budgeting.md`
  - minimum-context loading and sharding rules by command
- `policies/patching-strategy.md`
  - draft-vs-canonical mutation rules, promotions, reuse scan, and failure-safe writes

## Templates

- `templates/auto-plan-state.yaml`
  - runtime checkpoint state for `auto-plan`
- `templates/approval-gate-report.md`
  - generic reviewer-facing gate package
- `templates/roadmap-state-update.md`
  - roadmap activation and reordering proposal
- `templates/partial-failure-report.md`
  - deterministic failure report for stopped runs
- `templates/handoff-template.md`
  - structured agent or human handoff contract
- `templates/story-gate-report.md`
  - merge-risk or risky-change approval package
- `templates/auto-plan-report.md`
  - execution log and run summary
- `templates/epic-start-report.md`
  - epic readiness summary
- `templates/story-run-report.md`
  - story execution summary
- `templates/epic-end-report.md`
  - epic closeout summary

## Reference Rules

1. The canonical workflow stays in `_bmad/BMAD-workflow.md`.
2. Automation wraps the workflow. It does not replace the workflow.
3. The state model is BMAD artifacts plus `bd`, not TodoWrite.
4. `bd prime` should be treated as the workflow-context recovery command after compaction, clear, or a fresh automation session.
5. Human approvals remain explicit at roadmap, PRD, architecture, readiness, merge, and epic-closeout checkpoints.
6. Sequential execution is the default for v1.
7. Draft outputs must stay in draft locations until the relevant approval gate is accepted.
8. `auto-plan-report.md` is never a resume source.
9. Active phases, epics, and stories should have Beads issue references recorded in runtime state as the wrappers progress.

## Primary Inputs

- `_bmad/BMAD-workflow.md`
- `_bmad/bmm/module-help.csv`
- `planning/`
- `planning/templates/`
- `docs/`

## Current Boundary

These files define the approved shipped automation contract. They do not yet:

- create cataloged runtime commands in the deployed client surfaces
- assume a specific plugin runtime
- require background jobs, queues, or scheduled automation
- replace explicit human approvals
