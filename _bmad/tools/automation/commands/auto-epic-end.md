# `auto-epic-end`

## Purpose

- Close the active epic cleanly by gathering evidence, producing the retrospective, updating docs, and preparing the next epic.
- Prevent silent epic closure without human review of carry-over, docs deltas, and next-epic readiness.

## Prerequisites

- All in-scope stories in the epic are completed, deferred, or explicitly waived.
- Traceability and review outputs exist for completed stories.
- `bd` is available so epic closure and carry-over can be reconciled in Beads.

## Reads

- The epic definition
- Story files for the epic
- Current implementation evidence
- Testing and gate outputs
- Sprint status
- Current roadmap and phase state
- Relevant Beads epic and story issues

## Writes

- `planning/current/implementation/retrospectives/epic-<epic-id>-retrospective.md`
- `planning/current/implementation/evidence/epic-<epic-id>-end-report.md`
- Docs delta summary in `planning/current/implementation/evidence/epic-<epic-id>-docs-update.md`
- Next-epic preview in `planning/current/implementation/evidence/epic-<next-epic-id>-preview.md` if another epic exists
- Proposed phase-state updates
- Beads epic closure or carry-over issue updates

## Exact Step Sequence

1. Preflight epic completion, verify story statuses, and confirm `bd` availability.
2. Gather testing, review, traceability, and implementation evidence.
3. Draft the retrospective.
4. Draft the docs delta and promotion candidates.
5. Draft the next-epic preview and identify carry-over items, creating follow-up Beads issues for incomplete or deferred work when needed.
6. Draft any required phase-state updates.
7. Stop for human approval before marking the epic complete or advancing to the next epic.
8. Once approved, close the Beads epic issue when the epic is complete, clear `phase-state.yaml.beads.active_epic_issue_id`, append new carry-over issue ids to `phase-state.yaml.beads.follow_up_issue_ids`, and run `bd sync`.

## Approval Checkpoints

- Epic-complete decision
- Carry-over of incomplete or waived stories
- Promotion of planning artifacts into stable docs
- Advancing to the next epic when open blockers remain

## Failure Handling

- Write `planning/current/implementation/evidence/epic-<epic-id>-end-failure.md`.
- Do not mark the epic complete.
- Set `next_checkpoint` in `phase-state.yaml` to the unresolved epic-closeout action.

## Resume Behavior

- If the retrospective exists but docs delta is missing, resume from docs update.
- If next-epic preview exists but approval is pending, resume at the approval checkpoint.

## Final Outputs

- Retrospective
- Epic end report
- Docs delta summary
- Next-epic preview or final-epic note
- Beads epic closure or carry-over issue updates

## Example Invocation

```text
auto-epic-end --phase-id phase-002 --epic-id epic-03 --approval-mode manual
```

## Example Outcome

- The epic is either approved for closure or clearly blocked.
- The next epic is previewed with carry-over and dependency notes.
- Docs updates and lessons candidates are prepared for human review.
