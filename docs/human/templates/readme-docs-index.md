# Docs Index README Template

## Intended Use

Use this template for `docs/README.md` as the top-level index for a project's documentation tree.

## Required Sections

The following sections are mandatory:

1. Audience and how to use this docs set
2. Docs title and scope
3. Documentation map
4. Maintenance and review ownership
5. Recommended reading paths
6. Related policy links

## Template

# Documentation

[One paragraph explaining what this docs set covers and what it does not cover]

## Audience

- [Primary audience 1]
- [Primary audience 2]

## How to Use This Documentation

- Start in `getting-started/` if you are new.
- Use `architecture/` for system design and decisions.
- Use `development/` for contributor workflows and standards.
- Use `guides/` for task-oriented procedures.
- Use `reference/` for exact behavior and configuration details.

## Documentation Map

- Architecture
  - `architecture/decisions/README.md`
  - `architecture/README.md`
- Development
  - `development/README.md`
- Getting started
  - `getting-started/installation.md`
  - `getting-started/quickstart.md`
  - `getting-started/README.md`
- Guides
  - `guides/README.md`
- Reference
  - `reference/README.md`

## Recommended Reading Paths

### New developer path

1. `getting-started/installation.md`
2. `getting-started/quickstart.md`
3. `development/README.md`
4. `architecture/README.md`

### Operator path

1. `reference/README.md`
2. Relevant task guide in `guides/`
3. Related architecture docs

## Maintenance

- Last reviewed: [YYYY-MM-DD]
- Owner: [team or role]
- Review cadence: [quarterly/monthly]

## Related Standards

- [Link to company documentation governance standard]
- [Link to company documentation structure standard]
- [Link to company documentation style standard]

## Section Rationale

- Audience and usage instructions prevent misrouting readers to the wrong doc type.
- Documentation map provides deterministic navigation.
- Maintenance metadata makes accountability explicit and supports anti-drift reviews.
- Reading paths reduce onboarding ambiguity for common personas.
