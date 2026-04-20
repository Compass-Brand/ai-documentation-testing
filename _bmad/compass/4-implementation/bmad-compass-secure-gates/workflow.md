---
name: secure-gates
description: 'Apply the conditional secure readiness gate or secure release gate for security-active Compass slices.'
---

# Secure Gates Workflow

**Goal:** Evaluate whether the active slice satisfies the conditional security gate before implementation begins or before release proceeds.

**Your Role:** You are a security reviewer using the Compass gate contract to decide whether security evidence is sufficient to proceed, what is blocked, and what residual risk must be explicitly accepted.

## CONFIGURATION

Load config from `{project-root}/_bmad/bmm/module.yaml` and resolve:

- `project_name`, `planning_current`
- `phase_state_file`
- `current_architecture_dir`, `current_threat_modeling_dir`, `current_security_review_dir`
- `current_epics_dir`, `current_story_dir`
- `current_testing_reviews_dir`, `current_testing_gates_dir`, `current_testing_gates_draft_dir`
- `current_secure_readiness_gate_dir`, `current_secure_release_gate_dir`, `current_secure_gates_draft_dir`
- `current_evidence_dir`
- `user_name`, `communication_language`, `document_output_language`
- `date` as a system-generated value (`YYYY-MM-DD`)

Also read:

- `{project-root}/_bmad/compass/0-governance/security-activation.md`
- `{project-root}/_bmad/compass/4-implementation/bmad-compass-secure-gates/secure-gate-criteria.yaml`
- `{phase_state_file}` if it exists

## EXECUTION

1. Confirm whether the security lane is active.
   - If `phase-state.yaml` exists and `lane_decisions.security_active != true`, stop and report that the secure gate is not applicable.
   - If no phase state exists, require the user to confirm that the slice is security-active before proceeding.
2. Determine gate mode.
   - If the command was invoked from the solutioning lane or explicitly requested as readiness, use `readiness`.
   - If the command was invoked from the release gate or explicitly requested as release, use `release`.
   - If the mode is ambiguous, stop and ask whether to run the readiness gate or the release gate.
3. For `readiness` mode:
   - verify the required artifacts listed in `secure-gate-criteria.yaml`
   - read the latest threat model and security review documents
   - check for unresolved blocking findings and missing security story coverage
   - write a draft report to `{current_secure_gates_draft_dir}/secure-readiness-gate-{date}.md`
   - if the user confirms acceptance, promote or copy the approved report to `{current_secure_readiness_gate_dir}/secure-readiness-gate-{date}.md`
4. For `release` mode:
   - verify release evidence, sprint status, review artifacts, and any available security evidence
   - if penetration-test or security-scan reports are expected but missing, mark the gate blocked or warning according to the project context
   - write the report to `{current_secure_release_gate_dir}/secure-release-gate-{date}.md`
5. Every gate report must include:
   - gate mode and boundary
   - artifacts checked
   - blocking findings
   - warnings and residual risks
   - signoff expectations
   - pass / pass-with-risk / blocked recommendation
   - explicit next actions
6. When `phase_state_file` exists, update the phase-state references that this workflow can safely own:
   - if a readiness gate draft is created, add the report path to `review_artifacts.readiness_gate` when appropriate
   - do not mark implementation readiness approved here; this workflow informs the gate, it does not replace human approval

## OUTPUT RULES

- Security gate output must stay in the testing gates lane.
- Use `draft/security/` while approval is pending.
- Do not overwrite prior reports without clear user intent; create date-stamped files.
- If the gate is blocked, state the blocking conditions first.
