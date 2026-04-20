# `auto-plan`

## Purpose

- Automate the analysis, roadmap, detailed-analysis, planning, and solutioning flow up to implementation readiness.
- Stage the work through explicit roadmap, PRD, architecture, and readiness approvals.
- Keep runtime state deterministic so resume, rejection, and regeneration behavior are machine-checkable.

## Prerequisites

- `planning/roadmap/` exists or can be scaffolded.
- `planning/current/` exists or can be scaffolded.
- For brownfield runs, project context can be derived from the existing repo and current artifacts.
- For greenfield runs, initialization can scaffold the required planning surfaces.
- The canonical workflow is the current `_bmad/BMAD-workflow.md`.
- `bd` must be available in the environment so phase, epic, story, and follow-up work can be tracked in Beads.

## Reads

- `_bmad/BMAD-workflow.md`
- `_bmad/bmm/module-help.csv`
- `planning/roadmap/roadmap.md` if present
- `planning/roadmap/roadmap.yaml` if present
- `planning/current/phase.md` if present
- `planning/current/phase-state.yaml` if present
- `planning/current/implementation/evidence/auto-plan-state.yaml` if present
- Roadmap artifacts under `planning/roadmap/**`
- Prior lessons under `planning/lessons/**` when relevant
- Existing repo docs, planning artifacts, and structure for brownfield discovery
- Relevant Beads context from `bd ready`, `bd show <id>`, or previously linked phase issues when they already exist

## Writes

- `planning/current/implementation/evidence/auto-plan-preflight-failure.md`
- `planning/current/implementation/evidence/auto-plan-state.yaml`
- `planning/current/research/project-context/project-context.md`
- `planning/roadmap/brainstorming/`
- `planning/roadmap/research/market/`
- `planning/roadmap/research/domain/`
- `planning/roadmap/research/technical/`
- `planning/roadmap/strategy/`
- `planning/roadmap/storytelling/` when `lane_decisions.storytelling_mode=separate`
- `planning/roadmap/product-brief/`
- `planning/current/implementation/evidence/auto-plan-roadmap-proposal.md`
- `planning/current/implementation/evidence/auto-plan-prd-gate.md`
- `planning/current/implementation/evidence/auto-plan-architecture-gate.md`
- `planning/roadmap/roadmap.md` only after roadmap approval
- `planning/roadmap/roadmap.yaml` only after roadmap approval
- `planning/current/phase.md`
- `planning/current/phase-state.yaml`
- `planning/current/brainstorming/detailed/`
- `planning/current/research/market/`
- `planning/current/research/domain/`
- `planning/current/research/technical/`
- `planning/current/research/strategy/`
- `planning/current/planning/brief/`
- `planning/current/planning/prd/`
- `planning/current/planning/ux-design/trigger-mapping/` when `lane_decisions.wds_mode!=skipped`
- `planning/current/planning/ux-design/outline-scenarios/` when `lane_decisions.wds_mode!=skipped`
- `planning/current/planning/ux-design/conceptual-specifications/` when `lane_decisions.wds_mode!=skipped`
- `planning/current/planning/ux-design/design-delivery/` when `lane_decisions.wds_mode!=skipped`
- `planning/current/planning/architecture/`
- `planning/current/planning/architecture/threat-modeling/` when `lane_decisions.security_active=true`
- `planning/current/planning/architecture/security-review/` when `lane_decisions.security_active=true`
- `planning/current/planning/epics/draft/`
- `planning/current/implementation/stories/draft/`
- `planning/current/planning/epics/` only after readiness approval
- `planning/current/implementation/stories/` only after readiness approval
- `planning/current/testing/test-design/`
- `planning/current/testing/automation/`
- `planning/current/testing/gates/draft/auto-plan-readiness-summary.md`
- `planning/current/testing/gates/auto-plan-readiness-summary.md` only after readiness approval
- `planning/current/implementation/evidence/auto-plan-report.md`
- Beads issue creation or updates for the active initiative or phase plus draft epic and story tracking

`auto-plan-state.yaml` must carry at least:

- `version`
- `command`
- `phase_id`
- `run_status`
- `lane_decisions`
- `lane_outcomes`
- `approval_markers`
- `review_artifacts`
- `beads`
- `artifact_paths`
- `artifact_revisions`
- `automation_state`
- `workflow_status`
- `next_checkpoint`
- `draft_artifacts`

`draft_artifacts` must include:

- `roadmap_proposal`
- `prd_gate`
- `architecture_gate`
- `epics`
- `stories`
- `readiness_gate`

Each `draft_artifacts.*` entry must include:

- `path`
- `revision`
- `derived_from`
- `status`
- `supersedes`

## Exact Step Sequence

1. Preflight and determine greenfield or brownfield mode. Verify `bd` is available; if not, stop with a preflight failure before mutating planning state.
2. Initialize docs and planning structure if required, create the fallback evidence path, and initialize `auto-plan-state.yaml`. Do not create canonical `phase-state.yaml` yet.
3. If brownfield, generate or refresh project context from the live repo and existing artifacts.
4. Run high-level market, domain, and technical research.
5. Draft high-level innovation strategy and opportunity framing.
6. Handle storytelling according to `lane_decisions.storytelling_mode`, record the result in `lane_outcomes.storytelling`, and draft the corresponding artifact when applicable.
7. Draft the high-level product brief, update the current brief path, and record the current brief revision.
8. If greenfield, generate the seed project context now that high-level framing exists.
9. Draft `auto-plan-roadmap-proposal.md` using the roadmap-state-update template, set `review_artifacts.roadmap_gate` to that file, and update `auto-plan-state.yaml`.
10. Set `approval_markers.roadmap.status=pending`, set `approval_markers.roadmap.requested_revision`, set `automation_state.pending_approval`. If `{oversight_mode}` is `true`, run the oversight checkpoint workflow (`{project-root}/_bmad/compass/0-governance/bmad-compass-oversight-checkpoint/workflow.md`) with `gate_name` set to `roadmap` before presenting the approval request. Include the checkpoint report in the gate artifact. Stop for roadmap approval.
11. If roadmap approval is rejected, record the rejection in the proposal artifact and `auto-plan-state.yaml`, keep canonical roadmap files unchanged, and stop.
12. If roadmap approval is granted, update approved `roadmap.md` and `roadmap.yaml`, update the roadmap approval marker, create or reconcile the Beads parent or phase issue for the approved slice, record the resulting ids in `beads.*`, clear `automation_state.pending_approval`, and record `roadmap_approved` as the last completed checkpoint.
13. Run `Phase Sync` and create or update `phase.md` and `phase-state.yaml` from the approved slice plus the accepted values from `auto-plan-state.yaml`, including the Beads references.
14. Run detailed market, domain, and technical research for the active slice.
15. Draft detailed innovation strategy, detailed design-thinking output, and detailed brief, then update the brief path and revision state.
16. Draft PRD into its draft location, set the current PRD path to draft, run PRD validation, and record the current PRD revision with `state=draft`.
17. If `lane_decisions.wds_mode!=skipped`, generate Trigger Mapping, Outline Scenarios, Create UX Design, Conceptual Specifications, and Design Delivery, set the current UX path, record `lane_outcomes.wds=in_progress`, and populate `automation_state.derived_from`.
18. If WDS exposes requirement gaps, run `Edit PRD`, increment the current PRD revision, keep the PRD state as draft, and rerun `Validate PRD`.
19. If the revised PRD fails validation, mark WDS and downstream planning outputs stale, reset PRD approval to not requested, write `auto-plan-prd-gate.md` as blocked, and stop for manual correction.
20. If the revised PRD passes validation after PRD edits, regenerate affected WDS outputs and refresh their `derived_from` entries so they match the latest PRD revision.
21. Keep the PRD gate closed until the most recent PRD revision has a fresh validation result bound to the same revision id.
22. If WDS is skipped, set `lane_outcomes.wds=skipped`; otherwise set it to `complete` once WDS outputs match the current PRD revision.
23. Write `auto-plan-prd-gate.md`, set `review_artifacts.prd_gate`, set PRD approval to pending, set `automation_state.pending_approval`. If `{oversight_mode}` is `true`, run the oversight checkpoint workflow (`{project-root}/_bmad/compass/0-governance/bmad-compass-oversight-checkpoint/workflow.md`) with `gate_name` set to `prd` before presenting the approval request. Include the checkpoint report in the gate artifact. Stop for PRD approval.
24. If PRD approval is rejected, mark the PRD gate rejected, downgrade architecture and readiness approvals, append stale-output records for WDS, architecture, draft epics/stories, and readiness outputs, clear `automation_state.pending_approval`, and stop.
25. If PRD approval is granted, approve the current PRD revision and clear `automation_state.pending_approval`.
26. Draft architecture into its draft location, set the current architecture path to draft, record the current architecture revision with `state=draft`, and populate `automation_state.derived_from`.
27. Resolve security activation according to `lane_decisions.security_mode`. If active, run Threat Modeling and Security Architecture Review and set `lane_outcomes.security=in_progress`; otherwise set the lane outcome to `skipped` or `not_applicable`.
28. Run system-level test design and record its revision and source revisions.
29. Run CI/CD alignment.
30. Write `auto-plan-architecture-gate.md`, set `review_artifacts.architecture_gate`, set architecture approval to pending, set `automation_state.pending_approval`. If `{oversight_mode}` is `true`, run the oversight checkpoint workflow (`{project-root}/_bmad/compass/0-governance/bmad-compass-oversight-checkpoint/workflow.md`) with `gate_name` set to `architecture` before presenting the approval request. Include the checkpoint report in the gate artifact. Stop for architecture approval.
31. If architecture approval is rejected, mark the architecture gate rejected, downgrade readiness approval, append stale-output records for architecture-dependent outputs, clear `automation_state.pending_approval`, and stop.
32. If architecture approval is granted, approve the current architecture revision, clear `automation_state.pending_approval`, and if the security lane was active set `lane_outcomes.security=complete`.
33. Draft epics and story inputs into `current/planning/epics/draft/` and `current/implementation/stories/draft/`, set their current paths to draft, record their current revisions with `state=draft`, create or reconcile draft Beads issues for the epic and story work, record the ids in the run state, and populate `automation_state.derived_from`.
34. If the security lane is active, run Secure Readiness Gate.
35. Draft implementation-readiness outputs and write `current/testing/gates/draft/auto-plan-readiness-summary.md`, record the current readiness revision with `state=draft`, set `review_artifacts.readiness_gate`, and record its source revisions.
36. Set readiness approval to pending, set `automation_state.pending_approval`. If `{oversight_mode}` is `true`, run the oversight checkpoint workflow (`{project-root}/_bmad/compass/0-governance/bmad-compass-oversight-checkpoint/workflow.md`) with `gate_name` set to `readiness` before presenting the approval request. Include the checkpoint report in the gate artifact. Stop for implementation-readiness approval.
37. If readiness approval is rejected, keep epics, stories, and readiness outputs in draft locations, mark the rejected readiness package stale as needed, clear `automation_state.pending_approval`, and stop.
38. If readiness approval is granted, approve the readiness revision, promote approved epics and stories out of `draft/`, promote the readiness summary into its canonical gate location, write `auto-plan-report.md`, run `bd sync`, update `beads.last_synced_at`, and mark solutioning complete.

Required state transitions:

- After step 2, create `auto-plan-state.yaml`, initialize gate markers to `not_requested`, initialize `automation_state.pending_approval=null`, initialize `automation_state.stale_outputs=[]`, initialize `beads.parent_issue_id=""`, `beads.phase_issue_id=""`, `beads.active_epic_issue_id=""`, `beads.active_story_issue_id=""`, `beads.follow_up_issue_ids=[]`, initialize artifact revision objects to `not_started` unless the artifact already exists, initialize `lane_outcomes.storytelling=pending`, `lane_outcomes.wds=not_applicable`, and `lane_outcomes.security=not_applicable`, and do not create canonical `phase-state.yaml` yet.
- After step 12, canonical roadmap state becomes approved and `automation_state.last_completed_checkpoint=roadmap_approved`.
- After step 13, create or update canonical `phase-state.yaml`, copy the aligned machine fields from `auto-plan-state.yaml`, and set `workflow_status.phase_sync=complete`.
- After step 15, set `workflow_status.detailed_analysis=complete` and `next_checkpoint=Draft PRD for active slice`.
- After step 23, set `workflow_status.planning_experience=in_progress`.
- After step 25, set `workflow_status.planning_experience=complete`.
- After step 26, set `workflow_status.solutioning=in_progress`.
- After step 38, set `workflow_status.solutioning=complete`, move epics and stories to canonical locations, update approved revision fields for epics, stories, and readiness, set `review_artifacts.readiness_gate` to the approved location, and set `next_checkpoint=Begin sprint planning`.
- After canonical `phase-state.yaml` exists, every checkpoint update must be written to both `auto-plan-state.yaml` and `phase-state.yaml`.

Invalidation and regeneration rules:

- If roadmap approval is rejected, do not modify canonical roadmap files, keep the roadmap proposal as the only reviewer-facing draft, and keep `auto-plan-state.yaml` as the only machine-readable draft state source.
- If PRD approval is rejected or the PRD revision changes materially, append structured stale-output records for WDS, architecture, draft epics/stories, and readiness outputs, downgrade architecture and readiness approvals, and clear any `derived_from` entries that depend on the rejected PRD revision.
- If architecture approval is rejected or the architecture revision changes materially, append structured stale-output records for security review outputs, system test design, draft epics/stories, and readiness outputs, downgrade readiness approval, and clear any `derived_from` entries that depend on the rejected architecture revision.
- If readiness approval is rejected, keep draft epics/stories and readiness outputs in draft locations and do not promote them into canonical execution locations.
- Resume must regenerate every output listed in `automation_state.stale_outputs` before continuing.
- Resume must also regenerate any output whose `automation_state.derived_from.<artifact_key>.source_revisions` no longer match current `artifact_revisions`.

## Approval Checkpoints

- Roadmap activation or major roadmap reordering via `current/implementation/evidence/auto-plan-roadmap-proposal.md`
- Final PRD acceptance via `current/implementation/evidence/auto-plan-prd-gate.md`
- Final architecture acceptance via `current/implementation/evidence/auto-plan-architecture-gate.md`
- Implementation-readiness approval via `current/testing/gates/draft/auto-plan-readiness-summary.md`
- Security-lane activation when the activation mode is not already settled

## Failure Handling

- Write `partial-failure-report.md` output to `current/implementation/evidence/auto-plan-failure.md`.
- If the failure occurs before `Phase Sync`, also write the fallback preflight failure artifact.
- Always record the failure in `auto-plan-state.yaml`.
- If canonical `phase-state.yaml` exists, also set its `status` to `blocked`.
- If canonical `phase-state.yaml` exists, also record `automation_state.last_failure_report`.
- If canonical `phase-state.yaml` exists, also record `automation_state.last_completed_step`.
- Keep completed artifacts and record the last successful step.

## Resume Behavior

- If `--resume` is used, inspect `auto-plan-state.yaml` first, then reconcile with `phase-state.yaml` if it exists.
- Before `Phase Sync`, `auto-plan-state.yaml` is the sole machine-readable resume source.
- `auto-plan-roadmap-proposal.md` is the only reviewer-facing roadmap draft artifact.
- `auto-plan-report.md` is never used to determine resume position.
- Accepted outputs are only those with the corresponding gate approved, matching approved revisions, no stale-output record, and `derived_from` source revisions that match current `artifact_revisions`.
- Skip completed steps only when outputs are accepted.
- Restart from the first missing, rejected, or revision-mismatched checkpoint.
- If an approval was denied, resume from the first step associated with the denied checkpoint after stale outputs are regenerated.
- If a lane is marked `skipped` or `not_applicable`, resume must not infer work for that lane from missing files.

## Final Outputs

- Active roadmap state
- `auto-plan-state.yaml` as the canonical runtime record for the wrapper
- Active phase state
- Beads references for the approved roadmap slice plus drafted epic or story work
- Reviewer-facing gate artifacts for roadmap, PRD, architecture, and readiness
- Detailed-analysis artifacts
- PRD and WDS outputs aligned to the current accepted PRD revision
- Architecture outputs aligned to the current accepted architecture revision
- Approved epics and stories promoted out of `draft/` only after readiness approval
- Explicit lane outcome declarations for storytelling, WDS, and security in both runtime state and the readiness handoff
- `auto-plan-readiness-summary.md` as the canonical implementation-readiness handoff artifact only after readiness approval
- `auto-plan-report.md` as the execution log and run summary, not a resume surface

## Example Invocation

```text
auto-plan --phase-id phase-002 --mode brownfield --approval-mode manual
```

## Example Outcome

- Brownfield repo context is refreshed.
- A roadmap proposal is drafted, then the canonical roadmap is updated only after approval.
- `auto-plan-state.yaml` carries the checkpoint state from preflight through readiness.
- Roadmap slice `phase-002` is activated only after roadmap approval.
- WDS-triggered PRD edits force a second validation pass before the PRD gate can open.
- Detailed analysis, PRD, WDS, architecture, security artifacts when applicable, test design, CI/CD alignment, and readiness artifacts are drafted across staged approval checkpoints.
- Epics, stories, and readiness outputs stay in `draft/` locations until readiness approval is granted.
- Human review remains required at roadmap, PRD, architecture, and readiness gates.
