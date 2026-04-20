# Security Activation Note

Use the conditional CYBERSEC lane when either the repo heuristics or the project owner indicate that security risk is materially above baseline delivery work.

## Activate The Security Lane When One Or More Apply

- authentication, authorization, or permissions logic is central to the slice
- the slice handles customer, financial, health, or other sensitive data
- the slice introduces public-facing endpoints, apps, or external integrations
- regulatory, contractual, or audit-oriented security artifacts are required
- the slice changes trust boundaries, secrets handling, or cross-system data flows
- the user explicitly requests threat modeling, security review, or secure gates

## Phase-State Expectations

When the lane is active, set the following in `phase-state.yaml`:

- `lane_decisions.security_mode` to `auto` or `manual`
- `lane_decisions.security_active` to `true`
- `lane_outcomes.security` to `in_progress` when threat modeling or review starts

When the lane is not active:

- `lane_decisions.security_active` remains `false`
- `lane_outcomes.security` should be `skipped` or `not_applicable`

## Output Destinations

- threat models: `planning/current/planning/architecture/threat-modeling/`
- security reviews: `planning/current/planning/architecture/security-review/`
- secure readiness gate drafts: `planning/current/testing/gates/draft/security/`
- approved secure readiness gate reports: `planning/current/testing/gates/security/readiness/`
- secure release gate reports: `planning/current/testing/gates/security/release/`

## Commands In The Active BMM Layer

- `/bmad-cybersec-threat-modeling`
- `/bmad-cybersec-security-architecture-review`
- `/bmad-cybersec-secure-gates`
