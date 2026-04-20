# `auto-epic-start`

## Purpose

- Prepare one epic for execution by validating order, dependencies, test design, and baseline expectations.
- Produce a deterministic epic-start package before the story loop begins.

## Prerequisites

- `phase-state.yaml` exists and `workflow_status.solutioning=complete`.
- The target epic exists in `current/planning/epics/`.
- Prior epic cleanup is complete or explicitly acknowledged.
- `bd` is available and the epic can be linked to a Beads issue before execution starts.

## Reads

- `planning/current/phase.md`
- `planning/current/phase-state.yaml`
- Epic definitions in `planning/current/planning/epics/`
- Architecture docs
- Relevant WDS outputs
- Previous retrospective if this is not the first epic
- Existing sprint status and implementation evidence
- Relevant Beads phase and epic issues when they already exist

## Writes

- `planning/current/implementation/evidence/epic-<epic-id>-start-report.md`
- `planning/current/testing/test-design/test-design-epic-<epic-id>.md`
- `planning/current/research/implementation/epic-<epic-id>-implementation-research.md` when needed
- Beads update that links or creates the epic issue and moves it to `in_progress` once epic start is approved

## Exact Step Sequence

1. Preflight the epic id, dependencies, solutioning status, and `bd` availability.
2. Read epic scope, stories, dependencies, architecture context, and reconcile or create the epic's Beads issue id.
3. Check prior epic cleanup items and unresolved blockers.
4. Order stories for execution and identify parallel-safe versus sequential work.
5. Run epic-level test design.
6. Run implementation brainstorming if delivery risk or ambiguity is high.
7. Run implementation research if the epic introduces new patterns, integrations, or constraints.
8. Write the epic start report with story order, risks, ready-state summary, and the epic issue id.
9. Stop for human approval if epic scope or story order changed materially.
10. Once approved, set the epic issue to `in_progress`, update `phase-state.yaml.beads.active_epic_issue_id`, and run `bd sync`.

## Approval Checkpoints

- Material epic scope expansion
- Material story reordering caused by new dependencies
- Newly introduced technical pattern that changes architecture assumptions

## Failure Handling

- Write `planning/current/implementation/evidence/epic-<epic-id>-start-failure.md`.
- Keep the prior epic state unchanged if the new epic is not ready.
- Set `next_checkpoint` in `phase-state.yaml` to the unresolved epic-start blocker.

## Resume Behavior

- If epic test design already exists and is accepted, skip regeneration.
- If story ordering was already approved, resume from the next missing step.

## Final Outputs

- Approved epic story order
- Epic-level test design
- Epic start report
- Beads epic issue in `in_progress` state when the epic is approved to begin

## Example Invocation

```text
auto-epic-start --phase-id phase-002 --epic-id epic-03 --approval-mode manual
```

## Example Outcome

- Story execution order is proposed.
- Epic-level testing is prepared.
- The epic is either marked ready for story execution or blocked pending approval.
