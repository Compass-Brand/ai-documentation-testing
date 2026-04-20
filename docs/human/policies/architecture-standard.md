# Architecture Documentation Standard

## Purpose

Define mandatory architecture documentation for system understanding, decision traceability, and long-term maintainability.

## Scope

Applies to `docs/architecture/` and architecture-relevant content elsewhere in project docs.

## Requirements

### 1. Required architecture artifacts

Projects MUST maintain:

- ADRs in `docs/architecture/decisions/`,
- an architecture overview (`docs/architecture/README.md` or equivalent),
- current system boundaries, integrations, and data flow overview.

Rationale: architecture visibility reduces onboarding time and makes system-level decisions auditable.

Implementation Playbook (Mandatory):

1. Establish architecture overview before major feature expansion.
2. Keep architecture index updated when adding or removing architecture docs.
3. Link operational and development guides where architecture impacts implementation.

### 2. System overview requirements

System overview docs MUST describe:

- integration boundaries,
- major components and their responsibilities,
- what the system does,
- who it serves.

Rationale: teams need shared system context before component-level decisions can be evaluated correctly.

Implementation Playbook (Mandatory):

1. Keep a high-level component list and responsibilities table.
2. Update boundaries when integrations or service topology changes.
3. Reconcile overview against current deployment model during quarterly review.

### 3. ADR requirements

ADRs MUST:

- define status, context, decision, and consequences,
- list alternatives considered,
- reference superseding ADRs when deprecated,
- use sequential numbering (`0001-...`, `0002-...`).

ADRs SHOULD be written for decisions expensive to reverse.

Rationale: ADR discipline captures rationale at decision time, preventing future guesswork and repeated debates.

Implementation Playbook (Mandatory):

1. Create ADR at the time a significant decision is made.
2. Update status transitions (`Proposed`, `Accepted`, `Deprecated`, `Superseded`) as decisions evolve.
3. Add supersedes links when replacing prior ADRs.

### 4. Component deep-dive requirements

Component deep-dive docs MUST include:

- failure modes and operational impacts,
- inbound and outbound dependencies,
- key interfaces and contracts,
- responsibilities and ownership.

Rationale: component-specific clarity reduces coupling errors and incident resolution time.

Implementation Playbook (Mandatory):

1. Document each major component with ownership and dependency context.
2. Update deep-dives when interfaces or dependencies change.
3. Link deep-dives back to system overview and ADRs.

### 5. Diagram standards

Mermaid SHOULD be the default diagram format.
Diagrams MUST include title and scope.
C4 model levels SHOULD be used for complex systems (component, container, context).
When Mermaid diagrams contain ordered node or item lists, entries MUST be sorted alphabetically using standard file-explorer ordering.

Rationale: diagrams-as-code keep visuals reviewable and versioned while preserving shared architecture language.

Implementation Playbook (Mandatory):

1. Keep diagram source in markdown.
2. Choose diagram type by intent (context, flow, sequence, state).
3. Sort ordered Mermaid node or item lists alphabetically before merge.
4. Validate diagram readability during pull request review.

### 6. Change synchronization requirements

Architecture docs MUST be updated when any of the following change:

- data flow,
- deployment topology,
- major dependencies,
- service ownership,
- system boundaries.

Rationale: architecture documentation is only useful if it reflects actual system behavior.

Implementation Playbook (Mandatory):

1. Include architecture-impact check in pull requests.
2. Update relevant architecture docs in the same change set.
3. Flag unresolved architecture drift as non-compliant.

### 7. Operational linkage requirements

Architecture docs SHOULD link to implementation guides, runbooks, and reference docs where available.

Rationale: architecture context is most valuable when it leads directly to actionable operational resources.

Implementation Playbook (Mandatory):

1. Add related links to runbooks and guides in architecture pages.
2. Verify related links during quarterly review.
3. Remove stale links or replace with current destinations.

## Compliance checks

- ADR index and numbering are valid.
- ADR statuses and supersession links are accurate.
- Architecture docs are updated alongside major design changes.
- Architecture overview exists and is current.
- Component deep-dives exist for major components.
- Diagrams include title and scope.

## Exceptions

Exceptions MUST follow `documentation-governance.md`.

## Related

- `../templates/adr.md`
- `docs-structure-standard.md`
- `documentation-governance.md`
- `guides-standard.md`
- `style-standard.md`
