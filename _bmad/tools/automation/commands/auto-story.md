# `auto-story`

## Purpose

- Automate the story loop from validation through implementation evidence without bypassing review or risky-change approvals.
- Keep the story runnable through deterministic reuse, testing, review, and traceability steps.

## Prerequisites

- The target story exists in `current/implementation/stories/`.
- Story dependencies are satisfied.
- The epic has been started and is ready.
- `bd` is available and the story can be linked to a Beads issue before implementation begins.

## Reads

- The target story file
- `phase-state.yaml`
- Relevant PRD, WDS, architecture, and epic artifacts
- Existing codebase surfaces needed for the story
- Prior reuse notes, ADRs, and shared patterns
- Relevant tests and fixtures
- Relevant Beads story, blocker, and follow-up issues when they already exist

## Writes

- Updated story file in `current/implementation/stories/`
- Reuse-check note in `current/implementation/evidence/`
- ATDD artifacts in `current/testing/test-design/`
- Test automation artifacts in `current/testing/automation/`
- Code review notes in `current/testing/reviews/`
- Test review notes in `current/testing/reviews/`
- Traceability report in `current/testing/gates/`
- `planning/current/implementation/evidence/story-<story-id>-run-report.md`
- `planning/current/implementation/evidence/story-<story-id>-gate-report.md` when approval is required
- Beads story status updates, follow-up issues for discovered work, and story closure when the story is accepted

## Exact Step Sequence

1. Preflight story readiness, dependency completion, and `bd` availability.
2. Load the minimum context needed from PRD, WDS, architecture, epic, and codebase sources.
3. Reconcile or create the story's Beads issue id, update it to `in_progress`, and record it in `phase-state.yaml.beads.active_story_issue_id`.
4. Validate the story and update it if validation findings are minor.
5. Run ATDD.
6. Run the required reuse scan and write reuse evidence.
7. Stop for approval if the story appears to require net-new architecture, destructive schema work, or another hard-stop condition.
8. Implement the story.
9. Run primary test automation.
10. Run QA automation only when API or E2E expansion is justified.
11. Run code review.
12. Run test review.
13. Run traceability.
14. Create `bd` follow-up issues for confirmed blockers, defects, or deferred work that should survive the story run.
15. Write the story run report and stop for merge approval.
16. Once merge approval is granted and the story is accepted, close the story issue, append any new follow-up ids to `phase-state.yaml.beads.follow_up_issue_ids`, clear `phase-state.yaml.beads.active_story_issue_id`, and run `bd sync`.

## Approval Checkpoints

- Any hard-stop change category
- Net-new architecture or subsystem creation
- Destructive schema or migration changes
- Final merge or story-complete decision

## Failure Handling

- Write `planning/current/implementation/evidence/story-<story-id>-failure.md`.
- Keep the story in a non-closed state.
- Write the last successful step and open blockers into the story run report.

## Resume Behavior

- If ATDD exists and is accepted, do not rerun it unless the story changed materially.
- If implementation is complete but reviews failed, resume at review remediation.
- If automation artifacts exist, only regenerate the missing or invalid pieces.

## Final Outputs

- Validated story
- Reuse evidence
- Implementation changes
- Automation and review evidence
- Traceability evidence
- Merge-approval gate report
- Beads story issue updated through `in_progress` and `closed`, plus follow-up issues for discovered work

## Example Invocation

```text
auto-story --phase-id phase-002 --epic-id epic-03 --story-id story-03-02 --approval-mode manual
```

## Example Outcome

- The story is validated, implemented, tested, reviewed, and traced.
- Merge is blocked until human approval is given.
- Risky architectural or migration changes stop the run before irreversible work proceeds.
