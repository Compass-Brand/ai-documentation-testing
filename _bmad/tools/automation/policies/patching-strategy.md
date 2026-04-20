# Patching Strategy Policy

## Purpose

Define how automation mutates planning, evidence, and draft artifacts without corrupting canonical state or making resume behavior ambiguous.

## Core Rules

1. Machine files update first. Human-readable files update second.
2. Draft artifacts are written before approval. Canonical artifacts are updated only after approval.
3. Promotions from draft to canonical must be explicit, never implied by file presence.
4. Automation must preserve enough evidence to explain what changed, why, and from which source revisions.
5. Partial failure must leave the repo in a resumable state.

## Draft Versus Canonical Writes

### Draft-first rule

Use draft locations for:

- roadmap proposals
- PRD gate packages
- architecture gate packages
- draft epics
- draft stories
- readiness gate packages
- secure readiness gate packages

### Canonical write rule

Only write canonical locations when:

- the relevant approval checkpoint is `approved`
- the approved revision matches the current revision
- there is no stale-output record for the artifact

## Write Order

### Roadmap-level changes

1. Draft proposal artifact
2. Update runtime state
3. Stop for approval
4. Update `roadmap.yaml`
5. Update `roadmap.md`

### Phase entry

1. Update machine phase state
2. Update human phase brief
3. Begin downstream planning

### Phase closeout

1. Update machine phase state
2. Update roadmap machine state
3. Update human roadmap summary
4. Update human phase closeout notes if needed
5. Archive current phase

## Reuse Scan Rule

Before `Dev Story`, automation must perform a reuse scan in this order:

1. existing UI components
2. existing domain services
3. existing data-access layers and queries
4. existing integration clients
5. existing shared utilities and types
6. existing test fixtures and helpers
7. prior architectural patterns and ADRs

Required evidence:

- a short reuse note in `current/implementation/evidence/`
- what was searched
- what candidates were found
- what was reused or extended
- if net-new code is introduced, why reuse or extension was not chosen

Allowed justifications for net-new code:

- no suitable existing asset exists
- the existing asset is unsafe to extend
- extension would create worse coupling than a new isolated unit
- regulatory or security isolation requires a separate implementation

## Review Tooling Boundary

- CodeRabbit or similar tooling is checkpoint automation at story-exit or PR boundaries.
- It is not a mandatory per-commit requirement.
- Automated review output should supplement, not replace, code review and test review artifacts.

## Failure-Safe Writes

On failure:

- write a partial-failure report
- record the failure in runtime state
- preserve completed artifacts
- record the last successful step and checkpoint
- do not silently promote draft artifacts

If failure happens before `Phase Sync`, also write the deterministic preflight failure artifact.

## Promotion Rules

Promote draft artifacts only when:

- approval is accepted
- current revision equals requested revision
- derived inputs still match
- no stale-output record remains

When promoting:

- update `artifact_paths.current` to canonical
- update `artifact_revisions.approved`
- set `artifact_revisions.state=approved`
- clear or supersede the relevant draft record

## Anti-Patterns

- updating canonical roadmap state before approval
- writing approved epics or stories before readiness approval
- using report markdown files as resume state
- overwriting prior dated gate reports without explicit intent
- silently closing an epic, phase, or merge gate without human review
