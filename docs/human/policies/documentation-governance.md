# Documentation Governance Standard

## Purpose

Define mandatory governance for human-facing documentation across company projects.

## Scope

Applies to root-level policy files, the `docs/` tree, and all human-facing documentation maintained in-repo.

## Requirements

### 1. Baseline artifact requirements

Every project MUST include these root files:

- `CHANGELOG.md`
- `CODE_OF_CONDUCT.md`
- `CONTRIBUTING.md`
- `LICENSE`
- `README.md`
- `SECURITY.md`

Every project MUST include a `docs/` directory aligned with `docs-structure-standard.md`.

Rationale: a fixed baseline reduces onboarding friction, avoids policy drift between repos, and ensures legal/community files are always present.

Implementation Playbook (Mandatory):

1. Verify root file presence during repository setup.
2. Add missing baseline files before feature work begins.
3. Confirm `docs/` structure against the structure standard in every docs-focused pull request.

### 2. Documentation ownership and approval

Each project MUST assign at least one documentation owner.
Policy-level documentation changes MUST be approved by a documentation owner.

Rationale: standards without clear ownership degrade over time, and policy changes require accountable decision-makers.

Implementation Playbook (Mandatory):

1. Record documentation owner(s) in team ownership metadata or equivalent.
2. Require owner approval in pull requests that change policy docs.
3. Escalate unowned docs areas before accepting structural policy changes.

### 3. Documentation lifecycle control

Human docs MUST follow lifecycle states: draft, active, deprecated, archived.
Deprecated docs MUST include a replacement link or deprecation reason.

Rationale: lifecycle visibility prevents stale docs from being mistaken as current truth.

Implementation Playbook (Mandatory):

1. Mark lifecycle state in document metadata or heading note.
2. Add a replacement link when deprecating.
3. Remove or archive obsolete docs during major version shifts.

### 4. Review cadence

Human documentation MUST be reviewed at least once per quarter.
Operationally sensitive docs SHOULD include `Last reviewed: YYYY-MM-DD`.

Rationale: scheduled reviews catch behavioral drift that ad-hoc edits miss.

Implementation Playbook (Mandatory):

1. Schedule quarterly documentation review windows.
2. Track reviewed files and owners in team review notes.
3. Update `Last reviewed` fields when validating operational docs.

### 5. Quality gates for documentation changes

Human docs changes MUST satisfy:

- consistent core terminology,
- no broken internal links,
- no unresolved placeholders (`TODO`, `TBD`, `coming soon`),
- runnable or clearly marked illustrative code examples.

Rationale: hard quality gates protect reader trust and reduce avoidable support load.

Implementation Playbook (Mandatory):

1. Run link validation before merge.
2. Search for placeholder tokens and remove them.
3. Execute command examples where feasible, or mark as illustrative.
4. Check terminology against project glossary or established terms.

### 6. Drift prevention with code changes

Documentation updates MUST be included in the same pull request as behavior changes that affect users, setup, configuration, architecture, or operations.

Rationale: coupling docs and behavior in one change is the strongest anti-drift control.

Implementation Playbook (Mandatory):

1. Add a docs-impact checklist item in pull requests.
2. Require docs updates when behavior or interface changes.
3. Block merges where impacted docs are not updated.

### 7. Exceptions

Exceptions to this standard MUST include:

- business or technical rationale,
- expiry date,
- owner,
- remediation plan,
- scope.

Expired exceptions MUST be treated as non-compliant.

Rationale: exception records are necessary for temporary flexibility without permanent standards erosion.

Implementation Playbook (Mandatory):

1. Record exceptions in the target repository.
2. Assign an accountable owner and expiry date.
3. Review exceptions in each quarterly documentation cycle.

### 8. Promotion from planning artifacts

Planning artifacts in `planning/` MAY graduate into the repo `docs/` tree only when all of the following are true:

- the content is stable for the current phase or repo baseline,
- an owner is assigned,
- lifecycle state is set,
- the destination docs location is defined,
- the artifact has been reviewed for structure, terminology, and links,
- a replacement link or archive note is recorded if the planning artifact will later be frozen or superseded.

Rationale: planning artifacts are intentionally volatile. Promotion without explicit ownership and lifecycle metadata turns working notes into accidental source-of-truth docs.

Implementation Playbook (Mandatory):

1. Record the promotion candidate in planning closeout or docs update evidence.
2. Assign owner, lifecycle state, and destination path before moving content into `docs/`.
3. Preserve a link from the promoted doc back to the stabilizing planning artifact or decision.
4. Do not promote automation runtime files, gate packages, or phase-specific working evidence into `docs/`.

## Compliance checks

- Baseline root files are present.
- Docs and code changes are coupled when required.
- Documentation owner is assigned.
- Exception records are complete and unexpired.
- No unresolved placeholders remain.
- Quarterly review evidence exists.
- Promotions from planning artifacts include owner, lifecycle state, destination, and replacement or archive notes.

## Related

- `../templates/readme-docs-index.md`
- `../templates/readme-root.md`
- `architecture-standard.md`
- `docs-structure-standard.md`
- `guides-standard.md`
- `style-standard.md`
